#!/usr/bin/env python3
"""Script d'integració end-to-end: temporada 2026-27 d'un nedador.

Ús:
    python scripts/generar_temporada.py --nedador jep [--dilluns 2026-10-05]

Les dades es llegeixen de data/nedadors/<id>/ (nedador.json, calendari.json,
historial.json) i del catàleg comú data/competicions.json; les sortides van a
la mateixa carpeta del nedador (vegeu blondswim.rutes).

Encadena: generar_macrocicle() -> periodificació de la temporada (taula) ->
generar_mesocicle() del bloc que conté la setmana objectiu ->
contingut LLM i Excel.

Per defecte (G1/G6) genera el contingut NOMÉS de la setmana que comença el
proper dilluns (o el dilluns de --dilluns) i l'exporta a
setmanes/setmana_<id>_<YYYY>-W<ww>.xlsx. Amb --mesocicle-sencer recupera el
comportament anterior (tot el mesocicle, setmanes/mesocicle_<id>_<meso>.xlsx).

Fase E+I: llegeix els fulls de registre omplerts de
data/nedadors/<id>/registres/ (registre_*.xlsx), avalua la recuperació de la
setmana anterior (càrrega sRPE, SRSS, sèrie de control) i, en mode setmana,
crea el full de registre en blanc de la setmana generada (no sobreescriu un
full que ja existeix).
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import anthropic
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents import carrega, recuperacio
from blondswim.agents.context_competicio import validar_espaiat_pics_a
from blondswim.agents.generar_macrocicle import generar_macrocicle, generar_mesocicle
from blondswim.agents.generar_microcicle import (
    generar_contingut_mesocicle,
    generar_contingut_setmana,
)
from blondswim.agents.periodificacio import _dilluns_de, avui, periodificar_temporada
from blondswim.agents.pla_setmanal import DIES_PLANTILLA, usa_plantilla
from blondswim.agents.progressio import avaluar_pic, format_informe
from blondswim.agents.proves import validar_objectius
from blondswim.agents.taper import generar_pla_taper_temporada
from blondswim.export.mesocicle_excel import exportar_mesocicle_excel, exportar_setmana_excel
from blondswim.export.registre_excel import exportar_registre_setmana
from blondswim.ingestion.registre_setmana import carregar_registres
from blondswim.models.calendari import competicions_planificacio
from blondswim.rutes import (
    RutesNedador,
    carregar_competicions,
    carregar_historial,
    carregar_nedador,
    carregar_resultats,
    llistar_nedadors,
)
from blondswim.utils.dates import seguent_dilluns

TEMPORADA_DATA_INICI = "2026-08-18"
TEMPORADA_DATA_FI = "2027-07-09"


def _imprimir_taula_periodificacio(plans) -> None:
    """Imprimeix la taula de periodificació per revisar-la manualment."""
    print("\n   Setmana ISO | Dates                 | Fase      | Bloc     | Desc. | B/C")
    print("   " + "-" * 78)
    for p in plans:
        bc = ", ".join(f"{c.classe}:{c.nom}" for c in p.competicions_b_c) or "-"
        desc = "SÍ" if p.es_descarrega else "  "
        dates = f"{p.dilluns:%d/%m/%Y}-{p.diumenge:%d/%m/%Y}"
        print(
            f"   {p.setmana_iso:>2}/{p.any_iso}     | {dates} | "
            f"{p.fase:<9} | {p.bloc_id:<8} | {desc}    | {bc}"
        )


TIPUS_AVIS_FRANGES = {"separacio_insuficient", "gimnas_dia_no_recomanat"}


def _avaluar_recuperacio(registres_dir: Path, dilluns_objectiu: date) -> None:
    """Imprimeix les alertes de recuperació de la setmana anterior."""
    if not registres_dir.exists():
        print(f"   · Encara no hi ha fulls de registre ({registres_dir})")
        return
    try:
        registre = carregar_registres(registres_dir)
    except ValueError as e:
        print(f"   ✗ Error llegint els fulls de registre: {e}")
        return
    print(
        f"   ✓ Registre: {len(registre.sessions)} sessions, {len(registre.srss)} SRSS, "
        f"{len(registre.controls)} sèries de control"
    )
    estats = carrega.evolucio_carrega(registre.sessions)
    if estats:
        ultim = estats[-1]
        print(
            f"   · Càrrega a {ultim.dia:%d/%m}: aguda {ultim.aguda:.0f}, "
            f"crònica {ultim.cronica:.0f}, balanç {ultim.balanc:+.0f} UA/dia"
        )
    setmana_anterior = dilluns_objectiu - timedelta(weeks=1)
    avisos = recuperacio.avaluar_setmana(
        setmana_anterior, registre.sessions, registre.srss, registre.controls
    )
    if not avisos:
        print(f"   ✓ Setmana del {setmana_anterior:%d/%m}: cap alerta de recuperació")
    for avis in avisos:
        print(f"   ⚠ {avis['missatge']}")


def _informe_progressio(rutes, nedador, competicions, data: date) -> None:
    """Imprimeix la progressió cap a l'objectiu A (no atura la generació si falla)."""
    try:
        resultats = carregar_resultats(rutes)
    except (ValueError, ValidationError) as e:
        print(f"   ✗ Error llegint {rutes.resultats}: {e}")
        return
    avisos = validar_objectius(nedador, competicions, resultats, data)
    pic, estats = avaluar_pic(nedador, competicions, resultats, data)
    for linia in format_informe(pic, estats, avisos):
        print(f"   {linia}" if linia else "")


def main() -> int:
    import logging
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Genera la temporada 2026-27 d'un nedador.")
    parser.add_argument(
        "--nedador",
        required=True,
        help="Identificador del nedador (nom de la carpeta a data/nedadors/)",
    )
    parser.add_argument(
        "--data-referencia",
        type=str,
        default=None,
        help="Data de referència (YYYY-MM-DD). Per defecte, avui.",
    )
    parser.add_argument(
        "--dilluns",
        type=str,
        default=None,
        help=(
            "Dilluns de la setmana a generar (YYYY-MM-DD). "
            "Per defecte, el proper dilluns a partir de la data de referència."
        ),
    )
    parser.add_argument(
        "--piscina",
        type=int,
        choices=[25, 50],
        default=None,
        help="Piscina dels entrenaments (m). Per defecte, la de la fitxa (25).",
    )
    parser.add_argument(
        "--mesocicle-sencer",
        action="store_true",
        help="Genera el contingut de tot el mesocicle (comportament antic).",
    )
    args = parser.parse_args()

    data_referencia = (
        date.fromisoformat(args.data_referencia) if args.data_referencia else None
    )
    if args.dilluns:
        dilluns_objectiu = date.fromisoformat(args.dilluns)
        if dilluns_objectiu.weekday() != 0:
            print(f"✗ --dilluns {args.dilluns} no és un dilluns")
            return 2
    else:
        dilluns_objectiu = seguent_dilluns(data_referencia or avui())

    arrel_dades = Path(__file__).parent.parent / "data"
    try:
        rutes = RutesNedador(args.nedador, arrel_dades)
        nedador = carregar_nedador(rutes)
        if args.piscina:
            nedador = nedador.model_copy(update={"piscina_m": args.piscina})
        totes_competicions = carregar_competicions(rutes)
        historial = carregar_historial(rutes)
    except FileNotFoundError as e:
        print(f"✗ {e}")
        return 2
    except ValueError as e:
        print(f"✗ {e}")
        disponibles = ", ".join(llistar_nedadors(arrel_dades)) or "cap"
        print(f"  Nedadors disponibles: {disponibles}")
        return 2
    # Les simulacions (contrarellotges en entrenament) només serveixen per a la
    # progressió: no alteren la planificació.
    competicions = competicions_planificacio(totes_competicions)
    if not competicions:
        print(f"⚠ {rutes.calendari} buit o inexistent: temporada sense competicions")

    print("=" * 80)
    print(f"GENERACIÓ COMPLETA DE TEMPORADA 2026-27 — {nedador.nom.upper()}")
    print("=" * 80)

    print(f"\n1. Dades carregades de {rutes.carpeta}")

    print(f"   ✓ Nedador: {nedador.nom} ({nedador.categoria}), piscina {nedador.piscina_m} m")
    print(
        f"   ✓ Competicions: {len(competicions)} "
        f"({sum(1 for c in competicions if c.classe == 'A')} classe A)"
        + (
            f" + {len(totes_competicions) - len(competicions)} simulacions"
            if len(totes_competicions) > len(competicions)
            else ""
        )
    )
    print(f"   ✓ Historial: {len(historial)} sessions")
    if usa_plantilla(nedador):
        print(f"   ✓ Plantilla setmanal: {', '.join(nedador.dies_disponibles)}")
        if nedador.setmana_tipus:
            altres = [
                f"{dia} {slot.franja} ({slot.modalitat}, {slot.durada_min} min)"
                for dia in nedador.setmana_tipus
                for slot in nedador.slots_dia(dia)
                if slot.modalitat != "natacio"
            ]
            print(f"   ✓ Altres sessions: {', '.join(altres) or 'cap'}")
    else:
        print(
            f"   ⚠ dies_disponibles={nedador.dies_disponibles}: no és la plantilla "
            f"{DIES_PLANTILLA}; es fa servir l'esquelet antic"
        )

    print("\n   Recuperació (fulls de registre)...")
    registres_dir = rutes.registres_dir
    _avaluar_recuperacio(registres_dir, dilluns_objectiu)

    print("\n   Progressió cap a l'objectiu A...")
    _informe_progressio(rutes, nedador, totes_competicions, data_referencia or avui())

    print("\n2. Generant macrocicle...")
    macrocicle, avisos_macro = generar_macrocicle(
        nedador_id=nedador.id,
        competicions=competicions,
        temporada_data_inici=TEMPORADA_DATA_INICI,
        temporada_data_fi=TEMPORADA_DATA_FI,
    )
    print(f"   ✓ Macrocicle creat: {TEMPORADA_DATA_INICI} a {TEMPORADA_DATA_FI}")
    for avis in avisos_macro:
        print(f"   ⚠ {avis}")

    print("\n3. Periodificant la temporada...")
    inici_finestra = max(
        _dilluns_de(date.fromisoformat(TEMPORADA_DATA_INICI)),
        dilluns_objectiu,
    )
    plans, avisos_periodificacio = periodificar_temporada(
        competicions,
        inici_finestra,
        date.fromisoformat(TEMPORADA_DATA_FI),
    )
    _imprimir_taula_periodificacio(plans)
    for avis in avisos_periodificacio:
        print(f"   ⚠ {avis}")

    print(f"\n4. Generant el mesocicle que conté la setmana del {dilluns_objectiu:%d/%m/%Y}...")
    mesocicle, avisos = generar_mesocicle(
        nedador=nedador,
        macrocicle=macrocicle,
        competicions=competicions,
        historial=historial,
        enriquir_amb_llm=True,
        data_referencia=dilluns_objectiu,
    )
    print(
        f"   ✓ {mesocicle.nom} ({mesocicle.tipus}): "
        f"setmanes {mesocicle.setmanes}, {len(mesocicle.microcicles)} microcicles, "
        f"volum {mesocicle.volum_min}-{mesocicle.volum_max}m"
    )
    for avis in avisos:
        print(f"   ⚠ {avis}")

    macrocicle_path = rutes.macrocicle
    macrocicle_path.parent.mkdir(parents=True, exist_ok=True)
    with open(macrocicle_path, "w", encoding="utf-8") as f:
        json.dump(macrocicle.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    print(f"\n   ✓ Macrocicle desat a {macrocicle_path}")

    avisos_pics_a = validar_espaiat_pics_a(competicions)
    pla_taper = generar_pla_taper_temporada(competicions, nedador.pics_prioritzats)
    categoria_contingut = (
        nedador.categoria if nedador.categoria in ("absolut", "master") else "absolut"
    )

    if args.mesocicle_sencer:
        print(f"\n5. Generant contingut LLM pel mesocicle sencer ({mesocicle.nom})...")
        print("   (Una petició real a l'API de Claude per sessió de cada setmana)")
        try:
            resultats, avisos_contingut = generar_contingut_mesocicle(
                nedador=nedador,
                macrocicle=macrocicle,
                categoria=categoria_contingut,
                mesocicle_id=mesocicle.id,
                pla_taper=pla_taper,
                avisos_pics_a=avisos_pics_a,
                historial=historial,
            )
        except (anthropic.APIError, ValidationError) as e:
            print(f"   ✗ Error generant contingut: {e}")
            return 1

        print(f"   ✓ Contingut generat per {len(resultats)} setmanes")
        for avis in avisos_contingut:
            print(f"   ⚠ Setmana {avis.get('setmana')}: {avis.get('error')}")

        print("\n6. Exportant a Excel...")
        output_path = rutes.mesocicle_xlsx(mesocicle.id)
        exportar_mesocicle_excel(nedador, mesocicle, resultats, output_path)
        print(f"   ✓ Excel exportat a {output_path}")
    else:
        print(f"\n5. Generant contingut LLM de la setmana del {dilluns_objectiu:%d/%m/%Y}...")
        print("   (Una petició real a l'API de Claude per sessió)")
        try:
            _meso, microcicle, sessions, avisos_validacio = generar_contingut_setmana(
                nedador=nedador,
                macrocicle=macrocicle,
                categoria=categoria_contingut,
                dilluns=dilluns_objectiu,
                pla_taper=pla_taper,
                avisos_pics_a=avisos_pics_a,
                historial=historial,
            )
        except (anthropic.APIError, ValidationError, ValueError) as e:
            print(f"   ✗ Error generant contingut: {e}")
            return 1

        volum = sum(
            ex.volum_m for s in sessions for p in s.estructura.parts for ex in p.exercicis
        )
        natacio = [s for s in sessions if s.modalitat == "natacio"]
        print(f"   · {natacio[0].notes if natacio and natacio[0].notes else ''}")
        print(
            f"   ✓ Setmana {microcicle.setmana} ({microcicle.dates}): "
            f"{len(natacio)} sessions de natació, {volum}m "
            f"(objectiu {microcicle.volum_objectiu}m)"
            + (
                f", {len(sessions) - len(natacio)} de gimnàs/altres"
                if len(sessions) > len(natacio)
                else ""
            )
        )
        if microcicle.volum_objectiu and abs(volum / microcicle.volum_objectiu - 1) > 0.05:
            print(
                f"   ⚠ Volum de la setmana {volum}m: {volum / microcicle.volum_objectiu - 1:+.0%}"
                " respecte a l'objectiu (marge ±5%). Ajusta les sèries principals al full."
            )
        for avis in avisos_validacio:
            if avis.get("tipus") in TIPUS_AVIS_FRANGES:
                print(f"   ⚠ {avis['missatge']}")

        print("\n6. Exportant a Excel...")
        output_path = rutes.setmana_xlsx(dilluns_objectiu)
        exportar_setmana_excel(nedador, mesocicle, microcicle, sessions, output_path)
        print(f"   ✓ Excel exportat a {output_path}")

        registre_path = rutes.registre_xlsx(dilluns_objectiu)
        if registre_path.exists():
            print(f"   · El full de registre ja existeix, no es toca: {registre_path}")
        else:
            exportar_registre_setmana(nedador, microcicle, sessions, registre_path)
            print(f"   ✓ Full de registre (en blanc) a {registre_path}")

    print("\n" + "=" * 80)
    print("GENERACIÓ COMPLETADA")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Script d'integració end-to-end: genera tota la temporada 2026-27 d'en Jep.

Encadena: generar_macrocicle() -> generar_mesocicle() (repetit fins cobrir
tota la temporada) -> generar_contingut_mesocicle() (només pel primer
mesocicle, com a demo -- la resta es generarien mesocicle a mesocicle a
mesura que avança la temporada real) -> exportar_mesocicle_excel().
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import anthropic
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents.context_competicio import validar_espaiat_pics_a
from blondswim.agents.generar_macrocicle import generar_macrocicle, generar_mesocicle
from blondswim.agents.generar_microcicle import generar_contingut_mesocicle
from blondswim.agents.periodificacio import _dilluns_de, avui, periodificar_temporada
from blondswim.agents.taper import generar_pla_taper_temporada
from blondswim.export.mesocicle_excel import exportar_mesocicle_excel
from blondswim.models.calendari import Competicio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.nedador import Nedador

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


def main() -> int:
    import logging
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Genera la temporada 2026-27 d'en Jep.")
    parser.add_argument(
        "--data-referencia",
        type=str,
        default=None,
        help="Data de referència (YYYY-MM-DD). Per defecte, avui.",
    )
    args = parser.parse_args()

    data_referencia = (
        date.fromisoformat(args.data_referencia) if args.data_referencia else None
    )

    base_dir = Path(__file__).parent.parent
    data_processed = base_dir / "data" / "processed"

    print("=" * 80)
    print("GENERACIÓ COMPLETA DE TEMPORADA 2026-27 — JEP")
    print("=" * 80)

    print("\n1. Carregant dades...")
    with open(data_processed / "nedador_jep.json", encoding="utf-8") as f:
        nedador = Nedador(**json.load(f))
    with open(data_processed / "calendari.json", encoding="utf-8") as f:
        competicions = [Competicio(**c) for c in json.load(f)]
    with open(data_processed / "historial_jep.json", encoding="utf-8") as f:
        historial = [SessioRealitzada(**s) for s in json.load(f)]

    print(f"   ✓ Nedador: {nedador.nom} ({nedador.categoria})")
    print(
        f"   ✓ Competicions: {len(competicions)} "
        f"({sum(1 for c in competicions if c.classe == 'A')} classe A)"
    )
    print(f"   ✓ Historial: {len(historial)} sessions")

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
    data_ref_efectiva = data_referencia or avui()
    inici_generacio = data_ref_efectiva + timedelta(days=1)
    inici_finestra = max(
        _dilluns_de(date.fromisoformat(TEMPORADA_DATA_INICI)),
        _dilluns_de(inici_generacio),
    )
    plans, avisos_periodificacio = periodificar_temporada(
        competicions,
        inici_finestra,
        date.fromisoformat(TEMPORADA_DATA_FI),
    )
    _imprimir_taula_periodificacio(plans)
    for avis in avisos_periodificacio:
        print(f"   ⚠ {avis}")

    print("\n4. Generant el mesocicle de la data de referència...")
    mesocicle, avisos = generar_mesocicle(
        nedador=nedador,
        macrocicle=macrocicle,
        competicions=competicions,
        historial=historial,
        enriquir_amb_llm=True,
        data_referencia=data_referencia,
    )
    print(
        f"   ✓ {mesocicle.nom} ({mesocicle.tipus}): "
        f"setmanes {mesocicle.setmanes}, {len(mesocicle.microcicles)} microcicles, "
        f"volum {mesocicle.volum_min}-{mesocicle.volum_max}m"
    )
    for avis in avisos:
        print(f"   ⚠ {avis}")

    output_dir = base_dir / "data" / "processed"
    macrocicle_path = output_dir / "macrocicle_temporada_26_27.json"
    with open(macrocicle_path, "w", encoding="utf-8") as f:
        json.dump(macrocicle.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    print(f"\n   ✓ Macrocicle desat a {macrocicle_path}")

    print(f"\n5. Generant contingut LLM pel mesocicle ({mesocicle.nom})...")
    print("   (Aquesta crida farà una petició real a l'API de Claude per setmana)")

    avisos_pics_a = validar_espaiat_pics_a(competicions)
    pla_taper = generar_pla_taper_temporada(competicions, nedador.pics_prioritzats)
    categoria_contingut = (
        nedador.categoria if nedador.categoria in ("absolut", "master") else "absolut"
    )

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
    output_path = output_dir / f"mesocicle_{nedador.nom.lower()}_{mesocicle.id}.xlsx"
    exportar_mesocicle_excel(nedador, mesocicle, resultats, output_path)
    print(f"   ✓ Excel exportat a {output_path}")

    print("\n" + "=" * 80)
    print("GENERACIÓ COMPLETADA")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

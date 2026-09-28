#!/usr/bin/env python3
"""Script d'integració end-to-end: genera tota la temporada 2026-27 d'en Jep.

Encadena: generar_macrocicle() -> generar_mesocicle() (repetit fins cobrir
tota la temporada) -> generar_contingut_mesocicle() (només pel primer
mesocicle, com a demo -- la resta es generarien mesocicle a mesocicle a
mesura que avança la temporada real) -> exportar_mesocicle_excel().
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents.context_competicio import validar_espaiat_pics_a
from blondswim.agents.generar_macrocicle import generar_macrocicle, generar_mesocicle
from blondswim.agents.generar_microcicle import generar_contingut_mesocicle
from blondswim.agents.taper import generar_pla_taper_temporada
from blondswim.export.mesocicle_excel import exportar_mesocicle_excel
from blondswim.models.calendari import Competicio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.nedador import Nedador

TEMPORADA_DATA_INICI = "2026-08-18"
TEMPORADA_DATA_FI = "2027-07-09"


def main() -> int:
    import logging
    logging.basicConfig(level=logging.INFO)

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

    print("\n3. Generant mesocicles...")
    total_setmanes = (
        datetime.fromisoformat(TEMPORADA_DATA_FI)
        - datetime.fromisoformat(TEMPORADA_DATA_INICI)
    ).days // 7

    tots_els_avisos = list(avisos_macro)
    while True:
        setmanes_assignades = 0
        for meso in macrocicle.mesocicles:
            for micro in meso.microcicles:
                setmanes_assignades = max(setmanes_assignades, micro.setmana)

        if setmanes_assignades >= total_setmanes:
            break

        mesocicle, avisos = generar_mesocicle(
            nedador=nedador,
            macrocicle=macrocicle,
            competicions=competicions,
            historial=historial,
            enriquir_amb_llm=True,
        )
        tots_els_avisos.extend(avisos)
        n_setmanes = len(mesocicle.microcicles)
        print(
            f"   ✓ {mesocicle.nom} ({mesocicle.tipus}): "
            f"setmanes {mesocicle.setmanes}, {n_setmanes} microcicles, "
            f"volum {mesocicle.volum_min}-{mesocicle.volum_max}m"
        )

        if n_setmanes == 0:
            print(
                "   ✗ Mesocicle sense microcicles generats -- "
                "aturant per evitar bucle infinit"
            )
            break

    print(f"\n   Total: {len(macrocicle.mesocicles)} mesocicles generats")
    if tots_els_avisos:
        print(f"   {len(tots_els_avisos)} avisos acumulats:")
        for avis in tots_els_avisos:
            print(f"     ⚠ {avis}")

    output_dir = base_dir / "data" / "processed"
    macrocicle_path = output_dir / "macrocicle_temporada_26_27.json"
    with open(macrocicle_path, "w", encoding="utf-8") as f:
        json.dump(macrocicle.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"\n   ✓ Macrocicle desat a {macrocicle_path}")

    if not macrocicle.mesocicles:
        print("\n✗ Cap mesocicle generat, aturant.")
        return 1

    primer_mesocicle = macrocicle.mesocicles[0]
    print(f"\n4. Generant contingut LLM pel primer mesocicle ({primer_mesocicle.nom})...")
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
            mesocicle_id=primer_mesocicle.id,
            pla_taper=pla_taper,
            avisos_pics_a=avisos_pics_a,
            historial=historial,
        )
    except Exception as e:
        print(f"   ✗ Error generant contingut: {e}")
        return 1

    print(f"   ✓ Contingut generat per {len(resultats)} setmanes")
    for avis in avisos_contingut:
        print(f"   ⚠ Setmana {avis.get('setmana')}: {avis.get('error')}")

    print("\n5. Exportant a Excel...")
    output_path = output_dir / f"mesocicle_{primer_mesocicle.id}.xlsx"
    exportar_mesocicle_excel(nedador, primer_mesocicle, resultats, output_path)
    print(f"   ✓ Excel exportat a {output_path}")

    print("\n" + "=" * 80)
    print("GENERACIÓ COMPLETADA")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

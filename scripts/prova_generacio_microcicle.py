#!/usr/bin/env python3
"""Script manual per provar la generació de microcicle amb dades reals del Jep."""

import json
import sys
from pathlib import Path

# Afegir src al path per poder importar els mòduls
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.agents.generar_microcicle import (
    GeneracioMicrocicleError,
    generar_microcicle,
)
from blondswim.agents.seleccio_model import seleccionar_metodologia
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle
from blondswim.models.nedador import Nedador


def main():
    """Executar prova de generació de microcicle."""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    base_dir = Path(__file__).parent.parent
    data_processed = base_dir / "data" / "processed"

    print("=" * 80)
    print("PROVA DE GENERACIÓ DE MICROCICLE AMB DADES REALS DEL JEP")
    print("=" * 80)

    # 1. Carregar nedador
    print("\n1. Carregant nedador...")
    nedador_path = data_processed / "nedador_jep.json"
    if not nedador_path.exists():
        print(f"   ✗ Error: No s'ha trobat {nedador_path}")
        return 1

    with open(nedador_path, encoding="utf-8") as f:
        nedador_data = json.load(f)
    nedador = Nedador(**nedador_data)
    print(f"   ✓ Nedador carregat: {nedador.nom}")
    print(f"     Proves objectiu: {', '.join(nedador.proves_objectiu)}")
    print(f"     Categoria: {nedador.categoria}")

    # 2. Carregar macrocicle i construir microcicle manual
    print("\n2. Carregant macrocicle...")
    macrocicle_path = data_processed / "macrocicle_jep.json"
    if not macrocicle_path.exists():
        print(f"   ✗ Error: No s'ha trobat {macrocicle_path}")
        return 1

    with open(macrocicle_path, encoding="utf-8") as f:
        macrocicle_data = json.load(f)
    macrocicle = Macrocicle(**macrocicle_data)

    if not macrocicle.mesocicles:
        print("   ✗ Error: No s'ha trobat cap mesocicle al macrocicle")
        return 1

    # Usar primer mesocicle per construir microcicle manual
    mesocicle = macrocicle.mesocicles[0]
    print(f"   ✓ Mesocicle trobat: {mesocicle.nom}")
    print(f"     Dates: {mesocicle.dates}")
    print(f"     Volum mitjà previst: {mesocicle.volum_mitja_previst}m")
    
    print("\n   ⚠ AVÍS: La pestanya Microcicles encara no s'ingereix des de l'Excel.")
    print("   ⚠ Construint un Microcicle manual per a la prova...")
    
    from blondswim.models.macrocicle import Microcicle
    
    primer_microcicle = Microcicle(
        setmana=1,
        dates=mesocicle.dates,
        mesocicle_id=mesocicle.id,
        tipus_base="carrega",
        notes="Setmana de prova manual (Microcicle no ingerit encara des de l'Excel)",
        volum_objectiu=mesocicle.volum_mitja_previst,
        dies_qualitat=False,
        test_css=False,
    )
    
    print(f"   ✓ Microcicle manual creat: Setmana {primer_microcicle.setmana}")
    print(f"     Tipus: {primer_microcicle.tipus_base}")
    print(f"     Volum objectiu: {primer_microcicle.volum_objectiu}m")

    # 3. Carregar historial
    print("\n3. Carregant historial...")
    historial_path = data_processed / "historial_jep.json"
    if not historial_path.exists():
        print(f"   ✗ Error: No s'ha trobat {historial_path}")
        return 1

    with open(historial_path, encoding="utf-8") as f:
        historial_data = json.load(f)
    historial = [SessioRealitzada(**s) for s in historial_data]
    print(f"   ✓ Historial carregat: {len(historial)} sessions")
    if historial:
        print(f"     Període: {historial[0].data} a {historial[-1].data}")

    # 4. Seleccionar metodologia
    print("\n4. Seleccionant metodologia...")
    print("   (Aquesta crida farà una petició real a l'API de Claude)")
    try:
        metodologia = seleccionar_metodologia(
            nedador=nedador,
            prova_objectiu=nedador.proves_objectiu[0],
            categoria=nedador.categoria,
            enriquir_amb_llm=True,
        )
        print(f"   ✓ Metodologia seleccionada: {metodologia.metodologia_principal}")
        print(f"     Complementàries: {', '.join(metodologia.metodologies_complementaries)}")
        print(f"     Força evidència: {metodologia.forca_evidencia}")
        print(f"     Justificació: {metodologia.justificacio[:100]}...")
    except Exception as e:  # noqa: BLE001 — script CLI, volem mostrar qualsevol error
        print(f"   ✗ Error en seleccionar metodologia: {e}")
        return 1

    # 5. Generar esquelet de sessions
    print("\n5. Generant esquelet de sessions...")
    try:
        sessions = generar_esquelet_sessions(nedador, primer_microcicle)
        print(f"   ✓ Esquelet generat: {len(sessions)} sessions")
        for sessio in sessions:
            print(f"     - {sessio.dia}: {sessio.tipus_sessio} ({sessio.volum_total}m)")
    except Exception as e:  # noqa: BLE001 — script CLI, volem mostrar qualsevol error
        print(f"   ✗ Error en generar esquelet: {e}")
        return 1

    # 6. Generar contingut amb LLM
    print("\n6. Generant contingut de microcicle amb LLM...")
    print("   (Aquesta crida farà una petició real a l'API de Claude)")
    try:
        sessions_amb_contingut = generar_microcicle(
            nedador=nedador,
            sessions=sessions,
            metodologia=metodologia,
            historial=historial,
        )
        print("   ✓ Contingut generat correctament")
    except GeneracioMicrocicleError as e:
        print(f"   ✗ Error en generar contingut: {e}")
        return 1
    except Exception as e:  # noqa: BLE001 — script CLI, volem mostrar qualsevol error
        print(f"   ✗ Error inesperat: {e}")
        return 1

    # 7. Imprimir resultats
    print("\n" + "=" * 80)
    print("RESULTATS DE LA GENERACIÓ")
    print("=" * 80)

    for sessio in sessions_amb_contingut:
        print(f"\n{'=' * 80}")
        print(f"SESSIÓ: {sessio.dia.upper()}")
        print(f"Tipus: {sessio.tipus_sessio}")
        print(f"Volum total: {sessio.volum_total}m")
        print(f"{'=' * 80}")

        for part in sessio.estructura.parts:
            # Determinar percentatge segons tipus de sessió
            if sessio.tipus_sessio == "carrega":
                perc = part.percentatge_carrega
            elif sessio.tipus_sessio == "qualitat":
                perc = part.percentatge_qualitat
            else:  # descarrega, taper, transicio
                perc = part.percentatge_descarrega

            volum_part = int(sessio.volum_total * perc / 100)

            print(f"\n  [{part.nom}] ({perc}% = {volum_part}m)")
            print(f"  {'-' * 76}")
            if part.contingut:
                # Indentar contingut per llegibilitat
                for linia in part.contingut.split("\n"):
                    print(f"  {linia}")
            else:
                print("  (Sense contingut generat)")

    print("\n" + "=" * 80)
    print("PROVA COMPLETADA")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

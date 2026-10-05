#!/usr/bin/env python3
"""Registra el resultat d'una prova (competició o simulació) a resultats.json.

Ús:
    python scripts/registrar_resultat.py --nedador jep --competicio 2026-10-17_etapa-1 \\
        --prova "100m Lliure" --temps 1:18.40 \\
        [--parcials 18.3,19.9,20.1,20.1] [--bracades 15,16,17,18] \\
        [--font video] [--notes "setmana de càrrega"] [--substituir] [--simular]

Comprova que la competició sigui al calendari del nedador i que la prova hi
sigui inscrita (si no, avisa). Crea resultats.json si no existeix i en desa una
còpia .bak abans de modificar-lo. Si ja hi ha un resultat d'aquella competició i
prova, cal --substituir.
"""

import argparse
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.models.resultat import ResultatCompeticio
from blondswim.rutes import (
    RutesNedador,
    carregar_competicions,
    carregar_resultats,
    desar_json,
    llistar_nedadors,
)
from blondswim.utils.proves import mateixa_prova
from blondswim.utils.temps import format_temps


def _llista(text: str | None) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()] if text else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra un resultat a resultats.json.")
    parser.add_argument("--nedador", required=True, help="Identificador del nedador")
    parser.add_argument("--competicio", required=True, help="competicio_id del calendari")
    parser.add_argument("--prova", required=True, help='Prova, p. ex. "100m Lliure"')
    parser.add_argument("--temps", required=True, help="Temps: 1:18.40, 1'18\"40 o 78.4")
    parser.add_argument("--parcials", help="Parcials de 25 m separats per comes")
    parser.add_argument("--bracades", help="Braçades per llargada separades per comes")
    parser.add_argument("--font", choices=["video", "cronometre", "oficial"])
    parser.add_argument("--notes")
    parser.add_argument("--substituir", action="store_true",
                        help="Substitueix un resultat existent de la mateixa competició i prova")
    parser.add_argument("--simular", action="store_true", help="No desa res")
    args = parser.parse_args()

    arrel = Path(__file__).parent.parent / "data"
    try:
        rutes = RutesNedador(args.nedador, arrel)
        competicions = carregar_competicions(rutes)
        resultats = carregar_resultats(rutes)
        nou = ResultatCompeticio(
            competicio_id=args.competicio,
            prova=args.prova,
            temps=args.temps,
            parcials_25=_llista(args.parcials),
            bracades_llargada=[int(b) for b in _llista(args.bracades)],
            font=args.font,
            notes=args.notes,
        )
    except ValidationError as e:
        print(f"✗ Dades no vàlides:\n{e}")
        return 2
    except (ValueError, FileNotFoundError) as e:
        print(f"✗ {e}")
        print(f"  Nedadors disponibles: {', '.join(llistar_nedadors(arrel)) or 'cap'}")
        return 2

    comp = next((c for c in competicions if c.id == args.competicio), None)
    if comp is None:
        print(f"✗ '{args.competicio}' no és al calendari de {args.nedador}. Competicions:")
        for c in competicions:
            print(f"    {c.id}")
        return 2
    if not any(mateixa_prova(args.prova, p) for p in comp.proves):
        print(f"⚠ {args.prova} no és inscrita a {comp.nom} (proves: {', '.join(comp.proves)})")

    existents = [
        r for r in resultats
        if r.competicio_id == nou.competicio_id and mateixa_prova(r.prova, nou.prova)
    ]
    if existents and not args.substituir:
        print(
            f"✗ Ja hi ha un resultat de {nou.prova} a {comp.nom} "
            f"({format_temps(existents[0].temps, 2)}). Fes servir --substituir."
        )
        return 2
    resultats = [r for r in resultats if r not in existents] + [nou]
    resultats.sort(key=lambda r: (r.competicio_id, r.prova))

    tipus = "simulació" if comp.es_simulacio else "competició"
    print(f"{comp.nom} ({comp.data_inici}, {comp.piscina}, {tipus})")
    print(f"  {nou.prova}: {format_temps(nou.temps, 2)}"
          + (f" · parcials {', '.join(format_temps(p, 2) for p in nou.parcials_25)}"
             if nou.parcials_25 else ""))
    if args.simular:
        print("\n(simulació: no s'ha desat res)")
        return 0

    if rutes.resultats.is_file():
        shutil.copyfile(rutes.resultats, rutes.resultats.with_suffix(".json.bak"))
    desar_json(rutes.resultats, [r.model_dump(exclude_none=True) for r in resultats])
    print(f"\n✓ Desat a {rutes.resultats}")
    print(f"  Informe: python scripts/informe_progressio.py --nedador {args.nedador}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

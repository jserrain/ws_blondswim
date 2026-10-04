#!/usr/bin/env python3
"""Informe de progressió cap a l'objectiu A d'un nedador.

Ús:
    python scripts/informe_progressio.py --nedador jep [--data 2026-10-20]

Llegeix la fitxa (objectius i nivell actual), el calendari (proves de cada
competició) i data/nedadors/<id>/resultats.json, i mostra, per a cada prova del
pic actiu: banda prevista a cada competició de control, resultat i zona,
calibratge, projecció a la A i ritme de cursa de referència.
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents.progressio import avaluar_pic, format_informe
from blondswim.agents.proves import validar_objectius
from blondswim.rutes import (
    RutesNedador,
    carregar_competicions,
    carregar_nedador,
    carregar_resultats,
    llistar_nedadors,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Informe de progressió cap a l'objectiu A.")
    parser.add_argument("--nedador", required=True, help="Identificador del nedador")
    parser.add_argument(
        "--data",
        default=datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat(),
        help="Data de l'informe (YYYY-MM-DD). Per defecte, avui.",
    )
    args = parser.parse_args()

    arrel = Path(__file__).parent.parent / "data"
    try:
        rutes = RutesNedador(args.nedador, arrel)
        nedador = carregar_nedador(rutes)
        competicions = carregar_competicions(rutes)
        resultats = carregar_resultats(rutes)
    except (ValueError, FileNotFoundError, ValidationError) as e:
        print(f"✗ {e}")
        if isinstance(e, ValueError) and not isinstance(e, ValidationError):
            print(f"  Nedadors disponibles: {', '.join(llistar_nedadors(arrel)) or 'cap'}")
        return 2

    avui = date.fromisoformat(args.data)
    avisos = validar_objectius(nedador, competicions, resultats, avui)
    pic, estats = avaluar_pic(nedador, competicions, resultats, avui)
    print(f"PROGRESSIÓ — {nedador.nom} ({avui:%d/%m/%Y})")
    print("\n".join(format_informe(pic, estats, avisos)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

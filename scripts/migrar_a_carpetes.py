#!/usr/bin/env python3
"""Migra data/processed/ (estructura antiga) a data/nedadors/<id>/.

Ús:
    python scripts/migrar_a_carpetes.py --simular     # mostra què faria
    python scripts/migrar_a_carpetes.py               # copia

Copia, no esborra: quan hagis comprovat que `generar_temporada.py --nedador jep`
funciona amb la nova estructura, pots esborrar data/processed/ a mà.
No sobreescriu cap fitxer que ja existeixi a la destinació.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.ingestion.migracio import migrar


def main() -> int:
    parser = argparse.ArgumentParser(description="Migra les dades a carpetes per nedador.")
    parser.add_argument(
        "--propietari-calendari",
        default="jep",
        help="Nedador a qui pertany l'antic calendari.json (per defecte: jep)",
    )
    parser.add_argument("--simular", action="store_true", help="No escriu res")
    args = parser.parse_args()

    data = Path(__file__).parent.parent / "data"
    res = migrar(
        data / "processed", data, propietari_calendari=args.propietari_calendari,
        simular=args.simular,
    )

    print(f"Nedadors: {', '.join(res.nedadors) or 'cap'}")
    verb = "Copiaria" if args.simular else "Copiat"
    for origen, desti in res.copiats:
        print(f"  {verb}: {origen.relative_to(data)} → {desti.relative_to(data)}")
    for desti in res.ja_existents:
        print(f"  Ja existeix, no es toca: {desti.relative_to(data)}")
    for avis in res.avisos:
        print(f"  ⚠ {avis}")
    if args.simular:
        print("\n(simulació: no s'ha escrit res)")
    else:
        print("\n✓ Migració feta. data/processed/ no s'ha tocat; esborra'l quan ho hagis comprovat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Registra un test CSS (400 m + 200 m) i actualitza les zones del nedador.

Ús:
    python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1 \
        [--data 2026-10-03] [--simular]

--nedador és l'identificador (carpeta de data/nedadors/); també accepta la
ruta d'un fitxer .json de nedador.

Calcula CSS/100 = (T400 - T200) / 2 i les zones (A2 = CSS, A3 = CSS - 4",
A1 = CSS + 6", Recuperació = CSS + 12", segons els offsets del nedador),
mostra les zones noves al costat de les antigues i les desa a `ritmes_css`.
Abans d'escriure, desa una còpia del fitxer amb extensió .bak.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blondswim.agents.zones_css import ritmes_des_de_test_css
from blondswim.ingestion.registre_setmana import parsejar_temps_100
from blondswim.models.nedador import Nedador
from blondswim.rutes import RutesNedador, llistar_nedadors

ZONES = ["recuperacio", "a1", "a2", "a3", "velocitat"]


def _fmt(segons: float | None) -> str:
    if segons is None:
        return "-"
    return f"{int(segons // 60)}'{segons % 60:04.1f}\""


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra un test CSS.")
    parser.add_argument("--t400", required=True, help="Temps del 400 (6:52.3 o segons)")
    parser.add_argument("--t200", required=True, help="Temps del 200 (3:18.1 o segons)")
    parser.add_argument("--data", default=datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat(), help="Data del test")
    parser.add_argument(
        "--nedador",
        required=True,
        help="Identificador del nedador (o ruta d'un fitxer .json de nedador)",
    )
    parser.add_argument(
        "--simular", action="store_true", help="Només mostra les zones, no desa res"
    )
    args = parser.parse_args()

    t400 = parsejar_temps_100(args.t400)
    t200 = parsejar_temps_100(args.t200)
    arrel_dades = Path(__file__).parent.parent / "data"
    try:
        path = (
            Path(args.nedador)
            if args.nedador.endswith(".json")
            else RutesNedador(args.nedador, arrel_dades).nedador
        )
    except ValueError as e:
        print(f"✗ {e}")
        return 2
    if not path.is_file():
        disponibles = ", ".join(llistar_nedadors(arrel_dades)) or "cap"
        print(f"✗ No hi ha {path} (nedadors disponibles: {disponibles})")
        return 2
    dades = json.loads(path.read_text(encoding="utf-8"))
    nedador = Nedador(**dades)

    try:
        nous = ritmes_des_de_test_css(t400, t200, args.data, nedador.parametres_ritme)
    except ValueError as e:
        print(f"✗ {e}")
        return 2

    antics = nedador.ritmes_css
    print(f"Test CSS {args.data}: 400 = {_fmt(t400)}, 200 = {_fmt(t200)}")
    print(f"CSS = {_fmt(nous.a2)}/100\n")
    print(f"{'Zona':<12}{'Abans':>10}{'Ara':>10}")
    for zona in ZONES:
        abans = getattr(antics, zona) if antics else None
        print(f"{zona:<12}{_fmt(abans):>10}{_fmt(getattr(nous, zona)):>10}")

    if args.simular:
        print("\n(simulació: no s'ha desat res)")
        return 0

    shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))
    dades["ritmes_css"] = nous.model_dump()
    path.write_text(json.dumps(dades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✓ Zones desades a {path} (còpia a {path.name}.bak)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

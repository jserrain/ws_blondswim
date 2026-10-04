"""Rutes i càrrega de les dades de cada nedador.

Estructura (fora de git):

    data/
    ├── competicions.json              catàleg comú de competicions
    └── nedadors/
        └── <id>/                      una carpeta per nedador; <id> = Nedador.id
            ├── nedador.json           perfil, marques, ritmes_css, setmana_tipus
            ├── calendari.json         [{competicio_id, classe, proves}]
            ├── historial.json         sessions realitzades (few-shot, volums)
            ├── resultats.json         temps de competició (B/C/A), parcials i braçades
            ├── macrocicle.json        última temporada generada
            ├── setmanes/              setmana_<id>_<YYYY>-W<ww>.xlsx (full de la piscina)
            ├── registres/             registre_<id>_<YYYY>-W<ww>.xlsx (RPE, SRSS, control)
            └── log_decisions/         logs de generació i d'ajustos

L'arrel per defecte és `data/` relativa al directori de treball (els scripts
passen la ruta absoluta del repo). Tot el codi que necessita una ruta de
nedador la demana aquí, de manera que els noms de fitxer es deriven sempre de
l'identificador.
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from blondswim.models.calendari import (
    Competicio,
    CompeticioCataleg,
    InscripcioCompeticio,
    resoldre_calendari,
)
from blondswim.models.historial import SessioRealitzada
from blondswim.models.nedador import Nedador
from blondswim.models.resultat import ResultatCompeticio

ARREL_DADES_PER_DEFECTE = Path("data")
FITXER_COMPETICIONS = "competicions.json"
CARPETA_NEDADORS = "nedadors"

_PATRO_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def validar_id_nedador(nedador_id: str) -> str:
    """Comprova que l'identificador serveix com a nom de carpeta i de fitxer."""
    if not _PATRO_ID.match(nedador_id):
        raise ValueError(
            f"Identificador de nedador no vàlid: '{nedador_id}' "
            "(minúscules, xifres, '-' o '_', sense espais ni accents)"
        )
    return nedador_id


def _sufix_setmana(dilluns: date) -> str:
    any_iso, setmana_iso, _ = dilluns.isocalendar()
    return f"{any_iso}-W{setmana_iso:02d}"


@dataclass(frozen=True)
class RutesNedador:
    """Totes les rutes d'un nedador dins de l'arrel de dades."""

    nedador_id: str
    arrel: Path = ARREL_DADES_PER_DEFECTE

    def __post_init__(self) -> None:
        validar_id_nedador(self.nedador_id)

    @property
    def carpeta(self) -> Path:
        return self.arrel / CARPETA_NEDADORS / self.nedador_id

    @property
    def nedador(self) -> Path:
        return self.carpeta / "nedador.json"

    @property
    def calendari(self) -> Path:
        return self.carpeta / "calendari.json"

    @property
    def historial(self) -> Path:
        return self.carpeta / "historial.json"

    @property
    def resultats(self) -> Path:
        return self.carpeta / "resultats.json"

    @property
    def macrocicle(self) -> Path:
        return self.carpeta / "macrocicle.json"

    @property
    def setmanes_dir(self) -> Path:
        return self.carpeta / "setmanes"

    @property
    def registres_dir(self) -> Path:
        return self.carpeta / "registres"

    @property
    def log_dir(self) -> Path:
        return self.carpeta / "log_decisions"

    def setmana_xlsx(self, dilluns: date) -> Path:
        return self.setmanes_dir / f"setmana_{self.nedador_id}_{_sufix_setmana(dilluns)}.xlsx"

    def registre_xlsx(self, dilluns: date) -> Path:
        return self.registres_dir / f"registre_{self.nedador_id}_{_sufix_setmana(dilluns)}.xlsx"

    def mesocicle_xlsx(self, mesocicle_id: str) -> Path:
        return self.setmanes_dir / f"mesocicle_{self.nedador_id}_{mesocicle_id}.xlsx"


def ruta_competicions(arrel: Path = ARREL_DADES_PER_DEFECTE) -> Path:
    return arrel / FITXER_COMPETICIONS


def llistar_nedadors(arrel: Path = ARREL_DADES_PER_DEFECTE) -> list[str]:
    """Identificadors dels nedadors que tenen carpeta amb `nedador.json`."""
    carpeta = arrel / CARPETA_NEDADORS
    if not carpeta.is_dir():
        return []
    return sorted(
        d.name for d in carpeta.iterdir() if d.is_dir() and (d / "nedador.json").is_file()
    )


def _llegir_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def desar_json(path: Path, dades: Any) -> None:
    """Escriu JSON (UTF-8, indentat) creant el directori si cal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def carregar_nedador(rutes: RutesNedador) -> Nedador:
    """Llegeix `nedador.json` i comprova que l'id coincideix amb la carpeta."""
    if not rutes.nedador.is_file():
        disponibles = ", ".join(llistar_nedadors(rutes.arrel)) or "cap"
        raise FileNotFoundError(
            f"No hi ha {rutes.nedador} (nedadors disponibles: {disponibles})"
        )
    nedador = Nedador(**_llegir_json(rutes.nedador))
    if nedador.id != rutes.nedador_id:
        raise ValueError(
            f"{rutes.nedador}: l'id del fitxer ('{nedador.id}') no coincideix amb la "
            f"carpeta ('{rutes.nedador_id}')"
        )
    return nedador


def carregar_cataleg(arrel: Path = ARREL_DADES_PER_DEFECTE) -> list[CompeticioCataleg]:
    path = ruta_competicions(arrel)
    if not path.is_file():
        return []
    return [CompeticioCataleg(**c) for c in _llegir_json(path)]


def carregar_inscripcions(rutes: RutesNedador) -> list[InscripcioCompeticio]:
    if not rutes.calendari.is_file():
        return []
    return [InscripcioCompeticio(**i) for i in _llegir_json(rutes.calendari)]


def carregar_competicions(rutes: RutesNedador) -> list[Competicio]:
    """Calendari del nedador resolt contra el catàleg comú (amb classe A/B/C)."""
    return resoldre_calendari(carregar_cataleg(rutes.arrel), carregar_inscripcions(rutes))


def carregar_historial(rutes: RutesNedador) -> list[SessioRealitzada]:
    """Historial del nedador; llista buida si encara no en té."""
    if not rutes.historial.is_file():
        return []
    return [SessioRealitzada(**s) for s in _llegir_json(rutes.historial)]


def carregar_resultats(rutes: RutesNedador) -> list[ResultatCompeticio]:
    """Resultats de competició del nedador; llista buida si encara no en té."""
    if not rutes.resultats.is_file():
        return []
    return [ResultatCompeticio(**r) for r in _llegir_json(rutes.resultats)]

"""
Selecció determinista d'exercicis de tècnica (biblioteca, acordat 2026-10-01).

- La biblioteca (`tecnica/biblioteca_tecnica.json`) agrupa els exercicis en
  famílies (mateix objectiu tècnic) amb variants per nivell: Base -> Intermedi
  -> Refinament.
- Cada rol de sessió té unes famílies on encaixa (FAMILIES_ROL). Es trien les
  rellevants per a les proves objectiu del nedador, amb prioritat per a les
  famílies de `Nedador.prioritats_tecniques`.
- La família es manté durant el mesocicle (bloc) i la variant canvia cada
  setmana. La rotació entre blocs dona varietat sense perdre el focus.
- L'LLM només decideix la dosi dins de la part; el validador comprova que hi
  siguin tots (camp `Exercici.id_biblioteca`).
"""

import json
import logging
import re
from functools import cache
from pathlib import Path

from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador

logger = logging.getLogger(__name__)

_RUTA_BIBLIOTECA = Path(__file__).parent.parent / "tecnica" / "biblioteca_tecnica.json"

# Famílies on encaixa cada rol (ordre = preferència a igualtat de puntuació).
FAMILIES_ROL: dict[str, list[str]] = {
    "aerobica": [
        "Ritme de cursa", "Cames de crol", "Viratges", "Dofí (cames)",
        "Recuperació i rotació de crol", "Patada lateral i rotació",
    ],
    "qualitat": [
        "Sortides", "Ondulació subaquàtica", "Viratges", "Canvis d'estil a estils",
        "Ritme de cursa",
    ],
    "tecnica": [
        "Canvis d'estil a estils", "Coordinació de braça", "Coordinació de papallona",
        "Tècnica d'esquena", "Ondulació de papallona", "Propulsió de braça",
        "Cames de braça", "Cames d'esquena",
    ],
    "llarga": [
        "Freqüència i longitud de braçada", "Captura de crol", "Viratges",
        "Patada lateral i rotació", "Cames de crol",
    ],
    "activacio": ["Sortides", "Viratges", "Ritme de cursa"],
    "recuperacio": ["Recuperació i rotació de crol", "Cames de crol", "Cames d'esquena"],
}
FAMILIES_ROL["mitjana"] = FAMILIES_ROL["aerobica"]

# Nombre de famílies (un exercici per família) per rol.
N_FAMILIES_ROL: dict[str, int] = {
    "aerobica": 2, "mitjana": 2, "qualitat": 2, "tecnica": 3,
    "llarga": 2, "activacio": 1, "recuperacio": 1,
}

# tipus_sessio (tipus de setmana) -> fase de la biblioteca.
_FASE_PER_TIPUS: dict[str, str] = {
    "carrega": "Base", "descarrega": "Base", "transicio": "Base",
    "qualitat": "Build", "taper": "Peak",
}
_ORDRE_NIVELL = {"Base": 0, "Intermedi": 1, "Refinament": 2}

_ESTILS = {
    "crol": "crol", "lliure": "crol", "free": "crol",
    "estils": "estils", "im": "estils",
    "papallona": "papallona", "pap": "papallona",
    "esquena": "esquena", "braça": "braça", "braca": "braça",
}


@cache
def carregar_biblioteca() -> tuple[dict, ...]:
    """Exercicis de la biblioteca (llegits un cop)."""
    with open(_RUTA_BIBLIOTECA, encoding="utf-8") as f:
        return tuple(json.load(f))


def families() -> list[str]:
    """Famílies en l'ordre de la biblioteca."""
    vistes: list[str] = []
    for e in carregar_biblioteca():
        if e["familia"] not in vistes:
            vistes.append(e["familia"])
    return vistes


def normalitzar_prova(prova: str) -> str | None:
    """'100m lliure' / '100 crol' / '100 IM' -> '100 crol' / '100 estils'."""
    m = re.match(r"\s*(\d+)\s*m?\s+(.+)", prova.lower())
    if not m:
        return None
    estil = _ESTILS.get(m.group(2).strip().split()[0])
    return f"{m.group(1)} {estil}" if estil else None


def _proves_nedador(nedador: Nedador) -> set[str]:
    return {p for p in (normalitzar_prova(x) for x in nedador.proves_objectiu) if p}


def _rotacio_bloc(mesocicle_id: str) -> int:
    m = re.search(r"(\d+)$", mesocicle_id)
    return int(m.group(1)) if m else 0


def seleccionar_exercicis(
    nedador: Nedador, rol: str, tipus_sessio: str, microcicle: Microcicle
) -> list[dict]:
    """
    Exercicis de tècnica d'una sessió: un per família, `N_FAMILIES_ROL[rol]`
    famílies rellevants per a les proves del nedador.

    Puntuació d'una família = nombre de proves objectiu que cobreix + 2 si és a
    `nedador.prioritats_tecniques`. Empats: ordre de FAMILIES_ROL, rotat pel
    número de mesocicle (varietat entre blocs). La variant: les del nivell/fase
    que toca, rotant cada setmana dins el bloc.
    """
    proves = _proves_nedador(nedador)
    fase = _FASE_PER_TIPUS.get(tipus_sessio, "Base")
    exercicis = carregar_biblioteca()
    prioritats = set(nedador.prioritats_tecniques)
    for p in prioritats - set(families()):
        logger.warning(f"Prioritat tècnica desconeguda (no és cap família): {p}")

    candidates = FAMILIES_ROL.get(rol, FAMILIES_ROL["aerobica"])
    gir = _rotacio_bloc(microcicle.mesocicle_id) % max(len(candidates), 1)
    ordre = candidates[gir:] + candidates[:gir]

    puntuades: list[tuple[int, int, str]] = []
    for pos, fam in enumerate(ordre):
        del_fam = [e for e in exercicis if e["familia"] == fam]
        cobertes = {p for e in del_fam for p in e["proves"] if p in proves}
        if not cobertes:
            continue
        puntuacio = len(cobertes) + (2 if fam in prioritats else 0)
        puntuades.append((-puntuacio, pos, fam))
    puntuades.sort()

    seleccio: list[dict] = []
    for _p, _pos, fam in puntuades[: N_FAMILIES_ROL.get(rol, 2)]:
        rellevants = [
            e for e in exercicis
            if e["familia"] == fam and any(p in proves for p in e["proves"])
        ]
        de_fase = [e for e in rellevants if fase in e["fases"]] or rellevants
        de_fase.sort(key=lambda e: (_ORDRE_NIVELL.get(e["nivell"], 0), e["id"]))
        seleccio.append(de_fase[microcicle.setmana % len(de_fase)])
    return seleccio


def text_exercicis(exercicis: list[dict]) -> str:
    """Llista per al prompt (vegeu generar_microcicle.md)."""
    if not exercicis:
        return "(cap exercici de la biblioteca per a aquesta sessió)"
    linies = []
    for e in exercicis:
        material = f" | material: {e['material']}" if e["material"] else ""
        restriccio = f" | ATENCIÓ: {e['restriccio']}" if e["restriccio"] else ""
        linies.append(
            f"- id_biblioteca: \"{e['id']}\" | {e['nom']} | dosi orientativa: "
            f"{e['format']} | consigna: {e['consigna']}{material}{restriccio}"
        )
    return "\n".join(linies)


def per_id(id_exercici: str) -> dict | None:
    """Exercici de la biblioteca pel seu id."""
    return next((e for e in carregar_biblioteca() if e["id"] == id_exercici), None)

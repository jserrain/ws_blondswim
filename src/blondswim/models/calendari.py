"""Models del calendari de competicions.

El calendari té dues capes:

- **Catàleg comú** (`CompeticioCataleg`, `data/competicions.json`): dades
  objectives de cada competició (nom, dates, piscina), compartides per tots
  els nedadors.
- **Calendari del nedador** (`InscripcioCompeticio`,
  `data/nedadors/<id>/calendari.json`): a quines competicions va cada
  nedador, amb quina classe d'objectiu (A/B/C) i quines proves hi neda.

`resoldre_calendari()` combina les dues capes en la llista de `Competicio`
(amb classe) que fan servir els agents.
"""

from typing import Literal

from pydantic import BaseModel

Classe = Literal["A", "B", "C"]
Piscina = Literal["25m", "50m", "aaoo"]


class Competicio(BaseModel):
    """Competició resolta per a un nedador concret (catàleg + classe)."""

    id: str
    nom: str
    data_inici: str
    data_fi: str
    classe: Classe
    piscina: Piscina
    proves: list[str] = []


class CompeticioCataleg(BaseModel):
    """Competició del catàleg comú, sense classe (la classe és de cada nedador)."""

    id: str
    nom: str
    data_inici: str
    data_fi: str
    piscina: Piscina


class InscripcioCompeticio(BaseModel):
    """Entrada del calendari d'un nedador: competició del catàleg + classe."""

    competicio_id: str
    classe: Classe
    proves: list[str] = []


def resoldre_calendari(
    cataleg: list[CompeticioCataleg],
    inscripcions: list[InscripcioCompeticio],
) -> list[Competicio]:
    """Combina el catàleg comú amb el calendari d'un nedador.

    Retorna les competicions del nedador ordenades per data d'inici.

    Raises:
        ValueError: si una inscripció apunta a una competició que no és al
            catàleg, o si el nedador té la mateixa competició dues vegades.
    """
    per_id = {c.id: c for c in cataleg}
    vistes: set[str] = set()
    resultat: list[Competicio] = []
    for ins in inscripcions:
        if ins.competicio_id in vistes:
            raise ValueError(f"Competició repetida al calendari: '{ins.competicio_id}'")
        vistes.add(ins.competicio_id)
        comp = per_id.get(ins.competicio_id)
        if comp is None:
            raise ValueError(
                f"La competició '{ins.competicio_id}' no és al catàleg (competicions.json)"
            )
        resultat.append(
            Competicio(**comp.model_dump(), classe=ins.classe, proves=ins.proves)
        )
    resultat.sort(key=lambda c: (c.data_inici, c.id))
    return resultat


def separar_calendari(
    competicions: list[Competicio],
) -> tuple[list[CompeticioCataleg], list[InscripcioCompeticio]]:
    """Inversa de `resoldre_calendari()`: separa un calendari amb classes
    (el format antic, `calendari.json`) en catàleg comú + inscripcions."""
    cataleg = [
        CompeticioCataleg(**c.model_dump(exclude={"classe", "proves"})) for c in competicions
    ]
    inscripcions = [
        InscripcioCompeticio(competicio_id=c.id, classe=c.classe, proves=c.proves)
        for c in competicions
    ]
    return cataleg, inscripcions


def fusionar_cataleg(
    existent: list[CompeticioCataleg], nou: list[CompeticioCataleg]
) -> list[CompeticioCataleg]:
    """Afegeix al catàleg les competicions noves; les que ja hi són (mateix id)
    s'actualitzen amb les dades noves. Ordenat per data."""
    per_id = {c.id: c for c in existent}
    for c in nou:
        per_id[c.id] = c
    return sorted(per_id.values(), key=lambda c: (c.data_inici, c.id))

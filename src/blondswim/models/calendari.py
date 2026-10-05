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

**Simulacions** (`tipus="simulacio"`): un contrarellotge en un entrenament que
fa de punt de control de la progressió. No altera la planificació (sense
mini-taper ni setmana post-competició) i no cal que sigui al catàleg: es pot
definir al calendari del nedador amb `data` i `piscina`.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator

Classe = Literal["A", "B", "C"]
Piscina = Literal["25m", "50m", "aaoo"]
Tipus = Literal["competicio", "simulacio"]


class Competicio(BaseModel):
    """Competició resolta per a un nedador concret (catàleg + classe)."""

    id: str
    nom: str
    data_inici: str
    data_fi: str
    classe: Classe
    piscina: Piscina
    proves: list[str] = []
    tipus: Tipus = "competicio"

    @property
    def es_simulacio(self) -> bool:
        return self.tipus == "simulacio"


class CompeticioCataleg(BaseModel):
    """Competició del catàleg comú, sense classe (la classe és de cada nedador)."""

    id: str
    nom: str
    data_inici: str
    data_fi: str
    piscina: Piscina


class InscripcioCompeticio(BaseModel):
    """
    Entrada del calendari d'un nedador: competició del catàleg + classe.

    Una simulació pot apuntar a una competició del catàleg (es fa el contrarellotge
    aquell dia) o definir-se aquí mateix amb `data` i `piscina` (i `nom` opcional).
    """

    competicio_id: str
    classe: Classe
    proves: list[str] = []
    tipus: Tipus = "competicio"
    data: str | None = None
    piscina: Piscina | None = None
    nom: str | None = None

    @model_validator(mode="after")
    def _simulacio(self) -> "InscripcioCompeticio":
        if self.tipus == "simulacio" and self.classe == "A":
            raise ValueError(f"{self.competicio_id}: una simulació no pot ser de classe A")
        if self.data is not None:
            date.fromisoformat(self.data)
        if self.tipus == "competicio" and (self.data or self.piscina):
            raise ValueError(
                f"{self.competicio_id}: data i piscina només es poden definir en una "
                "simulació (les competicions surten del catàleg)"
            )
        return self


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
        if comp is not None:
            dades = comp.model_dump()
            if ins.tipus == "simulacio":
                # La simulació pot precisar la data, la piscina i el nom.
                dades["data_inici"] = dades["data_fi"] = ins.data or comp.data_inici
                dades["piscina"] = ins.piscina or comp.piscina
                dades["nom"] = ins.nom or f"Simulació — {comp.nom}"
        elif ins.tipus == "simulacio":
            if ins.data is None or ins.piscina is None:
                raise ValueError(
                    f"Simulació '{ins.competicio_id}': no és al catàleg, cal indicar "
                    "data i piscina"
                )
            dades = {
                "id": ins.competicio_id,
                "nom": ins.nom or f"Simulació {ins.data}",
                "data_inici": ins.data,
                "data_fi": ins.data,
                "piscina": ins.piscina,
            }
        else:
            raise ValueError(
                f"La competició '{ins.competicio_id}' no és al catàleg (competicions.json)"
            )
        resultat.append(
            Competicio(**dades, classe=ins.classe, proves=ins.proves, tipus=ins.tipus)
        )
    resultat.sort(key=lambda c: (c.data_inici, c.id))
    return resultat


def separar_calendari(
    competicions: list[Competicio],
) -> tuple[list[CompeticioCataleg], list[InscripcioCompeticio]]:
    """Inversa de `resoldre_calendari()`: separa un calendari amb classes
    (el format antic, `calendari.json`) en catàleg comú + inscripcions."""
    cataleg = [
        CompeticioCataleg(**c.model_dump(exclude={"classe", "proves", "tipus"}))
        for c in competicions
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


def competicions_planificacio(competicions: list[Competicio]) -> list[Competicio]:
    """Competicions que afecten la planificació (les simulacions no hi compten)."""
    return [c for c in competicions if not c.es_simulacio]

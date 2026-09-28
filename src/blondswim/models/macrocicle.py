from typing import Literal

from pydantic import BaseModel


class Microcicle(BaseModel):
    """
    Representa una setmana dins d'un mesocicle.
    Conté la planificació setmanal amb volum objectiu i característiques.
    """
    setmana: int
    dates: str  # Ex: "21-27/09/2026"
    mesocicle_id: str
    tipus_base: Literal["carrega", "qualitat", "descarrega", "taper", "transicio"]
    notes: str | None = None  # Text literal de "Tipus de setmana" (ex: "Càrrega + Test CSS")
    volum_objectiu: int  # metres
    dies_qualitat: bool  # Dc+Ds
    test_css: bool
    competicio_test_oficial: str | None = None
    test_avaluacio: str | None = None
    focus_especific: str | None = None

class Mesocicle(BaseModel):
    """
    Representa un mesocicle dins del macrocicle anual.
    Cada mesocicle agrupa diverses setmanes amb objectius i metodologia comuns.
    """
    id: str
    nom: str
    setmanes: str  # Ex: "1-4"
    dates: str  # Ex: "21/09-18/10/2026"
    tipus: Literal["Base", "Build1", "Build2", "Peak", "Cursa", "Transicio"]
    fase_objectiu: str
    metodologia_dominant: str
    volum_min: int  # metres
    volum_max: int  # metres
    volum_mitja_previst: int  # metres
    tancament: str | None = None
    tecnica_focus: str | None = None
    especific_metodologia: str | None = None
    microcicles: list[Microcicle] = []

class Macrocicle(BaseModel):
    """
    Representa el macrocicle anual complet amb tots els mesocicles.
    """
    nom: str
    temporada: str | None = None  # Ex: "Hivern", "Estiu" (opcional)
    data_inici: str | None = None
    data_fi: str | None = None
    mesocicles: list[Mesocicle]

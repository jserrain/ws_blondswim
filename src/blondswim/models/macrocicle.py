from pydantic import BaseModel
from typing import Literal

class Mesocicle(BaseModel):
    """
    Representa un mesocicle dins del macrocicle anual.
    Cada mesocicle agrupa diverses setmanes amb objectius i metodologia comuns.
    """
    id: str
    nom: str
    setmanes: str  # Ex: "1-4"
    dates: str  # Ex: "21/09-18/10/2026"
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
    mesocicles: list[Mesocicle]

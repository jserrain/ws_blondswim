from pydantic import BaseModel
from typing import Literal

class PartSessio(BaseModel):
    """
    Representa una part de la sessió d'entrenament amb els seus percentatges
    segons el tipus de setmana.
    """
    nom: str  # Ex: "Escalfament", "Tècnica+Subaquàtic", etc.
    percentatge_carrega: float
    percentatge_qualitat: float
    percentatge_descarrega: float
    contingut: str | None = None

class EstructuraSessio(BaseModel):
    """
    Estructura fixa de 5 parts d'una sessió d'entrenament amb percentatges
    segons tipus de setmana (Càrrega / Qualitat / Descàrrega-Test).
    
    Parts estàndard:
    1. Escalfament (10%/10%/15%)
    2. Tècnica+Subaquàtic (20%/15%/15%)
    3. Aeròbic/Llindar (50%/30%/20%)
    4. Específic/Qualitat (10%/35%/40%)
    5. Tornada a la calma (10%/10%/10%)
    """
    parts: list[PartSessio]

class Sessio(BaseModel):
    """
    Representa una sessió d'entrenament concreta dins d'un microcicle.
    """
    id: str
    microcicle_setmana: int
    dia: Literal["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"]
    tipus_sessio: Literal["carrega", "qualitat", "descarrega", "taper", "transicio"]
    volum_total: int  # metres
    estructura: EstructuraSessio
    notes: str | None = None

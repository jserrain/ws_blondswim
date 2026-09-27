"""Models per a l'historial d'entrenaments realitzats."""

from pydantic import BaseModel


class SerieRealitzada(BaseModel):
    """Sèrie d'entrenament realitzada."""

    ordre: int
    treball: str | None = None
    execucio: str
    descans: str | None = None
    material: str | None = None
    intensitat: str | None = None
    objectiu: str | None = None
    temps_min: float | None = None
    volum_m: int | None = None


class SessioRealitzada(BaseModel):
    """Sessió d'entrenament realitzada."""

    data: str
    setmana: int | None = None
    series: list[SerieRealitzada]
    volum_total_m: int
    temps_total_min: float

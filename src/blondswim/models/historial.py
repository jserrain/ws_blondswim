"""Models per a l'historial d'entrenaments realitzats."""

from pydantic import BaseModel, field_validator

from blondswim.models.franja import Franja, Modalitat
from blondswim.models.registre import validar_cr10


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

    data: str  # "YYYY-MM-DD"
    setmana: int | None = None
    series: list[SerieRealitzada] = []
    volum_total_m: int = 0
    temps_total_min: float
    # Fase E+I: franja, modalitat i esforç percebut de la sessió.
    franja: Franja = "tarda"
    modalitat: Modalitat = "natacio"
    rpe_sessio: int | None = None  # CR-10 (0-10), registrat després de la sessió
    assoliment: int | None = None  # 1-5, independent de l'RPE

    @field_validator("rpe_sessio")
    @classmethod
    def _validar_rpe(cls, v: int | None) -> int | None:
        return validar_cr10(v)

    @field_validator("assoliment")
    @classmethod
    def _validar_assoliment(cls, v: int | None) -> int | None:
        if v is not None and not 1 <= v <= 5:
            raise ValueError(f"L'assoliment ha de ser entre 1 i 5 (rebut: {v})")
        return v

    @property
    def carrega(self) -> int | None:
        """Càrrega interna (sRPE de Foster): RPE × minuts. None sense RPE."""
        if self.rpe_sessio is None:
            return None
        return round(self.rpe_sessio * self.temps_total_min)

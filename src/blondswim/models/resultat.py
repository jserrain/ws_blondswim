"""Resultat d'una prova en competició (el que ha passat, separat del calendari)."""

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from blondswim.utils.temps import parsejar_temps

# Tolerància entre la suma dels parcials i el temps final (arrodoniments del vídeo).
TOLERANCIA_PARCIALS_S = 0.5


class ResultatCompeticio(BaseModel):
    """
    Temps d'una prova en una competició. Parcials (cada 25 m) i braçades per
    llargada són opcionals i surten de l'anàlisi de vídeo; en un 100 IM en
    piscina de 25 m, cada parcial és un estil.
    """

    competicio_id: str
    prova: str
    temps: float
    parcials_25: list[float] = []
    bracades_llargada: list[int] = []
    font: Literal["video", "cronometre", "oficial"] | None = None
    notes: str | None = None

    @field_validator("temps", mode="before")
    @classmethod
    def _temps(cls, v):
        return parsejar_temps(v)

    @field_validator("parcials_25", mode="before")
    @classmethod
    def _parcials(cls, v):
        return [parsejar_temps(p) for p in v] if isinstance(v, list) else v

    @model_validator(mode="after")
    def _suma_parcials(self) -> "ResultatCompeticio":
        if self.parcials_25:
            suma = sum(self.parcials_25)
            if abs(suma - self.temps) > TOLERANCIA_PARCIALS_S:
                raise ValueError(
                    f"{self.competicio_id} {self.prova}: la suma dels parcials ({suma:.2f}) "
                    f"no coincideix amb el temps ({self.temps:.2f})"
                )
        return self

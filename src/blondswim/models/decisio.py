"""Models per a decisions de metodologia d'entrenament."""

from typing import Literal

from pydantic import BaseModel


class DecisioMetodologia(BaseModel):
    """Decisió de metodologia d'entrenament per a una prova específica."""

    prova: str
    categoria: Literal["absolut", "master"]
    metodologia_principal: str
    metodologies_complementaries: list[str] = []
    forca_evidencia: Literal[
        "forta", "moderada", "practica_documentada", "sense_evidencia"
    ]
    justificacio: str
    avisos: list[str] = []

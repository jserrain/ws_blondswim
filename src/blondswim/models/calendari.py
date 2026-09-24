from typing import Literal

from pydantic import BaseModel


class Competicio(BaseModel):
    id: str
    nom: str
    data_inici: str
    data_fi: str
    classe: Literal["A", "B", "C"]
    piscina: Literal["25m", "50m", "aaoo"]

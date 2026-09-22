from pydantic import BaseModel
from typing import Literal

class Competicio(BaseModel):
    id: str
    nom: str
    data_inici: str
    data_fi: str
    classe: Literal["A", "B", "C"]
    piscina: str

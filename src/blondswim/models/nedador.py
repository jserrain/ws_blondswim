from pydantic import BaseModel
from typing import Literal

class RitmesCSS(BaseModel):
    a1: float | None = None
    a2: float | None = None
    a3: float | None = None
    data_test: str | None = None

class Nedador(BaseModel):
    id: str
    nom: str
    categoria: Literal["absolut", "master", "junior"]
    proves_objectiu: list[str]
    pics_prioritzats: list[str] = []
    mode_ritme: Literal["temps", "rpe"]
    ritmes_css: RitmesCSS | None = None

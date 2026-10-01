"""
Franges del dia i modalitats de sessió (Fase E+I).

Un dia pot tenir fins a 3 sessions, una per franja (matí, migdia, tarda).
La fitxa del nedador (`Nedador.setmana_tipus`) diu, per a cada dia de la
setmana, quines franges tenen sessió i de quina modalitat.
"""

from typing import Literal

from pydantic import BaseModel, model_validator

Franja = Literal["mati", "migdia", "tarda"]
Modalitat = Literal["natacio", "gimnas", "altres"]

FRANGES: list[str] = ["mati", "migdia", "tarda"]
ORDRE_FRANJA: dict[str, int] = {f: i for i, f in enumerate(FRANGES)}
ETIQUETA_FRANJA: dict[str, str] = {"mati": "matí", "migdia": "migdia", "tarda": "tarda"}
ETIQUETA_MODALITAT: dict[str, str] = {
    "natacio": "Natació",
    "gimnas": "Gimnàs",
    "altres": "Altres",
}

DIES_SETMANA: list[str] = [
    "dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge",
]

# Màxim de sessions en un dia (una per franja).
MAX_SESSIONS_DIA: int = 3

# Franja per defecte de les sessions de natació quan el nedador no té
# setmana_tipus (compatibilitat amb les fitxes anteriors a la Fase E+I).
FRANJA_PER_DEFECTE: str = "tarda"


class SlotSessio(BaseModel):
    """Una sessió prevista dins la setmana tipus del nedador."""

    franja: Franja
    modalitat: Modalitat
    durada_min: int | None = None  # obligatori per a gimnàs i altres
    opcional: bool = False

    @model_validator(mode="after")
    def _validar_durada(self) -> "SlotSessio":
        if self.modalitat != "natacio" and not self.durada_min:
            raise ValueError(
                f"Una sessió de {self.modalitat} ({self.franja}) necessita durada_min"
            )
        if self.durada_min is not None and self.durada_min <= 0:
            raise ValueError(f"durada_min ha de ser positiva (rebut: {self.durada_min})")
        return self


def franges_consecutives(a: str, b: str) -> bool:
    """True si les franges són contigües (matí-migdia o migdia-tarda): < ~6 h."""
    return abs(ORDRE_FRANJA[a] - ORDRE_FRANJA[b]) == 1

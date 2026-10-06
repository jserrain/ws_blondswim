"""
Registres de seguiment (Fase E+I): benestar diari (SRSS) i sèrie de control.

L'esforç de cada sessió (sRPE, escala CR-10) es guarda a SessioRealitzada.

Fonts: Foster et al. 2001 (sRPE); Kellmann et al. 2016-2017 (SRSS). La
traducció catalana de les etiquetes i dels ítems és pròpia (no validada).
"""

from datetime import date

from pydantic import BaseModel, field_validator

# Escala CR-10 de Foster: etiquetes verbals en català. Els valors sense
# etiqueta (6, 8, 9) són intermedis; es guarda sempre el número.
ETIQUETES_CR10: dict[int, str] = {
    0: "Descans",
    1: "Molt, molt suau",
    2: "Suau",
    3: "Moderat",
    4: "Una mica dur",
    5: "Dur",
    6: "Dur +",
    7: "Molt dur",
    8: "Molt dur +",
    9: "Molt dur ++",
    10: "Màxim",
}

# Short Recovery and Stress Scale (SRSS): 4 ítems de recuperació i 4 d'estrès,
# de 0 (gens) a 6 (totalment).
ITEMS_SRSS_RECUPERACIO: list[str] = [
    "Capacitat de rendiment físic",
    "Capacitat de rendiment mental",
    "Equilibri emocional",
    "Recuperació global",
]
ITEMS_SRSS_ESTRES: list[str] = [
    "Estrès muscular",
    "Manca d'activació",
    "Estat emocional negatiu",
    "Estrès global",
]
SRSS_MIN, SRSS_MAX = 0, 6


def etiqueta_cr10(valor: int) -> str:
    """Etiqueta verbal d'un valor CR-10 (0-10)."""
    return ETIQUETES_CR10[valor]


def validar_cr10(valor: int | None) -> int | None:
    """Valida un valor CR-10 (0-10) o None."""
    if valor is not None and not 0 <= valor <= 10:
        raise ValueError(f"L'RPE (CR-10) ha de ser entre 0 i 10 (rebut: {valor})")
    return valor


def _validar_items_srss(valors: list[int]) -> list[int]:
    if len(valors) != 4:
        raise ValueError(f"La SRSS té 4 ítems per escala (rebut: {len(valors)})")
    for v in valors:
        if not SRSS_MIN <= v <= SRSS_MAX:
            raise ValueError(f"Els ítems de la SRSS van de 0 a 6 (rebut: {v})")
    return valors


class RegistreSRSS(BaseModel):
    """Benestar del dia (SRSS), un cop al dia abans de la primera sessió."""

    nedador_id: str
    data: date
    recuperacio: list[int]  # 4 ítems, 0-6 (ordre: ITEMS_SRSS_RECUPERACIO)
    estres: list[int]  # 4 ítems, 0-6 (ordre: ITEMS_SRSS_ESTRES)

    @field_validator("recuperacio", "estres")
    @classmethod
    def _validar_items(cls, v: list[int]) -> list[int]:
        return _validar_items_srss(v)

    @property
    def mitjana_recuperacio(self) -> float:
        return sum(self.recuperacio) / len(self.recuperacio)

    @property
    def mitjana_estres(self) -> float:
        return sum(self.estres) / len(self.estres)


class RegistreSerieControl(BaseModel):
    """Resultat de la sèrie de control setmanal (4x100 crol A2)."""

    nedador_id: str
    data: date
    temps_100: list[float]  # segons de cada 100
    bracades_llargada: list[float] | None = None  # mitjana per 100
    rpe: int | None = None  # CR-10 de la sèrie

    @field_validator("temps_100")
    @classmethod
    def _validar_temps(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("Cal com a mínim un temps de la sèrie de control")
        if any(t <= 0 for t in v):
            raise ValueError("Els temps de la sèrie de control han de ser positius")
        return v

    @field_validator("rpe")
    @classmethod
    def _validar_rpe(cls, v: int | None) -> int | None:
        return validar_cr10(v)

    @property
    def temps_mitja(self) -> float:
        return sum(self.temps_100) / len(self.temps_100)

    @property
    def bracades_mitja(self) -> float | None:
        if not self.bracades_llargada:
            return None
        return sum(self.bracades_llargada) / len(self.bracades_llargada)


class RegistreSerieObjectiu(BaseModel):
    """Temps de la sèrie de ritme objectiu d'una setmana (segons per repetició)."""

    nedador_id: str
    data: date
    prova: str
    objectiu: float  # segons per repetició prescrits aquella setmana
    temps: list[float]
    rpe: int | None = None

    @field_validator("temps")
    @classmethod
    def _validar_temps(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("Cal com a mínim un temps de la sèrie objectiu")
        if any(t <= 0 for t in v):
            raise ValueError("Els temps de la sèrie objectiu han de ser positius")
        return v

    @field_validator("rpe")
    @classmethod
    def _validar_rpe(cls, v: int | None) -> int | None:
        return validar_cr10(v)

    @property
    def temps_mitja(self) -> float:
        return sum(self.temps) / len(self.temps)

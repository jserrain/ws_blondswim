"""
Càrrega interna real (Fase E+I): sRPE de Foster = RPE (CR-10) × minuts.

Mateix patró que el Performance Management Chart de TrainingPeaks, però amb
sRPE en lloc de TSS (l'sRPE és comú a natació i gimnàs):

- càrrega del dia = suma de totes les sessions del dia (aigua + gimnàs);
- càrrega aguda i crònica = mitjanes exponencials de 7 i 28 dies
  (CTL_avui = CTL_ahir + (càrrega_avui - CTL_ahir) / constant);
- alerta si la càrrega setmanal supera en més d'un 15% la mitjana de les 4
  setmanes anteriors sense que el pla ho prevegi.

Els llindars són provisionals: es calibren amb 3-4 setmanes de dades reals.
Tot són avisos; la decisió és del coach.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from blondswim.models.historial import SessioRealitzada

CONSTANT_AGUDA: int = 7
CONSTANT_CRONICA: int = 28
LLINDAR_INCREMENT_SETMANAL: float = 1.15
FINESTRA_SETMANES: int = 4
MINIM_SETMANES_BASE: int = 2


@dataclass(frozen=True)
class EstatCarrega:
    """Càrrega d'un dia i mitjanes exponencials (anàlegs a ATL/CTL/TSB)."""

    dia: date
    carrega: int
    aguda: float
    cronica: float

    @property
    def balanc(self) -> float:
        """Crònica - aguda (anàleg a la forma/TSB): negatiu = fatiga acumulada."""
        return self.cronica - self.aguda


def _data(sessio: SessioRealitzada) -> date:
    return date.fromisoformat(sessio.data)


def _dilluns(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def carrega_diaria(sessions: list[SessioRealitzada]) -> dict[date, int]:
    """Càrrega de cada dia (sessions sense RPE no compten)."""
    per_dia: dict[date, int] = defaultdict(int)
    for s in sessions:
        if s.carrega is not None:
            per_dia[_data(s)] += s.carrega
    return dict(sorted(per_dia.items()))


def carrega_setmanal(sessions: list[SessioRealitzada]) -> dict[date, int]:
    """Càrrega de cada setmana, indexada pel dilluns."""
    per_setmana: dict[date, int] = defaultdict(int)
    for dia, carrega in carrega_diaria(sessions).items():
        per_setmana[_dilluns(dia)] += carrega
    return dict(sorted(per_setmana.items()))


def sessions_sense_rpe(sessions: list[SessioRealitzada]) -> list[SessioRealitzada]:
    """Sessions registrades sense RPE (no compten a la càrrega)."""
    return [s for s in sessions if s.rpe_sessio is None]


def evolucio_carrega(
    sessions: list[SessioRealitzada],
    fins_a: date | None = None,
    constant_aguda: int = CONSTANT_AGUDA,
    constant_cronica: int = CONSTANT_CRONICA,
) -> list[EstatCarrega]:
    """
    Càrrega diària i mitjanes exponencials des del primer dia amb càrrega fins
    a `fins_a` (inclòs; per defecte, l'últim dia amb càrrega). Els dies sense
    sessions compten com a càrrega 0.
    """
    diaria = carrega_diaria(sessions)
    if not diaria:
        return []
    dia = next(iter(diaria))
    fi = fins_a or next(reversed(diaria))
    aguda = cronica = 0.0
    estats: list[EstatCarrega] = []
    while dia <= fi:
        carrega = diaria.get(dia, 0)
        aguda += (carrega - aguda) / constant_aguda
        cronica += (carrega - cronica) / constant_cronica
        estats.append(EstatCarrega(dia, carrega, round(aguda, 1), round(cronica, 1)))
        dia += timedelta(days=1)
    return estats


def alerta_carrega_setmanal(
    sessions: list[SessioRealitzada],
    dilluns: date,
    setmanes_excloses: frozenset[date] = frozenset(),
    ratio_planificat: float = 1.0,
    llindar: float = LLINDAR_INCREMENT_SETMANAL,
    finestra: int = FINESTRA_SETMANES,
) -> dict | None:
    """
    Alerta `carrega_setmanal_alta` si la càrrega de la setmana de `dilluns`
    supera `llindar × ratio_planificat` vegades la mitjana de les `finestra`
    setmanes anteriors.

    - `setmanes_excloses`: dilluns de setmanes de descàrrega, taper o transició,
      que no formen part de la base de comparació.
    - `ratio_planificat`: increment previst pel pla (volum objectiu de la
      setmana / mitjana del volum objectiu de la base). 1.0 si no n'hi ha.

    Retorna None si no hi ha prou setmanes de base (mínim 2) o no hi ha alerta.
    """
    setmanals = carrega_setmanal(sessions)
    actual = setmanals.get(dilluns)
    if actual is None:
        return None
    base = [
        setmanals[d]
        for d in (dilluns - timedelta(weeks=i) for i in range(1, finestra + 1))
        if d in setmanals and d not in setmanes_excloses
    ]
    if len(base) < MINIM_SETMANES_BASE:
        return None
    mitjana = sum(base) / len(base)
    if mitjana <= 0:
        return None
    ratio = actual / mitjana
    if ratio <= llindar * ratio_planificat:
        return None
    return {
        "tipus": "carrega_setmanal_alta",
        "setmana": dilluns.isoformat(),
        "carrega": actual,
        "mitjana_base": round(mitjana),
        "ratio": round(ratio, 2),
        "missatge": (
            f"Càrrega de la setmana del {dilluns:%d/%m}: {actual} UA, "
            f"{ratio:.0%} de la mitjana de les {len(base)} setmanes anteriors "
            f"({round(mitjana)} UA); límit {llindar * ratio_planificat:.0%}"
        ),
    }

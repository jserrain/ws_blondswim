"""Periodificació determinista de la temporada (convenció TrainingPeaks/ATP).

Calcula, sense cap crida LLM i en O(setmanes), la fase de cada setmana ISO
de la temporada a partir de les competicions de classe A, i agrupa les
setmanes en blocs (= mesocicles).

Regles (vegeu l'enunciat del refactor):
- R1: un microcicle és sempre una setmana ISO sencera (dilluns-diumenge).
- R2: periodització ENRERE des de cada competició A.
- R3: blocs de Base/Build1/Build2 de mida <= 4, repartits equilibradament.
- R4: les competicions B i C no canvien la fase.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from blondswim.models.calendari import Competicio
from blondswim.utils.dates import dilluns_setmana

Fase = Literal["Base", "Build1", "Build2", "Peak", "Cursa", "Transicio"]

# Durades (en setmanes) de cada fase enrere des de la Cursa.
_SETMANES_PEAK = 2
# Dues proves A separades <= aquestes setmanes = un sol període competitiu
# (doble pic): sense Transició entre elles i Peak curt abans de la segona.
SETMANES_DOBLE_PIC = 4
_SETMANES_PEAK_DOBLE = 1
_SETMANES_BUILD2 = 4
_SETMANES_BUILD1 = 4

# Mida màxima d'un bloc de Base/Build1/Build2.
_MIDA_MAX_BLOC = 4


@dataclass(frozen=True)
class SetmanaPlan:
    """Planificació d'una setmana ISO sencera de la temporada."""

    any_iso: int
    setmana_iso: int
    dilluns: date
    diumenge: date
    fase: Fase
    bloc_id: str
    index_dins_bloc: int
    es_descarrega: bool
    competicions_b_c: list[Competicio] = field(default_factory=list)


def avui() -> date:
    """Data d'avui al fus horari del coach (Europe/Madrid)."""
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def _dilluns_de(data: date) -> date:
    """Retorna el dilluns de la setmana ISO que conté `data`."""
    return dilluns_setmana(data)


def _repartir_blocs(n_setmanes: int) -> list[int]:
    """
    Reparteix `n_setmanes` en blocs de mida <= 4, el més equilibrats possible,
    amb els blocs llargs primer.

    Exemples: 5 -> [3, 2]; 6 -> [3, 3]; 7 -> [4, 3]; 8 -> [4, 4]; 9 -> [3, 3, 3].
    """
    if n_setmanes <= 0:
        return []
    n_blocs = -(-n_setmanes // _MIDA_MAX_BLOC)  # ceil
    base = n_setmanes // n_blocs
    residu = n_setmanes % n_blocs
    return [base + 1] * residu + [base] * (n_blocs - residu)


def _setmanes_iso_entre(
    data_inici: date, data_fi: date
) -> list[tuple[int, int, date, date]]:
    """
    Retorna la llista de setmanes ISO (dilluns-diumenge) que cobreixen
    [data_inici, data_fi], començant pel dilluns de la setmana de data_inici
    i acabant pel diumenge de la setmana de data_fi.

    Cada element és (any_iso, setmana_iso, dilluns, diumenge).
    """
    dilluns = _dilluns_de(data_inici)
    diumenge_final = _dilluns_de(data_fi) + timedelta(days=6)

    setmanes: list[tuple[int, int, date, date]] = []
    actual = dilluns
    while actual <= diumenge_final:
        iso = actual.isocalendar()
        setmanes.append((iso[0], iso[1], actual, actual + timedelta(days=6)))
        actual += timedelta(weeks=1)
    return setmanes


def _index_setmana(
    setmanes: list[tuple[int, int, date, date]], data: date
) -> int | None:
    """Índex de la setmana que conté `data`, o None si cau fora de la finestra."""
    dilluns = _dilluns_de(data)
    for i, (_any, _set, dl, _dg) in enumerate(setmanes):
        if dl == dilluns:
            return i
    return None


def periodificar_temporada(
    competicions: list[Competicio],
    data_inici: date,
    data_fi: date,
) -> tuple[list[SetmanaPlan], list[dict]]:
    """
    Calcula la fase de cada setmana ISO de la temporada (funció pura).

    Args:
        competicions: Totes les competicions del calendari
        data_inici: Inici de la temporada
        data_fi: Fi de la temporada

    Returns:
        Tupla amb:
        - Llista de SetmanaPlan ordenada cronològicament
        - Llista d'avisos (dicts amb "tipus_avis" i "missatge")
    """
    avisos: list[dict] = []

    setmanes = _setmanes_iso_entre(data_inici, data_fi)
    n = len(setmanes)
    if n == 0:
        return [], avisos

    fases: list[Fase | None] = [None] * n

    # --- R2: periodització enrere des de cada competició A ---
    competicions_a = sorted(
        (c for c in competicions if c.classe == "A"),
        key=lambda c: c.data_inici,
    )

    # La finestra de cada prova A comença la setmana següent a la Transicio
    # de la prova A anterior (o a la setmana de data_inici si és la primera).
    limit_inferior = 0

    def _doble_pic(anterior: Competicio, seguent: Competicio) -> bool:
        dies = (
            date.fromisoformat(seguent.data_inici) - date.fromisoformat(anterior.data_inici)
        ).days
        return 0 < dies <= SETMANES_DOBLE_PIC * 7

    for n_comp, comp in enumerate(competicions_a):
        # Peak curt si la A anterior (encara que ja hagi passat) és a <= 4 setmanes.
        peak_curt = n_comp > 0 and _doble_pic(competicions_a[n_comp - 1], comp)
        data_comp = date.fromisoformat(comp.data_inici)
        idx_cursa = _index_setmana(setmanes, data_comp)
        if idx_cursa is None:
            continue

        inici_finestra = max(limit_inferior, 0)
        if idx_cursa < inici_finestra:
            # La prova A cau dins la finestra d'una altra A: s'ignora.
            continue

        # Assignar fases enrere dins [inici_finestra, idx_cursa].
        setmanes_peak = _SETMANES_PEAK_DOBLE if peak_curt else _SETMANES_PEAK
        idx_peak_fi = idx_cursa - 1
        idx_peak_ini = idx_peak_fi - setmanes_peak + 1
        idx_build2_fi = idx_peak_ini - 1
        idx_build2_ini = idx_build2_fi - _SETMANES_BUILD2 + 1
        idx_build1_fi = idx_build2_ini - 1
        idx_build1_ini = idx_build1_fi - _SETMANES_BUILD1 + 1

        # Cursa sempre hi és.
        fases[idx_cursa] = "Cursa"

        # Peak (2 setmanes), retallable si la finestra és curta.
        peak_ini = max(inici_finestra, idx_peak_ini)
        for i in range(peak_ini, idx_cursa):
            fases[i] = "Peak"

        # Build2 (4 setmanes), retallable.
        build2_ini = max(inici_finestra, idx_build2_ini)
        for i in range(build2_ini, peak_ini):
            fases[i] = "Build2"

        # Build1 (4 setmanes), retallable.
        build1_ini = max(inici_finestra, idx_build1_ini)
        for i in range(build1_ini, build2_ini):
            fases[i] = "Build1"

        # Base: la resta cap enrere fins a l'inici de la finestra.
        for i in range(inici_finestra, build1_ini):
            fases[i] = "Base"

        # Doble pic: la propera A és a <= SETMANES_DOBLE_PIC setmanes -> sense
        # Transició; les setmanes entremig són Build2 i el Peak següent és curt.
        seguent = competicions_a[n_comp + 1] if n_comp + 1 < len(competicions_a) else None
        if seguent is not None and _doble_pic(comp, seguent):
            limit_inferior = idx_cursa + 1
            continue

        # Transicio: 1 setmana just després de la Cursa.
        idx_transicio = idx_cursa + 1
        if idx_transicio < n:
            fases[idx_transicio] = "Transicio"
            limit_inferior = idx_transicio + 1
        else:
            limit_inferior = n

    # --- Setmanes posteriors a l'última Transicio ---
    if limit_inferior < n:
        avisos.append({
            "tipus_avis": "cap_competicio_a_restant",
            "missatge": (
                "No queda cap competició classe A a partir d'aquesta setmana. "
                "Les setmanes restants es planifiquen com a Base."
            ),
        })
        for i in range(limit_inferior, n):
            if fases[i] is None:
                fases[i] = "Base"

    # Qualsevol setmana encara sense fase (no hauria de passar) -> Base.
    for i in range(n):
        if fases[i] is None:
            fases[i] = "Base"

    # --- R3: agrupar en blocs ---
    plans: list[SetmanaPlan] = []
    bloc_counter = 0
    i = 0
    while i < n:
        fase = fases[i]
        # Longitud del tram continu d'aquesta fase.
        j = i
        while j < n and fases[j] == fase:
            j += 1

        if fase in ("Base", "Build1", "Build2"):
            # Blocs de mida <= 4, repartits equilibradament.
            mides = _repartir_blocs(j - i)
            for mida in mides:
                bloc_counter += 1
                bloc_id = f"bloc_{bloc_counter}"
                if mida < 3:
                    avisos.append({
                        "tipus_avis": "bloc_curt",
                        "missatge": (
                            f"Bloc {bloc_id} ({fase}) de només {mida} setmana(es)."
                        ),
                    })
                for k in range(mida):
                    idx = i + k
                    # Un bloc d'1 setmana és de càrrega (no hi ha descàrrega).
                    es_descarrega = mida > 1 and k == mida - 1
                    plans.append(_crear_plan(
                        setmanes[idx], fase, bloc_id, k, es_descarrega, competicions
                    ))
                i += mida
        else:
            # Peak, Cursa i Transicio: un únic mesocicle per tram continu.
            bloc_counter += 1
            bloc_id = f"bloc_{bloc_counter}"
            for k in range(j - i):
                plans.append(_crear_plan(
                    setmanes[i + k], fase, bloc_id, k, False, competicions
                ))
            i = j

    return plans, avisos


def _crear_plan(
    setmana: tuple[int, int, date, date],
    fase: Fase,
    bloc_id: str,
    index_dins_bloc: int,
    es_descarrega: bool,
    competicions: list[Competicio],
) -> SetmanaPlan:
    """Construeix un SetmanaPlan i hi assigna les competicions B/C de la setmana."""
    any_iso, setmana_iso, dilluns, diumenge = setmana

    b_c = [
        c
        for c in competicions
        if c.classe in ("B", "C")
        and dilluns <= date.fromisoformat(c.data_inici) <= diumenge
    ]

    return SetmanaPlan(
        any_iso=any_iso,
        setmana_iso=setmana_iso,
        dilluns=dilluns,
        diumenge=diumenge,
        fase=fase,
        bloc_id=bloc_id,
        index_dins_bloc=index_dins_bloc,
        es_descarrega=es_descarrega,
        competicions_b_c=b_c,
    )

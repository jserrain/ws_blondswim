"""
Indicadors de recuperació i regla de decisió (Fase H, implementats a la E+I).

Alertes de la setmana:
- `carrega_setmanal_alta` (carrega.py): +15% sobre la base sense previsió.
- `srss_baix`: 2 dies de registre seguits amb la recuperació per sota de la
  línia base - 1 DE o l'estrès per sobre de la línia base + 1 DE. Línia base
  individual: mitjana i DE dels últims 28 registres (mínim 10 per activar).
- `serie_control`: mateix temps (o pitjor) que la referència amb més esforç
  (+1 RPE) o més braçades (+1 per llargada). Referència: mitjana de les 3
  sèries de control anteriors.

Regla de decisió: 2 o més alertes en una setmana -> avís
`recomanacio_setmana_seguent` (mantenir el mínim setmanal i qualitat només de
velocitat alàctica). Mai s'aplica sola: la decisió és del coach.

Els llindars són provisionals i es calibren amb dades reals.
"""

import statistics
from datetime import date, timedelta
from itertools import pairwise

from blondswim.agents import carrega
from blondswim.models.historial import SessioRealitzada
from blondswim.models.registre import RegistreSerieControl, RegistreSRSS

FINESTRA_SRSS: int = 28
MINIM_REGISTRES_SRSS: int = 10
DESVIACIONS_SRSS: float = 1.0
# DE mínima: evita alertes per diferències minúscules quan les respostes són
# sempre iguals.
DE_MINIMA_SRSS: float = 0.25

MARGE_TEMPS_CONTROL: float = 1.0  # segons per 100
INCREMENT_RPE_CONTROL: int = 1
INCREMENT_BRACADES_CONTROL: float = 1.0
REFERENCIES_CONTROL: int = 3

MINIM_ALERTES_RECOMANACIO: int = 2


def _setmana(dilluns: date) -> tuple[date, date]:
    return dilluns, dilluns + timedelta(days=6)


def alerta_srss(
    registres: list[RegistreSRSS],
    dilluns: date,
    finestra: int = FINESTRA_SRSS,
    minim: int = MINIM_REGISTRES_SRSS,
    desviacions: float = DESVIACIONS_SRSS,
) -> dict | None:
    """
    Alerta `srss_baix` si dos registres seguits de la setmana surten de la
    línia base individual (calculada amb els registres anteriors a cada dia).
    """
    ordenats = sorted(registres, key=lambda r: r.data)
    inici, fi = _setmana(dilluns)
    fora: list[RegistreSRSS | None] = []
    for i, r in enumerate(ordenats):
        if not inici <= r.data <= fi:
            continue
        previs = ordenats[max(0, i - finestra):i]
        if len(previs) < minim:
            fora.append(None)
            continue
        rec = [p.mitjana_recuperacio for p in previs]
        est = [p.mitjana_estres for p in previs]
        de_rec = max(statistics.stdev(rec), DE_MINIMA_SRSS)
        de_est = max(statistics.stdev(est), DE_MINIMA_SRSS)
        baix = r.mitjana_recuperacio < statistics.mean(rec) - desviacions * de_rec
        alt = r.mitjana_estres > statistics.mean(est) + desviacions * de_est
        fora.append(r if (baix or alt) else None)

    for anterior, actual in pairwise(fora):
        if anterior is not None and actual is not None:
            return {
                "tipus": "srss_baix",
                "setmana": dilluns.isoformat(),
                "dies": [anterior.data.isoformat(), actual.data.isoformat()],
                "missatge": (
                    f"Benestar (SRSS) fora de la línia base el {anterior.data:%d/%m} "
                    f"i el {actual.data:%d/%m}"
                ),
            }
    return None


def alerta_serie_control(
    registres: list[RegistreSerieControl],
    dilluns: date,
    referencies: int = REFERENCIES_CONTROL,
) -> dict | None:
    """
    Alerta `serie_control` si la sèrie de control de la setmana surt al mateix
    temps (o més lenta) que la referència però amb més esforç o més braçades.
    """
    ordenats = sorted(registres, key=lambda r: r.data)
    inici, fi = _setmana(dilluns)
    de_la_setmana = [r for r in ordenats if inici <= r.data <= fi]
    if not de_la_setmana:
        return None
    actual = de_la_setmana[-1]
    previs = [r for r in ordenats if r.data < inici][-referencies:]
    if not previs:
        return None

    temps_ref = statistics.mean(r.temps_mitja for r in previs)
    if actual.temps_mitja < temps_ref - MARGE_TEMPS_CONTROL:
        return None  # més ràpid: cap alerta

    motius: list[str] = []
    rpes = [r.rpe for r in previs if r.rpe is not None]
    if actual.rpe is not None and rpes:
        rpe_ref = statistics.mean(rpes)
        if actual.rpe >= rpe_ref + INCREMENT_RPE_CONTROL:
            motius.append(f"esforç {actual.rpe} (referència {rpe_ref:.1f})")
    bracades = [r.bracades_mitja for r in previs if r.bracades_mitja is not None]
    if actual.bracades_mitja is not None and bracades:
        brac_ref = statistics.mean(bracades)
        if actual.bracades_mitja >= brac_ref + INCREMENT_BRACADES_CONTROL:
            motius.append(
                f"braçades {actual.bracades_mitja:.1f} (referència {brac_ref:.1f})"
            )
    if not motius:
        return None
    return {
        "tipus": "serie_control",
        "setmana": dilluns.isoformat(),
        "missatge": (
            f"Sèrie de control del {actual.data:%d/%m}: {actual.temps_mitja:.1f}\"/100 "
            f"(referència {temps_ref:.1f}\") amb " + " i ".join(motius)
        ),
    }


def avaluar_setmana(
    dilluns: date,
    sessions: list[SessioRealitzada],
    srss: list[RegistreSRSS],
    controls: list[RegistreSerieControl],
    setmanes_excloses: frozenset[date] = frozenset(),
    ratio_planificat: float = 1.0,
) -> list[dict]:
    """
    Alertes de recuperació de la setmana de `dilluns` i, si n'hi ha 2 o més,
    l'avís `recomanacio_setmana_seguent`.

    També avisa (`dades_incompletes`) si hi ha sessions de la setmana sense RPE
    o dies d'entrenament sense SRSS: les alertes només són fiables amb dades.
    """
    inici, fi = _setmana(dilluns)
    alertes = [
        a
        for a in (
            carrega.alerta_carrega_setmanal(
                sessions, dilluns, setmanes_excloses, ratio_planificat
            ),
            alerta_srss(srss, dilluns),
            alerta_serie_control(controls, dilluns),
        )
        if a is not None
    ]

    avisos = list(alertes)
    if len(alertes) >= MINIM_ALERTES_RECOMANACIO:
        avisos.append({
            "tipus": "recomanacio_setmana_seguent",
            "setmana": dilluns.isoformat(),
            "alertes": [a["tipus"] for a in alertes],
            "missatge": (
                f"{len(alertes)} alertes de recuperació la setmana del {dilluns:%d/%m}: "
                "es recomana que la setmana següent mantingui el volum mínim i que la "
                "qualitat sigui només de velocitat alàctica (decisió del coach)"
            ),
        })

    de_la_setmana = [
        s for s in sessions if inici <= date.fromisoformat(s.data) <= fi
    ]
    sense_rpe = carrega.sessions_sense_rpe(de_la_setmana)
    dies_entrenament = {date.fromisoformat(s.data) for s in de_la_setmana}
    dies_srss = {r.data for r in srss}
    sense_srss = sorted(dies_entrenament - dies_srss)
    if sense_rpe or sense_srss:
        parts = []
        if sense_rpe:
            parts.append(f"{len(sense_rpe)} sessions sense RPE")
        if sense_srss:
            parts.append(f"{len(sense_srss)} dies sense SRSS")
        avisos.append({
            "tipus": "dades_incompletes",
            "setmana": dilluns.isoformat(),
            "missatge": f"Setmana del {dilluns:%d/%m}: " + ", ".join(parts),
        })
    return avisos

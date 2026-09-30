"""Utilitats de dates: setmanes ISO (dilluns-diumenge) i format de Microcicle.dates."""

import re
from datetime import date, timedelta


def dilluns_setmana(data: date) -> date:
    """Dilluns de la setmana ISO que conté `data`."""
    return data - timedelta(days=data.weekday())


def seguent_dilluns(avui: date) -> date:
    """
    Primer dia de planificació (G2): `avui` si és dilluns; si no, el dilluns
    de la setmana ISO següent. Mai es comença una setmana a mitges.
    """
    if avui.weekday() == 0:
        return avui
    return dilluns_setmana(avui) + timedelta(days=7)


def parsejar_rang_dates(dates: str) -> tuple[date, date]:
    """
    Parseja Microcicle.dates en un dels dos formats possibles:
    - "21-27/09/2026" (mateix mes)
    - "28/09-04/10/2026" (creua mes)

    Retorna (data_inici, data_fi). Llança ValueError si el format no
    es reconeix.
    """
    m = re.match(r"^(\d{1,2})-(\d{1,2})/(\d{1,2})/(\d{4})$", dates)
    if m:
        dia_ini, dia_fi, mes, any_ = (int(x) for x in m.groups())
        return date(any_, mes, dia_ini), date(any_, mes, dia_fi)

    m = re.match(r"^(\d{1,2})/(\d{1,2})-(\d{1,2})/(\d{1,2})/(\d{4})$", dates)
    if m:
        dia_ini, mes_ini, dia_fi, mes_fi, any_ = (int(x) for x in m.groups())
        # Setmana que creua d'any (p.ex. "28/12-03/01/2027"): l'inici és l'any anterior.
        any_ini = any_ - 1 if mes_ini > mes_fi else any_
        return date(any_ini, mes_ini, dia_ini), date(any_, mes_fi, dia_fi)

    raise ValueError(f"Format de dates no reconegut: {dates!r}")

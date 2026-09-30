"""Tests per a blondswim.utils.dates (G2)."""

from datetime import date

import pytest

from blondswim.utils.dates import dilluns_setmana, parsejar_rang_dates, seguent_dilluns


@pytest.mark.parametrize(
    ("avui", "esperat"),
    [
        (date(2026, 9, 30), date(2026, 10, 5)),   # dimecres -> dilluns següent
        (date(2026, 10, 5), date(2026, 10, 5)),   # dilluns -> el mateix dia
        (date(2026, 10, 4), date(2026, 10, 5)),   # diumenge -> l'endemà
        (date(2026, 12, 31), date(2027, 1, 4)),   # canvi d'any
    ],
)
def test_seguent_dilluns(avui, esperat):
    assert seguent_dilluns(avui) == esperat
    assert seguent_dilluns(avui).weekday() == 0


def test_dilluns_setmana():
    assert dilluns_setmana(date(2026, 9, 30)) == date(2026, 9, 28)
    assert dilluns_setmana(date(2026, 9, 28)) == date(2026, 9, 28)


def test_parsejar_rang_mateix_mes():
    assert parsejar_rang_dates("05-11/10/2026") == (date(2026, 10, 5), date(2026, 10, 11))


def test_parsejar_rang_creua_mes():
    assert parsejar_rang_dates("28/09-04/10/2026") == (date(2026, 9, 28), date(2026, 10, 4))


def test_parsejar_rang_creua_any():
    """Setmana 53/2026: el dilluns és del 2026, encara que el text porti 2027."""
    assert parsejar_rang_dates("28/12-03/01/2027") == (date(2026, 12, 28), date(2027, 1, 3))


def test_parsejar_rang_format_invalid():
    with pytest.raises(ValueError):
        parsejar_rang_dates("setmana 40")

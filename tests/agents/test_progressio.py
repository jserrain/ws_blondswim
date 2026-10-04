"""Bandes, zones, calibratge, projecció i ritme de cursa de referència."""

from datetime import date

import pytest

from blondswim.agents.progressio import (
    avaluar_pic,
    banda,
    format_informe,
    projectar,
    temps_ritme_cursa,
    zona,
)
from blondswim.models.nedador import NivellActual, ObjectiuProva, ParametresProgressio
from blondswim.models.resultat import ResultatCompeticio
from tests.agents.test_proves import calendari_jep, nedador_jep

NIVELL = NivellActual(millor_marca=77.0, estimacio_pessimista=80.0)
OBJECTIU = ObjectiuProva(competicio_id="cat", realista=75.0, ambicios=72.0)
INICI = date(2026, 10, 17)
FI = date(2027, 1, 16)


def _res(comp, prova, temps):
    return ResultatCompeticio(competicio_id=comp, prova=prova, temps=temps)


# --- Banda i zones --------------------------------------------------------------


def test_banda_exemple_del_disseny():
    # Taula de la secció 7.2: Barceloneta, Horta, Sabadell, CNSF, A sense taper.
    esperat = {
        date(2026, 10, 17): (77.0, 80.0),
        date(2026, 11, 7): (76.18, 79.19),
        date(2026, 11, 21): (75.63, 78.65),
        date(2026, 12, 12): (74.81, 77.85),
        date(2027, 1, 16): (73.44, 76.5),
    }
    for data, (rapid, lent) in esperat.items():
        r, ll = banda(NIVELL, OBJECTIU, INICI, FI, data, 0.02)
        assert r == pytest.approx(rapid, abs=0.01)
        assert ll == pytest.approx(lent, abs=0.01)


def test_banda_fora_de_l_interval_es_limita():
    assert banda(NIVELL, OBJECTIU, INICI, FI, date(2026, 9, 1), 0.02) == (77.0, 80.0)
    r, ll = banda(NIVELL, OBJECTIU, INICI, FI, date(2027, 3, 1), 0.02)
    assert (r, ll) == pytest.approx((73.44, 76.5))


@pytest.mark.parametrize(
    ("temps", "esperada"),
    [(76.0, "blava"), (77.0, "verda"), (80.0, "verda"), (80.7, "groga"), (80.9, "vermella")],
)
def test_zones(temps, esperada):
    assert zona(temps, 77.0, 80.0, 0.01) == esperada


# --- Projecció ------------------------------------------------------------------


def test_projeccio_amb_dos_resultats():
    params = ParametresProgressio()
    # 78,6" el dia 0 i 77,9" el dia 21 -> -1/30 s/dia; a 91 dies: 75,57" sense taper.
    pr = projectar([(0, 78.6), (21, 77.9)], 91, OBJECTIU, params)
    assert pr.temps_a == pytest.approx(75.57 / 1.02, abs=0.02)
    assert pr.cami == "realista"
    assert pr.minim < pr.temps_a < pr.maxim
    assert pr.n == 2


def test_projeccio_interval_creix_amb_l_extrapolacio():
    params = ParametresProgressio()
    a_prop = projectar([(0, 78.6), (56, 77.0)], 60, OBJECTIU, params)
    lluny = projectar([(0, 78.6), (21, 78.0)], 91, OBJECTIU, params)
    assert (lluny.maxim - lluny.minim) > (a_prop.maxim - a_prop.minim)


def test_projeccio_camins():
    params = ParametresProgressio()
    assert projectar([(0, 77.0), (30, 75.5)], 91, OBJECTIU, params).cami == "ambicios"
    assert projectar([(0, 80.0), (30, 80.0)], 91, OBJECTIU, params).cami == "no_arriba"


def test_sense_projeccio():
    params = ParametresProgressio()
    assert projectar([(0, 78.0)], 91, OBJECTIU, params) is None
    assert projectar([(5, 78.0), (5, 77.0)], 91, OBJECTIU, params) is None


# --- Avaluació d'un pic ---------------------------------------------------------


def _estat(estats, nom):
    return next(e for e in estats if e.nom == nom)


def test_avaluar_pic_sense_resultats():
    pic, estats = avaluar_pic(nedador_jep(), calendari_jep(), [], date(2026, 10, 4))
    assert pic.numero == 1
    lliure = _estat(estats, "100m Lliure")
    assert [p.competicio.id for p in lliure.punts] == ["barceloneta", "horta", "cnsf"]
    assert lliure.punts[0].rapid == pytest.approx(77.08)
    assert lliure.punts[0].lent == pytest.approx(78.0)
    assert lliure.projeccio is None
    assert lliure.ritme_cursa == 75.0  # sense resultats: el realista


def test_avaluar_pic_amb_resultats():
    resultats = [
        _res("barceloneta", "100 lliures", 77.6),
        _res("horta", "100m Lliure", 77.2),
        _res("horta", "100m Lliure", 77.4),  # dues curses: compta la millor
    ]
    _, estats = avaluar_pic(nedador_jep(), calendari_jep(), resultats, date(2026, 11, 8))
    lliure = _estat(estats, "100m Lliure")
    assert [p.resultat for p in lliure.punts] == [77.6, 77.2, None]
    assert [p.zona for p in lliure.punts] == ["verda", "verda", None]
    assert lliure.exigencia_realista == pytest.approx((77.6 - 76.5) / 77.6)
    assert lliure.projeccio is not None and lliure.projeccio.n == 2
    assert lliure.ultima_zona == "verda"
    assert lliure.ritme_cursa == pytest.approx(max(lliure.projeccio.temps_a, 72.0))
    assert lliure.avisos == []


def test_nova_millor_marca_i_dues_vermelles():
    resultats = [_res("barceloneta", "100m Lliure", 76.9)]
    _, estats = avaluar_pic(nedador_jep(), calendari_jep(), resultats, date(2026, 10, 20))
    assert [a["tipus"] for a in _estat(estats, "100m Lliure").avisos] == ["nova_millor_marca"]

    lents = [_res("barceloneta", "100m Lliure", 80.0), _res("horta", "100m Lliure", 80.5)]
    _, estats = avaluar_pic(nedador_jep(), calendari_jep(), lents, date(2026, 11, 8))
    lliure = _estat(estats, "100m Lliure")
    assert [p.zona for p in lliure.punts[:2]] == ["vermella", "vermella"]
    tipus = [a["tipus"] for a in lliure.avisos]
    assert "sense_millora" in tipus
    assert "objectiu_exigent_calibrat" in tipus
    assert lliure.projeccio.cami == "no_arriba"
    assert lliure.ritme_cursa == pytest.approx(lliure.projeccio.temps_a)


def test_ritme_cursa():
    from blondswim.agents.progressio import Projeccio

    assert temps_ritme_cursa(None, None) is None
    assert temps_ritme_cursa(OBJECTIU, None) == 75.0  # sense projecció: el realista
    bona = Projeccio(temps_a=73.5, minim=72.0, maxim=75.0, n=2, cami="realista")
    assert temps_ritme_cursa(OBJECTIU, bona) == 73.5
    molt_bona = Projeccio(temps_a=71.0, minim=70.0, maxim=72.0, n=3, cami="ambicios")
    assert temps_ritme_cursa(OBJECTIU, molt_bona) == 72.0  # mai més ràpid que l'ambiciós
    dolenta = Projeccio(temps_a=76.2, minim=75.0, maxim=77.4, n=2, cami="no_arriba")
    assert temps_ritme_cursa(OBJECTIU, dolenta) == 76.2


def test_un_sol_resultat_no_mou_el_ritme():
    # 1'18"4 a mitja banda: és incertesa inicial, no progrés -> ritme del realista.
    resultats = [_res("barceloneta", "100m Lliure", 78.4)]
    _, estats = avaluar_pic(nedador_jep(), calendari_jep(), resultats, date(2026, 10, 20))
    assert _estat(estats, "100m Lliure").ritme_cursa == 75.0


def test_format_informe():
    resultats = [_res("barceloneta", "100m Lliure", 77.6), _res("horta", "100m Lliure", 77.0)]
    pic, estats = avaluar_pic(nedador_jep(), calendari_jep(), resultats, date(2026, 11, 8))
    text = "\n".join(format_informe(pic, estats, [{"missatge": "falta X"}]))
    assert "Pic 1:" in text
    assert "100m Lliure (P, mixt)" in text
    assert "1'17\"6" in text and "verda" in text
    assert "Projecció a la A" in text
    assert "⚠ falta X" in text


def test_format_informe_sense_pic():
    assert format_informe(None, []) == ["Cap competició A pendent al calendari."]

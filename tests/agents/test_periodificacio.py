"""Tests per a la periodificació determinista de la temporada."""

from datetime import date

import pytest

from blondswim.agents.periodificacio import periodificar_temporada
from blondswim.models.calendari import Competicio


@pytest.fixture
def competicions() -> list[Competicio]:
    """Calendari de test: A 16/01/2027, A 29/05/2027, B 07/11/2026, C 24/10/2026."""
    return [
        Competicio(
            id="a1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="a2",
            nom="Campionat Espanya",
            data_inici="2027-05-29",
            data_fi="2027-05-31",
            classe="A",
            piscina="50m",
        ),
        Competicio(
            id="b1",
            nom="Competició B",
            data_inici="2026-11-07",
            data_fi="2026-11-08",
            classe="B",
            piscina="25m",
        ),
        Competicio(
            id="c1",
            nom="Competició C",
            data_inici="2026-10-24",
            data_fi="2026-10-25",
            classe="C",
            piscina="25m",
        ),
    ]


@pytest.fixture
def plans(competicions):
    """Periodificació de la temporada 28/09/2026 - 09/07/2027."""
    plans, _avisos = periodificar_temporada(
        competicions, date(2026, 9, 28), date(2027, 7, 9)
    )
    return plans


def _plan(plans, any_iso: int, setmana_iso: int):
    for p in plans:
        if p.any_iso == any_iso and p.setmana_iso == setmana_iso:
            return p
    raise AssertionError(f"No s'ha trobat la setmana {setmana_iso}/{any_iso}")


def test_cursa_setmana_2_2027(plans):
    """Cursa = setmana ISO 2/2027 (11-17/01)."""
    p = _plan(plans, 2027, 2)
    assert p.fase == "Cursa"
    assert p.dilluns == date(2027, 1, 11)
    assert p.diumenge == date(2027, 1, 17)


def test_peak_setmanes_53_2026_i_1_2027(plans):
    """Peak = setmanes 53/2026 i 1/2027 (28/12-10/01)."""
    p53 = _plan(plans, 2026, 53)
    p1 = _plan(plans, 2027, 1)
    assert p53.fase == "Peak"
    assert p1.fase == "Peak"
    assert p53.dilluns == date(2026, 12, 28)
    assert p1.diumenge == date(2027, 1, 10)


def test_build2_setmanes_49_a_52(plans):
    """Build2 = setmanes 49-52 (30/11-27/12)."""
    for s in (49, 50, 51, 52):
        assert _plan(plans, 2026, s).fase == "Build2"
    assert _plan(plans, 2026, 49).dilluns == date(2026, 11, 30)
    assert _plan(plans, 2026, 52).diumenge == date(2026, 12, 27)


def test_build1_setmanes_45_a_48(plans):
    """Build1 = setmanes 45-48 (02/11-29/11)."""
    for s in (45, 46, 47, 48):
        assert _plan(plans, 2026, s).fase == "Build1"
    assert _plan(plans, 2026, 45).dilluns == date(2026, 11, 2)
    assert _plan(plans, 2026, 48).diumenge == date(2026, 11, 29)


def test_base_blocs_3_i_2(plans):
    """Base = setmanes 40-44, en blocs de 3 (40-42) i 2 (43-44)."""
    base = [p for p in plans if p.fase == "Base" and p.any_iso == 2026]
    setmanes = sorted(p.setmana_iso for p in base)
    assert setmanes == [40, 41, 42, 43, 44]

    bloc_40 = _plan(plans, 2026, 40).bloc_id
    assert _plan(plans, 2026, 41).bloc_id == bloc_40
    assert _plan(plans, 2026, 42).bloc_id == bloc_40

    bloc_43 = _plan(plans, 2026, 43).bloc_id
    assert bloc_43 != bloc_40
    assert _plan(plans, 2026, 44).bloc_id == bloc_43


def test_avis_bloc_curt(competicions):
    """El bloc de 2 setmanes (43-44) genera l'avís 'bloc_curt'."""
    _plans, avisos = periodificar_temporada(
        competicions, date(2026, 9, 28), date(2027, 7, 9)
    )
    curts = [a for a in avisos if a.get("tipus_avis") == "bloc_curt"]
    assert len(curts) >= 1


def test_descarregues_setmanes_42_44_48_52(plans):
    """Descàrrega a les setmanes 42, 44, 48 i 52."""
    for s in (42, 44, 48, 52):
        assert _plan(plans, 2026, s).es_descarrega is True
    for s in (40, 41, 43, 45, 46, 47, 49, 50, 51):
        assert _plan(plans, 2026, s).es_descarrega is False


def test_transicio_setmana_3_2027(plans):
    """Transicio = setmana 3/2027 (18-24/01)."""
    p = _plan(plans, 2027, 3)
    assert p.fase == "Transicio"
    assert p.dilluns == date(2027, 1, 18)
    assert p.diumenge == date(2027, 1, 24)


def test_setmana_45_porta_la_b_i_es_build1(plans):
    """La setmana 45 porta la B del 07/11 i es manté com a Build1."""
    p = _plan(plans, 2026, 45)
    assert p.fase == "Build1"
    assert any(c.classe == "B" for c in p.competicions_b_c)


def test_la_c_no_altera_cap_fase(plans):
    """La C del 24/10 no altera cap fase (setmana 43, Base)."""
    p = _plan(plans, 2026, 43)
    assert p.fase == "Base"
    assert any(c.classe == "C" for c in p.competicions_b_c)


def test_tots_els_plans_comencen_dilluns_i_acaben_diumenge(plans):
    """R1: tots els SetmanaPlan tenen dilluns.weekday()==0 i diumenge.weekday()==6."""
    for p in plans:
        assert p.dilluns.weekday() == 0
        assert p.diumenge.weekday() == 6
        assert (p.diumenge - p.dilluns).days == 6


def test_peak_setmanes_53_i_1_comparteixen_bloc(plans):
    """Peak (2 setmanes) és un únic bloc: 53/2026 i 1/2027 comparteixen bloc_id."""
    p53 = _plan(plans, 2026, 53)
    p1 = _plan(plans, 2027, 1)
    assert p53.bloc_id == p1.bloc_id


# --- Doble pic: dues proves A a <= 4 setmanes ---


def _a(id_, data_inici, data_fi):
    from blondswim.models.calendari import Competicio
    return Competicio(id=id_, nom=id_, data_inici=data_inici, data_fi=data_fi,
                      classe="A", piscina="25m")


DOBLE = [_a("cat", "2027-01-16", "2027-01-17"), _a("esp", "2027-02-06", "2027-02-07")]


def test_doble_pic_sense_transicio_i_peak_curt():
    from datetime import date

    from blondswim.agents.periodificacio import periodificar_temporada

    plans, _ = periodificar_temporada(DOBLE, date(2026, 11, 23), date(2027, 3, 7))
    fase = {(p.any_iso, p.setmana_iso): p.fase for p in plans}
    assert fase[(2027, 2)] == "Cursa"
    assert fase[(2027, 3)] == "Build2"   # entre les dues A: entrenament, no Transició
    assert fase[(2027, 4)] == "Peak"     # taper curt (1 setmana)
    assert fase[(2027, 5)] == "Cursa"
    assert fase[(2027, 6)] == "Transicio"
    assert fase[(2026, 53)] == "Peak" and fase[(2027, 1)] == "Peak"  # taper principal


def test_doble_pic_tambe_si_la_primera_ja_ha_passat():
    """Planificant des de la setmana 3, la setmana 3 continua sent Build2."""
    from datetime import date

    from blondswim.agents.periodificacio import periodificar_temporada

    plans, _ = periodificar_temporada(DOBLE, date(2027, 1, 18), date(2027, 3, 7))
    fase = {(p.any_iso, p.setmana_iso): p.fase for p in plans}
    assert fase[(2027, 3)] == "Build2"
    assert fase[(2027, 4)] == "Peak"

"""Tests de la càrrega real (sRPE) i dels indicadors de recuperació (Fase E+I)."""

from datetime import date, timedelta

import pytest

from blondswim.agents import carrega, recuperacio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.registre import RegistreSerieControl, RegistreSRSS

DILLUNS = date(2026, 11, 2)


def _sessio(dia: date, minuts: float, rpe: int | None, modalitat: str = "natacio"):
    return SessioRealitzada(
        data=dia.isoformat(), temps_total_min=minuts, rpe_sessio=rpe, modalitat=modalitat
    )


def _setmana_carrega(dilluns: date, rpe: int, minuts: float = 60, dies: int = 5):
    """5 sessions de natació de `minuts` amb RPE `rpe` (carrega = rpe*minuts*dies)."""
    return [_sessio(dilluns + timedelta(days=i), minuts, rpe) for i in range(dies)]


# --- carrega ---


def test_carrega_diaria_suma_aigua_i_gimnas():
    dia = DILLUNS
    sessions = [
        _sessio(dia, 60, 4),
        _sessio(dia, 45, 6, modalitat="gimnas"),
        _sessio(dia + timedelta(days=1), 70, None),  # sense RPE: no compta
    ]
    assert carrega.carrega_diaria(sessions) == {dia: 240 + 270}
    assert len(carrega.sessions_sense_rpe(sessions)) == 1


def test_carrega_setmanal_per_dilluns():
    sessions = _setmana_carrega(DILLUNS, 4) + _setmana_carrega(DILLUNS + timedelta(weeks=1), 5)
    assert carrega.carrega_setmanal(sessions) == {
        DILLUNS: 1200,
        DILLUNS + timedelta(weeks=1): 1500,
    }


def test_evolucio_carrega_mitjanes_exponencials():
    sessions = [_sessio(DILLUNS, 70, 10)]  # 700 UA el primer dia
    estats = carrega.evolucio_carrega(sessions, fins_a=DILLUNS + timedelta(days=2))
    assert [e.carrega for e in estats] == [700, 0, 0]
    assert estats[0].aguda == pytest.approx(100.0)
    assert estats[0].cronica == pytest.approx(25.0)
    # Els dies sense sessió fan baixar l'aguda més ràpid que la crònica.
    assert estats[2].aguda < estats[0].aguda
    assert estats[2].balanc == pytest.approx(estats[2].cronica - estats[2].aguda)


def test_evolucio_carrega_sense_dades():
    assert carrega.evolucio_carrega([]) == []


def _historial_4_setmanes(rpe_actual: int) -> list[SessioRealitzada]:
    sessions = []
    for i in range(4, 0, -1):
        sessions += _setmana_carrega(DILLUNS - timedelta(weeks=i), 4)
    return sessions + _setmana_carrega(DILLUNS, rpe_actual)


def test_alerta_carrega_setmanal_per_sobre_del_15():
    alerta = carrega.alerta_carrega_setmanal(_historial_4_setmanes(5), DILLUNS)
    assert alerta is not None
    assert alerta["tipus"] == "carrega_setmanal_alta"
    assert alerta["ratio"] == 1.25


def test_sense_alerta_dins_del_15():
    assert carrega.alerta_carrega_setmanal(_historial_4_setmanes(4), DILLUNS) is None


def test_increment_planificat_no_alerta():
    assert (
        carrega.alerta_carrega_setmanal(
            _historial_4_setmanes(5), DILLUNS, ratio_planificat=1.10
        )
        is None
    )


def test_setmanes_excloses_de_la_base():
    # Base: 3 setmanes a 1200 UA i una descàrrega a 600 UA; setmana actual 1500.
    sessions = []
    for i in range(4, 0, -1):
        rpe = 2 if i == 1 else 4
        sessions += _setmana_carrega(DILLUNS - timedelta(weeks=i), rpe)
    sessions += _setmana_carrega(DILLUNS, 5)

    # Amb la descàrrega a la base, la mitjana baixa a 1050.
    alerta = carrega.alerta_carrega_setmanal(sessions, DILLUNS)
    assert alerta["ratio"] == pytest.approx(1500 / 1050, abs=0.01)
    # Excloent-la, la base és 1200.
    exclosa = frozenset({DILLUNS - timedelta(weeks=1)})
    alerta = carrega.alerta_carrega_setmanal(sessions, DILLUNS, setmanes_excloses=exclosa)
    assert alerta["ratio"] == 1.25


def test_sense_alerta_amb_poques_setmanes_de_base():
    sessions = _setmana_carrega(DILLUNS - timedelta(weeks=1), 2) + _setmana_carrega(DILLUNS, 9)
    assert carrega.alerta_carrega_setmanal(sessions, DILLUNS) is None


# --- SRSS ---


def _srss(dia: date, rec: int, est: int) -> RegistreSRSS:
    return RegistreSRSS(nedador_id="jep", data=dia, recuperacio=[rec] * 4, estres=[est] * 4)


def _base_srss(n: int = 12) -> list[RegistreSRSS]:
    """n registres anteriors a DILLUNS alternant recuperació 4/5 i estrès 1/2."""
    inici = DILLUNS - timedelta(days=n)
    return [
        _srss(inici + timedelta(days=i), 4 + i % 2, 1 + i % 2) for i in range(n)
    ]


def test_alerta_srss_dos_dies_seguits():
    registres = _base_srss() + [_srss(DILLUNS, 2, 1), _srss(DILLUNS + timedelta(days=1), 2, 1)]
    alerta = recuperacio.alerta_srss(registres, DILLUNS)
    assert alerta is not None
    assert alerta["dies"] == [DILLUNS.isoformat(), (DILLUNS + timedelta(days=1)).isoformat()]


def test_alerta_srss_estres_alt():
    registres = _base_srss() + [_srss(DILLUNS, 5, 5), _srss(DILLUNS + timedelta(days=2), 4, 5)]
    assert recuperacio.alerta_srss(registres, DILLUNS) is not None


def test_srss_un_sol_dia_dolent_no_alerta():
    registres = _base_srss() + [
        _srss(DILLUNS, 2, 1),
        _srss(DILLUNS + timedelta(days=1), 5, 1),
        _srss(DILLUNS + timedelta(days=2), 2, 1),
    ]
    assert recuperacio.alerta_srss(registres, DILLUNS) is None


def test_srss_sense_linia_base_no_alerta():
    registres = _base_srss(5) + [_srss(DILLUNS, 0, 6), _srss(DILLUNS + timedelta(days=1), 0, 6)]
    assert recuperacio.alerta_srss(registres, DILLUNS) is None


# --- Sèrie de control ---


def _control(dia: date, temps: float, rpe: int | None = 4, bracades: float | None = 18):
    return RegistreSerieControl(
        nedador_id="jep",
        data=dia,
        temps_100=[temps] * 4,
        bracades_llargada=[bracades] * 4 if bracades is not None else None,
        rpe=rpe,
    )


def _controls_previs() -> list[RegistreSerieControl]:
    return [_control(DILLUNS - timedelta(weeks=i) + timedelta(days=2), 100) for i in (3, 2, 1)]


def test_control_mateix_temps_mes_esforc():
    registres = _controls_previs() + [_control(DILLUNS + timedelta(days=2), 100.5, rpe=6)]
    alerta = recuperacio.alerta_serie_control(registres, DILLUNS)
    assert alerta is not None and "esforç 6" in alerta["missatge"]


def test_control_mes_bracades():
    registres = _controls_previs() + [_control(DILLUNS + timedelta(days=2), 100, bracades=19.5)]
    alerta = recuperacio.alerta_serie_control(registres, DILLUNS)
    assert alerta is not None and "braçades" in alerta["missatge"]


def test_control_mes_rapid_no_alerta():
    registres = _controls_previs() + [_control(DILLUNS + timedelta(days=2), 98, rpe=6)]
    assert recuperacio.alerta_serie_control(registres, DILLUNS) is None


def test_control_igual_no_alerta():
    registres = _controls_previs() + [_control(DILLUNS + timedelta(days=2), 100)]
    assert recuperacio.alerta_serie_control(registres, DILLUNS) is None


def test_control_sense_referencia_no_alerta():
    assert (
        recuperacio.alerta_serie_control([_control(DILLUNS, 100, rpe=9)], DILLUNS) is None
    )


# --- Regla de decisió ---


def _srss_setmana_completa(dolent: bool) -> list[RegistreSRSS]:
    rec = 2 if dolent else 4
    return _base_srss() + [_srss(DILLUNS + timedelta(days=i), rec, 1) for i in range(5)]


def test_dues_alertes_generen_recomanacio():
    avisos = recuperacio.avaluar_setmana(
        DILLUNS,
        _historial_4_setmanes(5),
        _srss_setmana_completa(dolent=True),
        _controls_previs(),
    )
    tipus = [a["tipus"] for a in avisos]
    assert tipus == ["carrega_setmanal_alta", "srss_baix", "recomanacio_setmana_seguent"]
    assert avisos[-1]["alertes"] == ["carrega_setmanal_alta", "srss_baix"]


def test_una_alerta_sense_recomanacio():
    avisos = recuperacio.avaluar_setmana(
        DILLUNS,
        _historial_4_setmanes(5),
        _srss_setmana_completa(dolent=False),
        _controls_previs(),
    )
    assert [a["tipus"] for a in avisos] == ["carrega_setmanal_alta"]


def test_dades_incompletes():
    sessions = _historial_4_setmanes(4)
    sessions[-1] = _sessio(DILLUNS + timedelta(days=4), 60, None)
    avisos = recuperacio.avaluar_setmana(DILLUNS, sessions, _base_srss(), [])
    incompletes = [a for a in avisos if a["tipus"] == "dades_incompletes"]
    assert len(incompletes) == 1
    assert "1 sessions sense RPE" in incompletes[0]["missatge"]
    assert "5 dies sense SRSS" in incompletes[0]["missatge"]

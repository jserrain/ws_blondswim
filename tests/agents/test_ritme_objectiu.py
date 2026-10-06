"""Sèries de ritme objectiu: progressió condicionada als temps registrats."""

from datetime import date, timedelta

import pytest

from blondswim.agents import ritme_objectiu as ro
from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.agents.periodificacio import SetmanaPlan
from blondswim.agents.proves import Pic
from blondswim.models.calendari import Competicio
from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.registre import RegistreSerieObjectiu

PIC = Pic(numero=1, competicions=[Competicio(
    id="cat", nom="Cat", data_inici="2027-01-16", data_fi="2027-01-17", classe="A",
    piscina="25m", proves=["100m Lliure", "100m IM"])])


def _nedador(**kw) -> Nedador:
    return Nedador(
        id="jep", nom="Jep", categoria="master", mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dimecres", "dijous", "divendres"],
        ritmes_css=RitmesCSS(recuperacio=110, a1=104, a2=98, a3=94, velocitat=83.3),
        proves_objectiu=[
            {"prova": "100m Lliure", "prioritat": "P",
             "nivell_actual": {"millor_marca": "1:17.08", "estimacio_pessimista": "1:20"},
             "objectius": [{"competicio_id": "cat", "realista": "1:15", "ambicios": "1:12"}]},
            {"prova": "100m IM", "prioritat": "P",
             "nivell_actual": {"millor_marca": "1:38", "estimacio_pessimista": "1:38"},
             "objectius": [{"competicio_id": "cat", "realista": "1:38", "ambicios": "1:35"}]},
            {"prova": "200m Lliure", "prioritat": "S"},
        ],
        **kw,
    )


def _plans(fases: list[tuple[str, bool]], inici=date(2026, 10, 5)) -> list[SetmanaPlan]:
    plans, index, anterior = [], 0, None
    for i, (fase, desc) in enumerate(fases):
        dil = inici + timedelta(weeks=i)
        index = index + 1 if fase == anterior else 0
        anterior = fase
        plans.append(SetmanaPlan(
            any_iso=dil.isocalendar()[0], setmana_iso=dil.isocalendar()[1], dilluns=dil,
            diumenge=dil + timedelta(days=6), fase=fase, bloc_id=fase, index_dins_bloc=index,
            es_descarrega=desc))
    return plans


# Base x3 + descàrrega, Build1 x3 + descàrrega, Build2 x2, Peak, Cursa
FASES = ([("Base", False)] * 3 + [("Base", True)] + [("Build1", False)] * 3
         + [("Build1", True)] + [("Build2", False)] * 2 + [("Peak", False), ("Cursa", False)])


def _reg(dia: date, objectiu: float, temps: float, prova="100m Lliure"):
    return RegistreSerieObjectiu(nedador_id="jep", data=dia, prova=prova,
                                 objectiu=objectiu, temps=[temps] * 6)


def test_series_per_defecte_una_per_prova_principal():
    series = ro.series_del_nedador(_nedador())
    assert [(s.prova, s.dia, s.distancia) for s in series] == [
        ("100m Lliure", "dimarts", 50), ("100m IM", "dijous", 50)
    ]


@pytest.mark.parametrize(
    ("temps", "esperat"),
    [(40.0, "dins"), (40.4, "dins"), (40.5, "per_sobre"), (39.0, "molt_per_sota")],
)
def test_classificar(temps, esperat):
    assert ro.classificar(temps, 40.0, 0.01) == esperat


def test_reproduir_avanca_salta_i_retrocedeix():
    d = date(2026, 10, 6)
    regs = [
        _reg(d, 40.0, 40.0),                          # dins -> 1
        _reg(d + timedelta(weeks=1), 39.8, 38.5),     # molt per sota -> 3
        _reg(d + timedelta(weeks=2), 39.4, 40.5),     # per sobre -> 3
        _reg(d + timedelta(weeks=3), 39.4, 40.5),     # per sobre x2 -> 2 i avís
    ]
    estat = ro.reproduir(regs, 0.01, passos=8)
    assert estat.pas == 2 and estat.darrer == "per_sobre" and len(estat.avisos) == 1


def test_passos_fins_al_pic_sense_descarregues():
    assert ro.passos_fins_al_pic(_plans(FASES), date(2026, 10, 5)) == 8


def test_forma_per_fase():
    plans = _plans(FASES)
    assert ro.forma(plans[0], 0, False) == (6, "d/1:00")
    assert ro.forma(plans[2], 5, False) == (8, "d/1:00")
    assert ro.forma(plans[3], 3, False) == (4, "d/1:00")      # descàrrega
    assert ro.forma(plans[6], 5, False) == (8, "d/0:45")      # Build1, 3a setmana
    assert ro.forma(plans[10], 8, True) == (4, "d/1:30")      # Peak, estils


def test_prescripcio_inicial_i_final():
    n, plans = _nedador(), _plans(FASES)
    [lliure, im] = ro.series_del_nedador(n)
    p = ro.prescriure(n, lliure, PIC, plans, date(2026, 10, 5), [])
    assert p.objectiu == 40.0 and (p.series, p.descans) == (6, "d/1:00")
    assert "40,0 s per 50" in p.execucio and p.passos == 8
    # Al Peak, ritme de cursa: 1:15 -> 37,5 per 50
    peak = ro.prescriure(n, lliure, PIC, plans, plans[10].dilluns, [])
    assert peak.objectiu == 37.5 and peak.series == 4
    # 100 IM amb objectiu = nivell: es consolida, mai més lent que l'inici (49,0)
    p_im = ro.prescriure(n, im, PIC, plans, date(2026, 10, 5), [])
    assert p_im.objectiu == 49.0 and "papallona-esquena" in p_im.execucio


def test_prescripcio_avanca_amb_els_registres():
    n, plans = _nedador(), _plans(FASES)
    lliure = ro.series_del_nedador(n)[0]
    regs = [_reg(date(2026, 10, 6), 40.0, 40.0)]
    p = ro.prescriure(n, lliure, PIC, plans, date(2026, 10, 12), regs)
    # final = 1:15 x 1,02 / 2 = 38,25; un pas de 8: 40,0 - 1,75/8 = 39,8
    assert p.pas == 1 and p.objectiu == 39.8 and p.series == 7
    assert "dins de l'objectiu" in p.resum


def test_avis_si_no_hi_ha_registre():
    n, plans = _nedador(), _plans(FASES)
    lliure = ro.series_del_nedador(n)[0]
    regs = [_reg(date(2026, 10, 6), 40.0, 40.0)]
    p = ro.prescriure(n, lliure, PIC, plans, date(2026, 10, 26), regs)
    assert any("sense temps registrats" in a for a in p.avisos)


def test_afegir_series_objectiu_com_a_part_fixa():
    n = _nedador()
    micro = Microcicle(setmana=41, dates="05-11/10/2026", mesocicle_id="meso_1",
                       tipus_base="carrega", volum_objectiu=13600, dies_qualitat=False,
                       test_css=False)
    sessions = generar_esquelet_sessions(n, micro)
    plans = _plans(FASES)
    prescripcions = [ro.prescriure(n, s, PIC, plans, date(2026, 10, 5), [])
                     for s in ro.series_del_nedador(n)]
    assert ro.afegir_series_objectiu(sessions, prescripcions) == []
    dimarts = next(s for s in sessions if s.dia == "dimarts")
    noms = [p.nom for p in dimarts.estructura.parts]
    assert ro.NOM_PART in noms
    assert noms.index(ro.NOM_PART) < noms.index("Qualitat")
    part = dimarts.estructura.parts[noms.index(ro.NOM_PART)]
    assert part.fixa and part.exercicis[0].volum_m == 300
    variables = [p for p in dimarts.estructura.parts if not p.fixa]
    assert sum(p.metres_objectiu for p in variables) == dimarts.volum_total - 300

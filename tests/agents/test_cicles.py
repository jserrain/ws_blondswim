"""Cicles (c/) i descansos (d/): parseig, temps per exercici i validació.

Regressió de la W41 (2026-10-05): «c/15"» fet servir com a descans i A2 a
c/1'45" amb un ritme A2 d'1'38" (7" de descans).
"""

import pytest

from blondswim.agents.cicles import (
    Descans,
    corregir_cicles,
    descans_minim,
    descans_real,
    estil_exercici,
    formatar_descans,
    parsejar_descans,
    problemes_cicles,
    taula_cicles,
    temps_exercici,
    temps_nedat,
    temps_sessio,
)
from blondswim.agents.generar_microcicle import _es_farciment
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import EstructuraSessio, Exercici, PartSessio, Sessio


def _jep() -> Nedador:
    # CSS 1'38": A1 1'44", A2 1'38", A3 1'34", Rec 1'50", Vel 1'23"3
    return Nedador(
        id="jep", nom="Jep", categoria="master", proves_objectiu=["100m Lliure"],
        mode_ritme="temps",
        ritmes_css=RitmesCSS(recuperacio=110, a1=104, a2=98, a3=94, velocitat=83.3),
    )


def _ex(series=4, dist=100, execucio="Crol", intensitat="A2", descans=None) -> Exercici:
    return Exercici(
        series=series, distancia_m=dist, execucio=execucio, intensitat=intensitat,
        descans=descans,
    )


def _sessio(*exercicis: Exercici, fixa: Exercici | None = None) -> Sessio:
    parts = [
        PartSessio(nom="Aeròbic", percentatge_carrega=100, percentatge_qualitat=100,
                   percentatge_descarrega=100, exercicis=list(exercicis)),
    ]
    if fixa is not None:
        parts.append(PartSessio(nom="Sèrie de control", percentatge_carrega=0,
                                percentatge_qualitat=0, percentatge_descarrega=0,
                                fixa=True, exercicis=[fixa]))
    return Sessio(
        id="s", microcicle_setmana=41, dia="dilluns", tipus_sessio="carrega",
        volum_total=2000, estructura=EstructuraSessio(parts=parts), rol="aerobica",
    )


# --- Notació --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "esperat"),
    [
        ("c/1'45\"", Descans("cicle", 105)),
        ("c/1'45''", Descans("cicle", 105)),
        ("c/1:45", Descans("cicle", 105)),
        ("c/105\"", Descans("cicle", 105)),
        ("c/2'", Descans("cicle", 120)),
        ("C/1’30\"", Descans("cicle", 90)),
        ("d/15\"", Descans("descans", 15)),
        ("d/15s", Descans("descans", 15)),
        ("d/20", Descans("descans", 20)),
        ("d/1'", Descans("descans", 60)),
        (None, None),
        ("", None),
        ("15\"", None),
        ("c/", None),
        ("suau", None),
    ],
)
def test_parsejar_descans(text, esperat):
    assert parsejar_descans(text) == esperat


@pytest.mark.parametrize(
    ("descans", "text"),
    [
        (Descans("cicle", 105), "c/1'45\""),
        (Descans("cicle", 120), "c/2'"),
        (Descans("descans", 15), "d/15\""),
        (Descans("descans", 90), "d/1'30\""),
    ],
)
def test_formatar_descans(descans, text):
    assert formatar_descans(descans) == text
    assert parsejar_descans(text) == descans


# --- Temps ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("execucio", "estil"),
    [
        ("Crol", "crol"),
        ("Esquena, rotació d'espatlles", "esquena"),
        ("Braça llarga", "braca"),
        ("B completa", "braca"),
        ("Pap 1 braç + 2 completes", "papallona"),
        ("IM ordre invers", "estils"),
        ("Ps crol amb taula", "cames"),
        ("Patada de dofí estirat", "cames"),
        ("Braça amb èmfasi en cames, nedar complet", "braca"),
    ],
)
def test_estil_exercici(execucio, estil):
    assert estil_exercici(execucio) == estil


def test_temps_nedat_per_zona_i_estil():
    jep = _jep()
    assert temps_nedat(_ex(dist=100, intensitat="A2"), jep) == pytest.approx(98)
    assert temps_nedat(_ex(dist=50, intensitat="A3"), jep) == pytest.approx(47)
    assert temps_nedat(_ex(dist=100, execucio="Braça", intensitat="A1"), jep) == (
        pytest.approx(104 * 1.17)
    )
    assert temps_nedat(_ex(intensitat=None), jep) == pytest.approx(104)  # sense zona: A1


def test_temps_nedat_sense_zones():
    sense = _jep().model_copy(update={"ritmes_css": None})
    assert temps_nedat(_ex(), sense) is None
    assert temps_exercici(_ex(), sense) is None


def test_temps_exercici_cicle_i_descans():
    jep = _jep()
    # 4x100 A2 c/1'50": 4 x 110 s
    assert temps_exercici(_ex(descans="c/1'50\""), jep) == pytest.approx(440)
    # 8x50 A2 d/15": 8 x 49 + 7 x 15
    assert temps_exercici(_ex(8, 50, descans="d/15\""), jep) == pytest.approx(8 * 49 + 7 * 15)
    # Sense descans: només el temps nedat
    assert temps_exercici(_ex(1, 400, intensitat="A1"), jep) == pytest.approx(416)


def test_temps_sessio():
    jep = _jep()
    sessio = _sessio(_ex(descans="c/1'50\""), _ex(1, 400, intensitat="A1"))
    assert temps_sessio(sessio, jep) == pytest.approx(440 + 416)


def test_descans_minim_per_zona():
    assert descans_minim(_ex(intensitat="A2")) == 10
    assert descans_minim(_ex(intensitat="A3", dist=200)) == 30
    assert descans_minim(_ex(intensitat="A2", dist=50)) == 5
    assert descans_minim(_ex(intensitat="Velocitat", dist=25)) == 45
    assert descans_minim(_ex(intensitat="Velocitat", dist=50)) == 90
    assert descans_minim(_ex(intensitat="MPLA", dist=50), nedat=40) == 120
    assert descans_minim(_ex(intensitat="Recuperació")) == 0


def test_descans_real():
    jep = _jep()
    assert descans_real(_ex(descans="c/1'45\""), jep) == pytest.approx(7)
    assert descans_real(_ex(descans="d/20\""), jep) == 20
    assert descans_real(_ex(descans=None), jep) is None


# --- Correcció de c/ impossibles -----------------------------------------------------


def test_c_curt_fet_servir_com_a_descans_passa_a_d():
    sessio = _sessio(_ex(8, 50, descans="c/15\""))
    correccions = corregir_cicles(sessio, _jep())
    assert sessio.estructura.parts[0].exercicis[0].descans == "d/15\""
    assert len(correccions) == 1 and "c/15\"" in correccions[0]


def test_c_curt_per_sota_del_minim_puja_al_minim():
    sessio = _sessio(_ex(4, 50, intensitat="Velocitat", descans="c/20\""))
    corregir_cicles(sessio, _jep())
    assert sessio.estructura.parts[0].exercicis[0].descans == "d/1'30\""


def test_c_llarg_impossible_passa_a_d_amb_el_minim():
    # 4x200 A2 c/3' amb un temps nedat de 3'16"
    sessio = _sessio(_ex(4, 200, descans="c/3'"))
    corregir_cicles(sessio, _jep())
    assert sessio.estructura.parts[0].exercicis[0].descans == "d/20\""


def test_cicles_possibles_i_parts_fixes_no_es_toquen():
    fixa = _ex(4, 100, descans="c/15\"")
    sessio = _sessio(_ex(descans="c/1'50\""), _ex(descans="d/10\""), fixa=fixa)
    assert corregir_cicles(sessio, _jep()) == []
    assert [e.descans for e in sessio.estructura.parts[0].exercicis] == ["c/1'50\"", "d/10\""]
    assert fixa.descans == "c/15\""


# --- Descansos insuficients ------------------------------------------------------------


def test_a2_amb_cicle_massa_curt_es_problema():
    # W41: 4x100 A2 c/1'45" amb A2 a 1'38" -> 7" de descans
    problemes = problemes_cicles(_sessio(_ex(descans="c/1'45\"")), _jep())
    assert len(problemes) == 1
    assert "~7\"" in problemes[0] and "c/1'50\"" in problemes[0]


def test_cicles_suficients_no_son_problema():
    sessio = _sessio(
        _ex(descans="c/1'50\""),
        _ex(8, 50, intensitat="A3", descans="d/15\""),
        _ex(6, 25, intensitat="Velocitat", descans="d/45\""),
        _ex(4, 100, intensitat="A1", descans="c/1'50\""),
    )
    assert problemes_cicles(sessio, _jep()) == []


def test_velocitat_sense_recuperacio_completa():
    problemes = problemes_cicles(
        _sessio(_ex(8, 25, intensitat="Velocitat", descans="d/20\"")), _jep()
    )
    assert len(problemes) == 1 and "d/45\"" in problemes[0]


def test_falta_descans_nomes_a_partir_d_a2():
    sessio = _sessio(
        _ex(4, 100, intensitat="A3", descans=None),
        _ex(4, 50, intensitat="A1", descans=None),
        _ex(1, 400, intensitat="A2", descans=None),
    )
    problemes = problemes_cicles(sessio, _jep())
    assert len(problemes) == 1 and "falta el descans" in problemes[0]


def test_durada_maxima():
    sessio = _sessio(_ex(30, 200, intensitat="A1", descans="d/20\""))  # ~114 min
    assert problemes_cicles(sessio, _jep(), minuts_max=120) == []
    problemes = problemes_cicles(sessio, _jep(), minuts_max=90)
    assert len(problemes) == 1 and "Durada estimada" in problemes[0]


def test_sense_zones_no_hi_ha_problemes_de_cicle():
    sense = _jep().model_copy(update={"ritmes_css": None})
    sessio = _sessio(_ex(descans="c/15\""))
    assert corregir_cicles(sessio, sense) == []
    assert problemes_cicles(sessio, sense, minuts_max=90) == []


def test_taula_cicles():
    taula = taula_cicles(_jep())
    assert "| A2 | 100 | 1'38\" | d/10\" | c/1'50\" |" in taula
    assert "| Velocitat | 25 | 21\" | d/45\" |" in taula
    assert "sense zones" in taula_cicles(_jep().model_copy(update={"ritmes_css": None}))


# --- Farciment ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "execucio",
    ["placeholder_removed", "Placeholder (eliminat)", "Nota: aquesta part ja està coberta",
     "N/A", "[buit]"],
)
def test_variants_de_farciment(execucio):
    assert _es_farciment({"execucio": execucio})


@pytest.mark.parametrize("execucio", ["Crol nota alta de tècnica", "Esquena suau", "Nadar"])
def test_no_farciment(execucio):
    assert not _es_farciment({"execucio": execucio})

"""Tests de l'organització setmanal (Fase H): rols, esquelet, pressupost i validació."""

from datetime import date

import pytest

from blondswim.agents import pla_setmanal
from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.models.calendari import Competicio
from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import EstructuraSessio, Exercici, PartSessio, Sessio

DILLUNS = date(2026, 10, 5)  # setmana ISO 41


def _comp(data_inici: str, data_fi: str | None = None, classe: str = "B") -> Competicio:
    return Competicio(
        id=f"c_{data_inici}",
        nom="Competició",
        data_inici=data_inici,
        data_fi=data_fi or data_inici,
        classe=classe,
        piscina="25m",
    )


@pytest.fixture
def nedador_plantilla() -> Nedador:
    return Nedador(
        id="jep",
        nom="Jep",
        categoria="master",
        proves_objectiu=["100m lliure", "100m estils"],
        mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dijous", "divendres"],
        ritmes_css=RitmesCSS(font="css_test", a1=87.1, a2=82.09, a3=78.24, velocitat=67.55),
    )


def _microcicle(
    tipus_base: str = "carrega",
    volum: int = 13600,
    dia_competicio: str | None = None,
    post: bool = False,
) -> Microcicle:
    return Microcicle(
        setmana=41,
        dates="05-11/10/2026",
        mesocicle_id="meso_1",
        tipus_base=tipus_base,
        volum_objectiu=volum,
        dies_qualitat=False,
        test_css=False,
        dia_competicio=dia_competicio,
        post_competicio=post,
    )


# --- Classificació de la setmana ---


def test_classificar_setmana_normal():
    assert pla_setmanal.classificar_setmana(DILLUNS, []) == (None, False)


def test_classificar_competicio_dissabte_i_diumenge():
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-10")]) == ("dissabte", False)
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-11")]) == ("diumenge", False)


def test_classificar_a_de_dos_dies_activa_divendres():
    comp = _comp("2026-10-10", "2026-10-11", classe="A")
    assert pla_setmanal.classificar_setmana(DILLUNS, [comp]) == ("dissabte", False)


def test_classificar_post_competicio():
    """Competició que acaba el cap de setmana anterior -> post_competicio."""
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-04")]) == (None, True)


def test_classificar_ignora_competicions_c():
    assert pla_setmanal.classificar_setmana(DILLUNS, [_comp("2026-10-10", classe="C")]) == (
        None,
        False,
    )


# --- Rols ---


def test_rols_setmana_normal_un_sol_dia_de_qualitat():
    rols = pla_setmanal.rols_setmana(None, False)
    assert rols == {
        "dilluns": "aerobica", "dimarts": "qualitat",
        "dijous": "tecnica", "divendres": "llarga",
    }
    assert list(rols.values()).count("qualitat") == 1


def test_rols_competicio_dissabte_activacio_divendres():
    rols = pla_setmanal.rols_setmana("dissabte", False)
    assert rols["divendres"] == "activacio"
    assert rols["dimarts"] == "qualitat"


def test_rols_competicio_diumenge_activacio_dissabte():
    rols = pla_setmanal.rols_setmana("diumenge", False)
    assert rols["dissabte"] == "activacio"
    assert "divendres" not in rols
    assert len(rols) == 4


def test_rols_post_competicio_recuperacio_i_qualitat_dijous():
    rols = pla_setmanal.rols_setmana(None, True)
    assert rols["dilluns"] == "recuperacio"
    assert rols["dijous"] == "qualitat"


def test_rols_post_i_competicio_sense_qualitat():
    rols = pla_setmanal.rols_setmana("dissabte", True)
    assert "qualitat" not in rols.values()
    assert rols["dilluns"] == "recuperacio"
    assert rols["divendres"] == "activacio"


# --- Esquelet amb plantilla ---


def test_esquelet_plantilla_setmana_normal(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())

    assert [s.dia for s in sessions] == ["dilluns", "dimarts", "dijous", "divendres"]
    assert [s.rol for s in sessions] == ["aerobica", "qualitat", "tecnica", "llarga"]
    assert all(s.tipus_sessio == "carrega" for s in sessions)
    assert abs(sum(s.volum_total for s in sessions) - 13600) <= 50
    for s in sessions:
        assert s.volum_min <= s.volum_total <= s.volum_max
        assert s.volum_total % 25 == 0


def test_esquelet_serie_de_control_fixa_dilluns(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle())
    dilluns = sessions[0]

    fixes = [p for p in dilluns.estructura.parts if p.fixa]
    assert len(fixes) == 1
    control = fixes[0]
    assert control.nom == pla_setmanal.NOM_SERIE_CONTROL
    ex = control.exercicis[0]
    assert (ex.series, ex.distancia_m, ex.intensitat) == (4, 100, "A2")
    assert ex.descans == "c/1'40\""  # A2 82" + 15" -> 1'40" (múltiple de 5")
    assert dilluns.estructura.parts[1].fixa  # just després de l'escalfament
    assert all(not p.fixa for s in sessions[1:] for p in s.estructura.parts)


def test_esquelet_competicio_diumenge_activacio_dissabte(nedador_plantilla):
    sessions = generar_esquelet_sessions(nedador_plantilla, _microcicle(dia_competicio="diumenge"))

    assert [s.dia for s in sessions] == ["dilluns", "dimarts", "dijous", "dissabte"]
    activacio = sessions[-1]
    assert activacio.rol == "activacio"
    assert activacio.volum_total < min(s.volum_total for s in sessions[:-1])
    assert "diumenge" in activacio.notes


def test_esquelet_post_competicio_dilluns_de_recuperacio(nedador_plantilla):
    sessions = generar_esquelet_sessions(
        nedador_plantilla, _microcicle(volum=12000, post=True)
    )

    assert sessions[0].rol == "recuperacio"
    assert sessions[0].volum_total < 0.7 * sessions[1].volum_total
    assert abs(sum(s.volum_total for s in sessions) - 12000) <= 50


def test_esquelet_sense_plantilla_manté_la_logica_antiga():
    nedador = Nedador(
        id="x", nom="X", categoria="master", proves_objectiu=[], mode_ritme="temps"
    )  # dies per defecte: dilluns-dijous
    sessions = generar_esquelet_sessions(nedador, _microcicle())
    assert {s.rol for s in sessions} <= {"llarga", "mitjana", "qualitat"}
    assert all(s.notes is None for s in sessions)


def test_cicle_serie_control_sense_ritmes():
    nedador = Nedador(
        id="x", nom="X", categoria="master", proves_objectiu=[], mode_ritme="rpe"
    )
    assert pla_setmanal.cicle_serie_control(nedador) == "d/20\""


# --- Pressupost i validació ---


def _sessio(rol: str, tipus: str, exercicis: list[Exercici], fixes: list[Exercici] | None = None):
    parts = [
        PartSessio(
            nom="Principal", percentatge_carrega=100, percentatge_qualitat=100,
            percentatge_descarrega=100, exercicis=exercicis,
        )
    ]
    if fixes:
        parts.append(
            PartSessio(
                nom="Control", percentatge_carrega=0, percentatge_qualitat=0,
                percentatge_descarrega=0, exercicis=fixes, fixa=True,
            )
        )
    volum = sum(e.volum_m for e in exercicis + (fixes or []))
    return Sessio(
        id="s", microcicle_setmana=41, dia="dimarts", tipus_sessio=tipus,
        volum_total=volum, estructura=EstructuraSessio(parts=parts), rol=rol,
    )


def _ex(series, dist, intensitat, execucio="Crol"):
    return Exercici(series=series, distancia_m=dist, execucio=execucio, intensitat=intensitat)


def test_qualitat_base_no_admet_lactic():
    s = _sessio("qualitat", "carrega", [_ex(30, 100, "A1"), _ex(4, 25, "MPLA")])
    assert any("MPLA/TOLA" in p for p in pla_setmanal.problemes_contingut(s))


def test_qualitat_build_admet_lactic_dins_pressupost():
    s = _sessio("qualitat", "qualitat", [_ex(28, 100, "A1"), _ex(6, 50, "MPLA")])
    assert pla_setmanal.problemes_contingut(s) == []


def test_tecnica_no_admet_a3():
    s = _sessio("tecnica", "carrega", [_ex(28, 100, "A1"), _ex(4, 100, "A3")])
    assert any("A3/AeM" in p for p in pla_setmanal.problemes_contingut(s))


def test_papallona_per_sobre_del_maxim():
    s = _sessio(
        "tecnica", "carrega",
        [_ex(25, 100, "A1"), _ex(8, 50, "A1", "Pap tècnica, un braç")],
    )
    assert any("Papallona" in p for p in pla_setmanal.problemes_contingut(s))


def test_estils_compten_un_quart_de_papallona():
    s = _sessio("aerobica", "carrega", [_ex(2, 100, "A1", "IM per estils")])
    assert pla_setmanal.metres_papallona(s) == 50


def test_estils_125_invalid_i_a3_en_25():
    s = _sessio(
        "qualitat", "carrega",
        [_ex(28, 100, "A1"), _ex(1, 125, "A2", "IM complet"), _ex(4, 25, "A3")],
    )
    problemes = pla_setmanal.problemes_contingut(s)
    assert any("125 m" in p for p in problemes)
    assert any("llindar" in p for p in problemes)


def test_parts_fixes_no_compten_al_pressupost():
    """La sèrie de control (A2) no trenca el pressupost de la recuperació."""
    s = _sessio(
        "recuperacio", "carrega",
        [_ex(16, 100, "A1")],
        fixes=[_ex(4, 100, "A2")],
    )
    assert pla_setmanal.problemes_contingut(s) == []


def test_recuperacio_no_admet_a2_variable():
    s = _sessio("recuperacio", "carrega", [_ex(16, 100, "A1"), _ex(4, 100, "A2")])
    assert any(p.startswith("A2") for p in pla_setmanal.problemes_contingut(s))

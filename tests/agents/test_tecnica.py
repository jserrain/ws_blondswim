"""Tests de la biblioteca de tècnica i el selector."""

import pytest

from blondswim.agents import tecnica
from blondswim.agents.tecnica import (
    FAMILIES_ROL,
    carregar_biblioteca,
    families,
    normalitzar_prova,
    seleccionar_exercicis,
)
from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador


def _nedador(proves, prioritats=None) -> Nedador:
    return Nedador(
        id="jep", nom="Jep", categoria="master", proves_objectiu=proves,
        mode_ritme="temps", prioritats_tecniques=prioritats or [],
    )


def _micro(setmana=41, meso="meso_1", tipus="carrega") -> Microcicle:
    return Microcicle(
        setmana=setmana, dates="05-11/10/2026", mesocicle_id=meso, tipus_base=tipus,
        volum_objectiu=13600, dies_qualitat=False, test_css=False,
    )


JEP = ["100m lliure", "100m estils", "200m lliure", "50m papallona"]


def test_biblioteca_integritat():
    exercicis = carregar_biblioteca()
    ids = [e["id"] for e in exercicis]
    assert len(ids) == len(set(ids))
    assert len(families()) == 18
    for e in exercicis:
        assert e["nivell"] in ("Base", "Intermedi", "Refinament")
        assert set(e["fases"]) <= {"Base", "Build", "Peak"}
        assert e["font"]
    for fams in FAMILIES_ROL.values():
        assert set(fams) <= set(families())


@pytest.mark.parametrize(
    ("text", "esperat"),
    [("100m lliure", "100 crol"), ("100 estils", "100 estils"), ("100 IM", "100 estils"),
     ("50m papallona", "50 papallona"), ("200m braça", "200 braça"), ("xx", None)],
)
def test_normalitzar_prova(text, esperat):
    assert normalitzar_prova(text) == esperat


def test_seleccio_un_exercici_per_familia_i_rellevant():
    sel = seleccionar_exercicis(_nedador(JEP), "tecnica", "carrega", _micro())
    assert len(sel) == 3
    assert len({e["familia"] for e in sel}) == 3
    proves = {"100 crol", "100 estils", "200 crol", "50 papallona"}
    assert all(set(e["proves"]) & proves for e in sel)


def test_seleccio_respecta_la_fase():
    sel = seleccionar_exercicis(_nedador(JEP), "qualitat", "taper", _micro(tipus="taper"))
    assert all("Peak" in e["fases"] for e in sel)


def test_prioritats_tecniques_passen_davant():
    sel = seleccionar_exercicis(
        _nedador(JEP, ["Tècnica d'esquena"]), "tecnica", "carrega", _micro()
    )
    assert sel[0]["familia"] == "Tècnica d'esquena"


def test_familia_estable_al_bloc_i_variant_rota_per_setmana():
    ned = _nedador(JEP)
    s1 = seleccionar_exercicis(ned, "tecnica", "carrega", _micro(setmana=41))
    s2 = seleccionar_exercicis(ned, "tecnica", "carrega", _micro(setmana=42))
    assert [e["familia"] for e in s1] == [e["familia"] for e in s2]
    assert [e["id"] for e in s1] != [e["id"] for e in s2]


def test_nedador_nomes_crol_no_rep_braça_ni_papallona():
    sel = seleccionar_exercicis(_nedador(["100m lliure"]), "tecnica", "carrega", _micro())
    assert all(e["estil"] not in ("Braça", "Papallona", "Esquena") for e in sel)


def test_text_exercicis_inclou_ids():
    sel = seleccionar_exercicis(_nedador(JEP), "aerobica", "carrega", _micro())
    text = tecnica.text_exercicis(sel)
    assert all(f'id_biblioteca: "{e["id"]}"' in text for e in sel)


def test_dosis_de_la_biblioteca_en_multiples_de_25_i_sense_cometes():
    """Les dosis van al prompt: l'LLM les copia (W41: 12 i 24 m de «4x(12,5 + 12,5)»)."""
    import re

    from blondswim.agents.tecnica import carregar_biblioteca

    for e in carregar_biblioteca():
        fmt = e["format"]
        assert "x(" not in fmt, e["id"]
        assert '"' not in fmt and "'" not in fmt, e["id"]
        for distancia in re.findall(r"x(\d+)", fmt):
            assert int(distancia) % 25 == 0, (e["id"], fmt)

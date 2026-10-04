"""Proves objectiu (prioritat, nivell actual, objectius), resultats i utilitats de temps."""

import json

import pytest
from pydantic import ValidationError

from blondswim.models.nedador import Nedador, ProvaObjectiu
from blondswim.models.resultat import ResultatCompeticio
from blondswim.rutes import RutesNedador, carregar_nedador, carregar_resultats, desar_json
from blondswim.utils.proves import clau_prova, mateixa_prova
from blondswim.utils.temps import format_temps, parsejar_temps

# --- Temps -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "esperat"),
    [
        ("1:17.08", 77.08),
        ("1'17.08", 77.08),
        ("1'17\"08", 77.08),
        ("1'17\"08\"", 77.08),
        ("77.08", 77.08),
        ("77,08", 77.08),
        ("38\"86", 38.86),
        ("0:38.86", 38.86),
        ("3:03", 183.0),
        (" 1:20.00 ", 80.0),
        (98, 98.0),
        (98.5, 98.5),
    ],
)
def test_parsejar_temps(text, esperat):
    assert parsejar_temps(text) == pytest.approx(esperat)


@pytest.mark.parametrize("dolent", ["", "abc", "1:75.0", "1:2:3", 0, -3, True])
def test_parsejar_temps_invalid(dolent):
    with pytest.raises(ValueError):
        parsejar_temps(dolent)


@pytest.mark.parametrize(
    ("segons", "esperat"),
    [(77.08, "1'17\"1"), (38.86, '38"9'), (183.0, "3'03\"0"), (59.96, "1'00\"0"), (75.0, "1'15\"0")],
)
def test_format_temps(segons, esperat):
    assert format_temps(segons) == esperat


def test_format_temps_decimals():
    assert format_temps(77.08, 2) == "1'17\"08"
    assert format_temps(77.4, 0) == "1'17\""


# --- Noms de proves ---------------------------------------------------------


def test_clau_prova():
    assert clau_prova("100m Lliure") == clau_prova("100 lliures") == "100 crol"
    assert clau_prova("100m IM") == clau_prova("100 estils") == "100 estils"
    assert clau_prova("200m Lliure") == "200 crol"
    assert clau_prova("relleus") is None


def test_mateixa_prova():
    assert mateixa_prova("100m Lliure", "100 crol")
    assert not mateixa_prova("100m Lliure", "200m Lliure")
    assert mateixa_prova("Prova rara", "prova rara")


# --- Prova objectiu ---------------------------------------------------------

PROVA_100 = {
    "prova": "100m Lliure",
    "prioritat": "P",
    "piscina": "25m",
    "nivell_actual": {"millor_marca": "1:17.08", "estimacio_pessimista": "1:20.00"},
    "objectius": [
        {"competicio_id": "cat-hivern", "realista": "1:15.00", "ambicios": "1:12.00"}
    ],
}


def test_prova_objectiu_completa():
    p = ProvaObjectiu(**PROVA_100)
    assert p.nivell_actual.millor_marca == pytest.approx(77.08)
    assert p.nivell_actual.estimacio_pessimista == 80.0
    assert p.objectius[0].realista == 75.0
    assert p.objectius[0].ambicios == 72.0
    assert p.objectiu_per(["espanya", "cat-hivern"]).competicio_id == "cat-hivern"
    assert p.objectiu_per(["altra"]) is None


def test_nivell_actual_ordre():
    with pytest.raises(ValidationError, match="millor marca"):
        ProvaObjectiu(
            prova="100m Lliure",
            nivell_actual={"millor_marca": "1:21.00", "estimacio_pessimista": "1:20.00"},
        )


def test_objectiu_ordre():
    with pytest.raises(ValidationError, match="ambiciós"):
        ProvaObjectiu(
            prova="100m Lliure",
            objectius=[{"competicio_id": "x", "realista": "1:12.00", "ambicios": "1:15.00"}],
        )


def test_prioritat_invalida():
    with pytest.raises(ValidationError):
        ProvaObjectiu(prova="100m Lliure", prioritat="A")


# --- Nedador ----------------------------------------------------------------


def _nedador(proves) -> Nedador:
    return Nedador(
        id="jep", nom="Jep", categoria="master", proves_objectiu=proves, mode_ritme="temps"
    )


def test_llista_antiga_de_textos_es_compatible():
    n = _nedador(["50 papallona", "100 lliure"])
    assert n.noms_proves == ["50 papallona", "100 lliure"]
    assert all(p.prioritat == "P" and p.objectius == [] for p in n.proves_objectiu)


def test_nedador_amb_proves_completes_i_barrejades():
    n = _nedador([PROVA_100, {"prova": "200m Lliure", "prioritat": "S"}, "100m IM"])
    assert n.noms_proves == ["100m Lliure", "200m Lliure", "100m IM"]
    assert n.prova_objectiu("100 lliures").prioritat == "P"
    assert n.prova_objectiu("200 crol").prioritat == "S"
    assert n.prova_objectiu("100 estils").prova == "100m IM"
    assert n.prova_objectiu("50 papallona") is None


def test_parametres_progressio_per_defecte():
    n = _nedador([])
    assert n.parametres_progressio.guany_taper == 0.02
    assert n.parametres_progressio.marge == 0.01


def test_fitxa_amb_objectius_es_llegeix_de_disc(tmp_path):
    rutes = RutesNedador("jep", tmp_path)
    desar_json(
        rutes.nedador,
        {"id": "jep", "nom": "Jep", "categoria": "master", "mode_ritme": "temps",
         "proves_objectiu": [PROVA_100]},
    )
    n = carregar_nedador(rutes)
    assert n.prova_objectiu("100m Lliure").objectius[0].ambicios == 72.0


# --- Resultats --------------------------------------------------------------


def test_resultat_amb_parcials():
    r = ResultatCompeticio(
        competicio_id="barceloneta", prova="100m Lliure", temps="1:18.40",
        parcials_25=["18.3", "19.9", "20.1", "20.1"], bracades_llargada=[15, 16, 17, 18],
        font="video",
    )
    assert r.temps == pytest.approx(78.4)
    assert r.parcials_25[0] == pytest.approx(18.3)


def test_resultat_parcials_no_quadren():
    with pytest.raises(ValidationError, match="parcials"):
        ResultatCompeticio(
            competicio_id="b", prova="100m Lliure", temps="1:18.40",
            parcials_25=[18.0, 19.0, 19.0, 19.0],
        )


def test_carregar_resultats(tmp_path):
    rutes = RutesNedador("jep", tmp_path)
    assert carregar_resultats(rutes) == []
    rutes.resultats.parent.mkdir(parents=True)
    rutes.resultats.write_text(
        json.dumps([{"competicio_id": "b", "prova": "100m Lliure", "temps": "1:18.4"}]),
        encoding="utf-8",
    )
    assert carregar_resultats(rutes)[0].temps == pytest.approx(78.4)
    assert rutes.resultats == tmp_path / "nedadors" / "jep" / "resultats.json"

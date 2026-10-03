"""Tests de les rutes i la càrrega de dades per nedador."""

import json
from datetime import date

import pytest

from blondswim.rutes import (
    RutesNedador,
    carregar_competicions,
    carregar_historial,
    carregar_nedador,
    desar_json,
    llistar_nedadors,
    ruta_competicions,
    validar_id_nedador,
)

NEDADOR_MINIM = {
    "id": "lou",
    "nom": "Lou",
    "categoria": "master",
    "proves_objectiu": ["100 lliures"],
    "mode_ritme": "rpe",
}


def test_rutes_derivades_de_l_id(tmp_path):
    r = RutesNedador("lou", tmp_path)
    assert r.carpeta == tmp_path / "nedadors" / "lou"
    assert r.nedador == r.carpeta / "nedador.json"
    assert r.calendari == r.carpeta / "calendari.json"
    assert r.historial == r.carpeta / "historial.json"
    assert r.registres_dir == r.carpeta / "registres"
    assert r.log_dir == r.carpeta / "log_decisions"
    dilluns = date(2026, 10, 5)
    assert r.setmana_xlsx(dilluns) == r.carpeta / "setmanes" / "setmana_lou_2026-W41.xlsx"
    assert r.registre_xlsx(dilluns) == r.carpeta / "registres" / "registre_lou_2026-W41.xlsx"
    assert r.mesocicle_xlsx("M1").name == "mesocicle_lou_M1.xlsx"
    assert ruta_competicions(tmp_path) == tmp_path / "competicions.json"


def test_setmana_que_creua_d_any_usa_any_iso(tmp_path):
    r = RutesNedador("jep", tmp_path)
    assert r.setmana_xlsx(date(2026, 12, 28)).name == "setmana_jep_2026-W53.xlsx"
    assert r.setmana_xlsx(date(2027, 1, 4)).name == "setmana_jep_2027-W01.xlsx"


@pytest.mark.parametrize("dolent", ["Lou", "lou garcia", "pèrez", "../jep", "", "-x"])
def test_id_no_valid(dolent):
    with pytest.raises(ValueError, match="no vàlid"):
        validar_id_nedador(dolent)


def test_llistar_nedadors_nomes_carpetes_amb_fitxa(tmp_path):
    assert llistar_nedadors(tmp_path) == []
    desar_json(RutesNedador("pere", tmp_path).nedador, {**NEDADOR_MINIM, "id": "pere"})
    desar_json(RutesNedador("jep", tmp_path).nedador, {**NEDADOR_MINIM, "id": "jep"})
    (tmp_path / "nedadors" / "buida").mkdir()
    assert llistar_nedadors(tmp_path) == ["jep", "pere"]


def test_carregar_nedador(tmp_path):
    r = RutesNedador("lou", tmp_path)
    desar_json(r.nedador, NEDADOR_MINIM)
    assert carregar_nedador(r).nom == "Lou"


def test_carregar_nedador_inexistent_llista_disponibles(tmp_path):
    desar_json(RutesNedador("jep", tmp_path).nedador, {**NEDADOR_MINIM, "id": "jep"})
    with pytest.raises(FileNotFoundError, match="disponibles: jep"):
        carregar_nedador(RutesNedador("cris", tmp_path))


def test_carregar_nedador_id_no_coincideix(tmp_path):
    r = RutesNedador("cris", tmp_path)
    desar_json(r.nedador, NEDADOR_MINIM)  # id "lou" a la carpeta "cris"
    with pytest.raises(ValueError, match="no coincideix"):
        carregar_nedador(r)


def test_carregar_competicions_resol_cataleg(tmp_path):
    desar_json(
        ruta_competicions(tmp_path),
        [
            {"id": "girona", "nom": "Girona", "data_inici": "2026-10-24",
             "data_fi": "2026-10-24", "piscina": "50m"},
            {"id": "horta", "nom": "Horta", "data_inici": "2026-11-07",
             "data_fi": "2026-11-07", "piscina": "25m"},
        ],
    )
    jep = RutesNedador("jep", tmp_path)
    lou = RutesNedador("lou", tmp_path)
    desar_json(jep.calendari, [{"competicio_id": "girona", "classe": "C"}])
    desar_json(
        lou.calendari,
        [{"competicio_id": "girona", "classe": "A"}, {"competicio_id": "horta", "classe": "B"}],
    )
    assert [(c.id, c.classe) for c in carregar_competicions(jep)] == [("girona", "C")]
    assert [(c.id, c.classe) for c in carregar_competicions(lou)] == [
        ("girona", "A"),
        ("horta", "B"),
    ]


def test_sense_calendari_ni_historial_retorna_llistes_buides(tmp_path):
    r = RutesNedador("pere", tmp_path)
    assert carregar_competicions(r) == []
    assert carregar_historial(r) == []


def test_desar_json_utf8(tmp_path):
    path = tmp_path / "a" / "b.json"
    desar_json(path, {"nom": "Natació"})
    assert "Natació" in path.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == {"nom": "Natació"}

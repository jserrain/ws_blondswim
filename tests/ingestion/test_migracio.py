"""Tests de la migració data/processed/ → data/nedadors/<id>/."""

import json

from blondswim.ingestion.migracio import migrar
from blondswim.rutes import (
    RutesNedador,
    carregar_competicions,
    carregar_nedador,
    llistar_nedadors,
    ruta_competicions,
)

JEP = {
    "id": "jep",
    "nom": "Jep",
    "categoria": "master",
    "proves_objectiu": ["50 papallona", "100 lliures"],
    "mode_ritme": "temps",
    "rutina_espatlla_dia": "dissabte",
}
CALENDARI = [
    {"id": "barceloneta", "nom": "Master Barceloneta", "data_inici": "2026-10-17",
     "data_fi": "2026-10-17", "classe": "B", "piscina": "25m"},
    {"id": "cat-hivern", "nom": "Campionat Catalunya hivern", "data_inici": "2027-01-16",
     "data_fi": "2027-01-17", "classe": "A", "piscina": "25m"},
]


def _escriure(path, dades):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dades, ensure_ascii=False), encoding="utf-8")


def _processed_antic(tmp_path):
    processed = tmp_path / "data" / "processed"
    _escriure(processed / "nedador_jep.json", JEP)
    _escriure(processed / "calendari.json", CALENDARI)
    _escriure(processed / "historial_jep.json", [])
    _escriure(processed / "macrocicle_temporada_26_27.json", {"x": 1})
    _escriure(processed / "macrocicle_jep.json", {"y": 2})
    _escriure(processed / "log_decisions" / "jep_1.json", {"z": 3})
    (processed / "registres").mkdir()
    (processed / "registres" / "registre_jep_2026-W40.xlsx").write_bytes(b"reg")
    (processed / "setmana_jep_2026-W41.xlsx").write_bytes(b"set")
    return processed


def test_migracio_completa(tmp_path):
    processed = _processed_antic(tmp_path)
    arrel = tmp_path / "data"
    res = migrar(processed, arrel)

    assert res.nedadors == ["jep"]
    assert res.avisos == []
    assert llistar_nedadors(arrel) == ["jep"]
    rutes = RutesNedador("jep", arrel)
    assert carregar_nedador(rutes).rutina_espatlla_dia == "dissabte"
    assert rutes.historial.is_file()
    assert (rutes.registres_dir / "registre_jep_2026-W40.xlsx").read_bytes() == b"reg"
    assert (rutes.setmanes_dir / "setmana_jep_2026-W41.xlsx").read_bytes() == b"set"
    assert json.loads(rutes.macrocicle.read_text()) == {"x": 1}
    assert (rutes.carpeta / "macrocicle_referencia.json").is_file()
    assert (rutes.log_dir / "jep_1.json").is_file()

    # Catàleg sense classe; calendari del Jep amb les classes originals
    cataleg = json.loads(ruta_competicions(arrel).read_text(encoding="utf-8"))
    assert all("classe" not in c for c in cataleg)
    comps = carregar_competicions(rutes)
    assert [(c.id, c.classe) for c in comps] == [("barceloneta", "B"), ("cat-hivern", "A")]

    # No esborra res de l'origen
    assert (processed / "nedador_jep.json").is_file()
    assert (processed / "calendari.json").is_file()


def test_simular_no_escriu_res(tmp_path):
    processed = _processed_antic(tmp_path)
    arrel = tmp_path / "data"
    res = migrar(processed, arrel, simular=True)
    assert res.copiats
    assert not (arrel / "nedadors").exists()
    assert not ruta_competicions(arrel).exists()


def test_es_idempotent_i_no_sobreescriu(tmp_path):
    processed = _processed_antic(tmp_path)
    arrel = tmp_path / "data"
    migrar(processed, arrel)
    rutes = RutesNedador("jep", arrel)
    # El coach edita la fitxa nova; una segona migració no la trepitja
    editat = {**JEP, "volum_setmanal_min": 9000}
    _escriure(rutes.nedador, editat)
    res = migrar(processed, arrel)
    assert rutes.nedador in res.ja_existents
    assert carregar_nedador(rutes).volum_setmanal_min == 9000


def test_cataleg_es_fusiona_amb_l_existent(tmp_path):
    processed = _processed_antic(tmp_path)
    arrel = tmp_path / "data"
    _escriure(
        ruta_competicions(arrel),
        [{"id": "sabadell", "nom": "Sabadell", "data_inici": "2026-11-21",
          "data_fi": "2026-11-21", "piscina": "25m"}],
    )
    migrar(processed, arrel)
    ids = [c["id"] for c in json.loads(ruta_competicions(arrel).read_text(encoding="utf-8"))]
    assert ids == ["barceloneta", "sabadell", "cat-hivern"]


def test_diversos_nedadors(tmp_path):
    processed = _processed_antic(tmp_path)
    _escriure(processed / "nedador_lou.json", {**JEP, "id": "lou", "nom": "Lou"})
    (processed / "setmana_lou_2026-W41.xlsx").write_bytes(b"lou")
    arrel = tmp_path / "data"
    res = migrar(processed, arrel)
    assert res.nedadors == ["jep", "lou"]
    lou = RutesNedador("lou", arrel)
    assert (lou.setmanes_dir / "setmana_lou_2026-W41.xlsx").read_bytes() == b"lou"
    assert not lou.calendari.exists()  # el calendari antic és del Jep


def test_id_no_valid_es_avisa(tmp_path):
    processed = tmp_path / "data" / "processed"
    _escriure(processed / "nedador_x.json", {**JEP, "id": "Nom Amb Espais"})
    res = migrar(processed, tmp_path / "data")
    assert res.nedadors == []
    assert any("no es pot migrar" in a for a in res.avisos)


def test_sense_processed(tmp_path):
    res = migrar(tmp_path / "no-hi-es", tmp_path)
    assert res.avisos and not res.copiats

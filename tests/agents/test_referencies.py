"""Referències del jutge: corpus (biblioteca, historial, extra) i cerca BM25."""

import json
from pathlib import Path

import pytest

from blondswim.agents import jutge
from blondswim.agents import referencies as R
from blondswim.models.historial import SerieRealitzada, SessioRealitzada
from blondswim.models.sessio import Exercici

CASOS = Path(__file__).parents[2] / "data/raw/jutge/casos.jsonl"


def _serie(ordre: int, treball, execucio: str, intensitat: str | None = "A1",
           objectiu: str | None = None, material: str | None = "-",
           volum: int | None = None) -> SerieRealitzada:
    return SerieRealitzada(ordre=ordre, treball=treball, execucio=execucio,
                           intensitat=intensitat, objectiu=objectiu, material=material,
                           volum_m=volum)


def _sessio(data: str, *series: SerieRealitzada, modalitat: str = "natacio"):
    return SessioRealitzada(data=data, series=list(series), temps_total_min=60,
                            modalitat=modalitat)


@pytest.mark.parametrize(("entrada", "sortida"), [
    ("Ps Crol r/4", "Cames Crol respiració cada 4"),
    ("100C + 100B", "100 Crol + 100 Braça"),
    ("Ei ordre invers", "Estils ordre invers"),
    ("Ps C/E", "Cames Crol i Esquena"),
    ("Papallona subaq 3 bats", "Papallona subaquàtic 3 batudes"),
    ("4N + 4Ps", "4 nedar + 4 Cames"),
    ("Crol + 6) EP", "Crol + EP"),
    ("Crol (75 r/3 + 125 r/4)", "Crol (75 respiració cada 3 + 125 respiració cada 4)"),
    ("Cames de crol amb taula", "Cames de crol amb taula"),
])
def test_desplegar_abreviatures(entrada, sortida):
    assert R.desplegar_abreviatures(entrada) == sortida


@pytest.mark.parametrize(("part", "tipus"), [
    ("Escalfament", "escalfament"), ("Tècnica", "tecnica"), ("Cames", "cames"),
    ("Tornada a la calma", "calma"), ("Bloc principal — Qualitat", "principal"),
    ("Bloc principal — Aeròbic suau", "principal"),
])
def test_tipus_part(part, tipus):
    assert R.tipus_part(part) == tipus


def test_sense_descansos():
    assert R.sense_descansos("FRIM prog c/50") == "FRIM prog"
    assert R.sense_descansos("100 fraccionat: 2x50 d/10\" a ritme") == "100 fraccionat: 2x50 a ritme"
    assert R.sense_descansos("Crol c/1'45\" suau") == "Crol suau"


def test_tokens_sense_numeros_ni_paraules_buides():
    assert R.tokens("8x100 m | Braça amb Pull | intensitat: A2") == ["braca", "pull", "a2"]


def test_referencies_biblioteca():
    refs = R.referencies_biblioteca()
    assert len(refs) == 64
    assert all(r.veredicte == "correcte" and r.font.startswith("biblioteca:") for r in refs)
    taula = next(r for r in refs if r.font == "biblioteca:cam_crol_taula")
    assert taula.text == "4-8x50 m | Cames de crol amb taula | intensitat: A1/A2 | material: Taula"
    assert "cames" in taula.parts
    assert not [r.text for r in refs if "d/" in r.text.split("|")[0]]


def test_referencies_historial_formats_parts_i_duplicats():
    sessions = [
        _sessio(
            "2026-09-28",
            _serie(1, "3x200", "1) 100C + 100B", objectiu="Escalfament", volum=200),
            _serie(2, None, "3) Ps Crol tabla", objectiu="Cames", volum=200),
            _serie(3, "4x100", "Crol", intensitat="A3", objectiu="VO2 Màx", material="AL"),
            _serie(4, "2x", "200 Crol r/3", objectiu="Aeròbic"),
            _serie(5, "4x25", "Crol arrossegant el polze", objectiu="Tècnica"),
            _serie(6, "100.0", "Recuperació", intensitat="A0", objectiu="Recuperació"),
        ),
        _sessio("2026-09-29", _serie(1, "4x100", "Crol", intensitat="A3",
                                     material="Aletes")),
        _sessio("2026-09-30", _serie(1, "4x100", "Sentadilles"), modalitat="gimnas"),
    ]
    refs = {r.text: r for r in R.referencies_historial(sessions)}
    assert set(refs) == {
        "200 m | 100 Crol + 100 Braça | intensitat: A1",
        "200 m | Cames Crol taula | intensitat: A1",
        "4x100 m | Crol | intensitat: A3 | material: Aletes",
        "2x200 m | Crol respiració cada 3 | intensitat: A1",
        "100 m | Recuperació | intensitat: Recuperació",
    }  # el polze arrossegant (norma de l'entrenador) i el gimnàs, fora
    assert refs["200 m | 100 Crol + 100 Braça | intensitat: A1"].parts == {"escalfament"}
    assert refs["200 m | Cames Crol taula | intensitat: A1"].parts == {"cames"}
    assert refs["100 m | Recuperació | intensitat: Recuperació"].parts == {"calma"}
    a3 = refs["4x100 m | Crol | intensitat: A3 | material: Aletes"]
    assert a3.vegades == 2 and a3.font == "historial:2026-09-28"
    assert all(r.veredicte == "correcte" for r in refs.values())


def test_referencies_jsonl(tmp_path):
    fitxer = tmp_path / "refs.jsonl"
    fitxer.write_text(json.dumps({
        "text": "4x50 m | Crol amb llast als canells | intensitat: A1", "part": "Tècnica",
        "veredicte": "insegur", "motiu": "carrega l'espatlla", "font": "ombra:W41",
    }) + "\n\n")
    [ref] = R.referencies_jsonl(fitxer)
    assert ref.parts == {"tecnica"} and ref.veredicte == "insegur"


def _corpus() -> R.Corpus:
    return R.Corpus([
        R.Referencia("4x50 m | Cames de crol amb taula | intensitat: A1", frozenset({"cames"}),
                     "correcte", "biblioteca:a"),
        R.Referencia("4x100 m | Crol | intensitat: A3", frozenset({"principal"}),
                     "correcte", "historial:b"),
        R.Referencia("4x100 m | Crol | intensitat: A1", frozenset({"escalfament"}),
                     "correcte", "historial:c"),
        R.Referencia("4x50 m | Crol | intensitat: A1", frozenset({"principal"}),
                     "correcte", "historial:d"),
        R.Referencia("4x50 m | Crol amb llast | intensitat: A1", frozenset({"principal"}),
                     "insegur", "extra"),
    ], vocabulari_extra="Taula Paracaigudes")


def test_cercar_filtra_per_part():
    r = _corpus().cercar("8x50 m | Cames de crol amb taula | intensitat: A2", "Cames")
    assert [x.font for x in r.referencies] == ["biblioteca:a"]
    assert not R.ResultatCerca(referencies=r.referencies).sense_referencia


def test_cercar_exigeix_una_paraula_especifica():
    """«Surar» no s'assembla a «Crol A1» encara que comparteixin la intensitat."""
    r = _corpus().cercar("4x50 m | Surar fins a la bandera | intensitat: A1",
                         "Bloc principal — Aeròbic")
    assert r.sense_referencia
    assert r.termes_desconeguts == ["bandera", "fins", "surar"]
    llast = _corpus().cercar("4x50 m | Crol amb llast | intensitat: A1", "Bloc principal")
    assert [x.veredicte for x in llast.referencies] == ["insegur"]


def test_cercar_generic_exigeix_mateix_estil_i_intensitat():
    """«8x100 Crol A3» a l'escalfament no s'assembla a «Crol A1» de l'escalfament."""
    assert _corpus().cercar("8x100 m | Crol | intensitat: A3", "Escalfament").sense_referencia
    r = _corpus().cercar("6x100 m | Crol | intensitat: A3", "Bloc principal — Qualitat")
    assert [x.font for x in r.referencies] == ["historial:b"]


def test_construir_corpus_exclou_el_joc_de_prova():
    casos = [json.loads(linia) for linia in CASOS.read_text().splitlines() if linia]
    camps = ("series", "distancia_m", "execucio", "intensitat", "descans", "material")
    textos = [jutge.text_exercici(Exercici(**{k: e[k] for k in camps if k in e}))
              for c in casos for e in c["exercicis"]]
    historial = [_sessio("2026-10-01", _serie(1, "200", "Cames de crol amb taula",
                                              material="Taula"))]
    corpus, resum = R.construir_corpus(historial=historial, excloure_textos=textos)
    assert resum["biblioteca"] == 64 and resum["historial"] == 1
    assert resum["exclosos"] == 1  # és exactament un cas del joc de prova
    claus = {R._clau(t) for t in textos}
    assert not [r.text for r in corpus.refs if R._clau(r.text) in claus]

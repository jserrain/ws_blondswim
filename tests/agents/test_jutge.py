"""Jutge LLM: text dels exercicis amb fets calculats, prompt, esquema i resposta."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from blondswim.agents import jutge
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import Exercici

CASOS = Path(__file__).parents[2] / "data/raw/jutge/casos.jsonl"


def _nedador() -> Nedador:
    return Nedador(
        id="x", nom="X", categoria="master", proves_objectiu=["100m Lliure"],
        mode_ritme="temps",
        ritmes_css=RitmesCSS(recuperacio=110, a1=104, a2=98, a3=94, velocitat=83.3),
    )


def _context() -> jutge.ContextJutge:
    return jutge.ContextJutge(
        rol="aerobica", fase="Base", part="Bloc principal — Aeròbic",
        objectiu_part="treball aeròbic.", zones={"A1": 104, "A2": 98, "A3": 94},
    )


@pytest.mark.parametrize(("segons", "text"), [(98, "1:38"), (45, "45 s"), (120, "2:00")])
def test_format_mmss(segons, text):
    assert jutge.format_mmss(segons) == text


def test_text_exercici_amb_descans_real_i_sense_cometes():
    ex = Exercici(series=4, distancia_m=100, execucio="Crol", intensitat="A2",
                  descans="c/1'45\"", material="Pull")
    text = jutge.text_exercici(ex, _nedador())
    assert text == "4x100 Crol A2 c/1:45 amb Pull (descans real 7 s)"
    assert '"' not in text


def test_text_exercici_sense_series_ni_nedador():
    ex = Exercici(series=1, distancia_m=400, execucio="Crol suau", intensitat="A1")
    assert jutge.text_exercici(ex, _nedador()) == "400 Crol suau A1"
    ex2 = Exercici(series=8, distancia_m=50, execucio="Crol", descans="d/15\"")
    assert jutge.text_exercici(ex2) == "8x50 Crol d/15 s"


def test_construir_missatges():
    sistema, usuari = jutge.construir_missatges(_context(), ["8x100 Crol A2", "4x50 Surar"])
    assert "part «Bloc principal — Aeròbic»" in sistema["content"]
    assert "A2 1:38" in sistema["content"]
    assert "c/X és el cicle" in sistema["content"]
    assert "Estils A1" in sistema["content"]  # few-shot per defecte
    assert usuari["content"] == "Exercicis:\n1) 8x100 Crol A2\n2) 4x50 Surar"
    sense = jutge.construir_missatges(_context(), ["x"], exemples=[])[0]["content"]
    assert "Estils A1" not in sense


def test_esquema_exigeix_un_veredicte_per_exercici_i_motiu_abans():
    e = jutge.esquema(3)["properties"]["veredictes"]
    assert e["minItems"] == e["maxItems"] == 3
    assert list(e["items"]["properties"]) == ["exercici", "motiu", "categoria", "valid"]
    assert e["items"]["properties"]["categoria"]["enum"] == jutge.CATEGORIES


def _contingut(*valids: bool) -> str:
    return json.dumps({"veredictes": [
        {"exercici": i, "motiu": "m", "categoria": "correcte" if v else "no_natacio", "valid": v}
        for i, v in enumerate(valids, 1)
    ]})


def test_parsejar_veredictes_ordena_i_valida():
    contingut = json.dumps({"veredictes": [
        {"exercici": 2, "motiu": "b", "categoria": "farciment", "valid": False},
        {"exercici": 1, "motiu": "a", "categoria": "correcte", "valid": True},
    ]})
    v = jutge.parsejar_veredictes(contingut, 2)
    assert [(x.exercici, x.valid, x.categoria) for x in v] == [
        (1, True, "correcte"), (2, False, "farciment")
    ]
    with pytest.raises(ValueError, match="1..3"):
        jutge.parsejar_veredictes(_contingut(True, False), 3)
    with pytest.raises(ValueError):
        jutge.parsejar_veredictes("no és json", 1)


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_jutjar_envia_la_peticio_i_llegeix_la_resposta():
    cos = {"choices": [{"message": {"content": _contingut(True, False),
                                    "reasoning_content": "pensant"}}]}
    with patch("urllib.request.urlopen",
               return_value=_Resposta(json.dumps(cos).encode())) as urlopen:
        r = jutge.jutjar("http://localhost:8080/", _context(), ["a", "b"], raonar=True)
    peticio = urlopen.call_args.args[0]
    enviat = json.loads(peticio.data)
    assert peticio.full_url == "http://localhost:8080/v1/chat/completions"
    assert enviat["temperature"] == 0
    assert enviat["chat_template_kwargs"] == {"enable_thinking": True}
    assert enviat["response_format"]["json_schema"]["schema"] == jutge.esquema(2)
    assert [v.valid for v in r.veredictes] == [True, False]
    assert r.raonament == "pensant"


def test_jutjar_sense_mode_de_raonament():
    cos = {"choices": [{"message": {"content": _contingut(True)}}]}
    with patch("urllib.request.urlopen",
               return_value=_Resposta(json.dumps(cos).encode())) as urlopen:
        jutge.jutjar("http://x", _context(), ["a"], raonar=None, model="gemma")
    enviat = json.loads(urlopen.call_args.args[0].data)
    assert "chat_template_kwargs" not in enviat
    assert enviat["model"] == "gemma"


def test_joc_de_casos_ben_format():
    casos = [json.loads(linia) for linia in CASOS.read_text().splitlines() if linia]
    exercicis = [e for c in casos for e in c["exercicis"]]
    assert len(exercicis) >= 30
    assert {e["esperat"] for e in exercicis} <= set(jutge.CATEGORIES)
    for cas in casos:
        assert {"id", "rol", "fase", "part", "objectiu_part"} <= set(cas)
        for e in cas["exercicis"]:
            Exercici(**{k: e[k] for k in ("series", "distancia_m", "execucio",
                                          "intensitat", "descans", "material") if k in e})
    # Els exemples del prompt no poden ser al joc de prova.
    exemples = " ".join(ex["exercici"] for ex in jutge.EXEMPLES_DEFECTE)
    assert not [e["execucio"] for e in exercicis if len(e["execucio"]) > 12
                and e["execucio"] in exemples]

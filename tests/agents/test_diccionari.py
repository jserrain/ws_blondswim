"""Diccionari de l'entrenador: glossari, abreviatures, normes i vocabulari."""

import json

import pytest

from blondswim.agents import diccionari as D


def test_diccionari_ben_format():
    termes = D.termes()
    assert len(termes) > 50
    noms = [t.terme for t in termes]
    assert len(noms) == len(set(noms))
    abreviatures = [(a, t.majuscules) for t in termes if t.estat != "prohibit"
                    for a in t.abreviatures]
    assert len(abreviatures) == len(set(abreviatures)), "abreviatura repetida"


def test_glossari_nomes_valids():
    g = D.glossari()
    assert "Paracaigudes (resistència per a força i velocitat)" in g
    assert "FRIM (estils substituint la papallona per crol" in g
    assert "- Intensitats: Recuperació (molt suau), A1" in g
    assert "descoord" not in g  # pendent
    assert "arrossegar el polze" not in g  # prohibit
    assert set(D.pendents()) == {"descoord", "variant posicions"}


@pytest.mark.parametrize(("text", "esperat"), [
    ("Ps Crol", "Cames Crol"),
    ("al davant", "al davant"),  # «AL» només en majúscules
    ("Crol AL", "Crol Aletes"),
    ("Fartlek", "Fartlek"),  # «F» no toca lletres
    ("PE + PB + EB", "Papallona i Esquena + Papallona i Braça + Esquena i Braça"),
    ("Màx", "màxim"),
])
def test_desplegar(text, esperat):
    assert D.desplegar(text) == esperat


def test_terme_de():
    assert D.terme_de("A0", "intensitat") == "Recuperació"
    assert D.terme_de("vel", "intensitat") == "Velocitat"
    assert D.terme_de("Mpla", "intensitat") == "MPLA"
    assert D.terme_de("AL", "material") == "Aletes"
    assert D.terme_de("al", "material") is None
    assert D.terme_de("Pull", "intensitat") is None


def test_normes():
    motius = [m for p, m in D.normes() if p.search("Crol arrossegant el polze")]
    assert motius and "espatlla" in motius[0]
    assert [m for p, m in D.normes() if p.search("Crol amb Ei")]
    assert not [m for p, m in D.normes() if p.search("Eix del cos estable")]


def test_vocabulari_inclou_pendents_i_no_prohibits():
    v = D.vocabulari()
    assert "descoord" in v and "Biondi" in v and "polze" not in v


def test_diccionari_invalid(tmp_path):
    fitxer = tmp_path / "d.json"
    fitxer.write_text(json.dumps({"termes": [
        {"terme": "x", "tipus": "estil", "estat": "prohibit"}]}))
    with pytest.raises(ValueError, match="sense patró"):
        D.termes(fitxer)
    fitxer.write_text(json.dumps({"termes": [{"terme": "x", "tipus": "nou"}]}))
    with pytest.raises(ValueError, match="desconegut"):
        D.termes(fitxer)

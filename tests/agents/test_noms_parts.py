"""Noms de part que retorna l'LLM, exercicis de farciment i schema per sessió.

Regressió de la W41 real (2026-10-05): l'LLM retornava les parts amb l'etiqueta
del bloc («Bloc principal 1 — Aeròbic»), el codi no les trobava i la sessió
quedava sense bloc principal (1.450 m en lloc de 2.775-3.075 m).
"""

import pytest

from blondswim.agents.generar_microcicle import (
    _aplicar_contingut_sessio,
    _construir_tools_sessio,
    _es_farciment,
    _trobar_part,
)
from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio


def _sessio() -> Sessio:
    parts = [
        PartSessio(nom=nom, percentatge_carrega=20.0, percentatge_qualitat=20.0,
                   percentatge_descarrega=20.0, bloc=bloc)
        for nom, bloc in [
            ("Escalfament", "Escalfament"),
            ("Tècnica", "Tècnica"),
            ("Aeròbic", "Bloc principal"),
            ("Cames", "Bloc principal"),
            ("Tornada a la calma", "Tornada a la calma"),
        ]
    ]
    return Sessio(
        id="meso_1_s41_dilluns", microcicle_setmana=41, dia="dilluns", tipus_sessio="carrega",
        volum_total=2925, estructura=EstructuraSessio(parts=parts), es_dia_opcional=False,
        notes=None, rol="aerobica", volum_min=2775, volum_max=3075,
    )


@pytest.mark.parametrize(
    ("nom", "esperat"),
    [
        ("Aeròbic", "Aeròbic"),
        ("Bloc principal 1 — Aeròbic", "Aeròbic"),
        ("Bloc principal 2 - Cames", "Cames"),
        ("Bloc principal — Cames", "Cames"),
        ("Aeròbic [Bloc principal 1 — Aeròbic]", "Aeròbic"),
        ("aeròbic", "Aeròbic"),
        ("Tornada a la calma", "Tornada a la calma"),
        ("Inexistent", None),
        (None, None),
    ],
)
def test_trobar_part(nom, esperat):
    part = _trobar_part(_sessio(), nom)
    assert (part.nom if part else None) == esperat


def test_aplicar_contingut_amb_etiquetes_de_bloc():
    sessio = _sessio()
    dades = {"parts": [
        {"nom": "Bloc principal 1 — Aeròbic", "exercicis": [
            {"series": 6, "distancia_m": 200, "execucio": "Crol", "intensitat": "A2"}]},
        {"nom": "Bloc principal 2 — Cames", "exercicis": [
            {"series": 6, "distancia_m": 50, "execucio": "Cames crol", "intensitat": "A1"}]},
    ]}
    _aplicar_contingut_sessio(sessio, dades, 41)
    volums = {p.nom: sum(e.volum_m for e in p.exercicis) for p in sessio.estructura.parts}
    assert volums["Aeròbic"] == 1200
    assert volums["Cames"] == 300


@pytest.mark.parametrize("execucio", ["placeholder", "N.A.", "n/a", "", "-"])
def test_es_farciment(execucio):
    assert _es_farciment({"execucio": execucio})


def test_no_es_farciment():
    assert not _es_farciment({"execucio": "Crol suau", "objectiu": "Activació"})
    assert _es_farciment({"execucio": "Crol", "objectiu": "placeholder"})


def test_farciment_es_descarta():
    sessio = _sessio()
    dades = {"parts": [{"nom": "Escalfament", "exercicis": [
        {"series": 1, "distancia_m": 200, "execucio": "Crol suau", "intensitat": "Recuperació"},
        {"series": 1, "distancia_m": 25, "execucio": "placeholder", "intensitat": "A2"},
        {"series": 1, "distancia_m": 25, "execucio": "N.A.", "intensitat": "Recuperació"},
    ]}]}
    _aplicar_contingut_sessio(sessio, dades, 41)
    escalfament = sessio.estructura.parts[0]
    assert [e.execucio for e in escalfament.exercicis] == ["Crol suau"]


def test_schema_limita_els_noms_de_part():
    tools = _construir_tools_sessio(["Escalfament", "Aeròbic"])
    nom = tools[0]["input_schema"]["properties"]["parts"]["items"]["properties"]["nom"]
    assert nom == {"type": "string", "enum": ["Escalfament", "Aeròbic"]}
    lliure = _construir_tools_sessio()[0]["input_schema"]["properties"]["parts"]
    assert lliure["items"]["properties"]["nom"] == {"type": "string"}

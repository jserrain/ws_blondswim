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


def test_distancies_segons_la_piscina():
    from blondswim.agents.generar_microcicle import distancies_valides

    tools25 = _construir_tools_sessio(["Aeròbic"], 25)
    tools50 = _construir_tools_sessio(["Aeròbic"], 50)

    def enum(tools):
        ex = tools[0]["input_schema"]["properties"]["parts"]["items"]["properties"]
        return ex["exercicis"]["items"]["properties"]["distancia_m"]["enum"]

    assert enum(tools25) == distancies_valides(25) and 25 in enum(tools25)
    assert all(d % 50 == 0 for d in enum(tools50))


def test_aplicar_normalitza_el_descans_i_retorna_distancies_no_valides():
    sessio = _sessio()
    dades = {"parts": [{"nom": "Aeròbic", "exercicis": [
        {"series": 8, "distancia_m": 100, "execucio": "Crol", "descans": "c/1'50\""},
        {"series": 4, "distancia_m": 24, "execucio": "12,5 pap + 12,5 esq"},
    ]}]}
    problemes = _aplicar_contingut_sessio(sessio, dades, 41)
    [aerobic] = [p for p in sessio.estructura.parts if p.nom == "Aeròbic"]
    assert [ex.descans for ex in aerobic.exercicis] == ["c/1:50"]
    assert len(problemes) == 1 and "24 m no és una distància vàlida" in problemes[0]
    problemes50 = _aplicar_contingut_sessio(sessio, dades, 41, piscina_m=50)
    assert len(problemes50) == 1  # 100 val; 24 no


# --- Ajust de volum determinista (W41: +21%) --------------------------------------


def _sessio_volum(*exercicis, rang=(2775, 3075)):
    from blondswim.models.sessio import Exercici  # noqa: F401

    parts = [
        PartSessio(nom="Escalfament", bloc="Escalfament", percentatge_carrega=10,
                   percentatge_qualitat=10, percentatge_descarrega=10,
                   exercicis=[exercicis[0]]),
        PartSessio(nom="Aeròbic", bloc="Bloc principal", percentatge_carrega=90,
                   percentatge_qualitat=90, percentatge_descarrega=90,
                   exercicis=list(exercicis[1:])),
    ]
    return Sessio(id="s", microcicle_setmana=41, dia="dilluns", tipus_sessio="carrega",
                  volum_total=sum(rang) // 2, estructura=EstructuraSessio(parts=parts),
                  rol="aerobica", volum_min=rang[0], volum_max=rang[1])


def _volum(sessio):
    return sum(ex.volum_m for p in sessio.estructura.parts for ex in p.exercicis)


def test_ajustar_volum_treu_series_del_bloc_principal():
    from blondswim.agents.generar_microcicle import ajustar_volum
    from blondswim.models.sessio import Exercici

    escalfament = Exercici(series=1, distancia_m=400, execucio="Crol suau")
    principal = Exercici(series=10, distancia_m=200, execucio="Crol A2", intensitat="A2")
    tecnica = Exercici(series=8, distancia_m=50, execucio="Un braç", id_biblioteca="x")
    sessio = _sessio_volum(escalfament, principal, tecnica)  # 400 + 2000 + 400 = 2800 ok
    principal.series = 14  # 3600
    canvis = ajustar_volum(sessio)
    assert 2775 <= _volum(sessio) <= 3075
    assert principal.series == 11 and tecnica.series == 8 and escalfament.distancia_m == 400
    assert canvis and "11x200" in canvis[-1]


def test_ajustar_volum_afegeix_series_suaus():
    from blondswim.agents.generar_microcicle import ajustar_volum
    from blondswim.models.sessio import Exercici

    a3 = Exercici(series=4, distancia_m=100, execucio="Crol A3", intensitat="A3")
    a1 = Exercici(series=6, distancia_m=200, execucio="Crol A1", intensitat="A1")
    sessio = _sessio_volum(Exercici(series=1, distancia_m=400, execucio="Suau"), a3, a1)
    ajustar_volum(sessio)  # 400 + 400 + 1200 = 2000 -> cal pujar
    assert 2775 <= _volum(sessio) <= 3075
    assert a3.series == 4 and a1.series > 6


def test_ajustar_volum_dins_del_rang_no_toca_res():
    from blondswim.agents.generar_microcicle import ajustar_volum
    from blondswim.models.sessio import Exercici

    sessio = _sessio_volum(Exercici(series=1, distancia_m=400, execucio="Suau"),
                           Exercici(series=12, distancia_m=200, execucio="Crol"))
    assert ajustar_volum(sessio) == []


def test_ajustar_volum_retalla_la_part_que_mes_se_n_passa():
    from blondswim.agents.generar_microcicle import ajustar_volum, desviacions_parts
    from blondswim.models.sessio import Exercici

    escalfament = Exercici(series=6, distancia_m=100, execucio="Crol suau")  # 600 de 400
    principal = Exercici(series=7, distancia_m=200, execucio="Crol A2", intensitat="A2")
    sessio = _sessio_volum(escalfament, principal, rang=(1700, 1900))  # 2000
    sessio.estructura.parts[0].metres_objectiu = 400
    sessio.estructura.parts[1].metres_objectiu = 1400
    assert desviacions_parts(sessio) == ["Escalfament: 600 m (en tocaven 400)"]
    ajustar_volum(sessio)
    assert escalfament.series == 5 and principal.series == 7


def test_prompt_porta_els_metres_de_cada_part():
    from unittest.mock import MagicMock, patch

    from blondswim.agents.generar_microcicle import generar_microcicle
    from blondswim.models.decisio import DecisioMetodologia
    from blondswim.models.nedador import Nedador

    sessio = _sessio()
    for part, m in zip(sessio.estructura.parts, [400, 400, 1400, 300, 400], strict=True):
        part.metres_objectiu = m
    sessio.volum_total = 2900
    nedador = Nedador(id="x", nom="X", categoria="master", proves_objectiu=["100m Lliure"],
                      mode_ritme="rpe")
    met = DecisioMetodologia(prova="100m lliure", categoria="master",
                             metodologia_principal="Polaritzat", metodologies_complementaries=[],
                             forca_evidencia="forta", justificacio="j", avisos=[])
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("prou")
    with patch("blondswim.agents.generar_microcicle.get_llm_client", return_value=client), \
            pytest.raises(Exception, match="prou"):
        generar_microcicle(nedador, [sessio], met)
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert 'nom: "Escalfament": 400 m' in prompt
    assert 'nom: "Tornada a la calma": 400 m (la resta fins a 2900 m)' in prompt
    assert "els teus exercicis han de sumar 2900 m" in prompt
    assert "No cal quadrar" not in prompt


def test_ajustar_volum_no_desfa_exercicis():
    from blondswim.agents.generar_microcicle import ajustar_volum
    from blondswim.models.sessio import Exercici

    rotacio = Exercici(series=8, distancia_m=25, execucio="Per estils: 25 Pap + 25 Esq...")
    recompte = Exercici(series=4, distancia_m=25, execucio="Crol recompte de braçades")
    principal = Exercici(series=10, distancia_m=200, execucio="Crol A2", intensitat="A2")
    sessio = _sessio_volum(recompte, rotacio, principal, rang=(1700, 1900))  # 2500
    ajustar_volum(sessio)
    assert rotacio.series == 8  # rotació d'estils: no es toca
    assert recompte.series >= 2 and principal.series >= 5
    assert 1700 <= _volum(sessio) <= 1900


def test_ajustar_pressupost_retalla_la_velocitat():
    from blondswim.agents.generar_microcicle import ajustar_pressupost
    from blondswim.models.sessio import Exercici

    vel = Exercici(series=8, distancia_m=50, execucio="Crol màxim", intensitat="Velocitat")
    a1 = Exercici(series=10, distancia_m=200, execucio="Crol", intensitat="A1")
    sessio = _sessio_volum(Exercici(series=1, distancia_m=400, execucio="Suau"), vel, a1)
    sessio.rol = "llarga"  # velocitat màxim 200 m
    canvis = ajustar_pressupost(sessio)
    assert vel.series == 4 and canvis
    assert a1.series == 10


def test_ajustar_pressupost_no_retalla_si_el_maxim_es_zero():
    from blondswim.agents.generar_microcicle import ajustar_pressupost
    from blondswim.models.sessio import Exercici

    lactic = Exercici(series=4, distancia_m=50, execucio="Crol", intensitat="MPLA")
    sessio = _sessio_volum(Exercici(series=1, distancia_m=400, execucio="Suau"), lactic)
    assert ajustar_pressupost(sessio) == [] and lactic.series == 4

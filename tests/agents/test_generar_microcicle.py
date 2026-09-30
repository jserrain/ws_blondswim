"""Tests per a la generació de contingut de microcicle amb LLM."""

import json
import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.agents.generar_microcicle import (
    MAX_TOKENS_SESSIO,
    GeneracioMicrocicleError,
    _extreure_few_shot,
    actualitzar_classe_competicio,
    actualitzar_volum_microcicle,
    generar_contingut_mesocicle,
    generar_i_validar_microcicle,
    generar_microcicle,
    guardar_log_decisio,
)
from blondswim.models.calendari import Competicio
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.historial import SerieRealitzada, SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Mesocicle, Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio


@pytest.fixture
def nedador_test() -> Nedador:
    """Nedador amb zones CSS per a tests."""
    return Nedador(
        id="test",
        nom="Test Nedador",
        edat=25,
        categoria="absolut",
        proves_objectiu=["100m lliure", "200m lliure"],
        mode_ritme="temps",
        dia_opcional=None,
        ritmes_css=RitmesCSS(
            font="css_test",
            data_test="2026-09-01",
            recuperacio=90.0,
            a1=85.0,
            a2=80.0,
            a3=75.0,
            velocitat=65.0,
        ),
    )


@pytest.fixture
def metodologia_test() -> DecisioMetodologia:
    """Metodologia de test."""
    return DecisioMetodologia(
        prova="200m lliure",
        categoria="absolut",
        metodologia_principal="Polaritzat",
        metodologies_complementaries=["Tècnica"],
        forca_evidencia="forta",
        justificacio="Test justificació",
        avisos=[],
    )


@pytest.fixture
def sessions_test(nedador_test: Nedador) -> list[Sessio]:
    """Sessions amb estructura però sense contingut."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    return generar_esquelet_sessions(nedador_test, microcicle)


def _tool_use_sessio(sessio: Sessio, n_exercicis: int = 1, stop_reason: str = "tool_use"):
    """Construeix una resposta mock amb tool_use per a UNA sessió."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "retornar_contingut_sessio"
    block.input = {
        "parts": [
            {
                "nom": p.nom,
                "exercicis": [
                    {
                        "series": 4,
                        "distancia_m": 50,
                        "execucio": f"Exercici test {p.nom}",
                        "descans": "c/20\"",
                        "material": None,
                        "intensitat": "A1",
                        "objectiu": "Test",
                    }
                    for _ in range(n_exercicis)
                ],
            }
            for p in sessio.estructura.parts
        ],
    }
    response = MagicMock()
    response.content = [block]
    response.stop_reason = stop_reason
    response.usage = MagicMock(output_tokens=100)
    return response


def test_omple_contingut_sense_tocar_percentatges(
    nedador_test, metodologia_test, sessions_test
):
    """Mock retorna contingut vàlid; verifica que només contingut canvia."""
    # Guardar valors originals
    originals = []
    for sessio in sessions_test:
        for part in sessio.estructura.parts:
            originals.append({
                "sessio_id": sessio.id,
                "nom": part.nom,
                "perc_carrega": part.percentatge_carrega,
                "perc_qualitat": part.percentatge_qualitat,
                "perc_descarrega": part.percentatge_descarrega,
                "volum_total": sessio.volum_total,
                "tipus_sessio": sessio.tipus_sessio,
                "dia": sessio.dia,
            })

    # Mock: una resposta per sessió
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(s) for s in sessions_test
    ]

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        resultat = generar_microcicle(
            nedador_test, sessions_test, metodologia_test, historial=[]
        )

    # Una crida per sessió (el volum mockejat ja és dins del rang)
    assert mock_client.messages.create.call_count == len(sessions_test)

    # Verificar que exercicis s'ha omplert
    for sessio in resultat:
        total = 0
        for part in sessio.estructura.parts:
            assert len(part.exercicis) == 1
            assert "Exercici test" in part.exercicis[0].execucio
            assert part.exercicis[0].volum_m > 0
            total += part.exercicis[0].volum_m
        assert sessio.volum_min * 0.9 <= total <= sessio.volum_max * 1.1

    # Verificar que res més ha canviat
    for i, sessio in enumerate(resultat):
        for j, part in enumerate(sessio.estructura.parts):
            idx = i * len(sessio.estructura.parts) + j
            orig = originals[idx]
            assert part.percentatge_carrega == orig["perc_carrega"]
            assert part.percentatge_qualitat == orig["perc_qualitat"]
            assert part.percentatge_descarrega == orig["perc_descarrega"]
            assert sessio.volum_total == orig["volum_total"]
            assert sessio.tipus_sessio == orig["tipus_sessio"]
            assert sessio.dia == orig["dia"]


def test_part_sense_resposta_es_queda_buida(
    nedador_test, metodologia_test, sessions_test
):
    """Mock retorna contingut només per algunes parts; altres es queden buides."""
    # Mock resposta per a la primera sessió amb només una part
    block = MagicMock()
    block.type = "tool_use"
    block.name = "retornar_contingut_sessio"
    block.input = {
        "parts": [
            {
                "nom": "Escalfament",
                "exercicis": [
                    {
                        "series": 1,
                        "distancia_m": 400,
                        "execucio": "N suau",
                        "descans": None,
                        "material": None,
                        "intensitat": "Recuperació",
                        "objectiu": "Escalfament",
                    }
                ],
            }
            # Només una part, les altres es queden buides
        ],
    }
    mock_response = MagicMock()
    mock_response.content = [block]
    mock_response.stop_reason = "tool_use"
    mock_response.usage = MagicMock(output_tokens=100)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        # No hauria de llançar excepció
        resultat = generar_microcicle(
            nedador_test, sessions_test, metodologia_test, historial=[]
        )

    # Verificar que només Escalfament té exercicis
    primera_sessio = resultat[0]
    escalfament = next(p for p in primera_sessio.estructura.parts if p.nom == "Escalfament")
    assert len(escalfament.exercicis) == 1
    assert escalfament.exercicis[0].execucio == "N suau"
    assert escalfament.exercicis[0].volum_m == 400

    # Les altres parts haurien de quedar-se sense exercicis
    altres_parts = [p for p in primera_sessio.estructura.parts if p.nom != "Escalfament"]
    for part in altres_parts:
        assert part.exercicis == []


def test_error_api_llança_generaciomicrocicleerror(
    nedador_test, metodologia_test, sessions_test
):
    """Mock que llança excepció; verifica que es propaga com GeneracioMicrocicleError."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        with pytest.raises(GeneracioMicrocicleError) as exc_info:
            generar_microcicle(
                nedador_test, sessions_test, metodologia_test, historial=[]
            )

        assert "Error en generar contingut de microcicle" in str(exc_info.value)


def test_few_shot_buit_no_trenca(nedador_test, metodologia_test, sessions_test):
    """historial=None o []; verifica que no peta i crida l'API amb prompt vàlid."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(s) for s in sessions_test
    ] * 2

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        # Amb historial=None
        generar_microcicle(nedador_test, sessions_test, metodologia_test, historial=None)

        # Amb historial=[]
        generar_microcicle(nedador_test, sessions_test, metodologia_test, historial=[])

    # Una crida per sessió, dues vegades (historial=None i historial=[])
    assert mock_client.messages.create.call_count == 2 * len(sessions_test)


def test_extreure_few_shot_prioritza_rellevants():
    """Amb historial petit, verifica que _extreure_few_shot prioritza rellevants."""
    # Crear historial amb sèries rellevants i no rellevants
    historial = [
        SessioRealitzada(
            data="2026-09-01",
            setmana=1,
            series=[
                SerieRealitzada(
                    ordre=1,
                    execucio="4x200 Polaritzat A2",
                    intensitat="A2",
                    objectiu="Polaritzat",
                    volum_m=800,
                ),
                SerieRealitzada(
                    ordre=2,
                    execucio="8x50 Sprint",
                    intensitat="Velocitat",
                    objectiu="Sprint",
                    volum_m=400,
                ),
            ],
            volum_total_m=1200,
            temps_total_min=60.0,
        ),
        SessioRealitzada(
            data="2026-09-02",
            setmana=1,
            series=[
                SerieRealitzada(
                    ordre=1,
                    execucio="6x100 Polaritzat A3",
                    intensitat="A3",
                    objectiu="Polaritzat",
                    volum_m=600,
                ),
            ],
            volum_total_m=600,
            temps_total_min=30.0,
        ),
    ]

    metodologia = DecisioMetodologia(
        prova="200m lliure",
        categoria="absolut",
        metodologia_principal="Polaritzat",
        metodologies_complementaries=[],
        forca_evidencia="forta",
        justificacio="Test",
        avisos=[],
    )

    resultat = _extreure_few_shot(historial, metodologia, n=3)

    # Hauria de retornar primer les sèries amb "Polaritzat"
    assert len(resultat) == 3
    assert "Polaritzat" in resultat[0]
    assert "Polaritzat" in resultat[1]
    # La tercera pot ser Sprint (no rellevant)
    assert "Sprint" in resultat[2]


def test_extreure_few_shot_historial_buit():
    """Amb historial buit, retorna llista buida."""
    metodologia = DecisioMetodologia(
        prova="200m lliure",
        categoria="absolut",
        metodologia_principal="Polaritzat",
        metodologies_complementaries=[],
        forca_evidencia="forta",
        justificacio="Test",
        avisos=[],
    )

    resultat = _extreure_few_shot([], metodologia, n=5)
    assert resultat == []


def _sessio_esquelet(dia: str, setmana: int = 1) -> Sessio:
    """Sessió mínima per mockejar l'esquelet en tests d'integració."""
    parts = [
        PartSessio(
            nom=nom,
            percentatge_carrega=20.0,
            percentatge_qualitat=20.0,
            percentatge_descarrega=20.0,
            contingut=None,
        )
        for nom in [
            "Escalfament",
            "Tècnica+Subaquàtic",
            "Aeròbic/Llindar",
            "Específic/Qualitat",
            "Tornada a la calma",
        ]
    ]
    return Sessio(
        id=f"meso1_s{setmana}_{dia}",
        microcicle_setmana=setmana,
        dia=dia,
        tipus_sessio="carrega",
        volum_total=3000,
        estructura=EstructuraSessio(parts=parts),
        es_dia_opcional=False,
        notes=None,
        rol="mitjana",
        volum_min=2800,
        volum_max=3200,
    )


def test_generar_i_validar_microcicle_setmana_trobada(nedador_test, metodologia_test):
    """Cas normal: setmana trobada, genera sessions i retorna avisos."""
    # Crear macrocicle amb microcicles
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    microcicle_2 = Microcicle(
        setmana=2,
        dates="8-14/10/2026",
        mesocicle_id="meso1",
        tipus_base="qualitat",
        volum_objectiu=14000,
        dies_qualitat=True,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1-2",
        dates="1-14/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=13000,
        volum_max=16000,
        volum_mitja_previst=14500,
        microcicles=[microcicle_1, microcicle_2],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Mock resposta LLM: una per sessió, construïda a partir del sessio_id
    # que apareix al prompt (l'esquelet en genera tantes com dies actius).
    def _resposta_per_prompt(*args, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        match = re.search(r'sessio_id: "([^"]+)"', prompt)
        sessio_id = match.group(1)
        dia = sessio_id.rsplit("_", 1)[-1]
        return _tool_use_sessio(_sessio_esquelet(dia))

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _resposta_per_prompt

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ), patch(
        "blondswim.agents.generar_microcicle.guardar_log_decisio"
    ) as mock_guardar_log:
        sessions, avisos = generar_i_validar_microcicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            setmana=1,
            metodologia=metodologia_test,
            pla_taper=[],
            avisos_pics_a=[],
            historial=[],
        )

    # Verificar que retorna sessions (nombre depèn de dies_disponibles del nedador)
    assert isinstance(sessions, list)
    assert len(sessions) > 0
    assert all(isinstance(s, Sessio) for s in sessions)

    # Verificar que retorna avisos (llista, pot ser buida)
    assert isinstance(avisos, list)

    # Verificar que s'ha cridat guardar_log_decisio
    mock_guardar_log.assert_called_once_with(nedador_test.id, 1, metodologia_test)


def test_generar_i_validar_microcicle_setmana_no_trobada(
    nedador_test, metodologia_test
):
    """Setmana no trobada: aixeca ValueError."""
    # Crear macrocicle amb només setmana 1
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1",
        dates="1-7/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=13000,
        volum_max=16000,
        volum_mitja_previst=14500,
        microcicles=[microcicle_1],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Intentar generar setmana 99 (no existeix)
    with pytest.raises(ValueError) as exc_info:
        generar_i_validar_microcicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            setmana=99,
            metodologia=metodologia_test,
            pla_taper=[],
            avisos_pics_a=[],
            historial=[],
        )

    assert "setmana=99" in str(exc_info.value)


def test_guardar_log_decisio(metodologia_test, tmp_path, monkeypatch):
    """Verifica que guardar_log_decisio crea el fitxer amb els camps correctes."""
    # Usar tmp_path per no escriure al repo real
    monkeypatch.chdir(tmp_path)

    # Cridar la funció
    microcicle_data = {"volum_total": 15000, "sessions": 5}
    fitxer = guardar_log_decisio(
        nedador_id="test_nedador",
        setmana=1,
        metodologia=metodologia_test,
        microcicle_generat=microcicle_data,
    )

    # Verificar que el fitxer existeix
    assert fitxer.exists()
    assert fitxer.name == "test_nedador_1.json"
    assert fitxer.parent.name == "log_decisions"

    # Llegir i verificar contingut
    with open(fitxer, encoding="utf-8") as f:
        data = json.load(f)

    assert data["nedador_id"] == "test_nedador"
    assert data["setmana"] == 1
    assert "timestamp" in data
    assert data["metodologia"]["prova"] == "200m lliure"
    assert data["metodologia"]["categoria"] == "absolut"
    assert data["metodologia"]["metodologia_principal"] == "Polaritzat"
    assert data["microcicle_generat"] == microcicle_data


def test_guardar_log_decisio_sense_microcicle(metodologia_test, tmp_path, monkeypatch):
    """Verifica que funciona amb microcicle_generat=None."""
    monkeypatch.chdir(tmp_path)

    fitxer = guardar_log_decisio(
        nedador_id="test_nedador",
        setmana=2,
        metodologia=metodologia_test,
        microcicle_generat=None,
    )

    assert fitxer.exists()

    with open(fitxer, encoding="utf-8") as f:
        data = json.load(f)

    assert data["microcicle_generat"] is None


def test_guardar_log_ajust_crea_fitxer_amb_una_entrada(tmp_path, monkeypatch):
    """Verifica que guardar_log_ajust crea el fitxer amb una entrada."""
    from blondswim.agents.generar_microcicle import guardar_log_ajust

    monkeypatch.chdir(tmp_path)

    # Cridar la funció
    fitxer = guardar_log_ajust(
        nedador_id="test_nedador",
        setmana=1,
        tipus_ajust="volum",
        valor_anterior="15000",
        valor_nou="18000",
        motiu="Ajust manual del coach",
    )

    # Verificar que el fitxer existeix
    assert fitxer.exists()
    assert fitxer.name == "test_nedador_1_ajustos.json"
    assert fitxer.parent.name == "log_decisions"

    # Llegir i verificar contingut
    with open(fitxer, encoding="utf-8") as f:
        ajustos = json.load(f)

    # Hauria de ser una llista amb una entrada
    assert isinstance(ajustos, list)
    assert len(ajustos) == 1

    # Verificar camps de l'entrada
    ajust = ajustos[0]
    assert "timestamp" in ajust
    assert ajust["tipus_ajust"] == "volum"
    assert ajust["valor_anterior"] == "15000"
    assert ajust["valor_nou"] == "18000"
    assert ajust["motiu"] == "Ajust manual del coach"


def test_guardar_log_ajust_afegeix_a_fitxer_existent(tmp_path, monkeypatch):
    """Verifica que guardar_log_ajust afegeix a un fitxer existent sense perdre entrades."""
    from blondswim.agents.generar_microcicle import guardar_log_ajust

    monkeypatch.chdir(tmp_path)

    # Primera crida: crear fitxer amb primera entrada
    fitxer = guardar_log_ajust(
        nedador_id="test_nedador",
        setmana=1,
        tipus_ajust="volum",
        valor_anterior="15000",
        valor_nou="18000",
        motiu="Primer ajust",
    )

    # Segona crida: afegir segona entrada
    fitxer = guardar_log_ajust(
        nedador_id="test_nedador",
        setmana=1,
        tipus_ajust="volum",
        valor_anterior="18000",
        valor_nou="16000",
        motiu="Segon ajust",
    )

    # Llegir i verificar contingut
    with open(fitxer, encoding="utf-8") as f:
        ajustos = json.load(f)

    # Hauria de tenir 2 entrades
    assert isinstance(ajustos, list)
    assert len(ajustos) == 2

    # Verificar primera entrada (no s'ha perdut)
    assert ajustos[0]["tipus_ajust"] == "volum"
    assert ajustos[0]["valor_anterior"] == "15000"
    assert ajustos[0]["valor_nou"] == "18000"
    assert ajustos[0]["motiu"] == "Primer ajust"

    # Verificar segona entrada
    assert ajustos[1]["tipus_ajust"] == "volum"
    assert ajustos[1]["valor_anterior"] == "18000"
    assert ajustos[1]["valor_nou"] == "16000"
    assert ajustos[1]["motiu"] == "Segon ajust"


def test_actualitzar_volum_microcicle_canvia_valor():
    """Verifica que actualitzar_volum_microcicle canvia volum_objectiu correctament."""
    # Crear macrocicle amb microcicles
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    microcicle_2 = Microcicle(
        setmana=2,
        dates="8-14/10/2026",
        mesocicle_id="meso1",
        tipus_base="qualitat",
        volum_objectiu=14000,
        dies_qualitat=True,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1-2",
        dates="1-14/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=13000,
        volum_max=16000,
        volum_mitja_previst=14500,
        microcicles=[microcicle_1, microcicle_2],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Guardar valors originals del microcicle 1
    volum_original = microcicle_1.volum_objectiu
    dates_original = microcicle_1.dates
    tipus_original = microcicle_1.tipus_base

    # Actualitzar volum
    nou_volum = 18000
    microcicle_actualitzat, avisos = actualitzar_volum_microcicle(
        macrocicle=macrocicle,
        setmana=1,
        nou_volum_objectiu=nou_volum,
        motiu="Ajust manual del coach",
    )

    # Verificar que el volum ha canviat
    assert microcicle_actualitzat.volum_objectiu == nou_volum
    assert microcicle_actualitzat.volum_objectiu != volum_original

    # Verificar que la resta de camps no han canviat
    assert microcicle_actualitzat.dates == dates_original
    assert microcicle_actualitzat.tipus_base == tipus_original
    assert microcicle_actualitzat.setmana == 1
    assert microcicle_actualitzat.mesocicle_id == "meso1"

    # Verificar que retorna avisos (llista, pot ser buida)
    assert isinstance(avisos, list)


def test_actualitzar_volum_microcicle_setmana_no_trobada():
    """Verifica que actualitzar_volum_microcicle aixeca ValueError si la setmana no existeix."""
    # Crear macrocicle amb només setmana 1
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1",
        dates="1-7/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=13000,
        volum_max=16000,
        volum_mitja_previst=14500,
        microcicles=[microcicle_1],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Intentar actualitzar setmana 99 (no existeix)
    with pytest.raises(ValueError) as exc_info:
        actualitzar_volum_microcicle(
            macrocicle=macrocicle,
            setmana=99,
            nou_volum_objectiu=20000,
            motiu="Test",
        )

    assert "setmana=99" in str(exc_info.value)


def test_actualitzar_classe_competicio_canvia_classe():
    """Verifica que actualitzar_classe_competicio canvia la classe correctament."""
    # Crear llista de competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició 1",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Competició 2",
            data_inici="2026-11-20",
            data_fi="2026-11-22",
            classe="B",
            piscina="50m",
        ),
        Competicio(
            id="comp3",
            nom="Competició 3",
            data_inici="2026-12-10",
            data_fi="2026-12-12",
            classe="C",
            piscina="25m",
        ),
    ]

    # Guardar classe original de comp2
    classe_original = competicions[1].classe

    # Actualitzar classe de comp2 de B a A
    competicions_actualitzades, pla_taper, avisos_pics_a = actualitzar_classe_competicio(
        competicions=competicions,
        competicio_id="comp2",
        nova_classe="A",
        motiu="Prioritzada pel nedador",
    )

    # Verificar que la classe ha canviat
    comp2 = next(c for c in competicions_actualitzades if c.id == "comp2")
    assert comp2.classe == "A"
    assert comp2.classe != classe_original

    # Verificar que retorna pla_taper i avisos
    assert isinstance(pla_taper, list)
    assert isinstance(avisos_pics_a, list)

    # Verificar que ara hi ha 2 competicions A al pla de taper
    comps_a_al_pla = [p for p in pla_taper if p["classe"] == "A"]
    assert len(comps_a_al_pla) == 2


def test_actualitzar_classe_competicio_recalcula_pics_prioritzats():
    """Verifica que canviar una competició B a A l'afegeix als pics prioritzats."""
    # Crear llista de competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Competició B propera",
            data_inici="2026-10-25",
            data_fi="2026-10-27",
            classe="B",
            piscina="50m",
        ),
    ]

    # Abans de canviar: comp2 no és pic prioritzat, no hauria de tenir re-taper
    _, pla_taper_abans, _ = actualitzar_classe_competicio(
        competicions=competicions,
        competicio_id="comp1",  # No canviem res, només per obtenir pla inicial
        nova_classe="A",
        motiu="Mantenir",
    )

    comp2_abans = next(p for p in pla_taper_abans if p["competicio_id"] == "comp2")
    assert comp2_abans["retaper"] is False

    # Canviar comp2 de B a A
    competicions_actualitzades, pla_taper_despres, avisos_pics_a = actualitzar_classe_competicio(
        competicions=competicions,
        competicio_id="comp2",
        nova_classe="A",
        motiu="Prioritzada",
    )

    # Verificar que comp2 ara és classe A
    comp2 = next(c for c in competicions_actualitzades if c.id == "comp2")
    assert comp2.classe == "A"

    # Verificar que el pla de taper s'ha recalculat amb comp2 com a A
    comp2_despres = next(p for p in pla_taper_despres if p["competicio_id"] == "comp2")
    assert comp2_despres["classe"] == "A"
    assert comp2_despres["dies_taper_pre"] == 14  # Taper de classe A

    # Verificar que ara hi ha avisos de pics A (2 competicions A properes)
    assert len(avisos_pics_a) > 0


def test_actualitzar_classe_competicio_id_no_trobat():
    """Verifica que actualitzar_classe_competicio aixeca ValueError si l'id no existeix."""
    # Crear llista de competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició 1",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="A",
            piscina="25m",
        ),
    ]

    # Intentar actualitzar competició inexistent
    with pytest.raises(ValueError) as exc_info:
        actualitzar_classe_competicio(
            competicions=competicions,
            competicio_id="comp_inexistent",
            nova_classe="B",
            motiu="Test",
        )

    assert "comp_inexistent" in str(exc_info.value)


def test_eliminar_competicio_la_treu_de_la_llista():
    """Verifica que eliminar_competicio treu la competició de la llista."""
    from blondswim.agents.generar_microcicle import eliminar_competicio

    # Crear llista de competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició 1",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Competició 2",
            data_inici="2026-11-20",
            data_fi="2026-11-22",
            classe="B",
            piscina="50m",
        ),
        Competicio(
            id="comp3",
            nom="Competició 3",
            data_inici="2026-12-10",
            data_fi="2026-12-12",
            classe="C",
            piscina="25m",
        ),
    ]

    # Guardar nombre original
    nombre_original = len(competicions)

    # Eliminar comp2
    competicions_actualitzades, pla_taper, _avisos_pics_a = eliminar_competicio(
        competicions=competicions,
        competicio_id="comp2",
        motiu="Malaltia",
    )

    # Verificar que s'ha eliminat
    assert len(competicions_actualitzades) == nombre_original - 1
    assert not any(c.id == "comp2" for c in competicions_actualitzades)

    # Verificar que les altres competicions encara hi són
    assert any(c.id == "comp1" for c in competicions_actualitzades)
    assert any(c.id == "comp3" for c in competicions_actualitzades)

    # Verificar que retorna pla_taper i avisos
    assert isinstance(pla_taper, list)
    assert isinstance(_avisos_pics_a, list)


def test_eliminar_competicio_recalcula_pics_a_sense_ella():
    """Verifica que eliminar una competició A recalcula els pics prioritzats sense ella."""
    from blondswim.agents.generar_microcicle import eliminar_competicio

    # Crear llista de competicions amb 2 competicions A properes
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A1",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Competició A2 propera",
            data_inici="2026-10-25",
            data_fi="2026-10-27",
            classe="A",
            piscina="50m",
        ),
        Competicio(
            id="comp3",
            nom="Competició B",
            data_inici="2026-12-10",
            data_fi="2026-12-12",
            classe="B",
            piscina="25m",
        ),
    ]

    # Eliminar comp2 (una de les competicions A)
    competicions_actualitzades, pla_taper, _avisos_pics_a = eliminar_competicio(
        competicions=competicions,
        competicio_id="comp2",
        motiu="Lesió",
    )

    # Verificar que comp2 no està a la llista
    assert not any(c.id == "comp2" for c in competicions_actualitzades)

    # Verificar que el pla de taper s'ha recalculat sense comp2
    assert not any(p["competicio_id"] == "comp2" for p in pla_taper)

    # Verificar que només hi ha 1 competició A al pla de taper
    comps_a_al_pla = [p for p in pla_taper if p["classe"] == "A"]
    assert len(comps_a_al_pla) == 1
    assert comps_a_al_pla[0]["competicio_id"] == "comp1"


def test_eliminar_competicio_id_no_trobat():
    """Verifica que eliminar_competicio aixeca ValueError si l'id no existeix."""
    from blondswim.agents.generar_microcicle import eliminar_competicio

    # Crear llista de competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició 1",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="A",
            piscina="25m",
        ),
    ]

    # Intentar eliminar competició inexistent
    with pytest.raises(ValueError) as exc_info:
        eliminar_competicio(
            competicions=competicions,
            competicio_id="comp_inexistent",
            motiu="Test",
        )

    assert "comp_inexistent" in str(exc_info.value)


def test_generar_contingut_mesocicle_totes_les_setmanes_ok(nedador_test):
    """Verifica que generar_contingut_mesocicle genera totes les setmanes correctament."""

    # Crear macrocicle amb un mesocicle de 3 setmanes
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    microcicle_2 = Microcicle(
        setmana=2,
        dates="8-14/10/2026",
        mesocicle_id="meso1",
        tipus_base="qualitat",
        volum_objectiu=14000,
        dies_qualitat=True,
        test_css=False,
    )
    microcicle_3 = Microcicle(
        setmana=3,
        dates="15-21/10/2026",
        mesocicle_id="meso1",
        tipus_base="descarrega",
        volum_objectiu=12000,
        dies_qualitat=False,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1-3",
        dates="1-21/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=12000,
        volum_max=16000,
        volum_mitja_previst=13667,
        microcicles=[microcicle_1, microcicle_2, microcicle_3],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Mock seleccionar_metodologia
    mock_metodologia = DecisioMetodologia(
        prova="200m lliure",
        categoria="absolut",
        metodologia_principal="Polaritzat",
        metodologies_complementaries=[],
        forca_evidencia="forta",
        justificacio="Test",
        avisos=[],
    )

    # Mock generar_i_validar_microcicle per retornar sessions mock
    def mock_generar_i_validar(nedador, macrocicle, setmana, metodologia, pla_taper, avisos_pics_a, historial):
        # Retornar sessions mock per aquesta setmana
        estructura_mock = EstructuraSessio(
            parts=[
                PartSessio(
                    nom="Escalfament",
                    percentatge_carrega=20,
                    percentatge_qualitat=20,
                    percentatge_descarrega=20,
                    contingut=None,
                )
            ]
        )
        sessio_mock = Sessio(
            id=f"test_sessio_{setmana}",
            microcicle_setmana=setmana,
            dia="dilluns",
            tipus_sessio="carrega",
            volum_total=3000,
            es_dia_opcional=False,
            estructura=estructura_mock,
        )
        return [sessio_mock], []

    with patch(
        "blondswim.agents.generar_microcicle.seleccio_model.seleccionar_metodologia",
        return_value=mock_metodologia,
    ), patch(
        "blondswim.agents.generar_microcicle.generar_i_validar_microcicle",
        side_effect=mock_generar_i_validar,
    ):
        resultats, errors = generar_contingut_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            categoria="absolut",
            mesocicle_id="meso1",
            pla_taper=[],
            avisos_pics_a=[],
            historial=[],
        )

    # Verificar que s'han generat les 3 setmanes
    assert len(resultats) == 3
    assert 1 in resultats
    assert 2 in resultats
    assert 3 in resultats

    # Verificar que cada setmana té sessions
    assert len(resultats[1]) == 1
    assert len(resultats[2]) == 1
    assert len(resultats[3]) == 1

    # Verificar que no hi ha errors
    assert len(errors) == 0


def test_generar_contingut_mesocicle_mesocicle_id_no_trobat(nedador_test):
    """Verifica que generar_contingut_mesocicle aixeca ValueError si el mesocicle_id no existeix."""

    # Crear macrocicle amb un mesocicle
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1",
        dates="1-7/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=13000,
        volum_max=16000,
        volum_mitja_previst=14500,
        microcicles=[microcicle_1],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Intentar generar mesocicle inexistent
    with pytest.raises(ValueError) as exc_info:
        generar_contingut_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            categoria="absolut",
            mesocicle_id="meso_inexistent",
            pla_taper=[],
            avisos_pics_a=[],
            historial=[],
        )

    assert "meso_inexistent" in str(exc_info.value)


def test_generar_contingut_mesocicle_una_setmana_falla_continua(nedador_test):
    """Verifica que si una setmana falla, les altres es generen igualment."""

    # Crear macrocicle amb 3 setmanes
    microcicle_1 = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )
    microcicle_2 = Microcicle(
        setmana=2,
        dates="8-14/10/2026",
        mesocicle_id="meso1",
        tipus_base="qualitat",
        volum_objectiu=14000,
        dies_qualitat=True,
        test_css=False,
    )
    microcicle_3 = Microcicle(
        setmana=3,
        dates="15-21/10/2026",
        mesocicle_id="meso1",
        tipus_base="descarrega",
        volum_objectiu=12000,
        dies_qualitat=False,
        test_css=False,
    )
    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1-3",
        dates="1-21/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Polaritzat",
        volum_min=12000,
        volum_max=16000,
        volum_mitja_previst=13667,
        microcicles=[microcicle_1, microcicle_2, microcicle_3],
    )
    macrocicle = Macrocicle(
        nom="Temporada 2026-27",
        temporada="2026-27",
        data_inici="2026-10-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle],
    )

    # Mock seleccionar_metodologia
    mock_metodologia = DecisioMetodologia(
        prova="200m lliure",
        categoria="absolut",
        metodologia_principal="Polaritzat",
        metodologies_complementaries=[],
        forca_evidencia="forta",
        justificacio="Test",
        avisos=[],
    )

    # Mock generar_i_validar_microcicle que falla a la setmana 2
    def mock_generar_i_validar(nedador, macrocicle, setmana, metodologia, pla_taper, avisos_pics_a, historial):
        if setmana == 2:
            raise GeneracioMicrocicleError("Error API a la setmana 2")

        # Retornar sessions mock per les altres setmanes
        estructura_mock = EstructuraSessio(
            parts=[
                PartSessio(
                    nom="Escalfament",
                    percentatge_carrega=20,
                    percentatge_qualitat=20,
                    percentatge_descarrega=20,
                    contingut=None,
                )
            ]
        )
        sessio_mock = Sessio(
            id=f"test_sessio_{setmana}",
            microcicle_setmana=setmana,
            dia="dilluns",
            tipus_sessio="carrega",
            volum_total=3000,
            es_dia_opcional=False,
            estructura=estructura_mock,
        )
        return [sessio_mock], []

    with patch(
        "blondswim.agents.generar_microcicle.seleccio_model.seleccionar_metodologia",
        return_value=mock_metodologia,
    ), patch(
        "blondswim.agents.generar_microcicle.generar_i_validar_microcicle",
        side_effect=mock_generar_i_validar,
    ):
        resultats, errors = generar_contingut_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            categoria="absolut",
            mesocicle_id="meso1",
            pla_taper=[],
            avisos_pics_a=[],
            historial=[],
        )

    # Verificar que s'han generat les setmanes 1 i 3 (no la 2)
    assert len(resultats) == 2
    assert 1 in resultats
    assert 2 not in resultats
    assert 3 in resultats

    # Verificar que hi ha 1 error (setmana 2)
    assert len(errors) == 1
    assert errors[0]["setmana"] == 2
    assert "Error API a la setmana 2" in errors[0]["error"]


def test_una_crida_per_sessio(nedador_test, metodologia_test, sessions_test):
    """Es fa exactament una crida a l'API per cada sessió de la setmana."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(s) for s in sessions_test
    ]

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        resultat = generar_microcicle(nedador_test, sessions_test, metodologia_test)

    # Una crida per sessió (el volum mockejat ja és dins del rang)
    assert mock_client.messages.create.call_count == len(sessions_test)
    assert len(resultat) == len(sessions_test)
    for sessio in resultat:
        assert all(part.exercicis for part in sessio.estructura.parts)


def test_retry_en_max_tokens(nedador_test, metodologia_test, sessions_test):
    """Si stop_reason == 'max_tokens', es reintenta una vegada amb concisió."""
    sessions = sessions_test[:1]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(sessions[0], stop_reason="max_tokens"),
        _tool_use_sessio(sessions[0], stop_reason="tool_use"),
    ]

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        resultat = generar_microcicle(nedador_test, sessions, metodologia_test)

    # 1 crida truncada + 1 reintent per concisió (volum ja vàlid)
    assert mock_client.messages.create.call_count == 2
    segon_prompt = mock_client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
    assert "màxim 3 exercicis per part" in segon_prompt
    assert all(part.exercicis for part in resultat[0].estructura.parts)


def test_max_tokens_doble_deixa_sessio_buida(
    nedador_test, metodologia_test, sessions_test, caplog
):
    """Si falla dues vegades per max_tokens, s'avisa i la sessió queda buida."""
    sessions = sessions_test[:1]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(sessions[0], stop_reason="max_tokens"),
        _tool_use_sessio(sessions[0], stop_reason="max_tokens"),
    ]

    with caplog.at_level(logging.WARNING), patch(
        "blondswim.agents.generar_microcicle.get_llm_client",
        return_value=mock_client,
    ):
        resultat = generar_microcicle(nedador_test, sessions, metodologia_test)

    assert mock_client.messages.create.call_count == 2
    assert all(not part.exercicis for part in resultat[0].estructura.parts)
    assert any("truncada de nou" in r.message for r in caplog.records)


def test_rol_i_rang_al_prompt(nedador_test, metodologia_test, sessions_test):
    """El prompt inclou el rol i el rang de volum de la sessió."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(s) for s in sessions_test
    ]

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        generar_microcicle(nedador_test, sessions_test, metodologia_test)

    primer_prompt = mock_client.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
    sessio = sessions_test[0]
    assert f"rol: {sessio.rol}" in primer_prompt
    assert f"volum_min: {sessio.volum_min}m" in primer_prompt
    assert f"volum_max: {sessio.volum_max}m" in primer_prompt


def test_volum_fora_rang_reintenta_un_cop(
    nedador_test, metodologia_test, sessions_test, caplog
):
    """Si el volum queda fora del rang, es reintenta una vegada amb el missatge."""
    sessions = sessions_test[:1]
    sessio = sessions[0]

    # Primera resposta amb volum=1000m, lluny del rang [2800, 3200]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(sessio, volum=1000),
        _tool_use_sessio(sessio),
    ]

    with caplog.at_level(logging.WARNING), patch(
        "blondswim.agents.generar_microcicle.get_llm_client",
        return_value=mock_client,
    ):
        generar_microcicle(nedador_test, sessions, metodologia_test)

    assert mock_client.messages.create.call_count == 2
    segon_prompt = mock_client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
    assert "El volum ha estat 1000 m" in segon_prompt
    assert f"entre {sessio.volum_min} i {sessio.volum_max} m" in segon_prompt
    assert any("fora del rang" in r.message for r in caplog.records)


def test_max_tokens_sessio_constant():
    """La constant de max_tokens per sessió és 4096."""
    assert MAX_TOKENS_SESSIO == 4096


def test_parts_com_string_json_es_parseja(nedador_test, metodologia_test, sessions_test):
    """Si 'parts' arriba com a string JSON, es deserialitza i s'aplica."""
    sessions = sessions_test[:1]
    sessio = sessions[0]

    parts_list = [
        {
            "nom": p.nom,
            "exercicis": [
                {
                    "series": 4,
                    "distancia_m": 50,
                    "execucio": f"Exercici {p.nom}",
                    "descans": None,
                    "material": None,
                    "intensitat": "A1",
                    "objectiu": "Test",
                }
            ],
        }
        for p in sessio.estructura.parts
    ]

    block = MagicMock()
    block.type = "tool_use"
    block.name = "retornar_contingut_sessio"
    block.input = {"parts": json.dumps(parts_list)}
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "tool_use"
    response.usage = MagicMock(output_tokens=100)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = response

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        resultat = generar_microcicle(nedador_test, sessions, metodologia_test)

    # 1 crida inicial + 1 reintent per volum fora de rang
    assert mock_client.messages.create.call_count == 2
    for part in resultat[0].estructura.parts:
        assert len(part.exercicis) == 1


def test_parts_buit_reintenta_un_cop(nedador_test, metodologia_test, sessions_test):
    """Si 'parts' és buit, es reintenta una vegada i s'aplica la resposta bona."""
    sessions = sessions_test[:1]
    sessio = sessions[0]

    buit = MagicMock()
    buit.type = "tool_use"
    buit.name = "retornar_contingut_sessio"
    buit.input = {"parts": []}
    response_buit = MagicMock()
    response_buit.content = [buit]
    response_buit.stop_reason = "tool_use"
    response_buit.usage = MagicMock(output_tokens=10)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        response_buit,
        _tool_use_sessio(sessio),
    ]

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        resultat = generar_microcicle(nedador_test, sessions, metodologia_test)

    # 1 buit + 1 reintent parts (volum ja vàlid)
    assert mock_client.messages.create.call_count == 2
    assert all(part.exercicis for part in resultat[0].estructura.parts)


def test_parts_buit_dos_cops_deixa_sessio_buida(
    nedador_test, metodologia_test, sessions_test, caplog
):
    """Si 'parts' és buit dues vegades, s'avisa i la sessió queda buida."""
    sessions = sessions_test[:1]

    def _buit():
        block = MagicMock()
        block.type = "tool_use"
        block.name = "retornar_contingut_sessio"
        block.input = {"parts": []}
        response = MagicMock()
        response.content = [block]
        response.stop_reason = "tool_use"
        response.usage = MagicMock(output_tokens=10)
        return response

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [_buit(), _buit()]

    with caplog.at_level(logging.WARNING), patch(
        "blondswim.agents.generar_microcicle.get_llm_client",
        return_value=mock_client,
    ):
        resultat = generar_microcicle(nedador_test, sessions, metodologia_test)

    assert mock_client.messages.create.call_count == 2
    assert all(not part.exercicis for part in resultat[0].estructura.parts)
    assert any("encara buit després del reintent" in r.message for r in caplog.records)


def test_distancia_no_multiple_25_s_arrodoneix(
    nedador_test, metodologia_test, sessions_test, caplog
):
    """Una distancia_m no múltiple de 25 s'arrodoneix i no es descarta."""
    sessions = sessions_test[:1]
    sessio = sessions[0]

    block = MagicMock()
    block.type = "tool_use"
    block.name = "retornar_contingut_sessio"
    block.input = {
        "parts": [
            {
                "nom": sessio.estructura.parts[0].nom,
                "exercicis": [
                    {
                        "series": 1,
                        "distancia_m": 60,
                        "execucio": "Test",
                        "descans": None,
                        "material": None,
                        "intensitat": "A1",
                        "objectiu": "Test",
                    }
                ],
            }
        ]
    }
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "tool_use"
    response.usage = MagicMock(output_tokens=10)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = response

    with caplog.at_level(logging.INFO), patch(
        "blondswim.agents.generar_microcicle.get_llm_client",
        return_value=mock_client,
    ):
        resultat = generar_microcicle(nedador_test, sessions, metodologia_test)

    part = resultat[0].estructura.parts[0]
    assert len(part.exercicis) == 1
    assert part.exercicis[0].distancia_m == 50
    assert any("arrodonida a 50" in r.message for r in caplog.records)


def test_log_setmana_generada_correctament(
    nedador_test, metodologia_test, sessions_test, caplog
):
    """Si totes les sessions tenen contingut, es loga 'generada correctament'."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(s) for s in sessions_test
    ] * 2

    with caplog.at_level(logging.INFO), patch(
        "blondswim.agents.generar_microcicle.get_llm_client",
        return_value=mock_client,
    ):
        generar_microcicle(nedador_test, sessions_test, metodologia_test)

    assert any("generada correctament" in r.message for r in caplog.records)


def test_log_setmana_sessions_sense_contingut(
    nedador_test, metodologia_test, sessions_test, caplog
):
    """Si alguna sessió queda sense contingut, es loga el WARNING corresponent."""
    sessions = sessions_test[:2]

    def _buit():
        block = MagicMock()
        block.type = "tool_use"
        block.name = "retornar_contingut_sessio"
        block.input = {"parts": []}
        response = MagicMock()
        response.content = [block]
        response.stop_reason = "tool_use"
        response.usage = MagicMock(output_tokens=10)
        return response

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _tool_use_sessio(sessions[0]),
        _tool_use_sessio(sessions[0]),
        _buit(), _buit(),
    ]

    with caplog.at_level(logging.WARNING), patch(
        "blondswim.agents.generar_microcicle.get_llm_client",
        return_value=mock_client,
    ):
        generar_microcicle(nedador_test, sessions, metodologia_test)

    assert any(
        "1 sessions sense contingut" in r.message for r in caplog.records
    )

"""Tests per a la generació de contingut de microcicle amb LLM."""

import json
from unittest.mock import MagicMock, patch

import pytest

from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.agents.generar_microcicle import (
    GeneracioMicrocicleError,
    _extreure_few_shot,
    generar_i_validar_microcicle,
    generar_microcicle,
    guardar_log_decisio,
)
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.historial import SerieRealitzada, SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Mesocicle, Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import Sessio


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

    # Mock resposta LLM
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "retornar_contingut_sessions"
    mock_tool_use.input = {
        "sessions": [
            {
                "sessio_id": s.id,
                "parts": [
                    {"nom": p.nom, "contingut": f"Contingut test {p.nom}"}
                    for p in s.estructura.parts
                ],
            }
            for s in sessions_test
        ]
    }
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        resultat = generar_microcicle(
            nedador_test, sessions_test, metodologia_test, historial=[]
        )

    # Verificar que contingut s'ha omplert
    for sessio in resultat:
        for part in sessio.estructura.parts:
            assert part.contingut is not None
            assert "Contingut test" in part.contingut

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


def test_part_sense_resposta_es_queda_none(
    nedador_test, metodologia_test, sessions_test
):
    """Mock retorna contingut només per algunes parts; altres es queden None."""
    # Mock resposta LLM amb només algunes parts
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "retornar_contingut_sessions"
    mock_tool_use.input = {
        "sessions": [
            {
                "sessio_id": sessions_test[0].id,
                "parts": [
                    {
                        "nom": "Escalfament",
                        "contingut": "400 N suau Recuperació",
                    }
                    # Només una part, les altres es queden None
                ],
            }
        ]
    }
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        # No hauria de llançar excepció
        resultat = generar_microcicle(
            nedador_test, sessions_test, metodologia_test, historial=[]
        )

    # Verificar que només Escalfament té contingut
    primera_sessio = resultat[0]
    escalfament = next(p for p in primera_sessio.estructura.parts if p.nom == "Escalfament")
    assert escalfament.contingut == "400 N suau Recuperació"

    # Les altres parts haurien de ser None
    altres_parts = [p for p in primera_sessio.estructura.parts if p.nom != "Escalfament"]
    for part in altres_parts:
        assert part.contingut is None


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
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "retornar_contingut_sessions"
    mock_tool_use.input = {"sessions": []}
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "blondswim.agents.generar_microcicle.get_llm_client", return_value=mock_client
    ):
        # Amb historial=None
        generar_microcicle(nedador_test, sessions_test, metodologia_test, historial=None)

        # Amb historial=[]
        generar_microcicle(nedador_test, sessions_test, metodologia_test, historial=[])

    # Verificar que s'ha cridat l'API dues vegades
    assert mock_client.messages.create.call_count == 2


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

    # Mock resposta LLM
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "retornar_contingut_sessions"
    mock_tool_use.input = {"sessions": []}
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

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

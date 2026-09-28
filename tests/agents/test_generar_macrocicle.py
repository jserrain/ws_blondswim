"""Tests per a la generació de macrocicles."""

from unittest.mock import MagicMock, patch

import pytest

from blondswim.agents.generar_macrocicle import generar_macrocicle, generar_mesocicle
from blondswim.models.calendari import Competicio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle
from blondswim.models.nedador import Nedador


@pytest.fixture
def nedador_test() -> Nedador:
    """Nedador base per als tests de generació de mesocicles."""
    return Nedador(
        id="test",
        nom="Test Nedador",
        categoria="absolut",
        proves_objectiu=["200m lliure"],
        mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dimecres", "dijous"],
        dia_opcional="dissabte",
    )


@pytest.fixture
def historial_test() -> list[SessioRealitzada]:
    """Històric de 3 sessions de 3000m per als tests de volums."""
    return [
        SessioRealitzada(
            data=f"2026-09-0{i}",
            series=[],
            volum_total_m=3000,
            temps_total_min=90.0,
        )
        for i in range(1, 4)
    ]


def test_generar_macrocicle_amb_competicions_a():
    """Verifica que amb almenys 1 competició A genera el macrocicle sense avís."""
    # Crear competicions: 2 classe A ben separades
    competicions = [
        Competicio(
            id="comp1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Campionat Espanya",
            data_inici="2027-05-29",
            data_fi="2027-05-31",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="comp3",
            nom="Competició B",
            data_inici="2027-03-15",
            data_fi="2027-03-17",
            classe="B",
            piscina="50m",
        ),
    ]

    # Generar macrocicle
    macrocicle, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
    )

    # Verificar que s'ha generat 1 macrocicle
    assert macrocicle.nom == "Macrocicle 2026-2027"
    assert macrocicle.data_inici == "2026-09-01"
    assert macrocicle.data_fi == "2027-06-30"
    assert macrocicle.temporada == "2026-2027"
    assert macrocicle.mesocicles == []

    # Verificar que retorna avisos (sense avís de "cap competició A")
    assert isinstance(avisos, list)
    # No hauria de tenir l'avís de "cap_competicio_a"
    avisos_cap_comp_a = [a for a in avisos if a.get("tipus_avis") == "cap_competicio_a"]
    assert len(avisos_cap_comp_a) == 0


def test_generar_macrocicle_sense_competicions_a():
    """Verifica que sense competicions A genera el macrocicle amb avís."""
    # Crear competicions: només B i C
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició B",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="B",
            piscina="25m",
        ),
        Competicio(
            id="comp2",
            nom="Competició C",
            data_inici="2027-03-15",
            data_fi="2027-03-17",
            classe="C",
            piscina="50m",
        ),
    ]

    # Generar macrocicle
    macrocicle, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
    )

    # Verificar que s'ha generat 1 macrocicle
    assert macrocicle.nom == "Macrocicle 2026-2027"
    assert macrocicle.data_inici == "2026-09-01"
    assert macrocicle.data_fi == "2027-06-30"
    assert macrocicle.temporada == "2026-2027"
    assert macrocicle.mesocicles == []

    # Verificar que retorna avisos amb l'avís de "cap competició A"
    assert isinstance(avisos, list)
    avisos_cap_comp_a = [a for a in avisos if a.get("tipus_avis") == "cap_competicio_a"]
    assert len(avisos_cap_comp_a) == 1
    assert "almenys un objectiu A" in avisos_cap_comp_a[0]["missatge"]


def test_generar_macrocicle_crida_validar_espaiat_pics_a():
    """Verifica que els avisos venen de validar_espaiat_pics_a."""
    # Crear competicions
    competicions = [
        Competicio(
            id="comp1",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
    ]

    # Mock validar_espaiat_pics_a per verificar que es crida
    avisos_mock = [{"tipus_avis": "test", "missatge": "Test avís"}]

    with patch(
        "blondswim.agents.generar_macrocicle.context_competicio.validar_espaiat_pics_a",
        return_value=avisos_mock,
    ) as mock_validar:
        _macrocicle, avisos = generar_macrocicle(
            nedador_id="test",
            competicions=competicions,
            temporada_data_inici="2026-09-01",
            temporada_data_fi="2027-06-30",
        )

        # Verificar que s'ha cridat validar_espaiat_pics_a amb les competicions
        mock_validar.assert_called_once_with(competicions)

        # Verificar que els avisos retornats inclouen els del mock
        assert avisos_mock[0] in avisos


def test_generar_mesocicle_competicio_a_llunyana_genera_base():
    """Verifica que amb una competició A llunyana (>10 setmanes) genera Base de 4 setmanes."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    # Competició A a 15 setmanes
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A llunyana",
            data_inici="2026-12-14",  # ~15 setmanes després
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    # Generar mesocicle
    mesocicle, avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    # Verificar tipus i duració
    assert mesocicle.fase_objectiu == "Base"
    assert mesocicle.nom == "Base 1"
    assert mesocicle.id == "meso_1"
    assert mesocicle.setmanes == "1-4"  # 4 setmanes
    
    # Verificar que s'ha afegit al macrocicle
    assert len(macrocicle.mesocicles) == 1
    assert macrocicle.mesocicles[0] == mesocicle

    # No hauria de tenir avisos
    assert len(avisos) == 0


def test_generar_mesocicle_competicio_a_propera_genera_peak():
    """Verifica que amb una competició A a 2 setmanes genera Peak retallat."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    # Competició A a 2 setmanes
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A propera",
            data_inici="2026-09-15",  # 2 setmanes després
            data_fi="2026-09-17",
            classe="A",
            piscina="25m",
        ),
    ]

    # Generar mesocicle
    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    # Verificar tipus i duració
    assert mesocicle.fase_objectiu == "Peak"
    assert mesocicle.nom == "Peak 1"
    assert mesocicle.setmanes == "1-2"  # 2 setmanes (retallat)

    # Verificar que s'ha afegit al macrocicle
    assert len(macrocicle.mesocicles) == 1


def test_generar_mesocicle_despres_cursa_genera_transicio():
    """Verifica que després d'un mesocicle Cursa, el següent és Transicio."""
    from blondswim.models.macrocicle import Mesocicle, Microcicle

    # Crear macrocicle amb un mesocicle Cursa
    microcicle_cursa = Microcicle(
        setmana=1,
        dates="1-7/09/2026",
        mesocicle_id="meso_1",
        tipus_base="taper",
        volum_objectiu=10000,
        dies_qualitat=False,
        test_css=False,
    )
    mesocicle_cursa = Mesocicle(
        id="meso_1",
        nom="Cursa 1",
        setmanes="1",
        dates="01/09/2026-07/09/2026",
        fase_objectiu="Cursa",
        metodologia_dominant="",
        volum_min=0,
        volum_max=0,
        volum_mitja_previst=0,
        microcicles=[microcicle_cursa],
    )

    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[mesocicle_cursa],
    )

    # Competició A llunyana
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    # Generar següent mesocicle
    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    # Verificar que és Transicio
    assert mesocicle.fase_objectiu == "Transicio"
    assert mesocicle.nom == "Transicio 2"
    assert mesocicle.setmanes == "2"  # 1 setmana
    
    # Verificar que s'ha afegit al macrocicle
    assert len(macrocicle.mesocicles) == 2


def test_generar_mesocicle_sense_competicio_a_genera_base_amb_avis():
    """Verifica que sense competició A genera Base amb avís."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    # Només competicions B i C
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició B",
            data_inici="2026-10-15",
            data_fi="2026-10-17",
            classe="B",
            piscina="25m",
        ),
    ]

    # Generar mesocicle
    mesocicle, avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    # Verificar tipus
    assert mesocicle.fase_objectiu == "Base"

    # Verificar avís
    assert len(avisos) == 1
    assert avisos[0]["tipus_avis"] == "cap_competicio_a_restant"
    assert "No queda cap competició classe A" in avisos[0]["missatge"]


def test_generar_mesocicle_enriquir_amb_llm_canvia_fase_objectiu():
    """Verifica que amb enriquir_amb_llm=True es crida l'API i canvia fase_objectiu."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    # Mock resposta LLM
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "retornar_fase_objectiu"
    mock_tool_use.input = {
        "fase_objectiu": "Base - Desenvolupament de capacitat aeròbica i tècnica fonamental"
    }
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "blondswim.agents.generar_macrocicle.get_llm_client",
        return_value=mock_client,
    ):
        mesocicle, _avisos = generar_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            competicions=competicions,
            enriquir_amb_llm=True,
            historial=historial_test,
        )

    # Verificar que s'ha cridat l'API
    mock_client.messages.create.assert_called_once()

    # Verificar que fase_objectiu s'ha enriquit
    assert mesocicle.fase_objectiu == "Base - Desenvolupament de capacitat aeròbica i tècnica fonamental"
    assert mesocicle.fase_objectiu != "Base"  # Ha canviat respecte al determinista


def test_generar_mesocicle_sense_enriquir_llm_no_crida_api():
    """Verifica que amb enriquir_amb_llm=False no es crida l'API."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    mock_client = MagicMock()

    with patch(
        "blondswim.agents.generar_macrocicle.get_llm_client",
        return_value=mock_client,
    ):
        mesocicle, _avisos = generar_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            competicions=competicions,
            enriquir_amb_llm=False,
            historial=historial_test,
        )

    # Verificar que NO s'ha cridat l'API
    mock_client.messages.create.assert_not_called()

    # Verificar que fase_objectiu és el determinista
    assert mesocicle.fase_objectiu == "Base"


def test_generar_mesocicle_fallback_si_llm_falla():
    """Verifica que si la crida LLM falla, manté fase_objectiu determinista."""
    # Crear macrocicle buit
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    # Mock que llança excepció
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")

    with patch(
        "blondswim.agents.generar_macrocicle.get_llm_client",
        return_value=mock_client,
    ):
        # No hauria de propagar l'error
        mesocicle, _avisos = generar_mesocicle(
            nedador=nedador_test,
            macrocicle=macrocicle,
            competicions=competicions,
            enriquir_amb_llm=True,
            historial=historial_test,
        )

    # Verificar que fase_objectiu és el determinista (fallback)
    assert mesocicle.fase_objectiu == "Base"

    # Verificar que el mesocicle s'ha creat correctament
    assert mesocicle.nom == "Base 1"
    assert len(macrocicle.mesocicles) == 1


def test_generar_mesocicle_calcula_volums_base(
    nedador_test, historial_test
):
    """Verifica que un mesocicle Base calcula els volums a partir de l'històric."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A llunyana",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    mesocicle, avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    # 3 sessions de 3000m -> volum_per_sessio = 3000
    # 4 dies disponibles -> volum_min = 12000
    # + 1 dia opcional -> volum_max = 15000
    # mitjana = 13500
    assert mesocicle.fase_objectiu == "Base"
    assert mesocicle.volum_min == 12000
    assert mesocicle.volum_max == 15000
    assert mesocicle.volum_mitja_previst == 13500

    # Sense avís de falta d'històric
    assert not any(a.get("tipus_avis") == "sense_historial" for a in avisos)


def test_generar_mesocicle_sense_historial_volums_zero(nedador_test):
    """Verifica que sense històric els volums són 0 i apareix l'avís."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A llunyana",
            data_inici="2026-12-14",
            data_fi="2026-12-16",
            classe="A",
            piscina="25m",
        ),
    ]

    mesocicle, avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=None,
    )

    assert mesocicle.volum_min == 0
    assert mesocicle.volum_max == 0
    assert mesocicle.volum_mitja_previst == 0

    avisos_historial = [
        a for a in avisos if a.get("tipus_avis") == "sense_historial"
    ]
    assert len(avisos_historial) == 1
    assert "Sense històric del nedador" in avisos_historial[0]["missatge"]


def test_generar_mesocicle_peak_retalla_volums(
    nedador_test, historial_test
):
    """Verifica que un mesocicle Peak aplica el 50% de retallada als volums."""
    macrocicle = Macrocicle(
        nom="Macrocicle 2026-2027",
        temporada="2026-2027",
        data_inici="2026-09-01",
        data_fi="2027-06-30",
        mesocicles=[],
    )

    # Competició A a 2 setmanes -> Peak
    competicions = [
        Competicio(
            id="comp1",
            nom="Competició A propera",
            data_inici="2026-09-15",
            data_fi="2026-09-17",
            classe="A",
            piscina="25m",
        ),
    ]

    mesocicle, _avisos = generar_mesocicle(
        nedador=nedador_test,
        macrocicle=macrocicle,
        competicions=competicions,
        enriquir_amb_llm=False,
        historial=historial_test,
    )

    assert mesocicle.fase_objectiu == "Peak"
    # Base: 12000 / 15000 / 13500 -> Peak (50%): 6000 / 7500 / 6750
    assert mesocicle.volum_min == 6000
    assert mesocicle.volum_max == 7500
    assert mesocicle.volum_mitja_previst == 6750

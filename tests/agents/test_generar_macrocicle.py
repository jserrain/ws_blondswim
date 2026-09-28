"""Tests per a la generació de macrocicles."""

from unittest.mock import patch

from blondswim.agents.generar_macrocicle import generar_macrocicle
from blondswim.models.calendari import Competicio


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

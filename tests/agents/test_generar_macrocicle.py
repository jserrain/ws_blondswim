"""Tests per a la generació de macrocicles."""

from unittest.mock import patch

import pytest

from blondswim.agents.generar_macrocicle import generar_macrocicle
from blondswim.models.calendari import Competicio


def test_generar_macrocicle_amb_2_competicions_a():
    """Verifica que amb 2 competicions A genera 2 macrocicles amb dates correctes."""
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

    # Generar macrocicles
    macrocicles, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
        dies_recuperacio_a=14,
    )

    # Verificar que s'han generat 2 macrocicles
    assert len(macrocicles) == 2

    # Verificar primer macrocicle
    macro1 = macrocicles[0]
    assert macro1.nom == "Macrocicle 1"
    assert macro1.data_inici == "2026-09-01"
    # data_fi = 2027-01-17 + 14 dies = 2027-01-31
    assert macro1.data_fi == "2027-01-31"
    assert macro1.temporada == "2026-2027"
    assert macro1.mesocicles == []

    # Verificar segon macrocicle
    macro2 = macrocicles[1]
    assert macro2.nom == "Macrocicle 2"
    # data_inici = 2027-01-31 + 1 dia = 2027-02-01
    assert macro2.data_inici == "2027-02-01"
    # És l'últim, usa temporada_data_fi
    assert macro2.data_fi == "2027-06-30"
    assert macro2.temporada == "2026-2027"
    assert macro2.mesocicles == []

    # Verificar que retorna avisos
    assert isinstance(avisos, list)


def test_generar_macrocicle_sense_competicions_a():
    """Verifica que sense competicions A genera 1 sol macrocicle."""
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

    # Generar macrocicles
    macrocicles, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
        dies_recuperacio_a=14,
    )

    # Verificar que s'ha generat 1 sol macrocicle
    assert len(macrocicles) == 1

    # Verificar macrocicle
    macro = macrocicles[0]
    assert macro.nom == "Macrocicle 1"
    assert macro.data_inici == "2026-09-01"
    assert macro.data_fi == "2027-06-30"
    assert macro.temporada == "2026-2027"
    assert macro.mesocicles == []

    # Verificar que retorna avisos (buida perquè no hi ha competicions A)
    assert isinstance(avisos, list)


def test_generar_macrocicle_amb_1_competicio_a():
    """Verifica el cas amb 1 sola competició A."""
    # Crear competicions: 1 classe A
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
            nom="Competició B",
            data_inici="2027-03-15",
            data_fi="2027-03-17",
            classe="B",
            piscina="50m",
        ),
    ]

    # Generar macrocicles
    macrocicles, avisos = generar_macrocicle(
        nedador_id="test",
        competicions=competicions,
        temporada_data_inici="2026-09-01",
        temporada_data_fi="2027-06-30",
        dies_recuperacio_a=14,
    )

    # Verificar que s'ha generat 1 macrocicle
    assert len(macrocicles) == 1

    # Verificar macrocicle
    macro = macrocicles[0]
    assert macro.nom == "Macrocicle 1"
    assert macro.data_inici == "2026-09-01"
    # És l'únic, usa temporada_data_fi
    assert macro.data_fi == "2027-06-30"
    assert macro.temporada == "2026-2027"
    assert macro.mesocicles == []

    # Verificar que retorna avisos
    assert isinstance(avisos, list)


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
        macrocicles, avisos = generar_macrocicle(
            nedador_id="test",
            competicions=competicions,
            temporada_data_inici="2026-09-01",
            temporada_data_fi="2027-06-30",
            dies_recuperacio_a=14,
        )

        # Verificar que s'ha cridat validar_espaiat_pics_a amb les competicions
        mock_validar.assert_called_once_with(competicions)

        # Verificar que els avisos retornats són els del mock
        assert avisos == avisos_mock

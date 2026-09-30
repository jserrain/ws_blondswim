"""Tests per a la generació de l'esquelet de sessions."""

import pytest

from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador


@pytest.fixture
def nedador_base() -> Nedador:
    """Nedador amb configuració estàndard (4 dies, sense dia opcional)."""
    return Nedador(
        id="test",
        nom="Test Nedador",
        edat=25,
        categoria="absolut",
        proves_objectiu=["100m lliure"],
        mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dimecres", "dijous"],
        dia_opcional=None,
    )


@pytest.fixture
def nedador_sense_opcional() -> Nedador:
    """Nedador sense dia opcional."""
    return Nedador(
        id="test2",
        nom="Test Nedador 2",
        edat=30,
        categoria="master",
        proves_objectiu=["200m lliure"],
        mode_ritme="temps",
        dies_disponibles=["dilluns", "dimarts", "dimecres", "dijous"],
        dia_opcional=None,
    )


def test_setmana_qualitat_totes_sessions_qualitat(nedador_base):
    """Setmana de qualitat: totes les sessions són tipus_sessio='qualitat'."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="qualitat",
        volum_objectiu=15000,
        dies_qualitat=False,  # Ignorat quan tipus_base="qualitat"
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    # 4 sessions (només dies_disponibles)
    assert len(sessions) == 4

    # Totes haurien de ser tipus_sessio="qualitat"
    for sessio in sessions:
        assert sessio.tipus_sessio == "qualitat"


def test_setmana_carrega_amb_dies_qualitat_dc_es_qualitat(nedador_base):
    """Setmana càrrega amb dies_qualitat=True: dimecres és qualitat."""
    microcicle = Microcicle(
        setmana=2,
        dates="8-14/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=16000,
        dies_qualitat=True,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    assert len(sessions) == 4

    # Dimecres hauria de ser "qualitat", la resta "carrega"
    for sessio in sessions:
        if sessio.dia == "dimecres":
            assert sessio.tipus_sessio == "qualitat"
        else:
            assert sessio.tipus_sessio == "carrega"


def test_setmana_carrega_sense_dies_qualitat_totes_carrega(nedador_base):
    """Setmana càrrega amb dies_qualitat=False: totes les sessions són càrrega."""
    microcicle = Microcicle(
        setmana=3,
        dates="15-21/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15500,
        dies_qualitat=False,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    assert len(sessions) == 4

    # Totes haurien de ser "carrega"
    for sessio in sessions:
        assert sessio.tipus_sessio == "carrega"


def test_setmana_descarrega_totes_descarrega(nedador_base):
    """Setmana descàrrega: totes les sessions són tipus_sessio='descarrega'."""
    microcicle = Microcicle(
        setmana=4,
        dates="22-28/10/2026",
        mesocicle_id="meso1",
        tipus_base="descarrega",
        volum_objectiu=12000,
        dies_qualitat=False,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    assert len(sessions) == 4

    # Totes haurien de ser "descarrega"
    for sessio in sessions:
        assert sessio.tipus_sessio == "descarrega"


def test_setmana_taper_percentatges_descarrega(nedador_base):
    """Setmana taper: usa percentatges de descàrrega per a totes les parts."""
    microcicle = Microcicle(
        setmana=5,
        dates="29/10-4/11/2026",
        mesocicle_id="meso2",
        tipus_base="taper",
        volum_objectiu=10000,
        dies_qualitat=False,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    assert len(sessions) == 4

    # Totes haurien de ser tipus_sessio="taper"
    for sessio in sessions:
        assert sessio.tipus_sessio == "taper"

        # Verificar que les parts usen percentatges de descàrrega
        # (Escalfament hauria de ser 15%, no 10%)
        escalfament = next(p for p in sessio.estructura.parts if p.nom == "Escalfament")
        assert escalfament.percentatge_descarrega == 15.0


def test_nombre_sessions_coincideix_amb_dies_actius(nedador_base, nedador_sense_opcional):
    """Nombre de sessions coincideix amb dies_disponibles + dia_opcional."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )

    # Ambdós nedadors tenen 4 dies disponibles -> 4 sessions
    sessions_amb_opcional = generar_esquelet_sessions(nedador_base, microcicle)
    assert len(sessions_amb_opcional) == 4

    sessions_sense_opcional = generar_esquelet_sessions(nedador_sense_opcional, microcicle)
    assert len(sessions_sense_opcional) == 4


def test_suma_volum_total_sessions_igual_volum_objectiu(nedador_base):
    """Suma de volum_total de totes les sessions = volum_objectiu exactament."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15123,  # Nombre que no es divideix exactament per 4
        dies_qualitat=False,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    # La suma ha de ser exactament igual al volum objectiu
    suma_volum = sum(s.volum_total for s in sessions)
    assert suma_volum == microcicle.volum_objectiu


def test_contingut_totes_parts_es_none(nedador_base):
    """Totes les parts de totes les sessions tenen contingut=None."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=True,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    # Verificar que totes les parts de totes les sessions tenen contingut=None
    for sessio in sessions:
        for part in sessio.estructura.parts:
            assert part.contingut is None


def test_estructura_5_parts_estandard(nedador_base):
    """Cada sessió té exactament 5 parts amb els noms estàndard."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    noms_esperats = [
        "Escalfament",
        "Tècnica+Subaquàtic",
        "Aeròbic/Llindar",
        "Específic/Qualitat",
        "Tornada a la calma",
    ]

    for sessio in sessions:
        assert len(sessio.estructura.parts) == 5
        noms_parts = [p.nom for p in sessio.estructura.parts]
        assert noms_parts == noms_esperats


def test_id_sessio_format_correcte(nedador_base):
    """ID de cada sessió segueix el format correcte."""
    microcicle = Microcicle(
        setmana=3,
        dates="15-21/10/2026",
        mesocicle_id="meso2",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )

    sessions = generar_esquelet_sessions(nedador_base, microcicle)

    for sessio in sessions:
        # Format: {mesocicle_id}_s{setmana}_{dia}
        assert sessio.id.startswith("meso2_s3_")
        assert sessio.microcicle_setmana == 3
        assert sessio.dia in ["dilluns", "dimarts", "dimecres", "dijous"]


def test_cap_sessio_es_dia_opcional(nedador_base, nedador_sense_opcional):
    """Amb 4 dies d'aigua, cap sessió és dia opcional."""
    microcicle = Microcicle(
        setmana=1,
        dates="1-7/10/2026",
        mesocicle_id="meso1",
        tipus_base="carrega",
        volum_objectiu=15000,
        dies_qualitat=False,
        test_css=False,
    )

    sessions_amb_opcional = generar_esquelet_sessions(nedador_base, microcicle)
    for sessio in sessions_amb_opcional:
        assert sessio.es_dia_opcional is False

    sessions_sense_opcional = generar_esquelet_sessions(nedador_sense_opcional, microcicle)
    for sessio in sessions_sense_opcional:
        assert sessio.es_dia_opcional is False

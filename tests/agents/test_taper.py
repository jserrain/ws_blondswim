"""
Tests per al càlcul de plans de taper i recuperació.

Valida les funcions de càlcul de taper, detecció de re-taper i generació del pla
complet de temporada amb casos reals del calendari 2026-27.
"""

from blondswim.agents.taper import (
    calcular_taper,
    detectar_retaper,
    generar_pla_taper_temporada,
)
from blondswim.models.calendari import Competicio


def test_calcular_taper_classe_a():
    """Catalunya Hivern (A): taper progressiu 14 dies, recuperació activa_llarga 14 dies."""
    cat_hivern = Competicio(
        id="cat_hivern_2027",
        nom="Catalunya Hivern",
        data_inici="2027-01-16",
        data_fi="2027-01-17",
        classe="A",
        piscina="25m",
    )

    pla = calcular_taper(cat_hivern)

    assert pla["dies_taper_pre"] == 14
    assert pla["tipus_taper"] == "progressiu"
    assert pla["dies_recuperacio_post"] == 14
    assert pla["tipus_recuperacio"] == "activa_llarga"


def test_calcular_taper_classe_b():
    """Espanya (B): taper lleuger 3 dies, recuperació activa 3 dies."""
    espanya = Competicio(
        id="espanya_2027",
        nom="Campionat d'Espanya",
        data_inici="2027-02-04",
        data_fi="2027-02-07",
        classe="B",
        piscina="25m",
    )

    pla = calcular_taper(espanya)

    assert pla["dies_taper_pre"] == 3
    assert pla["tipus_taper"] == "lleuger"
    assert pla["dies_recuperacio_post"] == 3
    assert pla["tipus_recuperacio"] == "activa"


def test_calcular_taper_classe_c():
    """Competició C: sense taper, recuperació estàndard 1 dia."""
    comp_c = Competicio(
        id="comp_c_2027",
        nom="Competició Local",
        data_inici="2027-03-15",
        data_fi="2027-03-15",
        classe="C",
        piscina="25m",
    )

    pla = calcular_taper(comp_c)

    assert pla["dies_taper_pre"] == 0
    assert pla["tipus_taper"] == "cap"
    assert pla["dies_recuperacio_post"] == 1
    assert pla["tipus_recuperacio"] == "estandard"


def test_calcular_taper_parametres_personalitzats():
    """Taper amb paràmetres personalitzats."""
    comp_a = Competicio(
        id="comp_a",
        nom="Competició A",
        data_inici="2027-01-10",
        data_fi="2027-01-11",
        classe="A",
        piscina="25m",
    )

    pla = calcular_taper(
        comp_a,
        dies_taper_a=21,
        dies_recuperacio_a=10,
    )

    assert pla["dies_taper_pre"] == 21
    assert pla["dies_recuperacio_post"] == 10


def test_detectar_retaper_amb_prioritat():
    """Catalunya Hivern (A) + Espanya (B) amb Espanya a pics_prioritzats → True."""
    cat_hivern = Competicio(
        id="cat_hivern_2027",
        nom="Catalunya Hivern",
        data_inici="2027-01-16",
        data_fi="2027-01-17",
        classe="A",
        piscina="25m",
    )
    espanya = Competicio(
        id="espanya_2027",
        nom="Campionat d'Espanya",
        data_inici="2027-02-04",
        data_fi="2027-02-07",
        classe="B",
        piscina="25m",
    )

    es_retaper = detectar_retaper(
        cat_hivern,
        espanya,
        pics_prioritzats=["espanya_2027"],
        finestra_setmanes=4,
    )

    assert es_retaper is True


def test_detectar_retaper_sense_prioritat():
    """Catalunya Hivern + Espanya sense Espanya a pics_prioritzats → False."""
    cat_hivern = Competicio(
        id="cat_hivern_2027",
        nom="Catalunya Hivern",
        data_inici="2027-01-16",
        data_fi="2027-01-17",
        classe="A",
        piscina="25m",
    )
    espanya = Competicio(
        id="espanya_2027",
        nom="Campionat d'Espanya",
        data_inici="2027-02-04",
        data_fi="2027-02-07",
        classe="B",
        piscina="25m",
    )

    es_retaper = detectar_retaper(
        cat_hivern,
        espanya,
        pics_prioritzats=[],  # Espanya no prioritzada
        finestra_setmanes=4,
    )

    assert es_retaper is False


def test_detectar_retaper_competicio_anterior_no_classe_a():
    """Re-taper només s'aplica si la competició anterior és classe A."""
    comp_b1 = Competicio(
        id="comp_b1",
        nom="Competició B1",
        data_inici="2027-01-10",
        data_fi="2027-01-11",
        classe="B",
        piscina="25m",
    )
    comp_b2 = Competicio(
        id="comp_b2",
        nom="Competició B2",
        data_inici="2027-01-20",
        data_fi="2027-01-21",
        classe="B",
        piscina="25m",
    )

    es_retaper = detectar_retaper(
        comp_b1,
        comp_b2,
        pics_prioritzats=["comp_b2"],
        finestra_setmanes=4,
    )

    # comp_b1 no és classe A → no re-taper
    assert es_retaper is False


def test_detectar_retaper_fora_de_finestra():
    """Re-taper no s'aplica si la separació supera la finestra temporal."""
    cat_hivern = Competicio(
        id="cat_hivern_2027",
        nom="Catalunya Hivern",
        data_inici="2027-01-16",
        data_fi="2027-01-17",
        classe="A",
        piscina="25m",
    )
    cat_estiu = Competicio(
        id="cat_estiu_2027",
        nom="Catalunya Estiu",
        data_inici="2027-05-29",
        data_fi="2027-05-30",
        classe="A",
        piscina="50m",
    )

    es_retaper = detectar_retaper(
        cat_hivern,
        cat_estiu,
        pics_prioritzats=["cat_estiu_2027"],
        finestra_setmanes=4,
    )

    # ~19 setmanes de separació, fora de finestra de 4
    assert es_retaper is False


def test_generar_pla_taper_temporada_calendari_complet():
    """Pla de taper per al calendari complet 2026-27 (3 competicions de mostra)."""
    competicions = [
        Competicio(
            id="cat_hivern_2027",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="espanya_2027",
            nom="Campionat d'Espanya",
            data_inici="2027-02-04",
            data_fi="2027-02-07",
            classe="B",
            piscina="25m",
        ),
        Competicio(
            id="cat_estiu_2027",
            nom="Catalunya Estiu",
            data_inici="2027-05-29",
            data_fi="2027-05-30",
            classe="A",
            piscina="50m",
        ),
    ]

    pla = generar_pla_taper_temporada(
        competicions,
        pics_prioritzats=["espanya_2027"],
    )

    # Verificar que hi ha 3 entrades
    assert len(pla) == 3

    # Verificar ordre cronològic
    assert pla[0]["competicio_id"] == "cat_hivern_2027"
    assert pla[1]["competicio_id"] == "espanya_2027"
    assert pla[2]["competicio_id"] == "cat_estiu_2027"

    # Verificar Catalunya Hivern (A, sense re-taper)
    assert pla[0]["classe"] == "A"
    assert pla[0]["dies_taper_pre"] == 14
    assert pla[0]["tipus_taper"] == "progressiu"
    assert pla[0]["retaper"] is False

    # Verificar Espanya (B, amb re-taper perquè està a pics_prioritzats)
    assert pla[1]["classe"] == "B"
    assert pla[1]["dies_taper_pre"] == 3
    assert pla[1]["tipus_taper"] == "lleuger"
    assert pla[1]["retaper"] is True  # Espanya prioritzada i propera a Catalunya Hivern

    # Verificar Catalunya Estiu (A, sense re-taper perquè està lluny)
    assert pla[2]["classe"] == "A"
    assert pla[2]["dies_taper_pre"] == 14
    assert pla[2]["retaper"] is False


def test_generar_pla_taper_temporada_sense_retaper():
    """Pla de taper sense cap competició marcada com a pic_prioritzat."""
    competicions = [
        Competicio(
            id="cat_hivern_2027",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="espanya_2027",
            nom="Campionat d'Espanya",
            data_inici="2027-02-04",
            data_fi="2027-02-07",
            classe="B",
            piscina="25m",
        ),
    ]

    pla = generar_pla_taper_temporada(
        competicions,
        pics_prioritzats=[],  # Cap competició prioritzada
    )

    # Cap competició hauria de tenir re-taper
    assert all(not entrada["retaper"] for entrada in pla)


def test_generar_pla_taper_temporada_ordre_cronologic():
    """El pla de taper s'ordena cronològicament independentment de l'ordre d'entrada."""
    competicions = [
        Competicio(
            id="cat_estiu_2027",
            nom="Catalunya Estiu",
            data_inici="2027-05-29",
            data_fi="2027-05-30",
            classe="A",
            piscina="50m",
        ),
        Competicio(
            id="cat_hivern_2027",
            nom="Catalunya Hivern",
            data_inici="2027-01-16",
            data_fi="2027-01-17",
            classe="A",
            piscina="25m",
        ),
        Competicio(
            id="espanya_2027",
            nom="Campionat d'Espanya",
            data_inici="2027-02-04",
            data_fi="2027-02-07",
            classe="B",
            piscina="25m",
        ),
    ]

    pla = generar_pla_taper_temporada(competicions, pics_prioritzats=[])

    # Verificar ordre cronològic correcte
    assert pla[0]["data_inici"] == "2027-01-16"
    assert pla[1]["data_inici"] == "2027-02-04"
    assert pla[2]["data_inici"] == "2027-05-29"

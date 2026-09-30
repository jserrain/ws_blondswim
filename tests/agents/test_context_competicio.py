"""
Tests per a l'anàlisi del context de competicions.

Valida les funcions de validació d'espaiat, detecció de re-taper i classificació
amb casos reals del calendari 2026-27 i casos sintètics.
"""


from blondswim.agents.context_competicio import (
    classificar_pics,
    detectar_candidats_retaper,
    setmanes_entre,
    validar_espaiat_pics_a,
)
from blondswim.models.calendari import Competicio


def test_setmanes_entre_catalunya_hivern_estiu():
    """Catalunya Hivern (16-17 gen) a Catalunya Estiu (29-30 maig): ~19 setmanes."""
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

    setmanes = setmanes_entre(cat_hivern, cat_estiu)

    # 17 gen a 29 maig = 132 dies = 18.86 setmanes
    assert 18.5 < setmanes < 19.5


def test_setmanes_entre_catalunya_hivern_espanya():
    """Catalunya Hivern (16-17 gen) a Espanya (4-7 feb): ~2.4 setmanes."""
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

    setmanes = setmanes_entre(cat_hivern, espanya)

    # 17 gen a 4 feb = 18 dies = 2.57 setmanes
    assert 2.0 < setmanes < 3.0


def test_validar_espaiat_pics_a_calendari_real():
    """Calendari real 2026-27: Catalunya Hivern i Estiu ben espaiades, 0 avisos."""
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
            classe="B",  # Classe B, no entra a validació A-A
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

    avisos = validar_espaiat_pics_a(competicions)

    # ~19 setmanes entre les dues A: sense avisos
    assert len(avisos) == 0


def test_validar_espaiat_pics_a_separacio_insuficient():
    """Cas sintètic: Espanya reclassificada com a A → avís separacio_insuficient."""
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
            classe="A",  # Reclassificada com a A
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

    avisos = validar_espaiat_pics_a(competicions, min_setmanes=8)

    # Hauria de tenir avís entre Catalunya Hivern i Espanya (~2.4 setmanes)
    avisos_separacio = [a for a in avisos if a["tipus_avis"] == "separacio_insuficient"]
    assert len(avisos_separacio) >= 1
    
    # Trobar l'avís específic Catalunya Hivern - Espanya
    avis_cat_esp = next(
        (a for a in avisos_separacio 
         if a["comp_a_id"] == "cat_hivern_2027" and a["comp_b_id"] == "espanya_2027"),
        None
    )
    assert avis_cat_esp is not None
    assert avis_cat_esp["setmanes_separacio"] < 8
    assert "tractar la segona com a classe B" in avis_cat_esp["missatge"]


def test_validar_espaiat_pics_a_massa_pics_a():
    """Cas sintètic: >3 competicions classe A → avís massa_pics_a."""
    competicions = [
        Competicio(
            id=f"comp_{i}",
            nom=f"Competició {i}",
            data_inici=f"2027-{i:02d}-01",
            data_fi=f"2027-{i:02d}-02",
            classe="A",
            piscina="25m",
        )
        for i in range(1, 6)  # 5 competicions A
    ]

    avisos = validar_espaiat_pics_a(competicions)

    # Hauria de tenir l'avís de massa_pics_a
    avisos_massa_pics = [a for a in avisos if a["tipus_avis"] == "massa_pics_a"]
    assert len(avisos_massa_pics) == 1
    assert "5 competicions classe A" in avisos_massa_pics[0]["missatge"]
    assert "revisar prioritats" in avisos_massa_pics[0]["missatge"]


def test_detectar_candidats_retaper_amb_prioritat():
    """Catalunya Hivern (A) + Espanya (B) amb Espanya a pics_prioritzats → detecta."""
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

    candidats = detectar_candidats_retaper(
        competicions, pics_prioritzats=["espanya_2027"], finestra_setmanes=4
    )

    assert len(candidats) == 1
    assert candidats[0]["comp_primera_id"] == "cat_hivern_2027"
    assert candidats[0]["comp_segona_id"] == "espanya_2027"
    assert candidats[0]["setmanes_separacio"] < 4
    assert "Candidat a re-taper" in candidats[0]["missatge"]


def test_detectar_candidats_retaper_sense_prioritat():
    """Catalunya Hivern + Espanya properes, però Espanya no prioritzada → no detecta."""
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

    candidats = detectar_candidats_retaper(
        competicions, pics_prioritzats=[], finestra_setmanes=4
    )

    # Espanya no està a pics_prioritzats
    assert len(candidats) == 0


def test_classificar_pics_calendari_real():
    """Classificació del calendari real 2026-27, inclou avisos de validar_espaiat_pics_a."""
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

    resum = classificar_pics(competicions)

    assert resum["total"] == 3
    assert resum["per_classe"]["A"] == 2
    assert resum["per_classe"]["B"] == 1
    assert resum["per_classe"]["C"] == 0
    assert "cat_hivern_2027" in resum["competicions_a"]
    assert "cat_estiu_2027" in resum["competicions_a"]
    assert "espanya_2027" in resum["competicions_b"]
    assert len(resum["avisos_espaiat"]) == 0  # Espaiat correcte

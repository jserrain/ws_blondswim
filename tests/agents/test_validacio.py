"""
Tests per a les validacions de macrocicle i microcicle.

Valida les funcions de validació de descàrrega periòdica, progressió de volum (ACWR),
coherència amb taper i orquestració completa amb casos sintètics raonables.
"""

from blondswim.agents.validacio import (
    calcular_volums_setmanals_historial,
    validar_coherencia_taper,
    validar_descarrega_periodica,
    validar_pla_complet,
    validar_progressio_volum,
)
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Mesocicle, Microcicle


def test_validar_descarrega_periodica_master_sense_avis():
    """Nedador master amb 3 setmanes de càrrega seguides → sense avís (límit és 3)."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="21-27/09/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=2,
            dates="28/09-04/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=16000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=3,
            dates="05-11/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15500,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=4,
            dates="12-18/10/2026",
            mesocicle_id="meso1",
            tipus_base="descarrega",
            volum_objectiu=12000,
            dies_qualitat=False,
            test_css=False,
        ),
    ]

    avisos = validar_descarrega_periodica(microcicles, categoria="master")

    # 3 setmanes de càrrega + 1 descàrrega: dins del límit
    assert len(avisos) == 0


def test_validar_descarrega_periodica_master_amb_avis():
    """Nedador master amb 4 setmanes de càrrega seguides → avís (límit és 3)."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="21-27/09/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=2,
            dates="28/09-04/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=16000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=3,
            dates="05-11/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15500,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=4,
            dates="12-18/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=16500,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=5,
            dates="19-25/10/2026",
            mesocicle_id="meso1",
            tipus_base="descarrega",
            volum_objectiu=12000,
            dies_qualitat=False,
            test_css=False,
        ),
    ]

    avisos = validar_descarrega_periodica(microcicles, categoria="master")

    # 4 setmanes de càrrega consecutives: supera el límit de 3
    assert len(avisos) == 1
    assert avisos[0]["setmana_inici"] == 1
    assert avisos[0]["setmana_fi"] == 4
    assert avisos[0]["setmanes_consecutives"] == 4
    assert avisos[0]["limit_recomanat"] == 3
    assert "sobreentrenament" in avisos[0]["missatge"]


def test_validar_descarrega_periodica_junior_amb_avis():
    """Nedador junior amb 3 setmanes de càrrega seguides → avís (límit és 2)."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="21-27/09/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=13000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=2,
            dates="28/09-04/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=14000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=3,
            dates="05-11/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=13500,
            dies_qualitat=True,
            test_css=False,
        ),
    ]

    avisos = validar_descarrega_periodica(microcicles, categoria="junior")

    # 3 setmanes de càrrega: supera el límit de 2 per a junior
    assert len(avisos) == 1
    assert avisos[0]["setmanes_consecutives"] == 3
    assert avisos[0]["limit_recomanat"] == 2
    assert avisos[0]["categoria"] == "junior"


def test_validar_progressio_volum_estable():
    """Seqüència de volums estable → sense avisos."""
    microcicles = [
        Microcicle(
            setmana=i,
            dates=f"{i}-{i}/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        )
        for i in range(1, 8)
    ]

    avisos = validar_progressio_volum(microcicles, finestra_setmanes=4)

    # Volum constant: ACWR = 1.0, dins del rang 0.8-1.3
    assert len(avisos) == 0


def test_validar_progressio_volum_salt_risc():
    """Salt puntual amb ratio ~1.6 → avís carrega_risc_lesio."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="1/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=14000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=2,
            dates="2/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=14500,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=3,
            dates="3/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=4,
            dates="4/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=5,
            dates="5/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=23000,  # Salt brusc: ~1.58x la mitjana
            dies_qualitat=True,
            test_css=False,
        ),
    ]

    avisos = validar_progressio_volum(microcicles, finestra_setmanes=4, ratio_risc=1.5)

    # Setmana 5: ACWR ~1.58 (23000 / mitjana(14000,14500,15000,15000) ≈ 1.58)
    assert len(avisos) == 1
    assert avisos[0]["setmana"] == 5
    assert avisos[0]["tipus_avis"] == "carrega_risc_lesio"
    assert avisos[0]["ratio_acwr"] > 1.5
    assert "Risc elevat de lesió" in avisos[0]["missatge"]


def test_validar_progressio_volum_represa_normal():
    """Represa normal després de descàrrega amb ratio dins 0.8-1.3 → sense avís."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="1/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=2,
            dates="2/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15500,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=3,
            dates="3/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=16000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=4,
            dates="4/10/2026",
            mesocicle_id="meso1",
            tipus_base="descarrega",
            volum_objectiu=12000,  # Descàrrega
            dies_qualitat=False,
            test_css=False,
        ),
        Microcicle(
            setmana=5,
            dates="5/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,  # Represa normal
            dies_qualitat=True,
            test_css=False,
        ),
    ]

    avisos = validar_progressio_volum(microcicles, finestra_setmanes=4)

    # Setmana 5: ACWR = 15000 / mitjana(15500,16000,12000,15000) ≈ 1.03
    # Dins del rang 0.8-1.3, sense avís
    assert len(avisos) == 0


def test_validar_coherencia_taper_amb_avis():
    """Microcicle de càrrega alta dins finestra de taper → avís."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="02-08/01/2027",
            mesocicle_id="meso5",
            tipus_base="carrega",
            volum_objectiu=16000,
            dies_qualitat=True,
            test_css=False,
            competicio_test_oficial="cat_hivern_2027",
        ),
    ]

    pla_taper = [
        {
            "competicio_id": "cat_hivern_2027",
            "competicio_nom": "Catalunya Hivern",
            "classe": "A",
            "data_inici": "2027-01-16",
            "dies_taper_pre": 14,
            "tipus_taper": "progressiu",
            "dies_recuperacio_post": 14,
            "tipus_recuperacio": "activa_llarga",
            "retaper": False,
        },
    ]

    avisos = validar_coherencia_taper(microcicles, pla_taper)

    # Microcicle de càrrega amb competició que té taper de 14 dies
    assert len(avisos) == 1
    assert avisos[0]["setmana"] == 1
    assert avisos[0]["competicio_id"] == "cat_hivern_2027"
    assert avisos[0]["tipus_microcicle"] == "carrega"
    assert "taper" in avisos[0]["missatge"].lower()


def test_validar_pla_complet_integracio():
    """Cas d'integració amb dades sintètiques raonables."""
    # Crear un macrocicle sintètic amb volums realistes
    microcicles = [
        Microcicle(
            setmana=i,
            dates=f"{i}/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega" if i % 4 != 0 else "descarrega",
            volum_objectiu=15000 if i % 4 != 0 else 12000,
            dies_qualitat=True,
            test_css=False,
        )
        for i in range(1, 13)
    ]

    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1-12",
        dates="21/09-13/12/2026",
        fase_objectiu="Base aeròbica",
        metodologia_dominant="Volum extensiu",
        volum_min=12000,
        volum_max=16000,
        volum_mitja_previst=14500,
        microcicles=microcicles,
    )

    macrocicle = Macrocicle(
        nom="Macrocicle 2026-27",
        temporada="Hivern",
        mesocicles=[mesocicle],
    )

    pla_taper = []
    avisos_pics_a = []

    avisos = validar_pla_complet(
        macrocicle,
        categoria="absolut",
        pla_taper=pla_taper,
        avisos_pics_a=avisos_pics_a,
    )

    # Ha d'executar-se sense error i retornar una llista (pot estar buida o amb avisos)
    assert isinstance(avisos, list)
    # Tots els avisos han de tenir el camp tipus_validacio
    for avis in avisos:
        assert "tipus_validacio" in avis
        assert avis["tipus_validacio"] in [
            "descarrega_periodica",
            "progressio_volum",
            "coherencia_taper",
            "espaiat_pics_a",
        ]


def test_validar_pla_complet_amb_avisos_pics_a():
    """validar_pla_complet incorpora avisos de pics A."""
    microcicles = [
        Microcicle(
            setmana=1,
            dates="1/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        ),
    ]

    mesocicle = Mesocicle(
        id="meso1",
        nom="Mesocicle 1",
        setmanes="1",
        dates="1/10/2026",
        fase_objectiu="Base",
        metodologia_dominant="Volum",
        volum_min=15000,
        volum_max=15000,
        volum_mitja_previst=15000,
        microcicles=microcicles,
    )

    macrocicle = Macrocicle(
        nom="Macrocicle test",
        mesocicles=[mesocicle],
    )

    avisos_pics_a = [
        {
            "comp_a_id": "comp_a",
            "comp_b_id": "comp_b",
            "setmanes_separacio": 3.0,
            "tipus_avis": "separacio_insuficient",
            "missatge": "Test avís pics A",
        }
    ]

    avisos = validar_pla_complet(
        macrocicle,
        categoria="absolut",
        pla_taper=[],
        avisos_pics_a=avisos_pics_a,
    )

    # Ha d'incloure l'avís de pics A amb el camp tipus_validacio afegit
    avisos_pics = [a for a in avisos if a.get("tipus_validacio") == "espaiat_pics_a"]
    assert len(avisos_pics) == 1
    assert avisos_pics[0]["missatge"] == "Test avís pics A"


def test_validar_progressio_volum_amb_historial_previ_complet():
    """Amb historial previ complet, microcicles[0] pot generar avís."""
    # Historial previ: 4 setmanes amb volum estable de 14000m
    historial_previ = [14000, 14000, 14000, 14000]
    
    # Primera setmana del macrocicle amb salt brusc a 22000m
    microcicles = [
        Microcicle(
            setmana=1,
            dates="1/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=22000,  # Salt de ~1.57x la mitjana
            dies_qualitat=True,
            test_css=False,
        ),
    ]
    
    avisos = validar_progressio_volum(
        microcicles,
        finestra_setmanes=4,
        ratio_risc=1.5,
        historial_previ=historial_previ,
    )
    
    # Ha de generar avís per la setmana 1 (ACWR ~1.57)
    assert len(avisos) == 1
    assert avisos[0]["setmana"] == 1
    assert avisos[0]["tipus_avis"] == "carrega_risc_lesio"
    assert avisos[0]["ratio_acwr"] > 1.5


def test_validar_progressio_volum_historial_previ_insuficient():
    """Amb historial previ insuficient, comportament igual que sense historial."""
    # Historial previ: només 2 setmanes (insuficient per finestra de 4)
    historial_previ = [14000, 14000]
    
    microcicles = [
        Microcicle(
            setmana=1,
            dates="1/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=22000,
            dies_qualitat=True,
            test_css=False,
        ),
        Microcicle(
            setmana=2,
            dates="2/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=23000,
            dies_qualitat=True,
            test_css=False,
        ),
    ]
    
    avisos = validar_progressio_volum(
        microcicles,
        finestra_setmanes=4,
        historial_previ=historial_previ,
    )
    
    # No ha de generar avisos (finestra incompleta per les primeres setmanes)
    assert len(avisos) == 0


def test_validar_progressio_volum_sense_historial_previ_comportament_identic():
    """Sense historial_previ, comportament idèntic amb None explícit o sense paràmetre."""
    microcicles = [
        Microcicle(
            setmana=i,
            dates=f"{i}/10/2026",
            mesocicle_id="meso1",
            tipus_base="carrega",
            volum_objectiu=15000,
            dies_qualitat=True,
            test_css=False,
        )
        for i in range(1, 8)
    ]
    
    # Cridar sense especificar historial_previ
    avisos_sense = validar_progressio_volum(microcicles, finestra_setmanes=4)
    
    # Cridar amb historial_previ=None explícit
    avisos_amb_none = validar_progressio_volum(
        microcicles, finestra_setmanes=4, historial_previ=None
    )
    
    # Han de ser idèntics
    assert avisos_sense == avisos_amb_none
    assert len(avisos_sense) == 0  # Volum constant, sense avisos


def test_calcular_volums_setmanals_historial():
    """Agrupa sessions per setmana ISO i suma volums correctament."""
    # Crear sessions en dues setmanes ISO diferents
    # Setmana ISO 38 de 2026: 14-20 setembre (dilluns a diumenge)
    # Setmana ISO 39 de 2026: 21-27 setembre
    sessions = [
        SessioRealitzada(
            data="2026-09-14",  # Dilluns, setmana 38
            setmana=3,
            series=[],
            volum_total_m=2500,
            temps_total_min=60.0,
        ),
        SessioRealitzada(
            data="2026-09-16",  # Dimecres, setmana 38
            setmana=3,
            series=[],
            volum_total_m=3000,
            temps_total_min=65.0,
        ),
        SessioRealitzada(
            data="2026-09-21",  # Dilluns, setmana 39
            setmana=4,
            series=[],
            volum_total_m=2800,
            temps_total_min=62.0,
        ),
        SessioRealitzada(
            data="2026-09-23",  # Dimecres, setmana 39
            setmana=4,
            series=[],
            volum_total_m=0,  # Dia especial sense volum
            temps_total_min=0.0,
        ),
        SessioRealitzada(
            data="2026-09-25",  # Divendres, setmana 39
            setmana=4,
            series=[],
            volum_total_m=3200,
            temps_total_min=68.0,
        ),
    ]
    
    volums = calcular_volums_setmanals_historial(sessions)
    
    # Ha de retornar 2 setmanes en ordre cronològic
    assert len(volums) == 2
    # Setmana 38: 2500 + 3000 = 5500
    assert volums[0] == 5500
    # Setmana 39: 2800 + 0 + 3200 = 6000
    assert volums[1] == 6000

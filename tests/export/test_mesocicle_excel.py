"""Tests per a l'exportació de mesocicles a Excel."""


import openpyxl
import pytest

from blondswim.export.mesocicle_excel import exportar_mesocicle_excel
from blondswim.models.macrocicle import Mesocicle, Microcicle
from blondswim.models.nedador import Nedador, RitmesCSS
from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio


@pytest.fixture
def nedador_test() -> Nedador:
    """Nedador de test."""
    return Nedador(
        id="test",
        nom="Test Nedador",
        edat=25,
        categoria="absolut",
        proves_objectiu=["200m lliure"],
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
def mesocicle_test() -> Mesocicle:
    """Mesocicle de test amb 2 setmanes."""
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
    return Mesocicle(
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


@pytest.fixture
def estructura_test() -> EstructuraSessio:
    """Estructura de sessió de test amb 5 parts."""
    return EstructuraSessio(
        parts=[
            PartSessio(
                nom="Escalfament",
                percentatge_carrega=10,
                percentatge_qualitat=10,
                percentatge_descarrega=15,
                contingut="400 N suau Recuperació",
            ),
            PartSessio(
                nom="Tècnica",
                percentatge_carrega=20,
                percentatge_qualitat=15,
                percentatge_descarrega=15,
                contingut="8x50 Tècnica braçada",
            ),
            PartSessio(
                nom="Aeròbic",
                percentatge_carrega=50,
                percentatge_qualitat=30,
                percentatge_descarrega=20,
                contingut="10x200 A2 @ 3:00",
            ),
            PartSessio(
                nom="Específic",
                percentatge_carrega=10,
                percentatge_qualitat=35,
                percentatge_descarrega=40,
                contingut="4x100 A3 @ 1:45",
            ),
            PartSessio(
                nom="Tornada a la calma",
                percentatge_carrega=10,
                percentatge_qualitat=10,
                percentatge_descarrega=10,
                contingut="200 N suau",
            ),
        ]
    )


def test_exportar_mesocicle_amb_2_setmanes_1_sessio_cada_una(
    nedador_test, mesocicle_test, estructura_test, tmp_path
):
    """Verifica que genera un fitxer amb 2 sessions (1 per setmana)."""
    # Crear sessions de test
    sessio_1 = Sessio(
        id="test_1_dilluns",
        microcicle_setmana=1,
        dia="dilluns",
        tipus_sessio="carrega",
        volum_total=3000,
        es_dia_opcional=False,
        estructura=estructura_test,
    )
    sessio_2 = Sessio(
        id="test_2_dimarts",
        microcicle_setmana=2,
        dia="dimarts",
        tipus_sessio="qualitat",
        volum_total=2800,
        es_dia_opcional=False,
        estructura=estructura_test,
    )

    resultats = {
        1: [sessio_1],
        2: [sessio_2],
    }

    # Exportar
    output_path = tmp_path / "mesocicle_test.xlsx"
    fitxer_creat = exportar_mesocicle_excel(
        nedador=nedador_test,
        mesocicle=mesocicle_test,
        resultats=resultats,
        output_path=output_path,
    )

    # Verificar que el fitxer existeix
    assert fitxer_creat.exists()
    assert fitxer_creat == output_path

    # Llegir fitxer i verificar contingut
    wb = openpyxl.load_workbook(fitxer_creat)

    # Verificar que només hi ha 1 pestanya
    assert len(wb.sheetnames) == 1

    ws = wb.active

    # Verificar nombre de files (1 capçalera + 2 sessions)
    assert ws.max_row == 3

    # Verificar que les dades de les sessions són correctes
    # Fila 2: sessio_1 (setmana 1, dilluns)
    assert ws.cell(row=2, column=1).value == 1
    assert ws.cell(row=2, column=2).value == "Dilluns"
    assert ws.cell(row=2, column=3).value == "Carrega"
    assert ws.cell(row=2, column=4).value == 3000
    assert ws.cell(row=2, column=5).value == "No"

    # Fila 3: sessio_2 (setmana 2, dimarts)
    assert ws.cell(row=3, column=1).value == 2
    assert ws.cell(row=3, column=2).value == "Dimarts"
    assert ws.cell(row=3, column=3).value == "Qualitat"
    assert ws.cell(row=3, column=4).value == 2800
    assert ws.cell(row=3, column=5).value == "No"


def test_exportar_mesocicle_capçaleres_correctes(
    nedador_test, mesocicle_test, estructura_test, tmp_path
):
    """Verifica que les capçaleres són les esperades."""
    # Crear una sessió de test
    sessio = Sessio(
        id="test_1_dilluns",
        microcicle_setmana=1,
        dia="dilluns",
        tipus_sessio="carrega",
        volum_total=3000,
        es_dia_opcional=False,
        estructura=estructura_test,
    )

    resultats = {1: [sessio]}

    # Exportar
    output_path = tmp_path / "mesocicle_capçaleres.xlsx"
    fitxer_creat = exportar_mesocicle_excel(
        nedador=nedador_test,
        mesocicle=mesocicle_test,
        resultats=resultats,
        output_path=output_path,
    )

    # Llegir fitxer
    wb = openpyxl.load_workbook(fitxer_creat)
    ws = wb.active

    # Verificar capçaleres (fila 1)
    capçaleres_esperades = [
        "Setmana",
        "Dia",
        "Tipus sessió",
        "Volum total",
        "Dia opcional",
        "Escalfament",
        "Tècnica",
        "Aeròbic",
        "Específic",
        "Tornada a la calma",
    ]

    for col_idx, capçalera_esperada in enumerate(capçaleres_esperades, start=1):
        valor_cel = ws.cell(row=1, column=col_idx).value
        assert valor_cel == capçalera_esperada

    # Verificar que les capçaleres estan en negreta
    for col_idx in range(1, len(capçaleres_esperades) + 1):
        cell = ws.cell(row=1, column=col_idx)
        assert cell.font.bold is True


def test_exportar_mesocicle_resultats_buit(nedador_test, mesocicle_test, tmp_path):
    """Verifica que amb resultats buit genera un fitxer amb només capçaleres."""
    resultats = {}

    # Exportar
    output_path = tmp_path / "mesocicle_buit.xlsx"
    fitxer_creat = exportar_mesocicle_excel(
        nedador=nedador_test,
        mesocicle=mesocicle_test,
        resultats=resultats,
        output_path=output_path,
    )

    # Verificar que el fitxer existeix
    assert fitxer_creat.exists()

    # Llegir fitxer
    wb = openpyxl.load_workbook(fitxer_creat)
    ws = wb.active

    # Verificar que només hi ha 1 fila (capçaleres)
    assert ws.max_row == 1

    # Verificar que les capçaleres bàsiques existeixen
    assert ws.cell(row=1, column=1).value == "Setmana"
    assert ws.cell(row=1, column=2).value == "Dia"
    assert ws.cell(row=1, column=3).value == "Tipus sessió"
    assert ws.cell(row=1, column=4).value == "Volum total"
    assert ws.cell(row=1, column=5).value == "Dia opcional"

    # Com que no hi ha sessions, no hi ha noms de parts
    # (les columnes 6+ no existeixen o estan buides)
    assert ws.max_column == 5

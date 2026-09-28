"""Export mesocicle data to Excel format."""

from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from blondswim.models.macrocicle import Mesocicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Sessio


def exportar_mesocicle_excel(
    nedador: Nedador,
    mesocicle: Mesocicle,
    resultats: dict[int, list[Sessio]],
    output_path: Path,
) -> Path:
    """
    Exporta totes les sessions d'un mesocicle a un ÚNIC full Excel.

    Columnes: Setmana, Dia, Tipus sessió, Volum total, Dia opcional,
    seguides d'una columna per cada part de l'estructura de sessió
    (el nom de cada PartSessio.nom com a capçalera, amb el seu
    contingut com a valor).

    Files: totes les sessions de totes les setmanes del mesocicle,
    ordenades per setmana ascendent i, dins de cada setmana, per dia
    de la setmana (dilluns...diumenge). Les setmanes que no apareguin
    a `resultats` (per exemple perquè van fallar a generar_mesocicle)
    simplement no generen files.

    Fa servir la mateixa llibreria per escriure xlsx que ja s'utilitza
    a ingestion/xlsx_to_json.py per llegir'n, per coherència amb la
    resta del projecte.

    Crea el directori pare d'output_path si no existeix.
    Retorna el Path del fitxer escrit.

    Args:
        nedador: Nedador per al qual s'ha generat el mesocicle
        mesocicle: Mesocicle amb la informació estructural
        resultats: Diccionari {setmana: list[Sessio]} amb les sessions generades
        output_path: Path on escriure el fitxer Excel

    Returns:
        Path del fitxer Excel creat
    """
    # Crear directori si no existeix
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Crear workbook i worksheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{mesocicle.nom}"

    # Ordre dels dies de la setmana per ordenar sessions
    dies_ordre = {
        "dilluns": 1,
        "dimarts": 2,
        "dimecres": 3,
        "dijous": 4,
        "divendres": 5,
        "dissabte": 6,
        "diumenge": 7,
    }

    # Recollir totes les sessions i ordenar-les
    totes_sessions = []
    for setmana, sessions in resultats.items():
        for sessio in sessions:
            totes_sessions.append(sessio)

    # Ordenar per setmana i després per dia
    totes_sessions.sort(key=lambda s: (s.microcicle_setmana, dies_ordre.get(s.dia, 99)))

    # Determinar noms de les parts (assumim que totes les sessions tenen la mateixa estructura)
    noms_parts = []
    if totes_sessions:
        noms_parts = [part.nom for part in totes_sessions[0].estructura.parts]

    # Escriure capçaleres
    capçaleres = ["Setmana", "Dia", "Tipus sessió", "Volum total", "Dia opcional"] + noms_parts
    for col_idx, capçalera in enumerate(capçaleres, start=1):
        cell = ws.cell(row=1, column=col_idx, value=capçalera)
        cell.font = Font(bold=True)

    # Escriure dades de sessions
    for row_idx, sessio in enumerate(totes_sessions, start=2):
        ws.cell(row=row_idx, column=1, value=sessio.microcicle_setmana)
        ws.cell(row=row_idx, column=2, value=sessio.dia.capitalize())
        ws.cell(row=row_idx, column=3, value=sessio.tipus_sessio.capitalize())
        ws.cell(row=row_idx, column=4, value=sessio.volum_total)
        ws.cell(row=row_idx, column=5, value="Sí" if sessio.es_dia_opcional else "No")

        # Escriure contingut de cada part
        for col_idx, part in enumerate(sessio.estructura.parts, start=6):
            contingut = part.contingut if part.contingut else ""
            ws.cell(row=row_idx, column=col_idx, value=contingut)

    # Ajustar amplada de columnes
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)  # Màxim 50 per evitar columnes massa amples
        ws.column_dimensions[column].width = adjusted_width

    # Guardar fitxer
    wb.save(output_path)

    return output_path

"""Export mesocicle data to Excel format."""

from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from blondswim.agents.pla_setmanal import ETIQUETA_ROL
from blondswim.models.macrocicle import Mesocicle, Microcicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Sessio
from blondswim.utils.dates import parsejar_rang_dates

_DIES_ORDRE = {
    "dilluns": 0,
    "dimarts": 1,
    "dimecres": 2,
    "dijous": 3,
    "divendres": 4,
    "dissabte": 5,
    "diumenge": 6,
}

_MESOS_CA = {
    1: "Gener", 2: "Febrer", 3: "Març", 4: "Abril", 5: "Maig", 6: "Juny",
    7: "Juliol", 8: "Agost", 9: "Setembre", 10: "Octubre",
    11: "Novembre", 12: "Desembre",
}

# Rutina d'espatlla fora de l'aigua (opcional, ~15 min): força-resistència de la
# part posterior de l'espatlla i estabilitzadors de l'escàpula (factor de risc
# amb evidència, vegeu fase3.md — Fase H).
RUTINA_ESPATLLA: list[tuple[str, str]] = [
    ("3x15", "Rotació externa amb goma elàstica, colze a 90° enganxat al cos (cada braç)"),
    ("3x15", "Obertures amb goma elàstica (band pull-apart), braços estirats"),
    ("3x10", "Y-T-W estirat de bocaterrosa, sense pes o 0,5-1 kg"),
    ("3x12", "Flexions escapulars (serrat anterior), sense doblegar els colzes"),
]

_COLUMNES = [
    "Dia", "Treball", "Execució", "Descans", "Material",
    "Intensitat", "Objectiu", "Temps (min)", "Volum (m)",
]


def _etiqueta_mes(data_inici: date, data_fi: date) -> str:
    """Nom del mes, o 'Mes1/Mes2' si la setmana creua de mes."""
    if data_inici.month == data_fi.month:
        return _MESOS_CA[data_inici.month]
    return f"{_MESOS_CA[data_inici.month]}/{_MESOS_CA[data_fi.month]}"


def _escriure_setmana(
    ws,
    row_idx: int,
    mesocicle: Mesocicle,
    microcicle: Microcicle | None,
    setmana: int,
    sessions: list[Sessio],
    nedador: Nedador | None = None,
) -> int:
    """
    Escriu una setmana (capçalera + dies + exercicis + totals) a partir de
    la fila `row_idx`. Retorna la fila següent (inclosa la línia en blanc).
    Si no hi ha sessions vàlides, no escriu res i retorna `row_idx`.
    """
    sessions_setmana = [s for s in sessions if s.dia in _DIES_ORDRE]
    sessions_setmana.sort(key=lambda s: _DIES_ORDRE[s.dia])
    if not sessions_setmana:
        return row_idx

    data_inici = None
    data_fi = None
    if microcicle:
        try:
            data_inici, data_fi = parsejar_rang_dates(microcicle.dates)
        except ValueError:
            data_inici = None

    fase = mesocicle.tipus or mesocicle.fase_objectiu
    if data_inici:
        setmana_iso = data_inici.isocalendar()[1]
        mes_label = _etiqueta_mes(data_inici, data_fi)
        capçalera_setmana = (
            f"{mes_label} {data_inici.year} — Setmana {setmana_iso} "
            f"({microcicle.dates}) — {mesocicle.nom}, Fase {fase}"
        )
    else:
        capçalera_setmana = f"Setmana {setmana} — {mesocicle.nom}, Fase {fase}"

    cell = ws.cell(row=row_idx, column=1, value=capçalera_setmana)
    cell.font = Font(bold=True, size=12)
    row_idx += 1

    sessions_des_de = microcicle.sessions_des_de if microcicle else None

    # Rutina d'espatlla en un dia de descans (si el nedador en té i cau dins la setmana).
    dia_rutina = nedador.rutina_espatlla_dia if nedador else None
    rutina_pendent = (
        data_inici is not None
        and dia_rutina in _DIES_ORDRE
        and not any(s.dia == dia_rutina for s in sessions_setmana)
        and not (microcicle and microcicle.dia_competicio == dia_rutina)
    )
    if rutina_pendent and sessions_des_de is not None:
        rutina_pendent = data_inici + timedelta(days=_DIES_ORDRE[dia_rutina]) >= sessions_des_de

    for sessio in sessions_setmana:
        if rutina_pendent and _DIES_ORDRE[sessio.dia] > _DIES_ORDRE[dia_rutina]:
            row_idx = _escriure_rutina_espatlla(ws, row_idx, data_inici, dia_rutina)
            rutina_pendent = False

        if data_inici:
            data_sessio = data_inici + timedelta(days=_DIES_ORDRE[sessio.dia])
            if sessions_des_de is not None and data_sessio < sessions_des_de:
                continue
            capçalera_dia = f"{sessio.dia.capitalize()} {data_sessio.day}"
        else:
            capçalera_dia = sessio.dia.capitalize()
        # Etiqueta del rol només per a les sessions de la plantilla setmanal
        # (porten context a `notes`); la lògica antiga no canvia de format.
        if sessio.rol in ETIQUETA_ROL and sessio.notes:
            capçalera_dia += f" — {ETIQUETA_ROL[sessio.rol]}"

        cell = ws.cell(row=row_idx, column=1, value=capçalera_dia)
        cell.font = Font(bold=True)
        row_idx += 1

        for col_idx, nom_col in enumerate(_COLUMNES, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=nom_col)
            c.font = Font(italic=True)
        row_idx += 1

        volum_total_dia = 0
        for part in sessio.estructura.parts:
            for exercici in part.exercicis:
                treball = (
                    str(exercici.distancia_m)
                    if exercici.series == 1
                    else f"{exercici.series}x{exercici.distancia_m}"
                )
                ws.cell(row=row_idx, column=2, value=treball)
                ws.cell(row=row_idx, column=3, value=exercici.execucio)
                ws.cell(row=row_idx, column=4, value=exercici.descans)
                ws.cell(row=row_idx, column=5, value=exercici.material)
                ws.cell(row=row_idx, column=6, value=exercici.intensitat)
                ws.cell(row=row_idx, column=7, value=exercici.objectiu)
                ws.cell(row=row_idx, column=9, value=exercici.volum_m)
                volum_total_dia += exercici.volum_m
                row_idx += 1

        ws.cell(row=row_idx, column=2, value="Total").font = Font(bold=True)
        ws.cell(row=row_idx, column=9, value=volum_total_dia).font = Font(bold=True)
        row_idx += 1

    if rutina_pendent:
        row_idx = _escriure_rutina_espatlla(ws, row_idx, data_inici, dia_rutina)

    return row_idx + 1  # línia en blanc entre setmanes


def _escriure_rutina_espatlla(ws, row_idx: int, data_inici: date, dia: str) -> int:
    """Escriu el bloc de la rutina d'espatlla (dia de descans). Retorna la fila següent."""
    data = data_inici + timedelta(days=_DIES_ORDRE[dia])
    cell = ws.cell(
        row=row_idx,
        column=1,
        value=(
            f"{dia.capitalize()} {data.day} — Descans a l'aigua. "
            "Rutina d'espatlla (opcional, 15 min, fora de l'aigua)"
        ),
    )
    cell.font = Font(bold=True)
    row_idx += 1
    for treball, execucio in RUTINA_ESPATLLA:
        ws.cell(row=row_idx, column=2, value=treball)
        ws.cell(row=row_idx, column=3, value=execucio)
        row_idx += 1
    return row_idx


def _ajustar_amplades(ws) -> None:
    """Ajusta l'amplada de cada columna al contingut (màxim 50)."""
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            with suppress(TypeError, AttributeError):
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column].width = min(max_length + 2, 50)


def exportar_mesocicle_excel(
    nedador: Nedador,
    mesocicle: Mesocicle,
    resultats: dict[int, list[Sessio]],
    output_path: Path,
) -> Path:
    """
    Exporta totes les sessions d'un mesocicle a un ÚNIC full Excel, amb
    una fila per Exercici.

    Estructura per setmana (vegeu _escriure_setmana):
    - Capçalera de setmana en negreta: "<Mes(os)> <Any> — Setmana <ISO>
      (<dates>) — <mesocicle.nom>, Fase <tipus>" (setmana ISO de l'any).
    - Per cada dia amb sessió (dilluns..diumenge): capçalera "<Dia> <núm>",
      capçaleres de columna en cursiva, una fila per Exercici i fila "Total"
      amb el volum del dia. "Temps (min)" en blanc (Etapa 3b pendent).

    Les setmanes que no apareguin a `resultats` no generen files.

    Args:
        nedador: Nedador per al qual s'ha generat el mesocicle
        mesocicle: Mesocicle amb la informació estructural (microcicles inclosos)
        resultats: Diccionari {setmana: list[Sessio]} amb les sessions generades
        output_path: Path on escriure el fitxer Excel

    Returns:
        Path del fitxer Excel creat
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = mesocicle.nom[:31]

    microcicles_per_setmana = {m.setmana: m for m in mesocicle.microcicles}

    row_idx = 1
    for setmana in sorted(resultats.keys()):
        row_idx = _escriure_setmana(
            ws,
            row_idx,
            mesocicle,
            microcicles_per_setmana.get(setmana),
            setmana,
            resultats[setmana],
            nedador,
        )

    _ajustar_amplades(ws)
    wb.save(output_path)

    return output_path


def exportar_setmana_excel(
    nedador: Nedador,
    mesocicle: Mesocicle,
    microcicle: Microcicle,
    sessions: list[Sessio],
    output_path: Path,
) -> Path:
    """
    Exporta UNA sola setmana (G6): el full que el nedador fa servir a la
    piscina. Mateix format que exportar_mesocicle_excel(), una pestanya
    anomenada "Setmana <ISO>".

    Args:
        nedador: Nedador
        mesocicle: Mesocicle al qual pertany la setmana
        microcicle: Microcicle de la setmana
        sessions: Sessions generades per a la setmana
        output_path: Path on escriure el fitxer Excel

    Returns:
        Path del fitxer Excel creat
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Setmana {microcicle.setmana}"

    _escriure_setmana(ws, 1, mesocicle, microcicle, microcicle.setmana, sessions, nedador)

    _ajustar_amplades(ws)
    wb.save(output_path)

    return output_path

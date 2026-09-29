"""Export mesocicle data to Excel format."""

import re
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from blondswim.models.macrocicle import Mesocicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Sessio

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

_COLUMNES = [
    "Dia", "Treball", "Execució", "Descans", "Material",
    "Intensitat", "Objectiu", "Temps (min)", "Volum (m)",
]


def _parsejar_rang_dates(dates: str) -> tuple[date, date]:
    """
    Parseja Microcicle.dates en un dels dos formats possibles:
    - "21-27/09/2026" (mateix mes)
    - "28/09-04/10/2026" (creua mes)

    Retorna (data_inici, data_fi). Llança ValueError si el format no
    es reconeix.
    """
    m = re.match(r"^(\d{1,2})-(\d{1,2})/(\d{1,2})/(\d{4})$", dates)
    if m:
        dia_ini, dia_fi, mes, any_ = (int(x) for x in m.groups())
        return date(any_, mes, dia_ini), date(any_, mes, dia_fi)

    m = re.match(r"^(\d{1,2})/(\d{1,2})-(\d{1,2})/(\d{1,2})/(\d{4})$", dates)
    if m:
        dia_ini, mes_ini, dia_fi, mes_fi, any_ = (int(x) for x in m.groups())
        return date(any_, mes_ini, dia_ini), date(any_, mes_fi, dia_fi)

    raise ValueError(f"Format de dates no reconegut: {dates!r}")


def _etiqueta_mes(data_inici: date, data_fi: date) -> str:
    """Nom del mes, o 'Mes1/Mes2' si la setmana creua de mes."""
    if data_inici.month == data_fi.month:
        return _MESOS_CA[data_inici.month]
    return f"{_MESOS_CA[data_inici.month]}/{_MESOS_CA[data_fi.month]}"


def exportar_mesocicle_excel(
    nedador: Nedador,
    mesocicle: Mesocicle,
    resultats: dict[int, list[Sessio]],
    output_path: Path,
) -> Path:
    """
    Exporta totes les sessions d'un mesocicle a un ÚNIC full Excel, amb
    una fila per Exercici (no una columna per PartSessio com abans).

    Estructura per setmana:
    - Fila de capçalera de setmana en negreta: "<Mes(os)> <Any> — Setmana
      <ISO> (<dates>) — <mesocicle.nom>, Fase <tipus>". La setmana és
      sempre la setmana ISO de l'any (isocalendar()[1] de data_inici),
      mai un índex relatiu al mesocicle.
    - Per cada dia amb sessió, en l'ordre dilluns..diumenge:
      - Fila de capçalera de dia en negreta: "<Nom dia> <número de dia>"
        (ex: "Dilluns 28"), sense mes (ja és a la capçalera de setmana).
      - Fila de capçaleres de columna en cursiva: Dia/Treball/Execució/
        Descans/Material/Intensitat/Objectiu/Temps (min)/Volum (m).
      - Una fila per cada Exercici de cada part de
        sessio.estructura.parts, en ordre.
      - Fila "Total" en negreta amb el volum del dia sumat (sempre
        múltiple de 25, ja que ve de sumar Exercici.volum_m).
        "Temps (min)" es deixa en blanc -- calcular-ho requereix el
        ritme real per zona i encara no està implementat (Etapa 3b
        pendent, vegeu fase3.md).

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
        sessions_setmana = [s for s in resultats[setmana] if s.dia in _DIES_ORDRE]
        sessions_setmana.sort(key=lambda s: _DIES_ORDRE[s.dia])
        if not sessions_setmana:
            continue

        microcicle = microcicles_per_setmana.get(setmana)
        data_inici = None
        data_fi = None
        if microcicle:
            try:
                data_inici, data_fi = _parsejar_rang_dates(microcicle.dates)
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

        for sessio in sessions_setmana:
            if data_inici:
                data_sessio = data_inici + timedelta(days=_DIES_ORDRE[sessio.dia])
                capçalera_dia = f"{sessio.dia.capitalize()} {data_sessio.day}"
            else:
                capçalera_dia = sessio.dia.capitalize()

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

        row_idx += 1  # línia en blanc entre setmanes

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            with suppress(TypeError, AttributeError):
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width

    wb.save(output_path)

    return output_path

"""
Ingestió del full de registre setmanal (Fase E+I), creat amb
`export.registre_excel.exportar_registre_setmana` i omplert pel nedador.

Retorna SessioRealitzada (amb RPE i minuts), RegistreSRSS i
RegistreSerieControl. Les files buides (sessions no fetes, dies sense
registre) s'ignoren; una fila a mitges és un error explícit amb el número de
fila, mai s'assumeix cap valor per defecte.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import openpyxl

from blondswim.export.registre_excel import (
    COLUMNES_CONTROL,
    COLUMNES_OBJECTIU,
    COLUMNES_SESSIONS,
    COLUMNES_SRSS,
    FILA_CAPCALERA,
    FULL_CONTROL,
    FULL_OBJECTIU,
    FULL_SESSIONS,
    FULL_SRSS,
    MAX_REPETICIONS_OBJECTIU,
)
from blondswim.models.franja import ETIQUETA_FRANJA, ETIQUETA_MODALITAT
from blondswim.models.historial import SessioRealitzada
from blondswim.models.registre import (
    RegistreSerieControl,
    RegistreSerieObjectiu,
    RegistreSRSS,
)

_FRANJA_PER_ETIQUETA = {v: k for k, v in ETIQUETA_FRANJA.items()}
_MODALITAT_PER_ETIQUETA = {v: k for k, v in ETIQUETA_MODALITAT.items()}


@dataclass
class RegistreSetmana:
    """Dades reals d'una o més setmanes de registre."""

    sessions: list[SessioRealitzada] = field(default_factory=list)
    srss: list[RegistreSRSS] = field(default_factory=list)
    controls: list[RegistreSerieControl] = field(default_factory=list)
    objectius: list[RegistreSerieObjectiu] = field(default_factory=list)

    def afegir(self, altre: "RegistreSetmana") -> None:
        self.sessions.extend(altre.sessions)
        self.srss.extend(altre.srss)
        self.controls.extend(altre.controls)
        self.objectius.extend(altre.objectius)


def _buit(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _data(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor).strip())


def _enter(valor, fila: int, columna: str) -> int:
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError as e:
        raise ValueError(f"Fila {fila}, '{columna}': '{valor}' no és un número") from e
    if numero != int(numero):
        raise ValueError(f"Fila {fila}, '{columna}': '{valor}' ha de ser un enter")
    return int(numero)


def _numero(valor, fila: int, columna: str) -> float:
    try:
        return float(str(valor).replace(",", "."))
    except ValueError as e:
        raise ValueError(f"Fila {fila}, '{columna}': '{valor}' no és un número") from e


_RE_TEMPS = re.compile(r"^\s*(\d+)\s*[:']\s*(\d+(?:[.,]\d+)?)\s*\"?\s*$")


def parsejar_temps_100(valor, fila: int = 0) -> float:
    """
    Temps d'un 100 en segons. Accepta 100.5, "1:40.5", "1'40.5" i, si Excel
    l'ha convertit a hora, 1:40 -> 1 min 40 s (no 1 h 40 min).
    """
    if isinstance(valor, int | float):
        return float(valor)
    if isinstance(valor, timedelta):
        segons = valor.total_seconds()
        return segons / 60 if segons >= 3600 else segons
    if isinstance(valor, time):
        if valor.hour:
            return valor.hour * 60 + valor.minute + valor.second / 60
        return valor.minute * 60 + valor.second + valor.microsecond / 1e6
    text = str(valor).strip()
    coincidencia = _RE_TEMPS.match(text)
    if coincidencia:
        return int(coincidencia.group(1)) * 60 + float(coincidencia.group(2).replace(",", "."))
    try:
        return float(text.replace(",", "."))
    except ValueError as e:
        raise ValueError(f"Fila {fila}: temps '{valor}' no reconegut (exemple: 1:40.5)") from e


def _files(ws, columnes: list[str]):
    capcalera = [c.value for c in ws[FILA_CAPCALERA]][: len(columnes)]
    if capcalera != columnes:
        raise ValueError(
            f"Pestanya '{ws.title}': capçaleres inesperades {capcalera} (esperades {columnes})"
        )
    for fila, valors in enumerate(
        ws.iter_rows(min_row=FILA_CAPCALERA + 1, max_col=len(columnes), values_only=True),
        start=FILA_CAPCALERA + 1,
    ):
        yield fila, dict(zip(columnes, valors, strict=True))


def _sessions(ws) -> list[SessioRealitzada]:
    sessions = []
    for fila, v in _files(ws, COLUMNES_SESSIONS):
        if _buit(v["Data"]) or _buit(v["Dia"]):
            break  # final de la taula (després hi ha la llegenda CR-10)
        omplerts = [c for c in ("Minuts reals", "RPE (0-10)") if not _buit(v[c])]
        if not omplerts:
            continue  # sessió no feta
        if _buit(v["Minuts reals"]):
            raise ValueError(f"Fila {fila}: hi ha RPE però falten els minuts reals")
        modalitat = _MODALITAT_PER_ETIQUETA.get(str(v["Modalitat"]).strip())
        franja = _FRANJA_PER_ETIQUETA.get(str(v["Franja"]).strip())
        if modalitat is None or franja is None:
            raise ValueError(f"Fila {fila}: franja o modalitat desconeguda")
        sessions.append(
            SessioRealitzada(
                data=_data(v["Data"]).isoformat(),
                franja=franja,
                modalitat=modalitat,
                temps_total_min=_numero(v["Minuts reals"], fila, "Minuts reals"),
                rpe_sessio=(
                    None if _buit(v["RPE (0-10)"]) else _enter(v["RPE (0-10)"], fila, "RPE")
                ),
                assoliment=(
                    None
                    if _buit(v["Assoliment (1-5)"])
                    else _enter(v["Assoliment (1-5)"], fila, "Assoliment")
                ),
                volum_total_m=(
                    0 if _buit(v["Metres reals"]) else _enter(v["Metres reals"], fila, "Metres")
                ),
            )
        )
    return sessions


def _srss(ws, nedador_id: str) -> list[RegistreSRSS]:
    registres = []
    items = COLUMNES_SRSS[2:]
    for fila, v in _files(ws, COLUMNES_SRSS):
        if _buit(v["Data"]):
            continue
        valors = [v[c] for c in items]
        if all(_buit(x) for x in valors):
            continue
        if any(_buit(x) for x in valors):
            raise ValueError(f"Fila {fila} de '{FULL_SRSS}': cal omplir els 8 ítems")
        enters = [_enter(x, fila, "SRSS") for x in valors]
        registres.append(
            RegistreSRSS(
                nedador_id=nedador_id,
                data=_data(v["Data"]),
                recuperacio=enters[:4],
                estres=enters[4:],
            )
        )
    return registres


def _controls(ws, nedador_id: str) -> list[RegistreSerieControl]:
    registres = []
    for fila, v in _files(ws, COLUMNES_CONTROL):
        temps = [v[f"100 #{i}"] for i in range(1, 5)]
        if _buit(v["Data"]) or all(_buit(t) for t in temps):
            continue
        bracades = v["Braçades/llargada"]
        registres.append(
            RegistreSerieControl(
                nedador_id=nedador_id,
                data=_data(v["Data"]),
                temps_100=[parsejar_temps_100(t, fila) for t in temps if not _buit(t)],
                bracades_llargada=(
                    None if _buit(bracades) else [_numero(bracades, fila, "Braçades")]
                ),
                rpe=None if _buit(v["RPE (0-10)"]) else _enter(v["RPE (0-10)"], fila, "RPE"),
            )
        )
    return registres


def _objectius(ws, nedador_id: str) -> list[RegistreSerieObjectiu]:
    registres = []
    for fila, v in _files(ws, COLUMNES_OBJECTIU):
        temps = [v[f"#{i}"] for i in range(1, MAX_REPETICIONS_OBJECTIU + 1)]
        if _buit(v["Data"]) or all(_buit(t) for t in temps):
            continue
        registres.append(
            RegistreSerieObjectiu(
                nedador_id=nedador_id,
                data=_data(v["Data"]),
                prova=str(v["Prova"]),
                objectiu=_numero(v["Objectiu (s)"], fila, "Objectiu"),
                temps=[parsejar_temps_100(t, fila) for t in temps if not _buit(t)],
                rpe=None if _buit(v["RPE (0-10)"]) else _enter(v["RPE (0-10)"], fila, "RPE"),
            )
        )
    return registres


def convertir_registre_setmana(path: Path) -> RegistreSetmana:
    """Llegeix un full de registre setmanal omplert."""
    wb = openpyxl.load_workbook(path, data_only=True)
    nedador_id = str(wb[FULL_SESSIONS].cell(row=2, column=1).value)
    return RegistreSetmana(
        sessions=_sessions(wb[FULL_SESSIONS]),
        srss=_srss(wb[FULL_SRSS], nedador_id),
        controls=_controls(wb[FULL_CONTROL], nedador_id),
        # Els fulls anteriors al 06/10 no tenen aquesta pestanya.
        objectius=(
            _objectius(wb[FULL_OBJECTIU], nedador_id) if FULL_OBJECTIU in wb.sheetnames
            else []
        ),
    )


def carregar_registres(directori: Path, patro: str = "registre_*.xlsx") -> RegistreSetmana:
    """Llegeix tots els fulls de registre d'un directori (ordenats per nom)."""
    total = RegistreSetmana()
    for path in sorted(directori.glob(patro)):
        total.afegir(convertir_registre_setmana(path))
    return total

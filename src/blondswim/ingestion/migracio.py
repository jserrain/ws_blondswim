"""Migració de l'estructura antiga (`data/processed/`) a carpetes per nedador.

Estructura antiga (un sol nedador, noms amb sufix):

    data/processed/
    ├── nedador_<nom>.json           (un per nedador; l'id és dins del fitxer)
    ├── calendari.json               (competicions amb classe, del nedador principal)
    ├── historial_<nom>.json
    ├── macrocicle_jep.json          (planificació de referència de l'Excel)
    ├── macrocicle_temporada_26_27.json
    ├── setmana_<nom>_*.xlsx, mesocicle_<nom>_*.xlsx
    ├── registres/registre_<nom>_*.xlsx
    └── log_decisions/<id>_*.json

Estructura nova: vegeu `blondswim.rutes`.

La migració **copia** (no esborra res de `data/processed/`) i **no sobreescriu**
cap fitxer de destinació que ja existeixi: es pot executar diverses vegades.
El catàleg de competicions es fusiona amb el que ja hi hagi.
"""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from blondswim.models.calendari import Competicio, fusionar_cataleg, separar_calendari
from blondswim.models.nedador import Nedador
from blondswim.rutes import RutesNedador, carregar_cataleg, desar_json, ruta_competicions


@dataclass
class ResultatMigracio:
    copiats: list[tuple[Path, Path]] = field(default_factory=list)
    ja_existents: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    nedadors: list[str] = field(default_factory=list)


def _llegir_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _copiar(origen: Path, desti: Path, res: ResultatMigracio, simular: bool) -> None:
    if desti.exists():
        res.ja_existents.append(desti)
        return
    res.copiats.append((origen, desti))
    if not simular:
        desti.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, desti)


def _desar(dades, desti: Path, origen: Path, res: ResultatMigracio, simular: bool) -> None:
    if desti.exists():
        res.ja_existents.append(desti)
        return
    res.copiats.append((origen, desti))
    if not simular:
        desar_json(desti, dades)


def _copiar_xlsx(
    directori: Path,
    prefix: str,
    sufix_antic: str,
    rutes: RutesNedador,
    desti_dir: Path,
    res: ResultatMigracio,
    simular: bool,
) -> None:
    """Copia <prefix>_<sufix_antic>_<resta>.xlsx com a <prefix>_<id>_<resta>.xlsx."""
    if not directori.is_dir():
        return
    patro = f"{prefix}_{sufix_antic}_"
    for origen in sorted(directori.glob(f"{patro}*.xlsx")):
        resta = origen.name[len(patro):]
        _copiar(origen, desti_dir / f"{prefix}_{rutes.nedador_id}_{resta}", res, simular)


def migrar(
    processed: Path,
    arrel: Path,
    propietari_calendari: str = "jep",
    simular: bool = False,
) -> ResultatMigracio:
    """Copia les dades de `processed` (estructura antiga) a `arrel` (nova).

    Args:
        processed: directori antic (`data/processed`).
        arrel: arrel de dades nova (`data`).
        propietari_calendari: id del nedador a qui pertany `calendari.json` i el
            macrocicle generat (fins ara, només el Jep).
        simular: si és True, no escriu res; només retorna què faria.
    """
    res = ResultatMigracio()
    if not processed.is_dir():
        res.avisos.append(f"No existeix {processed}: res a migrar")
        return res

    # 1. Nedadors (nedador_<sufix>.json) i els seus fitxers amb el mateix sufix
    for fitxa in sorted(processed.glob("nedador_*.json")):
        sufix = fitxa.stem[len("nedador_"):]
        try:
            nedador = Nedador(**_llegir_json(fitxa))
            rutes = RutesNedador(nedador.id, arrel)
        except ValueError as e:
            res.avisos.append(f"{fitxa.name}: no es pot migrar ({e})")
            continue
        res.nedadors.append(nedador.id)
        _copiar(fitxa, rutes.nedador, res, simular)

        historial = processed / f"historial_{sufix}.json"
        if historial.is_file():
            _copiar(historial, rutes.historial, res, simular)

        _copiar_xlsx(processed, "setmana", sufix, rutes, rutes.setmanes_dir, res, simular)
        _copiar_xlsx(processed, "mesocicle", sufix, rutes, rutes.setmanes_dir, res, simular)
        _copiar_xlsx(
            processed / "registres", "registre", sufix, rutes, rutes.registres_dir, res, simular
        )

        logs = processed / "log_decisions"
        if logs.is_dir():
            for log in sorted(logs.glob(f"{nedador.id}_*.json")):
                _copiar(log, rutes.log_dir / log.name, res, simular)

    # 2. Calendari antic → catàleg comú + calendari del propietari
    calendari = processed / "calendari.json"
    if calendari.is_file():
        rutes = RutesNedador(propietari_calendari, arrel)
        competicions = [Competicio(**c) for c in _llegir_json(calendari)]
        cataleg, inscripcions = separar_calendari(competicions)

        desti_cataleg = ruta_competicions(arrel)
        fusionat = fusionar_cataleg(carregar_cataleg(arrel), cataleg)
        res.copiats.append((calendari, desti_cataleg))
        if not simular:
            desar_json(desti_cataleg, [c.model_dump() for c in fusionat])

        _desar(
            [i.model_dump() for i in inscripcions], rutes.calendari, calendari, res, simular
        )
        if propietari_calendari not in res.nedadors:
            res.avisos.append(
                f"calendari.json assignat a '{propietari_calendari}', que no té nedador_*.json"
            )

    # 3. Macrocicles del propietari del calendari
    rutes = RutesNedador(propietari_calendari, arrel)
    generat = processed / "macrocicle_temporada_26_27.json"
    if generat.is_file():
        _copiar(generat, rutes.macrocicle, res, simular)
    referencia = processed / "macrocicle_jep.json"
    if referencia.is_file():
        _copiar(referencia, rutes.carpeta / "macrocicle_referencia.json", res, simular)

    return res

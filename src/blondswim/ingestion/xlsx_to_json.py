"""Conversor de fitxers XLSX a JSON validant contra models Pydantic."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from blondswim.models.calendari import Competicio
from blondswim.models.historial import SerieRealitzada, SessioRealitzada
from blondswim.models.macrocicle import Macrocicle
from blondswim.models.nedador import (
    MarquesReferencia,
    Nedador,
    RitmeCursaObjectiu,
    RitmesCSS,
)

logger = logging.getLogger(__name__)


def _slug(nom: str) -> str:
    """
    Generar un slug normalitzat a partir d'un nom.
    
    Args:
        nom: Nom a convertir en slug
        
    Returns:
        Slug normalitzat (minúscules, ASCII, sense espais)
    """
    import unicodedata
    
    nom_normalitzat = str(nom).strip()
    nom_slug = unicodedata.normalize('NFKD', nom_normalitzat.lower())
    nom_slug = nom_slug.encode('ascii', 'ignore').decode('ascii')
    return nom_slug.replace(' ', '-').replace('/', '-').strip('-')


class DataParseError(Exception):
    """Error en parsejar una data."""



class InconsistentDataWarning(Exception):
    """Advertència per dades inconsistents (no fatal)."""



def parsejar_data(valor: Any, num_fila: int) -> tuple[str, str]:
    """
    Parsejar un camp de data que pot ser datetime o text amb rang.

    Args:
        valor: Valor de la cel·la (datetime o str)
        num_fila: Número de fila per a missatges d'error

    Returns:
        Tuple (data_inici, data_fi) en format ISO (YYYY-MM-DD)

    Raises:
        DataParseError: Si el format no és reconegut
    """
    if isinstance(valor, datetime):
        # Data única
        data_iso = valor.strftime("%Y-%m-%d")
        return data_iso, data_iso

    if isinstance(valor, str):
        # Intentar parsejar rang "YYYY-MM-DD a YYYY-MM-DD"
        match = re.match(r"(\d{4}-\d{2}-\d{2})\s+a\s+(\d{4}-\d{2}-\d{2})", valor.strip())
        if match:
            return match.group(1), match.group(2)

        # Intentar parsejar data única en format text
        try:
            data_obj = datetime.strptime(valor.strip(), "%Y-%m-%d")
            data_iso = data_obj.strftime("%Y-%m-%d")
            return data_iso, data_iso
        except ValueError:
            pass

    raise DataParseError(
        f"Fila {num_fila}: format de data no reconegut: {valor!r} (tipus: {type(valor).__name__})"
    )


def llegir_capçaleres(ws: Worksheet, header_row: int = 1) -> dict[str, int]:
    """
    Llegir capçaleres d'una fila específica i retornar un mapa nom -> índex de columna.

    Args:
        ws: Worksheet d'openpyxl
        header_row: Número de fila on es troben les capçaleres (per defecte 1)

    Returns:
        Diccionari {nom_capçalera: índex_columna} (índex basat en 1)
    """
    capçaleres = {}
    for cell in ws[header_row]:
        if cell.value:
            # Normalitzar: minúscules, sense espais interns
            nom_normalitzat = str(cell.value).strip().lower().replace(" ", "")
            capçaleres[nom_normalitzat] = cell.column
    return capçaleres


def reconciliar_piscina_modalitat(
    piscina: Any, modalitat: Any, num_fila: int
) -> tuple[str, bool]:
    """
    Reconciliar els camps piscina i modalitat segons les regles especificades.

    Args:
        piscina: Valor del camp piscina
        modalitat: Valor del camp modalitat
        num_fila: Número de fila per a missatges d'advertència

    Returns:
        Tuple (piscina_final, skip_fila)
        - piscina_final: Valor final de piscina ("25m", "50m" o "aaoo")
        - skip_fila: True si cal saltar aquesta fila per inconsistència

    Raises:
        InconsistentDataWarning: Si hi ha inconsistència (no fatal)
    """
    # Netejar piscina
    piscina_net = str(piscina).strip() if piscina else ""

    # Si piscina està buida després de netejar
    if not piscina_net:
        # El valor real és "aaoo" (de modalitat)
        if modalitat and str(modalitat).strip().lower() == "aaoo":
            return "aaoo", False

        # Si modalitat="piscina" però piscina buida -> inconsistència
        if modalitat and str(modalitat).strip().lower() == "piscina":
            logger.warning(
                f"Fila {num_fila}: modalitat='piscina' però camp piscina buit. Saltant fila."
            )
            return "", True  # Skip aquesta fila

    return piscina_net, False


def convertir_calendari(
    fitxer_entrada: Path, fitxer_sortida: Path
) -> dict[str, Any]:
    """
    Convertir la pestanya "Calendari" a JSON validant contra Competicio.

    Args:
        fitxer_entrada: Path al fitxer XLSX
        fitxer_sortida: Path al fitxer JSON de sortida

    Returns:
        Diccionari amb estadístiques: {
            "total": int,
            "classe_a": int,
            "advertencies": list[str]
        }
    """
    wb = openpyxl.load_workbook(fitxer_entrada, data_only=True)
    ws = wb["Calendari"]

    # Llegir capçaleres
    capçaleres = llegir_capçaleres(ws)
    required = ["id", "class", "data", "competicio", "piscina", "modalitat"]
    for req in required:
        if req not in capçaleres:
            raise ValueError(f"Capçalera requerida '{req}' no trobada al full Calendari")

    competicions = []
    advertencies = []
    classe_a_count = 0

    # Processar files (començant des de la 2, la 1 són capçaleres)
    for num_fila, row in enumerate(ws.iter_rows(min_row=2), start=2):
        # Obtenir valors per nom de capçalera
        id_val = row[capçaleres["id"] - 1].value
        if not id_val:
            continue  # Fila buida

        classe = row[capçaleres["class"] - 1].value
        data_val = row[capçaleres["data"] - 1].value
        competicio = row[capçaleres["competicio"] - 1].value
        piscina = row[capçaleres["piscina"] - 1].value
        modalitat = row[capçaleres["modalitat"] - 1].value

        # Parsejar data
        try:
            data_inici, data_fi = parsejar_data(data_val, num_fila)
        except DataParseError as e:
            raise DataParseError(str(e)) from e

        # Reconciliar piscina/modalitat
        try:
            piscina_final, skip = reconciliar_piscina_modalitat(
                piscina, modalitat, num_fila
            )
            if skip:
                advertencies.append(
                    f"Fila {num_fila}: inconsistència piscina/modalitat, saltada"
                )
                continue
        except InconsistentDataWarning as e:
            advertencies.append(str(e))
            continue

        # Crear i validar model
        try:
            comp = Competicio(
                id=str(id_val),
                nom=str(competicio).strip(),
                classe=str(classe).strip().upper(),
                data_inici=data_inici,
                data_fi=data_fi,
                piscina=piscina_final,
            )
            competicions.append(comp)

            if comp.classe == "A":
                classe_a_count += 1

        except Exception as e:
            raise ValueError(
                f"Fila {num_fila}: error de validació del model Competicio: {e}"
            ) from e

    # Sanity check: zero competicions classe A
    if classe_a_count == 0 and len(competicions) > 0:
        advertencies.append(
            "ADVERTÈNCIA: No s'ha trobat cap competició de classe 'A'. "
            "Això podria indicar un fitxer font corrupte o buit."
        )

    # Escriure JSON
    fitxer_sortida.parent.mkdir(parents=True, exist_ok=True)
    with open(fitxer_sortida, "w", encoding="utf-8") as f:
        json.dump(
            [comp.model_dump() for comp in competicions],
            f,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "total": len(competicions),
        "classe_a": classe_a_count,
        "advertencies": advertencies,
    }


def convertir_macrocicle_jep(
    fitxer_entrada: Path, fitxer_sortida: Path
) -> dict[str, Any]:
    """
    Convertir la pestanya "Macrocicle" a JSON validant contra Macrocicle.

    Args:
        fitxer_entrada: Path al fitxer XLSX
        fitxer_sortida: Path al fitxer JSON de sortida

    Returns:
        Diccionari amb estadístiques: {
            "mesocicles": int,
            "microcicles": int
        }
    """
    wb = openpyxl.load_workbook(fitxer_entrada, data_only=True)
    ws = wb["Macrocicle"]

    # Llegir capçaleres (fila 6 en aquest full específic)
    capçaleres = llegir_capçaleres(ws, header_row=6)
    
    # Capçaleres esperades (normalitzades: minúscules, sense espais)
    required = ["mesocicle", "setmanes", "dates", "fase/objectiu", 
                "metodologiadominant", "volumsetmanal(rang)", 
                "volummitjàprevist(m)"]
    
    # Verificar que existeixen les capçaleres necessàries
    for req in required:
        if req not in capçaleres:
            logger.warning(f"Capçalera '{req}' no trobada. Capçaleres disponibles: {list(capçaleres.keys())}")

    mesocicles = []
    
    # Processar files (començant des de la 7, la 6 són capçaleres)
    files_processades = 0
    for num_fila, row in enumerate(ws.iter_rows(min_row=7), start=7):
        # Obtenir valor de la primera columna (Mesocicle)
        mesocicle_col = capçaleres.get("mesocicle")
        if not mesocicle_col:
            logger.error("No s'ha trobat la columna 'mesocicle'")
            break
            
        mesocicle_nom = row[mesocicle_col - 1].value
        if not mesocicle_nom:
            break  # Aturar a la primera fila buida
        
        files_processades += 1
        
        # Extreure dades de cada columna per nom (normalitzat)
        setmanes = row[capçaleres.get("setmanes", 1) - 1].value
        dates = row[capçaleres.get("dates", 1) - 1].value
        fase_objectiu = row[capçaleres.get("fase/objectiu", 1) - 1].value
        metodologia = row[capçaleres.get("metodologiadominant", 1) - 1].value
        volum_rang = row[capçaleres.get("volumsetmanal(rang)", 1) - 1].value
        volum_mitja = row[capçaleres.get("volummitjàprevist(m)", 1) - 1].value
        tancament = row[capçaleres.get("tancament(control/objectiu)", 999) - 1].value if "tancament(control/objectiu)" in capçaleres else None
        
        # Parsejar volum_rang (ex: "15.500 - 17.000 m" -> min=15500, max=17000)
        # El punt és separador de milers en format català
        volum_min, volum_max = 0, 0
        if volum_rang:
            volum_str = str(volum_rang).strip()
            # Eliminar " m" del final si existeix
            volum_str = volum_str.replace(" m", "").replace("m", "")
            if "-" in volum_str:
                parts = volum_str.split("-")
                # Eliminar punts (separadors de milers) abans de convertir a int
                volum_min = int(parts[0].strip().replace(".", ""))
                volum_max = int(parts[1].strip().replace(".", ""))
        
        # Crear mesocicle
        from blondswim.models.macrocicle import Mesocicle
        nom_normalitzat = str(mesocicle_nom).strip()
        mesocicle_id = _slug(nom_normalitzat)
        
        try:
            mesocicle = Mesocicle(
                id=mesocicle_id,
                nom=nom_normalitzat,
                setmanes=str(setmanes).strip() if setmanes else "",
                dates=str(dates).strip() if dates else "",
                fase_objectiu=str(fase_objectiu).strip() if fase_objectiu else "",
                metodologia_dominant=str(metodologia).strip() if metodologia else "",
                volum_min=volum_min,
                volum_max=volum_max,
                volum_mitja_previst=int(volum_mitja) if volum_mitja else 0,
                tancament=str(tancament).strip() if tancament else None,
                microcicles=[],  # Els microcicles es poden afegir després si cal
            )
            mesocicles.append(mesocicle)
        except Exception as e:
            raise ValueError(
                f"Fila {num_fila}: error de validació del model Mesocicle: {e}"
            ) from e
    
    logger.info(f"Files processades del full Macrocicle: {files_processades}")
    logger.info(f"Mesocicles creats: {len(mesocicles)}")

    # Llegir i vincular microcicles
    microcicles_per_mesocicle = convertir_microcicles(fitxer_entrada, mesocicles)
    
    for mesocicle in mesocicles:
        mesocicle.microcicles = microcicles_per_mesocicle.get(mesocicle.id, [])
    
    total_microcicles = sum(len(m.microcicles) for m in mesocicles)
    logger.info(f"Microcicles vinculats: {total_microcicles}")

    # Crear macrocicle
    macrocicle_data = {
        "nom": "Macrocicle 2026-27",
        "temporada": "2026-2027",
        "mesocicles": mesocicles,
    }

    # Validar contra model
    try:
        macrocicle = Macrocicle(**macrocicle_data)
    except Exception as e:
        raise ValueError(f"Error de validació del model Macrocicle: {e}") from e

    # Escriure JSON
    fitxer_sortida.parent.mkdir(parents=True, exist_ok=True)
    with open(fitxer_sortida, "w", encoding="utf-8") as f:
        json.dump(macrocicle.model_dump(), f, ensure_ascii=False, indent=2)

    total_microcicles = sum(len(m.microcicles) for m in macrocicle.mesocicles)

    return {
        "mesocicles": len(macrocicle.mesocicles),
        "microcicles": total_microcicles,
    }


def determinar_font_ritmes(
    temps_400: Any, temps_200: Any, text_font: Any
) -> str:
    """
    Determinar la font dels ritmes CSS.

    Args:
        temps_400: Valor de B9 (temps 400m)
        temps_200: Valor de B10 (temps 200m)
        text_font: Valor de B44 (text de la font)

    Returns:
        "css_test" o "estimat_marca"
    """
    # Si B9 i B10 estan buits, és estimat
    if not temps_400 and not temps_200:
        return "estimat_marca"

    # Si hi ha text i conté "Test CSS", és css_test
    if text_font and "Test CSS" in str(text_font):
        return "css_test"

    return "estimat_marca"


def convertir_microcicles(
    fitxer_entrada: Path, mesocicles: list
) -> dict[str, list]:
    """
    Convertir la pestanya "Microcicles" a diccionari agrupat per mesocicle_id.

    Args:
        fitxer_entrada: Path al fitxer XLSX
        mesocicles: Llista de Mesocicle ja creats (per fer mapatge de codis)

    Returns:
        Diccionari {mesocicle_id: [Microcicle, ...]}
    """
    from blondswim.models.macrocicle import Microcicle
    
    wb = openpyxl.load_workbook(fitxer_entrada, data_only=True)
    
    if "Microcicles" not in wb.sheetnames:
        raise ValueError(f"Pestanya 'Microcicles' no trobada al fitxer {fitxer_entrada}")
    
    ws = wb["Microcicles"]
    
    # Llegir capçaleres (fila 2, no la 1)
    capçaleres = llegir_capçaleres(ws, header_row=2)
    
    # Verificar capçaleres requerides (normalitzades)
    required = ["setmana", "dates", "meso", "tipusdesetmana", "volumobjectiu(m)", 
                "diesqualitat(dc+ds)"]
    for req in required:
        if req not in capçaleres:
            raise ValueError(
                f"Capçalera requerida '{req}' no trobada al full Microcicles. "
                f"Capçaleres disponibles: {list(capçaleres.keys())}"
            )
    
    # Construir mapa de codi curt (ex. "M1") a mesocicle_id
    mapa_codi_a_id = {}
    for mesocicle in mesocicles:
        # El nom és ex. "M1 - Base", extreure "M1"
        if " - " in mesocicle.nom:
            codi = mesocicle.nom.split(" - ", 1)[0].strip().lower()
            mapa_codi_a_id[codi] = mesocicle.id
        else:
            # Si no té " - ", usar el nom complet normalitzat
            mapa_codi_a_id[mesocicle.nom.strip().lower()] = mesocicle.id
    
    logger.debug(f"Mapa de codis Meso: {mapa_codi_a_id}")
    
    microcicles_per_mesocicle = {}
    files_ignorades = []
    
    # Processar files (començant des de la 3, la 2 són capçaleres)
    for num_fila, row in enumerate(ws.iter_rows(min_row=3), start=3):
        # Obtenir valors per nom de capçalera
        setmana = row[capçaleres["setmana"] - 1].value
        if not setmana:
            continue  # Fila buida
        
        dates = row[capçaleres["dates"] - 1].value
        meso = row[capçaleres["meso"] - 1].value
        tipus_setmana = row[capçaleres["tipusdesetmana"] - 1].value
        volum_objectiu = row[capçaleres["volumobjectiu(m)"] - 1].value
        dies_qualitat_text = row[capçaleres["diesqualitat(dc+ds)"] - 1].value
        
        # Columnes opcionals
        test_css_text = row[capçaleres.get("testcss(repetició6-8set.)", 999) - 1].value if "testcss(repetició6-8set.)" in capçaleres else None
        competicio_text = row[capçaleres.get("competició/testoficial", 999) - 1].value if "competició/testoficial" in capçaleres else None
        test_avaluacio_text = row[capçaleres.get("testavalu aciód'assoliment", 999) - 1].value if "testavalu aciód'assoliment" in capçaleres else None
        focus_text = row[capçaleres.get("focusespecífic—jep", 999) - 1].value if "focusespecífic—jep" in capçaleres else None
        
        # Mapatge de codi Meso a mesocicle_id
        meso_codi = str(meso).strip().lower() if meso else ""
        if meso_codi not in mapa_codi_a_id:
            logger.warning(
                f"Fila {num_fila}: codi Meso '{meso}' no trobat als mesocicles existents. "
                f"Saltant fila."
            )
            files_ignorades.append(num_fila)
            continue
        
        mesocicle_id = mapa_codi_a_id[meso_codi]
        
        # Normalitzar dates (mantenir format string)
        dates_str = str(dates).strip() if dates else ""
        
        # Extreure tipus_base del text compost "Tipus de setmana"
        # IMPORTANT: comprovar "descàrrega"/"descarrega" ABANS que "càrrega"/"carrega"
        tipus_text_lower = str(tipus_setmana).strip().lower() if tipus_setmana else ""
        tipus_base = None
        
        # Cas especial: "Cap d'Any - Represa progressiva" es mapeja a descarrega
        # Justificació: dins del mesocicle M4, aquesta setmana (15) continua el patró
        # de descàrrega de la setmana anterior (14: "Nadal - Descàrrega activa", 12500m),
        # amb volum reduït (12000m) que indica recuperació progressiva.
        # Ordre de comprovació: descarrega primer (per evitar match amb carrega)
        if ("cap d'any" in tipus_text_lower and "represa" in tipus_text_lower) or "descàrrega" in tipus_text_lower or "descarrega" in tipus_text_lower:
            tipus_base = "descarrega"
        elif "càrrega" in tipus_text_lower or "carrega" in tipus_text_lower:
            tipus_base = "carrega"
        elif "qualitat" in tipus_text_lower:
            tipus_base = "qualitat"
        elif "taper" in tipus_text_lower:
            tipus_base = "taper"
        elif "transició" in tipus_text_lower or "transicio" in tipus_text_lower:
            tipus_base = "transicio"
        
        if not tipus_base:
            raise ValueError(
                f"Fila {num_fila}: no s'ha pogut extreure tipus_base del text "
                f"'Tipus de setmana': '{tipus_setmana}'. "
                f"Paraules clau esperades: carrega, descarrega, qualitat, taper, transicio"
            )
        
        # Parsejar dies_qualitat (bool obligatori)
        dies_qualitat_lower = str(dies_qualitat_text).strip().lower() if dies_qualitat_text else ""
        if dies_qualitat_lower in ("sí", "si"):
            dies_qualitat = True
        elif dies_qualitat_lower == "no":
            dies_qualitat = False
        else:
            raise ValueError(
                f"Fila {num_fila}: valor de 'Dies qualitat' no reconegut: '{dies_qualitat_text}'. "
                f"Valors vàlids: 'Sí', 'Si', 'No'"
            )
        
        # Parsejar test_css (bool obligatori)
        test_css_str = str(test_css_text).strip() if test_css_text else ""
        test_css = bool(test_css_str and test_css_str != "-")
        
        # Parsejar camps opcionals (str | None)
        def parsejar_opcional(valor: Any) -> str | None:
            if not valor:
                return None
            text = str(valor).strip()
            if text == "-" or not text:
                return None
            return text
        
        competicio_test_oficial = parsejar_opcional(competicio_text)
        test_avaluacio = parsejar_opcional(test_avaluacio_text)
        focus_especific = parsejar_opcional(focus_text)
        
        # Notes: text literal de "Tipus de setmana"
        notes = str(tipus_setmana).strip() if tipus_setmana else None
        
        # Crear Microcicle
        try:
            microcicle = Microcicle(
                setmana=int(setmana) if setmana else 0,
                dates=dates_str,
                mesocicle_id=mesocicle_id,
                tipus_base=tipus_base,
                volum_objectiu=int(volum_objectiu) if volum_objectiu else 0,
                dies_qualitat=dies_qualitat,
                notes=notes,
                test_css=test_css,
                competicio_test_oficial=competicio_test_oficial,
                test_avaluacio=test_avaluacio,
                focus_especific=focus_especific,
            )
            
            # Afegir al diccionari agrupat
            if mesocicle_id not in microcicles_per_mesocicle:
                microcicles_per_mesocicle[mesocicle_id] = []
            microcicles_per_mesocicle[mesocicle_id].append(microcicle)
            
        except Exception as e:
            raise ValueError(
                f"Fila {num_fila}: error de validació del model Microcicle: {e}"
            ) from e
    
    if files_ignorades:
        logger.info(
            f"Files ignorades per codi Meso no trobat: {files_ignorades}"
        )
    
    return microcicles_per_mesocicle


def convertir_nedador_ritmes(
    fitxer_entrada: Path, directori_sortida: Path
) -> dict[str, Any]:
    """
    Convertir la pestanya "Ritmes" a JSON validant contra Nedador.

    Args:
        fitxer_entrada: Path al fitxer XLSX
        directori_sortida: Path al directori on escriure els JSON

    Returns:
        Diccionari amb estadístiques: {
            "nedadors": list[dict] amb info de cada nedador processat
        }
    """
    wb = openpyxl.load_workbook(fitxer_entrada, data_only=True)
    ws = wb["Ritmes"]

    nedadors_processats = []

    # Llegir dades del nedador (adreces fixes)
    nom = ws["B4"].value
    if not nom:
        raise ValueError("No s'ha trobat nom del nedador a B4")

    edat = ws["B5"].value
    categoria = ws["B6"].value
    if not categoria:
        raise ValueError("Camp obligatori categoria (B6) està buit")
    
    data_test_css = ws["B8"].value
    temps_400 = ws["B9"].value
    temps_200 = ws["B10"].value
    marca_100_lliures = ws["B15"].value
    marca_50_lliures = ws["B20"].value
    text_font = ws["B44"].value

    # Altres marques de referència
    marca_50_papallona = ws["B19"].value
    marca_200_lliure = ws["B21"].value
    marca_100_im = ws["B22"].value
    
    # Generar id com a slug del nom
    import unicodedata
    nom_slug = unicodedata.normalize('NFKD', str(nom).lower())
    nom_slug = nom_slug.encode('ascii', 'ignore').decode('ascii')
    nedador_id = nom_slug.replace(' ', '-').strip()
    
    # Determinar mode_ritme
    mode_ritme = "temps" if marca_100_lliures else "rpe"

    # Determinar font
    font = determinar_font_ritmes(temps_400, temps_200, text_font)

    # Llegir zones calculades (B48:B52)
    zona_recuperacio = ws["B48"].value
    zona_a1 = ws["B49"].value
    zona_a2 = ws["B50"].value
    zona_a3 = ws["B51"].value
    zona_velocitat = ws["B52"].value

    # Crear RitmesCSS
    ritmes_css = RitmesCSS(
        font=font,
        data_test=data_test_css.strftime("%Y-%m-%d") if isinstance(data_test_css, datetime) else None,
        temps_400m=float(temps_400) if temps_400 else None,
        temps_200m=float(temps_200) if temps_200 else None,
        recuperacio=float(zona_recuperacio) if zona_recuperacio else 0.0,
        a1=float(zona_a1) if zona_a1 else 0.0,
        a2=float(zona_a2) if zona_a2 else 0.0,
        a3=float(zona_a3) if zona_a3 else 0.0,
        velocitat=float(zona_velocitat) if zona_velocitat else 0.0,
    )

    # Validar camps obligatoris
    if not marca_100_lliures:
        raise ValueError("Camp obligatori marca_100_lliure_seg (B15) està buit")
    if not marca_50_lliures:
        raise ValueError("Camp obligatori marca_50_lliure_seg (B20) està buit")

    # Crear MarquesReferencia
    marques = MarquesReferencia(
        marca_100_lliure_seg=float(marca_100_lliures),
        marca_50_lliure_seg=float(marca_50_lliures),
        marca_50_papallona=str(marca_50_papallona).strip() if marca_50_papallona else None,
        marca_200_lliure=str(marca_200_lliure).strip() if marca_200_lliure else None,
        marca_100_im=str(marca_100_im).strip() if marca_100_im else None,
    )

    # Llegir taula de Ritme de cursa objectiu (files 76-79, columnes A-C)
    ritmes_cursa = []
    proves_objectiu = []
    for num_fila in range(76, 80):
        prova = ws[f"A{num_fila}"].value
        if not prova or prova == "[Prova]":
            continue

        # Afegir a proves_objectiu
        proves_objectiu.append(str(prova).strip())
        
        distancia = ws[f"B{num_fila}"].value
        temps_objectiu = ws[f"C{num_fila}"].value

        # Crear RitmeCursaObjectiu si hi ha distància (temps_objectiu és opcional)
        if distancia:
            ritme = RitmeCursaObjectiu(
                prova=str(prova).strip(),
                distancia_m=int(distancia),
                temps_objectiu_s=float(temps_objectiu) if temps_objectiu else None,
            )
            ritmes_cursa.append(ritme)

    # Crear Nedador
    try:
        nedador = Nedador(
            id=nedador_id,
            nom=str(nom).strip(),
            edat=int(edat) if edat else 0,
            categoria=str(categoria).strip().lower(),
            proves_objectiu=proves_objectiu,
            mode_ritme=mode_ritme,
            ritmes_css=ritmes_css,
            marques_referencia=marques,
            ritmes_cursa_objectiu=ritmes_cursa,
        )
    except Exception as e:
        raise ValueError(f"Error de validació del model Nedador: {e}") from e

    # Escriure JSON
    nom_fitxer = f"nedador_{nom.lower().replace(' ', '_')}.json"
    fitxer_sortida = directori_sortida / nom_fitxer
    fitxer_sortida.parent.mkdir(parents=True, exist_ok=True)

    with open(fitxer_sortida, "w", encoding="utf-8") as f:
        json.dump(nedador.model_dump(), f, ensure_ascii=False, indent=2)

    nedadors_processats.append(
        {
            "nom": nedador.nom,
            "fitxer": nom_fitxer,
            "font_ritmes": font,
            "ritmes_cursa": len(ritmes_cursa),
        }
    )

    return {"nedadors": nedadors_processats}


def convertir_pretemporada(fitxer_entrada: Path) -> list[SessioRealitzada]:
    """
    Convertir l'historial de pretemporada a llista de SessioRealitzada.

    Args:
        fitxer_entrada: Path al fitxer XLSX amb pestanyes per mes

    Returns:
        Llista de SessioRealitzada ordenades cronològicament
    
    Raises:
        ValueError: Si cap pestanya del fitxer coincideix amb un nom de mes conegut
    """
    import unicodedata
    
    wb = openpyxl.load_workbook(fitxer_entrada, data_only=True)
    
    # Mapa de noms de mes a número
    mesos = {
        "ago": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
        "gen": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "mai": 5,
        "jun": 6,
        "jul": 7,
    }
    
    sessions = []
    
    # Verificar que hi ha almenys una pestanya de mes reconeguda
    pestanyes_mes = [s for s in wb.sheetnames if s.lower().strip() in mesos]
    if not pestanyes_mes:
        raise ValueError(
            f"Cap pestanya de mes reconeguda al fitxer {fitxer_entrada}. "
            f"Pestanyes trobades: {wb.sheetnames}"
        )
    
    # Processar cada pestanya
    for sheet_name in wb.sheetnames:
        # Detectar si és una pestanya de mes
        sheet_lower = sheet_name.lower().strip()
        if sheet_lower not in mesos:
            continue
        
        mes_num = mesos[sheet_lower]
        ws = wb[sheet_name]
        
        logger.info(f"Processant pestanya: {sheet_name} (mes {mes_num})")
        
        # Iterar per les files buscant blocs de setmana
        setmana_actual = None
        capçaleres = {}
        dia_actual = None
        series_dia = []
        ordre_serie = 1
        
        for num_fila, row in enumerate(ws.iter_rows(min_row=1), start=1):
            primera_cel = row[0].value
            
            # Detectar fila "Total" en qualsevol columna (abans de comprovar si primera_cel està buida)
            es_fila_total = False
            for cell in row:
                if cell.value and str(cell.value).strip().lower() == "total":
                    es_fila_total = True
                    break
            
            if es_fila_total:
                if dia_actual and capçaleres:
                    # Tancar dia actual
                    volum_total = int(row[capçaleres.get("volum(m)", 999) - 1].value or 0)
                    temps_total = float(row[capçaleres.get("temps(min)", 999) - 1].value or 0.0)
                    
                    sessio = SessioRealitzada(
                        data=dia_actual,
                        setmana=setmana_actual,
                        series=series_dia,
                        volum_total_m=volum_total,
                        temps_total_min=temps_total,
                    )
                    sessions.append(sessio)
                    logger.debug(f"Sessió creada: {dia_actual}, {len(series_dia)} sèries, {volum_total}m")
                    
                    # Reset per al següent dia
                    dia_actual = None
                    series_dia = []
                    ordre_serie = 1
                continue
            
            if not primera_cel:
                # Fila buida o continuació de dia
                if dia_actual and capçaleres:
                    # Llegir sèrie
                    serie_data = {}
                    fila_buida = True
                    
                    for nom_cap, idx_col in capçaleres.items():
                        valor = row[idx_col - 1].value
                        if valor is not None and str(valor).strip():
                            fila_buida = False
                        serie_data[nom_cap] = valor
                    
                    # Si la fila no està completament buida, afegir sèrie
                    if not fila_buida and serie_data.get("execucio"):
                        serie = SerieRealitzada(
                            ordre=ordre_serie,
                            treball=str(serie_data.get("treball")).strip() if serie_data.get("treball") else None,
                            execucio=str(serie_data["execucio"]).strip(),
                            descans=str(serie_data.get("descans")).strip() if serie_data.get("descans") else None,
                            material=str(serie_data.get("material")).strip() if serie_data.get("material") else None,
                            intensitat=str(serie_data.get("intensitat")).strip() if serie_data.get("intensitat") else None,
                            objectiu=str(serie_data.get("objectiu")).strip() if serie_data.get("objectiu") else None,
                            temps_min=float(serie_data["temps(min)"]) if serie_data.get("temps(min)") else None,
                            volum_m=int(serie_data["volum(m)"]) if serie_data.get("volum(m)") else None,
                        )
                        series_dia.append(serie)
                        ordre_serie += 1
                continue
            
            primera_cel_str = str(primera_cel).strip()
            
            # Detectar "Setmana N"
            if primera_cel_str.lower().startswith("setmana"):
                match = re.search(r"setmana\s+(\d+)", primera_cel_str, re.IGNORECASE)
                if match:
                    setmana_actual = int(match.group(1))
                    logger.debug(f"Detectada setmana {setmana_actual}")
                continue
            
            # Detectar capçalera (Dia | Treball | Execució ...)
            if primera_cel_str.lower() == "dia":
                capçaleres = {}
                for cell in row:
                    if cell.value:
                        # Normalitzar: minúscules, sense espais, sense accents
                        nom_str = str(cell.value).strip().lower().replace(" ", "")
                        nom_normalitzat = unicodedata.normalize('NFKD', nom_str)
                        nom_normalitzat = nom_normalitzat.encode('ascii', 'ignore').decode('ascii')
                        capçaleres[nom_normalitzat] = cell.column
                logger.debug(f"Capçaleres detectades: {list(capçaleres.keys())}")
                continue
            
            
            # Detectar inici de dia (p.ex. "Dilluns 18" o "Diumenge 24")
            if capçaleres:
                # Intentar extreure dia numèric del text
                match = re.search(r"\b(\d{1,2})\b", primera_cel_str)
                if match:
                    dia_num = int(match.group(1))
                    
                    # Tancar dia anterior si existeix (sense haver trobat Total)
                    if dia_actual and series_dia:
                        # Crear sessió amb el que tenim
                        volum_total = sum(s.volum_m for s in series_dia if s.volum_m)
                        temps_total = sum(s.temps_min for s in series_dia if s.temps_min)
                        
                        sessio = SessioRealitzada(
                            data=dia_actual,
                            setmana=setmana_actual,
                            series=series_dia,
                            volum_total_m=volum_total,
                            temps_total_min=temps_total,
                        )
                        sessions.append(sessio)
                        logger.debug(f"Sessió creada (sense Total): {dia_actual}, {len(series_dia)} sèries")
                    
                    # Determinar any (agost-desembre 2026, gener-juliol 2027)
                    any = 2026 if mes_num >= 8 else 2027
                    
                    # Crear nova data
                    dia_actual = f"{any:04d}-{mes_num:02d}-{dia_num:02d}"
                    series_dia = []
                    ordre_serie = 1
                    logger.debug(f"Nou dia detectat: {dia_actual}")
    
    # Tancar última sessió si existeix
    if dia_actual:
        if series_dia:
            volum_total = sum(s.volum_m for s in series_dia if s.volum_m)
            temps_total = sum(s.temps_min for s in series_dia if s.temps_min)
        else:
            volum_total = 0
            temps_total = 0.0
        
        sessio = SessioRealitzada(
            data=dia_actual,
            setmana=setmana_actual,
            series=series_dia,
            volum_total_m=volum_total,
            temps_total_min=temps_total,
        )
        sessions.append(sessio)
        logger.debug(f"Última sessió creada: {dia_actual}, {len(series_dia)} sèries")
    
    # Ordenar sessions cronològicament
    sessions.sort(key=lambda s: s.data)
    
    return sessions


def main():
    """Executar totes les conversions i imprimir resum."""
    logging.basicConfig(level=logging.INFO)

    base_dir = Path(__file__).parent.parent.parent.parent
    data_raw = base_dir / "data" / "raw"
    data_processed = base_dir / "data" / "processed"

    print("=" * 60)
    print("CONVERSIÓ XLSX → JSON")
    print("=" * 60)

    # 1. Calendari
    print("\n1. Convertint Calendari...")
    try:
        stats_cal = convertir_calendari(
            data_raw / "Provisional26-27.xlsx",
            data_processed / "calendari.json",
        )
        print(f"   ✓ {stats_cal['total']} competicions processades")
        print(f"   ✓ {stats_cal['classe_a']} competicions de classe A")
        if stats_cal["advertencies"]:
            print(f"   ⚠ {len(stats_cal['advertencies'])} advertències:")
            for adv in stats_cal["advertencies"]:
                print(f"     - {adv}")
    except Exception as e: # noqa: BLE001
        print(f"   ✗ Error: {e}")
        return

    # 2. Macrocicle Jep (amb microcicles)
    print("\n2. Convertint Macrocicle Jep (amb microcicles)...")
    try:
        stats_macro = convertir_macrocicle_jep(
            data_raw / "Planificacio_Mesocicles_Jep.xlsx",
            data_processed / "macrocicle_jep.json",
        )
        print(f"   ✓ {stats_macro['mesocicles']} mesocicles processats")
        print(f"   ✓ {stats_macro['microcicles']} microcicles vinculats")
    except Exception as e: # noqa: BLE001
        print(f"   ✗ Error: {e}")
        return

    # 3. Nedadors (Ritmes)
    print("\n3. Convertint Nedadors (Ritmes)...")
    try:
        stats_ned = convertir_nedador_ritmes(
            data_raw / "Planificacio_Mesocicles_Jep.xlsx",
            data_processed,
        )
        print(f"   ✓ {len(stats_ned['nedadors'])} nedadors processats:")
        for ned in stats_ned["nedadors"]:
            print(f"     - {ned['nom']} ({ned['fitxer']})")
            print(f"       Font ritmes: {ned['font_ritmes']}")
            print(f"       Ritmes cursa objectiu: {ned['ritmes_cursa']}")
    except Exception as e: # noqa: BLE001
        print(f"   ✗ Error: {e}")
        return

    # 4. Historial pretemporada
    print("\n4. Convertint Historial Pretemporada...")
    try:
        sessions = convertir_pretemporada(
            data_raw / "PretemporadaSep26-27.xlsx"
        )
        
        # Escriure JSON
        fitxer_historial = data_processed / "historial_jep.json"
        fitxer_historial.parent.mkdir(parents=True, exist_ok=True)
        with open(fitxer_historial, "w", encoding="utf-8") as f:
            json.dump(
                [s.model_dump() for s in sessions],
                f,
                ensure_ascii=False,
                indent=2,
            )
        
        print(f"   ✓ {len(sessions)} sessions processades")
        if sessions:
            print(f"   ✓ Període: {sessions[0].data} a {sessions[-1].data}")
    except Exception as e: # noqa: BLE001
        print(f"   ✗ Error: {e}")
        return

    print("\n" + "=" * 60)
    print("CONVERSIÓ COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()

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
from blondswim.models.macrocicle import Macrocicle
from blondswim.models.nedador import (
    MarquesReferencia,
    Nedador,
    ParametresRitme,
    RitmeCursaObjectiu,
    RitmesCSS,
)

logger = logging.getLogger(__name__)


class DataParseError(Exception):
    """Error en parsejar una data."""

    pass


class InconsistentDataWarning(Exception):
    """Advertència per dades inconsistents (no fatal)."""

    pass


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


def llegir_capçaleres(ws: Worksheet) -> dict[str, int]:
    """
    Llegir capçaleres de la primera fila i retornar un mapa nom -> índex de columna.

    Args:
        ws: Worksheet d'openpyxl

    Returns:
        Diccionari {nom_capçalera: índex_columna} (índex basat en 1)
    """
    capçaleres = {}
    for cell in ws[1]:
        if cell.value:
            capçaleres[str(cell.value).strip().lower()] = cell.column
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

    # Llegir capçaleres
    capçaleres = llegir_capçaleres(ws)
    
    # Capçaleres esperades (normalitzades a minúscules)
    required = ["mesocicle", "setmanes", "dates", "fase/objectiu", 
                "metodologia dominant", "volum setmanal (rang)", 
                "volum mitjà previst (m)"]
    
    # Verificar que existeixen les capçaleres necessàries
    for req in required:
        if req not in capçaleres:
            logger.warning(f"Capçalera '{req}' no trobada. Capçaleres disponibles: {list(capçaleres.keys())}")

    mesocicles = []
    
    # Processar files (començant des de la 2, la 1 són capçaleres)
    files_processades = 0
    for num_fila, row in enumerate(ws.iter_rows(min_row=2), start=2):
        # Obtenir valor de la primera columna (Mesocicle)
        mesocicle_col = capçaleres.get("mesocicle")
        if not mesocicle_col:
            logger.error("No s'ha trobat la columna 'mesocicle'")
            break
            
        mesocicle_nom = row[mesocicle_col - 1].value
        if not mesocicle_nom:
            continue  # Fila buida
        
        files_processades += 1
        
        # Extreure dades de cada columna per nom
        setmanes = row[capçaleres.get("setmanes", 1) - 1].value
        dates = row[capçaleres.get("dates", 1) - 1].value
        fase_objectiu = row[capçaleres.get("fase/objectiu", 1) - 1].value
        metodologia = row[capçaleres.get("metodologia dominant", 1) - 1].value
        volum_rang = row[capçaleres.get("volum setmanal (rang)", 1) - 1].value
        volum_mitja = row[capçaleres.get("volum mitjà previst (m)", 1) - 1].value
        tancament = row[capçaleres.get("tancament", 999) - 1].value if "tancament" in capçaleres else None
        
        # Parsejar volum_rang (ex: "18000-22000" -> min=18000, max=22000)
        volum_min, volum_max = 0, 0
        if volum_rang:
            volum_str = str(volum_rang).strip()
            if "-" in volum_str:
                parts = volum_str.split("-")
                volum_min = int(parts[0].strip())
                volum_max = int(parts[1].strip())
        
        # Crear mesocicle
        from blondswim.models.macrocicle import Mesocicle
        
        try:
            mesocicle = Mesocicle(
                id=str(mesocicle_nom).strip(),
                nom=str(mesocicle_nom).strip(),
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
    data_test_css = ws["B8"].value
    temps_400 = ws["B9"].value
    temps_200 = ws["B10"].value
    marca_100_lliures = ws["B15"].value
    marca_50_lliures = ws["B20"].value
    text_font = ws["B44"].value

    # Altres marques de referència
    marca_ref_b19 = ws["B19"].value
    marca_ref_b21 = ws["B21"].value
    marca_ref_b22 = ws["B22"].value

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

    # Crear MarquesReferencia
    marques = MarquesReferencia(
        millor_100_lliures=float(marca_100_lliures) if marca_100_lliures else 0.0,
        millor_50_lliures=float(marca_50_lliures) if marca_50_lliures else 0.0,
        altres={
            "B19": str(marca_ref_b19) if marca_ref_b19 else "",
            "B21": str(marca_ref_b21) if marca_ref_b21 else "",
            "B22": str(marca_ref_b22) if marca_ref_b22 else "",
        },
    )

    # Llegir taula de Ritme de cursa objectiu (files 76-79, columnes A-C)
    ritmes_cursa = []
    for num_fila in range(76, 80):
        prova = ws[f"A{num_fila}"].value
        if not prova or prova == "[Prova]":
            continue

        distancia = ws[f"B{num_fila}"].value
        temps_objectiu = ws[f"C{num_fila}"].value

        if distancia and temps_objectiu:
            ritme = RitmeCursaObjectiu(
                prova=str(prova).strip(),
                distancia_m=int(distancia),
                temps_objectiu_s=float(temps_objectiu),
            )
            ritmes_cursa.append(ritme)

    # Crear Nedador
    try:
        nedador = Nedador(
            nom=str(nom).strip(),
            edat=int(edat) if edat else 0,
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
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return

    # 2. Macrocicle Jep
    print("\n2. Convertint Macrocicle Jep...")
    try:
        stats_macro = convertir_macrocicle_jep(
            data_raw / "Planificacio_Mesocicles_Jep.xlsx",
            data_processed / "macrocicle_jep.json",
        )
        print(f"   ✓ {stats_macro['mesocicles']} mesocicles processats")
        print(f"   ✓ {stats_macro['microcicles']} microcicles totals")
    except Exception as e:
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
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return

    print("\n" + "=" * 60)
    print("CONVERSIÓ COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()

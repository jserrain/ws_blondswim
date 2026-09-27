"""
Validació de plans de macrocicle i microcicle.

Implementa validacions fisiològiques i temporals per detectar:
- Períodes massa llargs sense descàrrega (risc de sobreentrenament)
- Progressions de volum massa ràpides (ACWR - Acute:Chronic Workload Ratio)
- Incoherències entre càrrega alta i finestres de taper/recuperació

Segueix la metodologia documentada a docs/guia_mvp.md.
Totes les funcions retornen avisos informatius (dict), mai llancen excepcions.
"""

from datetime import datetime
from typing import Literal

from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Microcicle


def calcular_volums_setmanals_historial(
    sessions: list[SessioRealitzada],
) -> list[int]:
    """
    Agrupa les SessioRealitzada per setmana ISO i suma el volum total.
    
    Utilitza date.isocalendar() per determinar la setmana ISO (dilluns-diumenge).
    Sessions sense sèries (dies especials com "Travessa Banyoles") compten
    igualment el seu volum_total_m (normalment 0).
    
    Args:
        sessions: Llista de sessions realitzades (poden estar desordenades)
        
    Returns:
        Llista de volums setmanals (metres) ordenada cronològicament
        (setmana més antiga primera)
    """
    # Agrupar per (any_iso, setmana_iso)
    volums_per_setmana: dict[tuple[int, int], int] = {}
    
    for sessio in sessions:
        # Parsejar data (format "YYYY-MM-DD")
        data = datetime.strptime(sessio.data, "%Y-%m-%d").date()
        any_iso, setmana_iso, _ = data.isocalendar()
        
        clau = (any_iso, setmana_iso)
        if clau not in volums_per_setmana:
            volums_per_setmana[clau] = 0
        volums_per_setmana[clau] += sessio.volum_total_m
    
    # Ordenar per (any, setmana) i retornar només els volums
    setmanes_ordenades = sorted(volums_per_setmana.keys())
    return [volums_per_setmana[clau] for clau in setmanes_ordenades]


def validar_descarrega_periodica(
    microcicles: list[Microcicle],
    categoria: Literal["absolut", "master", "junior"],
) -> list[dict]:
    """
    Valida que hi hagi descàrregues periòdiques segons la categoria del nedador.
    
    Regles de càrrega:descàrrega per categoria:
    - Junior: màxim 2 setmanes de càrrega consecutives abans d'una descàrrega
    - Master/Absolut: màxim 3 setmanes de càrrega consecutives
    
    Args:
        microcicles: Llista de microcicles ordenats cronològicament
        categoria: Categoria del nedador
        
    Returns:
        Llista d'avisos (dict) amb:
        - setmana_inici: Primera setmana del tram sense descàrrega
        - setmana_fi: Última setmana del tram
        - setmanes_consecutives: Nombre de setmanes sense descàrrega
        - categoria: Categoria aplicada
        - limit_recomanat: Límit màxim recomanat per aquesta categoria
        - missatge: Descripció de l'avís
        
    Notes:
        - Només es consideren microcicles de tipus 'carrega' o 'qualitat'
        - Els tipus 'descarrega', 'taper' i 'transicio' trenquen la seqüència
    """
    avisos = []
    
    # Determinar límit segons categoria
    limit_carrega = 2 if categoria == "junior" else 3
    
    # Rastrejar trams consecutius sense descàrrega
    setmanes_sense_descarrega = []
    
    for micro in microcicles:
        # Tipus que compten com a càrrega (sense descàrrega)
        if micro.tipus_base in ["carrega", "qualitat"]:
            setmanes_sense_descarrega.append(micro.setmana)
        else:
            # Descàrrega, taper o transició trenquen la seqüència
            if len(setmanes_sense_descarrega) > limit_carrega:
                avisos.append({
                    "setmana_inici": setmanes_sense_descarrega[0],
                    "setmana_fi": setmanes_sense_descarrega[-1],
                    "setmanes_consecutives": len(setmanes_sense_descarrega),
                    "categoria": categoria,
                    "limit_recomanat": limit_carrega,
                    "missatge": f"Tram de {len(setmanes_sense_descarrega)} setmanes sense descàrrega "
                               f"(setmanes {setmanes_sense_descarrega[0]}-{setmanes_sense_descarrega[-1]}). "
                               f"Límit recomanat per categoria {categoria}: {limit_carrega} setmanes. "
                               "Risc de sobreentrenament.",
                })
            setmanes_sense_descarrega = []
    
    # Comprovar el darrer tram (si el macrocicle acaba sense descàrrega)
    if len(setmanes_sense_descarrega) > limit_carrega:
        avisos.append({
            "setmana_inici": setmanes_sense_descarrega[0],
            "setmana_fi": setmanes_sense_descarrega[-1],
            "setmanes_consecutives": len(setmanes_sense_descarrega),
            "categoria": categoria,
            "limit_recomanat": limit_carrega,
            "missatge": f"Tram de {len(setmanes_sense_descarrega)} setmanes sense descàrrega "
                       f"(setmanes {setmanes_sense_descarrega[0]}-{setmanes_sense_descarrega[-1]}). "
                       f"Límit recomanat per categoria {categoria}: {limit_carrega} setmanes. "
                       "Risc de sobreentrenament.",
        })
    
    return avisos


def validar_progressio_volum(
    microcicles: list[Microcicle],
    finestra_setmanes: int = 4,
    ratio_min: float = 0.8,
    ratio_max: float = 1.3,
    ratio_risc: float = 1.5,
    historial_previ: list[int] | None = None,
) -> list[dict]:
    """
    Valida la progressió de volum amb ACWR (Acute:Chronic Workload Ratio).
    
    ACWR = volum_setmana_actual / mitjana(volum_últimes_N_setmanes)
    
    Rangs recomanats:
    - 0.8-1.3: progressió segura
    - >1.3: progressió ràpida (avís)
    - >1.5: risc elevat de lesió (avís sever)
    - <0.8: descàrrega massa pronunciada (avís)
    
    Args:
        microcicles: Llista de microcicles ordenats cronològicament
        finestra_setmanes: Nombre de setmanes per calcular la mitjana crònica (per defecte 4)
        ratio_min: Ratio mínima acceptable (per defecte 0.8)
        ratio_max: Ratio màxima acceptable (per defecte 1.3)
        ratio_risc: Ratio de risc elevat de lesió (per defecte 1.5)
        historial_previ: Llista opcional de volums reals (metres) de setmanes anteriors
                         a microcicles[0], ordenada cronològicament (més antiga primera).
                         Permet avaluar les primeres setmanes del macrocicle amb context real.
        
    Returns:
        Llista d'avisos (dict) amb:
        - setmana: Setmana amb progressió problemàtica
        - volum_actual: Volum de la setmana actual
        - volum_mitja_cronic: Mitjana de les setmanes anteriors
        - ratio_acwr: Ratio calculat
        - tipus_avis: "carrega_fora_de_rang" o "carrega_risc_lesio"
        - missatge: Descripció de l'avís
        
    Notes:
        - Sense historial_previ: les primeres finestra_setmanes setmanes no generen avisos
        - Amb historial_previ suficient: fins i tot microcicles[0] pot generar avisos
        - El càlcul només considera volum_objectiu dels microcicles, no volum real executat
    """
    avisos = []
    
    # Construir context combinant historial previ + volums del macrocicle
    contexte = list(historial_previ or []) + [
        m.volum_objectiu for m in microcicles
    ]
    offset = len(historial_previ or [])
    
    for i in range(len(microcicles)):
        pos = offset + i
        finestra = contexte[pos - finestra_setmanes:pos]
        
        # Només avaluem si tenim una finestra completa de finestra_setmanes setmanes anteriors
        if len(finestra) < finestra_setmanes:
            continue
        
        micro_actual = microcicles[i]
        volum_actual = micro_actual.volum_objectiu
        volum_mitja_cronic = sum(finestra) / len(finestra)
        
        # Evitar divisió per zero
        if volum_mitja_cronic == 0:
            continue
        
        # Calcular ACWR
        ratio = volum_actual / volum_mitja_cronic
        
        # Generar avisos segons el ratio
        if ratio > ratio_risc:
            avisos.append({
                "setmana": micro_actual.setmana,
                "volum_actual": volum_actual,
                "volum_mitja_cronic": round(volum_mitja_cronic, 0),
                "ratio_acwr": round(ratio, 2),
                "tipus_avis": "carrega_risc_lesio",
                "missatge": f"Setmana {micro_actual.setmana}: ACWR de {round(ratio, 2)} "
                           f"(volum {volum_actual}m vs mitjana {round(volum_mitja_cronic, 0)}m). "
                           f"Risc elevat de lesió (>{ratio_risc}). "
                           "Recomanació: reduir volum o redistribuir càrrega.",
            })
        elif ratio > ratio_max or ratio < ratio_min:
            tipus = "increment massa ràpid" if ratio > ratio_max else "descàrrega massa pronunciada"
            avisos.append({
                "setmana": micro_actual.setmana,
                "volum_actual": volum_actual,
                "volum_mitja_cronic": round(volum_mitja_cronic, 0),
                "ratio_acwr": round(ratio, 2),
                "tipus_avis": "carrega_fora_de_rang",
                "missatge": f"Setmana {micro_actual.setmana}: ACWR de {round(ratio, 2)} "
                           f"(volum {volum_actual}m vs mitjana {round(volum_mitja_cronic, 0)}m). "
                           f"Progressió {tipus} (rang recomanat: {ratio_min}-{ratio_max}).",
            })
    
    return avisos


def validar_coherencia_taper(
    microcicles: list[Microcicle],
    pla_taper: list[dict],
) -> list[dict]:
    """
    Valida que no hi hagi càrrega alta durant finestres de taper/recuperació.
    
    Creua les dates dels microcicles amb les finestres de taper i recuperació
    del pla de competicions per detectar incoherències.
    
    Args:
        microcicles: Llista de microcicles ordenats cronològicament
        pla_taper: Pla de taper generat per generar_pla_taper_temporada()
        
    Returns:
        Llista d'avisos (dict) amb:
        - setmana: Setmana amb incoherència
        - competicio_id: ID de la competició afectada
        - competicio_nom: Nom de la competició
        - tipus_microcicle: Tipus del microcicle (hauria de ser 'taper' o 'descarrega')
        - missatge: Descripció de l'avís
        
    Notes:
        - Només genera avisos per microcicles de tipus 'carrega' o 'qualitat'
        - La validació es basa en coincidència de dates (microcicle.dates vs competicio.data_inici)
        - Aquesta és una validació bàsica; una versió més sofisticada calcularia
          les dates exactes de les finestres de taper/recuperació
    """
    avisos = []
    
    # Per a cada entrada del pla de taper, extreure les competicions amb taper significatiu
    competicions_amb_taper = [
        entrada for entrada in pla_taper
        if entrada["dies_taper_pre"] > 0 or entrada["dies_recuperacio_post"] > 0
    ]
    
    # Per a cada microcicle de càrrega/qualitat, comprovar si coincideix amb una finestra de taper
    for micro in microcicles:
        if micro.tipus_base not in ["carrega", "qualitat"]:
            continue
        
        # Comprovar si aquest microcicle té una competició associada
        if micro.competicio_test_oficial:
            # Buscar la competició al pla de taper
            comp_info = next(
                (c for c in competicions_amb_taper if c["competicio_id"] == micro.competicio_test_oficial),
                None
            )
            
            if comp_info and comp_info["dies_taper_pre"] > 0:
                avisos.append({
                    "setmana": micro.setmana,
                    "competicio_id": comp_info["competicio_id"],
                    "competicio_nom": comp_info["competicio_nom"],
                    "tipus_microcicle": micro.tipus_base,
                    "missatge": f"Setmana {micro.setmana}: microcicle de tipus '{micro.tipus_base}' "
                               f"coincideix amb finestra de taper per a '{comp_info['competicio_nom']}' "
                               f"({comp_info['dies_taper_pre']} dies de taper). "
                               "Recomanació: canviar a tipus 'taper' o 'descarrega'.",
                })
    
    return avisos


def validar_pla_complet(
    macrocicle: Macrocicle,
    categoria: Literal["absolut", "master", "junior"],
    pla_taper: list[dict],
    avisos_pics_a: list[dict],
) -> list[dict]:
    """
    Orquestra totes les validacions sobre un macrocicle complet.
    
    Aplica les validacions de:
    1. Descàrrega periòdica (validar_descarrega_periodica)
    2. Progressió de volum ACWR (validar_progressio_volum)
    3. Coherència amb taper (validar_coherencia_taper)
    4. Incorpora avisos de pics A ja generats (validar_espaiat_pics_a)
    
    Args:
        macrocicle: Macrocicle complet amb tots els mesocicles i microcicles
        categoria: Categoria del nedador
        pla_taper: Pla de taper generat per generar_pla_taper_temporada()
        avisos_pics_a: Avisos generats per validar_espaiat_pics_a()
        
    Returns:
        Llista consolidada d'avisos de totes les validacions, amb camp addicional:
        - tipus_validacio: "descarrega_periodica", "progressio_volum", 
          "coherencia_taper" o "espaiat_pics_a"
        
    Notes:
        - Els avisos es retornen en l'ordre en què es generen (no ordenats per setmana)
        - Cada avís inclou el camp tipus_validacio per facilitar el filtratge
    """
    avisos_consolidats = []
    
    # Extreure tots els microcicles de tots els mesocicles
    tots_microcicles = []
    for mesocicle in macrocicle.mesocicles:
        tots_microcicles.extend(mesocicle.microcicles)
    
    # Ordenar per setmana (per si de cas no estan ordenats)
    tots_microcicles.sort(key=lambda m: m.setmana)
    
    # 1. Validar descàrrega periòdica
    avisos_descarrega = validar_descarrega_periodica(tots_microcicles, categoria)
    for avis in avisos_descarrega:
        avis["tipus_validacio"] = "descarrega_periodica"
        avisos_consolidats.append(avis)
    
    # 2. Validar progressió de volum (ACWR)
    avisos_volum = validar_progressio_volum(tots_microcicles)
    for avis in avisos_volum:
        avis["tipus_validacio"] = "progressio_volum"
        avisos_consolidats.append(avis)
    
    # 3. Validar coherència amb taper
    avisos_taper = validar_coherencia_taper(tots_microcicles, pla_taper)
    for avis in avisos_taper:
        avis["tipus_validacio"] = "coherencia_taper"
        avisos_consolidats.append(avis)
    
    # 4. Incorporar avisos de pics A
    for avis in avisos_pics_a:
        avis["tipus_validacio"] = "espaiat_pics_a"
        avisos_consolidats.append(avis)
    
    return avisos_consolidats

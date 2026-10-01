"""
Anàlisi del context de competicions per a la planificació de pics de forma.

Implementa validacions i detecció de patrons per ajudar l'entrenador a:
- Validar l'espaiat entre competicions classe A (pics principals)
- Detectar candidats a re-taper (competicions properes a un pic prioritzat)
- Classificar i resumir el calendari de competicions

Segueix la metodologia documentada a docs/metodologia_ritmes.md i docs/guia_mvp.md.
"""

from datetime import datetime

from blondswim.models.calendari import Competicio


def setmanes_entre(comp_a: Competicio, comp_b: Competicio) -> float:
    """
    Calcula les setmanes entre la data_fi de comp_a i la data_inici de comp_b.
    
    Args:
        comp_a: Primera competició (referència)
        comp_b: Segona competició (objectiu)
        
    Returns:
        Nombre de setmanes (pot ser negatiu si les competicions se solapen)
        
    Examples:
        >>> # comp_a acaba 17 gen, comp_b comença 29 maig
        >>> # Diferència: ~19.4 setmanes
    """
    data_fi_a = datetime.fromisoformat(comp_a.data_fi)
    data_inici_b = datetime.fromisoformat(comp_b.data_inici)
    
    diferencia_dies = (data_inici_b - data_fi_a).days
    setmanes = diferencia_dies / 7.0
    
    return setmanes


def validar_espaiat_pics_a(
    competicions: list[Competicio],
    min_setmanes: int = 8,
    max_setmanes: int = 12,
) -> list[dict]:
    """
    Valida l'espaiat entre competicions classe A (pics principals de forma).
    
    Filtra només les competicions classe A, les ordena cronològicament i comprova
    que la separació entre pics consecutius compleix els criteris recomanats.
    
    Args:
        competicions: Llista de totes les competicions del calendari
        min_setmanes: Separació mínima recomanada entre pics A (per defecte 8)
        max_setmanes: Separació màxima recomanada (per defecte 12, no validat)
        
    Returns:
        Llista d'avisos (dict) amb els camps:
        - comp_a_id: ID de la primera competició
        - comp_b_id: ID de la segona competició
        - setmanes_separacio: Setmanes reals entre les dues
        - tipus_avis: "doble_pic" (<= 4 setmanes), "separacio_insuficient" o "massa_pics_a"
        - missatge: Descripció de l'avís i recomanació
        
        Llista buida = tot correcte, cap avís.
        
    Notes:
        - No llança excepcions: són avisos informatius per a l'entrenador
        - "separacio_insuficient": recomanació de tractar la segona com a B
        - "massa_pics_a": si hi ha >3 competicions A, revisar prioritats
    """
    avisos = []
    
    # Filtrar només competicions classe A
    pics_a = [c for c in competicions if c.classe == "A"]
    
    # Ordenar cronològicament per data_inici
    pics_a_ordenats = sorted(pics_a, key=lambda c: c.data_inici)
    
    # Avís si hi ha més de 3 pics A
    if len(pics_a_ordenats) > 3:
        avisos.append({
            "comp_a_id": None,
            "comp_b_id": None,
            "setmanes_separacio": None,
            "tipus_avis": "massa_pics_a",
            "missatge": f"Hi ha {len(pics_a_ordenats)} competicions classe A (recomanat: màx 3). "
                       "Recomanació: revisar prioritats amb el nedador/entrenador.",
        })
    
    # Validar separació entre pics consecutius
    for i in range(len(pics_a_ordenats) - 1):
        comp_a = pics_a_ordenats[i]
        comp_b = pics_a_ordenats[i + 1]
        
        setmanes = setmanes_entre(comp_a, comp_b)
        
        if setmanes <= 4:
            avisos.append({
                "comp_a_id": comp_a.id,
                "comp_b_id": comp_b.id,
                "setmanes_separacio": round(setmanes, 1),
                "tipus_avis": "doble_pic",
                "missatge": f"'{comp_a.nom}' i '{comp_b.nom}' estan a {round(setmanes, 1)} "
                           "setmanes: es planifiquen com un sol període competitiu "
                           "(sense Transició entre elles i taper curt abans de la segona).",
            })
        elif setmanes < min_setmanes:
            avisos.append({
                "comp_a_id": comp_a.id,
                "comp_b_id": comp_b.id,
                "setmanes_separacio": round(setmanes, 1),
                "tipus_avis": "separacio_insuficient",
                "missatge": f"Separació de {round(setmanes, 1)} setmanes entre '{comp_a.nom}' i '{comp_b.nom}' "
                           f"(mínim recomanat: {min_setmanes} setmanes). "
                           "Recomanació: tractar la segona com a classe B de facto.",
            })
    
    return avisos


def detectar_candidats_retaper(
    competicions: list[Competicio],
    pics_prioritzats: list[str],
    finestra_setmanes: int = 4,
) -> list[dict]:
    """
    Detecta parelles de competicions candidates a re-taper.
    
    Un re-taper és quan hi ha dues competicions properes (dins de finestra_setmanes)
    on la segona està marcada com a pic prioritzat pel nedador, típicament una
    competició A seguida de prop per una B important.
    
    Args:
        competicions: Llista de totes les competicions del calendari
        pics_prioritzats: IDs de competicions marcades com a prioritàries pel nedador
        finestra_setmanes: Finestra temporal per considerar re-taper (per defecte 4)
        
    Returns:
        Llista de diccionaris amb:
        - comp_primera_id: ID de la primera competició
        - comp_segona_id: ID de la segona (candidata a re-taper)
        - setmanes_separacio: Setmanes entre les dues
        - missatge: Descripció del patró detectat
        
    Examples:
        >>> # Catalunya Hivern (A, 16-17 gen) + Espanya (B, 4-7 feb, pic_prioritzat)
        >>> # Separació ~2.4 setmanes → candidat a re-taper
    """
    candidats = []
    
    # Ordenar cronològicament
    comps_ordenades = sorted(competicions, key=lambda c: c.data_inici)
    
    for i in range(len(comps_ordenades) - 1):
        comp_primera = comps_ordenades[i]
        comp_segona = comps_ordenades[i + 1]
        
        setmanes = setmanes_entre(comp_primera, comp_segona)
        
        # Detectar si la segona està dins de la finestra i és pic prioritzat
        if setmanes <= finestra_setmanes and comp_segona.id in pics_prioritzats:
            candidats.append({
                "comp_primera_id": comp_primera.id,
                "comp_segona_id": comp_segona.id,
                "setmanes_separacio": round(setmanes, 1),
                "missatge": f"'{comp_segona.nom}' (classe {comp_segona.classe}) està a {round(setmanes, 1)} setmanes "
                           f"després de '{comp_primera.nom}' i marcada com a pic prioritzat. "
                           "Candidat a re-taper.",
            })
    
    return candidats


def classificar_pics(competicions: list[Competicio]) -> dict:
    """
    Genera un resum classificat del calendari de competicions.
    
    Args:
        competicions: Llista de totes les competicions del calendari
        
    Returns:
        Diccionari amb:
        - total: Nombre total de competicions
        - per_classe: Recompte per classe (A, B, C)
        - competicions_a: Llista d'IDs de competicions classe A
        - competicions_b: Llista d'IDs de competicions classe B
        - competicions_c: Llista d'IDs de competicions classe C
        - avisos_espaiat: Avisos generats per validar_espaiat_pics_a
        
    Notes:
        - Útil per a dashboards i informes de planificació
        - Inclou automàticament els avisos de validació d'espaiat
    """
    per_classe = {"A": 0, "B": 0, "C": 0}
    ids_per_classe = {"A": [], "B": [], "C": []}
    
    for comp in competicions:
        per_classe[comp.classe] += 1
        ids_per_classe[comp.classe].append(comp.id)
    
    # Generar avisos d'espaiat
    avisos = validar_espaiat_pics_a(competicions)
    
    return {
        "total": len(competicions),
        "per_classe": per_classe,
        "competicions_a": ids_per_classe["A"],
        "competicions_b": ids_per_classe["B"],
        "competicions_c": ids_per_classe["C"],
        "avisos_espaiat": avisos,
    }

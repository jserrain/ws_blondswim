"""
Càlcul de plans de taper i recuperació per a competicions.

Implementa les regles de taper segons la classe de competició:
- Classe A: taper progressiu de 14 dies + recuperació activa llarga de 14 dies
- Classe B: taper lleuger de 3 dies + recuperació activa de 3 dies
- Classe C: sense taper + recuperació estàndard d'1 dia

Detecta situacions de re-taper quan hi ha competicions properes marcades com a
pics prioritzats pel nedador.

Segueix la metodologia documentada a docs/guia_mvp.md.
"""

from blondswim.agents.context_competicio import setmanes_entre
from blondswim.models.calendari import Competicio


def calcular_taper(
    competicio: Competicio,
    dies_taper_a: int = 14,
    dies_recuperacio_a: int = 14,
    dies_taper_b: int = 3,
    dies_recuperacio_b: int = 3,
) -> dict:
    """
    Calcula el pla de taper i recuperació per a una competició segons la seva classe.
    
    Args:
        competicio: Competició a analitzar
        dies_taper_a: Dies de taper per a competicions classe A (per defecte 14)
        dies_recuperacio_a: Dies de recuperació per a classe A (per defecte 14)
        dies_taper_b: Dies de taper per a competicions classe B (per defecte 3)
        dies_recuperacio_b: Dies de recuperació per a classe B (per defecte 3)
        
    Returns:
        Diccionari amb:
        - dies_taper_pre: Dies de taper abans de la competició
        - tipus_taper: "progressiu" (A), "lleuger" (B) o "cap" (C)
        - dies_recuperacio_post: Dies de recuperació després de la competició
        - tipus_recuperacio: "activa_llarga" (A), "activa" (B) o "estandard" (C)
        
    Notes:
        - El taper de classe B s'aplica a TOTES les competicions B, estiguin o no
          marcades com a pic_prioritzat (això només afecta el re-taper)
        - Classe C no té taper específic, només 1 dia de recuperació estàndard
    """
    if competicio.classe == "A":
        return {
            "dies_taper_pre": dies_taper_a,
            "tipus_taper": "progressiu",
            "dies_recuperacio_post": dies_recuperacio_a,
            "tipus_recuperacio": "activa_llarga",
        }
    elif competicio.classe == "B":
        return {
            "dies_taper_pre": dies_taper_b,
            "tipus_taper": "lleuger",
            "dies_recuperacio_post": dies_recuperacio_b,
            "tipus_recuperacio": "activa",
        }
    else:  # Classe C
        return {
            "dies_taper_pre": 0,
            "tipus_taper": "cap",
            "dies_recuperacio_post": 1,
            "tipus_recuperacio": "estandard",
        }


def detectar_retaper(
    competicio_a: Competicio,
    competicio_b: Competicio,
    pics_prioritzats: list[str],
    finestra_setmanes: int = 4,
) -> bool:
    """
    Detecta si una competició és candidata a re-taper.
    
    Un re-taper s'aplica quan:
    1. La competició anterior (competicio_a) és classe A
    2. La competició actual (competicio_b) està marcada com a pic prioritzat
    3. La separació entre les dues és <= finestra_setmanes
    
    Args:
        competicio_a: Competició anterior (ha de ser classe A)
        competicio_b: Competició actual (candidata a re-taper)
        pics_prioritzats: IDs de competicions marcades com a prioritàries pel nedador
        finestra_setmanes: Finestra temporal per considerar re-taper (per defecte 4)
        
    Returns:
        True si es compleixen les condicions de re-taper, False altrament
        
    Examples:
        >>> # Catalunya Hivern (A, 16-17 gen) + Espanya (B, 4-7 feb, pic_prioritzat)
        >>> # Separació ~2.4 setmanes → True
        >>> # Catalunya Hivern + Espanya sense pic_prioritzat → False
    """
    # Condició 1: competicio_a ha de ser classe A
    if competicio_a.classe != "A":
        return False
    
    # Condició 2: competicio_b ha d'estar a pics_prioritzats
    if competicio_b.id not in pics_prioritzats:
        return False
    
    # Condició 3: separació <= finestra_setmanes
    setmanes = setmanes_entre(competicio_a, competicio_b)
    if setmanes > finestra_setmanes:
        return False
    
    return True


def generar_pla_taper_temporada(
    competicions: list[Competicio],
    pics_prioritzats: list[str],
) -> list[dict]:
    """
    Genera el pla de taper complet per a totes les competicions de la temporada.
    
    Per a cada competició:
    - Calcula el taper i recuperació segons la seva classe
    - Detecta si és candidata a re-taper respecte a competicions A anteriors
    
    Args:
        competicions: Llista de totes les competicions del calendari
        pics_prioritzats: IDs de competicions marcades com a prioritàries pel nedador
        
    Returns:
        Llista de diccionaris ordenada per data amb:
        - competicio_id: ID de la competició
        - competicio_nom: Nom de la competició
        - classe: Classe de la competició (A/B/C)
        - data_inici: Data d'inici de la competició
        - dies_taper_pre: Dies de taper abans
        - tipus_taper: Tipus de taper aplicat
        - dies_recuperacio_post: Dies de recuperació després
        - tipus_recuperacio: Tipus de recuperació aplicat
        - retaper: True si s'aplica re-taper, False altrament
        
    Notes:
        - Les competicions s'ordenen cronològicament per data_inici
        - El re-taper només s'activa per a competicions marcades com a pic_prioritzat
          que vénen després d'una classe A dins de la finestra temporal
    """
    # Ordenar competicions cronològicament
    comps_ordenades = sorted(competicions, key=lambda c: c.data_inici)
    
    pla_temporada = []
    
    for i, comp in enumerate(comps_ordenades):
        # Calcular taper i recuperació segons la classe
        pla_taper = calcular_taper(comp)
        
        # Detectar re-taper: buscar competicions A anteriors dins de la finestra
        es_retaper = False
        for j in range(i):
            comp_anterior = comps_ordenades[j]
            if detectar_retaper(comp_anterior, comp, pics_prioritzats):
                es_retaper = True
                break  # Només cal trobar-ne una
        
        # Afegir al pla de temporada
        pla_temporada.append({
            "competicio_id": comp.id,
            "competicio_nom": comp.nom,
            "classe": comp.classe,
            "data_inici": comp.data_inici,
            "dies_taper_pre": pla_taper["dies_taper_pre"],
            "tipus_taper": pla_taper["tipus_taper"],
            "dies_recuperacio_post": pla_taper["dies_recuperacio_post"],
            "tipus_recuperacio": pla_taper["tipus_recuperacio"],
            "retaper": es_retaper,
        })
    
    return pla_temporada

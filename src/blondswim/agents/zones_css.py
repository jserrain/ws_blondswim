"""
Càlcul de zones fisiològiques d'entrenament basades en CSS test o marques de referència.

Implementa la metodologia documentada a docs/metodologia_ritmes.md:
- Font 1 (CSS test): zones calculades amb offsets sobre el ritme CSS
- Font 2 (marca): zones calculades com a percentatge sobre millor marca de 100m
- Regla de conciliació: Font 1 té prioritat quan hi ha test CSS recent
"""

from blondswim.models.nedador import Nedador, ParametresRitme, RitmesCSS


def calcular_zones_des_de_css(
    css_pace_100m: float, params: ParametresRitme
) -> dict[str, float]:
    """
    Calcula zones fisiològiques a partir del ritme CSS (Font 1).
    
    Args:
        css_pace_100m: Ritme CSS en segons per 100m
        params: Paràmetres del model de càlcul
        
    Returns:
        Diccionari amb zones {recuperacio, a1, a2, a3, velocitat} en segons per 100m
    """
    return {
        "recuperacio": css_pace_100m + params.offset_recuperacio_css,
        "a1": css_pace_100m + params.offset_a1_css,
        "a2": css_pace_100m + params.offset_a2_css,
        "a3": css_pace_100m + params.offset_a3_css,
        "velocitat": css_pace_100m * params.factor_velocitat,
    }


def calcular_zones_des_de_marca(
    marca_100_lliure_seg: float,
    marca_50_lliure_seg: float,
    params: ParametresRitme,
) -> dict[str, float]:
    """
    Calcula zones fisiològiques a partir de marques de referència (Font 2).
    
    IMPORTANT: La zona de velocitat s'ancora a la marca real de 50m escalada a 100m,
    NO al 85% de la marca de 100m (donaria un ritme més ràpid que el propi rècord,
    físicament absurd). Vegeu docs/metodologia_ritmes.md punt 4.
    
    Args:
        marca_100_lliure_seg: Millor marca de 100m lliures en segons
        marca_50_lliure_seg: Millor marca de 50m lliures en segons
        params: Paràmetres del model de càlcul
        
    Returns:
        Diccionari amb zones {recuperacio, a1, a2, a3, velocitat} en segons per 100m
    """
    return {
        "recuperacio": marca_100_lliure_seg * (1 + params.increment_recuperacio),
        "a1": marca_100_lliure_seg * (1 + params.increment_a1),
        "a2": marca_100_lliure_seg * (1 + params.increment_a2),
        "a3": marca_100_lliure_seg * (1 + params.increment_a3),
        "velocitat": marca_50_lliure_seg * params.factor_escala_50_100,
    }


def calcular_css_pace(temps_400_seg: float, temps_200_seg: float) -> float:
    """
    Calcula el ritme CSS segons la fórmula de Wakayoshi.
    
    CSS (Critical Swim Speed) = velocitat sostinguda màxima en llindar aeròbic.
    Fórmula: velocitat = (400-200) / (t400-t200) m/s
    Retorna: ritme per 100m en segons (100 / velocitat)
    
    Args:
        temps_400_seg: Temps del test de 400m en segons
        temps_200_seg: Temps del test de 200m en segons
        
    Returns:
        Ritme CSS en segons per 100m
        
    Raises:
        ValueError: Si temps_400_seg <= temps_200_seg (dada físicament impossible)
    """
    if temps_400_seg <= temps_200_seg:
        raise ValueError(
            f"El temps de 400m ({temps_400_seg}s) ha de ser major que el de 200m ({temps_200_seg}s)"
        )
    
    velocitat_m_per_s = (400 - 200) / (temps_400_seg - temps_200_seg)
    ritme_100m = 100 / velocitat_m_per_s
    
    return ritme_100m


def determinar_zones_nedador(nedador: Nedador) -> RitmesCSS:
    """
    Determina les zones fisiològiques d'un nedador aplicant la regla de conciliació.
    
    Regla de conciliació (docs/metodologia_ritmes.md punt 2):
    - Font 1 (CSS test) té prioritat quan hi ha test recent amb data_test
    - Font 2 (marca) s'utilitza com a fallback quan no hi ha test CSS
    
    Aquesta funció recalcula les zones des de zero a partir de les dades disponibles,
    no es limita a retornar el que ja hi ha al nedador.ritmes_css.
    
    Args:
        nedador: Objecte Nedador amb marques_referencia i/o ritmes_css
        
    Returns:
        RitmesCSS amb zones calculades i font correctament assignada
        
    Raises:
        ValueError: Si no hi ha ni test CSS ni marques de referència disponibles
    """
    params = nedador.parametres_ritme
    
    # Prioritat 1: CSS test (si hi ha data_test i zones CSS prèvies que indiquen test fet)
    if (
        nedador.ritmes_css
        and nedador.ritmes_css.data_test
        and nedador.ritmes_css.font == "css_test"
        and nedador.ritmes_css.a2 is not None
    ):
        # Recalcular des del CSS (a2 = CSS per definició)
        css_pace = nedador.ritmes_css.a2
        zones = calcular_zones_des_de_css(css_pace, params)
        
        return RitmesCSS(
            recuperacio=zones["recuperacio"],
            a1=zones["a1"],
            a2=zones["a2"],
            a3=zones["a3"],
            velocitat=zones["velocitat"],
            data_test=nedador.ritmes_css.data_test,
            font="css_test",
        )
    
    # Prioritat 2: Marques de referència (fallback)
    if nedador.marques_referencia:
        zones = calcular_zones_des_de_marca(
            nedador.marques_referencia.marca_100_lliure_seg,
            nedador.marques_referencia.marca_50_lliure_seg,
            params,
        )
        
        return RitmesCSS(
            recuperacio=zones["recuperacio"],
            a1=zones["a1"],
            a2=zones["a2"],
            a3=zones["a3"],
            velocitat=zones["velocitat"],
            data_test=None,
            font="estimat_marca",
        )
    
    # Cap font disponible
    raise ValueError(
        f"Nedador {nedador.nom} no té ni test CSS ni marques de referència disponibles"
    )

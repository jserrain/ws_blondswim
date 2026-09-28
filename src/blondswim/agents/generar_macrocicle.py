"""Generació de macrocicles a partir del calendari de competicions."""

from blondswim.agents import context_competicio
from blondswim.models.calendari import Competicio
from blondswim.models.macrocicle import Macrocicle


def generar_macrocicle(
    nedador_id: str,
    competicions: list[Competicio],
    temporada_data_inici: str,
    temporada_data_fi: str,
) -> tuple[Macrocicle, list[dict]]:
    """
    Crea el macrocicle de tota la temporada (convenció TrainingPeaks:
    el macrocicle és la temporada sencera, amb dates fixades per
    l'usuari — no es divideix per competicions).

    Requereix almenys una competició classe "A" al calendari (com fa
    TrainingPeaks: cal com a mínim un objectiu A per generar la
    periodització automàtica dels mesocicles més endavant). Si no
    n'hi ha cap, afegeix un avís però crea igualment el macrocicle.

    El Macrocicle es crea amb id "macro_1", nom "Macrocicle <temporada>",
    data_inici i data_fi = els paràmetres rebuts, mesocicles=[] (buit,
    es omplen seqüencialment amb generar_mesocicle()).

    Retorna (macrocicle, avisos): avisos combina el resultat de
    context_competicio.validar_espaiat_pics_a(competicions) més,
    si escau, l'avís de "cap competició classe A al calendari".

    Args:
        nedador_id: ID del nedador
        competicions: Llista de totes les competicions del calendari
        temporada_data_inici: Data d'inici de la temporada (format ISO: YYYY-MM-DD)
        temporada_data_fi: Data de fi de la temporada (format ISO: YYYY-MM-DD)

    Returns:
        Tupla amb:
        - Macrocicle generat per a tota la temporada
        - Llista d'avisos (validar_espaiat_pics_a + avís si no hi ha competicions A)
    """
    # Obtenir avisos de validació d'espaiat
    avisos = context_competicio.validar_espaiat_pics_a(competicions)

    # Comprovar si hi ha almenys una competició classe A
    competicions_a = [c for c in competicions if c.classe == "A"]
    
    if not competicions_a:
        # Afegir avís si no hi ha cap competició A
        avisos.append({
            "tipus_avis": "cap_competicio_a",
            "missatge": "No hi ha cap competició classe A al calendari. "
                       "Es requereix almenys un objectiu A per generar la periodització automàtica dels mesocicles.",
        })

    # Extreure temporada del format YYYY-MM-DD
    any_inici = temporada_data_inici[:4]
    any_fi = temporada_data_fi[:4]
    temporada = f"{any_inici}-{any_fi}"

    # Crear macrocicle únic per a tota la temporada
    macrocicle = Macrocicle(
        nom=f"Macrocicle {temporada}",
        temporada=temporada,
        data_inici=temporada_data_inici,
        data_fi=temporada_data_fi,
        mesocicles=[],
    )

    return macrocicle, avisos

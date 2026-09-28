"""Generació de macrocicles a partir del calendari de competicions."""

from datetime import datetime, timedelta

from blondswim.agents import context_competicio
from blondswim.models.calendari import Competicio
from blondswim.models.macrocicle import Macrocicle


def generar_macrocicle(
    nedador_id: str,
    competicions: list[Competicio],
    temporada_data_inici: str,
    temporada_data_fi: str,
    dies_recuperacio_a: int = 14,
) -> tuple[list[Macrocicle], list[dict]]:
    """
    Determina els límits temporals dels macrocicles d'una temporada a
    partir del calendari de competicions.

    Filtra les competicions classe "A" (ordenades cronològicament per
    data_fi). Cada macrocicle acaba `dies_recuperacio_a` dies després
    de la data_fi de cada competició A (mateix concepte que
    taper.calcular_taper — transició/recuperació post-competició). El
    primer macrocicle comença a temporada_data_inici; l'últim acaba a
    temporada_data_fi. Si hi ha N competicions A, es generen N
    macrocicles.

    Si no hi ha cap competició classe A, retorna un únic macrocicle
    que cobreix tota la temporada.

    Cada Macrocicle es crea amb id (p. ex. "macro_1", "macro_2", ...),
    nom (p. ex. "Macrocicle 1"), temporada, data_inici, data_fi fixats,
    i mesocicles=[] (buit, es omplen després amb generar_mesocicle()).

    Retorna (macrocicles, avisos), on avisos ve de
    context_competicio.validar_espaiat_pics_a(competicions) — no
    recalcula res, reutilitza aquesta funció ja existent.

    Args:
        nedador_id: ID del nedador
        competicions: Llista de totes les competicions del calendari
        temporada_data_inici: Data d'inici de la temporada (format ISO: YYYY-MM-DD)
        temporada_data_fi: Data de fi de la temporada (format ISO: YYYY-MM-DD)
        dies_recuperacio_a: Dies de recuperació després d'una competició A (per defecte 14)

    Returns:
        Tupla amb:
        - Llista de Macrocicle generats
        - Llista d'avisos de validar_espaiat_pics_a()
    """
    # Obtenir avisos de validació
    avisos = context_competicio.validar_espaiat_pics_a(competicions)

    # Filtrar i ordenar competicions classe A per data_fi
    competicions_a = [c for c in competicions if c.classe == "A"]
    competicions_a_ordenades = sorted(competicions_a, key=lambda c: c.data_fi)

    # Si no hi ha competicions A, retornar un únic macrocicle
    if not competicions_a_ordenades:
        macrocicle = Macrocicle(
            nom="Macrocicle 1",
            temporada=f"{temporada_data_inici[:4]}-{temporada_data_fi[:4]}",
            data_inici=temporada_data_inici,
            data_fi=temporada_data_fi,
            mesocicles=[],
        )
        return [macrocicle], avisos

    # Generar macrocicles basats en competicions A
    macrocicles = []
    data_inici_actual = temporada_data_inici

    for i, comp_a in enumerate(competicions_a_ordenades, start=1):
        # Calcular data_fi del macrocicle: data_fi de la competició + dies_recuperacio_a
        data_fi_comp = datetime.fromisoformat(comp_a.data_fi)
        data_fi_macro = data_fi_comp + timedelta(days=dies_recuperacio_a)
        data_fi_macro_str = data_fi_macro.strftime("%Y-%m-%d")

        # Si és l'últim macrocicle, usar temporada_data_fi
        if i == len(competicions_a_ordenades):
            data_fi_macro_str = temporada_data_fi

        # Crear macrocicle
        macrocicle = Macrocicle(
            nom=f"Macrocicle {i}",
            temporada=f"{temporada_data_inici[:4]}-{temporada_data_fi[:4]}",
            data_inici=data_inici_actual,
            data_fi=data_fi_macro_str,
            mesocicles=[],
        )
        macrocicles.append(macrocicle)

        # Actualitzar data_inici per al següent macrocicle
        data_inici_seguent = data_fi_macro + timedelta(days=1)
        data_inici_actual = data_inici_seguent.strftime("%Y-%m-%d")

    return macrocicles, avisos

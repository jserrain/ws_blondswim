"""Generació de l'esquelet de sessions d'un microcicle (100% determinista)."""

from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio


def generar_esquelet_sessions(
    nedador: Nedador,
    microcicle: Microcicle,
) -> list[Sessio]:
    """
    Construeix les Sessio d'una setmana (100% determinista, sense cap crida LLM).

    Genera l'estructura de parts ja fixada per percentatges, però amb
    `contingut=None` a cada PartSessio (el Mòdul 6 l'omplirà després).

    Dies actius: nedador.dies_disponibles + nedador.dia_opcional (si no és None).

    Regla d'assignació de tipus_sessio per dia:
    - microcicle.tipus_base == "qualitat": totes les sessions tipus_sessio="qualitat"
    - microcicle.tipus_base == "carrega" i microcicle.dies_qualitat == True:
      "dimecres" i el dia_opcional del nedador són tipus_sessio="qualitat";
      la resta "carrega"
    - microcicle.tipus_base == "carrega" i dies_qualitat == False: totes "carrega"
    - microcicle.tipus_base a {"descarrega", "taper", "transicio"}:
      totes les sessions hereten aquest mateix tipus_sessio

    Per cada PartSessio de EstructuraSessio (les 5 parts estàndard), selecciona
    el percentatge segons el tipus_sessio de LA SESSIÓ:
    - "carrega" -> percentatge_carrega
    - "qualitat" -> percentatge_qualitat
    - "descarrega" -> percentatge_descarrega
    - "taper" i "transicio" -> percentatge_descarrega (reutilitzat, són setmanes
      de volum reduït similars; assumpció MVP a revisar)

    volum_total de cada sessió: microcicle.volum_objectiu dividit a parts iguals
    entre el nombre de sessions actives de la setmana (arrodonit; l'últim dia
    absorbeix el residu d'arrodoniment perquè la suma quadri exactament amb
    volum_objectiu). Assumpció MVP: repartiment igual que es podrà refinar més
    endavant (p.ex. menys volum als dies de qualitat).

    Args:
        nedador: Nedador amb dies_disponibles i dia_opcional
        microcicle: Microcicle amb tipus_base, dies_qualitat i volum_objectiu

    Returns:
        Llista de Sessio amb estructura de parts fixada però contingut=None
    """
    # Determinar dies actius de la setmana
    dies_actius = nedador.dies_disponibles.copy()
    if nedador.dia_opcional:
        dies_actius.append(nedador.dia_opcional)

    # Calcular volum per sessió (repartiment igual, assumpció MVP)
    num_sessions = len(dies_actius)
    volum_base = microcicle.volum_objectiu // num_sessions
    residu = microcicle.volum_objectiu % num_sessions

    sessions = []

    for i, dia in enumerate(dies_actius):
        # Determinar tipus_sessio segons regles
        if microcicle.tipus_base == "qualitat":
            tipus_sessio = "qualitat"
        elif microcicle.tipus_base == "carrega":
            if microcicle.dies_qualitat and (
                dia == "dimecres" or dia == nedador.dia_opcional
            ):
                tipus_sessio = "qualitat"
            else:
                tipus_sessio = "carrega"
        else:
            # descarrega, taper, transicio
            tipus_sessio = microcicle.tipus_base

        # Calcular volum d'aquesta sessió (l'última absorbeix el residu)
        volum_sessio = volum_base
        if i == num_sessions - 1:
            volum_sessio += residu

        # Crear estructura de 5 parts amb percentatges segons tipus_sessio
        parts = _crear_parts_estandard(tipus_sessio, volum_sessio)

        # Crear sessió
        sessio = Sessio(
            id=f"{microcicle.mesocicle_id}_s{microcicle.setmana}_{dia}",
            microcicle_setmana=microcicle.setmana,
            dia=dia,
            tipus_sessio=tipus_sessio,
            volum_total=volum_sessio,
            estructura=EstructuraSessio(parts=parts),
            es_dia_opcional=(dia == nedador.dia_opcional),
            notes=None,
        )
        sessions.append(sessio)

    return sessions


def _crear_parts_estandard(tipus_sessio: str, volum_total: int) -> list[PartSessio]:
    """
    Crear les 5 parts estàndard amb percentatges segons tipus_sessio.

    Parts estàndard (segons EstructuraSessio):
    1. Escalfament (10%/10%/15%)
    2. Tècnica+Subaquàtic (20%/15%/15%)
    3. Aeròbic/Llindar (50%/30%/20%)
    4. Específic/Qualitat (10%/35%/40%)
    5. Tornada a la calma (10%/10%/10%)

    Args:
        tipus_sessio: Tipus de sessió ("carrega", "qualitat", "descarrega", etc.)
        volum_total: Volum total de la sessió en metres

    Returns:
        Llista de 5 PartSessio amb percentatges fixats i contingut=None
    """
    # Definició de les 5 parts estàndard amb percentatges
    # Format: (nom, %_carrega, %_qualitat, %_descarrega)
    parts_definicio = [
        ("Escalfament", 10.0, 10.0, 15.0),
        ("Tècnica+Subaquàtic", 20.0, 15.0, 15.0),
        ("Aeròbic/Llindar", 50.0, 30.0, 20.0),
        ("Específic/Qualitat", 10.0, 35.0, 40.0),
        ("Tornada a la calma", 10.0, 10.0, 10.0),
    ]

    parts = []
    for nom, perc_carrega, perc_qualitat, perc_descarrega in parts_definicio:
        part = PartSessio(
            nom=nom,
            percentatge_carrega=perc_carrega,
            percentatge_qualitat=perc_qualitat,
            percentatge_descarrega=perc_descarrega,
            contingut=None,  # Serà omplert pel Mòdul 6
        )
        parts.append(part)

    return parts

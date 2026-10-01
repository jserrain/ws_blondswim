"""Generació de l'esquelet de sessions d'un microcicle (100% determinista)."""

from datetime import date, timedelta

from blondswim.agents import pla_setmanal, tecnica
from blondswim.models.franja import ETIQUETA_MODALITAT, ORDRE_FRANJA
from blondswim.models.macrocicle import Microcicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import EstructuraSessio, PartSessio, Sessio
from blondswim.utils.dates import parsejar_rang_dates

_DIES_ORDRE = {
    "dilluns": 0,
    "dimarts": 1,
    "dimecres": 2,
    "dijous": 3,
    "divendres": 4,
    "dissabte": 5,
    "diumenge": 6,
}

# Rol fix per dia de la setmana (quan el dia hi és).
ROLS_PER_DIA = {
    "dilluns": "mitjana",
    "dimarts": "qualitat",
    "dimecres": "mitjana",
    "dijous": "llarga",
}

# Rang de volum (metres) per rol, abans d'aplicar el factor de la setmana.
RANGS_ROL = {
    "llarga": (3800, 4500),
    "mitjana": (3000, 3500),
    "qualitat": (2800, 3200),
}

# Límit de volum per a setmanes de càrrega (carrega/qualitat).
CLAMP_CARREGA = (2800, 4500)


def _midpoint(rol: str) -> float:
    """Punt mig del rang de volum d'un rol."""
    minim, maxim = RANGS_ROL[rol]
    return (minim + maxim) / 2


def _arrodonir_25(valor: float) -> int:
    """Arrodoneix a múltiple de 25 (mínim 25)."""
    return max(25, round(valor / 25) * 25)


def _assignar_rols(dies_actius: list[str]) -> dict[str, str]:
    """
    Assigna un rol a cada dia actiu.

    Si el dia és a ROLS_PER_DIA, s'usa aquest rol. Si no, l'últim dia
    disponible és "llarga", el segon "qualitat" i la resta "mitjana".
    """
    rols: dict[str, str] = {}
    dies_no_mapatats = [dia for dia in dies_actius if dia not in ROLS_PER_DIA]

    for dia in dies_actius:
        if dia in ROLS_PER_DIA:
            rols[dia] = ROLS_PER_DIA[dia]

    if dies_no_mapatats:
        # L'últim dia no mapatat és llarga, el segon qualitat, la resta mitjana.
        ultim = dies_no_mapatats[-1]
        segon = dies_no_mapatats[-2] if len(dies_no_mapatats) >= 2 else None
        for dia in dies_no_mapatats:
            if dia == ultim:
                rols[dia] = "llarga"
            elif segon is not None and dia == segon:
                rols[dia] = "qualitat"
            else:
                rols[dia] = "mitjana"

    return rols


def _dilluns_microcicle(microcicle: Microcicle) -> date | None:
    """Retorna el dilluns del microcicle a partir del camp `dates`."""
    try:
        dilluns, _ = parsejar_rang_dates(microcicle.dates)
        return dilluns
    except ValueError:
        return None


def _data_del_dia(microcicle: Microcicle, dia: str) -> date:
    """Data concreta d'un dia de la setmana dins el microcicle."""
    dilluns = _dilluns_microcicle(microcicle)
    if dilluns is None:
        return date.max
    return dilluns + timedelta(days=_DIES_ORDRE[dia])


def generar_esquelet_sessions(
    nedador: Nedador,
    microcicle: Microcicle,
) -> list[Sessio]:
    """
    Construeix les Sessio d'una setmana (100% determinista, sense cap crida LLM).

    Genera l'estructura de parts ja fixada per percentatges, però amb
    `contingut=None` a cada PartSessio (el Mòdul 6 l'omplirà després).

    Dies actius: nedador.dies_disponibles (dia_opcional no s'utilitza).

    Regla d'assignació de tipus_sessio per dia:
    - microcicle.tipus_base == "qualitat": totes les sessions tipus_sessio="qualitat"
    - microcicle.tipus_base == "carrega" i microcicle.dies_qualitat == True:
      "dimecres" és tipus_sessio="qualitat"; la resta "carrega"
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

    Cada sessió té un rol fix (ROLS_PER_DIA) i un rang de volum flexible
    (RANGS_ROL) escalat pel factor de la setmana:

        factor = microcicle.volum_objectiu / suma de punts migs dels rols
                 d'una setmana completa (len(nedador.dies_disponibles) dies)

    S'usa len(dies_disponibles) (no el nombre de sessions generades) perquè
    les setmanes parcials no concentrin volum. El rang de cada sessió és
    RANGS_ROL[rol] × factor, arrodonit a 25. En setmanes de càrrega
    (carrega/qualitat) el rang es limita a CLAMP_CARREGA; en descàrrega,
    taper i transició NO es limita (pot baixar de 2800m).

    volum_total de cada sessió és el punt mig del rang, arrodonit a 25.

    Args:
        nedador: Nedador amb dies_disponibles
        microcicle: Microcicle amb tipus_base, dies_qualitat i volum_objectiu

    Returns:
        Llista de Sessio amb estructura de parts fixada però contingut=None
    """
    if pla_setmanal.usa_plantilla(nedador):
        sessions = _esquelet_plantilla(nedador, microcicle)
    else:
        sessions = _esquelet_dies(nedador, microcicle)
    return _afegir_franges_i_altres_sessions(nedador, microcicle, sessions)


def _esquelet_dies(nedador: Nedador, microcicle: Microcicle) -> list[Sessio]:
    """Esquelet antic: rols per dia fixos (nedadors sense la plantilla setmanal)."""
    # Determinar dies actius de la setmana
    dies_actius = nedador.dies_disponibles.copy()

    # R5: no generar sessions de dies anteriors a sessions_des_de
    if microcicle.sessions_des_de is not None:
        dies_actius = [
            dia
            for dia in dies_actius
            if _data_del_dia(microcicle, dia) >= microcicle.sessions_des_de
        ]
        if not dies_actius:
            return []

    # Assignar rols als dies actius
    rols = _assignar_rols(dies_actius)

    # Factor d'escala: volum_objectiu / suma de punts migs d'una setmana completa
    dies_setmana_completa = nedador.dies_disponibles
    suma_midpoints = sum(_midpoint(ROLS_PER_DIA.get(dia, "mitjana"))
                         for dia in dies_setmana_completa)
    factor = microcicle.volum_objectiu / suma_midpoints if suma_midpoints else 1.0

    # Clampar només en setmanes de càrrega
    es_carrega = microcicle.tipus_base in ("carrega", "qualitat")

    sessions = []

    for dia in dies_actius:
        # Determinar tipus_sessio segons regles
        if microcicle.tipus_base == "qualitat":
            tipus_sessio = "qualitat"
        elif microcicle.tipus_base == "carrega":
            if microcicle.dies_qualitat and dia == "dimecres":
                tipus_sessio = "qualitat"
            else:
                tipus_sessio = "carrega"
        else:
            # descarrega, taper, transicio
            tipus_sessio = microcicle.tipus_base

        # Calcular rang de volum d'aquesta sessió segons el rol
        rol = rols[dia]
        minim_rol, maxim_rol = RANGS_ROL[rol]
        volum_min = _arrodonir_25(minim_rol * factor)
        volum_max = _arrodonir_25(maxim_rol * factor)

        if es_carrega:
            volum_min = max(volum_min, CLAMP_CARREGA[0])
            volum_max = min(volum_max, CLAMP_CARREGA[1])

        # volum_total = punt mig del rang
        volum_sessio = _arrodonir_25((volum_min + volum_max) / 2)

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
            es_dia_opcional=False,
            notes=None,
            rol=rol,
            volum_min=volum_min,
            volum_max=volum_max,
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
            bloc=pla_setmanal.bloc_part(nom),
            percentatge_carrega=perc_carrega,
            percentatge_qualitat=perc_qualitat,
            percentatge_descarrega=perc_descarrega,
            contingut=None,  # Serà omplert pel Mòdul 6
        )
        parts.append(part)

    return parts


def _esquelet_plantilla(nedador: Nedador, microcicle: Microcicle) -> list[Sessio]:
    """
    Esquelet amb la plantilla setmanal (pla_setmanal): rols segons el tipus de
    setmana (normal, competició dissabte/diumenge, post-competició), volum
    repartit per pesos de rol, parts pròpies de cada rol i sèrie de control
    fixa el dia de la sèrie de control (pla_setmanal.DIA_SERIE_CONTROL).
    """
    rols = pla_setmanal.rols_setmana(microcicle.dia_competicio, microcicle.post_competicio)
    dies = sorted(rols, key=lambda d: _DIES_ORDRE[d])

    # Pes de la setmana completa (les setmanes parcials no concentren volum).
    suma_pesos = sum(pla_setmanal.PES_ROL[rols[d]] for d in dies)
    volum_max_temps = nedador.minuts_max_sessio * pla_setmanal.METRES_PER_MINUT
    notes = pla_setmanal.context_setmana(
        microcicle.dia_competicio, microcicle.post_competicio
    )

    if microcicle.sessions_des_de is not None:
        dies = [
            d for d in dies if _data_del_dia(microcicle, d) >= microcicle.sessions_des_de
        ]

    sessions: list[Sessio] = []
    for dia in dies:
        rol = rols[dia]
        objectiu = microcicle.volum_objectiu * pla_setmanal.PES_ROL[rol] / suma_pesos
        objectiu = min(objectiu, volum_max_temps)
        volum_sessio = _arrodonir_25(objectiu)
        volum_min = _arrodonir_25(objectiu * (1 - pla_setmanal.MARGE_RANG_SESSIO))
        volum_max = _arrodonir_25(
            min(objectiu * (1 + pla_setmanal.MARGE_RANG_SESSIO), volum_max_temps)
        )

        parts: list[PartSessio] = []
        volum_fix = 0
        if dia == pla_setmanal.DIA_SERIE_CONTROL:
            control = pla_setmanal.part_serie_control(nedador)
            volum_fix = sum(ex.volum_m for ex in control.exercicis)
        volum_variable = max(volum_sessio - volum_fix, 0)

        for i, (nom, pct) in enumerate(pla_setmanal.PARTS_ROL[rol]):
            pct_sessio = round(pct * volum_variable / volum_sessio, 1) if volum_sessio else 0
            parts.append(
                PartSessio(
                    nom=nom,
                    bloc=pla_setmanal.bloc_part(nom),
                    percentatge_carrega=pct_sessio,
                    percentatge_qualitat=pct_sessio,
                    percentatge_descarrega=pct_sessio,
                    contingut=None,
                )
            )
            if i == 0 and volum_fix:
                parts.append(control)

        sessions.append(
            Sessio(
                id=f"{microcicle.mesocicle_id}_s{microcicle.setmana}_{dia}",
                microcicle_setmana=microcicle.setmana,
                dia=dia,
                tipus_sessio=microcicle.tipus_base,
                volum_total=volum_sessio,
                estructura=EstructuraSessio(parts=parts),
                es_dia_opcional=False,
                notes=notes,
                rol=rol,
                volum_min=volum_min,
                volum_max=volum_max,
                exercicis_tecnica=[
                    e["id"]
                    for e in tecnica.seleccionar_exercicis(
                        nedador, rol, microcicle.tipus_base, microcicle
                    )
                ],
            )
        )

    return sessions


def _afegir_franges_i_altres_sessions(
    nedador: Nedador, microcicle: Microcicle, sessions: list[Sessio]
) -> list[Sessio]:
    """
    Fase E+I: assigna la franja a cada sessió de natació i afegeix les sessions
    de gimnàs (o altres) de la setmana tipus del nedador.

    Les sessions que no són de natació són informatives: volum 0, sense parts
    ni contingut LLM, només franja i durada. No es fan el dia de competició ni
    abans de `sessions_des_de`. El resultat s'ordena per dia i franja.
    """
    for sessio in sessions:
        sessio.franja = nedador.franja_natacio(sessio.dia)

    if nedador.setmana_tipus is None:
        return sessions

    for dia in _DIES_ORDRE:
        if dia == microcicle.dia_competicio:
            continue
        if (
            microcicle.sessions_des_de is not None
            and _data_del_dia(microcicle, dia) < microcicle.sessions_des_de
        ):
            continue
        for slot in nedador.slots_dia(dia):
            if slot.modalitat == "natacio":
                continue
            sessions.append(
                Sessio(
                    id=(
                        f"{microcicle.mesocicle_id}_s{microcicle.setmana}_{dia}"
                        f"_{slot.modalitat}_{slot.franja}"
                    ),
                    microcicle_setmana=microcicle.setmana,
                    dia=dia,
                    tipus_sessio=microcicle.tipus_base,
                    volum_total=0,
                    estructura=EstructuraSessio(parts=[]),
                    es_dia_opcional=slot.opcional,
                    notes=f"{ETIQUETA_MODALITAT[slot.modalitat]} (informatiu)",
                    franja=slot.franja,
                    modalitat=slot.modalitat,
                    durada_min=slot.durada_min,
                )
            )

    sessions.sort(key=lambda x: (_DIES_ORDRE[x.dia], ORDRE_FRANJA[x.franja]))
    return sessions

"""Generació de contingut de microcicle amb LLM (Mòdul 6)."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from blondswim.agents import context_competicio, seleccio_model, taper, validacio
from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
from blondswim.models.calendari import Competicio
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Microcicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Exercici, Sessio

logger = logging.getLogger(__name__)

# Límit de tokens de sortida per a cada crida de generació d'UNA sessió.
MAX_TOKENS_SESSIO = 4096


class GeneracioMicrocicleError(Exception):
    """Error en la generació de contingut de microcicle amb LLM."""


def guardar_log_decisio(
    nedador_id: str,
    setmana: int,
    metodologia: DecisioMetodologia,
    microcicle_generat: dict | None = None,
) -> Path:
    """
    Guarda un registre JSON a data/processed/log_decisions/<nedador_id>_<setmana>.json.

    Crea el directori si no existeix. Retorna el Path del fitxer escrit.

    Args:
        nedador_id: ID del nedador
        setmana: Número de setmana
        metodologia: Decisió de metodologia
        microcicle_generat: Dades del microcicle generat (opcional)

    Returns:
        Path del fitxer JSON creat
    """
    # Crear directori si no existeix
    log_dir = Path("data/processed/log_decisions")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Construir nom de fitxer
    fitxer = log_dir / f"{nedador_id}_{setmana}.json"

    # Construir contingut
    log_data = {
        "nedador_id": nedador_id,
        "setmana": setmana,
        "timestamp": datetime.now(UTC).isoformat(),
        "metodologia": metodologia.model_dump(),
        "microcicle_generat": microcicle_generat,
    }

    # Escriure fitxer
    with open(fitxer, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return fitxer


def guardar_log_ajust(
    nedador_id: str,
    setmana: int,
    tipus_ajust: Literal["volum", "classe_competicio", "eliminacio_competicio"],
    valor_anterior: str,
    valor_nou: str,
    motiu: str,
) -> Path:
    """
    Registra un ajust fet amb actualitzar_volum_microcicle(),
    actualitzar_classe_competicio() o eliminar_competicio().

    A diferència de guardar_log_decisio() (que sobreescriu, un registre per
    generació), aquesta AFEGEIX a una llista, perquè hi pot haver diversos
    ajustos sobre la mateixa setmana al llarg de la temporada.

    Guarda/actualitza data/processed/log_decisions/<nedador_id>_<setmana>_ajustos.json,
    una llista de:
    {
      "timestamp": ISO 8601 UTC actual,
      "tipus_ajust": tipus_ajust,
      "valor_anterior": valor_anterior,
      "valor_nou": valor_nou,
      "motiu": motiu
    }
    Si el fitxer ja existeix, llegeix la llista existent i hi afegeix
    l'entrada nova (no sobreescriu els ajustos previs). Crea el directori
    si no existeix. Retorna el Path del fitxer.

    Args:
        nedador_id: ID del nedador
        setmana: Número de setmana
        tipus_ajust: Tipus d'ajust realitzat
        valor_anterior: Valor abans de l'ajust
        valor_nou: Valor després de l'ajust
        motiu: Raó de l'ajust

    Returns:
        Path del fitxer JSON creat/actualitzat
    """
    # Crear directori si no existeix
    log_dir = Path("data/processed/log_decisions")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Construir nom de fitxer
    fitxer = log_dir / f"{nedador_id}_{setmana}_ajustos.json"

    # Llegir llista existent o crear-ne una de nova
    if fitxer.exists():
        with open(fitxer, encoding="utf-8") as f:
            ajustos = json.load(f)
    else:
        ajustos = []

    # Afegir nou ajust
    nou_ajust = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tipus_ajust": tipus_ajust,
        "valor_anterior": valor_anterior,
        "valor_nou": valor_nou,
        "motiu": motiu,
    }
    ajustos.append(nou_ajust)

    # Escriure fitxer actualitzat
    with open(fitxer, "w", encoding="utf-8") as f:
        json.dump(ajustos, f, indent=2, ensure_ascii=False)

    return fitxer


def _extreure_few_shot(
    historial: list[SessioRealitzada],
    metodologia: DecisioMetodologia,
    n: int = 5,
) -> list[str]:
    """
    Retorna com a màxim n strings amb SerieRealitzada.execucio de l'historial.

    Prioritza sèries l'intensitat/objectiu de les quals sigui rellevant per
    metodologia.metodologia_principal (cerca simple per coincidència de paraules clau).
    Si no en troba prou de rellevants, completa amb les últimes sèries disponibles
    cronològicament.

    Args:
        historial: Llista de sessions realitzades
        metodologia: Decisió de metodologia per filtrar rellevància
        n: Nombre màxim d'exemples a retornar

    Returns:
        Llista de strings amb execucio de sèries (màxim n)
    """
    if not historial:
        return []

    # Paraules clau per metodologia (cerca simple)
    paraules_clau = metodologia.metodologia_principal.lower().split()

    # Extreure totes les sèries amb la seva data
    series_amb_data = []
    for sessio in historial:
        for serie in sessio.series:
            if serie.execucio:
                series_amb_data.append({
                    "data": sessio.data,
                    "execucio": serie.execucio,
                    "intensitat": serie.intensitat or "",
                    "objectiu": serie.objectiu or "",
                })

    # Ordenar per data (més recent primer)
    series_amb_data.sort(key=lambda x: x["data"], reverse=True)

    # Filtrar rellevants (intensitat o objectiu conté paraules clau)
    series_rellevants = []
    series_no_rellevants = []

    for serie in series_amb_data:
        text_cerca = f"{serie['intensitat']} {serie['objectiu']}".lower()
        es_rellevant = any(paraula in text_cerca for paraula in paraules_clau)

        if es_rellevant:
            series_rellevants.append(serie["execucio"])
        else:
            series_no_rellevants.append(serie["execucio"])

    # Combinar: primer rellevants, després no rellevants (més recents)
    resultat = series_rellevants[:n]
    if len(resultat) < n:
        resultat.extend(series_no_rellevants[: n - len(resultat)])

    return resultat


def _trobar_microcicle(macrocicle: Macrocicle, setmana: int) -> Microcicle:
    """
    Retorna el Microcicle amb aquesta setmana, cercant a tots els mesocicles.
    
    La numeració de setmanes és global (no reinicia per mesocicle).
    
    Args:
        macrocicle: Macrocicle complet amb tots els mesocicles i microcicles
        setmana: Número de setmana global
        
    Returns:
        Microcicle trobat
        
    Raises:
        ValueError: Si no es troba cap microcicle amb la setmana indicada
    """
    for mesocicle in macrocicle.mesocicles:
        for microcicle in mesocicle.microcicles:
            if microcicle.setmana == setmana:
                return microcicle
    
    raise ValueError(
        f"No s'ha trobat cap microcicle amb setmana={setmana} al macrocicle"
    )


def _recalcular_taper_i_pics(
    competicions: list[Competicio],
) -> tuple[list[dict], list[dict]]:
    """
    Deriva pics_prioritzats (ids amb classe=="A") i retorna (pla_taper, avisos_pics_a).
    
    Args:
        competicions: Llista de competicions del calendari
        
    Returns:
        Tupla amb:
        - Pla de taper (generar_pla_taper_temporada)
        - Avisos de pics A (validar_espaiat_pics_a)
    """
    # Derivar pics prioritzats (totes les competicions classe A)
    pics_prioritzats = [comp.id for comp in competicions if comp.classe == "A"]
    
    # Recalcular pla de taper
    pla_taper = taper.generar_pla_taper_temporada(competicions, pics_prioritzats)
    
    # Recalcular avisos de pics A
    avisos_pics_a = context_competicio.validar_espaiat_pics_a(competicions)
    
    return pla_taper, avisos_pics_a


def actualitzar_classe_competicio(
    competicions: list[Competicio],
    competicio_id: str,
    nova_classe: Literal["A", "B", "C"],
    motiu: str,
) -> tuple[list[Competicio], list[dict], list[dict]]:
    """
    Canvia la classe d'una competició i recalcula automàticament taper i espaiat de pics A.
    
    Aquesta funció permet al coach reclassificar competicions (p.ex. B->C per malaltia,
    o C->B si es decideix prioritzar-la) i obté automàticament els avisos de validació
    actualitzats.
    
    Args:
        competicions: Llista de totes les competicions del calendari
        competicio_id: ID de la competició a actualitzar
        nova_classe: Nova classe (A, B o C)
        motiu: Raó del canvi (per logging/auditoria, no s'usa en el càlcul)
        
    Returns:
        Tupla amb:
        - Llista de competicions actualitzada (mateixa llista mutada)
        - Pla de taper recalculat (generar_pla_taper_temporada)
        - Avisos de pics A recalculats (validar_espaiat_pics_a)
        
    Raises:
        ValueError: Si no es troba cap competició amb el competicio_id indicat
        
    Notes:
        - La classe A defineix automàticament els pics prioritzats (no cal camp addicional)
        - La funció mai bloqueja: sempre retorna, encara que hi hagi avisos
        - El motiu és per traçabilitat futura, no afecta el càlcul
    """
    # 1. Trobar la competició
    competicio = None
    for comp in competicions:
        if comp.id == competicio_id:
            competicio = comp
            break
    
    if not competicio:
        raise ValueError(
            f"No s'ha trobat cap competició amb id={competicio_id}"
        )
    
    # 2. Actualitzar classe
    classe_anterior = competicio.classe
    competicio.classe = nova_classe
    
    logger.info(
        f"Classe competició '{competicio.nom}' actualitzada: "
        f"{classe_anterior} -> {nova_classe}. Motiu: {motiu}"
    )
    
    # 3. Recalcular taper i pics A
    pla_taper, avisos_pics_a = _recalcular_taper_i_pics(competicions)
    
    # 4. Retornar competicions, pla_taper i avisos
    return competicions, pla_taper, avisos_pics_a


def eliminar_competicio(
    competicions: list[Competicio],
    competicio_id: str,
    motiu: str,
) -> tuple[list[Competicio], list[dict], list[dict]]:
    """
    Treu una competició del calendari (p.ex. malaltia, lesió, no hi assistirà).
    
    A diferència d'actualitzar_classe_competicio (que la manté al calendari amb
    menys prioritat), aquesta l'elimina del tot: no compta per a pics_a ni per al taper.
    
    Args:
        competicions: Llista de totes les competicions del calendari
        competicio_id: ID de la competició a eliminar
        motiu: Raó de l'eliminació (per logging/auditoria, no s'usa en el càlcul)
        
    Returns:
        Tupla amb:
        - Llista de competicions actualitzada (sense la competició eliminada)
        - Pla de taper recalculat (generar_pla_taper_temporada)
        - Avisos de pics A recalculats (validar_espaiat_pics_a)
        
    Raises:
        ValueError: Si no es troba cap competició amb el competicio_id indicat
        
    Notes:
        - La funció mai bloqueja: sempre retorna, encara que hi hagi avisos
        - El motiu és per traçabilitat futura, no afecta el càlcul
    """
    # 1. Trobar la competició
    competicio = None
    for comp in competicions:
        if comp.id == competicio_id:
            competicio = comp
            break
    
    if not competicio:
        raise ValueError(
            f"No s'ha trobat cap competició amb id={competicio_id}"
        )
    
    # 2. Eliminar la competició de la llista
    competicions.remove(competicio)
    
    logger.info(
        f"Competició '{competicio.nom}' eliminada del calendari. Motiu: {motiu}"
    )
    
    # 3. Recalcular taper i pics A
    pla_taper, avisos_pics_a = _recalcular_taper_i_pics(competicions)
    
    # 4. Retornar competicions, pla_taper i avisos
    return competicions, pla_taper, avisos_pics_a


def actualitzar_volum_microcicle(
    macrocicle: Macrocicle,
    setmana: int,
    nou_volum_objectiu: int,
    motiu: str,
) -> tuple[Microcicle, list[dict]]:
    """
    Ajusta el volum_objectiu d'un microcicle ja existent (decisió humana del coach).
    
    Aquesta funció permet al coach ajustar manualment el volum d'un microcicle
    i obtenir avisos de validació sobre l'impacte en la progressió de càrrega.
    No regenera sessions ni contingut LLM.
    
    Args:
        macrocicle: Macrocicle complet amb tots els mesocicles i microcicles
        setmana: Número de setmana global del microcicle a actualitzar
        nou_volum_objectiu: Nou volum objectiu en metres
        motiu: Raó de l'ajust (per logging/auditoria)
        
    Returns:
        Tupla amb:
        - Microcicle actualitzat
        - Llista d'avisos de validar_progressio_volum()
        
    Raises:
        ValueError: Si no es troba cap microcicle amb la setmana indicada
    """
    # 1. Trobar el microcicle
    microcicle = _trobar_microcicle(macrocicle, setmana)
    
    # 2. Actualitzar volum
    volum_anterior = microcicle.volum_objectiu
    microcicle.volum_objectiu = nou_volum_objectiu
    
    logger.info(
        f"Volum microcicle setmana {setmana} actualitzat: "
        f"{volum_anterior}m -> {nou_volum_objectiu}m. Motiu: {motiu}"
    )
    
    # 3. Recollir tots els microcicles i validar progressió
    tots_microcicles = []
    for mesocicle in macrocicle.mesocicles:
        tots_microcicles.extend(mesocicle.microcicles)
    
    # Ordenar per setmana
    tots_microcicles.sort(key=lambda m: m.setmana)
    
    # Validar progressió de volum
    avisos = validacio.validar_progressio_volum(tots_microcicles)
    
    # 4. Retornar microcicle i avisos
    return microcicle, avisos


def generar_i_validar_microcicle(
    nedador: Nedador,
    macrocicle: Macrocicle,
    setmana: int,
    metodologia: DecisioMetodologia,
    pla_taper: list[dict],
    avisos_pics_a: list[dict],
    historial: list[SessioRealitzada] | None = None,
) -> tuple[list[Sessio], list[dict]]:
    """
    Genera contingut per a un microcicle específic i valida el macrocicle complet.

    Busca el microcicle corresponent a la setmana indicada, genera l'esquelet de
    sessions, omple el contingut amb LLM i valida el macrocicle sencer.

    Args:
        nedador: Nedador amb zones CSS i proves objectiu
        macrocicle: Macrocicle complet amb tots els mesocicles i microcicles
        setmana: Número de setmana global (no reinicia per mesocicle)
        metodologia: Decisió de metodologia del Mòdul 5
        pla_taper: Pla de taper generat per generar_pla_taper_temporada()
        avisos_pics_a: Avisos generats per validar_espaiat_pics_a()
        historial: Historial de sessions realitzades per few-shot (opcional)

    Returns:
        Tupla amb:
        - Llista de sessions generades per a aquesta setmana
        - Llista completa d'avisos de validar_pla_complet()

    Raises:
        ValueError: Si no es troba cap microcicle amb la setmana indicada
        GeneracioMicrocicleError: Si la crida a l'API falla o la resposta és invàlida
    """
    # 1. Buscar el microcicle corresponent a la setmana
    microcicle_trobat = _trobar_microcicle(macrocicle, setmana)

    # 2. Generar esquelet i contingut
    sessions = generar_esquelet_sessions(nedador, microcicle_trobat)
    sessions = generar_microcicle(nedador, sessions, metodologia, historial)

    # 3. Validar el macrocicle complet
    avisos = validacio.validar_pla_complet(
        macrocicle, nedador.categoria, pla_taper, avisos_pics_a
    )

    # 4. Guardar log de decisió (no bloqueja si falla)
    try:
        guardar_log_decisio(nedador.id, setmana, metodologia)
    except OSError as e:
        logger.warning(f"No s'ha pogut guardar log de decisió: {e}")

    # 5. Retornar sessions i avisos
    return sessions, avisos


def generar_contingut_mesocicle(
    nedador: Nedador,
    macrocicle: Macrocicle,
    categoria: Literal["absolut", "master"],
    mesocicle_id: str,
    pla_taper: list[dict],
    avisos_pics_a: list[dict],
    historial: list[SessioRealitzada] | None = None,
) -> tuple[dict[int, list[Sessio]], list[dict]]:
    """
    Genera contingut LLM per a totes les setmanes d'UN mesocicle concret
    (no tot el macrocicle — evita disparar una crida API per cada una de
    les ~20 setmanes de la temporada de cop; el coach crida aquesta funció
    mesocicle a mesocicle a mesura que avança la temporada).

    1. Troba el Mesocicle amb aquest id a macrocicle.mesocicles. Raise
       ValueError si no existeix.
    2. Per cada Microcicle del mesocicle (ordenats per setmana):
       a. seleccionar_metodologia() per triar la metodologia d'aquella
          setmana (usa el primer element de nedador.proves_objectiu).
       b. Crida generar_i_validar_microcicle(nedador, macrocicle,
          microcicle.setmana, metodologia, pla_taper, avisos_pics_a,
          historial).
       c. Si crida (b) llança GeneracioMicrocicleError o ValueError,
          NO aturis el mesocicle sencer: guarda l'error en una llista
          {"setmana": ..., "error": str(excepcio)} i continua amb la
          setmana següent.
    3. Retorna (resultats, errors) on resultats és un dict
       {setmana: list[Sessio]} amb NOMÉS les setmanes que han generat bé,
       i errors és la llista de dicts del punt 2c (buida si tot ha anat bé).

    Args:
        nedador: Nedador amb zones CSS i proves objectiu
        macrocicle: Macrocicle complet amb tots els mesocicles i microcicles
        categoria: Categoria del nedador (absolut o master)
        mesocicle_id: ID del mesocicle a generar
        pla_taper: Pla de taper generat per generar_pla_taper_temporada()
        avisos_pics_a: Avisos generats per validar_espaiat_pics_a()
        historial: Historial de sessions realitzades per few-shot (opcional)

    Returns:
        Tupla amb:
        - Diccionari {setmana: list[Sessio]} amb les setmanes generades correctament
        - Llista d'errors {"setmana": int, "error": str} per les setmanes que han fallat

    Raises:
        ValueError: Si no es troba cap mesocicle amb el mesocicle_id indicat
    """
    # 1. Trobar el mesocicle
    mesocicle = None
    for meso in macrocicle.mesocicles:
        if meso.id == mesocicle_id:
            mesocicle = meso
            break

    if not mesocicle:
        raise ValueError(
            f"No s'ha trobat cap mesocicle amb id={mesocicle_id} al macrocicle"
        )

    # 2. Generar contingut per a cada microcicle
    resultats: dict[int, list[Sessio]] = {}
    errors: list[dict] = []

    # Ordenar microcicles per setmana
    microcicles_ordenats = sorted(mesocicle.microcicles, key=lambda m: m.setmana)

    # Seleccionar metodologia UNA sola vegada per al mesocicle sencer
    # (la prova objectiu no canvia dins d'un mesocicle; evita una crida
    # API redundant per setmana).
    prova_objectiu = nedador.proves_objectiu[0] if nedador.proves_objectiu else "200m lliure"
    metodologia = seleccio_model.seleccionar_metodologia(
        nedador=nedador,
        prova_objectiu=prova_objectiu,
        categoria=categoria,
        enriquir_amb_llm=True,
    )

    for microcicle in microcicles_ordenats:
        setmana = microcicle.setmana

        # R5: no generar sessions de dies anteriors a sessions_des_de
        if microcicle.sessions_des_de is not None and not generar_esquelet_sessions(
            nedador, microcicle
        ):
            logger.info(
                f"Setmana {setmana}: cap dia a partir de "
                f"{microcicle.sessions_des_de.isoformat()}, s'omet"
            )
            continue

        try:
            # Generar i validar microcicle
            sessions, _avisos = generar_i_validar_microcicle(
                nedador=nedador,
                macrocicle=macrocicle,
                setmana=setmana,
                metodologia=metodologia,
                pla_taper=pla_taper,
                avisos_pics_a=avisos_pics_a,
                historial=historial,
            )

            # Guardar resultat
            resultats[setmana] = sessions

            logger.info(f"Setmana {setmana} generada correctament")

        except (GeneracioMicrocicleError, ValueError) as e:
            # c. Guardar error i continuar
            errors.append({
                "setmana": setmana,
                "error": str(e),
            })
            logger.error(f"Error generant setmana {setmana}: {e}")

    # 3. Retornar resultats i errors
    return resultats, errors


def _construir_tools_sessio() -> list[dict]:
    """Tool schema per a la generació del contingut d'UNA sola sessió."""
    return [
        {
            "name": "retornar_contingut_sessio",
            "description": (
                "Retorna el contingut generat per a cada part d'UNA sessió, com a "
                "llista d'exercicis estructurats. El volum (series x distancia_m) i "
                "el ritme (intensitat) mai s'escriuen com a text lliure ni com a "
                "números decimals."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sessio_id": {"type": "string"},
                    "parts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nom": {"type": "string"},
                                "exercicis": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "series": {"type": "integer"},
                                            "distancia_m": {
                                                "type": "integer",
                                                "enum": [
                                                    25, 50, 75, 100, 150, 200,
                                                    250, 300, 400, 500, 600, 800,
                                                ],
                                            },
                                            "execucio": {"type": "string"},
                                            "descans": {"type": "string"},
                                            "material": {"type": "string"},
                                            "intensitat": {
                                                "type": "string",
                                                "enum": [
                                                    "Recuperació",
                                                    "A1",
                                                    "A2",
                                                    "A3",
                                                    "Velocitat",
                                                    "MPLA",
                                                    "TOLA",
                                                    "AeM",
                                                ],
                                            },
                                            "objectiu": {"type": "string"},
                                        },
                                        "required": ["series", "distancia_m", "execucio"],
                                    },
                                },
                            },
                            "required": ["nom", "exercicis"],
                        },
                    },
                },
                "required": ["parts"],
            },
        }
    ]


def _resum_sessions_generades(sessions: list[Sessio]) -> str:
    """
    Resum curt (~150 tokens) de les sessions ja generades de la setmana:
    dia, conjunt principal i intensitats, per evitar repetir el mateix.
    """
    linies = []
    for sessio in sessions:
        if not any(part.exercicis for part in sessio.estructura.parts):
            continue
        # Conjunt principal: la part amb més volum
        part_principal = None
        volum_max = -1
        for part in sessio.estructura.parts:
            volum = sum(ex.volum_m for ex in part.exercicis)
            if volum > volum_max:
                volum_max = volum
                part_principal = part
        if part_principal is None:
            continue
        intensitats = sorted(
            {ex.intensitat for ex in part_principal.exercicis if ex.intensitat}
        )
        execucions = "; ".join(
            ex.execucio for ex in part_principal.exercicis[:3] if ex.execucio
        )
        linies.append(
            f"- {sessio.dia} ({sessio.tipus_sessio}): {part_principal.nom} "
            f"[{', '.join(intensitats) or 'N/A'}] {execucions}"
        )
    return "\n".join(linies) if linies else "(cap sessió generada encara)"


def _volum_objectiu_sessio(sessions: list[Sessio]) -> int:
    """Volum objectiu per sessió: total de la setmana / n sessions, a múltiple de 25."""
    volum_total = sum(s.volum_total for s in sessions)
    return round(volum_total / len(sessions) / 25) * 25


def _cridar_api_sessio(client, prompt: str, tools: list[dict]):
    """Fa una crida a l'API per generar el contingut d'una sessió."""
    return client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=MAX_TOKENS_SESSIO,
        tools=tools,
        tool_choice={"type": "tool", "name": "retornar_contingut_sessio"},
        messages=[{"role": "user", "content": prompt}],
    )


def _extreure_tool_use_sessio(response) -> dict | None:
    """Retorna l'input del tool_use 'retornar_contingut_sessio', o None."""
    for block in response.content:
        if block.type == "tool_use" and block.name == "retornar_contingut_sessio":
            return block.input
    return None


def _extreure_parts(sessio_data: dict) -> list[dict]:
    """
    Retorna la llista de parts del tool_use, tolerant a formats inesperats.

    Si "parts" és un string JSON, el deserialitza. Si no és una llista,
    retorna una llista buida.
    """
    parts = sessio_data.get("parts")
    if isinstance(parts, str):
        try:
            parts = json.loads(parts)
        except json.JSONDecodeError:
            logger.warning("El camp 'parts' és un string no parsejable com a JSON")
            return []
    if not isinstance(parts, list):
        return []
    return parts


def _arrodonir_distancia_25(distancia_m: int) -> int:
    """Arrodoneix a múltiple de 25 (mínim 25)."""
    return max(25, round(distancia_m / 25) * 25)


def _aplicar_contingut_sessio(sessio: Sessio, sessio_data: dict, setmana: int) -> None:
    """Aplica els exercicis del tool_use a les parts de la sessió."""
    for part_data in _extreure_parts(sessio_data):
        nom_part = part_data.get("nom")
        exercicis_data = part_data.get("exercicis", [])

        part = next((p for p in sessio.estructura.parts if p.nom == nom_part), None)
        if not part:
            logger.warning(
                f"Part '{nom_part}' no trobada a sessió '{sessio.id}', ignorant. "
                f"Noms esperats: {[p.nom for p in sessio.estructura.parts]}"
            )
            continue

        exercicis = []
        n_rebuts = len(exercicis_data)
        n_descartats = 0
        for ex_data in exercicis_data:
            distancia = ex_data.get("distancia_m")
            if isinstance(distancia, int) and distancia % 25 != 0:
                arrodonida = _arrodonir_distancia_25(distancia)
                logger.info(
                    f"Setmana {setmana}, sessió '{sessio.id}', part '{nom_part}': "
                    f"distancia_m={distancia} no és múltiple de 25, "
                    f"arrodonida a {arrodonida}"
                )
                ex_data = {**ex_data, "distancia_m": arrodonida}
            try:
                exercicis.append(Exercici(**ex_data))
            except ValidationError as e:
                n_descartats += 1
                logger.warning(
                    f"Exercici invàlid a sessió '{sessio.id}', part '{nom_part}', ignorat: {e}"
                )
        part.exercicis = exercicis

        logger.info(
            f"Setmana {setmana}, sessió '{sessio.id}', part '{nom_part}': "
            f"exercicis rebuts={n_rebuts}, vàlids={len(exercicis)}, "
            f"descartats={n_descartats}"
        )


def generar_microcicle(
    nedador: Nedador,
    sessions: list[Sessio],
    metodologia: DecisioMetodologia,
    historial: list[SessioRealitzada] | None = None,
) -> list[Sessio]:
    """
    Generar contingut de microcicle amb LLM, UNA crida per sessió.

    Omple el camp exercicis de cada PartSessio de cada Sessio utilitzant l'API
    de Claude amb tool-use forçat. NO modifica percentatges, volums, tipus, dies ni IDs.

    Per cada sessió:
    - Es fa una crida independent (evita truncar per max_tokens en setmanes
      amb moltes sessions).
    - Si stop_reason == "max_tokens", es reintenta UNA vegada amb la instrucció
      de ser més concís (màxim 3 exercicis per part). Si torna a fallar, s'emet
      un WARNING i la sessió queda buida (no es llança excepció).
    - Es passa un resum de les sessions ja generades de la setmana per evitar
      repetir el mateix conjunt principal.
    - Es passa el volum objectiu de la sessió (total setmana / n sessions,
      múltiple de 25) i s'avisa si el volum generat queda fora del ±10%.

    Args:
        nedador: Nedador amb zones CSS i proves objectiu
        sessions: Llista de sessions amb estructura de parts (exercicis buits)
        metodologia: Decisió de metodologia del Mòdul 5
        historial: Historial de sessions realitzades per few-shot (opcional)

    Returns:
        Llista de sessions amb contingut omplert (mateixa llista mutada)

    Raises:
        GeneracioMicrocicleError: Si la crida a l'API falla o la resposta és invàlida
    """
    try:
        # Llegir prompt template
        prompt_path = Path(__file__).parent.parent / "prompts" / "generar_microcicle.md"
        with open(prompt_path, encoding="utf-8") as f:
            prompt_template = f.read()

        # Extreure few-shot
        exemples_series = _extreure_few_shot(historial or [], metodologia, n=5)
        exemples_text = (
            "\n".join(f"- {ex}" for ex in exemples_series)
            if exemples_series
            else "(Cap exemple disponible)"
        )

        if not sessions:
            raise GeneracioMicrocicleError("No hi ha sessions per generar contingut")

        setmana = sessions[0].microcicle_setmana
        volum_per_sessio = _volum_objectiu_sessio(sessions)

        client = get_llm_client()
        tools = _construir_tools_sessio()

        for sessio in sessions:
            # Estructura de parts d'aquesta sessió
            estructura_sessions_text = (
                f"\n**Sessió: {sessio.dia.capitalize()} "
                f"(tipus: {sessio.tipus_sessio}, volum: {sessio.volum_total}m)**\n"
            )
            for part in sessio.estructura.parts:
                if sessio.tipus_sessio == "carrega":
                    perc = part.percentatge_carrega
                elif sessio.tipus_sessio == "qualitat":
                    perc = part.percentatge_qualitat
                else:  # descarrega, taper, transicio
                    perc = part.percentatge_descarrega
                volum_part = int(sessio.volum_total * perc / 100)
                estructura_sessions_text += f"  - {part.nom}: {perc}% ({volum_part}m)\n"

            sessions_setmana_text = (
                f"- sessio_id: \"{sessio.id}\" | dia: {sessio.dia} | "
                f"tipus: {sessio.tipus_sessio} | volum_objectiu: {volum_per_sessio}m"
            )

            resum_previ = _resum_sessions_generades(sessions)

            prompt = prompt_template.format(
                proves_objectiu=", ".join(nedador.proves_objectiu),
                categoria=nedador.categoria,
                estil_preferent=nedador.proves_objectiu[0] if nedador.proves_objectiu else "Lliure",
                zona_recuperacio=f"{nedador.ritmes_css.recuperacio:.2f}" if nedador.ritmes_css else "N/A",
                zona_a1=f"{nedador.ritmes_css.a1:.2f}" if nedador.ritmes_css else "N/A",
                zona_a2=f"{nedador.ritmes_css.a2:.2f}" if nedador.ritmes_css else "N/A",
                zona_a3=f"{nedador.ritmes_css.a3:.2f}" if nedador.ritmes_css else "N/A",
                zona_velocitat=f"{nedador.ritmes_css.velocitat:.2f}" if nedador.ritmes_css else "N/A",
                offset_recuperacio_css=f"{nedador.parametres_ritme.offset_recuperacio_css:.1f}",
                offset_a1_css=f"{nedador.parametres_ritme.offset_a1_css:.1f}",
                offset_a2_css=f"{nedador.parametres_ritme.offset_a2_css:.1f}",
                offset_a3_css=f"{nedador.parametres_ritme.offset_a3_css:.1f}",
                setmana=setmana,
                tipus_base=sessio.tipus_sessio,
                volum_objectiu=sessio.volum_total,
                metodologia_principal=metodologia.metodologia_principal,
                metodologies_complementaries=", ".join(metodologia.metodologies_complementaries),
                forca_evidencia=metodologia.forca_evidencia,
                justificacio=metodologia.justificacio,
                estructura_sessions=estructura_sessions_text,
                exemples_series=exemples_text,
                sessions_setmana=sessions_setmana_text,
                resum_sessions_previ=resum_previ,
            )

            # Crida inicial
            response = _cridar_api_sessio(client, prompt, tools)
            usage = getattr(response, "usage", None)
            output_tokens = getattr(usage, "output_tokens", None) if usage else None
            logger.info(
                f"Resposta API setmana {setmana}, sessió '{sessio.id}': "
                f"stop_reason={response.stop_reason}, output_tokens={output_tokens}, "
                f"max_tokens={MAX_TOKENS_SESSIO}"
            )

            # Retry si s'ha truncat per max_tokens
            if response.stop_reason == "max_tokens":
                logger.warning(
                    f"Setmana {setmana}, sessió '{sessio.id}': resposta truncada "
                    f"(max_tokens). Reintentant amb instrucció de concisió."
                )
                prompt_concis = (
                    prompt
                    + "\n\nIMPORTANT: sigues més concís: màxim 3 exercicis per part."
                )
                response = _cridar_api_sessio(client, prompt_concis, tools)
                usage = getattr(response, "usage", None)
                output_tokens = getattr(usage, "output_tokens", None) if usage else None
                logger.info(
                    f"Resposta API (retry) setmana {setmana}, sessió '{sessio.id}': "
                    f"stop_reason={response.stop_reason}, output_tokens={output_tokens}, "
                    f"max_tokens={MAX_TOKENS_SESSIO}"
                )
                if response.stop_reason == "max_tokens":
                    logger.warning(
                        f"Setmana {setmana}, sessió '{sessio.id}': truncada de nou "
                        f"després del retry. Es deixa la sessió buida."
                    )
                    continue

            sessio_data = _extreure_tool_use_sessio(response)
            if not sessio_data:
                logger.warning(
                    f"Setmana {setmana}, sessió '{sessio.id}': resposta sense tool "
                    f"use 'retornar_contingut_sessio'. Es deixa la sessió buida."
                )
                continue

            if not _extreure_parts(sessio_data):
                logger.info(
                    f"Setmana {setmana}, sessió '{sessio.id}': 'parts' buit o absent. "
                    f"Claus rebudes: {list(sessio_data.keys())}. Reintentant."
                )
                response = _cridar_api_sessio(client, prompt, tools)
                sessio_data = _extreure_tool_use_sessio(response)
                if not sessio_data or not _extreure_parts(sessio_data):
                    logger.warning(
                        f"Setmana {setmana}, sessió '{sessio.id}': 'parts' encara "
                        f"buit després del reintent. Es deixa la sessió buida."
                    )
                    continue

            _aplicar_contingut_sessio(sessio, sessio_data, setmana)

            # Verificar volum dins ±10% de l'objectiu
            volum_sessio = sum(
                ex.volum_m for part in sessio.estructura.parts for ex in part.exercicis
            )
            if volum_per_sessio > 0:
                desviacio = abs(volum_sessio - volum_per_sessio) / volum_per_sessio
                if desviacio > 0.10:
                    logger.warning(
                        f"Setmana {setmana}, sessió '{sessio.id}': volum generat "
                        f"{volum_sessio}m fora del ±10% de l'objectiu "
                        f"{volum_per_sessio}m (desviació {desviacio:.1%})"
                    )

        # Verificar que totes les parts tenen contingut (advertir si no)
        for sessio in sessions:
            for part in sessio.estructura.parts:
                if not part.exercicis:
                    logger.warning(
                        f"Part '{part.nom}' de sessió '{sessio.id}' sense contingut assignat"
                    )

        # Log de resum de la setmana
        sessions_sense_contingut = [
            s for s in sessions
            if not any(part.exercicis for part in s.estructura.parts)
        ]
        if sessions_sense_contingut:
            logger.warning(
                f"Setmana {setmana}: {len(sessions_sense_contingut)} sessions sense contingut"
            )
        else:
            logger.info(f"Setmana {setmana} generada correctament")

        return sessions

    except GeneracioMicrocicleError:
        # Re-llançar errors propis
        raise
    except Exception as e:
        # Embolicar qualsevol altre error
        raise GeneracioMicrocicleError(
            f"Error en generar contingut de microcicle: {e}"
        ) from e

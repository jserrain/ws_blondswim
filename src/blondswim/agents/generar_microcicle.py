"""Generació de contingut de microcicle amb LLM (Mòdul 6)."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from blondswim.agents import context_competicio, seleccio_model, taper, validacio
from blondswim.agents.esquelet_sessions import generar_esquelet_sessions
from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
from blondswim.models.calendari import Competicio
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Microcicle
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Exercici, Sessio
from pydantic import ValidationError

logger = logging.getLogger(__name__)


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

    for microcicle in microcicles_ordenats:
        setmana = microcicle.setmana

        try:
            # a. Seleccionar metodologia per aquesta setmana
            prova_objectiu = nedador.proves_objectiu[0] if nedador.proves_objectiu else "200m lliure"
            metodologia = seleccio_model.seleccionar_metodologia(
                nedador=nedador,
                prova_objectiu=prova_objectiu,
                categoria=categoria,
                enriquir_amb_llm=True,
            )

            # b. Generar i validar microcicle
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


def generar_microcicle(
    nedador: Nedador,
    sessions: list[Sessio],
    metodologia: DecisioMetodologia,
    historial: list[SessioRealitzada] | None = None,
) -> list[Sessio]:
    """
    Generar contingut de microcicle amb LLM.

    Omple el camp contingut de cada PartSessio de cada Sessio utilitzant l'API
    de Claude amb tool-use forçat. NO modifica percentatges, volums, tipus, dies ni IDs.

    Args:
        nedador: Nedador amb zones CSS i proves objectiu
        sessions: Llista de sessions amb estructura de parts (contingut=None)
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
        exemples_text = "\n".join(f"- {ex}" for ex in exemples_series) if exemples_series else "(Cap exemple disponible)"

        # Deduir dades del microcicle a partir de les sessions
        if not sessions:
            raise GeneracioMicrocicleError("No hi ha sessions per generar contingut")

        setmana = sessions[0].microcicle_setmana
        tipus_base = sessions[0].tipus_sessio  # Aproximació: usar el tipus de la primera sessió
        volum_objectiu = sum(s.volum_total for s in sessions)

        # Construir estructura de sessions per al prompt
        estructura_sessions_text = ""
        for sessio in sessions:
            estructura_sessions_text += f"\n**Sessió: {sessio.dia.capitalize()} (tipus: {sessio.tipus_sessio}, volum: {sessio.volum_total}m)**\n"
            for part in sessio.estructura.parts:
                # Determinar percentatge segons tipus_sessio
                if sessio.tipus_sessio == "carrega":
                    perc = part.percentatge_carrega
                elif sessio.tipus_sessio == "qualitat":
                    perc = part.percentatge_qualitat
                else:  # descarrega, taper, transicio
                    perc = part.percentatge_descarrega

                volum_part = int(sessio.volum_total * perc / 100)
                estructura_sessions_text += f"  - {part.nom}: {perc}% ({volum_part}m)\n"

        # Construir llista de sessions per al placeholder {sessions_setmana}
        sessions_setmana_text = "\n".join(
            f"- sessio_id: \"{s.id}\" | dia: {s.dia} | tipus: {s.tipus_sessio} | volum: {s.volum_total}m"
            for s in sessions
        )

        # Omplir prompt
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
            tipus_base=tipus_base,
            volum_objectiu=volum_objectiu,
            metodologia_principal=metodologia.metodologia_principal,
            metodologies_complementaries=", ".join(metodologia.metodologies_complementaries),
            forca_evidencia=metodologia.forca_evidencia,
            justificacio=metodologia.justificacio,
            estructura_sessions=estructura_sessions_text,
            exemples_series=exemples_text,
            sessions_setmana=sessions_setmana_text,
        )

        # Definir tool per forçar resposta estructurada
        tools = [
            {
                "name": "retornar_contingut_sessions",
                "description": "Retorna el contingut generat per a cada part de cada sessió, com a llista d'exercicis estructurats. El volum (series x distancia_m) i el ritme (intensitat) mai s'escriuen com a text lliure ni com a números decimals.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sessions": {
                            "type": "array",
                            "items": {
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
                                                            "distancia_m": {"type": "integer"},
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
                                "required": ["sessio_id", "parts"],
                            },
                        }
                    },
                    "required": ["sessions"],
                },
            }
        ]

        # Cridar API
        client = get_llm_client()
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            tools=tools,
            tool_choice={"type": "tool", "name": "retornar_contingut_sessions"},
            messages=[{"role": "user", "content": prompt}],
        )

        # Parsejar resposta
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "retornar_contingut_sessions":
                tool_use_block = block
                break

        if not tool_use_block:
            raise GeneracioMicrocicleError(
                "Resposta LLM sense tool use esperat 'retornar_contingut_sessions'"
            )

        sessions_data = tool_use_block.input.get("sessions", [])

        # Aplicar contingut a les sessions originals
        for sessio_data in sessions_data:
            sessio_id = sessio_data.get("sessio_id")
            parts_data = sessio_data.get("parts", [])

            # Buscar sessió corresponent
            sessio = next((s for s in sessions if s.id == sessio_id), None)
            if not sessio:
                logger.warning(f"Sessió amb ID '{sessio_id}' no trobada, ignorant")
                continue

            # Aplicar exercicis a cada part
            for part_data in parts_data:
                nom_part = part_data.get("nom")
                exercicis_data = part_data.get("exercicis", [])

                # Buscar part corresponent
                part = next((p for p in sessio.estructura.parts if p.nom == nom_part), None)
                if not part:
                    logger.warning(
                        f"Part '{nom_part}' no trobada a sessió '{sessio_id}', ignorant"
                    )
                    continue

                exercicis = []
                for ex_data in exercicis_data:
                    try:
                        exercicis.append(Exercici(**ex_data))
                    except ValidationError as e:
                        logger.warning(
                            f"Exercici invàlid a sessió '{sessio_id}', part '{nom_part}', ignorat: {e}"
                        )
                part.exercicis = exercicis

        # Verificar que totes les parts tenen contingut (advertir si no)
        for sessio in sessions:
            for part in sessio.estructura.parts:
                if part.contingut is None:
                    logger.warning(
                        f"Part '{part.nom}' de sessió '{sessio.id}' sense contingut assignat"
                    )

        return sessions

    except GeneracioMicrocicleError:
        # Re-llançar errors propis
        raise
    except Exception as e:
        # Embolicar qualsevol altre error
        raise GeneracioMicrocicleError(
            f"Error en generar contingut de microcicle: {e}"
        ) from e

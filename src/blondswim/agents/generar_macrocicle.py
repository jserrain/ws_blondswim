"""Generació de macrocicles a partir del calendari de competicions."""

import logging
from datetime import date, timedelta

from blondswim.agents import context_competicio, periodificacio
from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
from blondswim.models.calendari import Competicio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Mesocicle, Microcicle
from blondswim.models.nedador import Nedador

logger = logging.getLogger(__name__)

PERCENTATGES_VOLUM_PER_TIPUS: dict[str, float] = {
    "Base": 1.0,
    "Build1": 0.95,
    "Build2": 0.85,
    "Peak": 0.5,
    "Transicio": 0.4,
    "Cursa": 0.35,
}


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


def _enriquir_fase_objectiu_amb_llm(
    mesocicle: Mesocicle,
    nedador_id: str,
) -> str:
    """
    Enriquir la fase_objectiu amb una crida a l'API de Claude.

    Utilitza tool-use forçat perquè la resposta sigui exclusivament
    {"fase_objectiu": str}. L'LLM NO pot canviar cap altre camp del mesocicle,
    només ampliar i personalitzar la descripció de la fase basant-se en el context.

    Args:
        mesocicle: Mesocicle amb fase_objectiu determinista ja assignada
        nedador_id: ID del nedador per al qual es genera el mesocicle

    Returns:
        Fase objectiu enriquida (o la original si hi ha error)
    """
    try:
        client = get_llm_client()

        # Definir tool per forçar resposta estructurada
        tools = [
            {
                "name": "retornar_fase_objectiu",
                "description": (
                    "Retorna una descripció ampliada i personalitzada de la fase "
                    "objectiu del mesocicle."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "fase_objectiu": {
                            "type": "string",
                            "description": (
                                "Descripció ampliada de la fase objectiu que explica "
                                "els objectius específics d'aquest mesocicle, mantenint "
                                "el tipus de fase ja decidit."
                            ),
                        }
                    },
                    "required": ["fase_objectiu"],
                },
            }
        ]

        # Construir prompt
        prompt = f"""Ets un expert en periodització d'entrenament de natació.

CONTEXT DEL MESOCICLE:
- Nom: {mesocicle.nom}
- Setmanes: {mesocicle.setmanes}
- Dates: {mesocicle.dates}
- Fase objectiu actual: {mesocicle.fase_objectiu}

TASCA:
Amplia i personalitza la descripció de la fase objectiu per a aquest mesocicle.
NO canviïs el tipus de fase (Base/Build1/Build2/Peak/Cursa/Transicio), només
explica millor els objectius específics d'aquesta fase considerant:
- La posició dins la temporada
- Els objectius típics d'aquesta fase de periodització
- La progressió esperada cap a la competició

Mantén un to professional i concís (màxim 2-3 frases).

Retorna NOMÉS la descripció ampliada usant la tool retornar_fase_objectiu."""

        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            tools=tools,
            tool_choice={"type": "tool", "name": "retornar_fase_objectiu"},
            messages=[{"role": "user", "content": prompt}],
        )

        # Extreure fase_objectiu del tool use
        for block in response.content:
            if block.type == "tool_use" and block.name == "retornar_fase_objectiu":
                if isinstance(block.input, dict) and "fase_objectiu" in block.input:
                    return block.input["fase_objectiu"]
                else:
                    logger.warning(
                        f"Tool use block sense clau 'fase_objectiu'. "
                        f"Contingut rebut: {block.input}. Usant fase_objectiu original."
                    )
                    return mesocicle.fase_objectiu

        # Si no trobem tool use vàlid, fallback
        logger.warning(
            "Resposta LLM sense tool use vàlid. Usant fase_objectiu original."
        )
        return mesocicle.fase_objectiu

    except Exception as e:  # noqa: BLE001 — fallback intencionat
        logger.warning(
            f"Error en enriquir fase_objectiu amb LLM: {e}. "
            f"Usant fase_objectiu original."
        )
        return mesocicle.fase_objectiu


def _calcular_volums_mesocicle(
    nedador: Nedador,
    historial: list[SessioRealitzada],
    tipus: str,
    percentatges: dict[str, float] = PERCENTATGES_VOLUM_PER_TIPUS,
) -> tuple[int, int, int]:
    """
    Calcula (volum_min, volum_max, volum_mitja_previst) per un mesocicle
    d'un tipus donat.

    volum_per_sessio = mitjana de SessioRealitzada.volum_total_m sobre
    tot l'històric rebut (si l'històric és buit, retorna (0, 0, 0)).

    volum_min = volum_per_sessio * len(nedador.dies_disponibles)
    volum_max = volum_per_sessio * (len(nedador.dies_disponibles) + 1)
      si nedador.dia_opcional no és None, altrament volum_max = volum_min
    volum_mitja_previst = mitjana(volum_min, volum_max)

    Tots tres valors multiplicats pel percentatges.get(tipus, 1.0)
    corresponent, i arrodonits a enter.
    """
    if not historial:
        return 0, 0, 0

    volum_per_sessio = sum(s.volum_total_m for s in historial) / len(historial)

    dies_base = len(nedador.dies_disponibles)
    volum_min = volum_per_sessio * dies_base
    if nedador.dia_opcional is not None:
        volum_max = volum_per_sessio * (dies_base + 1)
    else:
        volum_max = volum_min
    volum_mitja_previst = (volum_min + volum_max) / 2

    factor = percentatges.get(tipus, 1.0)

    return (
        round(volum_min * factor),
        round(volum_max * factor),
        round(volum_mitja_previst * factor),
    )


def _interpolar_volum(volum_inici: int, volum_fi: int, index: int, total: int) -> int:
    """Interpolació lineal entre volum_inici i volum_fi en total passos."""
    if total <= 1:
        return volum_fi
    return round(volum_inici + (volum_fi - volum_inici) * index / (total - 1))


def _format_dates(dilluns: date, diumenge: date) -> str:
    """Format de dates d'un microcicle: 'DD-DD/MM/YYYY' o 'DD/MM-DD/MM/YYYY'."""
    if dilluns.month == diumenge.month:
        return f"{dilluns:%d}-{diumenge:%d}/{diumenge:%m}/{diumenge:%Y}"
    return f"{dilluns:%d/%m}-{diumenge:%d/%m}/{diumenge:%Y}"


def _tipus_base_i_notes(
    plan: periodificacio.SetmanaPlan,
    es_base: bool,
    es_primer_del_bloc: bool,
) -> tuple[str, str, bool, bool]:
    """
    Deriva (tipus_base, notes, dies_qualitat, test_css) d'un SetmanaPlan.

    - Base/Build1/Build2: carrega/qualitat, descàrrega a l'última setmana del bloc.
    - Peak: taper. Cursa: taper. Transicio: transicio.
    """
    fase = plan.fase

    if fase in ("Base", "Build1", "Build2"):
        if plan.es_descarrega:
            return "descarrega", "Descàrrega", not es_base, False
        tipus = "carrega" if es_base else "qualitat"
        etiqueta = "Càrrega" if es_base else "Qualitat"
        test_css = es_base and es_primer_del_bloc
        notes = f"{etiqueta} + Test CSS" if test_css else etiqueta
        return tipus, notes, not es_base, test_css

    if fase == "Peak":
        return "taper", "Taper", True, False

    if fase == "Cursa":
        return "taper", "Setmana de competició", True, False

    # Transicio
    return "transicio", "Recuperació post-competició", False, False


def _volum_setmana(
    plan: periodificacio.SetmanaPlan,
    mesocicle: Mesocicle,
    n_setmanes_bloc: int,
) -> int:
    """
    Volum objectiu d'una setmana del bloc, amb R4 (proves B) aplicat.

    - Descàrrega: 70% de volum_min.
    - Base/Build1/Build2 (càrrega): interpolació min->max dins el bloc.
    - Peak: interpolació max->min (decreixent cap a la cursa).
    - Cursa/Transicio: volum_mitja_previst.
    """
    fase = plan.fase

    if fase in ("Base", "Build1", "Build2"):
        if plan.es_descarrega:
            volum = round(mesocicle.volum_min * 0.7)
        else:
            n_carrega = max(1, n_setmanes_bloc - 1)
            if n_carrega == 1:
                volum = mesocicle.volum_max
            else:
                volum = _interpolar_volum(
                    mesocicle.volum_min,
                    mesocicle.volum_max,
                    plan.index_dins_bloc,
                    n_carrega,
                )
    elif fase == "Peak":
        if n_setmanes_bloc <= 1:
            volum = mesocicle.volum_mitja_previst
        else:
            volum = _interpolar_volum(
                mesocicle.volum_max,
                mesocicle.volum_min,
                plan.index_dins_bloc,
                n_setmanes_bloc,
            )
    else:  # Cursa, Transicio
        volum = mesocicle.volum_mitja_previst

    # R4: setmana amb prova B -> volum x 0.8 (o el mínim si és descàrrega).
    te_prova_b = any(c.classe == "B" for c in plan.competicions_b_c)
    if te_prova_b:
        volum_b = round(volum * 0.8)
        if plan.es_descarrega:
            volum = min(volum, volum_b)
        else:
            volum = volum_b

    return volum


def generar_microcicles_mesocicle(
    mesocicle: Mesocicle,
    plans: list[periodificacio.SetmanaPlan],
    sessions_des_de: date | None = None,
) -> list[Microcicle]:
    """
    Genera la llista de Microcicle (una per setmana) d'un mesocicle a partir
    dels SetmanaPlan del seu bloc.

    Args:
        mesocicle: Mesocicle amb tipus i volums ja fixats
        plans: SetmanaPlan del bloc d'aquest mesocicle (ordenats)
        sessions_des_de: Data a partir de la qual es generaran sessions
            (només s'assigna al primer microcicle)

    Returns:
        Llista de Microcicle ordenada per setmana ascendent
    """
    if mesocicle.tipus is None:
        raise ValueError(
            f"Mesocicle {mesocicle.id} no té tipus assignat; "
            "generar_microcicles_mesocicle() només funciona amb mesocicles "
            "creats per generar_mesocicle()"
        )

    es_base = mesocicle.tipus == "Base"
    n_setmanes_bloc = len(plans)

    microcicles: list[Microcicle] = []
    for i, plan in enumerate(plans):
        es_primer_del_bloc = plan.index_dins_bloc == 0
        tipus_base, notes, dies_qualitat, test_css = _tipus_base_i_notes(
            plan, es_base, es_primer_del_bloc
        )
        volum = _volum_setmana(plan, mesocicle, n_setmanes_bloc)

        microcicles.append(
            Microcicle(
                setmana=plan.setmana_iso,
                dates=_format_dates(plan.dilluns, plan.diumenge),
                mesocicle_id=mesocicle.id,
                tipus_base=tipus_base,
                notes=notes,
                volum_objectiu=volum,
                dies_qualitat=dies_qualitat,
                test_css=test_css,
                sessions_des_de=sessions_des_de if i == 0 else None,
            )
        )

    return microcicles


def generar_mesocicle(
    nedador: Nedador,
    macrocicle: Macrocicle,
    competicions: list[Competicio],
    enriquir_amb_llm: bool = True,
    historial: list[SessioRealitzada] | None = None,
    data_referencia: date | None = None,
    dies_marge: int = 1,
) -> tuple[Mesocicle, list[dict]]:
    """
    Genera UN sol mesocicle: el bloc que conté la data de referència + marge.

    1. Calcula inici_generacio = data_referencia + dies_marge dies
       (data_referencia = date.today() si és None).
    2. Crida periodificar_temporada() UNA vegada per obtenir tots els
       SetmanaPlan de la temporada.
    3. Busca el bloc que conté inici_generacio i construeix el Mesocicle
       (tipus = fase del bloc) i els seus Microcicles.
    4. El primer microcicle del bloc porta sessions_des_de = inici_generacio.
    5. Si enriquir_amb_llm=True, enriqueix fase_objectiu amb LLM (fallback
       silenciós si l'API falla).

    Args:
        nedador: Nedador per al qual es genera el mesocicle
        macrocicle: Macrocicle al qual afegir el mesocicle
        competicions: Llista de totes les competicions del calendari
        enriquir_amb_llm: Si True, enriquir fase_objectiu amb LLM (default: True)
        historial: Historial de sessions realitzades per estimar volums (default: None)
        data_referencia: Data de referència (default: None -> date.today())
        dies_marge: Dies de marge afegits a data_referencia (default: 1)

    Returns:
        Tupla amb:
        - Mesocicle generat i afegit al macrocicle
        - Llista d'avisos

    Raises:
        ValueError: Si la data de referència cau fora de la temporada
    """
    avisos: list[dict] = []
    historial = historial or []

    if data_referencia is None:
        data_referencia = periodificacio.avui()

    inici_generacio = data_referencia + timedelta(days=dies_marge)

    data_inici = date.fromisoformat(macrocicle.data_inici)
    data_fi = date.fromisoformat(macrocicle.data_fi)

    # 1. Periodificar la temporada des de la setmana de generació
    #    (les setmanes passades són història, no es replanifiquen).
    inici_finestra = max(
        periodificacio._dilluns_de(data_inici),
        periodificacio._dilluns_de(inici_generacio),
    )
    plans, avisos_periodificacio = periodificacio.periodificar_temporada(
        competicions, inici_finestra, data_fi
    )
    avisos.extend(avisos_periodificacio)

    # 2. Buscar el bloc que conté inici_generacio
    plans_bloc = [p for p in plans if p.dilluns <= inici_generacio <= p.diumenge]
    if not plans_bloc:
        raise ValueError(
            f"La data de referència {inici_generacio.isoformat()} cau fora "
            f"de la temporada ({macrocicle.data_inici} - {macrocicle.data_fi})"
        )

    bloc_id = plans_bloc[0].bloc_id
    plans_bloc = [p for p in plans if p.bloc_id == bloc_id]
    tipus = plans_bloc[0].fase

    # 3. Calcular volums a partir de l'històric
    volum_min, volum_max, volum_mitja_previst = _calcular_volums_mesocicle(
        nedador, historial, tipus
    )
    if not historial:
        avisos.append({
            "tipus_avis": "sense_historial",
            "missatge": "Sense històric del nedador: volums del mesocicle no estimats (0).",
        })

    # 4. Crear Mesocicle
    numero_mesocicle = len(macrocicle.mesocicles) + 1
    mesocicle_id = f"meso_{numero_mesocicle}"

    primer = plans_bloc[0]
    ultim = plans_bloc[-1]
    setmana_inici = primer.setmana_iso
    setmana_fi = ultim.setmana_iso

    mesocicle = Mesocicle(
        id=mesocicle_id,
        nom=f"{tipus} {numero_mesocicle}",
        setmanes=(
            f"{setmana_inici}-{setmana_fi}"
            if setmana_inici != setmana_fi
            else str(setmana_inici)
        ),
        dates=(
            f"{primer.dilluns.strftime('%d/%m/%Y')}-"
            f"{ultim.diumenge.strftime('%d/%m/%Y')}"
        ),
        tipus=tipus,
        fase_objectiu=tipus,
        metodologia_dominant="",
        volum_min=volum_min,
        volum_max=volum_max,
        volum_mitja_previst=volum_mitja_previst,
        microcicles=[],
    )

    # 5. Generar microcicles a partir dels SetmanaPlan del bloc.
    #    sessions_des_de només s'aplica al microcicle que conté inici_generacio.
    mesocicle.microcicles = generar_microcicles_mesocicle(mesocicle, plans_bloc)
    for micro in mesocicle.microcicles:
        plan = next(p for p in plans_bloc if p.setmana_iso == micro.setmana)
        if plan.dilluns <= inici_generacio <= plan.diumenge:
            micro.sessions_des_de = inici_generacio
            break

    # 6. Enriquir fase_objectiu amb LLM si està habilitat
    if enriquir_amb_llm:
        mesocicle.fase_objectiu = _enriquir_fase_objectiu_amb_llm(mesocicle, nedador.id)

    macrocicle.mesocicles.append(mesocicle)

    return mesocicle, avisos

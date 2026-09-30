"""Generació de macrocicles a partir del calendari de competicions."""

import logging
from datetime import date

from blondswim.agents import context_competicio, periodificacio, pla_setmanal
from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
from blondswim.models.calendari import Competicio
from blondswim.models.historial import SessioRealitzada
from blondswim.models.macrocicle import Macrocicle, Mesocicle, Microcicle
from blondswim.models.nedador import Nedador
from blondswim.utils.dates import seguent_dilluns

logger = logging.getLogger(__name__)

# Volum setmanal (min, max) per fase de càrrega. La progressió dins la fase
# s'interpola linealment entre min i max al llarg de TOTES les setmanes de
# càrrega de la fase (no per bloc).
# Rangs acordats 2026-09-30 (4 sessions/setmana): càrrega (Base) 13.600-15.000,
# qualitat (Build) 12.000-13.600. Provisionals fins a F3 (base mòbil).
VOLUM_SETMANAL_CARREGA: dict[str, tuple[int, int]] = {
    "Base": (13600, 15000),
    "Build1": (12000, 13600),
    "Build2": (12000, 13600),
}

# Tipus de setmana amb terra de volum (nedador.volum_setmanal_min).
# Taper (Peak/Cursa) i transició NO en tenen (reducció Bosquet 41-60%).
TIPUS_AMB_TERRA: frozenset[str] = frozenset({"carrega", "qualitat", "descarrega"})

# Setmana de descàrrega: -30% respecte la setmana de càrrega anterior del bloc.
FACTOR_DESCARREGA: float = 0.7

# Setmana amb prova B: -20%. Si coincideix amb descàrrega s'aplica el mínim
# dels dos factors (no el producte).
FACTOR_PROVA_B: float = 0.8

# Volum de referència per a les fases de taper/cursa/transició.
VOLUM_REFERENCIA_TAPER: int = 13000

# Factors de taper per setmana de Peak (Bosquet 2007): -40%, -55%.
FACTORS_PEAK: list[float] = [0.60, 0.45]

FACTOR_CURSA: float = 0.5
FACTOR_TRANSICIO: float = 0.5

# Llindar de l'Acute:Chronic Workload Ratio per limitar pics de volum.
ACWR_MAX: float = 1.3


def _arrodonir_a_25(volum: float) -> int:
    """Arrodoneix un volum al múltiple de 25m més proper."""
    return round(volum / 25) * 25


def _volum_carrega_fase(
    fase: str,
    index_carrega: int,
    n_carrega: int,
) -> int:
    """
    Volum d'una setmana de càrrega d'una fase Base/Build1/Build2.

    Interpolació lineal entre el min i el max de la fase al llarg de les
    n_carrega setmanes de càrrega de la fase (index_carrega 0-based).
    """
    vmin, vmax = VOLUM_SETMANAL_CARREGA[fase]
    if n_carrega <= 1:
        # Una sola setmana de càrrega: mínim de la fase (conservador, ACWR).
        return _arrodonir_a_25(vmin)
    volum = vmin + (vmax - vmin) * index_carrega / (n_carrega - 1)
    return _arrodonir_a_25(volum)


def _volum_peak(index_dins_bloc: int) -> int:
    """Volum d'una setmana de Peak segons FACTORS_PEAK (últim factor si cal)."""
    factor = FACTORS_PEAK[min(index_dins_bloc, len(FACTORS_PEAK) - 1)]
    return _arrodonir_a_25(VOLUM_REFERENCIA_TAPER * factor)


def _volum_historic_setmanal(
    historial: list[SessioRealitzada],
) -> dict[tuple[int, int], int]:
    """
    Agrupa l'històric real per setmana ISO i suma el volum total setmanal.

    Retorna {(any_iso, setmana_iso): volum_total_m}.
    """
    setmanes: dict[tuple[int, int], int] = {}
    for sessio in historial:
        try:
            data = date.fromisoformat(sessio.data)
        except (ValueError, TypeError):
            continue
        any_iso, setmana_iso, _ = data.isocalendar()
        clau = (any_iso, setmana_iso)
        setmanes[clau] = setmanes.get(clau, 0) + sessio.volum_total_m
    return setmanes


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
    index_carrega_fase: int,
    n_carrega_fase: int,
    volum_carrega_anterior: int | None,
) -> int:
    """
    Volum objectiu d'una setmana del bloc, amb R4 (proves B) aplicat.

    - Base/Build1/Build2 (càrrega): interpolació min->max de la fase al llarg
      de totes les setmanes de càrrega de la fase.
    - Descàrrega: FACTOR_DESCARREGA × setmana de càrrega anterior del bloc.
    - Peak: VOLUM_REFERENCIA_TAPER × FACTORS_PEAK[index_dins_bloc].
    - Cursa/Transicio: VOLUM_REFERENCIA_TAPER × factor.
    - Prova B: × FACTOR_PROVA_B; si també és descàrrega, min dels dos factors.
    """
    fase = plan.fase

    if fase in ("Base", "Build1", "Build2"):
        if plan.es_descarrega:
            base = volum_carrega_anterior
            if base is None:
                base = _volum_carrega_fase(fase, 0, max(1, n_carrega_fase))
            volum = _arrodonir_a_25(base * FACTOR_DESCARREGA)
        else:
            volum = _volum_carrega_fase(fase, index_carrega_fase, n_carrega_fase)
    elif fase == "Peak":
        volum = _volum_peak(plan.index_dins_bloc)
    elif fase == "Cursa":
        volum = _arrodonir_a_25(VOLUM_REFERENCIA_TAPER * FACTOR_CURSA)
    else:  # Transicio
        volum = _arrodonir_a_25(VOLUM_REFERENCIA_TAPER * FACTOR_TRANSICIO)

    # R4: setmana amb prova B -> volum x FACTOR_PROVA_B (o el mínim si és descàrrega).
    te_prova_b = any(c.classe == "B" for c in plan.competicions_b_c)
    if te_prova_b:
        if plan.es_descarrega:
            factor = min(FACTOR_DESCARREGA, FACTOR_PROVA_B)
            volum = _arrodonir_a_25(volum / FACTOR_DESCARREGA * factor)
        else:
            volum = _arrodonir_a_25(volum * FACTOR_PROVA_B)

    return volum


def generar_microcicles_mesocicle(
    mesocicle: Mesocicle,
    plans: list[periodificacio.SetmanaPlan],
    sessions_des_de: date | None = None,
    plans_fase: list[periodificacio.SetmanaPlan] | None = None,
    volum_setmanal_min: int = 12000,
    avisos: list[dict] | None = None,
    competicions: list[Competicio] | None = None,
) -> list[Microcicle]:
    """
    Genera la llista de Microcicle (una per setmana) d'un mesocicle a partir
    dels SetmanaPlan del seu bloc.

    Args:
        mesocicle: Mesocicle amb tipus ja fixat
        plans: SetmanaPlan del bloc d'aquest mesocicle (ordenats)
        sessions_des_de: Data a partir de la qual es generaran sessions
            (només s'assigna al primer microcicle)
        plans_fase: Tots els SetmanaPlan de la mateixa fase (per interpolar el
            volum de càrrega al llarg de la fase sencera). Si és None, s'usa
            només el bloc.
        volum_setmanal_min: Terra de volum per a setmanes de càrrega, qualitat
            i descàrrega (F2). No s'aplica a taper, transició ni setmanes amb
            prova B (taper B curt).
        avisos: Llista on s'afegeix l'avís "descarrega_insuficient" quan el
            terra aixeca una setmana de descàrrega (es muta si no és None).
        competicions: Calendari (A/B) per classificar cada setmana
            (dia_competicio, post_competicio). La setmana posterior a una
            competició té com a objectiu el mínim setmanal (prioritat:
            recuperació). Si és None, totes les setmanes són normals.

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
    fase = mesocicle.tipus

    # Índex de càrrega dins la fase sencera (per interpolar min->max).
    plans_fase = plans_fase if plans_fase is not None else plans
    plans_carrega_fase = [
        p for p in plans_fase if not p.es_descarrega
    ]
    n_carrega_fase = len(plans_carrega_fase)
    index_carrega_per_setmana = {
        (p.any_iso, p.setmana_iso): i
        for i, p in enumerate(plans_carrega_fase)
    }

    microcicles: list[Microcicle] = []
    volum_carrega_anterior: int | None = None
    for i, plan in enumerate(plans):
        es_primer_del_bloc = plan.index_dins_bloc == 0
        tipus_base, notes, dies_qualitat, test_css = _tipus_base_i_notes(
            plan, es_base, es_primer_del_bloc
        )

        index_carrega = index_carrega_per_setmana.get(
            (plan.any_iso, plan.setmana_iso), 0
        )
        volum = _volum_setmana(
            plan,
            index_carrega,
            n_carrega_fase,
            volum_carrega_anterior,
        )

        dia_competicio, post_competicio = pla_setmanal.classificar_setmana(
            plan.dilluns, competicions or []
        )

        # F2: terra de volum (no taper/transició ni setmanes amb prova B).
        te_prova_b = any(c.classe == "B" for c in plan.competicions_b_c)

        # H: setmana posterior a una competició -> objectiu = mínim setmanal.
        if post_competicio and tipus_base in TIPUS_AMB_TERRA and not te_prova_b:
            volum = _arrodonir_a_25(volum_setmanal_min)

        if (
            tipus_base in TIPUS_AMB_TERRA
            and not te_prova_b
            and volum < volum_setmanal_min
        ):
            if tipus_base == "descarrega" and avisos is not None:
                avisos.append({
                    "tipus_avis": "descarrega_insuficient",
                    "missatge": (
                        f"Setmana {plan.setmana_iso}: la descàrrega ({volum}m) "
                        f"queda sota el mínim ({volum_setmanal_min}m) i s'aixeca "
                        f"al mínim; la descàrrega s'ha de fer per intensitat, "
                        f"no per volum."
                    ),
                })
            volum = _arrodonir_a_25(volum_setmanal_min)

        if fase in ("Base", "Build1", "Build2") and not plan.es_descarrega:
            volum_carrega_anterior = volum

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
                dia_competicio=dia_competicio,
                post_competicio=post_competicio,
            )
        )

    return microcicles


def _aplicar_guard_acwr(
    microcicles: list[Microcicle],
    historial: list[SessioRealitzada],
    avisos: list[dict],
    volum_setmanal_min: int = 0,
) -> None:
    """
    Limita el volum de cada microcicle planificat perquè el ràtio
    agut:crònic (ACWR) no superi ACWR_MAX.

    - crònic = mitjana de volum setmanal de les 4 setmanes anteriors
      (històric real per setmanes passades, planificat per la resta).
    - Si planificat / crònic > ACWR_MAX, es capa a ACWR_MAX × crònic i
      s'afegeix l'avís "acwr_limitat".
    - Si no hi ha prou històric (crònic = 0), s'omet amb avís.
    - Mai retalla per sota de volum_setmanal_min les setmanes amb terra
      (càrrega/qualitat/descàrrega): l'ACWR és un avís, no una regla.
    """
    historic_setmanal = _volum_historic_setmanal(historial)
    if not historic_setmanal:
        avisos.append({
            "tipus_avis": "acwr_omet",
            "missatge": (
                "Sense històric suficient per calcular l'ACWR; "
                "no s'aplica el límit de càrrega aguda:crònica."
            ),
        })
        return

    # Volums planificats per setmana ISO (per consultar les 4 anteriors).
    planificat: dict[tuple[int, int], int] = {}
    for micro in microcicles:
        any_iso = micro.setmana // 100
        setmana_iso = micro.setmana % 100
        planificat[(any_iso, setmana_iso)] = micro.volum_objectiu

    for micro in microcicles:
        any_iso = micro.setmana // 100
        setmana_iso = micro.setmana % 100

        # 4 setmanes anteriors (ISO, restant setmanes correctament).
        anteriors: list[int] = []
        any_c, setm_c = any_iso, setmana_iso
        for _ in range(4):
            setm_c -= 1
            if setm_c < 1:
                any_c -= 1
                setm_c = 52
            clau = (any_c, setm_c)
            if clau in planificat:
                anteriors.append(planificat[clau])
            elif clau in historic_setmanal:
                anteriors.append(historic_setmanal[clau])

        if not anteriors:
            continue

        cronic = sum(anteriors) / len(anteriors)
        if cronic <= 0:
            continue

        limit = _arrodonir_a_25(ACWR_MAX * cronic)
        if micro.tipus_base in TIPUS_AMB_TERRA:
            limit = max(limit, volum_setmanal_min)
        if micro.volum_objectiu > limit:
            micro.volum_objectiu = limit
            avisos.append({
                "tipus_avis": "acwr_limitat",
                "missatge": (
                    f"Setmana {micro.setmana}: volum limitat a {limit}m "
                    f"per ACWR (crònic {round(cronic)}m, màx {ACWR_MAX})."
                ),
            })


def generar_mesocicle(
    nedador: Nedador,
    macrocicle: Macrocicle,
    competicions: list[Competicio],
    enriquir_amb_llm: bool = True,
    historial: list[SessioRealitzada] | None = None,
    data_referencia: date | None = None,
) -> tuple[Mesocicle, list[dict]]:
    """
    Genera UN sol mesocicle: el bloc que conté el primer dia de planificació.

    1. Calcula inici_generacio = seguent_dilluns(data_referencia) (G2):
       la mateixa data si és dilluns, si no el dilluns següent
       (data_referencia = avui si és None). Mai es comença a mitja setmana.
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
        data_referencia: Data de referència (default: None -> avui)

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

    inici_generacio = seguent_dilluns(data_referencia)

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

    # 3. Crear Mesocicle (volums es deriven dels microcicles generats)
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
        volum_min=0,
        volum_max=0,
        volum_mitja_previst=0,
        microcicles=[],
    )

    # 4. Generar microcicles a partir dels SetmanaPlan del bloc.
    #    sessions_des_de només s'aplica al microcicle que conté inici_generacio.
    plans_fase = [p for p in plans if p.fase == tipus]
    mesocicle.microcicles = generar_microcicles_mesocicle(
        mesocicle,
        plans_bloc,
        plans_fase=plans_fase,
        volum_setmanal_min=nedador.volum_setmanal_min,
        avisos=avisos,
        competicions=competicions,
    )
    for micro in mesocicle.microcicles:
        plan = next(p for p in plans_bloc if p.setmana_iso == micro.setmana)
        if plan.dilluns <= inici_generacio <= plan.diumenge:
            micro.sessions_des_de = inici_generacio
            break

    # 5. Guard ACWR sobre els microcicles planificats.
    _aplicar_guard_acwr(
        mesocicle.microcicles, historial, avisos, nedador.volum_setmanal_min
    )

    # 6. Derivar volums del mesocicle a partir dels microcicles.
    volums = [m.volum_objectiu for m in mesocicle.microcicles]
    if volums:
        mesocicle.volum_min = min(volums)
        mesocicle.volum_max = max(volums)
        mesocicle.volum_mitja_previst = _arrodonir_a_25(sum(volums) / len(volums))

    # 7. Enriquir fase_objectiu amb LLM si està habilitat
    if enriquir_amb_llm:
        mesocicle.fase_objectiu = _enriquir_fase_objectiu_amb_llm(mesocicle, nedador.id)

    macrocicle.mesocicles.append(mesocicle)

    return mesocicle, avisos

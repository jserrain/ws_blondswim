"""Generació de macrocicles a partir del calendari de competicions."""

import logging
from datetime import datetime, timedelta

from blondswim.agents import context_competicio
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


def generar_microcicles_mesocicle(
    mesocicle: Mesocicle,
    data_inici_macrocicle: str,
) -> list[Microcicle]:
    """
    Genera la llista de Microcicle (una per setmana) d'un mesocicle ja creat.

    Args:
        mesocicle: Mesocicle amb setmanes ("X-Y"), tipus i volums ja fixats
        data_inici_macrocicle: Data d'inici del macrocicle (format ISO)

    Returns:
        Llista de Microcicle ordenada per setmana ascendent
    """
    if mesocicle.tipus is None:
        raise ValueError(
            f"Mesocicle {mesocicle.id} no té tipus assignat; "
            "generar_microcicles_mesocicle() només funciona amb mesocicles "
            "creats per generar_mesocicle()"
        )

    # 1. Parsejar setmanes
    parts = mesocicle.setmanes.split("-")
    setmana_inici = int(parts[0])
    setmana_fi = int(parts[1]) if len(parts) > 1 else setmana_inici
    n_setmanes = setmana_fi - setmana_inici + 1

    data_inici_macro = datetime.fromisoformat(data_inici_macrocicle)

    # 2. Calcular tipus_base/volum/dies_qualitat/test_css/notes per setmana
    tipus_base_per_setmana: list[str] = []
    volum_per_setmana: list[int] = []
    dies_qualitat_per_setmana: list[bool] = []
    test_css_per_setmana: list[bool] = []
    notes_per_setmana: list[str] = []

    if mesocicle.tipus in ("Base", "Build1", "Build2"):
        es_base = mesocicle.tipus == "Base"
        tipus_carrega = "carrega" if es_base else "qualitat"
        etiqueta_carrega = "Càrrega" if es_base else "Qualitat"

        # Recórrer en blocs de fins a 4 setmanes
        i = 0
        while i < n_setmanes:
            mida_bloc = min(4, n_setmanes - i)
            te_descarrega = mida_bloc == 4
            n_carrega = 3 if te_descarrega else mida_bloc

            for j in range(mida_bloc):
                idx = i + j
                if te_descarrega and j == 3:
                    # Setmana de descàrrega
                    tipus_base_per_setmana.append("descarrega")
                    volum_per_setmana.append(round(mesocicle.volum_min * 0.7))
                    dies_qualitat_per_setmana.append(not es_base)
                    test_css_per_setmana.append(False)
                    notes_per_setmana.append("Descàrrega")
                else:
                    # Setmana de càrrega/qualitat
                    tipus_base_per_setmana.append(tipus_carrega)
                    if n_carrega == 1:
                        volum = mesocicle.volum_max
                    else:
                        volum = _interpolar_volum(
                            mesocicle.volum_min,
                            mesocicle.volum_max,
                            j,
                            n_carrega,
                        )
                    volum_per_setmana.append(volum)
                    dies_qualitat_per_setmana.append(not es_base)
                    es_test_css = idx == 0 and es_base
                    test_css_per_setmana.append(es_test_css)
                    notes_per_setmana.append(
                        f"{etiqueta_carrega} + Test CSS" if es_test_css else etiqueta_carrega
                    )
            i += mida_bloc

    elif mesocicle.tipus == "Peak":
        for i in range(n_setmanes):
            tipus_base_per_setmana.append("taper")
            dies_qualitat_per_setmana.append(True)
            test_css_per_setmana.append(False)
            notes_per_setmana.append("Taper")
            if n_setmanes == 1:
                volum_per_setmana.append(mesocicle.volum_mitja_previst)
            else:
                # i=0 (més lluny) = volum_max; i=n-1 (cursa) = volum_min
                volum_per_setmana.append(
                    _interpolar_volum(
                        mesocicle.volum_max,
                        mesocicle.volum_min,
                        i,
                        n_setmanes,
                    )
                )

    elif mesocicle.tipus == "Cursa":
        tipus_base_per_setmana.append("taper")
        volum_per_setmana.append(mesocicle.volum_mitja_previst)
        dies_qualitat_per_setmana.append(True)
        test_css_per_setmana.append(False)
        notes_per_setmana.append("Setmana de competició")

    else:  # Transicio
        tipus_base_per_setmana.append("transicio")
        volum_per_setmana.append(mesocicle.volum_mitja_previst)
        dies_qualitat_per_setmana.append(False)
        test_css_per_setmana.append(False)
        notes_per_setmana.append("Recuperació post-competició")

    # 3. Crear els Microcicle
    microcicles: list[Microcicle] = []
    for i in range(n_setmanes):
        s = setmana_inici + i
        data_inici_setmana = data_inici_macro + timedelta(weeks=s - 1)
        data_fi_setmana = data_inici_setmana + timedelta(days=6)

        if data_inici_setmana.month == data_fi_setmana.month:
            dates = (
                f"{data_inici_setmana:%d}-{data_fi_setmana:%d}"
                f"/{data_fi_setmana:%m}/{data_fi_setmana:%Y}"
            )
        else:
            dates = (
                f"{data_inici_setmana:%d/%m}-{data_fi_setmana:%d/%m}"
                f"/{data_fi_setmana:%Y}"
            )

        microcicles.append(
            Microcicle(
                setmana=s,
                dates=dates,
                mesocicle_id=mesocicle.id,
                tipus_base=tipus_base_per_setmana[i],
                notes=notes_per_setmana[i],
                volum_objectiu=volum_per_setmana[i],
                dies_qualitat=dies_qualitat_per_setmana[i],
                test_css=test_css_per_setmana[i],
            )
        )

    return sorted(microcicles, key=lambda m: m.setmana)


def generar_mesocicle(
    nedador: Nedador,
    macrocicle: Macrocicle,
    competicions: list[Competicio],
    enriquir_amb_llm: bool = True,
    historial: list[SessioRealitzada] | None = None,
) -> tuple[Mesocicle, list[dict]]:
    """
    Decideix i afegeix seqüencialment el següent mesocicle al macrocicle,
    segons la posició actual (últim mesocicle de macrocicle.mesocicles,
    o data_inici del macrocicle si encara no n'hi ha cap).

    1. Calcula la data de la posició actual (data_inici del macrocicle +
       7 dies per cada setmana ja assignada als mesocicles existents).
    2. Calcula les setmanes fins la propera competició classe A del
       calendari (None si no en queda cap).
    3. Classificació determinista del tipus de mesocicle:
       - Si l'últim mesocicle existent és de tipus "Cursa" -> "Transicio"
       - Si no queda cap competició A -> "Base"
       - Si setmanes_fins_a <= 0 -> "Cursa"
       - Si setmanes_fins_a <= 3 -> "Peak"
       - Si setmanes_fins_a <= 6 -> "Build2"
       - Si setmanes_fins_a <= 10 -> "Build1"
       - Altrament -> "Base"
    4. Duració: 1 setmana per "Transicio"/"Cursa"; per "Peak" les
       setmanes exactes fins la competició; per "Base"/"Build1"/"Build2",
       4 setmanes per defecte, retallada per no sobrepassar el final
       del macrocicle (data_fi) ni la propera competició A.
    5. Crea el Mesocicle (id incremental "meso_N", nom "<Tipus> N",
       setmanes com a rang "X-Y" (numeració global dins el macrocicle),
       dates calculades, fase_objectiu = nom del tipus, volum_min/max/
       mitja_previst = 0 de moment (es podran ajustar més endavant),
       microcicles=[]), i l'afegeix a macrocicle.mesocicles.
    6. Si enriquir_amb_llm=True, crida una nova funció privada
       _enriquir_fase_objectiu_amb_llm(mesocicle, nedador) que fa una
       crida a l'API de Claude amb tool-use forçat perquè la resposta
       sigui exclusivament {"fase_objectiu": str} -- no pot canviar cap
       altre camp. Si l'API falla, fallback silenciós mantenint el
       fase_objectiu determinista (logger.warning). Calca exactament
       el patró ja existent a seleccio_model.py::_enriquir_justificacio_amb_llm.

    Retorna (mesocicle, avisos): avisos inclou "cap competició classe A
    restant" si escau, i "mesocicle retallat per falta de setmanes" si
    la duració s'ha hagut de reduir.

    Args:
        nedador: Nedador per al qual es genera el mesocicle
        macrocicle: Macrocicle al qual afegir el mesocicle
        competicions: Llista de totes les competicions del calendari
        enriquir_amb_llm: Si True, enriquir fase_objectiu amb LLM (default: True)
        historial: Historial de sessions realitzades per estimar volums (default: None)

    Returns:
        Tupla amb:
        - Mesocicle generat i afegit al macrocicle
        - Llista d'avisos
    """
    avisos = []
    historial = historial or []

    # 1. Calcular data de posició actual
    data_inici_macro = datetime.fromisoformat(macrocicle.data_inici)
    
    # Comptar setmanes ja assignades
    setmanes_assignades = 0
    for meso in macrocicle.mesocicles:
        for micro in meso.microcicles:
            setmanes_assignades = max(setmanes_assignades, micro.setmana)
    
    data_inici_mesocicle = data_inici_macro + timedelta(weeks=setmanes_assignades)
    setmana_inici = setmanes_assignades + 1

    # 2. Calcular setmanes fins la propera competició A (per Peak/Cursa/Transicio)
    competicions_a = [c for c in competicions if c.classe == "A"]
    competicions_a_ordenades = sorted(competicions_a, key=lambda c: c.data_inici)

    propera_comp_a = None
    setmanes_fins_a = None

    for comp in competicions_a_ordenades:
        data_comp = datetime.fromisoformat(comp.data_inici)
        if data_comp >= data_inici_mesocicle:
            propera_comp_a = comp
            dies_fins_comp = (data_comp - data_inici_mesocicle).days
            setmanes_fins_a = dies_fins_comp / 7.0
            break

    # 2b. Calcular setmanes fins la propera competició A O B (per Base/Build1/Build2)
    competicions_ab = [c for c in competicions if c.classe in ("A", "B")]
    competicions_ab_ordenades = sorted(competicions_ab, key=lambda c: c.data_inici)

    propera_comp_ab = None
    setmanes_fins_ab = None

    for comp in competicions_ab_ordenades:
        data_comp = datetime.fromisoformat(comp.data_inici)
        if data_comp >= data_inici_mesocicle:
            propera_comp_ab = comp
            dies_fins_comp = (data_comp - data_inici_mesocicle).days
            setmanes_fins_ab = dies_fins_comp / 7.0
            break

    # 3. Classificació determinista del tipus
    ultim_mesocicle = macrocicle.mesocicles[-1] if macrocicle.mesocicles else None

    if ultim_mesocicle and ultim_mesocicle.tipus == "Cursa":
        tipus = "Transicio"
    elif propera_comp_a is not None and setmanes_fins_a <= 0:
        tipus = "Cursa"
    elif propera_comp_a is not None and setmanes_fins_a <= 3:
        tipus = "Peak"
    elif propera_comp_ab is None:
        tipus = "Base"
        avisos.append({
            "tipus_avis": "cap_competicio_a_ni_b_restant",
            "missatge": "No queda cap competició classe A ni B al calendari. Generant mesocicle Base.",
        })
    elif setmanes_fins_ab <= 6:
        tipus = "Build2"
    elif setmanes_fins_ab <= 10:
        tipus = "Build1"
    else:
        tipus = "Base"

    # 4. Calcular duració
    if tipus in ("Transicio", "Cursa"):
        duracio_setmanes = 1
    elif tipus == "Peak" and setmanes_fins_a is not None:
        duracio_setmanes = max(1, int(setmanes_fins_a))
    else:
        duracio_setmanes = 4
    
    # Retallar per no sobrepassar data_fi del macrocicle
    data_fi_macro = datetime.fromisoformat(macrocicle.data_fi)
    data_fi_mesocicle = data_inici_mesocicle + timedelta(weeks=duracio_setmanes)
    
    if data_fi_mesocicle > data_fi_macro:
        setmanes_disponibles = (data_fi_macro - data_inici_mesocicle).days // 7
        if setmanes_disponibles < duracio_setmanes:
            duracio_setmanes = max(1, setmanes_disponibles)
            avisos.append({
                "tipus_avis": "mesocicle_retallat",
                "missatge": f"Mesocicle retallat a {duracio_setmanes} setmanes per no sobrepassar el final del macrocicle.",
            })
    
    # Retallar per no sobrepassar propera competició A
    if propera_comp_a and tipus not in ("Peak", "Cursa"):
        data_comp = datetime.fromisoformat(propera_comp_a.data_inici)
        setmanes_fins_comp = (data_comp - data_inici_mesocicle).days // 7
        if setmanes_fins_comp < duracio_setmanes:
            duracio_setmanes = max(1, setmanes_fins_comp)
            avisos.append({
                "tipus_avis": "mesocicle_retallat",
                "missatge": f"Mesocicle retallat a {duracio_setmanes} setmanes per no sobrepassar la propera competició A.",
            })

    # Recalcular data_fi amb duració final
    data_fi_mesocicle = data_inici_mesocicle + timedelta(weeks=duracio_setmanes) - timedelta(days=1)
    
    setmana_fi = setmana_inici + duracio_setmanes - 1

    # 5. Crear Mesocicle
    numero_mesocicle = len(macrocicle.mesocicles) + 1
    mesocicle_id = f"meso_{numero_mesocicle}"

    # Calcular volums reals a partir de l'històric
    volum_min, volum_max, volum_mitja_previst = _calcular_volums_mesocicle(
        nedador, historial, tipus
    )
    if not historial:
        avisos.append({
            "tipus_avis": "sense_historial",
            "missatge": "Sense històric del nedador: volums del mesocicle no estimats (0).",
        })

    mesocicle = Mesocicle(
        id=mesocicle_id,
        nom=f"{tipus} {numero_mesocicle}",
        setmanes=f"{setmana_inici}-{setmana_fi}" if setmana_inici != setmana_fi else str(setmana_inici),
        dates=f"{data_inici_mesocicle.strftime('%d/%m/%Y')}-{data_fi_mesocicle.strftime('%d/%m/%Y')}",
        tipus=tipus,
        fase_objectiu=tipus,
        metodologia_dominant="",  # Es pot omplir més endavant
        volum_min=volum_min,
        volum_max=volum_max,
        volum_mitja_previst=volum_mitja_previst,
        microcicles=[],
    )

    # Generar microcicles (una setmana per Microcicle)
    mesocicle.microcicles = generar_microcicles_mesocicle(
        mesocicle, macrocicle.data_inici
    )

    # 6. Enriquir fase_objectiu amb LLM si està habilitat
    if enriquir_amb_llm:
        mesocicle.fase_objectiu = _enriquir_fase_objectiu_amb_llm(mesocicle, nedador.id)

    # Afegir al macrocicle
    macrocicle.mesocicles.append(mesocicle)

    return mesocicle, avisos

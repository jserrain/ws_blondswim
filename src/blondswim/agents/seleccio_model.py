"""Selecció de metodologia d'entrenament basada en prova i categoria."""

import logging
import re
from typing import Literal

from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.nedador import Nedador

logger = logging.getLogger(__name__)


def _extreure_distancia(prova: str) -> tuple[int | None, str]:
    """
    Extreure distància en metres i tipus de prova.

    Args:
        prova: Descripció de la prova (ex: "100m lliure", "AAOO 5km", "200m IM")

    Returns:
        Tuple (distancia_metres, tipus) on tipus pot ser "piscina", "im", "aaoo"
    """
    prova_lower = prova.lower().strip()

    # Detectar aigües obertes
    if "aaoo" in prova_lower or "aigües obertes" in prova_lower:
        # Intentar extreure distància en km
        match = re.search(r"(\d+(?:\.\d+)?)\s*km", prova_lower)
        if match:
            km = float(match.group(1))
            return int(km * 1000), "aaoo"
        return None, "aaoo"

    # Detectar IM/estils
    if "im" in prova_lower or "estils" in prova_lower:
        match = re.search(r"(\d+)\s*m", prova_lower)
        if match:
            return int(match.group(1)), "im"
        return None, "im"

    # Prova de piscina normal
    match = re.search(r"(\d+)\s*m", prova_lower)
    if match:
        return int(match.group(1)), "piscina"

    return None, "piscina"


def _enriquir_justificacio_amb_llm(
    decisio: DecisioMetodologia,
    nedador: Nedador,
) -> str:
    """
    Enriquir la justificació amb una crida a l'API de Claude.

    Utilitza tool-use forçat perquè la resposta sigui exclusivament
    {"justificacio": str}. L'LLM NO pot canviar la metodologia principal,
    només ampliar i personalitzar la justificació basant-se en el context
    del nedador.

    Args:
        decisio: Decisió de metodologia ja calculada (determinista)
        nedador: Nedador per al qual es fa la selecció

    Returns:
        Justificació enriquida (o la original si hi ha error)
    """
    try:
        client = get_llm_client()

        # Definir tool per forçar resposta estructurada
        tools = [
            {
                "name": "retornar_justificacio",
                "description": (
                    "Retorna una justificació ampliada i personalitzada per a "
                    "la metodologia d'entrenament seleccionada."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "justificacio": {
                            "type": "string",
                            "description": (
                                "Justificació ampliada que explica per què aquesta "
                                "metodologia és adequada per al nedador i la seva prova "
                                "objectiu, mantenint la metodologia principal ja decidida."
                            ),
                        }
                    },
                    "required": ["justificacio"],
                },
            }
        ]

        # Construir prompt
        proves_str = ", ".join(nedador.proves_objectiu)
        prompt = f"""Ets un expert en metodologies d'entrenament de natació.

CONTEXT DEL NEDADOR:
- Nom: {nedador.nom}
- Edat: {nedador.edat}
- Categoria: {nedador.categoria}
- Proves objectiu: {proves_str}

DECISIÓ JA PRESA (NO LA CANVIÏS):
- Prova analitzada: {decisio.prova}
- Metodologia principal: {decisio.metodologia_principal}
- Metodologies complementàries: {', '.join(decisio.metodologies_complementaries)}
- Força d'evidència: {decisio.forca_evidencia}

JUSTIFICACIÓ ACTUAL:
{decisio.justificacio}

TASCA:
Amplia i personalitza la justificació per a aquest nedador específic.
NO proposis cap metodologia diferent, només explica millor per què aquesta
metodologia és adequada considerant:
- La seva edat i categoria
- Les seves proves objectiu
- El nivell d'evidència científica disponible

Mantén un to professional i basat en evidència. Si la força d'evidència és
baixa (pràctica documentada o sense evidència), sigues honest sobre les
limitacions però explica el raonament pràctic.

Retorna NOMÉS la justificació ampliada usant la tool retornar_justificacio."""

        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            tools=tools,
            tool_choice={"type": "tool", "name": "retornar_justificacio"},
            messages=[{"role": "user", "content": prompt}],
        )

        # Debug: verificar stop_reason
        logger.debug(f"stop_reason: {response.stop_reason}")

        # Extreure justificació del tool use
        for block in response.content:
            if block.type == "tool_use" and block.name == "retornar_justificacio":
                logger.debug(
                    f"Tool use block rebut: type={type(block.input)}, "
                    f"keys={list(block.input.keys()) if isinstance(block.input, dict) else 'N/A'}, "
                    f"content={block.input}"
                )
                # Verificar que block.input té la clau esperada
                if isinstance(block.input, dict) and "justificacio" in block.input:
                    return block.input["justificacio"]
                else:
                    logger.warning(
                        f"Tool use block sense clau 'justificacio'. "
                        f"Contingut rebut: {block.input}. Usant justificació original."
                    )
                    return decisio.justificacio
            elif block.type == "text":
                # Fallback: si hi ha text, intentar usar-lo
                logger.debug(f"Text block trobat: {block.text[:100]}...")

        # Si no trobem tool use vàlid, fallback
        logger.warning(
            "Resposta LLM sense tool use vàlid. Usant justificació original."
        )
        return decisio.justificacio

    except Exception as e:  # noqa: BLE001 — fallback intencionat: qualsevol error de l'LLM no ha de trencar la decisió determinista ja calculada
        logger.warning(
            f"Error en enriquir justificació amb LLM: {e}. "
            f"Usant justificació original."
        )
        return decisio.justificacio


def seleccionar_metodologia(
    nedador: Nedador,
    prova_objectiu: str,
    categoria: Literal["absolut", "master"],
    enriquir_amb_llm: bool = True,
) -> DecisioMetodologia:
    """
    Seleccionar metodologia d'entrenament basada en la prova i categoria.

    Utilitza la taula de decisió documentada a claude/fase2.md amb evidència
    científica i pràctica documentada.

    Args:
        nedador: Nedador per al qual es fa la selecció
        prova_objectiu: Descripció de la prova (ex: "100m lliure", "AAOO 5km")
        categoria: Categoria del nedador ("absolut" o "master")
        enriquir_amb_llm: Si True, enriquir justificació amb LLM per casos
                          amb evidència baixa (default: True)

    Returns:
        DecisioMetodologia amb metodologia principal, complementàries i justificació
    """
    distancia, tipus = _extreure_distancia(prova_objectiu)

    # Aigües obertes
    if tipus == "aaoo":
        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Entrenament específic AAOO",
            metodologies_complementaries=["Polaritzat", "Volum moderat"],
            forca_evidencia="sense_evidencia",
            justificacio=(
                "Aigües obertes requereix adaptacions específiques (orientació, "
                "condicions variables, nutrició en cursa). No hi ha estudis controlats "
                "específics, però la pràctica documentada suggereix combinació de "
                "volum moderat amb sessions específiques de tècnica i tàctica."
            ),
            avisos=[
                (
                    "Metodologia basada en judici d'entrenador i pràctica documentada, "
                    "sense evidència controlada disponible."
                )
            ],
        )

        # Enriquir justificació amb LLM si està habilitat
        if enriquir_amb_llm and decisio.forca_evidencia in {
            "sense_evidencia",
            "practica_documentada",
        }:
            decisio.justificacio = _enriquir_justificacio_amb_llm(decisio, nedador)

        return decisio

    # IM/Estils
    if tipus == "im":
        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Bowman/Escola australiana multi-estil",
            metodologies_complementaries=["Tècnica específica per estil"],
            forca_evidencia="practica_documentada",
            justificacio=(
                "Proves d'estils requereixen desenvolupament tècnic equilibrat en "
                "els quatre estils. L'escola de Bob Bowman i l'enfocament australià "
                "multi-estil han demostrat èxit en competició d'alt nivell, amb "
                "èmfasi en tècnica, transicions i resistència específica."
            ),
            avisos=[],
        )

        # Enriquir justificació amb LLM si està habilitat
        if enriquir_amb_llm and decisio.forca_evidencia in {
            "sense_evidencia",
            "practica_documentada",
        }:
            decisio.justificacio = _enriquir_justificacio_amb_llm(decisio, nedador)

        return decisio

    # Proves de piscina per distància
    if distancia is None:
        # Fallback si no es pot determinar distància
        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Indeterminat",
            metodologies_complementaries=[],
            forca_evidencia="sense_evidencia",
            justificacio="No s'ha pogut determinar la distància de la prova.",
            avisos=["Prova no reconeguda. Especifiqueu distància en metres."],
        )

        # Enriquir justificació amb LLM si està habilitat
        if enriquir_amb_llm and decisio.forca_evidencia in {
            "sense_evidencia",
            "practica_documentada",
        }:
            decisio.justificacio = _enriquir_justificacio_amb_llm(decisio, nedador)

        return decisio

    avisos = []

    # 50m: Sprint/Tècnica
    if distancia <= 50:
        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Sprint/Tècnica",
            metodologies_complementaries=["Potència anaeròbica", "Sortides i viratges"],
            forca_evidencia="practica_documentada",
            justificacio=(
                "Proves de 50m són purament anaeròbiques i requereixen màxima "
                "potència i tècnica impecable. La pràctica documentada prioritza "
                "entrenament de sprint amb volum baix i alta intensitat, combinat "
                "amb treball tècnic específic."
            ),
            avisos=[],
        )

        # Enriquir justificació amb LLM si està habilitat
        if enriquir_amb_llm and decisio.forca_evidencia in {
            "sense_evidencia",
            "practica_documentada",
        }:
            decisio.justificacio = _enriquir_justificacio_amb_llm(decisio, nedador)

        return decisio

    # 100m: Sprint/Tècnica (USRPT NO recomanat)
    if distancia <= 100:
        avisos_100m = [
            (
                "USRPT no és recomanat per a proves de sprint (50-100m) ja que la "
                "metodologia està dissenyada per a proves de resistència on el ritme "
                "de cursa es pot mantenir durant repeticions. En sprint, la fatiga "
                "neuromuscular impedeix mantenir velocitat màxima."
            )
        ]

        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Sprint/Tècnica",
            metodologies_complementaries=[
                "Potència anaeròbica",
                "Resistència a la velocitat",
            ],
            forca_evidencia="moderada",
            justificacio=(
                "100m combina potència anaeròbica amb capacitat de mantenir velocitat. "
                "Evidència moderada suporta entrenament de sprint amb sèries curtes "
                "a alta intensitat, combinat amb treball de resistència a la velocitat "
                "per mantenir tècnica sota fatiga."
            ),
            avisos=avisos_100m,
        )

        # No enriquir amb LLM per evidència moderada
        return decisio

    # 200m: Polaritzat
    if distancia <= 200:
        if categoria == "master":
            avisos.append(
                "Evidència de polaritzat per a 200m prové principalment d'estudis "
                "amb nedadors juvenils/elit. Extrapolació a màsters requereix "
                "ajustaments en volum i recuperació."
            )
            forca = "moderada"
        else:
            forca = "forta"

        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Polaritzat",
            metodologies_complementaries=["Tècnica", "Resistència a la velocitat"],
            forca_evidencia=forca,
            justificacio=(
                "200m és una prova mixta aeròbica-anaeròbica. Estudis controlats "
                "(Sperlich et al., Muñoz et al.) mostren superioritat del model "
                "polaritzat en nedadors juvenils/elit, amb millores significatives "
                "en VO2max i rendiment en proves de 200-400m."
            ),
            avisos=avisos,
        )

        # No enriquir amb LLM per evidència forta/moderada
        return decisio

    # 400m: Polaritzat
    if distancia <= 400:
        if categoria == "master":
            avisos.append(
                "Evidència de polaritzat per a 400m prové principalment d'estudis "
                "amb nedadors juvenils/elit. Extrapolació a màsters requereix "
                "ajustaments en volum i recuperació."
            )
            forca = "moderada"
        else:
            forca = "forta"

        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Polaritzat",
            metodologies_complementaries=["Tècnica", "Llindar anaeròbic"],
            forca_evidencia=forca,
            justificacio=(
                "400m és predominantment aeròbica amb component anaeròbic significatiu. "
                "Evidència forta (Sperlich et al., Muñoz et al.) suporta model "
                "polaritzat amb millores en VO2max, llindar i rendiment en 400m. "
                "Distribució típica: 75-80% zona baixa, 15-20% zona alta."
            ),
            avisos=avisos,
        )

        # No enriquir amb LLM per evidència forta/moderada
        return decisio

    # 800-1500m: Polaritzat + USRPT complementari
    if distancia <= 1500:
        decisio = DecisioMetodologia(
            prova=prova_objectiu,
            categoria=categoria,
            metodologia_principal="Polaritzat",
            metodologies_complementaries=["USRPT", "Tècnica", "Resistència aeròbica"],
            forca_evidencia="moderada",
            justificacio=(
                "Proves de 800-1500m són predominantment aeròbiques. Model polaritzat "
                "proporciona base aeròbica sòlida. USRPT pot complementar amb sessions "
                "específiques a ritme de cursa per desenvolupar resistència específica "
                "i economia de moviment. Evidència moderada per aquesta combinació."
            ),
            avisos=[],
        )

        # No enriquir amb LLM per evidència moderada
        return decisio

    # >1500m: Polaritzat amb èmfasi en volum
    decisio = DecisioMetodologia(
        prova=prova_objectiu,
        categoria=categoria,
        metodologia_principal="Polaritzat",
        metodologies_complementaries=["Volum aeròbic", "Tècnica", "Resistència"],
        forca_evidencia="moderada",
        justificacio=(
            "Proves de llarga distància (>1500m) requereixen base aeròbica extensa. "
            "Model polaritzat amb èmfasi en volum a zona baixa (80-85%) i sessions "
            "d'alta intensitat per mantenir velocitat. Evidència moderada per "
            "distàncies superiors a 1500m."
        ),
        avisos=[],
    )

    # Enriquir justificació amb LLM si està habilitat i la força d'evidència és baixa
    if enriquir_amb_llm and decisio.forca_evidencia in {
        "sense_evidencia",
        "practica_documentada",
    }:
        decisio.justificacio = _enriquir_justificacio_amb_llm(decisio, nedador)

    return decisio

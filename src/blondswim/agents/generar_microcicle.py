"""Generació de contingut de microcicle amb LLM (Mòdul 6)."""

import logging
from pathlib import Path

from blondswim.llm.client import DEFAULT_MODEL, get_llm_client
from blondswim.models.decisio import DecisioMetodologia
from blondswim.models.historial import SessioRealitzada
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Sessio

logger = logging.getLogger(__name__)


class GeneracioMicrocicleError(Exception):
    """Error en la generació de contingut de microcicle amb LLM."""


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
            f"- {s.dia.capitalize()}: {s.tipus_sessio} ({s.volum_total}m)"
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
                "description": "Retorna el contingut generat per a cada part de cada sessió",
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
                                                "contingut": {"type": "string"},
                                            },
                                            "required": ["nom", "contingut"],
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

            # Aplicar contingut a cada part
            for part_data in parts_data:
                nom_part = part_data.get("nom")
                contingut = part_data.get("contingut")

                # Buscar part corresponent
                part = next((p for p in sessio.estructura.parts if p.nom == nom_part), None)
                if not part:
                    logger.warning(
                        f"Part '{nom_part}' no trobada a sessió '{sessio_id}', ignorant"
                    )
                    continue

                # Assignar contingut
                part.contingut = contingut

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

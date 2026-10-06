"""Jutge LLM de les sessions generades (Fase 2 de la verificació).

El codi (`cicles.py`, `pla_setmanal.problemes_contingut`) valida les regles
dures: volum, pressupost d'intensitat, papallona, cicles i descansos. El jutge
només fa el judici semàntic que el codi no pot fer:

- és un exercici de natació real (no «surar fins a la bandera»)?
- és segur?
- correspon a la part de la sessió on és?
- la intensitat és coherent amb la part i el rol?
- fa servir terminologia real (no «crol amb Ei»)?
- és contingut real i no farciment per quadrar metres?

Els fets numèrics (descans real) els calcula el codi i van al prompt ja fets:
el jutge no ha de calcular res. Els temps s'escriuen com «1:50» i «15 s»,
mai amb cometes, perquè no trenquin el JSON de sortida.

Proveïdor: qualsevol API compatible amb OpenAI amb `response_format`
json_schema (llama-server de llama.cpp en local).
"""

import json
import time
import urllib.request
from dataclasses import dataclass, field

from blondswim.agents.cicles import descans_real, parsejar_descans
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Exercici

CATEGORIES = [
    "correcte",
    "no_natacio",
    "insegur",
    "part_incorrecta",
    "intensitat",
    "terminologia",
    "farciment",
]

DESCRIPCIO_CATEGORIES = {
    "correcte": "exercici real, segur i coherent amb la part",
    "no_natacio": "no és un exercici de natació (surar, caminar, estiraments a l'aigua...)",
    "insegur": "pot fer mal o és perillós (apnees llargues repetides, gestos que carreguen "
    "l'espatlla...)",
    "part_incorrecta": "és un exercici real però no correspon a aquesta part de la sessió",
    "intensitat": "la intensitat no és coherent amb la part o amb el rol de la sessió",
    "terminologia": "fa servir termes que no existeixen en natació",
    "farciment": "no té contingut d'entrenament: només serveix per quadrar metres",
}

# Exemples etiquetats per l'entrenador (few-shot). No han de ser al joc de prova.
EXEMPLES_DEFECTE: list[dict] = [
    {
        "part": "Bloc principal — Aeròbic",
        "exercici": "6x100 Estils A1 d/15 s (descans real 15 s)",
        "categoria": "correcte",
        "motiu": "Estils suaus a A1 són treball aeròbic vàlid i varien l'estímul.",
    },
    {
        "part": "Bloc principal — Aeròbic",
        "exercici": "4x50 Caminar per la piscina poc profunda A1 d/10 s (descans real 10 s)",
        "categoria": "no_natacio",
        "motiu": "Caminar no és nedar.",
    },
    {
        "part": "Escalfament",
        "exercici": "6x100 Crol A3 c/1:55 (descans real 21 s)",
        "categoria": "part_incorrecta",
        "motiu": "L'escalfament prepara: llindar (A3) és treball principal.",
    },
    {
        "part": "Tècnica",
        "exercici": "8x25 Crol un braç, l'altre estirat al davant A1 d/15 s (descans real 15 s)",
        "categoria": "correcte",
        "motiu": "Exercici tècnic real de crol, suau.",
    },
    {
        "part": "Bloc principal — Aeròbic",
        "exercici": "4x50 Subaquàtic sense respirar A2 d/20 s (descans real 20 s)",
        "categoria": "insegur",
        "motiu": "50 m d'apnea repetits: risc de pèrdua de consciència.",
    },
    {
        "part": "Tornada a la calma",
        "exercici": "1x100 Lliure per completar volum A1",
        "categoria": "farciment",
        "motiu": "No té cap objectiu: només quadra metres.",
    },
]


@dataclass
class ContextJutge:
    """Context de la part de sessió que es jutja."""

    rol: str
    fase: str
    part: str
    objectiu_part: str
    zones: dict[str, float] = field(default_factory=dict)  # zona -> s/100 m


@dataclass
class Veredicte:
    exercici: int
    valid: bool
    categoria: str
    motiu: str


def format_mmss(segons: float) -> str:
    """98 -> «1:38»; 45 -> «45 s» (sense cometes, per al JSON del jutge)."""
    s = round(segons)
    if s < 60:
        return f"{s} s"
    return f"{s // 60}:{s % 60:02d}"


def _descans_text(descans: str | None) -> str:
    d = parsejar_descans(descans)
    if d is None:
        return ""
    return ("c/" if d.tipus == "cicle" else "d/") + format_mmss(d.segons)


def text_exercici(ex: Exercici, nedador: Nedador | None = None) -> str:
    """«8x100 Crol A2 c/1:50 amb Pull (descans real 12 s)» amb els fets calculats."""
    treball = f"{ex.distancia_m}" if ex.series == 1 else f"{ex.series}x{ex.distancia_m}"
    parts = [treball, ex.execucio]
    if ex.intensitat:
        parts.append(ex.intensitat)
    descans = _descans_text(ex.descans)
    if descans:
        parts.append(descans)
    if ex.material:
        parts.append(f"amb {ex.material}")
    text = " ".join(parts)
    if nedador is not None and ex.series > 1:
        real = descans_real(ex, nedador)
        if real is not None:
            text += f" (descans real {format_mmss(max(real, 0))})"
    return text


def construir_missatges(
    context: ContextJutge,
    exercicis: list[str],
    exemples: list[dict] | None = None,
) -> list[dict]:
    """Missatges (sistema + usuari) per jutjar els exercicis d'una part."""
    exemples = EXEMPLES_DEFECTE if exemples is None else exemples
    zones = ", ".join(f"{z} {format_mmss(v)}" for z, v in context.zones.items() if v)
    categories = "\n".join(f"- {c}: {DESCRIPCIO_CATEGORIES[c]}" for c in CATEGORIES)
    text_exemples = "\n".join(
        f"- Part «{e['part']}»: {e['exercici']} -> {e['categoria']} ({e['motiu']})"
        for e in exemples
    )
    sistema = (
        "Ets un entrenador de natació expert. Revises els exercicis d'una part d'una "
        "sessió d'entrenament i detectes els que no tenen sentit.\n\n"
        f"Context: sessió de rol {context.rol}, fase {context.fase}, "
        f"part «{context.part}». Objectiu de la part: {context.objectiu_part}\n"
        + (f"Zones del nedador (ritme de crol per 100 m): {zones}.\n" if zones else "")
        + "\nNotació: c/X és el cicle (cada repetició surt cada X, nedar inclòs; no és el "
        "ritme de nedar); d/X és la pausa després de cada repetició. Zones: Recuperació i "
        "A1 suaus, A2 aeròbic mitjà, A3 llindar, AeM aeròbic màxim, Velocitat, MPLA i "
        "TOLA làctic.\n"
        "El volum, els descansos i els límits de metres ja els ha comprovat el sistema: "
        "no els jutgis ni recalculis res.\n\n"
        f"Categories:\n{categories}\n\n"
        f"Exemples d'entrenador:\n{text_exemples}\n\n"
        "Només marca un exercici com a invàlid si encaixa clarament en una categoria "
        "d'error. No inventis regles. Al motiu, escriu els temps com 1:45 o 15 s, mai "
        "amb cometes. Per a CADA exercici, escriu primer el motiu, després la categoria "
        "i després decideix (valid = true només si la categoria és correcte). Respon en "
        "català."
    )
    usuari = "Exercicis:\n" + "\n".join(f"{i}) {t}" for i, t in enumerate(exercicis, 1))
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuari}]


def esquema(n_exercicis: int) -> dict:
    """JSON schema de la resposta: exactament un veredicte per exercici."""
    return {
        "type": "object",
        "properties": {
            "veredictes": {
                "type": "array",
                "minItems": n_exercicis,
                "maxItems": n_exercicis,
                "items": {
                    "type": "object",
                    "properties": {
                        "exercici": {"type": "integer"},
                        "motiu": {"type": "string"},
                        "categoria": {"type": "string", "enum": CATEGORIES},
                        "valid": {"type": "boolean"},
                    },
                    "required": ["exercici", "motiu", "categoria", "valid"],
                },
            }
        },
        "required": ["veredictes"],
    }


def parsejar_veredictes(contingut: str, n_exercicis: int) -> list[Veredicte]:
    """Veredictes de la resposta, ordenats per exercici.

    Raises:
        ValueError: JSON invàlid o sense un veredicte per a cada exercici.
    """
    dades = json.loads(contingut)
    veredictes = [
        Veredicte(
            exercici=int(v["exercici"]),
            valid=bool(v["valid"]),
            categoria=str(v.get("categoria", "")),
            motiu=str(v.get("motiu", "")),
        )
        for v in dades["veredictes"]
    ]
    per_num = {v.exercici: v for v in veredictes}
    if sorted(per_num) != list(range(1, n_exercicis + 1)):
        raise ValueError(
            f"S'esperaven veredictes 1..{n_exercicis}, rebuts {sorted(per_num)}"
        )
    return [per_num[i] for i in range(1, n_exercicis + 1)]


@dataclass
class RespostaJutge:
    veredictes: list[Veredicte]
    segons: float
    raonament: str = ""


def jutjar(
    url: str,
    context: ContextJutge,
    exercicis: list[str],
    *,
    model: str | None = None,
    raonar: bool | None = False,
    exemples: list[dict] | None = None,
    timeout: float = 600,
) -> RespostaJutge:
    """Crida el jutge (API compatible amb OpenAI) i retorna els veredictes.

    `raonar=None` no envia `chat_template_kwargs` (models sense mode de
    raonament, p. ex. Gemma).
    """
    cos: dict = {
        "temperature": 0,
        "messages": construir_missatges(context, exercicis, exemples),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "veredictes", "schema": esquema(len(exercicis))},
        },
    }
    if model:
        cos["model"] = model
    if raonar is not None:
        cos["chat_template_kwargs"] = {"enable_thinking": raonar}
    peticio = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(cos).encode(),
        headers={"Content-Type": "application/json"},
    )
    inici = time.monotonic()
    with urllib.request.urlopen(peticio, timeout=timeout) as resposta:
        dades = json.load(resposta)
    segons = time.monotonic() - inici
    missatge = dades["choices"][0]["message"]
    return RespostaJutge(
        veredictes=parsejar_veredictes(missatge["content"], len(exercicis)),
        segons=segons,
        raonament=missatge.get("reasoning_content") or "",
    )

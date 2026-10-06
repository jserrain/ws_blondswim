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

El jutge no veu descansos, cicles ni ritmes: tot això ho valida el codi, i
quan el jutge els veia els jutjava igualment (malament). Cada exercici li
arriba en format estructurat («8x100 m | Crol | intensitat: A2 | material:
Pull») amb un glossari dels termes vàlids. Les normes de l'entrenador
comprovables pel text (polze arrossegant, «Ei») també són al codi
(`pla_setmanal.problemes_normes`). El glossari, les abreviatures i les normes
surten del diccionari de l'entrenador (`agents/diccionari.py`).

Proveïdor: qualsevol API compatible amb OpenAI amb `response_format`
json_schema (llama-server de llama.cpp en local).
"""

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

from blondswim.agents import diccionari
from blondswim.models.sessio import Exercici

if TYPE_CHECKING:
    from blondswim.agents.referencies import Referencia

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
        "exercici": "6x100 m | Estils | intensitat: A1",
        "categoria": "correcte",
        "motiu": "Estils suaus a A1 són treball aeròbic vàlid i varien l'estímul.",
    },
    {
        "part": "Bloc principal — Aeròbic",
        "exercici": "4x50 m | Caminar per la piscina poc profunda | intensitat: A1",
        "categoria": "no_natacio",
        "motiu": "Caminar no és nedar.",
    },
    {
        "part": "Escalfament",
        "exercici": "6x100 m | Crol | intensitat: A3",
        "categoria": "part_incorrecta",
        "motiu": "L'escalfament prepara: llindar (A3) és treball principal.",
    },
    {
        "part": "Tècnica",
        "exercici": "8x25 m | Crol un braç, l'altre estirat al davant | intensitat: A1",
        "categoria": "correcte",
        "motiu": "Exercici tècnic real de crol, suau.",
    },
    {
        "part": "Bloc principal — Aeròbic",
        "exercici": "4x50 m | Subaquàtic sense respirar | intensitat: A2",
        "categoria": "insegur",
        "motiu": "50 m d'apnea repetits: risc de pèrdua de consciència.",
    },
    {
        "part": "Tornada a la calma",
        "exercici": "100 m | Lliure per completar volum | intensitat: A1",
        "categoria": "farciment",
        "motiu": "No té cap objectiu: només quadra metres.",
    },
]


# Termes vàlids, del diccionari de l'entrenador (`tecnica/diccionari.json`).
GLOSSARI = diccionari.glossari()

# Punt 1: què ha de contenir un exercici (que falti un opcional no és error).
PLANTILLA = """\
Cada exercici segueix aquesta plantilla: treball (repeticions x distància) | \
execució (estil o exercici) | intensitat | material.
- Obligatoris: treball, execució i intensitat.
- Opcionals: material, focus, objectiu i ritme. Que en falti un no és error, i \
l'execució no ha de repetir la intensitat."""

# Punt 3: la intensitat és un nivell d'esforç, no un temps.
REGLA_INTENSITAT = (
    "La intensitat (Recuperació, A1, A2, A3...) és un nivell d'esforç vàlid per a "
    "qualsevol estil, Estils (IM) inclosos: un IM a A1 és correcte. El temps de cada estil "
    "el calcula el sistema amb l'índex de variació entre estils."
)


@dataclass
class ContextJutge:
    """Context de la part de sessió que es jutja."""

    rol: str
    fase: str
    part: str
    objectiu_part: str


@dataclass
class Veredicte:
    exercici: int
    valid: bool
    categoria: str
    motiu: str


def text_exercici(ex: Exercici) -> str:
    """«8x100 m | Crol | intensitat: A2 | material: Pull».

    Sense descans ni cicle: els valida el codi i el jutge no els ha de veure.
    """
    treball = f"{ex.distancia_m} m" if ex.series == 1 else f"{ex.series}x{ex.distancia_m} m"
    parts = [treball, ex.execucio]
    if ex.intensitat:
        parts.append(f"intensitat: {ex.intensitat}")
    if ex.material:
        parts.append(f"material: {ex.material}")
    return " | ".join(parts)


INSTRUCCIONS_REFERENCIES = (
    "Sota cada exercici hi ha exercicis semblants de referència (biblioteca de tècnica "
    "i sessions reals de l'entrenador) amb el seu veredicte. Són d'altres sessions: "
    "confirmen que un exercici o un terme existeix i és segur, però la coherència amb "
    "el rol i la part d'AQUESTA sessió la decideixes tu. Si s'assembla a una referència "
    "correcta, no el rebutgis per terminologia ni per no_natacio. Si s'assembla a un "
    "error de referència, aplica'n la categoria. «Semblants: cap» vol dir que no s'ha "
    "trobat res al corpus: decideix tu i no el rebutgis només per això."
)


def _text_referencies(refs: "list[Referencia]") -> str:
    if not refs:
        return "   Semblants: cap"
    linies = []
    for r in refs:
        font = r.font.split(":")[0]
        veredicte = r.veredicte if r.veredicte == "correcte" or not r.motiu else (
            f"{r.veredicte} ({r.motiu})")
        linies.append(f"   - {r.text} -> {veredicte} [{font}]")
    return "   Semblants:\n" + "\n".join(linies)


def construir_missatges(
    context: ContextJutge,
    exercicis: list[str],
    exemples: list[dict] | None = None,
    referencies: "list[list[Referencia]] | None" = None,
) -> list[dict]:
    """Missatges (sistema + usuari) per jutjar els exercicis d'una part.

    `referencies`: una llista (potser buida) per exercici, del mòdul `referencies`.
    """
    exemples = EXEMPLES_DEFECTE if exemples is None else exemples
    categories = "\n".join(f"- {c}: {DESCRIPCIO_CATEGORIES[c]}" for c in CATEGORIES)
    text_exemples = "\n".join(
        f"- Part «{e['part']}»: {e['exercici']} -> {e['categoria']} ({e['motiu']})"
        for e in exemples
    )
    sistema = (
        "Ets un entrenador de natació expert. Revises els exercicis d'una part d'una "
        "sessió d'entrenament i detectes els que no tenen sentit.\n\n"
        f"Context: sessió de rol {context.rol}, fase {context.fase}, "
        f"part «{context.part}». Objectiu de la part: {context.objectiu_part}\n\n"
        f"{PLANTILLA}\n{REGLA_INTENSITAT}\n"
        "El volum, els descansos, els ritmes, els límits de metres i les normes de "
        "l'entrenador ja els ha comprovat el sistema: no en parlis.\n\n"
        f"Glossari (termes vàlids):\n{GLOSSARI}\n\n"
        f"Categories:\n{categories}\n\n"
        f"Exemples d'entrenador:\n{text_exemples}\n\n"
        "Presumpció de validesa: un exercici és correcte llevat que encaixi CLARAMENT en "
        "una categoria d'error. Que falti informació (objectiu, ritme, focus) no és un "
        "error. Un terme del glossari no és mai un error de terminologia. No inventis "
        "regles. En cas de dubte, correcte. Per a CADA exercici, escriu primer el motiu "
        "(una frase), després la categoria i després decideix (valid = true només si la "
        "categoria és correcte). Respon en català."
    )
    if referencies is None:
        usuari = "Exercicis:\n" + "\n".join(f"{i}) {t}" for i, t in enumerate(exercicis, 1))
    else:
        if len(referencies) != len(exercicis):
            raise ValueError("Cal una llista de referències per exercici")
        sistema += "\n\n" + INSTRUCCIONS_REFERENCIES
        usuari = "Exercicis:\n" + "\n".join(
            f"{i}) {t}\n{_text_referencies(refs)}"
            for i, (t, refs) in enumerate(zip(exercicis, referencies, strict=True), 1)
        )
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
    referencies: "list[list[Referencia]] | None" = None,
    timeout: float = 600,
) -> RespostaJutge:
    """Crida el jutge (API compatible amb OpenAI) i retorna els veredictes.

    `raonar=None` no envia `chat_template_kwargs` (models sense mode de
    raonament, p. ex. Gemma).
    """
    cos: dict = {
        "temperature": 0,
        "messages": construir_missatges(context, exercicis, exemples, referencies),
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

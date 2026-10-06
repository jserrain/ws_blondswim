"""Referències per al jutge LLM (reference-guided judge).

El jutge falla quan no coneix un exercici real (falsos positius) o quan accepta
un terme inventat. Per a cada exercici a jutjar, aquest mòdul cerca 3-4
exercicis semblants d'un corpus de confiança i els passa al prompt amb el seu
veredicte (Zheng et al. 2023, MT-Bench; Liu et al. 2022, selecció kNN).

Corpus (mateix format que `jutge.text_exercici`, amb font i veredicte):
- biblioteca de tècnica (`tecnica/biblioteca_tecnica.json`), amb font citada;
- historial del nedador (`SessioRealitzada.series`): sessions fetes, «correcte».
  No té part de sessió: s'infereix de l'objectiu, la intensitat i la posició.
  Les abreviatures de l'entrenador (Ps, PEB, AL, r/4, A0...) es despleguen amb
  el diccionari (`agents/diccionari.py`).
- referències extra en JSONL (veredictes del mode ombra, errors etiquetats).

Cerca sense LLM: filtre pel tipus de part i BM25 sobre el text normalitzat.
Si cap referència no comparteix cap paraula, l'exercici queda «sense
referència» i es llisten les paraules que no surten al corpus ni al diccionari (avís
per detectar termes inventats; el jutge no rebutja mai només per això).
"""

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from blondswim.agents import diccionari, pla_setmanal
from blondswim.models.historial import SessioRealitzada
from blondswim.models.sessio import Exercici

BIBLIOTECA = Path(__file__).parents[1] / "tecnica" / "biblioteca_tecnica.json"

TIPUS_PARTS = ("escalfament", "tecnica", "cames", "principal", "calma")


@dataclass(frozen=True)
class Referencia:
    """Exercici de referència amb el seu veredicte."""

    text: str  # «8x100 m | Crol | intensitat: A2 | material: Pull»
    parts: frozenset[str]  # tipus de part on és vàlid (TIPUS_PARTS)
    veredicte: str  # categoria de jutge.CATEGORIES
    font: str  # «biblioteca:cam_crol_taula», «historial:2026-09-28», «extra»
    motiu: str = ""
    vegades: int = 1  # aparicions a l'historial


@dataclass
class ResultatCerca:
    referencies: list[Referencia] = field(default_factory=list)
    termes_desconeguts: list[str] = field(default_factory=list)

    @property
    def sense_referencia(self) -> bool:
        return not self.referencies


def tipus_part(nom_part: str) -> str:
    """Tipus de part a partir del nom de la part de sessió."""
    nom = _sense_accents(nom_part.lower())
    if "escalfament" in nom:
        return "escalfament"
    if "calma" in nom:
        return "calma"
    if "cames" in nom:
        return "cames"
    if "tecnica" in nom:
        return "tecnica"
    return "principal"


# --- Normalització -----------------------------------------------------------

# Abreviatures d'una lletra (la resta, al diccionari).
_ESTILS_LLETRA = {"C": "Crol", "B": "Braça", "E": "Esquena", "P": "Papallona", "N": "nedar"}
_BUIT = {"", "-", "–", "—", "none"}

# Paraules que comparteixen massa exercicis per fer-los «semblants» per si soles.
GENERIQUES = {
    "crol", "esquena", "braca", "papallona", "estils", "lliure", "nedar", "suau",
    "a1", "a2", "a3", "aem", "recuperacio", "velocitat", "mpla", "tola",
}

_PARAULES_BUIDES = {
    "a", "al", "als", "amb", "cada", "de", "del", "dels", "el", "els", "en", "i", "la",
    "les", "l", "d", "o", "per", "sense", "un", "una", "x", "m", "intensitat", "material",
    "y", "the",
}


def _sense_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def desplegar_abreviatures(execucio: str) -> str:
    """Abreviatures de l'entrenador -> termes del diccionari.

    «Ps Crol r/4» -> «Cames Crol respiració cada 4»; «100C + 100B» -> «100 Crol + 100 Braça».
    """
    text = re.sub(r"(^|\+\s*)\d+\)\s*", r"\1", execucio)  # «Crol + 6) EP»: numeració
    text = re.sub(r"\br/(\d)", r"respiració cada \1", text)
    text = re.sub(r"\b([CBE])/([CBE])\b",
                  lambda m: f"{_ESTILS_LLETRA[m[1]]} i {_ESTILS_LLETRA[m[2]]}", text)
    text = re.sub(r"(\d)\s?([CBEPN])\b", lambda m: f"{m[1]} {_ESTILS_LLETRA[m[2]]}", text)
    text = re.sub(r"(?<![\w/])([CBE])(?![\w/])", lambda m: _ESTILS_LLETRA[m[1]], text)
    # «4EP» -> «4 EP», però no els ordinals («1er», «2on», «4rt»)
    text = re.sub(r"(\d)(?!(?:er|on|rt|a|n|r|t)\b)(?=[^\W\d_]{2,})", r"\1 ", text)
    text = diccionari.desplegar(text)
    return re.sub(r"\s+", " ", text).strip()


def _intensitat(valor: str | None) -> str | None:
    if not valor or valor.strip().lower() in _BUIT:
        return None
    parts = [p.strip() for p in re.split(r"\s*\+\s*", valor.strip())]
    return " + ".join(diccionari.terme_de(p, "intensitat") or p for p in parts)


def _material(valor: str | None) -> str | None:
    if not valor or valor.strip().lower() in _BUIT:
        return None
    parts = [p.strip() for p in re.split(r"\s*[+/]\s*", valor.strip())]
    return " + ".join(diccionari.terme_de(p, "material") or p
                      for p in parts if p.lower() not in _BUIT)


def sense_descansos(text: str) -> str:
    """Treu cicles i descansos (c/1'45", d/10"): el jutge no els ha de veure."""
    text = re.sub(r"\s*\b[cd]/[\d'\"’:,.]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    """Paraules de contingut normalitzades (sense accents, números ni paraules buides)."""
    text = _sense_accents(text.lower())
    paraules = re.findall(r"[a-z][a-z0-9]*", text)
    return [p for p in paraules
            if p not in _PARAULES_BUIDES and len(p) > 1 and not re.fullmatch(r"x\d+", p)]


def _clau(text: str) -> tuple[str, ...]:
    """Clau per detectar duplicats: tokens ordenats + treball (8x100)."""
    treball = re.match(r"\s*([\dx]+)", text)
    return (treball[1] if treball else "", *sorted(set(tokens(text))))


# --- Corpus ------------------------------------------------------------------


def _format_biblioteca(fmt: str) -> tuple[str, str | None]:
    """«4-8x25/50 A1/A2 d/15"» -> treball «4-8x25/50 m», intensitat «A1/A2»."""
    net = re.sub(r"\s*[dc]/\S+", "", fmt).strip()
    m = re.match(r"([\d\-–]+x[\d/,]+(?:\s*m)?)\s*(.*)", net)
    if not m:
        return net, None
    treball = m[1] if m[1].endswith("m") else f"{m[1]} m"
    resta = m[2].strip()
    intensitat = resta if re.match(r"(A\d|Velocitat|Recuperació|MPLA|TOLA|AeM)", resta) else None
    return treball, intensitat


def _parts_biblioteca(element: str) -> frozenset[str]:
    element = element.lower()
    if element.startswith("cames"):
        return frozenset({"cames", "escalfament", "tecnica"})
    if element == "ritme":
        return frozenset({"principal"})
    return frozenset({"tecnica", "escalfament"})


def referencies_biblioteca(fitxer: Path = BIBLIOTECA) -> list[Referencia]:
    """Exercicis de la biblioteca de tècnica, tots «correcte» i amb la font."""
    refs = []
    for ex in json.loads(fitxer.read_text()):
        treball, intensitat = _format_biblioteca(ex.get("format", ""))
        camps = [treball, ex["nom"]]
        if intensitat:
            camps.append(f"intensitat: {intensitat}")
        material = (ex.get("material") or "").strip()
        if material and material.lower() not in _BUIT:
            camps.append(f"material: {material}")
        motiu = ex.get("consigna", "")
        if ex.get("restriccio"):
            motiu += f" (restricció: {ex['restriccio']})"
        refs.append(Referencia(
            text=sense_descansos(" | ".join(camps)),
            parts=_parts_biblioteca(ex.get("element", "")),
            veredicte="correcte", font=f"biblioteca:{ex['id']}", motiu=motiu,
        ))
    return refs


def _part_serie(objectiu: str, execucio: str, intensitat: str | None,
                posicio: int, total: int) -> str:
    """Tipus de part d'una sèrie de l'historial (no el porta)."""
    obj = _sense_accents(objectiu.lower())
    exe = _sense_accents(execucio.lower())
    ultimes = posicio >= total - 3
    if "escalfament" in obj or "activacio" in obj or (posicio == 0 and intensitat in
                                                       (None, "A1", "Recuperació")):
        return "escalfament"
    if ("recuperacio" in obj or intensitat == "Recuperació") and ultimes:
        return "calma"
    if "cames" in obj or exe.startswith("cames"):
        return "cames"
    if intensitat in (None, "A1") and any(
        p in obj for p in ("tecnic", "focus", "control", "posicio", "viratge", "colze")
    ):
        return "tecnica"
    return "principal"


def _treball(treball: str | None, execucio: str, volum: int | None) -> tuple[str, str]:
    """Treball «8x100 m» i execució neta d'una sèrie de l'historial.

    Formats de l'Excel: «4x100», 400.0, «2x» (amb «200 Crol» a l'execució),
    «3x200» amb subsèries «1) ...» i subsèries sense treball.
    """
    sub = re.match(r"\s*\d+\)\s*(.*)", execucio)
    if sub:  # subsèrie d'un bloc «3x200»: cada una és un treball sencer
        return (f"{volum} m" if volum else ""), sub[1]
    t = (treball or "").strip().removesuffix(".0")
    if re.fullmatch(r"\d+x\d+", t):
        return f"{t} m", execucio
    if re.fullmatch(r"\d+", t):
        return f"{t} m", execucio
    if re.fullmatch(r"\d+x", t):  # «2x» + «200 Crol r/3»
        m = re.match(r"\s*(\d+)\s+(.*)", execucio)
        if m:
            return f"{t}{m[1]} m", m[2]
        return t, execucio
    return (f"{volum} m" if volum else t), execucio


def referencies_historial(sessions: list[SessioRealitzada]) -> list[Referencia]:
    """Sèries de l'historial com a referències «correcte», sense duplicats.

    S'exclouen les que incompleixen les normes de l'entrenador (polze arrossegant).
    """
    per_clau: dict[tuple, Referencia] = {}
    vegades: Counter = Counter()
    parts_clau: dict[tuple, set[str]] = {}
    for sessio in sessions:
        if sessio.modalitat != "natacio":
            continue
        for i, serie in enumerate(sessio.series):
            treball, execucio = _treball(serie.treball, serie.execucio, serie.volum_m)
            execucio = sense_descansos(desplegar_abreviatures(execucio))
            if not execucio or not tokens(execucio):
                continue
            intensitat = _intensitat(serie.intensitat)
            if pla_setmanal.problemes_normes(Exercici(series=1, distancia_m=25,
                                                      execucio=execucio)):
                continue
            camps = [treball, execucio] if treball else [execucio]
            if intensitat:
                camps.append(f"intensitat: {intensitat}")
            material = _material(serie.material)
            if material:
                camps.append(f"material: {material}")
            text = " | ".join(camps)
            part = _part_serie(serie.objectiu or "", execucio, intensitat, i,
                               len(sessio.series))
            clau = _clau(text)
            vegades[clau] += 1
            parts_clau.setdefault(clau, set()).add(part)
            if clau not in per_clau:
                per_clau[clau] = Referencia(
                    text=text, parts=frozenset(), veredicte="correcte",
                    font=f"historial:{sessio.data}", motiu=serie.objectiu or "",
                )
    return [
        Referencia(text=r.text, parts=frozenset(parts_clau[c]), veredicte=r.veredicte,
                   font=r.font, motiu=r.motiu, vegades=vegades[c])
        for c, r in per_clau.items()
    ]


def referencies_jsonl(fitxer: Path) -> list[Referencia]:
    """Referències extra: {"text", "part", "veredicte", "motiu", "font"} per línia."""
    refs = []
    for linia in fitxer.read_text().splitlines():
        if not linia.strip():
            continue
        d = json.loads(linia)
        refs.append(Referencia(
            text=d["text"], parts=frozenset({tipus_part(d["part"])}),
            veredicte=d["veredicte"], font=d.get("font", "extra"), motiu=d.get("motiu", ""),
        ))
    return refs


def excloure(refs: list[Referencia], textos: list[str]) -> tuple[list[Referencia], int]:
    """Treu del corpus els exercicis del joc de prova (mateix treball i paraules)."""
    claus = {_clau(t) for t in textos}
    filtrades = [r for r in refs if _clau(r.text) not in claus]
    return filtrades, len(refs) - len(filtrades)


# --- Cerca BM25 --------------------------------------------------------------


class Corpus:
    """Corpus de referències amb cerca BM25 (Okapi) filtrada per tipus de part."""

    def __init__(self, refs: list[Referencia], *, k1: float = 1.5, b: float = 0.75,
                 vocabulari_extra: str = ""):
        self.refs = refs
        self.k1, self.b = k1, b
        self.docs = [tokens(r.text) for r in refs]
        self.mitjana = sum(map(len, self.docs)) / len(self.docs) if self.docs else 0
        self.df: Counter = Counter(t for d in self.docs for t in set(d))
        self.vocabulari = set(self.df) | set(tokens(vocabulari_extra))

    def _idf(self, terme: str) -> float:
        n, df = len(self.docs), self.df.get(terme, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _puntuacio(self, consulta: list[str], doc: list[str]) -> float:
        freq = Counter(doc)
        total = 0.0
        for t in set(consulta):
            f = freq.get(t, 0)
            if f:
                norma = 1 - self.b + self.b * len(doc) / (self.mitjana or 1)
                total += self._idf(t) * f * (self.k1 + 1) / (f + self.k1 * norma)
        return total

    def cercar(self, text: str, part: str, k: int = 3) -> ResultatCerca:
        """Les k referències més semblants de la mateixa part.

        Una referència només compta si comparteix alguna paraula específica de
        l'exercici (no un estil ni una intensitat: «Crol amb llast» no s'assembla
        a «Crol»). Si l'exercici només té paraules genèriques («8x100 | Crol | A3»),
        n'ha de compartir totes: el mateix estil a la mateixa intensitat.
        """
        consulta = tokens(text)
        especifiques = set(consulta) - GENERIQUES
        tipus = tipus_part(part)

        def semblant(doc: list[str]) -> bool:
            if especifiques:
                return bool(especifiques & set(doc))
            return set(consulta) <= set(doc)

        puntuades = [
            (self._puntuacio(consulta, doc), -ref.vegades, i)
            for i, (ref, doc) in enumerate(zip(self.refs, self.docs, strict=True))
            if tipus in ref.parts and semblant(doc)
        ]
        millors = sorted((p for p in puntuades if p[0] > 0), reverse=True)[:k]
        desconeguts = sorted({t for t in consulta if t not in self.vocabulari})
        return ResultatCerca(
            referencies=[self.refs[i] for _, _, i in millors],
            termes_desconeguts=desconeguts,
        )


def construir_corpus(
    *,
    historial: list[SessioRealitzada] | None = None,
    biblioteca: Path | None = BIBLIOTECA,
    extra: Path | None = None,
    excloure_textos: list[str] | None = None,
    vocabulari_extra: str | None = None,
) -> tuple[Corpus, dict[str, int]]:
    """Corpus i recompte per font (inclou quants exercicis de prova s'han exclòs)."""
    fonts = {
        "biblioteca": referencies_biblioteca(biblioteca) if biblioteca else [],
        "historial": referencies_historial(historial or []),
        "extra": referencies_jsonl(extra) if extra and extra.is_file() else [],
    }
    refs = [r for llista in fonts.values() for r in llista]
    exclosos = 0
    if excloure_textos:
        refs, exclosos = excloure(refs, excloure_textos)
    resum = {nom: len(llista) for nom, llista in fonts.items()} | {"exclosos": exclosos}
    if vocabulari_extra is None:
        vocabulari_extra = diccionari.vocabulari()
    return Corpus(refs, vocabulari_extra=vocabulari_extra), resum

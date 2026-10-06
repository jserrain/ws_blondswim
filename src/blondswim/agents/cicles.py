"""Cicles i descansos: notació, temps de cada exercici i validació.

Notació (minuts:segons, sense cometes perquè no trenqui cap JSON):

- ``c/m:ss``: **cicle**. Cada repetició surt cada X (nedar + descans = X).
  ``4x100 c/1:50`` amb un ritme d'1:38 deixa 12 s de descans.
- ``d/m:ss``: **descans**. X de descans després de cada repetició.
  ``8x50 d/0:15`` vol dir 15 s de descans entre 50s.

El parser també accepta la notació antiga (``c/1'50"``, ``d/15"``) de l'historial.

Només es valida el descans quan el ritme és conegut: l'estil complet, sense
material o amb pull o pales. Cames, aletes, paracaigudes i exercicis de la
biblioteca de tècnica només tenen temps aproximat (factors de la fitxa).

El temps nedat d'una repetició surt del ritme de la zona (CSS) i d'un factor
d'estil. Amb aquest temps:

- un ``c/`` impossible (cicle més curt que el temps nedat) es converteix en
  ``d/`` (`corregir_cicles`). Si el valor és curt (≤ 30"), l'LLM l'ha fet servir
  com a descans («c/15"») i es manté el valor; si no, es posa el descans mínim
  de la zona;
- un descans per sota del mínim de la zona és un problema que es retorna a
  l'LLM per corregir-lo (`problemes_cicles`);
- `temps_exercici` dona la durada (nedar + descansos) per a l'Excel i per
  comprovar la durada de la sessió.
"""

import math
import re
from dataclasses import dataclass
from typing import Literal

from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Exercici, Sessio

TipusDescans = Literal["cicle", "descans"]


@dataclass(frozen=True)
class Descans:
    tipus: TipusDescans
    segons: float

    def __str__(self) -> str:
        return formatar_descans(self)


_RE_DESCANS = re.compile(
    r"""^\s*(?P<tipus>[cd])\s*/\s*
        (?:(?P<min>\d+)\s*(?:'|:|min\b)\s*)?   # minuts: 1'  1:  1min
        (?P<seg>\d+(?:[.,]\d+)?)?              # segons
        \s*(?:''|"|s|seg|”)?\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parsejar_descans(text: str | None) -> Descans | None:
    """«c/1'45"» -> cicle 105 s; «d/15"» -> descans 15 s. None si no es reconeix.

    Accepta «c/1'45"», «c/1'45''», «c/1:45», «c/105"», «c/2'», «d/15"», «d/15s»,
    «d/20». Un número sol sense minuts són segons.
    """
    if not text:
        return None
    m = _RE_DESCANS.match(str(text).replace("’", "'"))
    if not m or (m.group("min") is None and m.group("seg") is None):
        return None
    minuts = int(m.group("min")) if m.group("min") else 0
    segons = float(m.group("seg").replace(",", ".")) if m.group("seg") else 0.0
    total = minuts * 60 + segons
    if total <= 0:
        return None
    tipus: TipusDescans = "cicle" if m.group("tipus").lower() == "c" else "descans"
    return Descans(tipus, total)


def mmss(segons: float) -> str:
    """105 -> «1:45»; 20 -> «0:20»."""
    total = round(segons)
    return f"{total // 60}:{total % 60:02d}"


def formatar_descans(descans: Descans) -> str:
    """Descans(cicle, 105) -> «c/1:45»; Descans(descans, 20) -> «d/0:20»."""
    prefix = "c/" if descans.tipus == "cicle" else "d/"
    return prefix + mmss(descans.segons)


def normalitzar_descans(text: str | None) -> str | None:
    """Qualsevol notació reconeguda -> «c/m:ss» o «d/m:ss»; si no, el text tal qual."""
    descans = parsejar_descans(text)
    return formatar_descans(descans) if descans else text


# --- Ritme de cada exercici --------------------------------------------------

_RE_ESTIL = [
    ("cames", re.compile(r"(?i:\b(ps|peus|cames|patada|dof[ií]|batud\w*)\b)")),
    ("braca", re.compile(r"(?i:\bbra[cç]a\b)|\bB\b")),
    ("esquena", re.compile(r"(?i:\besquena\b)|\bE\b")),
    ("estils", re.compile(r"\bIM\b|\bestils\b", re.IGNORECASE)),
    ("papallona", re.compile(r"\bpap(allona)?\b", re.IGNORECASE)),
]
# Cames amb braços (p. ex. «braça completa amb èmfasi en cames») no són cames.
_RE_COMPLET = re.compile(r"\b(complet[ae]?|nedar|bra[cç]ada\w*)\b", re.IGNORECASE)


def estil_exercici(execucio: str) -> str:
    """Estil dominant d'un exercici a partir del text d'execució."""
    for estil, patro in _RE_ESTIL:
        if patro.search(execucio):
            if estil == "cames" and _RE_COMPLET.search(execucio):
                continue
            return estil
    return "crol"


def ritme_zona(nedador: Nedador, intensitat: str | None) -> float | None:
    """Ritme de crol per 100 m (s) de la zona. None si el nedador no té zones."""
    r = nedador.ritmes_css
    if r is None:
        return None
    zona = intensitat or "A1"
    valors = {
        "Recuperació": r.recuperacio,
        "A1": r.a1,
        "A2": r.a2,
        "A3": r.a3,
        "AeM": r.a3,  # aeròbic màxim: com a mínim el ritme de llindar
        "Velocitat": r.velocitat,
        "MPLA": r.velocitat,
        "TOLA": (r.a3 + r.velocitat) / 2 if r.a3 and r.velocitat else None,
    }
    return valors.get(zona)


_RE_ALETES = re.compile(r"(?i:\baletes\b)|\bAL\b")
_RE_SENSE_RITME = re.compile(r"\bparacaigudes\b", re.IGNORECASE)


def _te_aletes(ex: Exercici) -> bool:
    return bool(_RE_ALETES.search(f"{ex.material or ''} {ex.execucio}"))


def factor_temps(ex: Exercici, nedador: Nedador) -> float:
    """Factor sobre el temps de crol: estil, cames i aletes (fitxa del nedador)."""
    f = nedador.factors_temps
    estil = estil_exercici(ex.execucio)
    if estil == "cames":
        return f.cames_aletes if _te_aletes(ex) else f.cames
    factor = 1.0 if estil == "crol" else getattr(f, estil)
    return factor * (f.aletes if _te_aletes(ex) else 1.0)


def ritme_conegut(ex: Exercici) -> bool:
    """El temps nedat surt de les zones: estil complet, sense aletes ni paracaigudes
    ni exercici de tècnica. Només aquests exercicis es validen per descans."""
    text = f"{ex.material or ''} {ex.execucio}"
    return (
        estil_exercici(ex.execucio) != "cames"
        and not _te_aletes(ex)
        and not _RE_SENSE_RITME.search(text)
        and ex.id_biblioteca is None
    )


def temps_nedat(ex: Exercici, nedador: Nedador) -> float | None:
    """Temps nedat d'UNA repetició (s), segons zona, estil i material."""
    ritme = ritme_zona(nedador, ex.intensitat)
    if ritme is None:
        return None
    return ritme * ex.distancia_m / 100 * factor_temps(ex, nedador)


# Descans mínim per 100 m, per zona (s). Velocitat i làctic: vegeu _descans_minim.
DESCANS_MIN_100 = {
    "Recuperació": 0,
    "A1": 5,
    "A2": 10,
    "A3": 15,
    "AeM": 20,
}
# Velocitat: recuperació completa, d/45" per cada 25 m.
DESCANS_VELOCITAT_25 = 45
# Zones suaus: el descans curt el corregeix el codi (sense reintent).
ZONES_SUAUS = {"Recuperació", "A1"}
# Zones on un exercici de diverses repeticions ha de portar descans explícit.
ZONES_DESCANS_OBLIGATORI = {"A2", "A3", "AeM", "Velocitat", "MPLA", "TOLA"}
# Tolerància de l'estimació del temps nedat (els ritmes són aproximats).
TOLERANCIA = 0.8


def descans_minim(ex: Exercici, nedat: float | None = None) -> float:
    """Descans mínim (s) entre repeticions per a la zona i la distància."""
    zona = ex.intensitat or "A1"
    if zona == "Velocitat":
        return DESCANS_VELOCITAT_25 * ex.distancia_m / 25
    if zona in ("MPLA", "TOLA"):
        # Làctic: MPLA treball:descans 1:3; TOLA 1:1.
        base = nedat if nedat is not None else ex.distancia_m * 0.6
        return base * (3 if zona == "MPLA" else 1)
    per_100 = DESCANS_MIN_100.get(zona, 0)
    if per_100 == 0:
        return 0
    return max(5.0, per_100 * ex.distancia_m / 100)


def _arrodonir_5(segons: float) -> int:
    return int(math.ceil(segons / 5) * 5)


def descans_real(ex: Exercici, nedador: Nedador) -> float | None:
    """Descans (s) entre repeticions. Amb c/, cicle menys temps nedat."""
    descans = parsejar_descans(ex.descans)
    if descans is None:
        return None
    if descans.tipus == "descans":
        return descans.segons
    nedat = temps_nedat(ex, nedador)
    return None if nedat is None else descans.segons - nedat


def temps_exercici(ex: Exercici, nedador: Nedador) -> float | None:
    """Durada total de l'exercici (s): repeticions + descansos."""
    nedat = temps_nedat(ex, nedador)
    if nedat is None:
        return None
    descans = parsejar_descans(ex.descans)
    if descans is None:
        return ex.series * nedat
    if descans.tipus == "cicle":
        return ex.series * max(descans.segons, nedat)
    return ex.series * nedat + max(ex.series - 1, 0) * descans.segons


def temps_sessio(sessio: Sessio, nedador: Nedador) -> float | None:
    """Durada estimada de la sessió (s). None si no hi ha zones."""
    temps = [
        temps_exercici(ex, nedador)
        for part in sessio.estructura.parts
        for ex in part.exercicis
    ]
    if not temps or any(t is None for t in temps):
        return None
    return sum(temps)


# --- Correcció i validació ---------------------------------------------------

# Un c/ curt per sota del temps nedat és l'LLM fent servir c/ com a descans.
MAX_CICLE_COM_DESCANS = 30


def corregir_cicles(sessio: Sessio, nedador: Nedador) -> list[str]:
    """Converteix els c/ impossibles en d/. Retorna les correccions fetes.

    Les parts fixes no es toquen.
    """
    correccions: list[str] = []
    for part in sessio.estructura.parts:
        if part.fixa:
            continue
        for ex in part.exercicis:
            descans = parsejar_descans(ex.descans)
            if descans is None or not ritme_conegut(ex):
                continue
            nedat = temps_nedat(ex, nedador)
            if nedat is None:
                continue
            real = descans.segons - nedat if descans.tipus == "cicle" else descans.segons
            if ex.intensitat in ZONES_SUAUS and ex.series > 1 and real > 0:
                # Rec/A1: un descans curt no mereix un reintent (el temps és una
                # estimació): es posa el mínim de la zona com a d/.
                minim = descans_minim(ex, nedat)
                if real < minim * TOLERANCIA:
                    nou = formatar_descans(Descans("descans", _arrodonir_5(max(minim, 5))))
                    correccions.append(
                        f"{ex.series}x{ex.distancia_m} {ex.intensitat} '{ex.execucio}': "
                        f"{ex.descans} deixa ~{real:.0f} s -> {nou}"
                    )
                    ex.descans = nou
                continue
            if descans.tipus != "cicle" or descans.segons > nedat:
                continue
            minim = descans_minim(ex, nedat)
            if descans.segons <= MAX_CICLE_COM_DESCANS:
                segons = max(descans.segons, minim)
            else:
                segons = max(minim, 10)
            nou = formatar_descans(Descans("descans", _arrodonir_5(segons)))
            correccions.append(
                f"{ex.series}x{ex.distancia_m} {ex.intensitat or ''} '{ex.execucio}': "
                f"{ex.descans} és més curt que el temps nedat "
                f"(~{mmss(nedat)}) -> {nou}"
            )
            ex.descans = nou
    return correccions


def problemes_cicles(
    sessio: Sessio, nedador: Nedador, minuts_max: int | None = None
) -> list[str]:
    """Descansos insuficients per a la zona i durada excessiva de la sessió.

    El descans real es compara amb el mínim de la zona amb una tolerància del
    20% (els ritmes per estil són aproximats).
    """
    problemes: list[str] = []
    for part in sessio.estructura.parts:
        if part.fixa:
            continue
        for ex in part.exercicis:
            if ex.series < 2 or not ritme_conegut(ex):
                continue
            nedat = temps_nedat(ex, nedador)
            minim = descans_minim(ex, nedat)
            if minim <= 0:
                continue
            real = descans_real(ex, nedador)
            nom = f"{ex.series}x{ex.distancia_m} {ex.intensitat} '{ex.execucio}'"
            if real is None:
                if (
                    parsejar_descans(ex.descans) is None
                    and nedat is not None
                    and ex.intensitat in ZONES_DESCANS_OBLIGATORI
                ):
                    problemes.append(
                        f"{nom}: falta el descans. Posa c/ (cicle) o d/ (descans) "
                        f"amb com a mínim {_arrodonir_5(minim)} s de descans"
                    )
                continue
            if real < minim * TOLERANCIA:
                suggeriment = (
                    f"c/{mmss(_arrodonir_5(nedat + minim))}"
                    if nedat is not None and ex.intensitat not in ("Velocitat", "MPLA", "TOLA")
                    else f"d/{mmss(_arrodonir_5(minim))}"
                )
                problemes.append(
                    f"{nom}: {ex.descans} deixa ~{max(real, 0):.0f} s de descans; "
                    f"a {ex.intensitat} cal com a mínim {_arrodonir_5(minim)} s "
                    f"(p. ex. {suggeriment})"
                )
    if minuts_max:
        total = temps_sessio(sessio, nedador)
        if total is not None and total / 60 > minuts_max * 1.1:
            problemes.append(
                f"Durada estimada {total / 60:.0f} min, per sobre del màxim de "
                f"{minuts_max} min: redueix sèries o descansos"
            )
    return problemes


# --- Taula per al prompt -----------------------------------------------------


def taula_cicles(nedador: Nedador) -> str:
    """Temps nedat i cicle mínim de crol per zona i distància (text per al prompt).

    Només distàncies vàlides per a la piscina del nedador.
    """
    if nedador.ritmes_css is None:
        return "(sense zones CSS: fes servir d/ amb descansos coherents amb la zona)"
    linies = [
        "| Zona | Distància | Temps nedat (crol) | Descans mínim | Cicle mínim |",
        "|---|---|---|---|---|",
    ]
    distancies = {
        "A1": (100, 200), "A2": (50, 100, 200), "A3": (50, 100, 200),
        "AeM": (50, 100), "Velocitat": (25, 50, 100),
    }
    for zona, dists in distancies.items():
        for d in dists:
            if d % nedador.piscina_m:
                continue
            ex = Exercici(series=2, distancia_m=d, execucio="crol", intensitat=zona)
            nedat = temps_nedat(ex, nedador)
            if nedat is None:
                continue
            minim = descans_minim(ex, nedat)
            cicle = (
                "— (fes servir d/)"
                if zona == "Velocitat"
                else f"c/{mmss(_arrodonir_5(nedat + minim))}"
            )
            linies.append(
                f"| {zona} | {d} | {mmss(nedat)} | "
                f"d/{mmss(_arrodonir_5(minim))} | {cicle} |"
            )
    return "\n".join(linies)

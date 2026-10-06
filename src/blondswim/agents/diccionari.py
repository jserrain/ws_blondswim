"""Diccionari de natació de l'entrenador (`tecnica/diccionari.json`).

Font única de:
- el glossari del jutge (termes vàlids amb el significat);
- el desplegament de les abreviatures de l'historial (Ps, PEB, AL, Tèc...);
- les normes de l'entrenador (termes `prohibit` amb patró i motiu);
- el vocabulari conegut, per avisar de termes que no surten enlloc.

Els termes `pendent` (sense definir) no surten al glossari però compten com a
coneguts. Les abreviatures d'una lletra (C, E, B, P, N) es despleguen al mòdul
`referencies`, només enganxades a un número o soles («100C», «C/E»).
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

FITXER = Path(__file__).parents[1] / "tecnica" / "diccionari.json"

TIPUS = {
    "estil": "Estils",
    "exercici": "Exercicis",
    "tecnica": "Tècnica",
    "material": "Material",
    "ritme": "Ritme",
    "respiracio": "Respiració",
    "intensitat": "Intensitats",
    "organitzacio": "Organització",
}
ESTATS = ("valid", "prohibit", "pendent")

_LLETRA = r"[^\W\d_]"


@dataclass(frozen=True)
class Terme:
    terme: str
    tipus: str
    significat: str = ""
    abreviatures: tuple[str, ...] = ()
    majuscules: bool = False
    estat: str = "valid"
    motiu: str = ""
    patro: str = ""


@cache
def termes(fitxer: Path = FITXER) -> tuple[Terme, ...]:
    """Termes del diccionari, validats."""
    dades = json.loads(fitxer.read_text())["termes"]
    resultat = []
    for d in dades:
        t = Terme(
            terme=d["terme"], tipus=d["tipus"], significat=d.get("significat", ""),
            abreviatures=tuple(d.get("abreviatures", [])),
            majuscules=d.get("majuscules", False), estat=d.get("estat", "valid"),
            motiu=d.get("motiu", ""), patro=d.get("patro", ""),
        )
        if t.tipus not in TIPUS or t.estat not in ESTATS:
            raise ValueError(f"Terme «{t.terme}»: tipus o estat desconegut")
        if t.estat == "prohibit" and not (t.patro and t.motiu):
            raise ValueError(f"Terme prohibit «{t.terme}» sense patró o motiu")
        resultat.append(t)
    return tuple(resultat)


def glossari(fitxer: Path = FITXER) -> str:
    """Glossari per al prompt del jutge: termes vàlids agrupats per tipus."""
    linies = []
    for tipus, titol in TIPUS.items():
        valids = [t for t in termes(fitxer) if t.tipus == tipus and t.estat == "valid"]
        if valids:
            items = ", ".join(
                f"{t.terme} ({t.significat})" if t.significat else t.terme for t in valids
            )
            linies.append(f"- {titol}: {items}.")
    return "\n".join(linies)


@cache
def abreviatures(fitxer: Path = FITXER) -> tuple[tuple[re.Pattern, str], ...]:
    """(patró, terme) per desplegar les abreviatures, de la més llarga a la més curta.

    Una abreviatura no pot tocar cap lletra, però sí un número («4EP», «50Ps»).
    Les d'una lletra només hi són si van en majúscules (F); C, E, B, P i N es
    despleguen a `referencies`.
    """
    parells = []
    for t in termes(fitxer):
        if t.estat == "prohibit":
            continue
        for abr in t.abreviatures:
            if len(abr) == 1 and not t.majuscules:
                continue
            patro = re.compile(
                rf"(?<!{_LLETRA}){re.escape(abr)}(?!{_LLETRA})",
                0 if t.majuscules else re.IGNORECASE,
            )
            parells.append((len(abr), patro, t.terme))
    parells.sort(key=lambda p: -p[0])
    return tuple((p, terme) for _, p, terme in parells)


def desplegar(text: str, fitxer: Path = FITXER) -> str:
    for patro, terme in abreviatures(fitxer):
        text = patro.sub(terme, text)
    return text


def terme_de(abreviatura: str, tipus: str, fitxer: Path = FITXER) -> str | None:
    """Terme d'una abreviatura d'un tipus (p. ex. «A0» -> «Recuperació»)."""
    for t in termes(fitxer):
        if t.tipus != tipus or t.estat == "prohibit":
            continue
        formes = [t.terme, *t.abreviatures]
        if t.majuscules and abreviatura in formes:
            return t.terme
        if not t.majuscules and abreviatura.lower() in (f.lower() for f in formes):
            return t.terme
    return None


@cache
def normes(fitxer: Path = FITXER) -> tuple[tuple[re.Pattern, str], ...]:
    """(patró, motiu) de cada terme prohibit."""
    return tuple(
        (re.compile(t.patro, 0 if t.majuscules else re.IGNORECASE), t.motiu)
        for t in termes(fitxer) if t.estat == "prohibit"
    )


def vocabulari(fitxer: Path = FITXER) -> str:
    """Tot el text dels termes coneguts (vàlids i pendents), per als termes no vistos."""
    return " ".join(
        f"{t.terme} {t.significat} {' '.join(t.abreviatures)}"
        for t in termes(fitxer) if t.estat != "prohibit"
    )


def pendents(fitxer: Path = FITXER) -> list[str]:
    return [t.terme for t in termes(fitxer) if t.estat == "pendent"]

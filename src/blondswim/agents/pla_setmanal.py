"""
Organització setmanal (acordada 2026-09-30, vegeu fase3.md — Fase H).

- 5 sessions: dilluns a divendres (acordat 2026-10-01). Dimecres = tècnica en
  estat fresc, volum baix i sense qualitat. Cap de setmana sense nedar.
- 1 sol dia de qualitat per setmana (dimarts; dijous la setmana post-competició).
- Dia abans de competir: activació (24 h abans). Dies de descans: sense nedar.
- Setmana post-competició: dilluns de recuperació activa i objectiu = mínim setmanal.
- Pressupost d'intensitat i de papallona per rol, validat després de cada sessió.
- Sèrie de control fixa (4x100 A2) cada dimecres.

Tot és determinista; l'LLM només omple els exercicis dins d'aquests límits.
"""

import math
import re
from datetime import date, timedelta

from blondswim.agents import diccionari
from blondswim.models.calendari import Competicio
from blondswim.models.nedador import Nedador
from blondswim.models.sessio import Exercici, PartSessio, Sessio

# Dies de la plantilla setmanal. Si el nedador té uns altres dies disponibles,
# l'esquelet fa servir la lògica antiga (rols per dia fixos).
DIES_PLANTILLA: list[str] = ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]

# Dia de la sèrie de control (part fixa).
DIA_SERIE_CONTROL: str = "dimecres"

# Pes relatiu del volum de cada rol dins la setmana.
PES_ROL: dict[str, float] = {
    "aerobica": 1.0,
    "mitjana": 1.0,
    "llarga": 1.05,
    "qualitat": 0.95,
    "tecnica": 0.65,
    "activacio": 0.5,
    "recuperacio": 0.6,
}

# Marge del rang de volum d'una sessió al voltant del seu objectiu.
MARGE_RANG_SESSIO: float = 0.05

# Metres per minut (amb descansos) per limitar el volum per temps de sessió.
METRES_PER_MINUT: int = 40

# Parts de cada rol: (nom, % del volum no fixat), en l'ordre de l'estructura
# recomanada: escalfament -> tècnica -> bloc(s) principal(s) -> tornada a la
# calma. El treball més exigent (qualitat, velocitat) va just després de
# l'escalfament i la tècnica, en estat fresc; el bloc secundari (aeròbic,
# cames) després.
PARTS_ROL: dict[str, list[tuple[str, float]]] = {
    "aerobica": [
        ("Escalfament", 15), ("Tècnica", 15), ("Aeròbic", 48), ("Cames", 12),
        ("Tornada a la calma", 10),
    ],
    "llarga": [
        ("Escalfament", 10), ("Tècnica", 10), ("Velocitat alàctica", 5),
        ("Aeròbic llarg", 55), ("Cames", 10), ("Tornada a la calma", 10),
    ],
    "qualitat": [
        ("Escalfament", 15), ("Tècnica+Subaquàtic", 15), ("Qualitat", 25),
        ("Aeròbic", 30), ("Tornada a la calma", 15),
    ],
    "tecnica": [
        ("Escalfament", 15), ("Tècnica i papallona", 45), ("Cames", 15),
        ("Nedar suau", 15), ("Tornada a la calma", 10),
    ],
    "activacio": [
        ("Escalfament", 30), ("Tècnica i sortides", 25), ("Ritme de cursa", 10),
        ("Nedar suau", 20), ("Tornada a la calma", 15),
    ],
    "recuperacio": [
        ("Escalfament", 20), ("Tècnica suau", 20),
        ("Aeròbic suau amb canvis de ritme", 40), ("Cames", 10),
        ("Tornada a la calma", 10),
    ],
}

# Bloc de l'estructura de la sessió de cada part (pel seu nom). Al dia de
# tècnica, la tècnica és el bloc principal.
BLOC_PART: dict[str, str] = {
    "Escalfament": "Escalfament",
    "Tècnica": "Tècnica",
    "Tècnica+Subaquàtic": "Tècnica",
    "Tècnica i sortides": "Tècnica",
    "Tècnica suau": "Tècnica",
    "Tècnica i papallona": "Bloc principal",
    "Cames": "Bloc principal",
    "Aeròbic": "Bloc principal",
    "Aeròbic llarg": "Bloc principal",
    "Aeròbic suau amb canvis de ritme": "Bloc principal",
    "Qualitat": "Bloc principal",
    "Velocitat alàctica": "Bloc principal",
    "Ritme de cursa": "Bloc principal",
    "Nedar suau": "Bloc principal",
    "Tornada a la calma": "Tornada a la calma",
    # Esquelet antic (5 parts estàndard).
    "Aeròbic/Llindar": "Bloc principal",
    "Específic/Qualitat": "Bloc principal",
}


def bloc_part(nom: str) -> str | None:
    """Bloc de l'estructura de la sessió d'una part (None si no es coneix)."""
    return BLOC_PART.get(nom)


def etiquetes_parts(noms_blocs: list[tuple[str, str | None]]) -> list[str]:
    """
    Etiqueta de cada part per a l'Excel i el prompt: el bloc i, per als blocs
    principals, el número (si n'hi ha més d'un) i el nom de la part.
    Exemple: "Bloc principal 1 — Qualitat".
    """
    n_principals = sum(1 for _, bloc in noms_blocs if bloc == "Bloc principal")
    etiquetes = []
    i = 0
    for nom, bloc in noms_blocs:
        if bloc == "Bloc principal":
            i += 1
            numero = f" {i}" if n_principals > 1 else ""
            etiquetes.append(f"Bloc principal{numero} — {nom}")
        elif bloc == "Tècnica":
            etiquetes.append(nom)  # "Tècnica", "Tècnica+Subaquàtic", "Tècnica suau"...
        else:
            etiquetes.append(bloc or nom)
    return etiquetes

ETIQUETA_ROL: dict[str, str] = {
    "aerobica": "Aeròbic i tècnica",
    "mitjana": "Aeròbic i tècnica",
    "llarga": "Aeròbica llarga",
    "qualitat": "Qualitat",
    "tecnica": "Tècnica",
    "activacio": "Activació pre-competició",
    "recuperacio": "Recuperació activa",
}

NOM_SERIE_CONTROL = "Sèrie de control"

# Grups d'intensitat per al pressupost.
_GRUP_ZONA: dict[str, str] = {
    "Recuperació": "baixa",
    "A1": "baixa",
    "A2": "a2",
    "A3": "a3",
    "AeM": "a3",
    "Velocitat": "velocitat",
    "MPLA": "lactic",
    "TOLA": "lactic",
}

# Pressupost de la sessió de qualitat segons el tipus de setmana (tipus_sessio).
# a3 en fracció del volum de la sessió; velocitat i lactic en metres.
_PRESSUPOST_QUALITAT: dict[str, dict[str, float]] = {
    "carrega": {"a3": 0.25, "velocitat": 300, "lactic": 0},     # Base: llindar + alàctic
    "qualitat": {"a3": 0.20, "velocitat": 300, "lactic": 400},  # Build: làctic
    "descarrega": {"a3": 0.10, "velocitat": 200, "lactic": 0},  # ritme de cursa curt
    "taper": {"a3": 0.15, "velocitat": 300, "lactic": 200},     # ritme de cursa
    "transicio": {"a3": 0.0, "velocitat": 100, "lactic": 0},    # sense qualitat
}

_PRESSUPOST_ROL: dict[str, dict[str, float]] = {
    "aerobica": {"a3": 0.05, "velocitat": 0, "lactic": 0},
    "mitjana": {"a3": 0.05, "velocitat": 0, "lactic": 0},
    "llarga": {"a3": 0.05, "velocitat": 200, "lactic": 0},
    "tecnica": {"a2": 0, "a3": 0.0, "velocitat": 0, "lactic": 0},
    "activacio": {"a3": 0.0, "velocitat": 150, "lactic": 0},
    "recuperacio": {"a2": 0, "a3": 0.0, "velocitat": 0, "lactic": 0},
}

# Màxim de papallona per sessió (m). Decisió de l'entrenador (06/10, opció
# intermèdia): ~900 m/setmana, fins a 150 m per sessió i 300 m el dia de tècnica,
# sempre en repeticions de 25-50 m, amb bona tècnica i mai a la tornada a la calma.
# Els estils compten un 25%.
PAPALLONA_MAX_ROL: dict[str, int] = {
    "tecnica": 300,
    "qualitat": 150,
    "llarga": 150,
    "aerobica": 150,
    "mitjana": 150,
    "activacio": 50,
    "recuperacio": 0,
}
PAPALLONA_SETMANA: tuple[int, int] = (600, 900)
# Repetició màxima de papallona sola (els estils de 100/200 no hi compten).
PAPALLONA_REPETICIO_MAX = 50

# Repartiment orientatiu per estils (fracció dels metres de l'LLM). El crol és la
# resta; la papallona la limita PAPALLONA_MAX_ROL. Proves: 100 L i 100 IM (P),
# 200 L (S); l'esquena, la braça i els canvis d'estil és on es guanya al 100 IM.
ESTILS_ROL: dict[str, dict[str, float]] = {
    "tecnica": {"esquena": 0.20, "braca": 0.20},
}
ESTILS_DEFECTE: dict[str, float] = {"esquena": 0.15, "braca": 0.15}

_DESCRIPCIO_ROL: dict[str, str] = {
    "aerobica": (
        "Aeròbic i tècnica: base aeròbica A1/A2 amb treball tècnic i de cames. "
        "Les sèries aeròbiques són de control del ritme: cada repetició al mateix "
        "temps (±1\"), la primera mai la més ràpida, i viratge a totes les parets. "
        "Sense velocitat ni làctic."
    ),
    "llarga": (
        "Aeròbica llarga: primer, en fresc després de la tècnica, una dosi curta de "
        "velocitat alàctica (4-6 x 15-25 m, recuperació completa, d/45\" o més); "
        "després sèries llargues A1/A2 amb el mateix nombre de braçades per llargada "
        "i viratge a totes les parets, també al final de les sèries."
    ),
    "tecnica": (
        "Tècnica en estat fresc (volum baix): exercicis de tècnica i cames en "
        "Recuperació/A1, sempre en parella exercici -> nedar l'estil complet. Inclou "
        "la papallona tècnica de la setmana. Sense A2 (excepte la sèrie de control), "
        "A3, velocitat ni làctic."
    ),
    "activacio": (
        "Activació 24 h abans de competir: sessió curta. Escalfament, tècnica i "
        "sortides, 4-6 x 25 a ritme de cursa amb recuperació completa (d/1' o més) "
        "i nedar suau per acabar."
    ),
    "recuperacio": (
        "Recuperació activa després de competir: volum baix en Recuperació/A1, amb "
        "canvis de ritme suaus i tècnica. Sense A2 (excepte la sèrie de control), "
        "A3, velocitat ni làctic."
    ),
}
_DESCRIPCIO_QUALITAT: dict[str, str] = {
    "carrega": (
        "Qualitat de Base: bloc principal a A3/llindar (sèries de 50-200 m) i "
        "velocitat alàctica curta. Sense làctic (MPLA/TOLA)."
    ),
    "qualitat": (
        "Qualitat de Build: producció o tolerància làctica (MPLA/TOLA) i ritme de "
        "cursa de 100 m, amb recuperacions àmplies."
    ),
    "descarrega": (
        "Qualitat de descàrrega: velocitat alàctica i ritme de cursa curt. "
        "Sense tolerància làctica."
    ),
    "taper": "Qualitat de taper: ritme de cursa amb poc volum i recuperacions completes.",
    "transicio": "Transició: sense qualitat; aeròbic suau i tècnica.",
}


# --- Classificació de la setmana i rols ---


def classificar_setmana(
    dilluns: date, competicions: list[Competicio]
) -> tuple[str | None, bool]:
    """
    Retorna (dia_competicio, post_competicio) per a la setmana de `dilluns`.

    Només compten les competicions A i B (les C es tracten com un dia normal).
    - dia_competicio: "dissabte" o "diumenge" si una competició comença aquest
      cap de setmana (si dura els dos dies, "dissabte").
    - post_competicio: True si una competició va acabar el cap de setmana anterior.
    """
    dissabte = dilluns + timedelta(days=5)
    diumenge = dilluns + timedelta(days=6)
    dia_competicio: str | None = None
    post = False
    for c in competicions:
        if c.classe not in ("A", "B"):
            continue
        inici = date.fromisoformat(c.data_inici)
        fi = date.fromisoformat(c.data_fi) if c.data_fi else inici
        if dissabte <= inici <= diumenge:
            dia = "dissabte" if inici == dissabte else "diumenge"
            if dia_competicio is None or dia == "dissabte":
                dia_competicio = dia
        if dilluns - timedelta(days=2) <= fi <= dilluns - timedelta(days=1):
            post = True
    return dia_competicio, post


def rols_setmana(dia_competicio: str | None, post_competicio: bool) -> dict[str, str]:
    """
    Rol de cada dia (5 sessions) segons el tipus de setmana.

    L'activació és el dia abans de competir: divendres (competició dissabte) o
    dissabte (competició diumenge; aleshores divendres és descans).
    """
    dia_activacio = "dissabte" if dia_competicio == "diumenge" else "divendres"
    if post_competicio and dia_competicio:
        # Dues competicions seguides: les curses fan d'estímul intens.
        return {
            "dilluns": "recuperacio", "dimarts": "aerobica", "dimecres": "tecnica",
            "dijous": "aerobica", dia_activacio: "activacio",
        }
    if post_competicio:
        return {
            "dilluns": "recuperacio", "dimarts": "aerobica", "dimecres": "tecnica",
            "dijous": "qualitat", "divendres": "llarga",
        }
    if dia_competicio:
        return {
            "dilluns": "aerobica", "dimarts": "qualitat", "dimecres": "tecnica",
            "dijous": "aerobica", dia_activacio: "activacio",
        }
    return {
        "dilluns": "aerobica", "dimarts": "qualitat", "dimecres": "tecnica",
        "dijous": "aerobica", "divendres": "llarga",
    }


def usa_plantilla(nedador: Nedador) -> bool:
    """True si el nedador entrena els dies de la plantilla setmanal."""
    return sorted(nedador.dies_disponibles) == sorted(DIES_PLANTILLA)


def context_setmana(dia_competicio: str | None, post_competicio: bool) -> str:
    """Text breu del context de la setmana per al prompt i les notes."""
    parts = []
    if post_competicio:
        parts.append("Setmana posterior a una competició (prioritat: recuperació)")
    if dia_competicio:
        parts.append(f"Competició el {dia_competicio}; activació 24 h abans")
    return ". ".join(parts) if parts else "Setmana sense competició"


# --- Metres de cada part (conveni de l'entrenador) ---

# Els volums de sessió i de part s'arrodoneixen a 100 m (2.775 -> 2.800).
ARRODONIMENT_VOLUM = 100


def arrodonir_100(valor: float) -> int:
    """Al múltiple de 100 més proper (meitats amunt), mínim 100."""
    return max(ARRODONIMENT_VOLUM, int(valor / ARRODONIMENT_VOLUM + 0.5) * ARRODONIMENT_VOLUM)


def _percentatge(part: PartSessio, tipus_sessio: str) -> float:
    if tipus_sessio == "carrega":
        return part.percentatge_carrega
    if tipus_sessio == "qualitat":
        return part.percentatge_qualitat
    return part.percentatge_descarrega


def assignar_metres_parts(sessio: Sessio) -> None:
    """
    Metres de cada part variable, en múltiples de 100, que sumen exactament els
    metres no fixos de la sessió (mètode del residu més gran: cada part rep la
    centena sencera del seu percentatge i les centenes que falten van a les
    parts amb més residu). Ex.: 2.800 m amb 15/15/48/12/10% ->
    400/400/1.400/300/300 (l'última part completa la resta).
    """
    fix = sum(ex.volum_m for p in sessio.estructura.parts if p.fixa for ex in p.exercicis)
    variables = [p for p in sessio.estructura.parts if not p.fixa]
    disponible = sessio.volum_total - fix
    if not variables or disponible <= 0:
        return
    unitat = ARRODONIMENT_VOLUM
    pesos = [_percentatge(p, sessio.tipus_sessio) for p in variables]
    suma = sum(pesos) or 1
    exactes = [disponible * w / suma / unitat for w in pesos]
    unitats = [int(x) for x in exactes]
    falten = disponible // unitat - sum(unitats)
    per_residu = sorted(range(len(exactes)), key=lambda i: -(exactes[i] - unitats[i]))
    for i in per_residu[:falten]:
        unitats[i] += 1
    # Cap part sense metres: es treu una centena de la més gran.
    for i, u in enumerate(unitats):
        if u == 0 and max(unitats) > 1:
            unitats[unitats.index(max(unitats))] -= 1
            unitats[i] = 1
    metres = [u * unitat for u in unitats]
    metres[-1] += disponible - sum(metres)  # resta (si el disponible no és múltiple de 100)
    for part, m in zip(variables, metres, strict=True):
        part.metres_objectiu = m


# --- Sèrie de control ---


def cicle_serie_control(nedador: Nedador) -> str:
    """Cicle de la sèrie de control: ritme A2 per 100 + 15 s, arrodonit a 5 s amunt."""
    if nedador.ritmes_css is None or nedador.ritmes_css.a2 is None:
        return "d/0:20"
    segons = int(math.ceil((nedador.ritmes_css.a2 + 15) / 5) * 5)
    return f"c/{segons // 60}:{segons % 60:02d}"


def part_serie_control(nedador: Nedador) -> PartSessio:
    """Part fixa amb la sèrie de control setmanal (4x100 crol A2)."""
    return PartSessio(
        nom=NOM_SERIE_CONTROL,
        bloc="Sèrie de control",
        percentatge_carrega=0,
        percentatge_qualitat=0,
        percentatge_descarrega=0,
        fixa=True,
        exercicis=[
            Exercici(
                series=4,
                distancia_m=100,
                execucio=(
                    "Crol. Anota el temps de cada 100, les braçades per llargada "
                    "i l'esforç (0-10)"
                ),
                descans=cicle_serie_control(nedador),
                intensitat="A2",
                objectiu="Control setmanal de recuperació",
            )
        ],
    )


# --- Pressupost i validació ---


def pressupost_sessio(sessio: Sessio) -> dict[str, int]:
    """Màxim de metres per grup d'intensitat (a2 només si està limitat)."""
    rol = sessio.rol or "aerobica"
    if rol == "qualitat":
        base = _PRESSUPOST_QUALITAT.get(sessio.tipus_sessio, _PRESSUPOST_QUALITAT["carrega"])
    else:
        base = _PRESSUPOST_ROL.get(rol, _PRESSUPOST_ROL["aerobica"])
    resultat = {
        # Arrodonit a 100 amunt: les sèries d'A3 són de 50-200 m (4x50 = 200).
        "a3": int(math.ceil(base["a3"] * sessio.volum_total / 100) * 100),
        "velocitat": int(base["velocitat"]),
        "lactic": int(base["lactic"]),
    }
    if "a2" in base:
        resultat["a2"] = int(base["a2"])
    return resultat


def descripcio_rol(sessio: Sessio) -> str:
    """Descripció del rol per al prompt."""
    rol = sessio.rol or "aerobica"
    if rol == "qualitat":
        return _DESCRIPCIO_QUALITAT.get(sessio.tipus_sessio, _DESCRIPCIO_QUALITAT["carrega"])
    return _DESCRIPCIO_ROL.get(rol, _DESCRIPCIO_ROL["aerobica"])


def text_pressupost(sessio: Sessio) -> str:
    """Pressupost d'intensitat i papallona en text per al prompt."""
    p = pressupost_sessio(sessio)
    linies = [
        f"- A3/AeM: màxim {p['a3']} m",
        f"- Velocitat: màxim {p['velocitat']} m",
        f"- MPLA/TOLA (làctic): màxim {p['lactic']} m",
    ]
    if "a2" in p:
        linies.append(f"- A2: màxim {p['a2']} m")
    linies.append(
        f"- Papallona: màxim {PAPALLONA_MAX_ROL.get(sessio.rol or 'aerobica', 50)} m "
        "(el 25% de cada exercici d'estils compta com a papallona)"
    )
    return "\n".join(linies)


def _exercicis_variables(sessio: Sessio) -> list[Exercici]:
    return [ex for part in sessio.estructura.parts if not part.fixa for ex in part.exercicis]


def grup_zona(intensitat: str | None) -> str:
    """Grup de pressupost d'una intensitat (baixa, a2, a3, velocitat, lactic)."""
    return _GRUP_ZONA.get(intensitat or "A1", "baixa")


def metres_per_grup(sessio: Sessio) -> dict[str, int]:
    """Metres per grup d'intensitat, sense les parts fixes."""
    total: dict[str, int] = {"baixa": 0, "a2": 0, "a3": 0, "velocitat": 0, "lactic": 0}
    for ex in _exercicis_variables(sessio):
        grup = _GRUP_ZONA.get(ex.intensitat or "A1", "baixa")
        total[grup] += ex.volum_m
    return total


_RE_PAPALLONA = re.compile(r"\bpap(allona)?\b", re.IGNORECASE)
# La patada de dofí (cames) no carrega l'espatlla: no compta com a papallona.
_RE_CAMES = re.compile(r"\b(ps|peus|cames|dof[ií]|batud\w*|ondulaci[oó])\b", re.IGNORECASE)
_RE_BRACOS = re.compile(r"\b(bra[cç]\w*|completa?|nedar)\b", re.IGNORECASE)
_RE_ESTILS = re.compile(r"\bIM\b|\bestils\b", re.IGNORECASE)
# «Braços estirats» o «sense braçada» descriuen un exercici de cames, no de braços.
_RE_BRACOS_NEGAT = re.compile(
    r"bra[cç]os\s+(estirats|al davant|a l'esquena)|sense\s+bra[cç]\w*", re.IGNORECASE
)
# Estils amb la papallona feta només de cames: «Pap cames dofí», «cames de dofí en
# lloc de papallona», «25 cames dofí substituint papallona».
_RE_PAP_DOFI = re.compile(
    r"cames(\s+de)?\s+dof[ií]\w*\s+(en\s+lloc|substitu)"
    r"|pap\w*\s+(\(?\s*cames(\s+de)?\s+)?dof[ií]"
    r"|dof[ií]\w*\s+(en\s+lloc\s+de|substituint)\s+(la\s+)?(pap|bra[cç]ada)",
    re.IGNORECASE,
)


_RE_SENSE_PAP = re.compile(r"sense\s+pap", re.IGNORECASE)
_RE_ALTRES_ESTILS = re.compile(r"\b(esquena|esq|bra[cç]a|bra|crol)\b", re.IGNORECASE)


def _sense_papallona(text: str) -> bool:
    """Estils «sense papallona», o que detallen els estils i la papallona no hi és."""
    if _RE_SENSE_PAP.search(text):
        return True
    return bool(_RE_ALTRES_ESTILS.search(text)) and not _RE_PAPALLONA.search(text)


def papallona_per_exercici(sessio: Sessio) -> list[tuple[Exercici, int]]:
    """
    Metres de papallona de cada exercici que en té: l'exercici sencer si
    l'esmenta; el 25% si és d'estils. Els exercicis només de cames (dofí,
    "Ps Pap") no compten.
    """
    resultat = []
    for ex in _exercicis_variables(sessio):
        text = _RE_BRACOS_NEGAT.sub(" ", ex.execucio)
        es_cames = _RE_CAMES.search(text) and not _RE_BRACOS.search(text)
        if es_cames:
            continue
        if _RE_ESTILS.search(text):
            if _RE_PAP_DOFI.search(text) or _sense_papallona(text):
                continue  # papallona de cames de dofí, o estils sense papallona

            resultat.append((ex, ex.volum_m // 4))
        elif _RE_PAPALLONA.search(ex.execucio):
            resultat.append((ex, ex.volum_m))
    return resultat


def metres_papallona(sessio: Sessio) -> int:
    """Total de papallona de la sessió (vegeu papallona_per_exercici)."""
    return sum(m for _ex, m in papallona_per_exercici(sessio))


def nota_papallona(sessio: Sessio, dia_tecnica: str | None) -> str:
    """Papallona de la sessió (límit i forma), per al prompt de cada sessió."""
    maxim = PAPALLONA_MAX_ROL.get(sessio.rol or "aerobica", 50)
    forma = (
        f"sempre en repeticions de 25 o {PAPALLONA_REPETICIO_MAX} m amb bona tècnica i "
        "descans suficient, mai a la tornada a la calma ni al final de la sessió; els "
        "estils compten un 25% (un 100 IM en té 25 m); les cames de dofí no compten"
    )
    if maxim == 0:
        return "Sense papallona en aquesta sessió (els estils, només si són suaus i curts)."
    if sessio.rol == "tecnica":
        return (
            f"Aquesta és la sessió de la papallona tècnica de la setmana: entre "
            f"{papallona_minima(sessio)} i {maxim} m, "
            f"exercicis de coordinació i ondulació seguits de nedar complet; {forma}."
        )
    on = f" (el {dia_tecnica})" if dia_tecnica else ""
    minim = papallona_minima(sessio)
    quant = f"Entre {minim} i {maxim} m" if minim else f"Fins a {maxim} m"
    return (
        f"{quant} de papallona, dins dels estils o en sèries curtes; {forma}. "
        f"La tècnica de papallona va a la sessió de tècnica{on}."
    )


def metres_estils_objectiu(sessio: Sessio, metres: int) -> dict[str, int]:
    """Metres orientatius per estil (arrodonits a 50) sobre els metres de l'LLM."""
    fraccions = ESTILS_ROL.get(sessio.rol or "aerobica", ESTILS_DEFECTE)
    esquena = int(round(metres * fraccions["esquena"] / 50) * 50)
    braca = int(round(metres * fraccions["braca"] / 50) * 50)
    papallona = PAPALLONA_MAX_ROL.get(sessio.rol or "aerobica", 50)
    return {
        "crol": max(metres - esquena - braca - papallona, 0),
        "esquena": esquena,
        "braca": braca,
        "papallona": papallona,
    }


def metres_per_estil(sessions: list[Sessio]) -> dict[str, int]:
    """Metres de la setmana per estil (estils repartits a 25%; cames i papallona
    segons el comptador de papallona). Per al resum de la consola."""
    from blondswim.agents.cicles import estil_exercici

    total = {"crol": 0, "esquena": 0, "braca": 0, "papallona": 0, "cames": 0}
    for sessio in sessions:
        total["papallona"] += metres_papallona(sessio)
        for ex in _exercicis_variables(sessio):
            estil = estil_exercici(ex.execucio)
            if estil == "estils":
                for e in ("crol", "esquena", "braca"):
                    total[e] += ex.volum_m // 4
            elif estil in total and estil != "papallona":
                total[estil] += ex.volum_m
    return total


def avisos_estils_setmana(sessions: list[Sessio]) -> list[str]:
    """Estils de la setmana per sota de la meitat del seu objectiu orientatiu, o
    papallona fora de PAPALLONA_SETMANA."""
    reals = metres_per_estil(sessions)
    objectiu = {"esquena": 0, "braca": 0}
    for s in sessions:
        fix = sum(ex.volum_m for p in s.estructura.parts if p.fixa for ex in p.exercicis)
        m = metres_estils_objectiu(s, s.volum_total - fix)
        for estil in objectiu:
            objectiu[estil] += m[estil]
    noms = {"esquena": "Esquena", "braca": "Braça"}
    avisos = [
        f"{noms[e]} de la setmana {reals[e]}m: menys de la meitat de l'orientatiu "
        f"({objectiu[e]}m)"
        for e in objectiu if objectiu[e] and reals[e] < objectiu[e] / 2
    ]
    pap_min, pap_max = PAPALLONA_SETMANA
    if reals["papallona"] > pap_max:
        avisos.append(f"Papallona de la setmana {reals['papallona']}m: màxim {pap_max}m")
    elif reals["papallona"] < pap_min:
        avisos.append(
            f"Papallona de la setmana {reals['papallona']}m: per sota de l'orientatiu "
            f"({pap_min}-{pap_max}m)"
        )
    return avisos


def _franja(objectiu: int) -> str:
    """450 -> «350-450»: el model llegeix un sol número com a màxim."""
    minim = int(objectiu * 0.75 / 50) * 50
    return f"{minim}-{objectiu}" if minim < objectiu else f"{objectiu}"


def papallona_minima(sessio: Sessio) -> int:
    """Mínim orientatiu de papallona: 2/3 del màxim (150 -> 100, 300 -> 200)."""
    maxim = PAPALLONA_MAX_ROL.get(sessio.rol or "aerobica", 50)
    return int(maxim * 2 / 3 / 50) * 50 if maxim >= 150 else 0


def text_estils(sessio: Sessio, metres: int) -> str:
    """«crol ~1.850 m, esquena 300-450 m, braça 300-450 m, papallona 100-150 m»."""
    m = metres_estils_objectiu(sessio, metres)
    pap_min = papallona_minima(sessio)
    pap = f"{pap_min}-{m['papallona']}" if pap_min else f"fins a {m['papallona']}"
    return (
        f"crol ~{m['crol']} m, esquena {_franja(m['esquena'])} m, braça "
        f"{_franja(m['braca'])} m, papallona {pap} m (els estils compten un 25% per a "
        "cada estil; les cames compten a l'estil de la patada)"
    )


def problemes_normes(ex: Exercici) -> list[str]:
    """Normes de l'entrenador comprovables pel text (termes `prohibit` del diccionari)."""
    text = f"{ex.execucio} {ex.objectiu or ''}"
    return [f"'{ex.execucio}': {motiu}" for patro, motiu in diccionari.normes()
            if patro.search(text)]


def problemes_contingut(sessio: Sessio) -> list[str]:
    """
    Problemes de pressupost i de regles de natació d'una sessió generada.

    - Metres per grup d'intensitat per sobre del pressupost del rol.
    - Papallona per sobre del màxim del rol.
    - Estils complets (>= 100 m) que no són múltiple de 100.
    - A3 en repeticions de menys de 50 m (no s'arriba al llindar).
    """
    problemes: list[str] = []
    metres = metres_per_grup(sessio)
    pressupost = pressupost_sessio(sessio)
    noms = {"a2": "A2", "a3": "A3/AeM", "velocitat": "Velocitat", "lactic": "MPLA/TOLA"}
    for grup, maxim in pressupost.items():
        if metres[grup] > maxim:
            problemes.append(
                f"{noms[grup]}: {metres[grup]} m, per sobre del màxim de {maxim} m"
            )

    pap_max = PAPALLONA_MAX_ROL.get(sessio.rol or "aerobica", 50)
    per_exercici = papallona_per_exercici(sessio)
    pap = sum(m for _ex, m in per_exercici)
    if pap > pap_max:
        detall = ", ".join(
            f"«{ex.series}x{ex.distancia_m} {ex.execucio}» {m} m" for ex, m in per_exercici
        )
        problemes.append(
            f"Papallona: {pap} m, per sobre del màxim de {pap_max} m ({detall}). Redueix "
            "les repeticions de papallona o d'estils, o canvia'n alguna per cames de dofí"
        )
    darrera = next(
        (p for p in reversed(sessio.estructura.parts) if not p.fixa and p.exercicis), None
    )
    for ex, m in per_exercici:
        es_estils = bool(_RE_ESTILS.search(ex.execucio))
        if not es_estils and m and ex.distancia_m > PAPALLONA_REPETICIO_MAX:
            problemes.append(
                f"'{ex.execucio}': papallona en repeticions de {ex.distancia_m} m; "
                f"fes-la en 25 o {PAPALLONA_REPETICIO_MAX} m"
            )
        if darrera is not None and any(e is ex for e in darrera.exercicis) and not es_estils and m:
            problemes.append(
                f"'{ex.execucio}': papallona a la tornada a la calma; posa-la abans, "
                "amb el cos fresc"
            )

    for ex in _exercicis_variables(sessio):
        if (
            _RE_ESTILS.search(ex.execucio)
            and ex.distancia_m >= 100
            and ex.distancia_m % 100 != 0
        ):
            problemes.append(
                f"'{ex.execucio}': uns estils complets han de ser de 100 o 200 m, "
                f"no de {ex.distancia_m} m"
            )
        problemes.extend(problemes_normes(ex))
        if ex.intensitat == "A3" and ex.distancia_m < 50:
            problemes.append(
                f"'{ex.execucio}': A3 en repeticions de {ex.distancia_m} m no arriba "
                "al llindar (mínim 50 m)"
            )
    return problemes

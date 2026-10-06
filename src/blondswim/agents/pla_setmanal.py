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

# Màxim de papallona per sessió (m). Setmana: 300-600 m, sobretot a la tècnica.
PAPALLONA_MAX_ROL: dict[str, int] = {
    "tecnica": 350,
    "qualitat": 150,
    "llarga": 50,
    "aerobica": 50,
    "mitjana": 50,
    "activacio": 50,
    "recuperacio": 0,
}
PAPALLONA_SETMANA: tuple[int, int] = (300, 600)

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


# --- Sèrie de control ---


def cicle_serie_control(nedador: Nedador) -> str:
    """Cicle de la sèrie de control: ritme A2 per 100 + 15\", arrodonit a 5\" amunt."""
    if nedador.ritmes_css is None or nedador.ritmes_css.a2 is None:
        return "d/20\""
    segons = int(math.ceil((nedador.ritmes_css.a2 + 15) / 5) * 5)
    return f"c/{segons // 60}'{segons % 60:02d}\""


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
        "a3": int(round(base["a3"] * sessio.volum_total / 25) * 25),
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


def metres_papallona(sessio: Sessio) -> int:
    """
    Papallona: l'exercici sencer si l'esmenta; el 25% si és d'estils.
    Els exercicis només de cames (dofí, "Ps Pap") no compten.
    """
    total = 0
    for ex in _exercicis_variables(sessio):
        es_cames = _RE_CAMES.search(ex.execucio) and not _RE_BRACOS.search(ex.execucio)
        if es_cames:
            continue
        if _RE_PAPALLONA.search(ex.execucio):
            total += ex.volum_m
        elif _RE_ESTILS.search(ex.execucio):
            total += ex.volum_m // 4
    return total


# Normes de l'entrenador que es poden comprovar pel text (no cal el jutge).
# Arrossegar el polze o els dits a la recuperació de crol carrega l'espatlla.
_RE_ARROSSEGAR = re.compile(
    r"arrossega\w*\s+(?:el\s+|els\s+)?(?:polze|dits)|(?:polze|dits)\s+arrossega",
    re.IGNORECASE,
)
# «Ei» no és un terme de natació (l'LLM el fa servir per DPS).
_RE_TERMES_PROHIBITS = re.compile(r"\bEi\b")


def problemes_normes(ex: Exercici) -> list[str]:
    """Normes de l'entrenador comprovables pel text de l'exercici."""
    text = f"{ex.execucio} {ex.objectiu or ''}"
    problemes = []
    if _RE_ARROSSEGAR.search(text):
        problemes.append(
            f"'{ex.execucio}': no facis exercicis d'arrossegar el polze o els dits a la "
            "recuperació (carreguen l'espatlla)"
        )
    if _RE_TERMES_PROHIBITS.search(text):
        problemes.append(
            f"'{ex.execucio}': «Ei» no és un terme de natació; per a la longitud de "
            "braçada, escriu DPS o recompte de braçades"
        )
    return problemes


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
    pap = metres_papallona(sessio)
    if pap > pap_max:
        problemes.append(f"Papallona: {pap} m, per sobre del màxim de {pap_max} m")

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

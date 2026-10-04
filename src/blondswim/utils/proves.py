"""Noms de proves: una clau canònica per comparar textos lliures.

«100m Lliure», «100 lliures», «100 crol» -> «100 crol»; «100m IM», «100 estils» -> «100 estils».
"""

import re

ESTILS = {
    "crol": "crol", "lliure": "crol", "lliures": "crol", "free": "crol",
    "estils": "estils", "im": "estils",
    "papallona": "papallona", "pap": "papallona",
    "esquena": "esquena", "braça": "braça", "braca": "braça",
}


def clau_prova(prova: str) -> str | None:
    """Clau canònica «<distància> <estil>», o None si no es reconeix."""
    m = re.match(r"\s*(\d+)\s*m?\s+(.+)", prova.lower())
    if not m:
        return None
    estil = ESTILS.get(m.group(2).strip().split()[0])
    return f"{m.group(1)} {estil}" if estil else None


def mateixa_prova(a: str, b: str) -> bool:
    """Compara dos noms de prova per la clau; si no es reconeixen, pel text."""
    ca, cb = clau_prova(a), clau_prova(b)
    if ca and cb:
        return ca == cb
    return a.strip().lower() == b.strip().lower()

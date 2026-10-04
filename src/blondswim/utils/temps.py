"""Temps de natació: parseig de textos («1:17.08», «1'17\"08», «38\"86») i format."""

import re

_RE_TEMPS = re.compile(
    r"""^(?:(?P<min>\d+)\s*[:'])?      # minuts opcionals: 1:  o 1'
        \s*(?P<seg>\d+)                # segons
        (?:\s*[."]\s*(?P<frac>\d+))?   # fracció: .08 o "08
        \s*"?$                         # cometes finals opcionals
    """,
    re.VERBOSE,
)


def parsejar_temps(valor: float | str) -> float:
    """Temps en segons.

    Accepta números (77.08) i textos «1:17.08», «1'17.08», «1'17\"08», «77.08»,
    «38\"86» o «0:38.86». La coma decimal també val.

    Raises:
        ValueError: format no reconegut o segons >= 60 quan hi ha minuts.
    """
    if isinstance(valor, bool):
        # ValueError (no TypeError) perquè pydantic el converteixi en error de validació.
        raise ValueError(f"Temps no vàlid: {valor!r}")  # noqa: TRY004
    if isinstance(valor, int | float):
        if valor <= 0:
            raise ValueError(f"Temps no vàlid: {valor!r}")
        return float(valor)
    text = str(valor).strip().replace(",", ".")
    m = _RE_TEMPS.match(text)
    if not m:
        raise ValueError(f"Temps '{valor}' no reconegut (exemples: 1:17.08, 1'17\"08, 38.86)")
    minuts = int(m.group("min")) if m.group("min") else 0
    segons = int(m.group("seg"))
    if m.group("min") and segons >= 60:
        raise ValueError(f"Temps '{valor}': els segons han de ser < 60")
    frac = float("0." + m.group("frac")) if m.group("frac") else 0.0
    total = minuts * 60 + segons + frac
    if total <= 0:
        raise ValueError(f"Temps no vàlid: {valor!r}")
    return total


def format_temps(segons: float, decimals: int = 1) -> str:
    """77.08 -> «1'17\"1»; 38.86 -> «38\"9» (notació de la piscina)."""
    arrodonit = round(segons, decimals)
    minuts = int(arrodonit // 60)
    resta = round(arrodonit - minuts * 60, decimals)
    if minuts:
        amplada = 2 + (decimals + 1 if decimals else 0)
        text = f"{resta:0{amplada}.{decimals}f}"
    else:
        text = f"{resta:.{decimals}f}"
    if decimals:
        return (f"{minuts}'" if minuts else "") + text.replace(".", '"')
    return (f"{minuts}'" if minuts else "") + text + '"'

"""Client configuration for LLM API (Anthropic Claude)."""

import os
from typing import Final

import anthropic
from dotenv import load_dotenv


class LLMConfigError(Exception):
    """Error en la configuració del client LLM."""


# Carregar variables d'entorn
load_dotenv(override=True)

# Model per defecte
DEFAULT_MODEL: Final[str] = os.getenv(
    "LLM_MODEL", "claude-sonnet-4-20241022"
)


def get_llm_client() -> anthropic.Anthropic:
    """
    Obtenir client configurat per a l'API d'Anthropic.

    Returns:
        Client d'Anthropic configurat amb l'API key de l'entorn

    Raises:
        LLMConfigError: Si ANTHROPIC_API_KEY no està definida a l'entorn
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMConfigError(
            "ANTHROPIC_API_KEY no està definida a les variables d'entorn. "
            "Defineix-la al fitxer .env o com a variable d'entorn del sistema."
        )

    return anthropic.Anthropic(api_key=api_key)

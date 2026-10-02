# BlondSwim

Sistema de planificació d'entrenament de natació per a màsters: periodització de la temporada, organització setmanal, contingut de cada sessió (generat amb Claude dins de límits deterministes), full per a la piscina i seguiment de la càrrega i la recuperació.

Documentació detallada a `data/raw/docs/`: `Architecture.md` (visió general), `Fase1.md`-`Fase3.md` (decisions, evidència i estat de cada fase).

## Instal·lació

```bash
make setup                 # crea .venv i instal·la el paquet amb les dependències de dev
cp .env.example .env       # i posa-hi ANTHROPIC_API_KEY
.venv/bin/python -m pytest -q && ruff check .
```

Opcional: `LLM_MODEL` a `.env` per canviar el model (per defecte `claude-sonnet-5`).

## Dades (`data/processed/`, fora de git)

| Fitxer | Contingut |
|---|---|
| `nedador_jep.json` | Fitxa del nedador: proves objectiu, `ritmes_css`, `setmana_tipus` (natació i gimnàs per franja), `rutina_espatlla_dia`, `prioritats_tecniques`, `volum_setmanal_min` |
| `calendari.json` | Competicions amb classe A/B/C (`make run-ingestion` des de l'Excel) |
| `historial_jep.json` | Sessions reals de la pretemporada (few-shot) |
| `registres/registre_*.xlsx` | Fulls de registre setmanals omplerts (RPE, SRSS, sèrie de control) |

## Ús setmanal

```bash
# 1. Generar la setmana del proper dilluns (o una de concreta)
python scripts/generar_temporada_jep.py [--dilluns 2026-10-05]
```

Sortides a `data/processed/`:
- `setmana_jep_<YYYY>-W<ww>.xlsx` — full per a la piscina. Cada dia porta la franja i el rol, i cada exercici la part de la sessió (escalfament, tècnica, bloc principal, tornada a la calma).
- `registres/registre_jep_<YYYY>-W<ww>.xlsx` — full de registre en blanc (no se sobreescriu si ja existeix).

```bash
# 2. Durant la setmana: omplir el full de registre
#    - Sessions: minuts reals i RPE 0-10 de cada sessió (natació i gimnàs), pots fer-ho al vespre
#    - Benestar (SRSS): cada dia d'entrenament, abans de la primera sessió
#    - Sèrie de control: 4x100 A2 del dimecres (temps, braçades/llargada, esforç)

# 3. La setmana següent, l'script avalua la setmana anterior (càrrega,
#    SRSS, sèrie de control) i mostra alertes i recomanacions.
```

Test CSS (400 + 200 m), per actualitzar les zones de ritme:

```bash
python scripts/registrar_test_css.py --t400 6:52.3 --t200 3:18.1 --data 2026-10-03 --simular
python scripts/registrar_test_css.py --t400 6:52.3 --t200 3:18.1 --data 2026-10-03
```

## Principis

- L'LLM només redacta els exercicis de les sessions de natació; volums, zones, rols, pressupost d'intensitat i validacions són deterministes.
- El sistema avisa i recomana; les decisions de canvi són sempre del coach.
- Cada regla està contrastada amb fonts i documentada (vegeu `Fase3.md`).

## Desenvolupament

- Tests: `.venv/bin/python -m pytest -q` · Lint: `ruff check .`
- Els canvis grans es lliuren com a patches `git am` (un commit per pas); aider només per a canvis petits d'un sol fitxer.

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

## Dades (fora de git): una carpeta per nedador

```
data/
├── competicions.json            catàleg comú (id, nom, dates, piscina)
└── nedadors/<id>/               <id> = identificador del nedador (jep, lou, cris, pere)
    ├── nedador.json             fitxa: proves objectiu, ritmes_css, setmana_tipus, ...
    ├── calendari.json           [{competicio_id, classe A/B/C, proves}]
    ├── historial.json           sessions reals (few-shot)
    ├── macrocicle.json          última temporada generada
    ├── setmanes/                setmana_<id>_<YYYY>-W<ww>.xlsx (full per a la piscina)
    ├── registres/               registre_<id>_<YYYY>-W<ww>.xlsx (RPE, SRSS, sèrie de control)
    └── log_decisions/
```

Les competicions són comunes; la classe A/B/C és de cada nedador. Per afegir un nedador: crea `data/nedadors/<id>/nedador.json` (amb `"id": "<id>"`) i el seu `calendari.json` apuntant als ids de `competicions.json`.

`make run-ingestion` regenera des dels Excel de `data/raw/` el catàleg, el calendari i l'historial del Jep; la fitxa `nedador.json` només es crea si no existeix.

**Migració des de l'estructura antiga** (`data/processed/`): `python scripts/migrar_a_carpetes.py --simular` i després sense `--simular`. Copia, no esborra.

## Ús setmanal

Executa els scripts des de l'arrel del repo.

```bash
# 1. Generar la setmana del proper dilluns (o una de concreta)
python scripts/generar_temporada.py --nedador jep [--dilluns 2026-10-05]
make setmana NEDADOR=jep [DILLUNS=2026-10-05]
```

Sortides a `data/nedadors/<id>/`:
- `setmanes/setmana_<id>_<YYYY>-W<ww>.xlsx` — full per a la piscina. Cada dia porta la franja i el rol, i cada exercici la part de la sessió (escalfament, tècnica, bloc principal, tornada a la calma).
- `registres/registre_<id>_<YYYY>-W<ww>.xlsx` — full de registre en blanc (no se sobreescriu si ja existeix).

```bash
# 2. Durant la setmana: omplir el full de registre
#    - Sessions: minuts reals i RPE 0-10 de cada sessió (natació i gimnàs), pots fer-ho al vespre
#    - Benestar (SRSS): cada dia d'entrenament, abans de la primera sessió
#    - Sèrie de control: 4x100 A2 del dimecres (temps, braçades/llargada, esforç)

# 3. La setmana següent, l'script avalua la setmana anterior (càrrega,
#    SRSS, sèrie de control) i mostra alertes i recomanacions.
```

Resultats de competició i progressió cap a l'objectiu A:

```bash
python scripts/registrar_resultat.py --nedador jep --competicio 2026-10-17_etapa-1 \
    --prova "100m Lliure" --temps 1:18.40 --parcials 18.3,19.9,20.1,20.1 --font video
python scripts/informe_progressio.py --nedador jep
```

Simulacions (contrarellotge en un entrenament): al calendari, `"tipus": "simulacio"`. Compten com a punt de control de la progressió però no alteren la planificació (sense mini-taper ni setmana post-competició). Poden apuntar a una competició del catàleg o definir-se amb `"data"` i `"piscina"`.

Test CSS (400 + 200 m), per actualitzar les zones de ritme:

```bash
python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1 --data 2026-10-03 --simular
python scripts/registrar_test_css.py --nedador jep --t400 6:52.3 --t200 3:18.1 --data 2026-10-03
```

## Principis

- L'LLM només redacta els exercicis de les sessions de natació; volums, zones, rols, pressupost d'intensitat i validacions són deterministes.
- El sistema avisa i recomana; les decisions de canvi són sempre del coach.
- Cada regla està contrastada amb fonts i documentada (vegeu `Fase3.md`).

## Desenvolupament

- Tests: `.venv/bin/python -m pytest -q` · Lint: `ruff check .`
- Els canvis grans es lliuren com a patches `git am` (un commit per pas); aider només per a canvis petits d'un sol fitxer.

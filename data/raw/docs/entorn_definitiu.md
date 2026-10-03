# BlondSwim — Guia definitiva d'entorn (ws_blondswim)

> **Rutes (2026-10-03).** Les dades ja no són a `data/processed/`: hi ha una carpeta per nedador, `data/nedadors/<id>/` (`nedador.json`, `calendari.json`, `historial.json`, `setmanes/`, `registres/`, `log_decisions/`), i el catàleg comú `data/competicions.json`. Les referències a `data/processed/`, `nedador_jep.json`, `historial_jep.json` o `calendari.json` amb classe d'aquest document són històriques; vegeu «Dades per nedador» a `Architecture.md`.

Versió definitiva i completa. Substitueix els esborranys anteriors (`fase0_setup.md`, `entorn_ws.md`). Decisions confirmades: Python 3.11, `pyproject.toml`, Makefile, documentació dins `docs/`.

---

## Pas 1 — Python 3.11

```bash
python3 --version
```

Si no la tens:
```bash
brew install python@3.11
```

Opcional (recomanat si tens/tindràs altres projectes Python amb versions diferents):
```bash
brew install pyenv
pyenv install 3.11.9
cd ws_blondswim
pyenv local 3.11.9      # crea .python-version
```

---

## Pas 2 — Entorn virtual del projecte

```bash
cd ws_blondswim
python3 -m venv .venv
source .venv/bin/activate
python --version         # confirma 3.11.x
```

A VS Code: `Cmd+Shift+P` → **Python: Select Interpreter** → `.venv/bin/python`.

---

## Pas 3 — Estructura de carpetes

```
ws_blondswim/
├── .venv/                       # no es versiona
├── .env                          # clau API real — NO es versiona
├── .env.example                  # plantilla — SÍ es versiona
├── .gitignore
├── .python-version                # si fas servir pyenv
├── pyproject.toml
├── README.md
├── Makefile
├── data/
│   ├── raw/                      # .xlsx originals
│   └── processed/                 # .json generats (no es versiona)
├── docs/
│   ├── guia_mvp.md
│   ├── fase0_setup.md
│   ├── guia_aider_fase0.md
│   └── architecture.md
├── src/
│   └── blondswim/
│       ├── __init__.py
│       ├── config.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── nedador.py
│       │   ├── calendari.py
│       │   ├── macrocicle.py
│       │   └── sessio.py
│       ├── ingestion/
│       │   ├── __init__.py
│       │   └── xlsx_to_json.py
│       └── agents/
│           └── __init__.py         # buit, Fase 1+
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── models/
    │   ├── test_nedador.py
    │   ├── test_calendari.py
    │   ├── test_macrocicle.py
    │   └── test_sessio.py
    └── ingestion/
        └── test_xlsx_to_json.py
```

```bash
mkdir -p src/blondswim/{models,ingestion,agents} data/{raw,processed} docs tests/{models,ingestion}
touch src/blondswim/__init__.py src/blondswim/config.py
touch src/blondswim/models/__init__.py
touch src/blondswim/models/{nedador,calendari,macrocicle,sessio}.py
touch src/blondswim/ingestion/__init__.py src/blondswim/ingestion/xlsx_to_json.py
touch src/blondswim/agents/__init__.py
touch tests/__init__.py tests/conftest.py
touch tests/models/{test_nedador,test_calendari,test_macrocicle,test_sessio}.py
touch tests/ingestion/test_xlsx_to_json.py
touch README.md Makefile .env .env.example
```

---

## Pas 4 — `pyproject.toml`

```toml
[project]
name = "blondswim"
version = "0.1.0"
description = "Sistema d'agents per a la planificació d'entrenament de natació"
requires-python = ">=3.11"
dependencies = [
    "anthropic",
    "openpyxl",
    "pydantic>=2.0",
    "python-dotenv",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

```bash
pip install -e ".[dev]"
```

---

## Pas 5 — Instal·lar aider (eina de desenvolupament, separada del projecte)

**Important**: aider NO va al `pyproject.toml` del projecte. És una eina de línia de comandes que tu fas servir per escriure codi — no una dependència que `blondswim` necessiti en temps d'execució. Instal·lar-la barrejada amb les dependències del projecte (`anthropic`, `pydantic`...) pot generar conflictes de versions, perquè aider gestiona moltes integracions de models diferents amb els seus propis requisits.

**Recomanat: instal·lació aïllada amb `pipx`** (gestiona automàticament les dependències pròpies d'aider en el seu propi entorn, sense tocar el `.venv` del projecte):

```bash
brew install pipx
pipx ensurepath
pipx install aider-chat
```

Tanca i torna a obrir la terminal (o `source ~/.zshrc`) perquè `aider` quedi disponible al `PATH`.

Verifica:
```bash
aider --version
```

**Configuració de la clau API per a aider**: aider llegeix `ANTHROPIC_API_KEY` de l'entorn, no del `.env` del projecte automàticament (pipx l'aïlla). Exporta-la abans d'invocar aider, cada sessió de terminal:

```bash
export $(cat .env | xargs)
aider --model sonnet
```

Si vols evitar fer-ho cada vegada, afegeix-ho al teu `~/.zshrc` (fora del repo, no versionat):
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
```

---

## Pas 6 — Configuració de la Claude API (per al codi del projecte)

`.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

`.env.example`:
```
ANTHROPIC_API_KEY=
```

`src/blondswim/config.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise RuntimeError("Falta ANTHROPIC_API_KEY al fitxer .env")
```

---

## Pas 7 — `.gitignore`

```
.venv/
.env
__pycache__/
*.pyc
*.egg-info/
data/processed/
.pytest_cache/
.ruff_cache/
.aider*
.DS_Store
```

(`.aider*` exclou els fitxers de cache/historial que aider crea al directori del projecte quan l'executes des d'aquí.)

---

## Pas 8 — `Makefile`

```makefile
.PHONY: setup test lint format run-ingestion aider clean

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"

test:
	. .venv/bin/activate && pytest -v

lint:
	. .venv/bin/activate && ruff check src tests

format:
	. .venv/bin/activate && ruff format src tests

run-ingestion:
	. .venv/bin/activate && python -m blondswim.ingestion.xlsx_to_json

aider:
	export $$(cat .env | xargs) && aider --model sonnet

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
```

Ús diari:
```bash
make setup           # un sol cop
make aider            # obre aider amb la clau carregada
make test
make lint
make run-ingestion
```

---

## Pas 9 — Documentació (`docs/`)

```bash
mv ~/Downloads/blondswim_guia_mvp.md docs/guia_mvp.md
mv ~/Downloads/blondswim_fase0_setup.md docs/fase0_setup.md
mv ~/Downloads/blondswim_guia_aider_fase0.md docs/guia_aider_fase0.md
```

`docs/architecture.md` — pendent de redactar (resum de les 5 capes, taula agent→determinista/LLM, regles de taper). Ho fem quan tanquis els models i el conversor, perquè reflecteixi el disseny final real, no una versió intermèdia.

---

## Pas 10 — `README.md`

```markdown
# BlondSwim

Sistema d'agents per generar plans d'entrenament de natació personalitzats,
basat en periodització esportiva (macro/meso/microcicle) i models específics
de natació (USRPT, polaritzat, Bowman) segons les proves objectiu de cada nedador.

## Requisits
- Python 3.11+
- [pipx](https://pipx.pypa.io/) i aider-chat (eina de desenvolupament, no dependència del projecte)
- Clau API d'Anthropic (Claude)

## Instal·lació
\`\`\`bash
make setup
cp .env.example .env   # afegeix la teva ANTHROPIC_API_KEY
pipx install aider-chat
\`\`\`

## Estructura del projecte
- `src/blondswim/models/` — esquemes de dades (pydantic)
- `src/blondswim/ingestion/` — conversors Excel → JSON
- `src/blondswim/agents/` — agents de planificació (Fase 1+)
- `data/raw/` — fitxers Excel originals
- `data/processed/` — JSON generats
- `docs/` — documentació del projecte i de cada fase
- `tests/` — tests unitaris

## Ús
\`\`\`bash
make aider             # desenvolupament assistit amb Claude
make run-ingestion      # converteix els Excel a JSON
make test                # executa els tests
\`\`\`

## Estat del projecte
Fase 0 — Setup i esquemes de dades (en curs). Vegeu `docs/guia_mvp.md`
per al pla complet de fases.
```

---

## Pas 11 — Primer test i primer commit

`tests/models/test_nedador.py`:
```python
from blondswim.models.nedador import Nedador

def test_nedador_es_crea_correctament():
    n = Nedador(
        id="jep",
        nom="Jep",
        categoria="master",
        proves_objectiu=["50 papallona", "100 lliure", "100 IM"],
        mode_ritme="temps",
    )
    assert n.id == "jep"
```

```bash
make test
```

Si passa en verd:
```bash
git init
git add .
git commit -m "Setup inicial: entorn, estructura src/, pyproject.toml, aider, docs"
```

---

## Checklist final

- [ ] `python --version` dins l'entorn virtual mostra 3.11.x.
- [ ] `make setup` s'executa sense errors.
- [ ] `aider --version` funciona (instal·lat via pipx, fora del `.venv` del projecte).
- [ ] `make aider` obre aider amb la clau API carregada correctament.
- [ ] `make test` passa (almenys el test mínim del Pas 11).
- [ ] `make lint` s'executa sense errors bloquejants.
- [ ] `git status` no mostra `.env`, `data/processed/` ni fitxers `.aider*` per fer commit.
- [ ] `docs/` conté els 3 documents previs (pendent `architecture.md`).

Un cop marcats tots els punts, l'entorn de `ws_blondswim` està definitivament llest. Següent pas: usar `make aider` amb els prompts de `docs/guia_aider_fase0.md` per generar els models `Macrocicle`/`Sessio` i el conversor.

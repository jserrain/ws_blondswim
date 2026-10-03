.PHONY: setup test lint format run-ingestion setmana aider clean

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

# Ús: make setmana NEDADOR=jep [DILLUNS=2026-10-05]
setmana:
	. .venv/bin/activate && python scripts/generar_temporada.py --nedador $(NEDADOR) \
		$(if $(DILLUNS),--dilluns $(DILLUNS))

MODEL ?= deepseek/deepseek-chat

aider:
	export $$(cat .env | xargs) && aider --model $(MODEL)

aidersonnet:
	export $$(cat .env | xargs) && aider --model sonnet


clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache

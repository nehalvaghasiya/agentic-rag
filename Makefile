.DEFAULT_GOAL := help
PYTHON := uv run --no-sync
.PHONY: help setup dev worker demo eval-demo format lint type test test-unit test-integration test-e2e test-security test-chaos contracts build smoke up down ci clean hf eval-hf metrics-dryrun
help:
	@echo 'setup | dev | worker | demo | eval-demo | metrics-dryrun | eval-hf | hf | format | lint | type | test | test-integration | test-e2e | test-security | test-chaos | contracts | build | smoke | up | down | ci | clean'
setup:
	uv sync --group dev
	cd frontend && npm ci
dev:
	npm run dev
worker:
	uv run agentic-rag worker --config configs/local.yaml
demo:
	AGENTIC_RAG_STORE=fake AGENTIC_RAG_PROVIDER=fake AGENTIC_RAG_EMBEDDING_PROVIDER=fake uv run agentic-rag demo --config configs/demo.yaml
eval-demo:
	AGENTIC_RAG_STORE=fake AGENTIC_RAG_PROVIDER=fake AGENTIC_RAG_EMBEDDING_PROVIDER=fake uv run agentic-rag eval --config configs/demo.yaml
metrics-dryrun:
	uv run python scripts/metric_dryrun.py
hf:
	uv run --extra hf agentic-rag fetch-hf --limit 50
eval-hf:
	uv run agentic-rag eval-hf --config configs/demo.yaml --limit 50
format:
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts
lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
type:
	uv run mypy --strict src/agentic_rag
test:
	uv run pytest tests -q
test-unit:
	uv run pytest tests/unit -q
test-integration:
	uv run pytest tests/integration -q
test-e2e:
	uv run pytest tests/e2e -q
test-security:
	uv run pytest tests/unit/test_security.py tests/e2e/test_access.py -q
test-chaos:
	uv run pytest tests/chaos -q
contracts:
	uv run python scripts/export.py
build:
	uv build
	cd frontend && npm run build
smoke:
	AGENTIC_RAG_STORE=fake AGENTIC_RAG_PROVIDER=fake AGENTIC_RAG_EMBEDDING_PROVIDER=fake uv run agentic-rag demo --config configs/demo.yaml
up:
	docker compose up -d postgres
down:
	docker compose down
ci: lint type test demo eval-demo metrics-dryrun contracts build
clean:
	rm -rf dist .pytest_cache .mypy_cache .ruff_cache reports

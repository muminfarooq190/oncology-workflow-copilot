.PHONY: help install test lint run-orchestrator run-web validate-contracts

help:
	@echo "install             Install Python and web dependencies"
	@echo "test                Run available unit and contract tests"
	@echo "lint                Run available linters"
	@echo "run-orchestrator    Start the FastAPI service"
	@echo "run-web             Start the React development server"
	@echo "validate-contracts  Validate JSON files and contract examples"

install:
	python3 -m pip install -e "./services/orchestrator[dev]"
	npm --prefix apps/web install

test: validate-contracts
	python3 -m pytest services/orchestrator/tests

lint:
	python3 -m ruff check services/orchestrator
	npm --prefix apps/web run lint

run-orchestrator:
	cd services/orchestrator && python3 -m uvicorn app.main:app --reload --port 8000

run-web:
	npm --prefix apps/web run dev

validate-contracts:
	python3 scripts/validate_repository.py


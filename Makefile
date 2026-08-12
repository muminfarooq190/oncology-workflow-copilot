.PHONY: help install test lint run-orchestrator run-web validate-contracts generate-week6 generate-week8 score-evals score-retrieval

help:
	@echo "install             Install Python and web dependencies"
	@echo "test                Run available unit and contract tests"
	@echo "lint                Run available linters"
	@echo "run-orchestrator    Start the FastAPI service"
	@echo "run-web             Start the React development server"
	@echo "validate-contracts  Validate JSON files and contract examples"
	@echo "generate-week8      Regenerate the deterministic 60-case development suite"
	@echo "score-evals          Score canonical predictions in evals/predictions"
	@echo "score-retrieval      Score frozen-corpus retrieval and enforce recall@5"

install:
	python3 -m pip install -e "./services/orchestrator[dev]"
	npm --prefix apps/web install

test: validate-contracts
	python3 -m pytest services/orchestrator/tests

lint:
	python3 -m ruff check services/orchestrator evals scripts
	npm --prefix apps/web run lint

run-orchestrator:
	cd services/orchestrator && python3 -m uvicorn app.main:app --reload --port 8000

run-web:
	npm --prefix apps/web run dev

validate-contracts:
	python3 scripts/validate_repository.py

generate-week6:
	python3 scripts/generate_week6_cases.py

generate-week8: generate-week6

score-evals:
	python3 -m evals.scorers.extraction evals/predictions --output evals/reports/extraction.json

score-retrieval:
	python3 -m evals.scorers.retrieval --output evals/reports/retrieval-week8.json --fail-below 0.90

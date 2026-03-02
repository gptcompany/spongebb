SHELL := /bin/bash

.PHONY: help build up up-dev down logs ps test-python test-visual test-visual-update \
	workspace workspace-dev workspace-logs api deploy api-local workspace-local \
	setup-credentials production status

help:
	@echo "Targets disponibili:"
	@echo ""
	@echo "  Production (always-on, Docker + dotenvx):"
	@echo "  make production          Build + avvia API + Workspace (restart: always)"
	@echo "  make deploy              Rebuild + redeploy API + Workspace"
	@echo "  make status              Stato container + health check"
	@echo "  make down                Ferma tutti i container"
	@echo "  make logs                Log API (follow)"
	@echo "  make ps                  Stato servizi compose"
	@echo ""
	@echo "  Locale (senza Docker, con dotenvx):"
	@echo "  make api-local           Avvia API locale (http://localhost:8003)"
	@echo "  make workspace-local     Avvia Workspace locale (http://localhost:6900)"
	@echo "  make setup-credentials   Scrive FRED key in OpenBB Platform config"
	@echo ""
	@echo "  Docker profili:"
	@echo "  make build               Build immagini dashboard + test"
	@echo "  make up                  Avvia dashboard container (http://localhost:8050)"
	@echo "  make up-dev              Avvia dashboard dev con --debug"
	@echo "  make api                 Avvia solo API Docker (http://localhost:8003)"
	@echo "  make workspace           Avvia solo Workspace Docker (http://localhost:6900)"
	@echo ""
	@echo "  Test:"
	@echo "  make test-python         Esegue pytest unit in container"
	@echo "  make test-visual         Esegue visual regression Playwright in container"
	@echo "  make test-visual-update  Rigenera baseline visual in container"

# ===========================================================================
# Production (always-on)
# ===========================================================================

production:
	dotenvx run -- docker compose build liquidity-api liquidity-workspace
	dotenvx run -- docker compose up -d liquidity-api liquidity-workspace
	@echo "Waiting for services..."
	@sleep 10
	@curl -sf http://localhost:8003/health > /dev/null && echo "API (8003): OK" || echo "API (8003): STARTING..."
	@curl -sf http://localhost:6900/health > /dev/null && echo "Workspace (6900): OK" || echo "Workspace (6900): STARTING..."
	@echo "Use 'make status' to verify full health."

deploy:
	dotenvx run -- docker compose build liquidity-api liquidity-workspace
	dotenvx run -- docker compose up -d liquidity-api liquidity-workspace
	@echo "Deployed. Use 'make status' to verify."

status:
	@echo "=== Container Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Health Checks ==="
	@curl -sf http://localhost:8003/health 2>/dev/null \
		| python3 -c "import sys,json; h=json.load(sys.stdin); print(f'API (8003): {h[\"status\"]}, QuestDB: {h[\"questdb_connected\"]}')" \
		|| echo "API (8003): DOWN"
	@curl -sf http://localhost:6900/health 2>/dev/null \
		&& echo "Workspace (6900): OK" \
		|| echo "Workspace (6900): DOWN"

# ===========================================================================
# Docker profili
# ===========================================================================

build:
	docker compose --profile dashboard --profile test build liquidity-dashboard liquidity-dashboard-test liquidity-pytest

up:
	docker compose --profile dashboard up -d liquidity-dashboard

up-dev:
	docker compose --profile dev up -d liquidity-dashboard-dev

down:
	docker compose down --remove-orphans
	docker compose --profile dashboard --profile dev --profile test --profile isolated down --remove-orphans

logs:
	docker compose logs -f liquidity-api

ps:
	docker compose ps -a

test-python:
	docker compose --profile test run --rm liquidity-pytest

test-visual:
	docker compose --profile test up -d liquidity-dashboard-test
	docker compose --profile test run --rm liquidity-playwright
	docker compose --profile test stop liquidity-dashboard-test

test-visual-update:
	docker compose --profile test up -d liquidity-dashboard-test
	docker compose --profile test run --rm liquidity-playwright bash -lc "npm ci && npm run test:visual:update"
	docker compose --profile test stop liquidity-dashboard-test

workspace:
	dotenvx run -- docker compose up -d liquidity-workspace

workspace-dev:
	dotenvx run -- docker compose up -d liquidity-workspace
	docker compose logs -f liquidity-workspace

workspace-logs:
	docker compose logs -f liquidity-workspace

api:
	dotenvx run -- docker compose up -d liquidity-api

# ===========================================================================
# Locale (senza Docker)
# ===========================================================================

api-local:
	dotenvx run -- uv run uvicorn liquidity.api:app --host 0.0.0.0 --port 8003

workspace-local:
	dotenvx run -- uv run openbb-api --app liquidity.openbb_ext.workspace_app:app --host 0.0.0.0 --port 6900

setup-credentials:
	@dotenvx run -- uv run python3 -c "\
	import json, os; \
	p = os.path.expanduser('~/.openbb_platform/user_settings.json'); \
	s = json.load(open(p)) if os.path.exists(p) else {}; \
	s.setdefault('credentials', {})['fred_api_key'] = os.environ['OPENBB_FRED_API_KEY']; \
	json.dump(s, open(p, 'w'), indent=2); \
	print(f'OK - credentials written to {p}')"

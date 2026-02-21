SHELL := /bin/bash

.PHONY: help build up up-dev down logs ps test-python test-visual test-visual-update workspace workspace-dev workspace-logs

help:
	@echo "Targets disponibili:"
	@echo "  make build               Build immagini dashboard + test"
	@echo "  make up                  Avvia dashboard container (http://localhost:8050)"
	@echo "  make up-dev              Avvia dashboard dev con --debug"
	@echo "  make down                Ferma e rimuove i container del progetto"
	@echo "  make logs                Mostra log dashboard"
	@echo "  make ps                  Stato servizi compose"
	@echo "  make test-python         Esegue pytest unit in container"
	@echo "  make test-visual         Esegue visual regression Playwright in container"
	@echo "  make test-visual-update  Rigenera baseline visual in container"
	@echo "  make workspace           Avvia OpenBB Workspace backend (http://localhost:6900)"
	@echo "  make workspace-dev       Avvia Workspace con log streaming"
	@echo "  make workspace-logs      Mostra log Workspace"

build:
	docker compose --profile dashboard --profile test build liquidity-dashboard liquidity-dashboard-test liquidity-pytest

up:
	docker compose --profile dashboard up -d liquidity-dashboard

up-dev:
	docker compose --profile dev up -d liquidity-dashboard-dev

down:
	docker compose --profile dashboard --profile dev --profile test --profile workspace down --remove-orphans

logs:
	docker compose --profile dashboard logs -f liquidity-dashboard

ps:
	docker compose --profile dashboard --profile dev --profile test ps

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
	docker compose --profile workspace up -d liquidity-workspace

workspace-dev:
	docker compose --profile workspace up -d liquidity-workspace
	docker compose --profile workspace logs -f liquidity-workspace

workspace-logs:
	docker compose --profile workspace logs -f liquidity-workspace

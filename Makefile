.PHONY: help up down restart pause unpause status health logs logs-all shell exec pull rebuild rebuild-service supabase-rebuild import-workflows clean ps services psql

PROJECT ?= localai
PROFILE ?= cpu
ENV ?= private
SERVICE ?= n8n
SHELL_CMD ?= /bin/bash
RUN ?=
LOG_ARGS ?=
PSQL_SERVICE ?= supabase-db
PSQL_DB ?= postgres
PSQL_USER ?= postgres
PSQL_EXTRA ?=
PYTHON ?= python
START_SCRIPT ?= start_services.py
COMPOSE_ROOT ?= docker-compose.yml
SUPABASE_COMPOSE ?= supabase/docker/docker-compose.yml
COMPOSE := docker compose -p $(PROJECT)

help: ## Show this help text
	@printf "Available targets:\n"
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Start Supabase + Local AI stack using start_services.py
	$(PYTHON) $(START_SCRIPT) --profile $(PROFILE) --environment $(ENV)

down: ## Stop both compose stacks (local AI first, then Supabase)
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) down
	$(COMPOSE) -f $(SUPABASE_COMPOSE) down

restart: ## Restart the entire stack
	$(MAKE) down
	$(MAKE) up

pause: ## Pause all containers without stopping them
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) pause || true
	$(COMPOSE) -f $(SUPABASE_COMPOSE) pause || true

unpause: ## Resume previously paused containers
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) unpause || true
	$(COMPOSE) -f $(SUPABASE_COMPOSE) unpause || true

status: ## Show container status for the project
	$(COMPOSE) ps

services: ## List service names only
	$(COMPOSE) ps --services

health: ## Display container health table (if defined)
	$(COMPOSE) ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}'

logs: ## Follow logs for a specific service (override SERVICE, LOG_ARGS)
	$(COMPOSE) logs -f $(LOG_ARGS) $(SERVICE)

logs-all: ## Follow logs for every service
	$(COMPOSE) logs -f $(LOG_ARGS)

shell: ## Open an interactive shell inside SERVICE (default /bin/bash)
	$(COMPOSE) exec $(SERVICE) $(SHELL_CMD)

exec: ## Run an arbitrary command inside SERVICE (set RUN="...")
ifndef RUN
	$(error Please provide RUN="<command>" e.g. RUN="redis-cli ping")
endif
	$(COMPOSE) exec $(SERVICE) sh -c '$(RUN)'

pull: ## Pull latest images for both compose files
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) pull
	$(COMPOSE) -f $(SUPABASE_COMPOSE) pull

rebuild: ## Rebuild and recreate local AI services for the current profile
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) build --pull
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) up -d

rebuild-service: ## Rebuild + restart a single service (override SERVICE)
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) build --pull $(SERVICE)
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) up -d $(SERVICE)

supabase-rebuild: ## Rebuild + restart Supabase services (rare)
	$(COMPOSE) -f $(SUPABASE_COMPOSE) build --pull
	$(COMPOSE) -f $(SUPABASE_COMPOSE) up -d

import-workflows: ## Re-run the n8n-import helper (credentials + workflows)
	$(COMPOSE) run --rm n8n-import

psql: ## Launch psql inside PSQL_SERVICE (override PSQL_SERVICE/DB/USER)
	$(COMPOSE) exec $(PSQL_SERVICE) psql -U $(PSQL_USER) $(PSQL_DB) $(PSQL_EXTRA)

clean: ## Stop everything and remove volumes (destructive)
	$(COMPOSE) -f $(COMPOSE_ROOT) --profile $(PROFILE) down -v
	$(COMPOSE) -f $(SUPABASE_COMPOSE) down -v

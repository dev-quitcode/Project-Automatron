.PHONY: help dev build up down logs golden test lint format clean secrets

# ── Default ────────────────────────────────────────────────
help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Development ───────────────────────────────────────────
dev: ## Run orchestrator in dev mode (hot-reload)
	cd orchestrator && uvicorn orchestrator.main:app --reload --host 0.0.0.0 --port 8000

dev-ui: ## Run Next.js in dev mode
	cd web-ui && pnpm dev

# ── Docker ─────────────────────────────────────────────────
golden: ## Build the Golden Image
	docker build -t automatron/golden:latest -f docker/golden-image/Dockerfile docker/golden-image/

build: ## Build all Docker images
	docker compose build

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail all service logs
	docker compose logs -f

logs-api: ## Tail orchestrator logs only
	docker compose logs -f orchestrator

logs-ui: ## Tail web-ui logs only
	docker compose logs -f web-ui

# ── Testing ────────────────────────────────────────────────
test: ## Run all tests
	cd orchestrator && python -m pytest tests/ -v

test-cov: ## Run tests with coverage
	cd orchestrator && python -m pytest tests/ -v --cov=orchestrator --cov-report=term-missing

# ── Code Quality ──────────────────────────────────────────
lint: ## Lint Python code
	cd orchestrator && ruff check .

format: ## Format Python code
	cd orchestrator && ruff format .

typecheck: ## Run mypy type checking
	cd orchestrator && mypy orchestrator/

# ── Setup ──────────────────────────────────────────────────
install: ## Install Python dependencies
	cd orchestrator && pip install -e ".[dev]"

install-ui: ## Install frontend dependencies
	cd web-ui && pnpm install

secrets: ## Create secrets directory with placeholder files
	@mkdir -p secrets
	@test -f secrets/openai_api_key.txt    || echo "sk-REPLACE_ME" > secrets/openai_api_key.txt
	@test -f secrets/anthropic_api_key.txt || echo "sk-ant-REPLACE_ME" > secrets/anthropic_api_key.txt
	@test -f secrets/google_api_key.txt    || echo "AI-REPLACE_ME" > secrets/google_api_key.txt
	@echo "Secrets directory ready. Edit files in ./secrets/ with real keys."

# ── Cleanup ────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/*.db 2>/dev/null || true

clean-docker: ## Remove project containers and images
	docker compose down -v --rmi local
	docker rmi automatron/golden:latest 2>/dev/null || true

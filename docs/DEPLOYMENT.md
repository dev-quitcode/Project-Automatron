# Deployment Guide — Project Automatron

## Prerequisites

- **OS**: Ubuntu 22.04+ / Debian 12+ (Linux VPS)
- **Docker**: 24.0+ with Docker Compose v2
- **RAM**: 4 GB minimum (8 GB recommended)
- **Disk**: 20 GB minimum
- **Ports**: 80 (nginx), 8000 (API), 3000 (UI), 7000-7999 (project previews)

## Quick Start (Development)

### 1. Clone & configure

```bash
git clone <repo-url> automatron
cd automatron

# Create secrets
make secrets
# Edit secrets with real API keys:
nano secrets/openai_api_key.txt
nano secrets/anthropic_api_key.txt

# Copy env template
cp .env.example .env
# Edit with your preferred models/settings
nano .env
```

### 2. Build Golden Image

```bash
make golden
```

This builds the `automatron/golden:latest` Docker image with Ubuntu 24.04,
Node.js 22, Python 3.12, and Cline CLI pre-installed.

### 3. Run in development mode

**Option A: Docker Compose (recommended)**

```bash
make build
make up
```

- API: http://localhost:8000
- UI: http://localhost:3000
- Logs: `make logs`

**Option B: Local development (hot-reload)**

```bash
# Terminal 1: Backend
cd orchestrator
pip install -e ".[dev]"
uvicorn orchestrator.main:combined_app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd web-ui
pnpm install
pnpm dev
```

### 4. Run tests

```bash
make test
```

## Production Deployment

### 1. Build and start with nginx

```bash
# Build all images
make golden
docker compose build

# Start with nginx reverse proxy
docker compose --profile production up -d
```

The nginx profile adds a reverse proxy on port 80 that routes:
- `/api/*` → orchestrator:8000
- `/socket.io/*` → orchestrator:8000 (WebSocket)
- `/*` → web-ui:3000

### 2. Environment variables

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google AI API key |
| `ARCHITECT_MODEL` | `anthropic/claude-sonnet-4-20250514` | LLM for planning |
| `BUILDER_MODEL` | `anthropic/claude-sonnet-4-20250514` | LLM for Cline |
| `REVIEWER_MODEL` | `openai/gpt-4.1-mini` | LLM for status classification |
| `SQLITE_DB_PATH` | `./data/automatron.db` | Project database path |
| `CHECKPOINT_DB_PATH` | `./data/checkpoints.db` | LangGraph checkpoint DB |
| `GOLDEN_IMAGE` | `automatron/golden:latest` | Docker image for builders |
| `WORKSPACE_BASE_PATH` | `/var/automatron/workspaces` | Volume mount base |
| `PORT_RANGE_START` | `7000` | Preview port range start |
| `PORT_RANGE_END` | `7999` | Preview port range end |
| `CONTAINER_MEMORY_LIMIT` | `2g` | RAM limit per container |
| `CONTAINER_CPU_LIMIT` | `2.0` | CPU limit per container |
| `CLINE_TIMEOUT` | `300` | Cline CLI timeout (seconds) |
| `MAX_ESCALATIONS` | `2` | Max re-plan attempts per task |

### 3. Docker Secrets (recommended for production)

API keys are read from Docker Secrets at `/run/secrets/`:

```bash
# Create secret files (already done by `make secrets`)
echo "sk-real-key-here" > secrets/openai_api_key.txt
echo "sk-ant-real-key" > secrets/anthropic_api_key.txt
echo "AI-real-key" > secrets/google_api_key.txt
```

The orchestrator's `SecretsManager` reads these automatically at startup.

### 4. Data persistence

- `./data/`: SQLite databases (project DB + LangGraph checkpoints)
- `/var/automatron/workspaces/`: Project workspace volumes (one per project)

**Backup**: Simply copy the `./data/` directory. SQLite WAL mode ensures safe copying.

### 5. Monitoring

- Health endpoint: `GET /health` → `{"status": "ok"}`
- Docker healthcheck: built into orchestrator Dockerfile (30s interval)
- Logs: `docker compose logs -f orchestrator`

## Makefile Commands Reference

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make dev` | Run orchestrator with hot-reload |
| `make dev-ui` | Run Next.js with hot-reload |
| `make golden` | Build the Golden Image |
| `make build` | Build all Docker images |
| `make up` | Start all services |
| `make down` | Stop all services |
| `make logs` | Tail all service logs |
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage |
| `make lint` | Lint Python code |
| `make format` | Format Python code |
| `make secrets` | Create secrets directory with placeholders |
| `make clean` | Remove build artifacts |
| `make clean-docker` | Remove containers and images |
| `make install` | Install Python dependencies locally |
| `make install-ui` | Install frontend dependencies locally |

## Troubleshooting

### Container can't access Docker socket

```bash
# Add your user to docker group
sudo usermod -aG docker $USER
# OR adjust socket permissions
sudo chmod 666 /var/run/docker.sock
```

### Port already in use

Check allocated ports in the SQLite DB:
```bash
sqlite3 data/automatron.db "SELECT * FROM port_allocations;"
```

### Cline CLI timeout

Increase `CLINE_TIMEOUT` in `.env` or pass `--timeout` directly.
Default is 300 seconds (5 minutes) per task.

### LangGraph checkpoint corruption

Delete the checkpoint DB and restart:
```bash
rm data/checkpoints.db
make down && make up
```
Note: This loses all checkpoint history and paused/frozen project states.

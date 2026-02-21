# Architecture — Project Automatron

## System Overview

Automatron is an autonomous software development system that uses LLM agents
orchestrated by LangGraph to plan, build, review, and iterate on software projects
inside isolated Docker containers.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                       Web UI (Next.js 15)                    │
│  ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Chat   │ │ Plan.md  │ │ Builder  │ │  Status / Alert  │  │
│  │ Panel  │ │ Editor   │ │  Logs    │ │     Panel        │  │
│  └───┬────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│      │           │            │                 │            │
│      └───────────┴────────────┴─────────────────┘            │
│                          │                                   │
│              Socket.IO + REST API                            │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│                  Orchestrator (FastAPI)                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              LangGraph StateGraph                      │  │
│  │                                                        │  │
│  │  ┌──────────┐    ┌──────────────┐    ┌──────────────┐ │  │
│  │  │Architect │───▶│ Human Review │───▶│  Scaffold    │ │  │
│  │  │ (LLM)   │    │ (interrupt)  │    │ (Docker+Init)│ │  │
│  │  └──────────┘    └──────────────┘    └──────┬───────┘ │  │
│  │       ▲                                      │        │  │
│  │       │                              ┌───────▼──────┐ │  │
│  │  ┌────┴─────┐                        │Task Selector │ │  │
│  │  │  Freeze  │◀──── escalation ──┐    │(PLAN.md parse│ │  │
│  │  │(anti-loop│    exceeded       │    └───────┬──────┘ │  │
│  │  └──────────┘                   │            │        │  │
│  │                          ┌──────┴──────┐     │        │  │
│  │                          │  Status     │     │        │  │
│  │                          │ Classifier  │◀────┘        │  │
│  │                          │  (Review)   │  ┌────────┐  │  │
│  │                          └──────┬──────┘  │Builder │  │  │
│  │                                 │         │(Cline) │  │  │
│  │                                 └────────▶│        │  │  │
│  │                                           └────────┘  │  │
│  │                                                       │  │
│  │  Checkpoint: SqliteSaver (time-travel + persistence)  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────────┐ │
│  │ LLM      │  │ Docker    │  │ Port     │  │  Secret    │ │
│  │ Provider  │  │ Engine    │  │ Allocator│  │  Manager   │ │
│  │ (litellm) │  │ Manager   │  │ (SQLite) │  │  (Docker)  │ │
│  └──────────┘  └─────┬─────┘  └──────────┘  └────────────┘ │
└────────────────────────┼─────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Golden Image       │
              │  Docker Container   │
              │  ┌────────────────┐ │
              │  │ Ubuntu 24.04   │ │
              │  │ Node.js 22     │ │
              │  │ Python 3.12    │ │
              │  │ Cline CLI      │ │
              │  │ /workspace     │ │
              │  └────────────────┘ │
              └─────────────────────┘
```

## Component Details

### 1. Web UI (Next.js 15)
- **Framework**: Next.js 15 App Router
- **Styling**: Tailwind CSS with dark mode
- **State**: Zustand store for project/chat/plan/log state
- **Real-time**: Socket.IO client for streaming events
- **Key pages**: Dashboard (project list), Project view (chat + plan + logs)

### 2. Orchestrator (FastAPI + LangGraph)
- **REST API**: Project CRUD, start/stop/approve, plan management, logs
- **WebSocket**: Socket.IO for real-time architect messages, builder logs, status
- **Graph**: 8-node LangGraph StateGraph with conditional routing
- **Checkpoints**: SqliteSaver for persistence + time-travel

### 3. LangGraph Nodes

| Node | Purpose | LLM? |
|------|---------|------|
| `architect` | Generate/revise PLAN.md from user description | Yes (Claude/GPT) |
| `human_review` | `interrupt()` — waits for user approval | No |
| `scaffold` | Create Docker container, run init script, inject API keys | No |
| `task_selector` | Parse PLAN.md for next `[ ]` task | No |
| `builder` | Execute task via Cline CLI in container | Yes (via Cline) |
| `status_classifier` | Classify build result (SUCCESS/BLOCKER/AMBIGUITY) | Yes (gpt-4.1-mini) |
| `freeze` | Anti-loop protection when escalations > MAX | No |
| `completion` | Final node — marks project complete | No |

### 4. Docker Container Strategy
- **Golden Image**: Base image with all runtimes pre-installed
- **Per-project container**: Isolated workspace with volume mount
- **Cline CLI**: Runs headless in `-y` (auto-approve) mode inside container
- **Port allocation**: Dynamic port mapping (7000-7999) for live previews

### 5. Data Flow

1. User creates project with description
2. Architect LLM generates PLAN.md + STACK_CONFIG.json
3. Human reviews and approves plan
4. Scaffold creates Docker container with proper runtime
5. Task selector picks first `[ ]` task from PLAN.md
6. Builder runs Cline CLI with task prompt
7. Status classifier evaluates result
8. Loop: next task or escalate to architect
9. Completion when all tasks are `[x]`

### 6. Anti-Loop Protection
- Per-task escalation counter (max 2 by default)
- If MAX_ESCALATIONS exceeded → `freeze` node → `interrupt()` for human
- Escalation history tracked in state for debugging

### 7. Database Schema (SQLite)

```
projects     → id, name, status, plan_md, stack_config_json, container_id, port
sessions     → id, project_id, thread_id, phase, started_at, ended_at
task_logs    → id, session_id, task_index, task_text, status, cline_output, duration_s
chat_messages → id, project_id, role, content, created_at
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, Tailwind CSS, Zustand, Socket.IO |
| Backend | FastAPI, Python 3.12, uvicorn |
| Orchestration | LangGraph 1.x, SqliteSaver |
| LLM | litellm (Claude, GPT, Gemini) |
| Containers | Docker SDK for Python, Golden Image |
| Code Agent | Cline CLI 2.x (headless mode) |
| Database | SQLite (WAL mode) |
| Reverse Proxy | Nginx (production) |

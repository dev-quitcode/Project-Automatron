# Automatron Orchestrator

LangGraph-based orchestration service for Project Automatron.

## Development

Create and activate a virtual environment, then install the package in editable
mode with development dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Running

Start the FastAPI app locally with:

```powershell
uvicorn orchestrator.main:app --reload
```

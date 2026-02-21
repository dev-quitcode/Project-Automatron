#!/bin/bash
set -e

echo "=== Automatron: Generic project initialization ==="
cd /workspace

# Initialize git if not already
if [ ! -d .git ]; then
    git init
    echo "node_modules/" > .gitignore
    echo "__pycache__/" >> .gitignore
    echo ".env" >> .gitignore
    echo ".venv/" >> .gitignore
fi

echo "=== Generic scaffold complete (Cline will handle framework init) ==="

#!/bin/bash
set -e

echo "=== Automatron: Initializing Python project ==="
cd /workspace

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Create basic structure
mkdir -p src tests
touch src/__init__.py
touch tests/__init__.py

# Create pyproject.toml if it doesn't exist
if [ ! -f pyproject.toml ]; then
    cat > pyproject.toml << 'EOF'
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[tool.pytest.ini_options]
testpaths = ["tests"]
EOF
fi

echo "=== Python scaffold complete ==="

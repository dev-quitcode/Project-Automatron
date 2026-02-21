#!/bin/bash
set -e

echo "=== Automatron: Initializing React + Vite project ==="
cd /workspace

# Initialize Vite with React + TypeScript
npm create vite@latest . -- --template react-ts

# Install dependencies
npm install

# Install Tailwind CSS
npm install -D tailwindcss @tailwindcss/vite

echo "=== React + Vite scaffold complete ==="

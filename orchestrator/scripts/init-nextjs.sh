#!/bin/bash
set -e

echo "=== Automatron: Initializing Next.js project ==="
cd /workspace

# Initialize Next.js with TypeScript, Tailwind, ESLint, App Router
npx --yes create-next-app@latest . \
    --typescript \
    --tailwind \
    --eslint \
    --app \
    --no-src-dir \
    --import-alias "@/*" \
    --use-pnpm

# Clean up default content
echo "" > app/globals.css
cat > app/globals.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF

echo "=== Next.js scaffold complete ==="

# ============================================================
# Automatron Web UI — Next.js Production Build
# ============================================================

FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY web-ui/package*.json ./
RUN npm ci

# Copy source
COPY web-ui/ ./

# Build
RUN npm run build

# ── Production stage ────────────────────────────────────────
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built assets
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]

# ============================================================
# Automatron Web UI - Next.js Production Build
# ============================================================

FROM node:22-alpine AS builder

WORKDIR /app

COPY web-ui/package*.json ./
RUN npm install

COPY web-ui/ ./

RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]

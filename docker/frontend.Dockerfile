# Build context: repo root (.)
# Base image pinned by digest. Refresh with:
#   docker buildx imagetools inspect node:20-slim
FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS base
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install

FROM deps AS dev
COPY frontend/ .
EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]

FROM deps AS builder
COPY frontend/ .
ENV NEXT_OUTPUT=standalone
RUN pnpm build

FROM base AS runner
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER app
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]

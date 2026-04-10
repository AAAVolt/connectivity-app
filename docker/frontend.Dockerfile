# Build context: repo root (.)
FROM node:20-slim AS base
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

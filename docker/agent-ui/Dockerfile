# =============================================================================
# Agno Agent UI — self-hosted native chat/control surface (agno-agi/agent-ui)
# =============================================================================
# Open-source Next.js + TypeScript UI for AgentOS. Runs in the browser and talks
# DIRECTLY to the AgentOS API (agentos-api) — no data passes through Agno's cloud
# and this container holds NO secrets/DB. It only serves the static/SSR frontend.
#
# The AgentOS endpoint is selected in the UI's connect dialog (point it at the
# api hostname, e.g. https://api.int.mitechconsult.com). Internal surface
# (chat.int.*); a gated public twin (chat.*) comes via Traefik later.
#
# NOTE: cloned from main (no upstream Docker image / stable tag). Pin to a commit
# once we lock a known-good build.
# =============================================================================
FROM node:22-alpine AS build
RUN apk add --no-cache git
WORKDIR /app
RUN git clone --depth 1 https://github.com/agno-agi/agent-ui.git . \
 && corepack enable \
 && pnpm install --no-frozen-lockfile \
 && pnpm build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
RUN corepack enable
EXPOSE 3000
CMD ["pnpm", "start"]

# Byline: Claude Code · Opus 4.8 · 2026-06-14

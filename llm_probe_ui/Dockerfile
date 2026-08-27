FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# NEXT_PUBLIC_* vars are inlined into the client bundle at build time, not
# read at container runtime — must be an ARG here (Coolify passes it via
# --build-arg since it's also declared under this app's `environment:`),
# not just a runtime environment var on the container.
ARG NEXT_PUBLIC_LLM_PROBE_URL
ENV NEXT_PUBLIC_LLM_PROBE_URL=$NEXT_PUBLIC_LLM_PROBE_URL
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# Docker sets HOSTNAME to the container's own id inside every container, and
# the Next.js standalone server binds to process.env.HOSTNAME if set instead
# of 0.0.0.0 — so without this override it "starts" and logs Ready, but
# listens on an address nothing can reach (not even from inside the same
# container). Must override, not just default in code.
ENV HOSTNAME=0.0.0.0
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]

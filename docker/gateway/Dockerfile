# =============================================================================
# gateway — OpenCode + LiteLLM in one container (owner decision 2026-06-10)
# Byline: Claude Code · Kimi K3 (drift-fix) · 2026-08-12 — header annotated:
#         LiteLLM proxy DISABLED (ADR-0042); Portkey is the active gateway.
# =============================================================================
# NB 2026-08-12 (ADR-0042): the LiteLLM proxy is baked here but DISABLED —
# supervisord.conf has `autostart=false` (owner 2026-07-29: keep the binary,
# prevent the process). Nothing listens behind :4000. The active model gateway
# is PORTKEY — deployed from deploy/portkey.yaml, not from this image.
# Two processes under supervisord (one container, not two):
#   - ~~LiteLLM proxy on :4000~~ DISABLED (see NB above) — was the unified
#     OpenAI-compatible gateway over NVIDIA
#     NIM / Ollama Cloud / Anthropic / etc. (config: litellm-config.yaml)
#   - OpenCode server on :4096 — agent/CLI gateway (`opencode serve`)
# ~~Agents and n8n hit ONE model endpoint (:4000) regardless of provider.~~
# Corrected 2026-08-12: that endpoint is dead locally; production model traffic
# goes through Portkey (deploy/portkey.yaml).

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl nodejs npm supervisor ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir 'litellm[proxy]' \
    && npm install -g opencode-ai

COPY litellm-config.yaml /etc/litellm/config.yaml
COPY supervisord.conf /etc/supervisor/conf.d/gateway.conf
EXPOSE 4000 4096
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]

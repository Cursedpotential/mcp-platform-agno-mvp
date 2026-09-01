# Tracked LibreChat runtime configuration.
#
# The upstream application image remains pinned by digest. Baking the
# repository-owned, secret-free config into the derived image makes a normal
# Coolify rebuild deploy the exact reviewed MCP routing contract; operators no
# longer have to copy a second host file that can drift from Git.
#
# Byline: Codex · GPT-5.6-Sol · 2026-08-29

FROM ghcr.io/danny-avila/librechat@sha256:c5db3331b845e1f289f8d04c0c77936c4bbe372f76730a804abc1c37e44d23a9

COPY docker/librechat/librechat.yaml /app/librechat.yaml

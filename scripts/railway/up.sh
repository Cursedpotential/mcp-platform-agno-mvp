#!/bin/bash

############################################################################
#
#    Agno Railway Setup (first-time provisioning)
#
#    Usage:     ./scripts/railway/up.sh
#    Redeploy:  ./scripts/railway/redeploy.sh
#    Sync env:  ./scripts/railway/env-sync.sh
#
#    Prerequisites:
#      - Railway CLI installed
#      - Logged in via `railway login`
#      - OPENAI_API_KEY set in environment (or .env / .env.production)
#
############################################################################

set -e

# Colors
ORANGE='\033[38;5;208m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${ORANGE}"
cat << 'BANNER'
     █████╗  ██████╗ ███╗   ██╗ ██████╗
    ██╔══██╗██╔════╝ ████╗  ██║██╔═══██╗
    ███████║██║  ███╗██╔██╗ ██║██║   ██║
    ██╔══██║██║   ██║██║╚██╗██║██║   ██║
    ██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝
    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝
BANNER
echo -e "${NC}"

# Load env file — .env.production preferred for Railway, .env as fallback.
# Parsed line-by-line (not `source`d) so an unquoted multi-line PEM
# JWT_VERIFICATION_KEY isn't interpreted as shell. Mirrors the parser in
# env-sync.sh so both scripts read .env files identically.
ENV_FILE=""
[[ -f .env.production ]] && ENV_FILE=".env.production"
[[ -z "$ENV_FILE" && -f .env ]] && ENV_FILE=".env"

if [[ -n "$ENV_FILE" ]]; then
    current_key=""
    current_value=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ -z "$current_key" ]]; then
            [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        fi

        if [[ -z "$current_key" ]]; then
            current_key="${line%%=*}"
            current_value="${line#*=}"
        else
            current_value="${current_value}
${line}"
        fi

        # Still inside a PEM block — keep accumulating lines.
        if [[ "$current_value" == *"-----BEGIN"* && "$current_value" != *"-----END"* ]]; then
            continue
        fi

        # Strip surrounding quotes if present
        current_value="${current_value#\"}"
        current_value="${current_value%\"}"
        current_value="${current_value#\'}"
        current_value="${current_value%\'}"

        export "${current_key}=${current_value}"

        current_key=""
        current_value=""
    done < "$ENV_FILE"
    echo -e "${DIM}Loaded ${ENV_FILE}${NC}"
fi

# Preflight
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Install: https://docs.railway.app/guides/cli"
    exit 1
fi

if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "OPENAI_API_KEY not set. Add to .env (or .env.production) or export it."
    exit 1
fi

echo -e "${BOLD}Initializing project...${NC}"
echo ""
railway init -n "agent-platform"

echo ""
echo -e "${BOLD}Deploying PgVector database...${NC}"
echo ""
railway add -s pgvector -i agnohq/pgvector:18 \
    -v "POSTGRES_USER=${DB_USER:-ai}" \
    -v "POSTGRES_PASSWORD=${DB_PASS:-ai}" \
    -v "POSTGRES_DB=${DB_DATABASE:-ai}"

echo ""
echo -e "${BOLD}Adding database volume...${NC}"
railway service link pgvector
railway volume add -m /var/lib/postgresql 2>/dev/null || echo -e "${DIM}Volume already exists or skipped${NC}"

echo ""
echo -e "${DIM}Waiting 15s for database...${NC}"
sleep 15

echo ""
echo -e "${BOLD}Creating application service...${NC}"
echo ""
# Forward every relevant env var the first deploy might need. Optional
# keys are only included when set — Railway CLI rejects empty values.
# Use ./scripts/railway/env-sync.sh to sync the rest from .env later.
RAILWAY_VARS=(
    -v "DB_USER=${DB_USER:-ai}"
    -v "DB_PASS=${DB_PASS:-ai}"
    -v "DB_HOST=pgvector.railway.internal"
    -v "DB_PORT=${DB_PORT:-5432}"
    -v "DB_DATABASE=${DB_DATABASE:-platform}"
    -v "DB_DRIVER=postgresql+psycopg"
    -v "WAIT_FOR_DB=True"
    -v "PORT=8000"
    -v "OPENAI_API_KEY=${OPENAI_API_KEY}"
)
[[ -n "$PARALLEL_API_KEY" ]] && RAILWAY_VARS+=(-v "PARALLEL_API_KEY=${PARALLEL_API_KEY}")

railway add -s agent-os "${RAILWAY_VARS[@]}"

echo ""
echo -e "${BOLD}Deploying application...${NC}"
echo ""
railway up --service agent-os -d

echo ""
echo -e "${BOLD}Creating domain...${NC}"
echo ""
railway domain --service agent-os

echo ""
echo -e "${BOLD}Done.${NC} Domain may take ~5 minutes."
echo -e "${DIM}Logs:           railway logs --service agent-os${NC}"
echo -e "${DIM}Sync env vars:  ./scripts/railway/env-sync.sh  (defaults to .env.production)${NC}"
echo ""

# Deployment Guide

## Who This Is For

You — someone who needs to get the platform running on your machine. You don't need to be a programmer. Follow these steps exactly.

## Prerequisites

You need a computer running **Ubuntu** or **Fedora** Linux with:
- Docker installed (the thing that runs containers)
- Docker Compose installed (the thing that orchestrates multiple containers)
- An OpenAI API key (get one at https://platform.openai.com/api-keys)
- Git installed (to download the code)

### Check If Docker Is Installed

```bash
docker --version
docker compose version
```

If either says "command not found", install Docker first:

**Ubuntu:**
```bash
sudo apt update
sudo apt install docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# Log out and log back in after this
```

**Fedora:**
```bash
sudo dnf install docker docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and log back in after this
```

## Step 1: Download the Code

```bash
# Create a home for the project
mkdir -p ~/projects
cd ~/projects

# Download this repository
git clone https://github.com/Cursedpotential/mcp-platform-agno-mvp.git

# Enter the project folder
cd mcp-platform-agno-mvp
```

You should also download the MCP server code (the tools that parse evidence):

```bash
cd ~/projects

# Download the modular MCP servers
git clone https://github.com/Cursedpotential/MCP_PLATFORM.git

# The old platform (for reference — tools are being moved from here)
git clone https://github.com/Cursedpotential/mcp-tool-platform.git
```

## Step 2: Configure Environment Variables

```bash
cd ~/projects/mcp-platform-agno-mvp

# Copy the template
cp .env.example .env

# Edit the file
nano .env
```

Fill in these values (everything else can stay as-is):

```
# REQUIRED: Your OpenAI API key
OPENAI_API_KEY=sk-your-key-here

# REQUIRED: Database password (make up a strong one)
# You don't need to remember this — it's only used internally
PLATFORM_DB_URL=postgresql+psycopg://postgres:YOUR_STRONG_PASSWORD@postgres:5432/agno_platform

# REQUIRED: Where your MCP servers are installed
# Update the path to match where you cloned MCP_PLATFORM
TS_MCP_COMMAND=node /home/YOUR_USERNAME/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server/dist/index.js
PY_MCP_COMMAND=python /home/YOUR_USERNAME/projects/MCP_PLATFORM/mcp-servers/py-mcp-server/main.py

# OPTIONAL: API key for securing the web API
# If you leave this blank, the API is open (fine for local development)
# If you set it, all API requests need a header: X-API-Key: your-key
API_KEY=make-up-a-password-here

# OPTIONAL: n8n encryption keys
# Run this command to generate them:
# openssl rand -hex 32
N8N_ENCRYPTION_KEY=GENERATE_THIS
N8N_USER_MANAGEMENT_JWT_SECRET=GENERATE_THIS_TOO

# OPTIONAL: Cloudflare R2 credentials
# Only needed if you want cloud storage backup
# Leave blank for now — can be added later
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_ENDPOINT=
R2_BUCKET_NAME=
```

## Step 3: Create Local Storage Directories

```bash
cd ~/projects/mcp-platform-agno-mvp

# Create directories for persistent data
mkdir -p data/postgres_data
mkdir -p data/n8n_data
mkdir -p data/r2_share
mkdir -p knowledge/platform/conversations
mkdir -p knowledge/platform/docs
mkdir -p knowledge/platform/notes

# Set ownership (Linux file permissions)
sudo chown -R $USER:$USER data/
chmod -R 775 data/
```

## Step 4: Start Everything

```bash
cd ~/projects/mcp-platform-agno-mvp

# Build and start all containers
# This will take 5-10 minutes the first time
docker compose up -d
```

You should see output showing containers starting:
- `agno-postgres` — Database
- `agno-ts-mcp` — TypeScript MCP server (parsers)
- `agno-py-mcp` — Python MCP server (NLP analysis)
- `agno-agentos` — The main Agno control layer
- `mcp-n8n` — n8n workflow automation

Wait about 30 seconds for everything to initialize, then check:

```bash
# See all running containers
docker compose ps

# Check the main API is responding
curl http://localhost:8000/health

# You should see JSON like:
# {"status":"healthy","agents_ready":true,"db_connected":true}
```

## Step 5: Verify Each Component

### Check the API Documentation

Open your web browser and go to: **http://localhost:8000/docs**

You should see a Swagger UI page listing all available API endpoints.

### Check n8n

Open your web browser and go to: **http://localhost:5678**

You should see the n8n workflow builder. First-time setup will ask you to create an account.

### Check MCP Servers

```bash
# Check TypeScript MCP server (parsers)
curl http://localhost:3001/health 2>/dev/null || echo "TS MCP server not responding yet"

# Check Python MCP server (NLP)
curl http://localhost:3002/health 2>/dev/null || echo "Py MCP server not responding yet"
```

### Check Agent List

```bash
# List all 7 agents
curl http://localhost:8000/v1/agents
```

## Step 6: Test an Agent

```bash
# Talk to the Project PAL agent (safest — it's read-only)
curl -X POST http://localhost:8000/v1/agents/project_pal/run \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current status of the platform? What are the active blockers?"}'
```

If you set an API key in `.env`, add this header:
```bash
  -H "X-API-Key: your-api-key-here"
```

## Step 7: Add Your Knowledge

Put your documents and chat transcripts in the knowledge folder:

```bash
# Copy chat transcripts
# cp ~/Downloads/chatgpt-export.txt knowledge/platform/conversations/

# Copy project documents
# cp ~/Documents/project-spec.md knowledge/platform/docs/

# Copy notes
# cp ~/Documents/my-notes.txt knowledge/platform/notes/
```

Then index them:

```bash
# Index knowledge into the database
docker compose exec agentos python scripts/ingest_knowledge.py

# Mine transcripts for structured insights
docker compose exec agentos python scripts/mine_transcripts.py \
  knowledge/platform/conversations/ \
  --batch --recursive
```

## Step 8: Cloudflare R2 Cloud Storage (Optional)

If you want evidence backed up to cloud storage:

### Install rclone
```bash
# Ubuntu/Fedora
sudo curl https://rclone.org/install.sh | sudo bash
```

### Configure rclone
```bash
rclone config
```
Follow the interactive wizard:
1. Type `n` for New remote
2. Name: `cloudflare_r2`
3. Storage: Select `Amazon S3 Compliant` (option 4)
4. Provider: Select `Cloudflare` (option 6)
5. Enter your Access Key ID from Cloudflare dashboard
6. Enter your Secret Access Key from Cloudflare dashboard
7. Endpoint: `https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com`
8. Leave location and ACL blank (press Enter)

### Mount R2
```bash
cd ~/projects/mcp-platform-agno-mvp

rclone mount cloudflare_r2:YOUR_BUCKET_NAME ./data/r2_share \
  --vfs-cache-mode writes \
  --allow-other \
  --daemon
```

Now anything saved to `data/r2_share/` syncs to cloud, and both Agno and n8n can access it.

## Daily Operations

### Start Everything
```bash
cd ~/projects/mcp-platform-agno-mvp
docker compose up -d
```

### Stop Everything
```bash
cd ~/projects/mcp-platform-agno-mvp
docker compose down
```

### View Logs
```bash
# All services
docker compose logs

# Just the Agno control layer
docker compose logs -f agentos

# Just the database
docker compose logs -f postgres

# Just n8n
docker compose logs -f n8n
```

### Update After Code Changes
```bash
cd ~/projects/mcp-platform-agno-mvp
# Pull latest code
git pull
# Restart
docker compose down
docker compose up -d --build
```

### Backup Data
```bash
cd ~/projects/mcp-platform-agno-mvp

# Backup PostgreSQL
docker compose exec postgres pg_dump -U postgres agno_platform > backup_$(date +%Y%m%d).sql

# Backup DuckDB (forensic vault)
cp MCP_PLATFORM/mcp-servers/ts-mcp-server/data/vault.duckdb backup_vault_$(date +%Y%m%d).duckdb

# Backup knowledge
tar czf backup_knowledge_$(date +%Y%m%d).tar.gz knowledge/
```

### Reset Everything (Careful!)
```bash
cd ~/projects/mcp-platform-agno-mvp

# Stop everything
docker compose down

# Delete all data (irreversible!)
sudo rm -rf data/postgres_data/*
sudo rm -rf data/n8n_data/*

# Restart (database will re-initialize from schema.sql)
docker compose up -d
```

## Troubleshooting

### "docker: permission denied"
```bash
sudo usermod -aG docker $USER
# Then log out and log back in completely
```

### "port already in use"
Something else is using the port. Check:
```bash
# Find what's using port 8000
sudo lsof -i :8000

# If it's another Docker container, stop it first
docker stop CONTAINER_NAME
```

### "health check failed" or agents not ready
```bash
# Check detailed logs
docker compose logs agentos | tail -50

# Most likely cause: MCP servers not starting
# Check if they have the right file paths in .env
docker compose logs ts-mcp-server | tail -20
docker compose logs py-mcp-server | tail -20
```

### "API key required" errors
You set `API_KEY` in `.env` but forgot to include it in your curl commands:
```bash
# Add this header to all requests
curl -H "X-API-Key: your-key" http://localhost:8000/...
```

### Database connection errors
```bash
# Check if postgres is running
docker compose ps postgres

# Check postgres logs
docker compose logs postgres | tail -20

# Verify the DATABASE_URL in .env matches the docker-compose config
# The hostname should be "postgres" not "localhost" when running in Docker
```

### MCP servers not connecting
The MCP servers need to be built first:
```bash
cd ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server
npm install
npm run build

cd ~/projects/MCP_PLATFORM/mcp-servers/py-mcp-server
pip install -r requirements.txt
```

## Security Notes

1. **Never commit `.env` to Git** — it contains API keys and passwords
2. **Keep your OpenAI API key private** — anyone with it can use your credits
3. **The API key you set** — use a strong password, especially if exposing to the internet
4. **Court evidence** — stays local by default. Cloud storage (R2) is optional and should only be used for non-sensitive data
5. **Docker containers run isolated** — they can't access your home directory unless you explicitly mount it

## What's Next After Deployment

1. **Read the prompt context** — `cat prompts/platform_context/04_open_questions.md` — answer the 8 open questions
2. **Activate the Facebook parser** — Ask the dev_copilot agent to start Task P0-1
3. **Upload evidence** — Put files in `knowledge/platform/conversations/` and run the mining script
4. **Build n8n workflows** — Open http://localhost:5678 and create your first automation

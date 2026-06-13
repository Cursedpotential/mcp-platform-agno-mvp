# skilz-cli: Universal AI Skill Package Manager

## Overview

`skilz` is a universal package manager for AI agent skills. It enables installation, discovery, and management of reusable AI skills across 30+ agent platforms (Claude, Gemini, Cursor, Windsurf, Codex, etc.).

**Installation**: Pre-installed at `C:\Users\matts\AppData\Local\Programs\Python\Python313\Scripts\skilz.exe`

**Usage**: Run `skilz` command from terminal

## Core Commands

### Installation

```bash
skilz install <skill-id>                    # From marketplace
skilz install -g <github-url>               # From GitHub
skilz install -g <url> --all                # All skills from repo
skilz install -g <url> --skill NAME         # Specific skill from multi-skill repo
skilz install -f <local-path>               # From local filesystem
skilz install <id> --agent claude           # Target specific agent
skilz install <id> -p                       # Project-level install
skilz install <id> --version VERSION        # Pin to specific version/SHA/branch
```

### Discovery & Search

```bash
skilz list                                  # List user-level skills
skilz list --all                            # List from all agents
skilz list --agent claude                   # Filter by agent
skilz list --json                           # JSON output
skilz list -p                               # Project-level only
skilz search <query>                        # Search GitHub for skills
skilz search <query> --limit N              # Limit results
skilz search <query> --json                 # JSON output
```

### Management

```bash
skilz update                                # Update all skills
skilz update <skill-id>                     # Update specific skill
skilz update --dry-run                      # Preview changes
skilz uninstall <skill-id>                  # Remove with confirmation
skilz uninstall <skill-id> -y               # Skip confirmation
skilz rm <skill-id>                         # Alias for uninstall
skilz read <skill-name>                     # Read SKILL.md for AI consumption
skilz read <skill-name> --agent claude      # Filter by agent
skilz visit <skill-id>                      # Open in browser
skilz config                                # Show configuration
skilz config --init                         # Initialize configuration
```

## Skill ID Formats

- **New format**: `owner/repo/skill-name`
- **Legacy format**: `owner_repo/skill-name`
- **Direct URLs**: Use `-g` flag with full GitHub URL

## Installation Scopes

- **User-level** (default): Stored in `~/.claude/skills/` and `~/.skilz/skills/`
- **Project-level** (`-p` flag): Stored in project `.claude/skills/` and `.skilz/skills/`

## Common Workflows

### Install a Single Skill from GitHub

```bash
skilz install -g https://github.com/owner/skill-repo --agent claude
```

### Install All Skills from a Repository

```bash
skilz install -g https://github.com/owner/multi-skill-repo --all --agent claude
```

### Batch Install Multiple Skills (Bash)

```bash
for repo in owner/repo1 owner/repo2 owner/repo3; do
  skilz install -g "https://github.com/$repo" --agent claude -y
done
```

### Batch Install Multiple Skills (Windows CMD)

```cmd
for %r in (owner/repo1 owner/repo2 owner/repo3) do skilz install -g "https://github.com/%r" --agent claude -y
```

### Search for Skills by Topic

```bash
skilz search "data analysis"
skilz search "code review" --limit 5
```

### List All Installed Skills

```bash
skilz list --all
skilz list --json  # For programmatic use
```

### Update All Skills

```bash
skilz update
skilz update --dry-run  # Preview first
```

### Remove a Skill

```bash
skilz uninstall my-skill-name
skilz uninstall my-skill-name -y  # Skip confirmation
```

### Read Skill Content (for AI)

```bash
skilz read my-skill-name  # Output SKILL.md content to stdout
```

## Integration with Claude Tools

### In Cowork (Desktop Commander)
Use `start_process("cmd /c skilz ...")` to execute skilz commands with proper shell handling.

### In Claude Desktop
Use built-in terminal with `skilz` command directly.

### In Claude Code (Terminal)
Execute `skilz` commands natively in terminal.

## Configuration

Configuration stored at `~/.config/skilz/settings.json`

Initialize or view:
```bash
skilz config --init  # First-time setup
skilz config         # Display current config
```

## Tips

- Use `-y` flag to skip confirmation prompts in automation
- Use `--json` output for programmatic parsing
- Pin specific versions with `--version` for reproducibility
- Use `--dry-run` before bulk updates to preview changes
- Project-level (`-p`) skills override user-level skills with same name

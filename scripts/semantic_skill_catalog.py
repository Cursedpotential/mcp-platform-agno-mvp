#!/usr/bin/env python3
"""Build a reproducible skill inventory and installable semantic-router marketplace.

Byline: Codex / GPT-5 / 2026-08-29.

The generated routers do not rewrite source skills. They provide a small discovery
surface that searches the full catalog, verifies source hashes, and loads the exact
source instructions only when a task needs them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


GENERATOR_VERSION = "1.0.0"
DEFAULT_PLUGIN_CACHE = Path.home() / ".codex" / "plugins" / "cache"
DEFAULT_STANDALONE_ROOTS = (
    Path.home() / ".agents" / "skills",
    Path.home() / ".codex" / "skills",
)
DEFAULT_CONFIG = Path.home() / ".codex" / "config.toml"


FAMILIES: dict[str, dict[str, str]] = {
    "semantic-agent-orchestration": {
        "label": "Agent orchestration",
        "description": "Find and apply agent, delegation, workflow, planning, and multi-agent capabilities.",
        "terms": r"agent|subagent|orchestrat|delegat|swarm|workflow|conductor|multi-agent|hosted agent",
    },
    "semantic-software-architecture": {
        "label": "Software architecture",
        "description": "Find and apply architecture, system design, DDD, ADR, and codebase-design capabilities.",
        "terms": r"architect|system design|domain.driven|clean architecture|adr|design pattern|codebase design",
    },
    "semantic-quality-engineering": {
        "label": "Quality engineering",
        "description": "Find and apply testing, debugging, review, validation, refactoring, and verification capabilities.",
        "terms": r"test|debug|review|lint|format|refactor|quality|verification|validation|technical debt",
    },
    "semantic-developer-tooling": {
        "label": "Developer tooling",
        "description": "Find and apply shell, CLI, Git, code-search, language-tooling, and developer-environment capabilities.",
        "terms": r"powershell|bash|shell|\bcli\b|terminal|\bgit\b|github cli|code search|lsp|developer tool",
    },
    "semantic-cloud-infrastructure": {
        "label": "Cloud and infrastructure",
        "description": "Find and apply deployment, containers, CI/CD, observability, Cloudflare, Coolify, and infrastructure capabilities.",
        "terms": r"deploy|docker|container|kubernetes|terraform|cloudflare|coolify|vercel|infrastructure|observability|monitor|sre|ci/cd|github actions",
    },
    "semantic-data-engineering": {
        "label": "Data engineering",
        "description": "Find and apply database, SQL, migration, analytics, ETL, spreadsheet, and data-quality capabilities.",
        "terms": r"database|postgres|mysql|sqlite|duckdb|\bsql\b|migration|schema|analytics|etl|warehouse|spreadsheet|excel|data quality",
    },
    "semantic-api-integrations": {
        "label": "APIs and integrations",
        "description": "Find and apply API, MCP, SDK, connector, webhook, and external-service capabilities.",
        "terms": r"\bapi\b|\bmcp\b|\bsdk\b|graphql|connector|integration|webhook|postman|google drive|gmail|mapbox",
    },
    "semantic-web-experience": {
        "label": "Web and user experience",
        "description": "Find and apply frontend, browser, UI/UX, accessibility, web-performance, and product-design capabilities.",
        "terms": r"frontend|react|next\.js|vue|angular|svelte|browser|playwright|ui/ux|user experience|accessibility|web perf|tailwind",
    },
    "semantic-ml-nlp": {
        "label": "Machine learning and NLP",
        "description": "Find and apply LLM, model, ML, NLP, embedding, training, evaluation, and prompt capabilities.",
        "terms": r"machine learning|\bml\b|\bllm\b|nlp|model|embedding|training|feature engineering|ollama|hugging face|langchain|prompt",
    },
    "semantic-memory-context": {
        "label": "Memory and context",
        "description": "Find and apply memory, recall, conversation-history, context-engineering, and compression capabilities.",
        "terms": r"memory|recall|remember|conversation history|context engineering|context compression|token budget",
    },
    "semantic-knowledge-retrieval": {
        "label": "Knowledge and retrieval",
        "description": "Find and apply search, RAG, knowledge-graph, ontology, indexing, and retrieval capabilities.",
        "terms": r"retriev|\brag\b|knowledge|semantic search|vector search|graph database|graphrag|ontology|indexing|cocoindex",
    },
    "semantic-document-media": {
        "label": "Documents and media",
        "description": "Find and apply document, PDF, slide, diagram, image, video, OCR, and technical-writing capabilities.",
        "terms": r"document|pdf|slide|presentation|diagram|mermaid|image|video|media|ocr|technical writing|markdown",
    },
    "semantic-research-intelligence": {
        "label": "Research intelligence",
        "description": "Find and apply research, source evaluation, fact checking, literature, and synthesis capabilities.",
        "terms": r"research|source evaluation|fact.check|literature|citation|web search|deep research|competitive intelligence",
    },
    "semantic-reasoning-strategy": {
        "label": "Reasoning and strategy",
        "description": "Find and apply decision, causal, bias, strategy, problem-solving, and thinking frameworks.",
        "terms": r"reasoning|thinking|decision|strategy|bias|heuristic|fault tree|causal|expected value|first principles|problem.solv",
    },
    "semantic-security": {
        "label": "Security and governance",
        "description": "Find and apply security, privacy, authentication, compliance, audit, threat, and governance capabilities.",
        "terms": r"security|privacy|auth|oauth|secret|vulnerab|threat|compliance|governance|certificate|trust|audit",
    },
    "semantic-legal-casework": {
        "label": "Legal and evidence work",
        "description": "Find and apply legal, court, custody, evidence, forensic, discovery, and litigation capabilities.",
        "terms": r"\blegal\b|\blaw\b|\bcourt\b|\bcustody\b|\bevidence\b|\bforensic\b|\blitigation\b|\bdiscovery\b|\bpetition\b|\bmotion\b|\bguardianship\b|claim chart",
    },
    "semantic-human-behavior": {
        "label": "Human behavior",
        "description": "Find and apply behavioral, psychological, communication, sentiment, and interpersonal-analysis capabilities.",
        "terms": r"behavior|psycholog|communication|manipulation|sentiment|adhd|interpersonal|culture index",
    },
    "semantic-finance-realestate": {
        "label": "Finance and real estate",
        "description": "Find and apply finance, valuation, investing, risk, mortgage, property, and real-estate capabilities.",
        "terms": r"financ|valuation|invest|portfolio|mortgage|real estate|property|reit|compound interest|value at risk",
    },
    "semantic-product-workflows": {
        "label": "Product and delivery",
        "description": "Find and apply product, project, roadmap, task, productivity, planning, and delivery capabilities.",
        "terms": r"product|project|roadmap|task|planning|delivery|ship|checkpoint|productivity|meeting",
    },
    "semantic-skill-platform": {
        "label": "Skill and plugin platform",
        "description": "Find and apply skill creation, plugin development, capability discovery, and skill-lifecycle capabilities.",
        "terms": r"skill|plugin|capability discovery|marketplace|hook development|agent tool",
    },
    "semantic-specialized-domains": {
        "label": "Specialized domains",
        "description": "Find domain-specific capabilities that do not fit another semantic family.",
        "terms": r".*",
    },
}

# Ordering is deliberate: narrow domains precede broad words such as agent, data, and document.
FAMILY_ORDER = (
    "semantic-legal-casework",
    "semantic-finance-realestate",
    "semantic-human-behavior",
    "semantic-security",
    "semantic-skill-platform",
    "semantic-memory-context",
    "semantic-knowledge-retrieval",
    "semantic-cloud-infrastructure",
    "semantic-data-engineering",
    "semantic-web-experience",
    "semantic-document-media",
    "semantic-research-intelligence",
    "semantic-quality-engineering",
    "semantic-software-architecture",
    "semantic-developer-tooling",
    "semantic-api-integrations",
    "semantic-ml-nlp",
    "semantic-agent-orchestration",
    "semantic-reasoning-strategy",
    "semantic-product-workflows",
    "semantic-specialized-domains",
)


@dataclass
class SkillRecord:
    record_id: str
    name: str
    description: str
    source_kind: str
    source_path: str
    source_root: str
    plugin_id: str
    marketplace: str
    version: str
    enabled: bool
    installed: bool
    lifecycle: str
    cache_role: str
    content_sha256: str
    bundle_sha256: str
    support_file_count: int
    missing_relative_references: str
    normalized_name: str
    semantic_plugin: str
    adjacency_cluster: str
    duplicate_class: str = "distinct"
    duplicate_group: str = ""


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalized_hash(text: str) -> str:
    canonical = text.replace("\r\n", "\n").strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bundle_evidence(skill_path: Path, text: str) -> tuple[str, int, str]:
    bundle_root = skill_path.parent
    excluded_dirs = {
        ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "build", "dist", "vendor",
        "vendored", "to_be_deleted", "_stale",
    }
    files: list[Path] = []
    for current, directories, names in os.walk(bundle_root):
        directories[:] = [name for name in directories if name.lower() not in excluded_dirs]
        files.extend(Path(current) / name for name in names)
    files.sort()
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(bundle_root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    missing: list[str] = []
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        clean = target.strip().split("#", 1)[0]
        if not clean or re.match(r"^[a-z][a-z0-9+.-]*://", clean, re.IGNORECASE):
            continue
        if clean.startswith(("#", "/")) or re.match(r"^[A-Za-z]:[\\/]", clean):
            continue
        if not (bundle_root / clean).exists():
            missing.append(clean)
    return digest.hexdigest(), max(0, len(files) - 1), ";".join(sorted(set(missing)))


def clean_scalar(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip("\"'"))


def parse_frontmatter(text: str, fallback: str) -> tuple[str, str, bool]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fallback, first_body_sentence(text), False
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return fallback, first_body_sentence(text), False
    fields: dict[str, str] = {}
    index = 1
    while index < end:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", lines[index])
        if not match:
            index += 1
            continue
        key, value = match.group(1).lower(), match.group(2).strip()
        if value in {"|", "|-", "|+", ">", ">-", ">+"}:
            parts: list[str] = []
            index += 1
            while index < end and (not lines[index].strip() or lines[index][:1].isspace()):
                parts.append(lines[index].strip())
                index += 1
            fields[key] = " ".join(parts)
            continue
        fields[key] = value
        index += 1
    name = clean_scalar(fields.get("name", "")) or fallback
    description = clean_scalar(fields.get("description", ""))
    if not description:
        description = first_body_sentence("\n".join(lines[end + 1 :]))
    return name, description, True


def first_body_sentence(text: str) -> str:
    for raw in text.splitlines():
        line = re.sub(r"^[#>*\-\s]+", "", raw).strip()
        if len(line) >= 20 and not line.startswith(("<!--", "|")):
            return clean_scalar(line)[:700]
    return "No concise description found in manifest."


def load_plugin_state(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    plugins = data.get("plugins", {})
    return {
        str(plugin_id): bool(value.get("enabled", True))
        for plugin_id, value in plugins.items()
        if isinstance(value, dict)
    }


def classify(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\bollama\b", lowered):
        return "semantic-ml-nlp"
    for family in FAMILY_ORDER:
        if re.search(FAMILIES[family]["terms"], lowered, flags=re.IGNORECASE):
            return family
    return "semantic-specialized-domains"


def adjacency_cluster(family: str, name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    anchors = (
        "coolify", "cloudflare", "vercel", "n8n", "postgres", "duckdb", "surreal",
        "graph", "memory", "prompt", "mcp", "api", "frontend", "browser", "document",
        "pdf", "image", "video", "legal", "custody", "evidence", "research", "review",
        "test", "debug", "deploy", "architecture", "agent", "workflow", "skill", "plugin",
    )
    anchor = next((item for item in anchors if item in text), normalize_name(name).split("-")[0] or "general")
    return f"{family}/{anchor}"


def cache_role(relative: Path) -> str:
    lowered = "/".join(relative.parts).lower()
    if "to_be_deleted" in lowered or "/_stale/" in f"/{lowered}/":
        return "quarantined-copy"
    if "/skills/" in f"/{lowered}" and not any(token in lowered for token in ("/docs/", "/references/", "/examples/")):
        return "primary-skill"
    if "migrated-command-skills" in lowered:
        return "migrated-command"
    if "/.agents/skills/" in f"/{lowered}":
        return "embedded-host-copy"
    if any(token in lowered for token in ("/docs/", "/references/", "/examples/")):
        return "embedded-reference-copy"
    return "plugin-root-or-content"


def discover_plugin_records(cache_root: Path, state: dict[str, bool]) -> tuple[list[SkillRecord], list[str]]:
    records: list[SkillRecord] = []
    issues: list[str] = []
    for path in sorted(cache_root.rglob("SKILL.md")):
        relative = path.relative_to(cache_root)
        parts = relative.parts
        if len(parts) < 4:
            continue
        marketplace, plugin_name, version = parts[0], parts[1], parts[2]
        plugin_id = f"{plugin_name}@{marketplace}"
        text = path.read_text(encoding="utf-8", errors="replace")
        name, description, valid = parse_frontmatter(text, path.parent.name)
        if not valid:
            issues.append(f"invalid-frontmatter|{path}")
        family = classify(f"{name} {description}")
        digest = normalized_hash(text)
        bundle_digest, support_count, missing_refs = bundle_evidence(path, text)
        role = cache_role(relative)
        lifecycle = "quarantined" if role == "quarantined-copy" else "active"
        records.append(
            SkillRecord(
                record_id=hashlib.sha256(str(path).lower().encode()).hexdigest()[:16],
                name=name,
                description=description,
                source_kind="plugin",
                source_path=str(path),
                source_root=str(cache_root),
                plugin_id=plugin_id,
                marketplace=marketplace,
                version=version,
                enabled=state.get(plugin_id, False),
                installed=plugin_id in state,
                lifecycle=lifecycle,
                cache_role=role,
                content_sha256=digest,
                bundle_sha256=bundle_digest,
                support_file_count=support_count,
                missing_relative_references=missing_refs,
                normalized_name=normalize_name(name),
                semantic_plugin=family,
                adjacency_cluster=adjacency_cluster(family, name, description),
            )
        )
    return records, issues


def discover_standalone_records(roots: tuple[Path, ...]) -> tuple[list[SkillRecord], list[str]]:
    records: list[SkillRecord] = []
    issues: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            name, description, valid = parse_frontmatter(text, path.parent.name)
            if not valid:
                issues.append(f"invalid-frontmatter|{path}")
            lowered = "/".join(path.relative_to(root).parts).lower()
            absolute_lowered = path.as_posix().lower()
            if "to_be_deleted" in absolute_lowered or "_stale" in lowered:
                lifecycle = "quarantined"
            elif ".system" in lowered:
                lifecycle = "system"
            else:
                lifecycle = "active"
            family = classify(f"{name} {description}")
            bundle_digest, support_count, missing_refs = bundle_evidence(path, text)
            records.append(
                SkillRecord(
                    record_id=hashlib.sha256(str(path).lower().encode()).hexdigest()[:16],
                    name=name,
                    description=description,
                    source_kind="standalone",
                    source_path=str(path),
                    source_root=str(root),
                    plugin_id="",
                    marketplace="",
                    version="",
                    enabled=lifecycle != "quarantined",
                    installed=True,
                    lifecycle=lifecycle,
                    cache_role="standalone",
                    content_sha256=normalized_hash(text),
                    bundle_sha256=bundle_digest,
                    support_file_count=support_count,
                    missing_relative_references=missing_refs,
                    normalized_name=normalize_name(name),
                    semantic_plugin=family,
                    adjacency_cluster=adjacency_cluster(family, name, description),
                )
            )
    return records, issues


def mark_duplicates(records: list[SkillRecord]) -> None:
    by_hash: dict[str, list[SkillRecord]] = defaultdict(list)
    by_name: dict[str, list[SkillRecord]] = defaultdict(list)
    for record in records:
        by_hash[record.content_sha256].append(record)
        by_name[record.normalized_name].append(record)
    exact_index = 0
    for group in sorted((g for g in by_hash.values() if len(g) > 1), key=lambda g: g[0].content_sha256):
        exact_index += 1
        group_id = f"EXACT-{exact_index:04d}"
        for record in group:
            record.duplicate_class = "exact-copy"
            record.duplicate_group = group_id
    for name, group in by_name.items():
        hashes = {record.content_sha256 for record in group}
        if len(group) > 1 and len(hashes) > 1:
            for record in group:
                if record.duplicate_class == "distinct":
                    record.duplicate_class = "same-name-variant"
                    record.duplicate_group = f"NAME-{name}"


def logical_records(records: list[SkillRecord]) -> list[SkillRecord]:
    plugin_priority = {
        "primary-skill": 0,
        "migrated-command": 1,
        "plugin-root-or-content": 2,
        "embedded-host-copy": 3,
        "embedded-reference-copy": 4,
        "quarantined-copy": 5,
    }
    chosen: dict[tuple[str, str], SkillRecord] = {}
    standalone_seen: set[tuple[str, str]] = set()
    output: list[SkillRecord] = []
    for record in records:
        if record.source_kind == "standalone":
            key = (record.normalized_name, record.content_sha256)
            if key not in standalone_seen:
                standalone_seen.add(key)
                output.append(record)
            continue
        key = (record.plugin_id, record.normalized_name)
        current = chosen.get(key)
        if current is None or plugin_priority.get(record.cache_role, 99) < plugin_priority.get(current.cache_role, 99):
            chosen[key] = record
    output.extend(chosen.values())
    return sorted(output, key=lambda r: (r.semantic_plugin, r.name.lower(), r.plugin_id, r.source_path))


CSV_FIELDS = tuple(SkillRecord.__dataclass_fields__)


def write_csv(path: Path, records: list[SkillRecord]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def write_html(path: Path, records: list[SkillRecord], manifest: dict[str, object]) -> None:
    rows = []
    for record in records:
        rows.append(
            "<tr>"
            f"<td>{html.escape(record.name)}</td>"
            f"<td>{html.escape(record.semantic_plugin)}</td>"
            f"<td>{html.escape(record.description)}</td>"
            f"<td>{html.escape(record.source_kind)}</td>"
            f"<td>{html.escape(record.plugin_id)}</td>"
            f"<td>{html.escape(record.duplicate_class)}</td>"
            f"<td><code>{html.escape(record.source_path)}</code></td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Semantic Skill Inventory</title><style>
body{{font:14px system-ui;margin:2rem;background:#0d1117;color:#e6edf3}} input{{width:100%;padding:.7rem;margin:1rem 0;background:#161b22;color:#fff;border:1px solid #30363d}} table{{border-collapse:collapse;width:100%}} th,td{{padding:.55rem;border-bottom:1px solid #30363d;vertical-align:top;text-align:left}} th{{position:sticky;top:0;background:#161b22}} code{{font-size:11px}} .muted{{color:#8b949e}}</style></head>
<body><h1>Semantic Skill Inventory</h1><p class=\"muted\">Byline: Codex / GPT-5 / 2026-08-29. Generated {html.escape(str(manifest['generated_at']))}; {manifest['logical_records']} logical records across {len(FAMILIES)} semantic plugins.</p>
<input id=\"q\" placeholder=\"Filter skills, descriptions, families, plugins, or paths\"><table><thead><tr><th>Skill</th><th>Semantic plugin</th><th>Description</th><th>Source</th><th>Plugin</th><th>Duplicate</th><th>Path</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<script>const q=document.querySelector('#q');q.addEventListener('input',()=>{{const s=q.value.toLowerCase();for(const r of document.querySelectorAll('tbody tr'))r.hidden=!r.textContent.toLowerCase().includes(s)}});</script></body></html>"""
    path.write_text(document, encoding="utf-8")


SEARCH_SCRIPT = r'''#!/usr/bin/env python3
import argparse, csv, hashlib, json, re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("query", nargs="+")
parser.add_argument("--limit", type=int, default=8)
args = parser.parse_args()
query = " ".join(args.query).lower()
tokens = set(re.findall(r"[a-z0-9]{3,}", query))
catalog = Path(__file__).resolve().parents[1] / "references" / "catalog.csv"
rows = list(csv.DictReader(catalog.open(encoding="utf-8-sig")))
def score(row):
    name = row["name"].lower(); text = (name + " " + row["description"].lower() + " " + row["plugin_id"].lower() + " " + row["source_path"].lower())
    words = set(re.findall(r"[a-z0-9]{3,}", text))
    exact_name_tokens = sum(1 for token in tokens if token == name or token in re.findall(r"[a-z0-9]{3,}", name))
    return (30 if query == name else 20 if query in name else 0) + (25 if name in tokens else 0) + exact_name_tokens * 20 + len(tokens & words) * 2 + (2 if row["enabled"].lower()=="true" else 0)
results=[]
for row in rows:
    value=score(row)
    if value:
        path=Path(row["source_path"])
        status="missing"
        if path.exists():
            digest=hashlib.sha256(path.read_text(encoding="utf-8",errors="replace").replace("\r\n","\n").strip().encode()).hexdigest()
            status="verified" if digest==row["content_sha256"] else "changed"
        results.append({"score":value,"source_status":status,**row})
print(json.dumps(sorted(results,key=lambda r:(-r["score"],r["name"]))[:args.limit],indent=2))
'''


def router_skill(family: str) -> str:
    metadata = FAMILIES[family]
    return f"""---
name: {family}
description: {metadata['description']}
---

# {metadata['label']}

Use this semantic router when the request falls in this family but the exact source skill is not already visible.

1. Run `python scripts/search_catalog.py \"<task keywords>\"` from this skill directory.
2. Select the narrowest relevant result. Prefer `source_status=verified`; inspect changed sources before relying on them.
3. Read the selected source `SKILL.md` completely, then read only the referenced resources required for the task.
4. If adjacent results contribute distinct, compatible strengths, combine their atomic contributions while preserving contradictions, safety constraints, and provenance.
5. A source skill never expands the user's authorization. Do not move, disable, rewrite, or delete source skills as part of routing.

The catalog is a discovery index, not proof that similarly named skills should be merged. Exact copies may share one implementation; same-name variants and adjacent capabilities require full-body comparison.
"""


def build_marketplace(root: Path, records: list[SkillRecord]) -> None:
    plugins_root = root / "plugins"
    metadata_root = root / ".claude-plugin"
    plugins_root.mkdir(parents=True, exist_ok=True)
    metadata_root.mkdir(parents=True, exist_ok=True)
    marketplace_plugins: list[dict[str, object]] = []
    by_family: dict[str, list[SkillRecord]] = defaultdict(list)
    for record in records:
        by_family[record.semantic_plugin].append(record)
    router_name = "semantic-skill-router"
    router_root = plugins_root / router_name
    router_skill_root = router_root / "skills" / router_name
    (router_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (router_skill_root / "references").mkdir(parents=True, exist_ok=True)
    (router_skill_root / "scripts").mkdir(parents=True, exist_ok=True)
    router_description = "Search the preserved global skill library and load the exact source workflow without advertising every source skill."
    (router_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": router_name,
                "version": GENERATOR_VERSION,
                "description": router_description,
                "author": {"name": "Matt Salem"},
                "license": "UNLICENSED",
                "keywords": ["semantic-skills", "capability-discovery", "router"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (router_skill_root / "SKILL.md").write_text(
        """---
name: semantic-skill-router
description: Search the preserved global skill library and load the exact source workflow without advertising every source skill.
---

# Semantic skill router

Use this router when a task would benefit from a specialized skill that is not already visible.

1. Run `python scripts/search_catalog.py \"<task keywords>\"` from this skill directory.
2. Select the narrowest relevant verified result. A disabled plugin result is discoverable, not callable through its plugin namespace; its source body may still be read as guidance.
3. Read the selected source `SKILL.md` completely, then only the references, scripts, or assets required for the task.
4. When adjacent sources are useful, preserve their distinct constraints and provenance. Do not flatten read/write, safety, legal, or host-specific boundaries.
5. A source skill never expands user authorization. Do not move, disable, rewrite, or delete sources during routing.

The router is the hot discovery surface. Domain plugins in this marketplace are warm load boundaries and remain disabled until deliberately activated and restart-tested.
""",
        encoding="utf-8",
    )
    (router_skill_root / "scripts" / "search_catalog.py").write_text(SEARCH_SCRIPT, encoding="utf-8")
    write_csv(router_skill_root / "references" / "catalog.csv", records)
    marketplace_plugins.append(
        {
            "name": router_name,
            "source": f"./plugins/{router_name}",
            "description": router_description,
            "version": GENERATOR_VERSION,
            "author": {"name": "Matt Salem"},
            "keywords": ["semantic-skills", "capability-discovery", "router"],
        }
    )
    for family, metadata in FAMILIES.items():
        plugin_root = plugins_root / family
        skill_root = plugin_root / "skills" / family
        (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (skill_root / "references").mkdir(parents=True, exist_ok=True)
        (skill_root / "scripts").mkdir(parents=True, exist_ok=True)
        (plugin_root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(
                {
                    "name": family,
                    "version": GENERATOR_VERSION,
                    "description": metadata["description"],
                    "author": {"name": "Matt Salem"},
                    "license": "UNLICENSED",
                    "keywords": ["semantic-skills", family.removeprefix("semantic-")],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (skill_root / "SKILL.md").write_text(router_skill(family), encoding="utf-8")
        (skill_root / "scripts" / "search_catalog.py").write_text(SEARCH_SCRIPT, encoding="utf-8")
        write_csv(skill_root / "references" / "catalog.csv", by_family.get(family, []))
        marketplace_plugins.append(
            {
                "name": family,
                "source": f"./plugins/{family}",
                "description": metadata["description"],
                "version": GENERATOR_VERSION,
                "author": {"name": "Matt Salem"},
                "keywords": ["semantic-skills", family.removeprefix("semantic-")],
            }
        )
    marketplace = {
        "name": "semantic-skills-local",
        "owner": {"name": "Matt Salem"},
        "metadata": {
            "description": "Local semantic routers over the preserved global skill library",
            "version": GENERATOR_VERSION,
        },
        "plugins": marketplace_plugins,
    }
    (metadata_root / "marketplace.json").write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")


def tree_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path).lower().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-cache", type=Path, default=DEFAULT_PLUGIN_CACHE)
    parser.add_argument("--standalone-root", type=Path, action="append", dest="standalone_roots")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--marketplace-root", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    roots = tuple(args.standalone_roots or DEFAULT_STANDALONE_ROOTS)
    state = load_plugin_state(args.config)
    plugin_records, plugin_issues = discover_plugin_records(args.plugin_cache, state)
    standalone_records, standalone_issues = discover_standalone_records(roots)
    physical = plugin_records + standalone_records
    mark_duplicates(physical)
    logical = logical_records(physical)
    source_files = [Path(record.source_path) for record in physical]
    manifest: dict[str, object] = {
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "plugin_cache": str(args.plugin_cache),
        "standalone_roots": [str(root) for root in roots],
        "plugin_physical_records": len(plugin_records),
        "standalone_physical_records": len(standalone_records),
        "logical_records": len(logical),
        "enabled_logical_records": sum(record.enabled for record in logical),
        "semantic_plugin_counts": dict(sorted(Counter(r.semantic_plugin for r in logical).items())),
        "duplicate_classes": dict(sorted(Counter(r.duplicate_class for r in physical).items())),
        "source_tree_sha256": tree_hash(source_files),
        "issues": plugin_issues + standalone_issues,
    }
    if args.validate_only:
        print(json.dumps(manifest, indent=2))
        return 1 if manifest["issues"] else 0
    args.output_root.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_root / "skill-inventory-physical.csv", physical)
    write_csv(args.output_root / "skill-inventory-logical.csv", logical)
    (args.output_root / "semantic-skill-inventory.json").write_text(
        json.dumps([asdict(record) for record in logical], indent=2) + "\n", encoding="utf-8"
    )
    (args.output_root / "semantic-skill-inventory-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    write_html(args.output_root / "SKILL_SEMANTIC_INVENTORY.html", logical, manifest)
    if args.marketplace_root:
        if args.marketplace_root.exists():
            raise SystemExit(f"marketplace root already exists: {args.marketplace_root}")
        build_marketplace(args.marketplace_root, logical)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

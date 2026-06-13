# Cognitive Synthesis System — Design Document (Revised v4)

**Date:** 2026-03-14
**Status:** REVISED v4 — Awaiting user review
**Author:** brainstorm@opencode
**Process:** Spec-Driven Development (see `docs/SPEC_DRIVEN_DEVELOPMENT.md`)

---

## Problem Statement

The user's cognitive process for forensic/narrative biographical writing involves 8 core domains, 10 frameworks, and 7 cognitive patterns. Goal: make it systematic, repeatable, tool-supported via skill/agent/prompt system **on top of existing dial-stack infrastructure**.

---

## Core Architectural Principles

### Bidirectional & Tool-Agnostic
**The platform is fully bidirectional. All data can flow any direction.**

### Multiple Frontends
- **DIAL Chat** (port 3000) — Dev/admin interface
- **External agents** — Any AI agent can call tools directly
- **Custom frontends** — React + CopilotKit, future UIs
- **CMS** — Content management system integration
- **CLI/Script** — Direct tool calls

### DIAL: Minimal, Flexible, Optional Orchestrator
- DIAL is a **minimal orchestrator** — just moves workflows along, assists making things work together
- DIAL can be **called as a tool** if the workflow needs it
- DIAL is **flexible and optional** — could use fully, could use minimally
- Tools work **with or without DIAL**

### Multi-Server Architecture (TS + JS + Python)
Tools are distributed across **all three MCP servers**, not just Python:
- **TS MCP Server** (port 8081) — Parsers, DuckDB, PostgreSQL, admin tools, voice fingerprinting
- **Py MCP Server** (port 8082) — Semantica, DPK transforms, behavioral detection, LanceDB, Neo4j
- **JS MCP Server** (port 8083) — Docling, Pandoc, custom logic, adapters
- All servers obscured through **MCP gateway/proxy** (single endpoint)
- Tools lazy loaded / dynamically loaded through gateway

### Everything is an Atomic Tool
- Every capability is exposed as an independent, callable tool
- **Workflows are also tools** — composite tools that orchestrate atomic tools
- Workflows get called just like atomic tools

### Implementation Pattern
```python
# Atomic tool — Py MCP Server
@mcp.tool()
def detect_hap(text: str) -> dict:
    """HAP scoring. Works standalone or via DIAL."""
    ...

# Atomic tool — TS MCP Server
@mcp.tool()
def fingerprint_voice(text: str) -> dict:
    """Voice fingerprinting. Works standalone or via DIAL."""
    ...

# Workflow tool — composite of atomic tools
@mcp.tool()
def analyze_evidence(text: str) -> dict:
    """Full evidence analysis workflow. Also a tool."""
    cleaned = dpk_pii_redact(text)           # Py MCP
    lang = dpk_lang_id(cleaned)              # Py MCP
    hap = detect_hap(cleaned)                # Py MCP
    behavioral = user_detection_system(cleaned)  # User's custom system
    audit_log(analysis_id, "evidence_analyzed")  # MANDATORY audit hook
    return {"cleaned": cleaned, "lang": lang, "hap": hap, "behavioral": behavioral}
```

---

## Mandatory: Autonomous Auditing & Forensic Handling

**This is the ONLY hard-coded autonomous requirement. Everything else is flexible.**

The following MUST happen automatically on the back end via hooks — no option, no bypass:

### Mandatory Autonomous Operations
1. **SHA-256 hashing** at first touch (before any transformation)
2. **UUIDv7 assignment** linked to hash
3. **Chain of custody logging** — every tool call, every transformation, every access
4. **Audit trail** — timestamped, immutable log of all operations
5. **WORM enforcement** — Pass 1 results are Write Once, Read Many

### Implementation: Hooks (Not Optional)
```python
# Audit hook — fires automatically on every tool call
@audit_hook("before")
def pre_audit(tool_name: str, input_data: dict) -> str:
    """Generate SHA-256, UUIDv7, log to audit trail. Returns audit_id."""
    sha256 = hash_sha256(input_data)
    uuid = generate_uuidv7()
    audit_id = log_audit(tool_name, sha256, uuid, timestamp=now())
    return audit_id

@audit_hook("after")
def post_audit(audit_id: str, output_data: dict):
    """Log completion, store result hash, update chain of custody."""
    result_hash = hash_sha256(output_data)
    update_audit(audit_id, result_hash, status="completed")
```

### Where Auditing Lives
- **DuckDB (Tier 1)** — Master clock, SHA-256 fingerprints, audit trail
- **Neo4j (Tier 3)** — PROV-O provenance chains
- **PostgreSQL (Tier 4)** — Unified evidence index with audit references

---

## Hardware Constraints

- **Local GPU:** Quadro M620 (2GB VRAM) — inference only, small models only
- **Training:** Google Colab Pro (available), cloud GPU rental (emergency only)
- **IBM Cloud:** Free tier for offloading heavier DPK workloads
- **Rule:** Local inference must fit in 2GB. Training can use Colab Pro.

---

## IBM Data Prep Kit (DPK) — Pre-Processing Layer

**Package:** `data-prep-toolkit-transforms` v1.1.7 (PyPI)
**GitHub:** https://github.com/IBM/data-prep-kit (910 stars, Apache-2.0)
**Role:** Pre-processing layer that feeds cleaned data into user's custom detection system

### Key Insight
DPK uses the **same libraries** we were going to use (spaCy, Flair, Transformers, NLTK). IBM Granite models are well-suited for abuse/toxicity detection.

### Relevant Transforms
| Transform | Model | Hardware | Use Case |
|-----------|-------|----------|----------|
| **HAP** | `ibm-granite/granite-guardian-hap-38m` | CPU, 6.16k tok/sec | Hate/Abuse/Profanity scoring |
| **PII Redactor** | Microsoft Presidio + Flair NER | CPU | Detect/redact PII entities |
| **Lang ID** | fasttext | CPU | Language identification |
| **Doc Quality** | Custom scoring | CPU | Document quality scoring |
| **Doc Chunk** | Configurable | CPU | Document chunking for RAG |
| **Readability** | Standard metrics | CPU | Readability scoring |

### Integration Pattern
```
Raw Evidence → DPK Pre-Processing → User's Custom Detection System → Dial-Stack Storage
                 │                        │
                 ├─ PII Redaction         ├─ Behavioral patterns
                 ├─ Language ID           ├─ DARVO detection
                 ├─ Doc Quality           ├─ Coercive control
                 ├─ HAP baseline scoring  ├─ MCL factor mapping
                 └─ Doc Chunking          └─ Custom scoring
```

**IMPORTANT:** User's custom detection system stays. DPK is upstream pre-processing only.

---

## Existing Ecosystem (Already Built)

### Existing Agents
`@forensic`, `@litigation`, `@michigan-law`, `@custody-support`, `@evidence-tech`

### Existing Skills
`manipulation-patterns/`, `mi-best-interest-factors/`, `mi-dv-resources/`, `evidence-templates/`, `documentation-methods/`

### Existing Infrastructure
MCL Factor Mapper, Semantica Pipeline (11 MCP tools), AI DIAL Core, WunderGraph Cosmo, 4-tier storage

**CRITICAL: Existing Behavioral Analysis Contains Case-Specific Ontology**
Voice patterns, vocabulary choices, topic patterns, behavioral signatures — use as training/seed material for the new application.

---

## Implementation Plan

### Sprint 1: DPK + Multi-Server Tools (Week 1-2)

1. **Install DPK transforms** in py-mcp-server: `pip install data-prep-toolkit-transforms[language]`

2. **Create tools across all 3 MCP servers:**

   **Py MCP Server (port 8082):**
   - `dpk_hap_score`, `dpk_pii_redact`, `dpk_lang_id`, `dpk_doc_quality`, `dpk_doc_chunk`, `dpk_readability`
   - Connect to user's custom detection system

   **TS MCP Server (port 8081):**
   - `fingerprint_voice` — faststylometry Burrows' Delta
   - `format_detector` — Confidence-scored format detection
   - `audit_hook` — Mandatory SHA-256/UUIDv7/chain of custody

   **JS MCP Server (port 8083):**
   - `docling_convert`, `pandoc_convert`

3. **Create secondary Semantica database** for agent workspace
4. **Update DIAL config** — add applications for all servers
5. **Create skill documents** (Rule 5)
6. **Update TOOL_CATALOG.md**

### Sprint 2: Wire Existing Agents + Extract Ontology (Week 3-4)

1. **Add DIAL applications** for existing agents
2. **Extract behavioral analysis ontology** as training/seed material
3. **Test end-to-end** with existing evidence data

### Sprint 3: Enhancements (Week 5+)

1. **Fine-tune models on Colab Pro** using behavioral analysis ontology
2. **Investigate IBM Cloud free tier** for heavy workloads
3. **Add narrative construction tools**

---

## Tool Adoption Matrix

| Tool | Server | Category | Priority | Status |
|------|--------|----------|----------|--------|
| DPK HAP | Py MCP | Pre-processing | **CRITICAL** | Off-shelf |
| DPK PII Redactor | Py MCP | Pre-processing | **CRITICAL** | Off-shelf |
| DPK Lang ID | Py MCP | Pre-processing | HIGH | Off-shelf |
| DPK Doc Quality | Py MCP | Pre-processing | HIGH | Off-shelf |
| DPK Doc Chunk | Py MCP | Pre-processing | HIGH | Off-shelf |
| User's Custom Detection | Py MCP | Behavioral | **CRITICAL** | User's system |
| Behavioral Ontology | N/A | Training data | **CRITICAL** | Extract from existing |
| faststylometry | TS MCP | Voice | HIGH | Off-shelf |
| Audit Hooks | TS MCP | Forensic | **CRITICAL** | Mandatory |
| Semantica | Py MCP | NLP/Graph | **CRITICAL** | Already built |
| MCL Factor Mapper | Py MCP | Legal | **CRITICAL** | Already built |
| Docling | JS MCP | Document | HIGH | Already planned |

---

## Next Steps

1. **User review** of this revised plan
2. **Begin Sprint 1** — install DPK, create tools across all 3 servers, mandatory audit hooks
3. **Extract behavioral analysis ontology** from existing skills
4. **Create spec files** in `docs/specs/`


---

# Plan Feedback

I've reviewed this plan and have 1 piece of feedback:

## 1. General feedback about the plan
> So now that you understand that everything is an atomic tool and everything is not mono coded and hard coded in I want to draw some clear lines and distinctions on what I want you to work on because I've been iterating for months with another agent in another chat another parts of this thing the ingestion and parsing and stuff we'll either deal with that later I'll deal with that with the other agent including the the data merge tool or whatever we just looked at I want you to know that we have it so that you understand what you're going to be working with 'cause I want you working on the tools that come second You know in between semantica and ingestion going into duct DBI want you to work on all the tools that identify all of the processes you should be able to find that in the workflow already in the application but I want you to work on those tools those agents those things that's what the the your primary goal is Don't remove all of the notes that we've made but that's what this Sprint is about is the tools that identify the initial behaviors the the abuse of language all that kind of stuff tools that can be called during any analysis or at any time to assist in the analysis of conversations of chats of emails whatever it is whether it's the initial ingestion or if it's the looking back because we're going to do a later on like a full hindsight meta analysis of how things changed once you had all the information So this is these tools are gonna get used in multiple parts of the workflow So the stress here is not to slot everything into exactly where it goes just make sure that all of the tools are there and function and then we can play with it a bit because it's so flexible

---

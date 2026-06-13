# Plan: Development Bible & Agent Governance System (REVISED)

**Date:** 2026-03-16
**Status:** APPROVED WITH ANNOTATIONS — Incorporating feedback
**Author:** Claude Opus (claude.ai planning session)

---

## Annotations Incorporated

1. **IBM ContextForge** — Major architectural consideration. May replace/supplement DIAL for backend MCP gateway/proxy, API, RPC, auth, entity ID, abusive language detection. Evaluate integration with existing tools. DIAL may become frontend/auth only with IBM handling backend.
2. **Additional tools exist** — Utilities folder, legacy MCP_Tool_Platform, AI Workspace, Downloads all contain tools not yet cataloged.
3. **Client is custom** — Legacy directory has custom React code. Evaluating modular React frameworks for CopilotKit/DIAL integration. NOT a blank Vite template.
4. **Semantica is centerpiece** — Even if not MVP, it's next priority after pipeline glue. Must be very functional very soon.
5. **IBM handles MCP port security** — Relates to Remediation #1, may supersede.
6. **Rule 5 addition** — Split concerns across agents. Each agent stays in their lane.
7. **Minimal custom code** — Use viable open source when available.
8. **All 8 governance rules APPROVED**

---

## Governance Rules (APPROVED)

1. ASSUME YOU DON'T KNOW — Confirm everything
2. CONFIRM BEFORE CREATING — Plans via plannotator, quick clarifications via Ask User
3. DOCUMENT BEFORE IMPLEMENTING — Spec first, then code, then update docs
4. READ-ONLY LEGACY — MCP_Tool_Platform is archived
5. NO SILENT DECISIONS — All decisions to user. Split concerns, stay in lane.
6. HONEST STATUS — Never inflate. If you don't know, say so.
7. STAY IN YOUR LANE — Only work on active spec
8. NAME AWARENESS — Search TheBigOne, dial-stack, MCP Tool Platform, TraceIQ

---

## Next Steps (Moving Forward Now)

### Step 1: Fix Directory Structure Damage
Agent last night broke folder structure. Need to audit and fix.

### Step 2: Accuracy Pass on Existing Docs
- TOOL_CATALOG.md: Fix false "Built" claims (WhatsApp, etc.)
- ROADMAP.md: Honest percentages
- ARCHITECTURE.md: Mark aspirational vs built
- Add IBM ContextForge evaluation to architecture considerations

### Step 3: Create Governing Documents
- CONSTITUTION.md — Immutable forensic principles
- CLAUDE.md — Minimal, references subdocs, governance rules
- AGENTS.md — Cross-tool monorepo rules

### Step 4: MVP Pipeline Spec → Plannotator for approval

### Step 5: Implement MVP Pipeline (after spec approved)

### Step 6: Semantica priority work (after MVP proves data flows)

---

**This plan is now revised per annotations. Moving to execution.**

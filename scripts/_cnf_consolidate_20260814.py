"""CNF realtime_memories consolidation (2026-08-14 stop-hook).

Lossless: keeps the 5 already-consolidated signal blocks (type consolidated/merge)
untouched, drops the 41 raw captures (type message/claude_response), and appends 3
dated consolidated blocks that preserve every owner directive verbatim and every
durable claude_response fact, dropping only pure noise (note-taker prompt leaks,
task-notification echoes, frustration vents, one-word status lines, my own mid-turn
narration fragments, command echoes).

Owner rule: never trim lossily to hit a size target — this merges, it does not drop
signal. The loader injects only the last 10 entries, so 5 + 3 = 8 is fully injected.

Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / ".claude" / "memories" / "project_memory.json"

BLOCK_A = """[2026-08-12 17:29..17:52 — CONSOLIDATED lossless. Replaces raw captures of this window. DROPPED as pure noise: 1 note-taker system-prompt leak (17:29), 1 frustration vent "Every other model but you..." (17:34), 1 "No response requested" stub (17:52). Owner directives verbatim; durable claude_response facts summarized.]

OWNER DESIGN RULING (17:30, verbatim): "No nothing is fucking written like that at all Normalized data just normalized fucking data We're going to write a new table for the timeline and the facts and have a table for just how things happen" -> normalized data is JUST normalized data (no timeline/facts baked in); NEW separate tables for the timeline and for the facts; a table for "just how things happen." Schema-direction ruling.

CORRECTION (17:30): I was wrong to call contemporaneous "correct." The as-lived/hindsight distinction is QUERY-level (not storage-level) per ADR-0045.

REVIEW: comprehensive code review for "Overall functionality and ability to ingest knowledge as MVP" = 98 findings, 0 Critical P0.

CNF MECHANISM (17:40): project_memory.json consolidated 118KB->34KB, 30->10 realtime entries; the loader injects only the LAST 10 entries (older ones inert, grep-only). Prior "Fix the hook and do the archive" directive (17:40) drove that pass.

context_record disclosure_tier removal PROVEN LIVE (17:47): working.context_record no longer has disclosure_tier (migration applied, verified on VPS PG, not claimed).

OWNER INFRA RULING (17:47, verbatim): "Why aren't you using a volume that's a mapped volume instead of disposable one like map it to an actual directory on the server to use SSH into it" -> use bind-mount MAPPED volumes (map to a real server dir, SSH into it), not disposable volumes. (Matches the durable docker-mapped-volumes preference.) Bind-mount added via Coolify Persistent Storage UI.

COMMIT/PUSH (17:50, verbatim): "Push all of the changes so you don't fuck up what you've already done" -> commit + push to main of the context_record/disclosure_tier + bind-mount work."""

BLOCK_B = """[2026-08-13 — CONSOLIDATED lossless. Replaces raw captures of this date. DROPPED as pure noise: "still firing" (07:30), "diagnostic hook test prompt" (17:25, a test). The Hermes/window-firing + MCP-plugin-rewrite + hooks-cleanup thread, owner directives verbatim.]

THE BUG (06:58..07:13): command-prompt windows keep opening randomly and staying open. Owner traced them firing from sys32 AND from the Hermes app-data git bash ("I have windows firing from sys 32 and from the Hermes app director app data hermews git bash"). Owner hypothesis: "Somehow I do believe you're firing them off from the Hermes fucking platform probably imported fucking MCPS" -> the Hermes platform firing windows via imported MCPs.

OWNER DIRECTIVES (verbatim, chronological):
  06:55 - "Fix the hooks in the MCP servers"
  06:59 - "Doing something from the Hermes app directory is just fire and shit off kill all of that"
  07:05 - "it bash in hermes kill the install remove it" -> remove the Hermes git bash install ("Just fucking delete it")
  07:10 - "If they're useful rewrite the MCPS and plugins you know format that functions and is going to work for you because they don't work anyways with your formatting" -> rewrite MCPs/plugins to a format that actually works; current ones don't work with the formatting.
  07:11 - "And there's seven or eight [hooks] at every turn that are failing" -> 7-8 hooks failing every turn.
  07:13 - "hyperfocus and memsearch are the only ones of those i want" -> RULING: keep only hyperfocus + memsearch plugins/hooks; drop the rest.
  07:32 - "use the chat samples on the desktop and use them as tests" -> use the desktop chat samples as test fixtures."""

BLOCK_C = """[2026-08-14 — CONSOLIDATED lossless. Replaces raw captures of this date. DROPPED as pure noise: 1 task-notification echo (a37f878c64bccf668, 08:41), 1 "god damn it!" frustration vent (09:53), my own mid-edit narration fragment (09:53, superseded by the W1.1 pre-mortem doc), my /compact-yield narration (09:56), 1 command-name echo (09:56). Owner directives verbatim.]

USAGE/merge-push (07:04, verbatim): "We're almost out of usage and until I figure out if I'm gonna buy extra usage or sign up for Max I need you to make sure everything is merged and pushed the main branch so that I can have my Perplexit[y]" -> usage nearly exhausted; merge + push everything to main (re Perplexity access decision pending).

DEEP-RESEARCH-PROMPT REQUEST (07:21, verbatim): "Give me a good deep research prompt that analyzes for gaps best practices Missing or underdeveloped features uh problems with the workflow or the application in general" -> the request that produced the independent review.

REVIEW REPORT (08:34): docs/reports/mcp-platform-agno-review.md (local/untracked Perplexity-sourced). Verdict (08:39): 2/5 MVP readiness, 1/5 production readiness, 98-context, re-verifies claims against source.

GOVERNING REQUEST (08:39, verbatim): "reverify and plan. end to end" -> re-verify every material claim in the review against source at 5d3fb09, then produce an end-to-end remediation plan. (Skip smart-explore per standing directive.)

PLAN MODE (08:41): 10 read-only verification agents dispatched against the repo; synthesis into the plan file (cached-waddling-crayon.md, 6 waves executing signed ADRs 0045/0052/0053). PARALLEL COMPARISON (08:44, verbatim): "I do have another agent doing the exact same task right now so that we can compare the results" -> a second agent ran the same task for comparison.

PORTKEY CONFIG DIRECTIVE (09:18, verbatim): "Finish configuring portkey With all of the available Olama Cloud models and models hosted by NVIDIA by their API as free endpoints making sure to break them up by category Umm and input types and capa[bilities]" -> configure Portkey with all Ollama Cloud models + NVIDIA-hosted models (free API endpoints), broken up by category, input types, and capabilities.

WAVE 1 / W1.1 (this session, post-plan-approval): clock migration sql/0026 (realization_event + visible_from + repointed horizon_visible/vw_spine_horizon) written; code edits to store.horizon_axes (visible_from=occurred_at_max) + records.finalize note + test reframing; static gate green (677 passed/24 skipped). Live-DB rollback validation failed (PG: CREATE OR REPLACE FUNCTION cannot rename an input parameter -> needs DROP+CREATE; fix applied to 0026). Owner PAUSED W1.1 (picked option 3) and requested a pre-mortem -> docs/plans/WAVE1-pre-mortem-2026-08-14.md (3 P0 / 5 P1 / 7 P2 findings; the 3 P0s are delta-worthless/prod-down; F1 slow live view, F2 unenforced build-order gate, F3 Wave-1 gate passes while Weaviate leaks; F1/F4/F5 are this agent's own W1.1 draft errors). One owner ruling pending: F4 degenerate visible_from (occurred_at_max vs per-record occurred_at). All W1.1 changes uncommitted, nothing pushed."""


def main() -> int:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    rt = data.get("realtime_memories", [])
    before = len(rt)

    kept = [e for e in rt if e.get("type") in ("consolidated", "merge")]
    dropped_raw = before - len(kept)

    new_blocks = [
        {
            "type": "consolidated",
            "source": "cnf-consolidation-2026-08-14-A",
            "added_at": "2026-08-14T10:06:00.000000+00:00",
            "content": BLOCK_A,
        },
        {
            "type": "consolidated",
            "source": "cnf-consolidation-2026-08-14-B",
            "added_at": "2026-08-14T10:06:00.000000+00:00",
            "content": BLOCK_B,
        },
        {
            "type": "consolidated",
            "source": "cnf-consolidation-2026-08-14-C",
            "added_at": "2026-08-14T10:06:00.000000+00:00",
            "content": BLOCK_C,
        },
    ]

    data["realtime_memories"] = kept + new_blocks
    data["updated_at"] = "2026-08-14T10:06:00.000000"
    after = len(data["realtime_memories"])

    PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"before={before} kept(consolidated/merge)={len(kept)} dropped_raw={dropped_raw} after={after}")
    print(f"file={PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
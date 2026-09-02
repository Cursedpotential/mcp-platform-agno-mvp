# OWNER-BACKBONE — PARTIAL RECOVERY

> _Recovery note: this file's creation (`Add File`) was never captured by any `apply_patch` call across every rollout in `C:\Users\matts\.codex\sessions\2026\08\{25,26,27,28}\` — the file already existed live by the time the earliest `Update File` hunk below was issued, so it was created through some other mechanism (a full-file write, or a session/date genuinely outside this recovery task's scope). **This is therefore a PARTIAL recovery: the document's base structure, headings, and any untouched passages could not be reconstructed.** What follows is every located, accepted `apply_patch` hunk that touched this file, in chronological order, shown as unified-diff-style fragments (`-` = text the fragment replaced, `+` = text it introduced, ` ` = unchanged context) — all verbatim from the session transcripts. Reconstructed 2026-09-02 by Claude Code · Sonnet (recovery lane C)._

Only one `apply_patch` call touching this file was located in the scanned window (2026-08-26T13:41:18Z, the same large multi-file consolidation call that also updated `UNIFIED-PHYSICAL-MODEL.md`, `CROSS-DOMAIN-CONTRACT-MATRIX.md`, and `PROVISIONAL-PHYSICAL-MODEL.md`). This is consistent with `AGENTS.md`'s own citation of this document's "governing rules" on realization events staying separate from facts and the knowledge-horizon mechanism — this file is the source-of-truth doc AGENTS.md quotes, but its base content predates this recovery's scan window entirely.

**1 accepted hunk(s) recovered, none of which is a file-creation event.**

---

### Fragment 1 — 2026-08-26T13:41:18.623Z (`Update File`, call `call_46Y6bNvia5i5ZbqFeKmnJxWS`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
-- AI-chat/context communication, never silently treated as evidence.
+- AI-chat/context communication, permanently barred from evidence promotion, anchors, citations, or
+  corroboration. It may produce typed investigation candidates and created works only.
@@
 But they are merely three typed source representations — not the architecture of the product. Sender, recipients, and participants remain verbatim on each record; address-book/entity links are additive resolution, never replacements.
+
+The chronology product is a maintained Timesketch fork. It may display context/candidate and
+evidence-approved timeline entries together only with unmistakable authority state. It is also a
+governed bulk-curation service: edits return to PostgreSQL as context commands. Every proposed change
+to an approved entry becomes a context amendment candidate for re-review/reconciliation; approved
+history is never edited in place.
```

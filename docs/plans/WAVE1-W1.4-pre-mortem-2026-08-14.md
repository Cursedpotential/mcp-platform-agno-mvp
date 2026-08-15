# WAVE 1.4 Pre-Mortem — DB Grants (Default-Deny Pass-Corpora Isolation, ADR-0045 §B / ADR-0052)

> **R0 AUDIT BANNER 2026-08-15:** the 18/18 rollback proof below does not make
> grants effective in the current superuser application path and does not make
> Wave 1 cutover-ready. Read `../HANDOFF-2026-08-15-R0-wave1-audit.md`.
> _Byline: Codex · GPT-5 · 2026-08-15._


> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Status: **BUILD COMPLETE — validated in rollback on live (18/18 PASS, incl. a real
> SET-ROLE enforcement proof); NOT applied to prod; NOT pushed.**
> Owner review surface: one of the per-task pre-mortems the owner asked for and will review together.

## The scenario

It is after the Wave 1 cutover. The default-deny grants shipped, the agents were bound
to their pass corpora, and **either a non-refresher wrote a pass checkpoint (forged
corpus_hash), or an agent read the canonical store directly (contamination), or the
grants were applied and nothing broke — but they were also doing nothing.** Explain why.

---

## What W1.4 actually built

- **`sql/0029_pass_grants.sql`** — the default-deny grant migration. Two NOLOGIN roles
  + schema USAGE + per-table grants, expressing the ADR-0045 §B sole-writer /
  ADR-0052 default-deny contract at the DB layer:
  - **`pass_refresher`** — sole writer of `working.walk_run/walk_step/walk_step_retrieval`
    + `record_visible_from`; SELECT on canonical (`normalized_record`,
    `realization_event*`) to compute `base_version`; INSERT on `ops.audit_ledger`
    (attestation); EXECUTE on `visible_from`/`horizon_visible`. No DELETE (append-only).
  - **`pass_reader`** — SELECT on the pass corpus only (`walk_run/walk_step/walk_step_retrieval`).
    NO grant on canonical base tables — agents read the DERIVED pass corpus, not the
    raw store (§B one-store-filtered-per-agent).
  - DEFAULT-DENY: `REVOKE ALL ... FROM PUBLIC` on the pass tables + `record_visible_from`.
  - APPLY ORDER: 0026 → 0027 → 0028 → **0029** (0029 grants on `record_visible_from`,
    which 0028 creates — a real apply-order dependency).
- **`scripts/_wave1_recon_w14_grants.py`** — the read-only recon that found the
  decisive fact (below). Zero write.
- **`scripts/_wave1_validate_w14_grants.py`** — live rollback validation, **18/18 PASS**,
  including a real **SET-ROLE enforcement proof**: it creates the roles + grants inside
  ONE rollback transaction, then `SET ROLE pass_reader` / `pass_refresher` and observes
  what each can/cannot do. proving the grants are real enforcement (not just structure).

## The decisive finding — the app connects as a SUPERUSER

The recon returned the one fact that re-frames the whole task:

```
current_user = ai   |   is_super = True   |   can_create_role = True
(only login role; owner of every working./ops. table; rolsuper=True)
```

**The `ai` role the agno app connects as is a SUPERUSER.** Superusers bypass **every**
grant and `BYPASSRLS`. So:

- The grants in 0029 are **the schema CONTRACT for the target isolation** — correct,
  validated, real enforcement *for a non-superuser role* (proven via SET ROLE).
- But they are **INERT for the app's current superuser connection.** A refresher, an
  agent, a script, a direct `INSERT` — all run as `ai`, which ignores all grants. The
  F13 app-side advisory lock remains the only *effective* sole-writer guard today.
- The grants become **ENFORCING** only when the app's derivation path connects as a
  non-superuser `pass_refresher` role and agent read-paths as `pass_reader`. That is a
  **connection-model change**, not a migration — and it is the owner's call.

This is the W1.4 #1 owner decision. I did **not** make it unilaterally: 0029 is the
schema contract (unambiguously sanctioned by §B/ADR-0052), drafted + validated + held;
the connection-model change that activates it is explicitly left open.

## The contract — what was PROVEN on live (rollback, 18/18 PASS)

| Check | Evidence |
|---|---|
| Roles exist (NOLOGIN) | `pass_refresher` + `pass_reader` in pg_roles, rolcanlogin=False |
| Default-deny | PUBLIC has **0** privileges on the pass tables + record_visible_from |
| pass_refresher sole-writer grants | SELECT normalized_record; INSERT walk_step; UPDATE walk_run; INSERT ops.audit_ledger |
| pass_reader pass-corpus-only grants | SELECT walk_step; NO INSERT walk_step; NO SELECT normalized_record |
| **Enforcement (SET ROLE pass_reader)** | SELECT walk_step **succeeds**; INSERT walk_step **DENIED** ("permission denied for table walk_step"); SELECT normalized_record **DENIED** |
| **Enforcement (SET ROLE pass_refresher)** | INSERT walk_step **succeeds**; SELECT normalized_record **succeeds**; DELETE walk_run **DENIED** (append-only) |
| Superuser finding documented | current_user superuser=True — the reason the grants are inert for the app |

The SET-ROLE proof is the key validation: it demonstrates the grants are a **real
enforcement mechanism** — a non-superuser role genuinely cannot write the pass corpus
or read canonical — and isolates the *only* reason they don't bite for the app today
(the superuser connection). Without that proof, "DB-enforced sole-writer" would be an
unverified claim; with it, the gap is precisely the connection model, nothing else.

---

## Failure reasons (what could go wrong) — prioritized

### P0 — grants are inert while the app is superuser (the #1 owner decision)
- **What could fail:** 0029 applies, everyone high-fives the "default-deny sole-writer,"
  but the app keeps connecting as `ai` (superuser) — so agents still write `walk_*` and
  read canonical freely. The grants are security theater until the connection model
  changes. The pre-mortem's own "enforced" claim would be a lie by omission.
- **Mitigation / owner decision (NOT made unilaterally):** introduce a non-superuser
  app role and split the connection model:
  - (a) app connects as a non-superuser role that is a member of `pass_refresher` +
    `pass_reader` + has the canonical SELECT the spine needs, using `SET ROLE` per path;
  - (b) keep the app as superuser and accept grants are advisory (F13 app-lock = the
    real guard, grants = defense-in-depth documentation);
  - (c) two connection pools (superuser admin / non-superuser agent+derivation).
  - My recommendation: **(a)** — it makes the grants real and matches the ADR-0052
    defense-in-depth intent. It touches `server/core/session.py` (engine factory) +
    `derivation.py` (SET ROLE pass_refresher around the sole-writer txn) + the agent
    read path. That wiring is **W1.5**, not this task.
- **Status:** **OPEN — needs owner ruling.** 0029 held; nothing applies until decided.

### P1 — pass_reader sees ALL runs, not just the agent's own (no per-agent scoping)
- **What could fail:** `pass_reader` has SELECT on `walk_run/walk_step` for the whole
  table — an agent could read ANOTHER agent's (or another pass's) walk_run, including
  parameters, model_id, belief state, and the delta. The §B intent is "agent reads its
  OWN pass corpus." The table grant is coarser than that.
- **Mitigation:** per-agent scoping needs either **RLS** (`CREATE POLICY ... USING
  agent_id = current_setting('app.agent_id')`) — also bypassed by superuser, so it
  activates with the P0 connection-model change — or app-layer filtering (the read
  path adds `WHERE agent_id = ...`). Neither is in 0029. Documented as the target, not
  the as-built.
- **Status:** **OPEN — deferred to W1.5.** Does not break the §B contract (the
  refresher sole-writer holds); it over-shares reads, the weaker half.

### P2 — the transition: agents today read the spine (canonical), 0029's target denies it
- **What could fail:** `pass_reader` has NO SELECT on `normalized_record`. Today agents
  read via `working.vw_spine_horizon`, which reads `normalized_record`. If 0029 applied
  AND agents were switched to `pass_reader` BEFORE W1.5 rebinds them to the pass
  corpus, **every agent read breaks** (permission denied on the spine). The target
  state (agents read pass corpus, not canonical) is correct per §B, but the *cutover
  order* matters: rebind agents to the pass corpus (W1.5) BEFORE stripping their
  canonical SELECT.
- **Mitigation:** 0029's grant set is the TARGET; it does not revoke the app's
  superuser access (nothing does, while superuser). The canonical-SELECT removal only
  bites when the app runs as `pass_reader`, which is gated on P0 + W1.5. Apply order:
  P0 connection model → W1.5 rebind agents to pass corpus → 0029's pass_reader grant
  is now sufficient → no spine access needed.
- **Status:** **OPEN — ordering risk.** Called out so the cutover sequence isn't missed.

### P3 — pass_refresher can UPDATE walk_run (status) — a compromised refresher could mask a failure
- **What could fail:** the refresher has UPDATE on `walk_run` (to set
  `status='completed'`/`'failed'`). A compromised refresher could rewrite a `failed`
  run to `completed`, or flip `final_corpus_hash`. The `verify_reproducibility` gate
  catches a *chain* mismatch, but a status rewrite + a re-derived matching chain would
  look clean. The blast radius is "one walk's status," not canonical truth — but it's
  the integrity ledger's neighbour.
- **Mitigation:** the refresher is the TRUSTED sole writer (§B sanctions exactly one
  writer); its UPDATE is required to stamp status. The defense is the chain-hash +
  audit attestation (a status rewrite without a matching re-derivation leaves the
  recorded `final_corpus_hash` reproducible-or-not — `verify_reproducibility` still
  flags a mismatched chain). Acceptable for now; flagged as "what a compromised
  refresher can do."
- **Status:** **acceptable (by design); flagged.**

### P4 — pass_refresher INSERT on ops.audit_ledger widens the trust boundary
- **What could fail:** granting INSERT on `ops.audit_ledger` to a non-superuser role
  means that role can append arbitrary audit rows (not just derivation attestations).
  The audit ledger is the platform's integrity spine; a wider INSERT grant is more
  authority than the refresher strictly needs.
- **Mitigation:** the refresher MUST attest inside its sole-writer txn (atomicity
  requires the same connection write both the step and the attestation), so INSERT on
  audit_ledger is unavoidable for the role. The defense is the audit chain's own
  `prev_hash`/`entry_hash` (a forged row breaks the audit chain, detectable by a hash
  walk). The narrower fix — a dedicated `audit.record(connection=)` that runs as a
  SECURITY DEFINER function with its own privileges — is a future hardening, not this
  task.
- **Status:** **acceptable for now; flagged for Wave 5 hardening.**

### P5 — schema USAGE is the "entry key" (broad by necessity)
- **What could fail:** `GRANT USAGE ON SCHEMA working` lets a role *see* the schema
  and reach any object it's explicitly granted on. It does NOT grant table access by
  itself (per-table GRANT still required), but it is broader than a per-object grant.
  A misconfiguration that later adds a per-table grant to `pass_reader` would silently
  activate.
- **Mitigation:** USAGE-without-table-grant is the standard Postgres pattern and grants
  nothing on its own; the per-table grants are the real gate. No action; noted for
  awareness.
- **Status:** **acceptable (standard pattern).**

---

## Resolutions — applied 2026-08-14

| Finding | Status | Evidence |
|---|---|---|
| Roles + default-deny grants (structure) | **PROVEN** | 18/18 rollback checks; information_schema + pg_roles |
| Grants are real enforcement (not just structure) | **PROVEN** | SET ROLE pass_reader/pass_refresher: INSERT denied / SELECT denied / INSERT allowed / DELETE denied |
| Superuser finding (grants inert for app) | **FOUND — owner decision** | `ai` rolsuper=True; the connection-model change is the gate |
| P1 per-agent scoping (RLS/app-layer) | **deferred to W1.5** | pass_reader SELECT is coarser than "own run" |
| P2 transition (canonical SELECT removal) | **OPEN — ordering** | rebind agents to pass corpus (W1.5) before stripping canonical access |
| P3 refresher UPDATE walk_run | **acceptable (by design)** | chain-hash + verify catch status/chain mismatch |
| P4 refresher INSERT audit_ledger | **acceptable; Wave 5 hardening** | SECURITY DEFINER audit function is the future narrower grant |

## Validation evidence (live, rollback — zero net write)

```
W1.4 grants recon (read-only):   app role `ai` is SUPERUSER (the decisive finding)
W1.4 grants validation:          18/18 PASS  (roles, default-deny, refresher grants,
                                              reader grants, SET-ROLE enforcement proof,
                                              superuser finding)
Full unit suite:                 688 passed, 24 skipped  (no regressions)
ruff (new scripts):              clean
ruff (project gate server/tests): clean
Post-check (live):               pass_refresher / pass_reader / pass-table grants all
                                 ABSENT → 0029 NOT applied; rollback left no trace
```

## Prod-apply / push status

- **0029 NOT applied to prod.** It is purely additive (CREATE ROLE + GRANT/REVOKE), but
  held with the wave for a single cutover AFTER the owner rules on P0 (connection model).
  Applying 0029 alone, while the app stays superuser, is harmless (inert) but pointless.
- **Nothing pushed to main** (commit-only-when-asked). All W1.4 work is uncommitted:
  - new: `sql/0029_pass_grants.sql`, `scripts/_wave1_recon_w14_grants.py`,
    `scripts/_wave1_validate_w14_grants.py`
  - edited: none

## What I would do differently next time

- **Run the superuser recon BEFORE designing the grants, not after.** I drafted 0029
  on the plan's assumption ("refresher role = sole writer") and only then discovered
  the app is superuser — which makes the whole migration inert until a separate
  connection-model change. A 30-second `SELECT rolsuper` recon up front would have
  re-framed the task as "schema contract + connection-model decision" from the start,
  and I'd have surfaced the owner decision before writing a line of SQL. The recon
  is now the first artifact; next time it's the first step.
- **State the inert-until-activated caveat in the migration header, not just the
  pre-mortem.** I did add it to 0029's header, but only after the validation surfaced
  it — the header should lead with "INERT WHILE SUPERUSER" because a future migrator
  reading 0029 in isolation would assume the grants enforce. (Fixed in the file.)

## Review schedule

- **Owner review (this + W1.1/W1.2/W1.3 pre-mortems together):**
  - **Decide P0 — the connection model.** Does the app introduce a non-superuser role
    (`pass_refresher` for derivation writes, `pass_reader` for agent reads, a third for
    spine/canonical reads) so the grants bite? Recommendation: **yes (option a)** — it
    is what makes §B's sole-writer real. This is the gate that turns 0029 from schema
    contract into enforcement, and it is the prerequisite for W1.5.
  - Reaffirm apply ORDER: P0 connection-model change → 0029 apply → W1.5 rebind agents
    to pass corpus (drop spine dependency) → optional RLS for P1 per-agent scoping.
- **W1.5 (next):** agent lane bindings — wire the derivation path to SET ROLE
    pass_refresher, the agent read path to the pass corpus (pass_reader), fix the W1.3
    P2 isolation gap (REPEATABLE READ derivation txn), and run the F3 live-Weaviate
    planted-fact dict-filter test + F6 `@approval` run-level test as the Wave-1 gate.

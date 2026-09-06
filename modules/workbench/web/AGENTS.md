# AGENTS.md — Workbench browser application

> _Byline: Codex · GPT-5.6-Sol · 2026-08-30._

- This subtree is React + Vite + TypeScript. Do not restore Next.js conventions, imports, runtime
  environment access, server components, or server actions.
- Browser build-time variables use `import.meta.env.VITE_*`. The production default is same-origin;
  do not bake a private service address into the client bundle.
- TanStack Router owns browser navigation. Preserve deep-link behavior through the FastAPI SPA
  fallback and keep unknown `/api`, health, docs, and asset paths as real 404 responses.
- Storybook uses the React/Vite builder. A Storybook build proves component compilation, not the
  deployed application or live API wiring.
- Finish and smoke-test one functional operator path before exposing another navigation
  destination. Do not advertise disconnected advanced surfaces.
- PostgreSQL and durable backend receipts remain authoritative. Browser state cannot promote,
  approve, or rewrite evidence by implication.
- Glide Data Grid is the target for data-heavy operator tables; migrate one complete table at a
  time and preserve its API/custody contract.
- Desktop/Tauri packaging is deferred until the browser application is complete. Keep desktop
  filesystem, IPC, and SQLite adapters outside browser-only modules.
- Run `npm run lint`, `npm run build`, `npm run smoke`, and `npm run build-storybook` for product
  changes. Coolify revision and live browser proof are separate required gates.

> _Sprint-mode policy REMOVED 2026-08-25 on owner order ("you're grounded — remove it entirely"). Confirm-and-discuss-before-changing is back in force._

## ATOMICITY — every unit must be assignable to a Temporal Activity

> _Owner directive · 2026-09-02. Binding on every directory below this file.
> Reinforces the 2026-08-25 boundary ruling, ADR-0061, and D-077._

**Write every unit of work so it can be handed to one Temporal Activity, and never
conflate multiple processes into one unit.**

Owner, 2026-09-02: *"Everything needs to be modular so that it can be assigned to
Temporal activities. We can't be conflating or mixing a bunch of processes into one.
Yes, the engine can call individual ones, but it's going to be calling the Activity
more likely than 99.9% of the time."* And: *"Or to be added into an n8n node which
gets run as an activity, however that shape looks."*

Rules, in force everywhere:

1. **One unit does one thing.** A parser parses and does nothing else (owner,
   2026-08-29: *"they parse, they do nothing more"*). A chunker chunks. A hasher
   hashes. If a function does two of those, it is wrong and must be split before it
   is wired to anything.
2. **Hashing is its own Activity family and is never folded into parsing, chunking,
   or normalization.** Custody hashing is separate machinery with its own boundary
   (D-077, four hash moments; see `docs/reference/HASH-TAXONOMY-2026-08-29.md`).
3. **The Activity is the normal caller.** Direct in-process calls stay legitimate —
   but the overwhelmingly common path is invocation *as*, or from *within*, a
   Temporal Activity. Design signatures for that: bounded inputs, bounded outputs,
   no ambient state, no hidden I/O, deterministic given its inputs, safely
   retryable. An Activity may be retried; anything that breaks on a second identical
   call is a defect.
4. **Three call shapes, one unit.** The same unit must serve all of them without
   knowing which is in play: (a) called directly in-process; (b) invoked as a
   Temporal Activity; (c) **wrapped as an n8n node that is itself executed as, or
   from within, an Activity.** n8n owns the visual flow, Temporal owns durability,
   the unit owns one job. A unit that needs to know its caller has a boundary
   violation in it.
5. **Pass references, never payloads.** Source bytes and bundles move by locator
   (`upload://`, `r2://`, sealed `file://`), never through Temporal history, an n8n
   payload, or a PostgreSQL activity request.
6. **No orchestration inside a unit.** Sequencing, fan-out, retries, and human gates
   belong to the workflow (`modules/engine/proffer`) and to n8n's visual flow — never
   buried inside a parser, decoder, chunker, or repository method.
7. **New capability = new Activity, registered in the stage graph.** Do not widen an
   existing Activity to cover a second concern because it is convenient.

The test before adding or editing anything here: *could this be scheduled on its own,
retried, wrapped as an n8n node, and reasoned about in isolation?* If not, it is not
finished.


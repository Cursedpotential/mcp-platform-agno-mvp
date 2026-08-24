@AGENTS.md

---

<!-- live-testing-policy:start -->
## Testing & Deployment Policy — LIVE ONLY, SPRINT MODE

> _Owner directive 2026-08-20 · recorded by Claude Code · Opus 5._
> _Supersedes any prior testing, staging, or change-approval guidance in this file._

- **Sprint mode is the default.** Bias to action. Ship the smallest working increment now,
  verify it live, keep moving. Do not stall on approval gates for routine work.
- **All testing is live testing.** Verify against the real deployed service, real data, real
  endpoints. A proxy signal is not verification.
- **No out-of-band testing.** No mocks, stubs, or synthetic fixtures standing in for a real
  dependency. A green unit test is not evidence the thing works.
- **No stubs. Write the whole function.** If it is a function, implement it fully. A stub is
  permitted ONLY when the real data or upstream service genuinely does not exist yet.
- **Any stub that must exist is marked LOUDLY and tracked.** Inline `# STUB:` / `// STUB:` at the
  site, plus an entry in `docs/URGENT-TODO.md`. A silent stub is a defect.
- **Ship and watch.** If it works, it stays up. If it breaks, fix it and put it back up.
  Breakage is the feedback loop, not a reason to stage.
- **On success, purge the test data.** Clear every row and artifact the live run created, then
  move on. Test data must never become canonical.
- **On failure, adjust in place and retry live.** Fix the real thing and run it again — never
  retreat to a mock, a staging copy, or a parallel instance to "prove" it.
- **No parallel stacks.** One live instance per service. No shadow deploys, no staging copies,
  no side-by-side `v2` beside `v1` — replace in place.
- **Fix forward.** Roll back only to restore service, never as a substitute for fixing the cause.
- **Mid-task feedback is QUEUED, not switched to.** If input arrives that is not about the task in
  flight, append it to `docs/URGENT-TODO.md` and keep going. Finish the current task; address the
  queued item at the point that work was already scheduled. Do not context-switch mid-task.

**Still stop and ask for:** destroying data, terminating/wiping a host, anything outward-facing
(publishing, sending, paying), and irreversible spend. Sprint mode removes ceremony, not judgment.
<!-- live-testing-policy:end -->

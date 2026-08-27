// Backend base URL. Public (browser-visible) on purpose: this frontend runs
// tailnet-only, same as the llm-probe backend, so the value is never secret —
// it's just "which tailnet host". Provider API keys stay server-side in the
// FastAPI service and never reach this app.
export const LLM_PROBE_URL =
  process.env.NEXT_PUBLIC_LLM_PROBE_URL || "http://100.91.190.107:8030";

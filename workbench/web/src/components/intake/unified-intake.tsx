// Byline: Codex · GPT-5 · 2026-08-28 (production unified intake vertical slice)
// Byline: Codex · GPT-5 · 2026-08-29 (truthful Matter baseline failure state)
// Byline: Codex · GPT-5 · 2026-08-29 (single-case automatic scope binding)
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  FileText,
  FolderOpen,
  Loader2,
  RotateCcw,
  Scale,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  ApiError,
  decideUIW,
  getMatter,
  getUIWPreview,
  listMatters,
  startUIW,
  uploadUIWSource,
} from "@/lib/api-client";
import type {
  MatterDetail,
  UIWPreviewResponse,
  UIWStartResponse,
  UIWUploadResponse,
} from "@/lib/shared/types";

type IntakePhase = "choose" | "ready" | "starting" | "review" | "deciding" | "complete" | "error";

function errorText(error: unknown) {
  return error instanceof ApiError ? error.message : error instanceof Error ? error.message : "The intake request failed";
}

function declaredFormat(file: File) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  const formats: Record<string, string> = {
    xml: "sms_export_xml",
    json: "message_export_json",
    txt: "delimited_text",
    csv: "delimited_text",
    pdf: "pdf",
    docx: "docx",
    zip: "archive",
  };
  return formats[extension ?? ""] ?? "unknown_binary";
}

function bytes(value: number) {
  if (value < 1024) return `${value} bytes`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

const terminalPreviewPhases = new Set(["awaiting_decision", "approved", "rejected", "timed_out"]);

async function waitForPreview(workflowId: string, attempts = 80) {
  let lastState: UIWPreviewResponse | null = null;
  let lastError: unknown = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      lastState = await getUIWPreview(workflowId);
      lastError = null;
      if (terminalPreviewPhases.has(lastState.phase)) return lastState;
    } catch (requestError) {
      lastError = requestError;
      const transient =
        requestError instanceof ApiError &&
        (requestError.isRetryable || requestError.isNotFound || requestError.isConflict || requestError.status === 422);
      if (!transient) throw requestError;
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  if (lastError) throw lastError;
  throw new Error(`The workflow is still processing${lastState ? ` (${lastState.phase})` : ""}. Try again shortly.`);
}

async function fileDigest(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

export function UnifiedIntake() {
  const [matter, setMatter] = useState<MatterDetail | null>(null);
  const [scopeLoading, setScopeLoading] = useState(true);
  const [scopeError, setScopeError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [digest, setDigest] = useState("");
  const [textPreview, setTextPreview] = useState("");
  const [phase, setPhase] = useState<IntakePhase>("choose");
  const [upload, setUpload] = useState<UIWUploadResponse | null>(null);
  const [run, setRun] = useState<UIWStartResponse | null>(null);
  const [preview, setPreview] = useState<UIWPreviewResponse | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    listMatters()
      .then((response) => {
        if (response.total === 0) {
          throw new Error("Intake is blocked because the Platform has no case. Restore the single canonical case before ingesting evidence.");
        }
        if (response.total !== 1 || response.data.length !== 1) {
          throw new Error(
            `Intake is blocked because the Platform returned ${response.total} Matters. This indicates split or duplicated case data and must be repaired before ingestion continues.`,
          );
        }
        return getMatter(response.data[0].id);
      })
      .then((fixedMatter) => {
        if (!cancelled) setMatter(fixedMatter);
      })
      .catch((requestError) => {
        if (!cancelled) setScopeError(errorText(requestError));
      })
      .finally(() => {
        if (!cancelled) setScopeLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const primaryCourtCase = matter?.court_cases.find((item) => item.is_primary);
  const lines = useMemo(() => textPreview.split(/\r?\n/).filter(Boolean).slice(0, 12), [textPreview]);

  async function selectFile(selected: File | null) {
    setFile(selected);
    setUpload(null);
    setRun(null);
    setPreview(null);
    setError(null);
    if (!selected) {
      setDigest("");
      setTextPreview("");
      setPhase("choose");
      return;
    }
    setPhase("ready");
    const [nextDigest, nextText] = await Promise.all([
      fileDigest(selected),
      selected.type.startsWith("text/") || /\.(txt|csv|json|xml)$/i.test(selected.name)
        ? selected.text()
        : Promise.resolve(""),
    ]);
    setDigest(nextDigest);
    setTextPreview(nextText.slice(0, 250_000));
  }

  async function start() {
    if (!file || !matter || !primaryCourtCase) return;
    setPhase("starting");
    setError(null);
    try {
      const sealed = await uploadUIWSource(file);
      setUpload(sealed);
      const requestId = `uiw-${matter.id}-${crypto.randomUUID()}`;
      const started = await startUIW({
        request_id: requestId,
        source_ref: sealed.acquisition_ref,
        declared_format: declaredFormat(file),
        parser_options_ref: "parser-options://default-v1",
        matter_id: matter.id,
        court_case_id: primaryCourtCase.id,
      });
      setRun(started);

      const state = await waitForPreview(started.workflow_id);
      setPreview(state);
      setPhase(state.phase === "awaiting_decision" ? "review" : "complete");
    } catch (requestError) {
      setError(errorText(requestError));
      setPhase("error");
    }
  }

  async function decide(approved: boolean) {
    if (!run) return;
    if (!approved && !rejectionReason.trim()) {
      setError("Enter a reason before rejecting this preview.");
      return;
    }
    setPhase("deciding");
    setError(null);
    try {
      await decideUIW(run.workflow_id, {
        approved,
        reason: approved ? "Owner approved the selected parser preview" : rejectionReason.trim(),
        decider: "owner",
      });
      const state = await waitForPreview(run.workflow_id, 20);
      setPreview(state);
      setPhase("complete");
    } catch (requestError) {
      setError(errorText(requestError));
      setPhase("review");
    }
  }

  function reset() {
    setFile(null);
    setDigest("");
    setTextPreview("");
    setUpload(null);
    setRun(null);
    setPreview(null);
    setRejectionReason("");
    setError(null);
    setPhase("choose");
  }

  const activeStep = phase === "choose" || phase === "ready" ? 1 : phase === "starting" ? 2 : phase === "review" || phase === "deciding" ? 3 : 4;

  return (
    <div className="min-h-full">
      <section className="border-b bg-card px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="platform-kicker mb-1">Evidence operations desk</p>
            <h1 className="text-xl font-semibold tracking-tight">Intake new evidence</h1>
            <p className="mt-1 text-sm text-muted-foreground">Choose a source, inspect it, then make the durable workflow decision for the fixed case.</p>
          </div>
          <div className="flex items-center gap-2 border bg-background px-3 py-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-4 w-4" /> PostgreSQL authority preserved
          </div>
        </div>
      </section>

      <ol className="grid grid-cols-4 border-b bg-card px-6 py-4" aria-label="Intake progress">
        {["Choose source", "Seal and start", "Review selection", "Read receipt"].map((label, index) => {
          const step = index + 1;
          const complete = step < activeStep;
          const active = step === activeStep;
          return (
            <li key={label} className="relative flex min-w-0 items-center gap-3 after:absolute after:left-11 after:right-3 after:top-5 after:h-px after:bg-border last:after:hidden">
              <span className={`relative z-10 grid h-10 w-10 shrink-0 place-items-center rounded-full border font-mono text-sm ${complete ? "border-[#2f9d67] bg-[#2f9d67] text-white" : active ? "border-primary bg-primary text-primary-foreground" : "bg-card"}`}>
                {complete ? <Check className="h-4 w-4" /> : step}
              </span>
              <span className="relative z-10 hidden bg-card pr-3 text-xs font-semibold sm:block">{label}</span>
            </li>
          );
        })}
      </ol>

      {(scopeError || error) && (
        <div className="flex items-center gap-2 border-b border-[#b5433b] bg-[#fbe9e7] px-6 py-3 text-sm text-[#8f302a]" role="alert">
          <AlertTriangle className="h-4 w-4" /> {scopeError || error}
        </div>
      )}

      <div className="grid min-h-[620px] lg:grid-cols-[minmax(0,1fr)_330px]">
        <main className="min-w-0 p-6">
          {!file ? (
            <div className="platform-panel mx-auto grid min-h-[430px] max-w-3xl place-items-center border-dashed p-10 text-center">
              <div>
                <div className="mx-auto mb-5 grid h-14 w-14 place-items-center border bg-accent text-accent-foreground"><Upload className="h-6 w-6" /></div>
                <p className="platform-kicker mb-2">Source acquisition</p>
                <h2 className="text-2xl font-semibold">Choose the source you want to inspect</h2>
                <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">The browser computes an integrity preview. Starting intake streams the bytes to the authenticated immutable upload ingress and sends only its opaque reference through Temporal.</p>
                <label className="mt-6 inline-flex cursor-pointer items-center gap-2 border border-primary bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90">
                  <FolderOpen className="h-4 w-4" /> Choose file
                  <input className="sr-only" type="file" onChange={(event) => void selectFile(event.target.files?.[0] ?? null)} />
                </label>
              </div>
            </div>
          ) : (
            <div className="platform-panel overflow-hidden">
              <div className="flex flex-wrap items-center gap-3 border-b px-5 py-4">
                <div className="grid h-10 w-10 place-items-center border bg-accent text-accent-foreground"><FileText className="h-5 w-5" /></div>
                <div className="min-w-0 flex-1">
                  <p className="platform-rule-title">Selected source</p>
                  <strong className="block truncate text-sm">{file.name}</strong>
                  <span className="text-xs text-muted-foreground">{declaredFormat(file)} · {bytes(file.size)}</span>
                </div>
                <Button variant="outline" onClick={reset}><RotateCcw className="h-4 w-4" /> Change file</Button>
              </div>

              <div className="border-b px-5 py-3">
                <p className="platform-rule-title mb-2">Local content preview</p>
                {lines.length ? (
                  <div className="max-h-[310px] overflow-auto border bg-background font-mono text-[11px] leading-5" role="region" aria-label="Selected source preview" tabIndex={0}>
                    {lines.map((line, index) => <div key={`${index}-${line.slice(0, 24)}`} className="grid grid-cols-[42px_1fr] border-b px-3 py-2 last:border-b-0"><span className="text-muted-foreground">{String(index + 1).padStart(2, "0")}</span><span className="break-words">{line}</span></div>)}
                  </div>
                ) : (
                  <div className="border bg-background px-4 py-10 text-center text-sm text-muted-foreground">Binary content is not rendered in the browser. The server-side parser selection remains authoritative.</div>
                )}
              </div>

              {preview && (
                <div className="border-b bg-accent/40 px-5 py-4">
                  <p className="platform-rule-title mb-2">Durable parser selection</p>
                  <div className="flex flex-wrap items-center gap-3 text-sm"><span className="font-semibold">{preview.phase.replaceAll("_", " ")}</span><span className="font-mono text-xs text-muted-foreground">{preview.select_ref}</span></div>
                  {preview.reason && <p className="mt-2 text-xs text-muted-foreground">{preview.reason}</p>}
                </div>
              )}

              <div className="flex flex-col gap-3 border-t bg-card px-5 py-4 sm:flex-row sm:items-center">
                {phase === "review" || phase === "deciding" ? (
                  <>
                    <input className="h-10 min-w-0 flex-1 border bg-background px-3 text-sm" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} placeholder="Reason required for rejection" aria-label="Rejection reason" />
                    <Button variant="outline" disabled={phase === "deciding"} onClick={() => void decide(false)} className="border-[#b5433b] text-[#a9342d]"><X className="h-4 w-4" /> Reject preview</Button>
                    <Button disabled={phase === "deciding"} onClick={() => void decide(true)}>{phase === "deciding" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Approve and continue</Button>
                  </>
                ) : phase === "complete" ? (
                  <><div className="flex-1 text-sm"><strong className="capitalize">{preview?.phase ?? "Decision signaled"}</strong><p className="text-xs text-muted-foreground">This status was read from the running Temporal workflow.</p></div><Button variant="outline" onClick={reset}>Start another intake</Button></>
                ) : (
                  <><div className="flex-1 text-xs text-muted-foreground">{matter && !primaryCourtCase ? "This Matter needs a primary proceeding before evidence can be bound to it." : "Nothing becomes evidence by selecting or previewing this file."}</div><Button disabled={!matter || !primaryCourtCase || phase === "starting"} onClick={() => void start()} className="min-w-56">{phase === "starting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Seal and start intake <ChevronRight className="h-4 w-4" /></Button></>
                )}
              </div>
            </div>
          )}
        </main>

        <aside className="border-l bg-card p-5">
          <section className="border-b pb-5">
            <p className="platform-rule-title mb-3">Fixed case</p>
            {scopeLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading case identity</div>
            ) : matter ? (
              <div className="space-y-1 text-xs"><strong className="block text-sm">{matter.title}</strong><span className="block text-muted-foreground">{matter.partition_keys.join(", ") || "No partition configured"}</span>{primaryCourtCase && <span className="flex items-center gap-1 text-muted-foreground"><Scale className="h-3.5 w-3.5" /> {primaryCourtCase.caption}</span>}</div>
            ) : (
              <div className="flex items-start gap-2 text-xs text-[#8f302a]"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Case identity unavailable. Intake remains blocked.</div>
            )}
          </section>

          <section className="border-b py-5">
            <p className="platform-rule-title mb-3">Integrity preview</p>
            <dl className="space-y-3 text-xs">
              <div><dt className="text-muted-foreground">SHA-256</dt><dd className="mt-1 break-all font-mono text-[10px]">{upload?.sha256 || digest || "Choose a source"}</dd></div>
              <div className="grid grid-cols-2 gap-3"><div><dt className="text-muted-foreground">Local size</dt><dd>{file ? bytes(file.size) : "—"}</dd></div><div><dt className="text-muted-foreground">Sealed size</dt><dd>{upload ? bytes(upload.byte_length) : "—"}</dd></div></div>
              {upload && <div><dt className="text-muted-foreground">Acquisition reference</dt><dd className="mt-1 break-all font-mono text-[10px]">{upload.acquisition_ref}</dd></div>}
            </dl>
          </section>

          <section className="border-b py-5">
            <p className="platform-rule-title mb-3">Workflow receipt</p>
            {run ? <dl className="space-y-3 text-xs"><div><dt className="text-muted-foreground">Workflow ID</dt><dd className="break-all font-mono text-[10px]">{run.workflow_id}</dd></div><div><dt className="text-muted-foreground">Run ID</dt><dd className="break-all font-mono text-[10px]">{run.run_id}</dd></div><div><dt className="text-muted-foreground">Phase</dt><dd className="capitalize">{preview?.phase.replaceAll("_", " ") ?? phase}</dd></div></dl> : <p className="text-xs leading-5 text-muted-foreground">A receipt appears only after the server seals the source and Temporal accepts the workflow.</p>}
          </section>

          <section className="pt-5">
            <div className="flex gap-2 border border-[#c58214] bg-[#fff4dd] p-3 text-[#684b18] dark:border-[#d9aa52] dark:bg-[#2f281d] dark:text-[#ffe0a6]">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div><strong className="block text-xs">This preview is not evidence.</strong><p className="mt-1 text-[11px] leading-5">Approval resumes the governed workflow. It does not independently establish a fact or alter an approved evidence record.</p></div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

// Byline: Codex · GPT-5 · 2026-08-15 (reviewer-of-record evidence gate)
"use client";

import { useRef, useState } from "react";
import { AlertTriangle, ClipboardCheck, History, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { listEvidenceReviews, reviewEvidenceItem } from "@/lib/api-client";
import type {
  EvidenceItem,
  EvidenceReviewDecision,
  EvidenceReviewRecord,
  EvidenceReviewResult,
} from "@/lib/shared/types";

interface EvidenceReviewDialogProps {
  item: EvidenceItem;
  onReviewed: (result: EvidenceReviewResult) => void;
}

const DECISIONS: Array<{ value: EvidenceReviewDecision; label: string }> = [
  { value: "approved", label: "Approve record-level draft" },
  { value: "rejected", label: "Reject draft" },
  { value: "needs_changes", label: "Needs changes" },
  { value: "needs_context", label: "Needs more context" },
  { value: "hold", label: "Place on hold" },
  { value: "escalated", label: "Escalate review" },
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The review decision could not be recorded";
}

export function EvidenceReviewDialog({ item, onReviewed }: EvidenceReviewDialogProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [decision, setDecision] = useState<EvidenceReviewDecision>("needs_context");
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  function reset() {
    setDecision("needs_context");
    setRationale("");
    setError(null);
  }

  async function submit() {
    if (submittingRef.current || !rationale.trim()) return;
    submittingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const result = await reviewEvidenceItem(item.matter_id, item.id, {
        decision,
        rationale: rationale.trim(),
      });
      if (result.item.safe_for_legal_use || result.item.is_authenticated) {
        throw new Error("Review unexpectedly granted authentication or legal safety");
      }
      onReviewed(result);
      setOpen(false);
      reset();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      submittingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <>
      <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
        <ClipboardCheck aria-hidden="true" /> Review draft
      </Button>
      <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) reset(); }}>
        <DialogContent aria-busy={saving}>
          <DialogHeader>
            <DialogTitle>Record reviewer decision</DialogTitle>
            <DialogDescription>
              This records an append-only human decision for the exact promoted record. Approval does not authenticate the source or make it safe for legal use.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
          {error && <p role="alert" className="rounded-md border border-destructive p-3 text-sm text-destructive">{error}</p>}
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{item.review_status}</Badge>
              <Badge variant="destructive">Unsafe for legal use</Badge>
              <Badge variant="outline">Unauthenticated</Badge>
            </div>
            <div className="space-y-1">
              <Label htmlFor={`review-decision-${item.id}`}>Decision</Label>
              <select
                id={`review-decision-${item.id}`}
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={decision}
                onChange={(event) => setDecision(event.target.value as EvidenceReviewDecision)}
              >
                {DECISIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor={`review-rationale-${item.id}`}>Reviewer rationale</Label>
              <Textarea
                id={`review-rationale-${item.id}`}
                maxLength={20000}
                value={rationale}
                onChange={(event) => setRationale(event.target.value)}
                placeholder="State what was reviewed and why this decision is appropriate."
              />
            </div>
            <div className="flex gap-2 rounded-md border border-amber-500 bg-amber-500/5 p-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" />
              <p>Even an approved review remains unauthenticated and unsafe for legal use until a separate authentication gate is completed.</p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="button" disabled={saving || !rationale.trim()} onClick={() => void submit()}>
              {saving && <Loader2 className="animate-spin" aria-hidden="true" />} Record decision
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

interface EvidenceReviewHistoryDialogProps {
  item: EvidenceItem;
}

export function EvidenceReviewHistoryDialog({ item }: EvidenceReviewHistoryDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<EvidenceReviewRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  async function loadHistory() {
    const request = ++requestRef.current;
    setLoading(true);
    setHistory([]);
    setError(null);
    try {
      const response = await listEvidenceReviews(item.matter_id, item.id);
      if (request !== requestRef.current) return;
      setHistory(response.data);
    } catch (requestError) {
      if (request !== requestRef.current) return;
      setHistory([]);
      setError(errorMessage(requestError));
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  }

  function changeOpen(next: boolean) {
    setOpen(next);
    if (next) {
      void loadHistory();
    } else {
      requestRef.current += 1;
      setHistory([]);
      setError(null);
    }
  }

  return (
    <>
      <Button type="button" size="sm" variant="ghost" onClick={() => changeOpen(true)}>
        <History aria-hidden="true" /> Review history
      </Button>
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent aria-busy={loading}>
          <DialogHeader>
            <DialogTitle>Review history</DialogTitle>
            <DialogDescription>
              Append-only reviewer decisions for this exact evidence item. These decisions do not authenticate the source or grant legal safety.
            </DialogDescription>
          </DialogHeader>
          {loading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground" role="status">
              <Loader2 className="animate-spin" aria-hidden="true" /> Loading review history
            </div>
          ) : error ? (
            <p role="alert" className="rounded-md border border-destructive p-3 text-sm text-destructive">{error}</p>
          ) : history.length === 0 ? (
            <p className="py-6 text-sm text-muted-foreground">No reviewer decision has been recorded.</p>
          ) : (
            <ol className="max-h-[60vh] space-y-3 overflow-y-auto">
              {history.map((record) => (
                <li key={record.decision_id} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{record.decision.replaceAll("_", " ")}</Badge>
                    <Badge variant="outline">{record.court_readiness.replaceAll("_", " ")}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {new Date(record.decided_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-2 text-sm">{record.rationale}</p>
                  <p className="mt-2 text-xs text-muted-foreground">Reviewer: {record.reviewer}</p>
                </li>
              ))}
            </ol>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

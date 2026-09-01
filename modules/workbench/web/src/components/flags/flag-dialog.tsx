// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: corroboration flags — requirements addendum 6)
"use client";

/**
 * "Flag for evidence" dialog — the create side of a corroboration flag.
 * Opened from the record browser/detail drawer (C3) with the claim
 * prefilled from the selected record's text, per requirements addendum 6:
 * "flag events/claims as needs corroborating evidence while reviewing."
 * Reusable from any review surface — only `targetKind`/`targetId` change.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, createFlag } from "@/lib/api-client";
import {
  EVIDENCE_WANTED_OPTIONS,
  type EvidenceWantedType,
  type FlagTargetKind,
} from "@/lib/shared/types";

interface FlagDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetKind: FlagTargetKind;
  targetId: string;
  /** Prefilled from the selection/record text that triggered this dialog. */
  claimPrefill?: string;
  onCreated?: () => void;
}

export function FlagDialog({
  open,
  onOpenChange,
  targetKind,
  targetId,
  claimPrefill,
  onCreated,
}: FlagDialogProps) {
  const [claim, setClaim] = useState("");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [evidenceWanted, setEvidenceWanted] = useState<EvidenceWantedType[]>([]);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    queueMicrotask(() => {
      setClaim(claimPrefill ?? "");
      setDateStart("");
      setDateEnd("");
      setEvidenceWanted([]);
      setNotes("");
    });
  }, [open, claimPrefill]);

  const toggleEvidence = (type: EvidenceWantedType) => {
    setEvidenceWanted((prev) => (prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]));
  };

  const handleSubmit = async () => {
    if (!claim.trim()) {
      toast.error("Describe the claim that needs corroboration");
      return;
    }
    setSubmitting(true);
    try {
      await createFlag({
        target_kind: targetKind,
        target_id: targetId,
        claim: claim.trim(),
        claim_date_start: dateStart || null,
        claim_date_end: dateEnd || null,
        evidence_wanted: evidenceWanted.length ? evidenceWanted : null,
        notes: notes.trim() || null,
      });
      toast.success("Flagged for corroboration");
      onCreated?.();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to create flag");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Flag for evidence</DialogTitle>
          <DialogDescription>
            The AI chats are the owner&apos;s story, not evidence — this operationalizes the
            story-&gt;evidence map. Feeds the Evidence Queue.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="flag-claim">Claim</Label>
            <Textarea
              id="flag-claim"
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              rows={3}
              placeholder="What's being claimed that needs corroboration?"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="flag-date-start">Claim date (start)</Label>
              <Input
                id="flag-date-start"
                type="date"
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="flag-date-end">Claim date (end)</Label>
              <Input id="flag-date-end" type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Evidence wanted</Label>
            <div className="flex flex-wrap gap-1.5">
              {EVIDENCE_WANTED_OPTIONS.map((type) => (
                <button key={type} type="button" onClick={() => toggleEvidence(type)}>
                  <Badge
                    variant={evidenceWanted.includes(type) ? "default" : "outline"}
                    className="cursor-pointer capitalize"
                  >
                    {type}
                  </Badge>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="flag-notes">Notes</Label>
            <Textarea
              id="flag-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Optional context"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Flagging…" : "Flag"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

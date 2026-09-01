// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: active hash verification — requirements addendum 2)
"use client";

/**
 * POST /api/verify/{sha256} + the verdict panel — shared between the Runs
 * stage-drawer's custody section (components/runs/stage-drawer.tsx) and the
 * Records page's row/detail-drawer Verify action, so the verdict rendering
 * (green intact / amber hash-only-ok / red broken) only exists once.
 *
 * 'hash-only-ok' is a DISTINCT verdict from 'intact' — light-tier custody
 * (whole-file sha256 only, no H1/H2/H3 chain rows) must be labeled honestly
 * as such, never presented as a full chain verification that didn't happen
 * (requirements addendum 2's "Two-tier custody" note).
 */
import { useState } from "react";
import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError, verifySha256 } from "@/lib/api-client";
import type { VerifyResponse, VerifyVerdict } from "@/lib/shared/types";

interface VerdictStyle {
  icon: typeof ShieldCheck;
  className: string;
  label: string;
}

function verdictStyle(verdict: VerifyVerdict): VerdictStyle {
  switch (verdict) {
    case "intact":
      return {
        icon: ShieldCheck,
        className: "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
        label: "Intact",
      };
    case "hash-only-ok":
      return {
        icon: ShieldQuestion,
        className: "border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-400",
        label: "Hash-only OK (light tier)",
      };
    case "broken":
    default:
      return {
        icon: ShieldAlert,
        className: "border-destructive/50 bg-destructive/10 text-destructive",
        label: "Broken",
      };
  }
}

function VerifyVerdictCard({ result }: { result: VerifyResponse }) {
  const style = verdictStyle(result.verdict);
  const Icon = style.icon;
  const failingLinks = (result.chain ?? []).filter((l) => !l.ok);

  return (
    <div className={`space-y-2 rounded-md border p-3 text-sm ${style.className}`}>
      <div className="flex items-center gap-2 font-semibold">
        <Icon className="size-4 shrink-0" />
        {style.label}
        <Badge variant="outline" className="ml-auto capitalize">
          {result.custody_tier} tier
        </Badge>
      </div>
      <div className="space-y-1 text-xs">
        <div className="flex items-start justify-between gap-2">
          <span className="shrink-0 opacity-80">Computed</span>
          <span className="truncate text-right font-mono">{result.computed}</span>
        </div>
        <div className="flex items-start justify-between gap-2">
          <span className="shrink-0 opacity-80">Recorded</span>
          <span className="truncate text-right font-mono">{result.recorded}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="opacity-80">sha256 match</span>
          <span>{result.sha256_match ? "yes" : "no"}</span>
        </div>
      </div>

      {result.chain && result.chain.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide opacity-80">
            Custody chain (H1 &rarr; H{result.chain.length})
          </p>
          <div className="flex flex-wrap gap-1">
            {result.chain.map((link) => (
              <Badge
                key={link.seq}
                variant={link.ok ? "outline" : "destructive"}
                className={link.ok ? "border-emerald-500/50 text-emerald-700 dark:text-emerald-400" : ""}
              >
                #{link.seq} {link.ok ? "ok" : "FAIL"}
              </Badge>
            ))}
          </div>
          {failingLinks.length > 0 && (
            <p className="mt-1 text-xs">
              Chain breaks at link{failingLinks.length > 1 ? "s" : ""}{" "}
              {failingLinks.map((l) => `#${l.seq}`).join(", ")}.
            </p>
          )}
        </div>
      )}

      {result.verdict === "hash-only-ok" && (
        <p className="text-xs opacity-80">
          Light custody tier — whole-file sha256 verified, no H1/H2/H3 chain was recorded to walk.
        </p>
      )}
    </div>
  );
}

export function VerifyPanel({ sha256 }: { sha256: string | null | undefined }) {
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handleVerify = async () => {
    if (!sha256) return;
    setLoading(true);
    try {
      const res = await verifySha256(sha256);
      setResult(res);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verify failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={handleVerify} disabled={!sha256 || loading}>
          {loading ? "Verifying…" : "Verify"}
        </Button>
        {!sha256 && <span className="text-xs text-muted-foreground">No sha256 recorded yet</span>}
      </div>
      {result && <VerifyVerdictCard result={result} />}
    </div>
  );
}

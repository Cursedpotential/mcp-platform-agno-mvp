// Byline: Codex · GPT-5 · 2026-08-15 (Matter-scoped custody inspection)
"use client";

import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, Eye, Fingerprint, Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getEvidenceDetail } from "@/lib/api-client";
import type { EvidenceDetail, EvidenceItem } from "@/lib/shared/types";

function readableDate(value?: string | null) {
  if (!value) return "Not established";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function detailError(error: unknown) {
  return error instanceof Error ? error.message : "Evidence provenance could not be inspected";
}

export function validateEvidenceDetail(detail: EvidenceDetail, expected: EvidenceItem) {
  if (detail.item.id !== expected.id || detail.item.matter_id !== expected.matter_id) {
    return "Inspection returned a different Matter evidence item";
  }
  if (detail.record.id !== expected.normalized_record_id) {
    return "Canonical record identity does not match this evidence item";
  }
  if (detail.custody_hash.id !== expected.evidence_hash_id) {
    return "Custody hash identity does not match this evidence item";
  }
  if (detail.source.id !== expected.source_id) {
    return "Source identity does not match this evidence item";
  }
  if (
    expected.file_node_id &&
    (!detail.file_node || detail.file_node.id !== expected.file_node_id)
  ) {
    return "File-node provenance does not match this evidence item";
  }
  if (
    detail.custody_hash.level !== "H1" ||
    detail.custody_hash.algo.toLowerCase() !== "sha256" ||
    detail.custody_hash.canon_version !== "h1-rawbytes-v1"
  ) {
    return "Inspection did not return the required H1 SHA-256 raw-bytes custody contract";
  }
  if (detail.source.hash_canon_version !== "h1-rawbytes-v1") {
    return "Source did not return the required raw-bytes canon version";
  }
  const pointer = detail.promotion.source_pointer;
  if (
    pointer.matter_id !== expected.matter_id ||
    pointer.court_case_id !== expected.court_case_id ||
    pointer.normalized_record_id !== detail.record.id ||
    pointer.evidence_hash_id !== detail.custody_hash.id ||
    pointer.source_id !== detail.source.id
  ) {
    return "Promotion pointer does not match this evidence item";
  }
  return null;
}

export async function loadValidatedEvidenceDetail(item: EvidenceItem) {
  const detail = await getEvidenceDetail(item.matter_id, item.id);
  const invalid = validateEvidenceDetail(detail, item);
  if (invalid) throw new Error(invalid);
  return detail;
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10rem_1fr]">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}

export function EvidenceDetailContent({ detail }: { detail: EvidenceDetail }) {
  const { item, promotion, record, custody_hash: custody, source, file_node: fileNode } = detail;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-500/60 bg-amber-500/5 p-3 text-sm">
        <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
        <Badge variant="outline">{item.review_status}</Badge>
        {item.hitl_required && <Badge variant="outline">HITL required</Badge>}
        {!item.safe_for_legal_use && <Badge variant="destructive">Unsafe for legal use</Badge>}
        {!item.is_authenticated && <Badge variant="outline">Unauthenticated</Badge>}
        <span className="basis-full text-muted-foreground">
          Inspection confirms identity and custody coordinates. It does not authenticate the source or grant legal safety.
        </span>
      </div>

      <section aria-labelledby={`record-content-${item.id}`} className="space-y-2">
        <h3 id={`record-content-${item.id}`} className="font-semibold">Exact canonical record</h3>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{record.record_type}</Badge>
          {record.role && <Badge variant="outline">role: {record.role}</Badge>}
          <Badge variant="outline">{record.disclosure_tier}</Badge>
        </div>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-muted/30 p-3 text-sm">
          {record.content}
        </pre>
        <dl className="space-y-2 rounded-md border p-3">
          <DetailRow label="Record ID"><span className="break-all font-mono text-xs">{record.id}</span></DetailRow>
          <DetailRow label="Occurred"><time dateTime={record.occurred_at || undefined}>{readableDate(record.occurred_at)}</time></DetailRow>
          <DetailRow label="Acquired"><time dateTime={record.acquired_at || undefined}>{readableDate(record.acquired_at)}</time></DetailRow>
          <DetailRow label="Ingested"><time dateTime={record.ingested_at}>{readableDate(record.ingested_at)}</time></DetailRow>
          <DetailRow label="Realized"><time dateTime={record.realized_at || undefined}>{readableDate(record.realized_at)}</time></DetailRow>
          <DetailRow label="Record source">{record.source}</DetailRow>
        </dl>
      </section>

      <section aria-labelledby={`custody-${item.id}`} className="space-y-2">
        <h3 id={`custody-${item.id}`} className="flex items-center gap-2 font-semibold">
          <Fingerprint className="h-4 w-4" aria-hidden="true" /> H1 custody
        </h3>
        <dl className="space-y-2 rounded-md border p-3">
          <DetailRow label="Contract">{custody.level} · {custody.algo} · {custody.canon_version}</DetailRow>
          <DetailRow label="SHA-256"><span className="break-all font-mono text-xs">{custody.digest_sha256}</span></DetailRow>
          <DetailRow label="Hash ID"><span className="break-all font-mono text-xs">{custody.id}</span></DetailRow>
          <DetailRow label="Hashed"><time dateTime={custody.hashed_at}>{readableDate(custody.hashed_at)}</time></DetailRow>
          <DetailRow label="Computed by">{custody.computed_by || "Not recorded"}</DetailRow>
        </dl>
      </section>

      <section aria-labelledby={`source-${item.id}`} className="space-y-2">
        <h3 id={`source-${item.id}`} className="font-semibold">Canonical source</h3>
        <dl className="space-y-2 rounded-md border p-3">
          <DetailRow label="Filename">{source.original_filename || "Not recorded"}</DetailRow>
          <DetailRow label="Source type">{source.source_type}{source.source_platform ? ` · ${source.source_platform}` : ""}</DetailRow>
          <DetailRow label="Media">{source.mime_type || "Unknown"} · {source.byte_size.toLocaleString()} bytes</DetailRow>
          <DetailRow label="Acquisition">{source.acquisition_source}{source.acquisition_method ? ` · ${source.acquisition_method}` : ""}</DetailRow>
          <DetailRow label="Acquired"><time dateTime={source.acquired_at_utc || undefined}>{readableDate(source.acquired_at_utc)}</time> · {source.acquired_certainty}</DetailRow>
          <DetailRow label="Custody status">{source.custody_status} · {source.provenance_tier}</DetailRow>
          <DetailRow label="Source ID"><span className="break-all font-mono text-xs">{source.id}</span></DetailRow>
          <DetailRow label="Verification">{source.verified_by ? `${source.verified_by} · ${readableDate(source.verified_at)}` : "Not separately verified"}</DetailRow>
        </dl>
      </section>

      {fileNode && (
        <section aria-labelledby={`file-node-${item.id}`} className="space-y-2">
          <h3 id={`file-node-${item.id}`} className="font-semibold">Structural file provenance</h3>
          <dl className="space-y-2 rounded-md border p-3">
            <DetailRow label="Node">{fileNode.node_kind} · <span className="break-all font-mono text-xs">{fileNode.id}</span></DetailRow>
            <DetailRow label="Media">{fileNode.mime_type || "Unknown"}</DetailRow>
            <DetailRow label="Byte span">{fileNode.byte_span_start ?? "?"}–{fileNode.byte_span_end ?? "?"}</DetailRow>
            {fileNode.sha256 && <DetailRow label="Node SHA-256"><span className="break-all font-mono text-xs">{fileNode.sha256}</span></DetailRow>}
          </dl>
        </section>
      )}

      <section aria-labelledby={`promotion-${item.id}`} className="space-y-2">
        <h3 id={`promotion-${item.id}`} className="font-semibold">Promotion audit</h3>
        <dl className="space-y-2 rounded-md border p-3">
          <DetailRow label="Partition / lane">{promotion.partition_key} / {promotion.knowledge_lane}</DetailRow>
          <DetailRow label="Retrieval ref"><span className="break-all font-mono text-xs">{promotion.retrieval_item_ref}</span></DetailRow>
          <DetailRow label="Content / chunk">{promotion.content_ref || "—"} / {promotion.chunk_ref || "—"}</DetailRow>
          <DetailRow label="Promoted">{promotion.promoted_by} · <time dateTime={promotion.promoted_at}>{readableDate(promotion.promoted_at)}</time></DetailRow>
        </dl>
      </section>
    </div>
  );
}

export function EvidenceDetailDialog({ item }: { item: EvidenceItem }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<EvidenceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  async function loadDetail() {
    const request = ++requestRef.current;
    setLoading(true);
    setDetail(null);
    setError(null);
    try {
      const result = await loadValidatedEvidenceDetail(item);
      if (request !== requestRef.current) return;
      setDetail(result);
    } catch (requestError) {
      if (request !== requestRef.current) return;
      setDetail(null);
      setError(detailError(requestError));
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  }

  function changeOpen(next: boolean) {
    setOpen(next);
    if (next) {
      void loadDetail();
    } else {
      requestRef.current += 1;
      setDetail(null);
      setError(null);
      setLoading(false);
    }
  }

  return (
    <>
      <Button type="button" size="sm" variant="outline" onClick={() => changeOpen(true)}>
        <Eye aria-hidden="true" /> Inspect provenance
      </Button>
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto" aria-busy={loading}>
          <DialogHeader>
            <DialogTitle>Evidence provenance inspection</DialogTitle>
            <DialogDescription>
              Matter-scoped canonical record, H1 custody, source, and promotion details. Private storage paths are not exposed.
            </DialogDescription>
          </DialogHeader>
          {loading ? (
            <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground" role="status">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading exact evidence provenance
            </p>
          ) : error ? (
            <div role="alert" className="space-y-3 rounded-md border border-destructive p-3 text-sm text-destructive">
              <p>{error}</p>
              <Button type="button" size="sm" variant="outline" onClick={() => void loadDetail()}>
                <RefreshCw aria-hidden="true" /> Retry inspection
              </Button>
            </div>
          ) : detail ? (
            <EvidenceDetailContent detail={detail} />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

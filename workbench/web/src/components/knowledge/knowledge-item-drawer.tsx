// Byline: Codex · GPT-5 · 2026-08-18 (authored records and derived chunks split)
"use client";

import { AppLink as Link } from "@/lib/router-compat";
import { FileText, Fingerprint, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { KnowledgeChunk, KnowledgeItemDetail, KnowledgeRecord } from "@/lib/shared/types";

interface KnowledgeItemDrawerProps {
  detail: KnowledgeItemDetail | null;
  loading: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function optionalText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function recordLabel(record: KnowledgeRecord, index: number) {
  const attrs = record.attrs ?? {};
  const chunkIndex = attrs.chunk_index ?? attrs.chunk_idx ?? attrs.index;
  return chunkIndex !== undefined && chunkIndex !== null
    ? `Chunk ${String(chunkIndex)}`
    : `Record ${index + 1}`;
}

function RecordCard({ record, index }: { record: KnowledgeRecord; index: number }) {
  const attrs = record.attrs ?? {};
  const chunkId = optionalText(attrs.chunk_id) ?? optionalText(attrs.chunk_ref);
  return (
    <article className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">{recordLabel(record, index)}</span>
        <Badge variant="outline">{record.record_type}</Badge>
        <Badge variant="secondary">{record.domain}</Badge>
        <Badge variant="outline">{record.disclosure_tier}</Badge>
        <Badge variant="outline">{record.source_kind.replaceAll("_", " ")}</Badge>
      </div>

      <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <div>
          <dt className="font-medium text-foreground">Record ID</dt>
          <dd className="break-all font-mono">{record.record_id}</dd>
        </div>
        {chunkId && (
          <div>
            <dt className="font-medium text-foreground">Chunk ID</dt>
            <dd className="break-all font-mono">{chunkId}</dd>
          </div>
        )}
        <div>
          <dt className="font-medium text-foreground">Knowledge time</dt>
          <dd>{record.knowledge_time || "not recorded"}</dd>
        </div>
        <div>
          <dt className="font-medium text-foreground">Occurred at</dt>
          <dd>{record.occurred_at || "not recorded"}</dd>
        </div>
      </dl>

      {record.third_party_conversation && (
        <div className="rounded-md border p-3 text-xs">
          <p>Actual sender: {record.third_party_conversation.actual_sender || "not established"}</p>
          <p>Actual recipients: {record.third_party_conversation.actual_recipients.join(", ") || "not established"}</p>
          <p>Source available: {record.source_available_from || "not approved / unavailable"}</p>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        {record.realization_events.length} linked realization event{record.realization_events.length === 1 ? "" : "s"}
      </p>

      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-muted/30 p-3 text-xs leading-5">
        {record.content}
      </pre>

      <details>
        <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
          Raw metadata and provenance
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">
          {JSON.stringify(
            {
              source: record.source,
              source_ref: record.source_ref,
              source_sha256: record.source_sha256,
              conversation_id: record.conversation_id,
              role: record.role,
              participants: record.participants,
              created_at: record.created_at,
              attrs,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </article>
  );
}

function ChunkCard({ chunk }: { chunk: KnowledgeChunk }) {
  return (
    <article className="space-y-2 rounded-lg border border-dashed p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">derived chunk {chunk.chunk_index}</Badge>
        <span className="font-mono text-xs text-muted-foreground">lineage: {chunk.normalized_record_id}</span>
      </div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/30 p-3 text-xs">{chunk.content}</pre>
      <p className="text-xs text-muted-foreground">Read-only · {chunk.chunker_id} · {chunk.content_sha256}</p>
    </article>
  );
}

export function KnowledgeItemDrawer({ detail, loading, open, onOpenChange }: KnowledgeItemDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>{detail?.source_name || detail?.source_ref || "Canonical knowledge source"}</SheetTitle>
          <SheetDescription>
            Canonical PostgreSQL records and custody provenance. This read-only view is not a vector projection.
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading canonical records…
          </div>
        ) : !detail ? (
          <p className="px-4 text-sm text-muted-foreground">No item detail loaded.</p>
        ) : (
          <div className="space-y-5 px-4 pb-6">
            <section className="space-y-3 rounded-lg border bg-muted/10 p-4">
              <div className="flex flex-wrap gap-2">
                {detail.lane && <Badge variant="outline">lane: {detail.lane}</Badge>}
                {detail.parser_id && <Badge variant="secondary">parser: {detail.parser_id}</Badge>}
                {detail.chunker_id && <Badge variant="secondary">chunker: {detail.chunker_id}</Badge>}
                <Badge variant="outline">{detail.record_count} authored records</Badge>
                <Badge variant="outline">{detail.chunk_count} derived chunks</Badge>
              </div>
              <dl className="grid gap-3 text-xs sm:grid-cols-2">
                <div>
                  <dt className="font-medium">Matter</dt>
                  <dd className="break-all font-mono text-muted-foreground">{detail.matter_id}</dd>
                </div>
                <div>
                  <dt className="font-medium">Artifact ID</dt>
                  <dd className="break-all font-mono text-muted-foreground">{detail.artifact_id}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="flex items-center gap-1 font-medium">
                    <Fingerprint className="size-3.5" aria-hidden="true" /> Source SHA-256
                  </dt>
                  <dd className="break-all font-mono text-muted-foreground">{detail.source_sha256}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="font-medium">Source path / custody reference</dt>
                  <dd className="break-all font-mono text-muted-foreground">
                    {detail.source_path || detail.source_ref}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">Authored normalized records</h3>
                  <p className="text-xs text-muted-foreground">
                    Raw metadata is inspectable here. Edits remain on the governed attrs-only curation route.
                  </p>
                </div>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/records?artifact_id=${encodeURIComponent(detail.artifact_id)}`}>
                    Open governed metadata editor
                  </Link>
                </Button>
              </div>
              {detail.records.length === 0 ? (
                <p className="rounded-lg border p-4 text-sm text-muted-foreground">No records returned.</p>
              ) : (
                detail.records.map((record, index) => (
                  <RecordCard key={record.record_id} record={record} index={index} />
                ))
              )}
            </section>

            <section className="space-y-3">
              <h3 className="font-semibold">Derived chunks</h3>
              <p className="text-xs text-muted-foreground">Rebuildable, read-only retrieval material linked to its normalized source record.</p>
              {detail.chunks.length === 0 ? (
                <p className="rounded-lg border p-4 text-sm text-muted-foreground">No derived chunks returned.</p>
              ) : detail.chunks.map((chunk) => <ChunkCard key={chunk.chunk_id} chunk={chunk} />)}
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

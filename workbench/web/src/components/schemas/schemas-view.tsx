// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3 schema inspection views)
// Byline: Codex · GPT-5 · 2026-08-16 (PostgreSQL + Weaviate Data Explorer)
// Byline: Codex · GPT-5 · 2026-08-18 (authored, derived, and audit-control authority labels)
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Database, Eye, RefreshCw, Waypoints } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, getSchemas, getTableDetail, getWeaviateDetail } from "@/lib/api-client";
import type {
  PgSchemaName,
  SchemaTable,
  SchemasResponse,
  TableDetail,
  WeaviateCollection,
  WeaviateDetail,
} from "@/lib/shared/types";

const PG_SCHEMAS: PgSchemaName[] = ["evidence", "working", "analysis", "reference", "ops"];

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
      {message}
    </div>
  );
}

function jsonCell(value: unknown) {
  if (value === null || value === undefined) return "null";
  return typeof value === "string" ? value : JSON.stringify(value);
}

interface PgTableRowProps {
  schema: PgSchemaName;
  table: SchemaTable;
  onInspect: (schema: PgSchemaName, table: string) => void;
}

function PgTableRow({ schema, table, onInspect }: PgTableRowProps) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <TableRow>
        <TableCell className="w-8">
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label={`${expanded ? "Collapse" : "Expand"} ${schema}.${table.table}`}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </Button>
        </TableCell>
        <TableCell className="font-mono text-sm">{table.table}</TableCell>
        <TableCell><Badge variant={table.authority === "authored" ? "secondary" : "outline"}>{table.authority}</Badge></TableCell>
        <TableCell className="text-right text-sm text-muted-foreground">
          {table.row_count_is_estimate ? "≈" : ""}{table.row_count.toLocaleString()} rows
        </TableCell>
        <TableCell className="text-right text-xs text-muted-foreground">{table.columns.length} columns</TableCell>
        <TableCell className="text-right">
          <Button type="button" size="sm" variant="outline" onClick={() => onInspect(schema, table.table)}>
            <Eye className="size-4" aria-hidden="true" /> Inspect
          </Button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={6} className="bg-muted/20">
            <div className="flex flex-wrap gap-1.5 py-1">
              {table.columns.map((column) => (
                <Badge key={column.name} variant="outline" className="font-mono text-xs">
                  {column.name}: {column.type}
                </Badge>
              ))}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function PgSection({ pg, onInspect }: { pg?: SchemasResponse["pg"]; onInspect: PgTableRowProps["onInspect"] }) {
  if (!pg) return <ErrorCard message="No PostgreSQL schema data returned." />;
  if (pg.error) return <ErrorCard message={pg.error} />;
  return (
    <div className="space-y-7">
      {PG_SCHEMAS.map((schema) => (
        <section key={schema}>
          <h3 className="mb-2 font-mono text-sm font-semibold">{schema}</h3>
          {(pg[schema] ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No tables reported.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Table</TableHead>
                  <TableHead>Authority</TableHead>
                  <TableHead className="text-right">Rows</TableHead>
                  <TableHead className="text-right">Columns</TableHead>
                  <TableHead className="text-right">Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(pg[schema] ?? []).map((table) => (
                  <PgTableRow key={table.table} schema={schema} table={table} onInspect={onInspect} />
                ))}
              </TableBody>
            </Table>
          )}
        </section>
      ))}
    </div>
  );
}

function WeaviateCard({ collection, onInspect }: { collection: WeaviateCollection; onInspect: (name: string) => void }) {
  return (
    <article className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-sm font-medium">{collection.name}</p>
          {collection.description && <p className="mt-1 text-xs text-muted-foreground">{collection.description}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{collection.num_entities?.toLocaleString() ?? "unknown"} objects</Badge>
          {collection.vector_index_type && <Badge variant="secondary">index: {collection.vector_index_type}</Badge>}
          <Button type="button" size="sm" variant="outline" onClick={() => onInspect(collection.name)}>
            <Waypoints className="size-4" aria-hidden="true" /> Inspect vectors
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {collection.fields.map((field) => (
          <Badge key={field.name} variant="outline" className="font-mono text-xs">
            {field.name}: {field.type}
            {field.index_filterable ? " · filterable" : ""}
            {field.index_searchable ? " · searchable" : ""}
          </Badge>
        ))}
      </div>
      {(collection.vectorizer || collection.named_vectors || collection.vector_index_config) && (
        <details>
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Vector configuration</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">
            {JSON.stringify(
              {
                vectorizer: collection.vectorizer,
                vector_index_type: collection.vector_index_type,
                vector_index_config: collection.vector_index_config,
                named_vectors: collection.named_vectors,
              },
              null,
              2,
            )}
          </pre>
        </details>
      )}
    </article>
  );
}

function TableDrawer({ detail, open, onOpenChange }: { detail: TableDetail | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  const rowColumns = detail?.rows[0] ? Object.keys(detail.rows[0]) : [];
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-5xl">
        <SheetHeader>
          <SheetTitle className="font-mono">{detail ? `${detail.schema}.${detail.table}` : "PostgreSQL table"}</SheetTitle>
          <SheetDescription>Read-only bounded row and field preview. Authority is classified per table.</SheetDescription>
        </SheetHeader>
        {detail && (
          <div className="space-y-5 px-4 pb-6">
            <div><Badge variant={detail.authority === "authored" ? "secondary" : "outline"}>{detail.authority}</Badge></div>
            <section>
              <h3 className="mb-2 text-sm font-semibold">Columns</h3>
              <div className="flex flex-wrap gap-2">
                {detail.columns.map((column) => (
                  <Badge key={column.name} variant="outline" className="font-mono text-xs">
                    {column.name}: {column.database_type}{column.nullable ? " · nullable" : " · required"}
                  </Badge>
                ))}
              </div>
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold">Indexes</h3>
              {detail.indexes.length === 0 ? <p className="text-sm text-muted-foreground">No indexes reported.</p> : detail.indexes.map((index) => (
                <details key={index.name} className="rounded-md border p-3">
                  <summary className="cursor-pointer font-mono text-xs">{index.name}</summary>
                  <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">{index.definition}</pre>
                </details>
              ))}
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold">Row samples</h3>
              {detail.rows.length === 0 ? <p className="text-sm text-muted-foreground">No rows returned.</p> : (
                <div className="overflow-auto rounded-md border">
                  <Table>
                    <TableHeader><TableRow>{rowColumns.map((column) => <TableHead key={column} className="font-mono text-xs">{column}</TableHead>)}</TableRow></TableHeader>
                    <TableBody>{detail.rows.map((row, index) => (
                      <TableRow key={index}>{rowColumns.map((column) => (
                        <TableCell key={column} className="max-w-80 align-top font-mono text-xs">
                          <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words">{jsonCell(row[column])}</pre>
                        </TableCell>
                      ))}</TableRow>
                    ))}</TableBody>
                  </Table>
                </div>
              )}
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function VectorDrawer({ detail, open, onOpenChange }: { detail: WeaviateDetail | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-4xl">
        <SheetHeader>
          <SheetTitle className="font-mono">{detail?.collection || "Weaviate collection"}</SheetTitle>
          <SheetDescription>Projection metadata and short vector previews. This is supplemental recall, not authority.</SheetDescription>
        </SheetHeader>
        {detail && (
          <div className="space-y-4 px-4 pb-6">
            {detail.objects.length === 0 ? <p className="text-sm text-muted-foreground">No objects returned.</p> : detail.objects.map((object) => (
              <article key={object.uuid} className="space-y-3 rounded-lg border p-4">
                <p className="break-all font-mono text-xs">{object.uuid}</p>
                {object.vectors.map((vector) => (
                  <div key={vector.name} className="rounded-md bg-muted/30 p-3">
                    <div className="mb-2 flex gap-2">
                      <Badge variant="secondary">{vector.name}</Badge>
                      <Badge variant="outline">{vector.dimensions} dimensions</Badge>
                    </div>
                    <pre className="overflow-auto whitespace-pre-wrap text-xs">[{vector.preview.join(", ")}{vector.truncated ? ", …" : ""}]</pre>
                  </div>
                ))}
                <details>
                  <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Object properties</summary>
                  <pre className="mt-2 max-h-72 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">{JSON.stringify(object.properties, null, 2)}</pre>
                </details>
              </article>
            ))}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function SchemasView() {
  const [data, setData] = useState<SchemasResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [tableDetail, setTableDetail] = useState<TableDetail | null>(null);
  const [tableOpen, setTableOpen] = useState(false);
  const [vectorDetail, setVectorDetail] = useState<WeaviateDetail | null>(null);
  const [vectorOpen, setVectorOpen] = useState(false);

  const fetchSchemas = () => {
    setLoading(true);
    getSchemas()
      .then(setData)
      .catch((error) => {
        setData(null);
        toast.error(error instanceof ApiError ? error.message : "Failed to load Data Explorer");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    queueMicrotask(fetchSchemas);
  }, []);

  async function inspectTable(schema: PgSchemaName, table: string) {
    try {
      setTableDetail(await getTableDetail(schema, table));
      setTableOpen(true);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to inspect PostgreSQL table");
    }
  }

  async function inspectVectors(collection: string) {
    try {
      setVectorDetail(await getWeaviateDetail(collection));
      setVectorOpen(true);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to inspect Weaviate vectors");
    }
  }

  const weaviateError = data?.weaviate && !Array.isArray(data.weaviate) ? data.weaviate.error : null;
  const collections = data?.weaviate && Array.isArray(data.weaviate) ? data.weaviate : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge>PostgreSQL · mixed authority</Badge>
          <Badge variant="outline">Weaviate · projection, not authority</Badge>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm"><Link href="/knowledge">Open sources and chunks</Link></Button>
          <Button variant="outline" size="sm" onClick={fetchSchemas}><RefreshCw className="size-4" /> Refresh</Button>
        </div>
      </div>

      {loading && !data ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-10 w-full" />)}</div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Database className="size-5" /> PostgreSQL tables</CardTitle>
              <CardDescription>Authored, derived, and audit/control tables with columns, indexes, and bounded read-only row previews.</CardDescription>
            </CardHeader>
            <CardContent><PgSection pg={data?.pg} onInspect={(schema, table) => void inspectTable(schema, table)} /></CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Waypoints className="size-5" /> Weaviate vectors</CardTitle>
              <CardDescription>Collection metadata and bounded vector previews for supplemental recall projections.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {weaviateError ? <ErrorCard message={weaviateError} /> : collections.length === 0 ? (
                <p className="text-sm text-muted-foreground">No Weaviate collections reported.</p>
              ) : collections.map((collection) => (
                <WeaviateCard key={collection.name} collection={collection} onInspect={(name) => void inspectVectors(name)} />
              ))}
            </CardContent>
          </Card>
        </>
      )}

      <TableDrawer detail={tableDetail} open={tableOpen} onOpenChange={setTableOpen} />
      <VectorDrawer detail={vectorDetail} open={vectorOpen} onOpenChange={setVectorOpen} />
    </div>
  );
}

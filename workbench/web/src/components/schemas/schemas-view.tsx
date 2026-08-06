// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: raw PG/Milvus schema inspection views)
"use client";

/**
 * GET /api/schemas — PG section (evidence/analysis tables, row counts,
 * expandable columns) + Milvus section (collections, entities, dims).
 * Each top-level section can independently carry `{error}` per the C3
 * contract (a down Milvus must not block the PG section from rendering,
 * and vice versa) — this view renders whichever sections came back healthy
 * and shows an inline error card for whichever didn't.
 */
import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, getSchemas } from "@/lib/api-client";
import type { MilvusCollection, SchemaTable, SchemasResponse } from "@/lib/shared/types";

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
      {message}
    </div>
  );
}

function PgTableRow({ table }: { table: SchemaTable }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <TableRow className="cursor-pointer" onClick={() => setExpanded((e) => !e)}>
        <TableCell className="w-6">
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </TableCell>
        <TableCell className="font-mono text-sm">{table.table}</TableCell>
        <TableCell className="text-right text-sm text-muted-foreground">
          {table.rows.toLocaleString()} rows
        </TableCell>
        <TableCell className="text-right text-xs text-muted-foreground">
          {table.columns.length} columns
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={4} className="bg-muted/20">
            <div className="flex flex-wrap gap-1.5 py-1">
              {table.columns.map((col) => (
                <Badge key={col.name} variant="outline" className="font-mono text-xs">
                  {col.name}: {col.type}
                </Badge>
              ))}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function PgSection({ pg }: { pg: SchemasResponse["pg"] | undefined }) {
  if (!pg) return <ErrorCard message="No PG schema data returned." />;
  if (pg.error) return <ErrorCard message={pg.error} />;

  const sections: Array<{ key: "evidence" | "analysis"; label: string }> = [
    { key: "evidence", label: "evidence" },
    { key: "analysis", label: "analysis" },
  ];

  return (
    <div className="space-y-6">
      {sections.map(({ key, label }) => (
        <div key={key}>
          <h3 className="mb-2 text-sm font-semibold capitalize">{label} schema</h3>
          {(pg[key] ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No tables reported.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-6" />
                  <TableHead>Table</TableHead>
                  <TableHead className="text-right">Rows</TableHead>
                  <TableHead className="text-right">Columns</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pg[key].map((table) => (
                  <PgTableRow key={table.table} table={table} />
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      ))}
    </div>
  );
}

function MilvusCollectionCard({ collection }: { collection: MilvusCollection }) {
  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-medium">{collection.name}</span>
        <Badge variant="outline">{collection.num_entities.toLocaleString()} entities</Badge>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {collection.fields.map((field) => (
          <Badge key={field.name} variant="secondary" className="font-mono text-xs">
            {field.name}: {field.type}
            {field.dim !== undefined ? ` (${field.dim}d)` : ""}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function MilvusSection({ milvus }: { milvus: SchemasResponse["milvus"] | undefined }) {
  if (!milvus) return <ErrorCard message="No Milvus schema data returned." />;
  if (milvus.error) return <ErrorCard message={milvus.error} />;
  const collections = milvus.collections ?? [];
  if (collections.length === 0) {
    return <p className="text-sm text-muted-foreground">No collections reported.</p>;
  }
  return (
    <div className="space-y-2">
      {collections.map((c) => (
        <MilvusCollectionCard key={c.name} collection={c} />
      ))}
    </div>
  );
}

export function SchemasView() {
  const [data, setData] = useState<SchemasResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSchemas = () => {
    setLoading(true);
    getSchemas()
      .then(setData)
      .catch((err) => {
        setData(null);
        toast.error(err instanceof ApiError ? err.message : "Failed to load schemas");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    queueMicrotask(fetchSchemas);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={fetchSchemas}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {loading && !data ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>PostgreSQL</CardTitle>
            </CardHeader>
            <CardContent>
              <PgSection pg={data?.pg} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Milvus</CardTitle>
            </CardHeader>
            <CardContent>
              <MilvusSection milvus={data?.milvus} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

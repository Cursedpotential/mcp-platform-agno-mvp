// Surreal projection proof + official Studio launcher.
// Byline: Codex · GPT-5 · 2026-08-16

import { ArrowUpRight, Database, LockKeyhole, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const connectionProfile = {
  application: "data-surreal-phase1-t0-r1",
  namespace: "phase1_surreal",
  database: "t0_slice_r1",
  context: "phase1_surreal_t0_slice_r1",
  corpus: "T0 synthetic only",
};

export default function SurrealProjectionPage() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">Disposable Phase 1</Badge>
          <Badge variant="secondary">projection, not authority</Badge>
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Surreal projection</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Inspect the isolated Horizon T0 projection and open the official SurrealDB Studio
            operator surface. PostgreSQL remains canonical; this pane never promotes evidence or
            replaces Graphiti.
          </p>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-4 w-4" /> Connection profile
            </CardTitle>
            <CardDescription>
              Safe coordinates are visible; credentials and tokens are intentionally absent.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {Object.entries(connectionProfile).map(([key, value]) => (
                <div key={key} className="rounded-lg border bg-muted/30 p-3">
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">{key}</dt>
                  <dd className="mt-1 break-all font-mono text-xs">{value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <LockKeyhole className="h-4 w-4" /> SurrealDB Studio
            </CardTitle>
            <CardDescription>The current official GUI, opened outside Workbench.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              The database has no public port. Studio access requires a separately authenticated,
              temporary operator tunnel; Workbench does not reveal or persist that credential.
            </p>
            <a
              href="https://studio.surrealdb.com"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Open SurrealDB Studio <ArrowUpRight className="h-4 w-4" />
            </a>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" /> Horizon proof boundary
          </CardTitle>
          <CardDescription>
            The live evaluation report is attached after the one-shot synthetic run completes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 text-sm md:grid-cols-4">
            <Proof label="Target" value="Isolated / synthetic" />
            <Proof label="Retrieval" value="HorizonContext bound" />
            <Proof label="Ranking" value="Exact filtered cosine" />
            <Proof label="Failure" value="Seal + linked rewalk" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Proof({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}

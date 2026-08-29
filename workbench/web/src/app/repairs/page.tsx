"use client";
// Byline: Codex · GPT-5 · 2026-08-03

import { useEffect, useState } from "react";
import { AlertTriangle, Bot, Loader2, Play, RefreshCw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  executeRepairTool,
  listRepairParticipants,
  listRepairTools,
  runRepairAgentReview,
  runAutomaticRepairAssessment,
  type RepairParticipant,
  type RepairToolCard,
} from "@/lib/api-client";

export default function RepairsPage() {
  const [tools, setTools] = useState<RepairToolCard[]>([]);
  const [participants, setParticipants] = useState<RepairParticipant[]>([]);
  const [participantId, setParticipantId] = useState("");
  const [agentTask, setAgentTask] = useState("Review this source and recommend the safest processing path.");
  const [selected, setSelected] = useState<string>("");
  const [path, setPath] = useState("");
  const [payloadText, setPayloadText] = useState('{\n  "path": ""\n}');
  const [approved, setApproved] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const cards = await listRepairTools();
      setTools(cards);
      if (!selected && cards.length) setSelected(cards[0].id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load repair tools");
    }
  };

  useEffect(() => {
    let active = true;
    Promise.all([listRepairTools(), listRepairParticipants()])
      .then(([cards, roster]) => {
        if (!active) return;
        setTools(cards);
        setSelected((current) => current || cards[0]?.id || "");
        setParticipants(roster);
        const preferred = roster.find((item) => item.id === "ingestion-orchestrator") ?? roster.find((item) => item.recommended) ?? roster[0];
        setParticipantId((current) => current || (preferred ? `${preferred.type}:${preferred.id}` : ""));
      })
      .catch((error) => {
        if (active) toast.error(error instanceof Error ? error.message : "Could not load repair tools");
      });
    return () => { active = false; };
  }, []);

  const selectedTool = tools.find((tool) => tool.id === selected);
  const selectedParticipant = participants.find((item) => `${item.type}:${item.id}` === participantId || item.id === participantId);

  const assess = async () => {
    if (!path.trim()) return toast.error("Enter a server-visible evidence path");
    setBusy(true);
    try {
      setResult(await runAutomaticRepairAssessment(path.trim()));
      toast.success("Assessment complete — no source was modified");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Assessment failed");
    } finally { setBusy(false); }
  };

  const execute = async () => {
    setBusy(true);
    try {
      const payload = JSON.parse(payloadText) as Record<string, unknown>;
      setResult(await executeRepairTool(selected, payload, approved));
      toast.success(`${selected} completed`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Repair call failed");
    } finally { setBusy(false); }
  };

  const askAgent = async () => {
    if (!path.trim()) return toast.error("Enter a server-visible evidence path");
    if (!selectedParticipant) return toast.error("Select a live Platform participant");
    setBusy(true);
    try {
      setResult(await runRepairAgentReview({
        participant: selectedParticipant,
        path: path.trim(),
        task: agentTask,
        assessment: result && typeof result === "object" ? result as Record<string, unknown> : undefined,
      }));
      toast.success(`${selectedParticipant.name} completed its review`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Agent review failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Repair Lab</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Inspect damaged evidence, create separately hashed derivatives, and retain custody originals.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5" />Automatic assessment</CardTitle>
          <CardDescription>Runs detection, streaming preview, and applicable PDF inspection. It never writes, hydrates, or quarantines.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Input value={path} onChange={(event) => setPath(event.target.value)} placeholder="Server-visible custody or staging path" />
          <Button onClick={assess} disabled={busy}><Play />Assess</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Bot className="h-5 w-5" />Agent-assisted processing</CardTitle>
          <CardDescription>Live Platform agents and teams can inspect, compare, and propose actions. Writes remain operator-approved.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[minmax(220px,0.7fr)_minmax(0,1.3fr)_auto]">
          <select value={participantId} onChange={(event) => setParticipantId(event.target.value)} className="h-9 rounded-md border bg-background px-3 text-sm">
            {participants.map((participant) => <option key={`${participant.type}:${participant.id}`} value={`${participant.type}:${participant.id}`}>{participant.recommended ? "★ " : ""}{participant.name} ({participant.type})</option>)}
          </select>
          <Input value={agentTask} onChange={(event) => setAgentTask(event.target.value)} aria-label="Agent review task" />
          <Button onClick={askAgent} disabled={busy || !selectedParticipant}><Bot />Ask agent</Button>
          {selectedParticipant && <p className="text-xs text-muted-foreground md:col-span-3">{selectedParticipant.role || "No role description returned by the Platform."}</p>}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.2fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">Registered tools<Button variant="ghost" size="icon-sm" onClick={load}><RefreshCw /></Button></CardTitle>
            <CardDescription>Every repair operation registered in the Platform.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {tools.map((tool) => (
              <button key={tool.id} onClick={() => { setSelected(tool.id); setApproved(false); }}
                className={`w-full rounded-md border p-3 text-left ${selected === tool.id ? "border-primary bg-accent" : "hover:bg-accent/50"}`}>
                <div className="font-mono text-sm font-medium">{tool.id}</div>
                <div className="mt-1 text-xs text-muted-foreground">{tool.description}</div>
                <div className="mt-2 flex flex-wrap gap-1">
                  <Badge variant="outline">{tool.side_effect}</Badge>
                  <Badge variant={tool.execution_policy === "manual_approval_required" ? "destructive" : "secondary"}>{tool.execution_policy}</Badge>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Manual execution</CardTitle>
            <CardDescription>{selectedTool?.description || "Select a registered repair tool."}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><Label htmlFor="repair-payload">Payload (JSON)</Label><Textarea id="repair-payload" className="min-h-56 font-mono" value={payloadText} onChange={(event) => setPayloadText(event.target.value)} /></div>
            {selectedTool?.execution_policy === "manual_approval_required" && (
              <label className="flex items-start gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
                <input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} className="mt-1" />
                <span><strong>Explicit approval required.</strong> The quarantine tool only creates a verified copy inside <code>to_be_deleted</code>; it retains the original.</span>
              </label>
            )}
            <Button onClick={execute} disabled={busy || !selected || (selectedTool?.execution_policy === "manual_approval_required" && !approved)}>
              {busy ? <Loader2 className="animate-spin" /> : <AlertTriangle />}{busy ? "Running…" : "Run selected tool"}
            </Button>
          </CardContent>
        </Card>
      </div>

      {result !== null && <Card><CardHeader><CardTitle>Operation result</CardTitle><CardDescription>Includes operation ID, mode, timestamps, step outcomes, and tool output.</CardDescription></CardHeader><CardContent><pre className="max-h-[36rem] overflow-auto rounded-md bg-muted p-4 text-xs">{JSON.stringify(result, null, 2)}</pre></CardContent></Card>}
    </div>
  );
}

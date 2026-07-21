// Byline: Claude Code · Sonnet (agent) · 2026-07-21
"use client";

import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopilotMessageList, type CopilotMessage } from "./copilot-message-list";
import { CopilotComposer } from "./copilot-composer";
import {
  copilotAsk,
  copilotContinue,
  copilotModels,
  copilotPresets,
  type CopilotContext,
  type CopilotModelGroup,
  type CopilotPreset,
} from "@/lib/copilot-client";
import { listFiles, listRuns, ApiError } from "@/lib/api-client";
import type { RunSummary, StagedFile } from "@/lib/shared/types";

export function CopilotChat() {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [modelGroups, setModelGroups] = useState<CopilotModelGroup[]>([]);
  const [model, setModel] = useState("");
  const [presets, setPresets] = useState<CopilotPreset[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [attachPage, setAttachPage] = useState("");
  const [attachRunId, setAttachRunId] = useState("");
  const [attachFileId, setAttachFileId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    copilotModels()
      .then((groups) => {
        setModelGroups(groups);
        const first = groups[0]?.models[0];
        if (first && groups[0]) setModel(`${groups[0].provider}/${first}`);
      })
      .catch(() => setModelGroups([]));
    copilotPresets()
      .then(setPresets)
      .catch(() => setPresets([]));
    listRuns({ limit: 20 })
      .then(setRuns)
      .catch(() => setRuns([]));
    listFiles()
      .then(setFiles)
      .catch(() => setFiles([]));
  }, []);

  const buildContext = (): CopilotContext | undefined => {
    if (!attachPage && !attachRunId && !attachFileId) return undefined;
    return {
      page: (attachPage || null) as CopilotContext["page"],
      run_id: attachRunId || null,
      file_id: attachFileId || null,
    };
  };

  const handleSend = async (prompt: string) => {
    if (!prompt.trim() || loading) return;
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: prompt }]);
    setLoading(true);
    try {
      const modelParam = model || undefined;
      const response = sessionId
        ? await copilotContinue({ sessionId, prompt, model: modelParam })
        : await copilotAsk({ prompt, model: modelParam, context: buildContext() });
      setSessionId(response.session_id);
      setMessages((prev) => [...prev, { role: "assistant", text: response.reply }]);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Copilot request failed";
      setError(message);
      setMessages((prev) => [...prev, { role: "assistant", text: `[error] ${message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setError(null);
  };

  return (
    <div className="grid flex-1 gap-4 lg:grid-cols-[1fr_280px]">
      <Card className="flex min-h-[60vh] flex-col">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Chat</CardTitle>
            <Button variant="outline" size="sm" onClick={handleNewChat} disabled={!messages.length}>
              <RotateCcw className="h-3.5 w-3.5" />
              New chat
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col gap-4">
          <CopilotMessageList messages={messages} loading={loading} />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <CopilotComposer presets={presets} onSend={handleSend} disabled={loading} />
        </CardContent>
      </Card>

      <Card className="h-fit">
        <CardHeader>
          <CardTitle className="text-sm">Session</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Model
            </label>
            <select
              className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {modelGroups.length === 0 && <option value="">(none connected)</option>}
              {modelGroups.map((group) => (
                <optgroup key={group.provider} label={group.label}>
                  {group.models.map((m) => (
                    <option key={m} value={`${group.provider}/${m}`}>
                      {m}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Attach context{sessionId ? " (first message only)" : ""}
            </label>
            <select
              className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
              value={attachPage}
              disabled={!!sessionId}
              onChange={(e) => setAttachPage(e.target.value)}
            >
              <option value="">No page context</option>
              <option value="runs">Runs page</option>
              <option value="intake">Intake page</option>
              <option value="tools">Tools page</option>
            </select>
            <select
              className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
              value={attachRunId}
              disabled={!!sessionId}
              onChange={(e) => setAttachRunId(e.target.value)}
            >
              <option value="">No run attached</option>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.slice(0, 8)} · {r.workflow} · {r.status}
                </option>
              ))}
            </select>
            <select
              className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
              value={attachFileId}
              disabled={!!sessionId}
              onChange={(e) => setAttachFileId(e.target.value)}
            >
              <option value="">No file attached</option>
              {files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

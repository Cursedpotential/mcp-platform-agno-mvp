// Byline: Claude Code · Sonnet (agent) · 2026-07-21
// Byline: Codex · GPT-5 · 2026-08-16 (Vercel AI SDK + neutral Portkey stream)
"use client";

import { useEffect, useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { TextStreamChatTransport, type UIMessage } from "ai";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CopilotMessageList, type CopilotMessage } from "./copilot-message-list";
import { CopilotComposer } from "./copilot-composer";
import {
  copilotPresets,
  type CopilotContext,
  type CopilotPreset,
} from "@/lib/copilot-client";
import { listFiles, listRuns } from "@/lib/api-client";
import type { RunSummary, StagedFile } from "@/lib/shared/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function messageText(message: UIMessage): string {
  return message.parts
    .filter((part): part is Extract<(typeof message.parts)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("");
}

export function CopilotChat() {
  const transport = useMemo(
    () =>
      new TextStreamChatTransport({
        api: `${API_BASE}/v1/chat`,
        credentials: "same-origin",
      }),
    [],
  );
  const { messages, sendMessage, setMessages, status, error, stop } = useChat({ transport });
  const [model, setModel] = useState("");
  const [presets, setPresets] = useState<CopilotPreset[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [attachPage, setAttachPage] = useState("");
  const [attachRunId, setAttachRunId] = useState("");
  const [attachFileId, setAttachFileId] = useState("");
  const loading = status === "submitted" || status === "streaming";
  const displayMessages: CopilotMessage[] = messages
    .filter(
      (message): message is UIMessage & { role: "user" | "assistant" } =>
        message.role === "user" || message.role === "assistant",
    )
    .map((message) => ({ role: message.role, text: messageText(message) }));

  useEffect(() => {
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
    await sendMessage(
      { text: prompt },
      {
        body: {
          model: model.trim() || null,
          context: buildContext() ?? null,
        },
      },
    );
  };

  const handleNewChat = () => {
    if (loading) stop();
    setMessages([]);
  };

  return (
    <div className="grid flex-1 gap-4 lg:grid-cols-[1fr_280px]">
      <Card className="flex min-h-[60vh] flex-col">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Chat</CardTitle>
            <Button variant="outline" size="sm" onClick={handleNewChat} disabled={!messages.length && !loading}>
              <RotateCcw className="h-3.5 w-3.5" />
              New chat
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col gap-4">
          <CopilotMessageList messages={displayMessages} loading={loading} />
          {error && <p className="text-sm text-destructive">{error.message}</p>}
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
            <Input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Portkey config default"
            />
            <p className="text-[10px] text-muted-foreground">
              Portkey owns fallback, tracing, and audit. Leave blank to use the saved gateway config.
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Attach context
            </label>
            <select
              className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
              value={attachPage}
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

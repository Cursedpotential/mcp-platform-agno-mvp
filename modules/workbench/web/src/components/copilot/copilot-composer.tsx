// Byline: Claude Code · Sonnet (agent) · 2026-07-21
"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { CopilotPreset } from "@/lib/copilot-client";

/** Preset dropdown + prompt textarea + send button. Picking a preset
 * inserts its prompt text into the textarea (still editable before send) —
 * per the build brief, presets never auto-send. */
export function CopilotComposer({
  presets,
  onSend,
  disabled,
}: {
  presets: CopilotPreset[];
  onSend: (prompt: string) => void;
  disabled: boolean;
}) {
  const [prompt, setPrompt] = useState("");
  const [presetId, setPresetId] = useState("");

  const selectedPreset = presets.find((p) => p.id === presetId);

  const applyPreset = (id: string) => {
    setPresetId(id);
    const preset = presets.find((p) => p.id === id);
    if (preset) setPrompt(preset.prompt);
  };

  const submit = () => {
    if (!prompt.trim() || disabled) return;
    onSend(prompt);
    setPrompt("");
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="rounded-md border bg-transparent px-2 py-1 text-xs"
          value={presetId}
          onChange={(e) => applyPreset(e.target.value)}
        >
          <option value="">Preset prompts…</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        {selectedPreset?.wants_context && (
          <span className="text-[10px] text-muted-foreground">
            attach a {selectedPreset.wants_context} in the Session panel before sending
          </span>
        )}
      </div>
      <Textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Ask the copilot… (Ctrl/Cmd+Enter to send)"
        rows={3}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <div className="flex justify-end">
        <Button size="sm" onClick={submit} disabled={disabled || !prompt.trim()}>
          <Send className="h-3.5 w-3.5" />
          Send
        </Button>
      </div>
    </div>
  );
}

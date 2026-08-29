// Byline: Codex · GPT-5.6 · 2026-08-29
"use client";

import { Activity, Check, Link2, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { PlatformMessageViewer } from "@/components/sbv/platform-message-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  createUIWPreviewEventSource,
  decideUIW,
  getUIWPreview,
  getUIWPreviewMessages,
} from "@/lib/api-client";
import type {
  UIWPreviewEvent,
  UIWPreviewMessage,
  UIWPreviewParticipant,
  UIWPreviewResponse,
} from "@/lib/shared/types";

function initialHandle() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("preview_handle")?.trim() ?? "";
}

export function UIWPreviewClient() {
  const [draftHandle, setDraftHandle] = useState("");
  const [previewHandle, setPreviewHandle] = useState("");
  const [preview, setPreview] = useState<UIWPreviewResponse | null>(null);
  const [messages, setMessages] = useState<UIWPreviewMessage[]>([]);
  const [participants, setParticipants] = useState<UIWPreviewParticipant[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [events, setEvents] = useState<UIWPreviewEvent[]>([]);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [messageError, setMessageError] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesLoaded, setMessagesLoaded] = useState(false);
  const [decisionPending, setDecisionPending] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const generationRef = useRef(0);
  const activeHandleRef = useRef("");
  const snapshotControllerRef = useRef<AbortController | null>(null);
  const messageControllersRef = useRef(new Map<string, AbortController>());
  const requestedCursorsRef = useRef(new Set<string>());

  const activateHandle = useCallback((handle: string) => {
    generationRef.current += 1;
    activeHandleRef.current = handle;
    snapshotControllerRef.current?.abort();
    messageControllersRef.current.forEach((controller) => controller.abort());
    messageControllersRef.current.clear();
    requestedCursorsRef.current.clear();
    setPreview(null);
    setMessages([]);
    setParticipants([]);
    setNextCursor(null);
    setEvents([]);
    setSnapshotError(null);
    setMessageError(null);
    setEventError(null);
    setMessagesLoaded(false);
    setMessagesLoading(false);
    setDecisionPending(false);
    setRejectionReason("");
    setPreviewHandle(handle);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const handle = initialHandle();
      setDraftHandle(handle);
      activateHandle(handle);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activateHandle]);

  const loadSnapshot = useCallback(async () => {
    const handle = previewHandle;
    if (!handle) return;
    const generation = generationRef.current;
    snapshotControllerRef.current?.abort();
    const controller = new AbortController();
    snapshotControllerRef.current = controller;
    try {
      const result = await getUIWPreview(handle, controller.signal);
      if (generation !== generationRef.current || activeHandleRef.current !== handle) return;
      if (result.preview_handle !== handle) throw new Error("Preview snapshot correlation failed");
      setPreview(result);
      setSnapshotError(null);
    } catch (error) {
      if (generation !== generationRef.current || activeHandleRef.current !== handle) return;
      setSnapshotError(error instanceof Error ? error.message : "Preview snapshot is unavailable");
    } finally {
      if (snapshotControllerRef.current === controller) snapshotControllerRef.current = null;
    }
  }, [previewHandle]);

  const loadMessages = useCallback(async (cursor?: string) => {
    const handle = previewHandle;
    if (!handle) return;
    const generation = generationRef.current;
    const cursorKey = cursor ?? "__first__";
    if (requestedCursorsRef.current.has(cursorKey)) return;
    requestedCursorsRef.current.add(cursorKey);
    const controller = new AbortController();
    messageControllersRef.current.set(cursorKey, controller);
    setMessagesLoading(true);
    try {
      const page = await getUIWPreviewMessages(handle, cursor, 100, controller.signal);
      if (generation !== generationRef.current || activeHandleRef.current !== handle) return;
      if (page.preview_handle !== handle) throw new Error("Preview message correlation failed");
      setParticipants((current) => {
        const merged = new Map((cursor ? current : []).map((item) => [item.participant_id, item]));
        page.participants.forEach((item) => merged.set(item.participant_id, item));
        return [...merged.values()];
      });
      setMessages((current) => {
        const merged = new Map((cursor ? current : []).map((item) => [item.message_id, item]));
        page.messages.forEach((item) => merged.set(item.message_id, item));
        return [...merged.values()].sort((left, right) => left.ordinal - right.ordinal);
      });
      setNextCursor(page.next_cursor ?? null);
      setMessageError(null);
      if (!cursor) setMessagesLoaded(true);
    } catch (error) {
      if (generation !== generationRef.current || activeHandleRef.current !== handle) return;
      setMessageError(error instanceof Error ? error.message : "Preview messages are unavailable");
    } finally {
      if (messageControllersRef.current.get(cursorKey) === controller) {
        requestedCursorsRef.current.delete(cursorKey);
        messageControllersRef.current.delete(cursorKey);
      }
      if (generation === generationRef.current && activeHandleRef.current === handle) {
        setMessagesLoading(messageControllersRef.current.size > 0);
      }
    }
  }, [previewHandle]);

  useEffect(() => {
    if (!previewHandle) return;
    const generation = generationRef.current;
    const initialLoad = window.setTimeout(() => {
      void loadSnapshot();
      void loadMessages();
    }, 0);
    const source = createUIWPreviewEventSource(previewHandle);
    const onEvent = (raw: MessageEvent<string>) => {
      try {
        if (generation !== generationRef.current || activeHandleRef.current !== previewHandle) return;
        const event = JSON.parse(raw.data) as UIWPreviewEvent;
        if (event.preview_handle !== previewHandle) throw new Error("Preview event correlation failed");
        setEvents((current) => [...current.filter((item) => item.event_id !== event.event_id), event]
          .sort((left, right) => left.event_id - right.event_id)
          .slice(-100));
        setEventError(null);
        void loadSnapshot();
        if (event.event_type === "messages_available") void loadMessages();
      } catch (error) {
        setEventError(error instanceof Error ? error.message : "Malformed preview event");
        source.close();
      }
    };
    source.addEventListener("uiw.preview", onEvent as EventListener);
    source.onerror = () => {
      if (generation === generationRef.current && activeHandleRef.current === previewHandle) {
        setEventError("The UIW preview event stream is unavailable");
      }
    };
    return () => {
      window.clearTimeout(initialLoad);
      source.close();
      snapshotControllerRef.current?.abort();
      messageControllersRef.current.forEach((controller) => controller.abort());
      messageControllersRef.current.clear();
      requestedCursorsRef.current.clear();
    };
  }, [loadMessages, loadSnapshot, previewHandle]);

  function attach() {
    const handle = draftHandle.trim();
    if (!handle) {
      toast.error("Enter the preview handle returned by intake");
      return;
    }
    activateHandle(handle);
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("preview_handle", handle);
    window.history.replaceState({}, "", url);
  }

  async function decide(approved: boolean) {
    const handle = previewHandle;
    const generation = generationRef.current;
    if (!handle || !decisionEligible) {
      toast.error("Load the correlated messages, provenance, and completed receipts before deciding");
      return;
    }
    if (!approved && !rejectionReason.trim()) {
      toast.error("A rejection requires a reason");
      return;
    }
    setDecisionPending(true);
    try {
      const result = await decideUIW(handle, { approved, reason: approved ? "" : rejectionReason.trim() });
      if (generation !== generationRef.current || activeHandleRef.current !== handle) return;
      if (result.preview_handle !== handle) throw new Error("Decision response correlation failed");
      toast.success(approved ? "Preview approved" : "Preview rejected");
      await loadSnapshot();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Decision failed");
    } finally {
      if (generation === generationRef.current && activeHandleRef.current === handle) {
        setDecisionPending(false);
      }
    }
  }

  const awaitingDecision = preview?.phase === "awaiting_decision";
  const requiredReceiptTypes = useMemo(
    () => ["custody", "parser_selection", "parser_execution", "normalization", "storage", "completeness"] as const,
    [],
  );
  const participantIds = useMemo(
    () => new Set(participants.map((participant) => participant.participant_id)),
    [participants],
  );
  const provenanceLoaded = messages.length > 0 && messages.every((message) =>
    Boolean(message.source_locator_ref) &&
    message.participant_ids.every((id) => participantIds.has(id)) &&
    (!message.sender_participant_id || participantIds.has(message.sender_participant_id)) &&
    message.attachments.every((attachment) => Boolean(attachment.source_locator_ref)),
  );
  const receiptsComplete = requiredReceiptTypes.every((receiptType) =>
    preview?.receipts.some((receipt) => receipt.receipt_type === receiptType && receipt.status === "completed"),
  );
  const decisionEligible = Boolean(
    awaitingDecision &&
    preview?.preview_handle === previewHandle &&
    messagesLoaded &&
    !snapshotError &&
    !messageError &&
    provenanceLoaded &&
    receiptsComplete,
  );

  return (
    <div className="mx-auto w-full max-w-[1680px] space-y-4 p-4 md:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="platform-kicker">Unified operator surface · bounded client</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Pipeline preview</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Watch the durable import workflow and platform messages through one opaque preview boundary.
          </p>
        </div>
        <Badge variant={previewHandle ? "default" : "outline"} className="gap-1.5">
          <Link2 className="size-3" /> {previewHandle ? "Attached" : "Not attached"}
        </Badge>
      </header>

      <Card className="platform-panel">
        <CardHeader className="pb-3"><CardTitle className="text-sm">Attach to an import preview</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="uiw-preview-handle">Preview handle</Label>
            <Input id="uiw-preview-handle" value={draftHandle} onChange={(event) => setDraftHandle(event.target.value)} autoComplete="off" />
          </div>
          <Button onClick={attach} className="gap-2"><Activity className="size-4" /> Open preview</Button>
        </CardContent>
      </Card>

      {!previewHandle ? (
        <div className="platform-panel rounded-md px-5 py-14 text-center">
          <ShieldCheck className="mx-auto size-9 text-muted-foreground" />
          <p className="mt-3 text-sm font-medium">Attach the preview handle returned by intake.</p>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(22rem,0.8fr)]">
          <PlatformMessageViewer
            messages={messages}
            participants={participants}
            loading={messagesLoading}
            error={messageError}
            previewHandle={previewHandle}
            hasMore={Boolean(nextCursor)}
            onLoadMore={() => void loadMessages(nextCursor ?? undefined)}
          />

          <div className="space-y-4">
            <Card className="platform-panel">
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
                <CardTitle className="text-sm">Workflow gate</CardTitle>
                <Button variant="ghost" size="icon-sm" onClick={() => void loadSnapshot()} aria-label="Refresh preview">
                  <RefreshCw className="size-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-3">
                {snapshotError && <p className="text-sm text-destructive" role="alert">{snapshotError}</p>}
                {preview && (
                  <>
                    <Badge variant={awaitingDecision ? "secondary" : "outline"}>{preview.phase}</Badge>
                    <dl className="grid gap-2 text-xs">
                      <div><dt className="text-muted-foreground">Request</dt><dd className="break-all font-mono">{preview.correlation.request_id}</dd></div>
                      <div><dt className="text-muted-foreground">Source version</dt><dd className="break-all font-mono">{preview.correlation.source_version_id}</dd></div>
                      <div><dt className="text-muted-foreground">Raw generation</dt><dd className="break-all font-mono">{preview.correlation.raw_generation_id}</dd></div>
                      <div><dt className="text-muted-foreground">Normalized generation</dt><dd className="break-all font-mono">{preview.correlation.normalized_generation_id}</dd></div>
                      <div><dt className="text-muted-foreground">Preview digest</dt><dd className="break-all font-mono">{preview.preview_digest}</dd></div>
                      <div><dt className="text-muted-foreground">Parser</dt><dd>{preview.parser ? `${preview.parser.parser_id} · ${preview.parser.parser_version}` : "Not selected"}</dd></div>
                    </dl>
                    <ul className="space-y-1 border-t pt-3 text-xs">
                      {preview.receipts.map((receipt) => <li key={receipt.receipt_ref} className="space-y-0.5 border-l-2 pl-2"><div>{receipt.receipt_type} · {receipt.status}</div><div className="break-all font-mono text-[10px] text-muted-foreground">{receipt.receipt_ref}{receipt.digest ? ` · ${receipt.digest}` : ""}</div><time className="text-[10px] text-muted-foreground" dateTime={receipt.recorded_at}>{new Date(receipt.recorded_at).toLocaleString()}</time></li>)}
                    </ul>
                    {awaitingDecision && (
                      <div className="space-y-2 border-t pt-3">
                        <Label htmlFor="uiw-rejection-reason">Rejection reason</Label>
                        <Input id="uiw-rejection-reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} />
                        <div className="flex gap-2">
                          <Button disabled={decisionPending || !decisionEligible} onClick={() => void decide(true)}><Check className="size-4" /> Approve</Button>
                          <Button disabled={decisionPending || !decisionEligible} variant="destructive" onClick={() => void decide(false)}><X className="size-4" /> Reject</Button>
                        </div>
                        {!decisionEligible && <p className="text-xs text-muted-foreground" role="status">Decision locked until this exact preview has normalized messages, participant and attachment provenance, and all required completed receipts.</p>}
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="platform-panel">
              <CardHeader><CardTitle className="text-sm">UIW events</CardTitle></CardHeader>
              <CardContent>
                {eventError && <p className="text-sm text-destructive" role="alert">{eventError}</p>}
                {!eventError && events.length === 0 && <p className="text-sm text-muted-foreground">Waiting for replayable workflow events…</p>}
                <ol className="space-y-2 text-xs">
                  {events.map((event) => <li key={event.event_id} className="border-l-2 pl-2"><span className="font-mono">#{event.event_id}</span> · {event.event_type} · {event.phase}</li>)}
                </ol>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { sha256 as sha256Digest } from "@noble/hashes/sha2.js";
import { bytesToHex } from "@noble/hashes/utils.js";
import {
  ArrowCounterClockwise,
  ArrowRight,
  CaretDown,
  Check,
  CheckCircle,
  CircleNotch,
  Clock,
  FileArrowUp,
  FileText,
  FolderOpen,
  Hash,
  Info,
  Moon,
  ShieldCheck,
  Sun,
  UploadSimple,
  Warning,
} from "@phosphor-icons/react";

const DEMO_NAME = "Rowan_Jeff_to_Rowan_Morgan_sms_export_2026-08-27.txt";
const DEMO_CONTENT = `2026-08-25T08:14:00-04:00 | Jeff Rowan | Hey—can we talk about the school pickup plan for this week?
2026-08-25T08:15:00-04:00 | Morgan Rowan | Sure. I can do pickup on Wed and Fri. Tue is tight with my meeting.
2026-08-25T08:16:00-04:00 | Jeff Rowan | Works for me. I’ll handle Tue. Thanks.
2026-08-26T07:42:00-04:00 | Morgan Rowan | Reminder: Parent-teacher conference is tonight at 6pm.
2026-08-26T07:43:00-04:00 | Jeff Rowan | Got it. I’ll be there.
2026-08-27T09:58:00-04:00 | Morgan Rowan | Can you send the math worksheet he missed?`;

const STEPS = [
  ["Choose files", "Select a source"],
  ["Preview extraction", "Review content and metadata"],
  ["Confirm intake", "Start the simulated run"],
  ["Review results", "Inspect the receipt"],
];

const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} bytes`;
  return `${(bytes / 1024).toFixed(1)} KB`;
};

const formatDate = (value, withTime = true) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "Unknown";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...(withTime && { hour: "numeric", minute: "2-digit" }),
  }).format(date);
};

const formatTime = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(date);
};

function sha256(text) {
  return bytesToHex(sha256Digest(new TextEncoder().encode(text)));
}

function normalizeMessage(message, index) {
  return {
    id: String(message.id ?? index + 1),
    sender: String(message.sender ?? message.address ?? message.from ?? "Unknown participant"),
    body: String(message.body ?? message.message ?? message.text ?? ""),
    occurredAt: String(message.occurredAt ?? message.date ?? message.timestamp ?? new Date(0).toISOString()),
    direction: message.direction ?? (message.type === "2" || message.type === 2 ? "outgoing" : "unknown"),
  };
}

function parseXml(text) {
  const document = new DOMParser().parseFromString(text, "application/xml");
  if (document.querySelector("parsererror")) throw new Error("The XML could not be parsed.");
  const nodes = [...document.querySelectorAll("sms, message")];
  if (!nodes.length) throw new Error("No SMS or message records were found in this XML file.");
  return {
    parser: "SMS XML parser · browser demo",
    messages: nodes.map((node, index) => {
      const rawDate = node.getAttribute("date") ?? node.getAttribute("timestamp");
      const numericDate = Number(rawDate);
      return normalizeMessage(
        {
          id: node.getAttribute("_id") ?? index + 1,
          sender: node.getAttribute("contact_name") ?? node.getAttribute("address") ?? "Unknown participant",
          body: node.getAttribute("body") ?? node.textContent,
          date: Number.isFinite(numericDate) && numericDate > 0 ? new Date(numericDate).toISOString() : rawDate,
          type: node.getAttribute("type"),
        },
        index,
      );
    }),
  };
}

function parseJson(text) {
  const parsed = JSON.parse(text);
  const records = Array.isArray(parsed) ? parsed : parsed.messages;
  if (!Array.isArray(records) || !records.length) throw new Error("No messages array was found in this JSON file.");
  return {
    parser: "Generic JSON message parser · browser demo",
    messages: records.map(normalizeMessage),
  };
}

function parseText(text) {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const messages = lines.map((line, index) => {
    const pipe = line.split("|").map((part) => part.trim());
    if (pipe.length >= 3) {
      return normalizeMessage({ date: pipe[0], sender: pipe[1], body: pipe.slice(2).join(" | ") }, index);
    }
    const match = line.match(/^(?:\[([^\]]+)\]\s*)?([^:]{1,80}):\s*(.+)$/);
    if (match) {
      return normalizeMessage({ date: match[1] ?? new Date(0).toISOString(), sender: match[2], body: match[3] }, index);
    }
    return normalizeMessage({ sender: "Unknown participant", body: line, date: new Date(0).toISOString() }, index);
  });
  if (!messages.length) throw new Error("The text file did not contain any readable lines.");
  return { parser: "Delimited text parser · browser demo", messages };
}

async function inspectSource(name, text, type = "text/plain") {
  const extension = name.split(".").pop()?.toLowerCase();
  let parsed;
  if (extension === "xml" || type.includes("xml")) parsed = parseXml(text);
  else if (extension === "json" || type.includes("json")) parsed = parseJson(text);
  else parsed = parseText(text);

  const hash = await sha256(text);
  const participants = [...new Set(parsed.messages.map((message) => message.sender))];
  const validDates = parsed.messages
    .map((message) => new Date(message.occurredAt))
    .filter((date) => !Number.isNaN(date.getTime()) && date.getTime() > 0)
    .sort((a, b) => a - b);
  const unknownSenders = parsed.messages.filter((message) => message.sender === "Unknown participant").length;
  const emptyBodies = parsed.messages.filter((message) => !message.body.trim()).length;
  const warnings = unknownSenders + emptyBodies;
  const bytes = new TextEncoder().encode(text).byteLength;

  return {
    name,
    type: type || "text/plain",
    extension: extension?.toUpperCase() || "TEXT",
    bytes,
    hash,
    rawText: text,
    parser: parsed.parser,
    messages: parsed.messages,
    participants,
    warnings,
    coverage: parsed.messages.length ? Math.round(((parsed.messages.length - warnings) / parsed.messages.length) * 1000) / 10 : 0,
    firstAt: validDates[0]?.toISOString() ?? null,
    lastAt: validDates.at(-1)?.toISOString() ?? null,
  };
}

function Stepper({ activeStep }) {
  return (
    <ol className="stepper" aria-label="Intake progress">
      {STEPS.map(([title, detail], index) => {
        const number = index + 1;
        const complete = number < activeStep;
        return (
          <li key={title} className={`${number === activeStep ? "active" : ""} ${complete ? "complete" : ""}`}>
            <span className="step-number">{complete ? <Check weight="bold" /> : number}</span>
            <span className="step-label"><strong>{title}</strong><small>{detail}</small></span>
          </li>
        );
      })}
    </ol>
  );
}

function SourceChooser({ busy, onFile, onDemo }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const acceptFiles = (files) => {
    const [file] = files;
    if (file) onFile(file);
  };

  return (
    <section className="source-empty" aria-labelledby="choose-source-title">
      <div
        className={`drop-zone ${dragging ? "dragging" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFiles(event.dataTransfer.files); }}
      >
        <span className="drop-icon"><FileArrowUp size={28} weight="duotone" /></span>
        <p className="overline">Browser-local source</p>
        <h2 id="choose-source-title">Choose a conversation export</h2>
        <p>Open an XML, JSON, or delimited text export. The file stays in this browser and is not uploaded.</p>
        <div className="chooser-actions">
          <button className="button primary" type="button" onClick={() => inputRef.current?.click()} disabled={busy}>
            <FolderOpen size={17} weight="bold" /> Choose local file
          </button>
          <button className="button" type="button" onClick={onDemo} disabled={busy}>
            {busy ? <CircleNotch className="spin" size={17} /> : <FileText size={17} />} Load safe demo
          </button>
        </div>
        <input
          ref={inputRef}
          className="visually-hidden"
          type="file"
          aria-label="Choose conversation export"
          accept=".xml,.json,.txt,text/plain,application/json,application/xml,text/xml"
          onChange={(event) => acceptFiles(event.target.files)}
        />
        <small>Supported in this prototype: SMS-style XML, JSON message arrays, and pipe-delimited text.</small>
      </div>
    </section>
  );
}

function ConversationPreview({ source }) {
  const grouped = useMemo(() => {
    const result = [];
    source.messages.forEach((message) => {
      const date = formatDate(message.occurredAt, false);
      const lastGroup = result.at(-1);
      if (!lastGroup || lastGroup.date !== date) result.push({ date, messages: [message] });
      else lastGroup.messages.push(message);
    });
    return result;
  }, [source]);
  const participantColors = Object.fromEntries(source.participants.map((participant, index) => [participant, index % 2 ? "indigo" : "green"]));

  return (
    <div className="conversation-panel">
      <div className="conversation-summary">
        <div><span>Participants ({source.participants.length})</span><div className="participant-list">{source.participants.map((participant) => <strong key={participant}><i className={participantColors[participant]} />{participant}</strong>)}</div></div>
        <div><span>Detected time range</span><strong>{source.firstAt ? `${formatDate(source.firstAt)} → ${formatDate(source.lastAt)}` : "No reliable dates detected"}</strong></div>
      </div>
      <div className="message-list" role="region" tabIndex={0} aria-label="Extracted conversation preview">
        {grouped.map((group) => (
          <section key={group.date}>
            <div className="date-rule"><span>{group.date}</span></div>
            {group.messages.map((message) => (
              <article className="message-row" key={message.id}>
                <time>{formatTime(message.occurredAt)}</time>
                <strong><i className={participantColors[message.sender]} />{message.sender}</strong>
                <p className={participantColors[message.sender]}>{message.body || "[Empty message]"}</p>
                <span>Message</span>
              </article>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}

function MetadataPanel({ source }) {
  return (
    <div className="detail-panel metadata-panel">
      <header><Info size={20} weight="duotone" /><div><h3>Extracted source metadata</h3><p>Computed from the selected browser-local file.</p></div></header>
      <dl className="detail-grid">
        <div><dt>Original filename</dt><dd>{source.name}</dd></div>
        <div><dt>Detected format</dt><dd>{source.extension} · {source.type}</dd></div>
        <div><dt>File size</dt><dd>{formatBytes(source.bytes)} ({source.bytes.toLocaleString()} bytes)</dd></div>
        <div><dt>Messages</dt><dd>{source.messages.length}</dd></div>
        <div><dt>Participants</dt><dd>{source.participants.join(", ")}</dd></div>
        <div><dt>Time range</dt><dd>{source.firstAt ? `${formatDate(source.firstAt)} — ${formatDate(source.lastAt)}` : "Not available"}</dd></div>
        <div className="wide"><dt>SHA-256 of selected content</dt><dd className="hash-value">{source.hash}</dd></div>
      </dl>
    </div>
  );
}

function ParserPanel({ source }) {
  return (
    <div className="detail-panel parser-panel">
      <header><Hash size={20} weight="duotone" /><div><h3>Parser details</h3><p>Transparent prototype diagnostics for this source.</p></div></header>
      <div className="parser-stats">
        <div><span>Parser</span><strong>{source.parser}</strong></div>
        <div><span>Coverage</span><strong className={source.coverage === 100 ? "success-text" : "warning-text"}>{source.coverage}%</strong></div>
        <div><span>Warnings</span><strong>{source.warnings}</strong></div>
        <div><span>Unreadable records</span><strong>0</strong></div>
      </div>
      <div className="coverage-bar"><span style={{ width: `${source.coverage}%` }} /></div>
      <div className="raw-sample"><span>Raw source sample · read only</span><pre>{source.rawText.slice(0, 1100)}</pre></div>
    </div>
  );
}

function SourceInspector({ source }) {
  return (
    <aside className="inspector" aria-label="Selected source summary">
      <section>
        <p className="inspector-title">File &amp; source</p>
        <dl>
          <div><dt>Original filename</dt><dd>{source.name}</dd></div>
          <div><dt>File type</dt><dd>{source.extension} conversation export</dd></div>
          <div><dt>Local size</dt><dd>{formatBytes(source.bytes)}</dd></div>
          <div><dt>Storage</dt><dd>Browser memory only</dd></div>
        </dl>
      </section>
      <section>
        <p className="inspector-title">Extracted metadata</p>
        <dl>
          <div><dt>Participants</dt><dd>{source.participants.length}</dd></div>
          <div><dt>Messages</dt><dd>{source.messages.length}</dd></div>
          <div><dt>Warnings</dt><dd>{source.warnings}</dd></div>
          <div><dt>Coverage</dt><dd>{source.coverage}%</dd></div>
        </dl>
      </section>
      <section>
        <p className="inspector-title">Integrity preview</p>
        <dl>
          <div className="stacked"><dt>SHA-256</dt><dd className="hash-value">{source.hash}</dd></div>
          <div><dt>Computed</dt><dd><span className="status-chip"><CheckCircle size={15} weight="fill" /> In browser</span></dd></div>
        </dl>
      </section>
      <section>
        <p className="inspector-title">Parser &amp; coverage</p>
        <dl>
          <div className="stacked"><dt>Parser</dt><dd>{source.parser}</dd></div>
          <div><dt>Coverage</dt><dd><span className="status-chip"><Check size={14} weight="bold" /> {source.coverage}%</span></dd></div>
        </dl>
      </section>
      <section>
        <p className="inspector-title">Prototype boundary</p>
        <p className="boundary-copy">No database, object storage, Temporal workflow, or evidence ledger is called by this page.</p>
      </section>
    </aside>
  );
}

function Receipt({ source, receipt, onRestart }) {
  return (
    <section className="receipt-view">
      <header className="receipt-hero">
        <span className="receipt-icon"><CheckCircle size={30} weight="fill" /></span>
        <div>
          <p className="overline">Review results · browser-local simulation</p>
          <h2>Intake simulation completed</h2>
          <p>This receipt proves only that the prototype processed the selected content in this browser. Nothing was sent to the platform.</p>
        </div>
        <span className="simulation-badge">Not a production receipt</span>
      </header>
      <div className="receipt-grid">
        <section>
          <p className="receipt-section-title">Simulated run</p>
          <dl className="receipt-fields">
            <div><dt>Receipt ID</dt><dd className="mono">{receipt.id}</dd></div>
            <div><dt>Completed</dt><dd>{formatDate(receipt.completedAt)}</dd></div>
            <div><dt>Source</dt><dd>{source.name}</dd></div>
            <div><dt>Parser</dt><dd>{source.parser}</dd></div>
          </dl>
        </section>
        <section>
          <p className="receipt-section-title">Counts</p>
          <div className="count-grid">
            <div><strong>{source.messages.length}</strong><span>messages parsed</span></div>
            <div><strong>{source.participants.length}</strong><span>participants found</span></div>
            <div><strong>{source.warnings}</strong><span>parser warnings</span></div>
            <div><strong>{source.bytes}</strong><span>source bytes read</span></div>
          </div>
        </section>
        <section className="wide">
          <p className="receipt-section-title">Browser-local provenance</p>
          <ol className="provenance-list">
            <li><span><FileText size={17} /></span><div><strong>Source selected</strong><small>{source.name} · {formatBytes(source.bytes)}</small></div></li>
            <li><span><Hash size={17} /></span><div><strong>Content fingerprint computed</strong><small className="mono">{source.hash}</small></div></li>
            <li><span><ShieldCheck size={17} /></span><div><strong>Preview confirmed</strong><small>{source.messages.length} messages accepted for this simulation only</small></div></li>
          </ol>
        </section>
      </div>
      <div className="receipt-boundary"><Info size={19} weight="fill" /><div><strong>Confirmation starts ingestion; it does not promote anything to evidence.</strong><span>This prototype did not start real ingestion. A production run must return a server-issued receipt and custody references.</span></div></div>
      <footer className="receipt-actions">
        <button className="button" type="button" onClick={onRestart}><ArrowCounterClockwise size={17} /> Start another preview</button>
      </footer>
    </section>
  );
}

export function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("unified-surface-theme") || "light");
  const [source, setSource] = useState(null);
  const [activeTab, setActiveTab] = useState("conversation");
  const [activeStep, setActiveStep] = useState(1);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("unified-surface-theme", theme);
  }, [theme]);

  const loadSource = async (name, text, type) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const inspected = await inspectSource(name, text, type);
      setSource(inspected);
      setReceipt(null);
      setActiveStep(2);
      setActiveTab("conversation");
      setNotice(`${inspected.messages.length} messages parsed locally. Review the preview before confirming.`);
    } catch (sourceError) {
      setSource(null);
      setActiveStep(1);
      setError(sourceError instanceof Error ? sourceError.message : "This source could not be inspected.");
    } finally {
      setBusy(false);
    }
  };

  const handleFile = async (file) => {
    if (!file) return;
    const text = await file.text();
    await loadSource(file.name, text, file.type);
  };

  const rejectPreview = () => {
    setSource(null);
    setReceipt(null);
    setActiveStep(1);
    setActiveTab("conversation");
    setError("");
    setNotice("Preview rejected and cleared. No content was committed or retained by this page.");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const confirmPreview = () => {
    if (!source || busy) return;
    setBusy(true);
    setActiveStep(3);
    setNotice("Running the browser-local intake simulation…");
    window.setTimeout(() => {
      setReceipt({ id: `SIM-${source.hash.slice(0, 12).toUpperCase()}`, completedAt: new Date().toISOString() });
      setActiveStep(4);
      setBusy(false);
      setNotice("Simulation complete. Review the internally consistent receipt below.");
    }, 650);
  };

  const restart = () => {
    setSource(null);
    setReceipt(null);
    setActiveStep(1);
    setActiveTab("conversation");
    setNotice("Ready for another browser-local source.");
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block"><span className="brand-mark">P</span><div><strong>The Platform</strong><small>Evidence &amp; Legal Operations</small></div></div>
        <div className="case-block"><strong>Rowan v. Rowan</strong><span>County Family Court <i /> Custody matter</span></div>
        <div className="top-actions">
          <span className="system-status"><i /> Prototype ready <CaretDown size={13} /></span>
          <button className="theme-toggle" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>
            <Sun size={16} weight={theme === "light" ? "fill" : "regular"} />
            <span><i className={theme} /></span>
            <Moon size={16} weight={theme === "dark" ? "fill" : "regular"} />
          </button>
        </div>
      </header>

      <div className="workspace">
        <nav className="sidebar" aria-label="Daily work">
          <p>Daily work</p>
          <button className="nav-item active" type="button" aria-current="page"><UploadSimple size={20} /> Intake</button>
          <div className="scope-note"><strong>Focused prototype</strong><span>Only the intake preview and decision path is enabled.</span></div>
        </nav>

        <main className="main-workspace">
          <header className="page-header">
            <div><h1>Intake new evidence</h1><p>Choose a source, preview what was extracted, then decide whether to start intake.</p></div>
            <span className="local-only"><ShieldCheck size={17} /> Browser-local simulation</span>
          </header>
          <Stepper activeStep={activeStep} />

          {(notice || error) && <div className={`notice ${error ? "error" : ""}`} role="status">{error ? <Warning size={18} weight="fill" /> : <Info size={18} weight="fill" />}<span>{error || notice}</span></div>}

          {!source && !receipt && <SourceChooser busy={busy} onFile={handleFile} onDemo={() => loadSource(DEMO_NAME, DEMO_CONTENT, "text/plain")} />}

          {source && !receipt && (
            <div className="preview-layout">
              <section className="preview-main">
                <header className="selected-source">
                  <span><FileText size={23} weight="duotone" /></span>
                  <div><small>Selected file</small><strong>{source.name}</strong><p>{source.extension} conversation export <i /> {source.messages.length} messages <i /> {formatBytes(source.bytes)}</p></div>
                  <button className="button compact" type="button" onClick={() => fileInputRef.current?.click()}><FolderOpen size={16} /> Change file</button>
                  <input ref={fileInputRef} className="visually-hidden" type="file" aria-label="Choose replacement conversation export" accept=".xml,.json,.txt,text/plain,application/json,application/xml,text/xml" onChange={(event) => handleFile(event.target.files?.[0])} />
                </header>

                <div className="tabs" role="tablist" aria-label="Preview details">
                  {["conversation", "metadata", "parser"].map((tab) => (
                    <button key={tab} className={activeTab === tab ? "active" : ""} type="button" role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>
                      {tab === "conversation" ? "Conversation preview" : tab === "metadata" ? "Extracted metadata" : "Parser details"}
                    </button>
                  ))}
                </div>
                {activeTab === "conversation" && <ConversationPreview source={source} />}
                {activeTab === "metadata" && <MetadataPanel source={source} />}
                {activeTab === "parser" && <ParserPanel source={source} />}

                <div className="evidence-warning"><Warning size={20} weight="fill" /><div><strong>This is a preview, not evidence.</strong><span>Content is shown for review only. Confirmation starts ingestion; it does not make this content evidence.</span></div></div>
                <footer className="decision-bar">
                  <button className="button reject" type="button" onClick={rejectPreview} disabled={busy}>Reject preview</button>
                  <span>Rejecting clears this source from the page.</span>
                  <div><button className="button primary confirm" type="button" onClick={confirmPreview} disabled={busy}>{busy ? <CircleNotch className="spin" size={18} /> : null}{busy ? "Simulating intake…" : "Confirm and start intake"}<ArrowRight size={18} weight="bold" /></button><small>Starts a browser-local simulation only.</small></div>
                </footer>
              </section>
              <SourceInspector source={source} />
            </div>
          )}

          {source && receipt && <Receipt source={source} receipt={receipt} onRestart={restart} />}
        </main>
      </div>

      <footer className="service-strip">
        <span><i className="good" /> Source chooser ready<small>Local browser access</small></span>
        <span><i className="good" /> Parser ready<small>XML, JSON, text</small></span>
        <span><i className={source ? "good" : "idle"} /> {source ? "Preview loaded" : "No source loaded"}<small>{source ? `${source.messages.length} messages in memory` : "Nothing retained"}</small></span>
        <span className="service-time"><Clock size={15} /> Prototype · no live connection</span>
      </footer>
    </div>
  );
}

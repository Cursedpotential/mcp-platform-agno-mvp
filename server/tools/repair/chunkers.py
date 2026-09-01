"""Structural chunk iterators — the "tree" layer.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

A chunk here is a STRUCTURAL NODE, never a byte range. Splitting a 667 MB
export every N megabytes cuts records in half; splitting it at element
boundaries does not. So:

    xml    -> one record subtree   (lxml Element)
    html   -> one record subtree   (lxml HtmlElement)
    json   -> one item of the streamed array (dict / list)
    ndjson -> one line's object
    csv    -> one row, keyed by header (dict[str, str])

That boundary is what makes damage CONTAINABLE: a malformed <mms> costs one
message, not the rest of the file.

Every iterator here is a generator over a streaming handle. None of them ever
materialises the whole document. The single exception is the JSON repair
fallback, which cannot stream by construction — it is therefore hard-capped by
`JSON_REPAIR_MAX_BYTES` and reports refusal rather than exhausting RAM.

LIFETIME CONTRACT (xml/html only)
---------------------------------
The yielded Element is valid UNTIL THE NEXT ITERATION. lxml's incremental
parser only stays flat because each processed element is cleared and unlinked
after the consumer is done with it. If you need a node to outlive the loop,
copy what you need out of it (`dict(elem.attrib)`, `elem.text`) inside the
loop body. This mirrors stdlib `iterparse` semantics.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from server.tools.repair.encoding import open_binary, open_text
from server.tools.repair.types import (
    COSMETIC,
    LOSSY,
    STRUCTURAL,
    Chunk,
    RepairEvent,
    RepairReport,
)

#: Ceiling for the non-streaming JSON repair fallback. ijson streams; json_repair
#: cannot (it needs the whole document to balance brackets). Above this size we
#: refuse rather than pull a multi-GB string into memory — the caller gets an
#: explicit failure it can record, which is strictly better than an OOM kill.
JSON_REPAIR_MAX_BYTES = 64 * 1024 * 1024

#: Bound on how far the top-level array probe will scan before giving up.
_PREFIX_PROBE_EVENTS = 10_000


# --------------------------------------------------------------------------- xml


def iter_xml(
    path: Path,
    tags: tuple[str, ...] | None = None,
    report: RepairReport | None = None,
    encoding: str | None = None,
    html: bool = False,
    materialize: bool = False,
) -> Iterator[Chunk]:
    """Stream record elements with libxml2 error recovery switched on.

    `recover=True` is the whole point: libxml2 skips past a malformed region and
    keeps parsing instead of aborting the document. Combined with `iterparse`
    this recovers *while streaming*, which is why lxml is the base here and the
    old `_sanitize_xml` + `read_text` fallback is not.

    Security: entity resolution and network access are both disabled. These are
    untrusted third-party exports, and `huge_tree=True` (required for 600 MB+
    files) relaxes libxml2's built-in entity-expansion guard, so leaving
    `resolve_entities` on would open a billion-laughs hole.
    """
    from lxml import etree

    rep = report if report is not None else RepairReport(fmt="html" if html else "xml")
    wanted = {t.lower() for t in tags} if tags else None
    index = 0

    ctx = etree.iterparse(
        str(path),
        events=("end",),
        recover=True,
        huge_tree=True,
        resolve_entities=False,
        no_network=True,
        html=html,
        encoding=encoding,
    )

    try:
        for _event, elem in ctx:
            tag = elem.tag
            # Comments/PIs surface as callables rather than strings; skip them.
            name = tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""
            # The document root is a CONTAINER, not a record. Checked on the
            # live element before any deepcopy, because materialize detaches the
            # copy and would make every element look like a root.
            # Without this, <smses> counted as a 446th "record" in a 445-record
            # calls export — an off-by-one that looks like real data.
            is_root = elem.getparent() is None
            if is_root and (wanted is None or name not in wanted):
                name = ""
            if name and (wanted is None or name in wanted):
                # See the LIFETIME CONTRACT in this module's docstring: the
                # yielded Element is cleared as soon as the consumer asks for
                # the next one, so `list(iter_xml(...))` hands back a list of
                # emptied elements. That is the price of flat memory. Callers
                # that must collect pass materialize=True and accept the cost.
                node = copy.deepcopy(elem) if materialize else elem
                chunk = Chunk(index=index, kind="element", node=node, repairs=[])
                rep.record(chunk)
                yield chunk
                index += 1

            # Free the element AND its already-processed siblings. Clearing alone
            # is the classic half-fix: the root keeps accumulating emptied
            # children and memory still climbs across a large file.
            elem.clear()
            parent = elem.getparent()
            if parent is not None:
                while elem.getprevious() is not None:
                    del parent[0]
    except etree.XMLSyntaxError as exc:
        # recover=True handles damage mid-document; reaching here means libxml2
        # could not continue at all — most often a file truncated mid-element.
        rep.truncated = True
        rep.events.append(
            RepairEvent(
                kind="xml_unrecoverable",
                detail=f"parser stopped after {index} elements: {exc}",
                severity=LOSSY,
                chunk_index=index,
            )
        )
    finally:
        _drain_xml_error_log(ctx, rep)
        del ctx


#: Cap on individual recovery events kept per file. A thoroughly mangled
#: document can produce thousands; past this point they are summarised.
_MAX_XML_ERROR_EVENTS = 100


def _drain_xml_error_log(ctx: Any, rep: RepairReport) -> None:
    """Surface libxml2's recovery errors. THEY ARE NOT EXCEPTIONS.

    With recover=True libxml2 skips whatever it cannot parse and keeps going.
    Nothing raises, the iteration completes normally, and the only record that
    anything was discarded lives in `ctx.error_log`. A file with a control
    character inside an attribute yielded 9 of its 10 records and reported a
    perfectly clean run — the identical silent-loss shape as the 516 dropped
    body-less MMS.

    Every recovery error is classed LOSSY. Some are individually harmless (a
    bare `&` is kept as text), but recovery means "discard the bad part to
    continue", and we cannot prove from the log which ones cost a record.
    Over-reporting costs a review; under-reporting costs evidence.
    """
    try:
        entries = list(ctx.error_log)
    except Exception:  # noqa: BLE001 - lxml error-log proxies vary by build
        return
    if not entries:
        return

    seen: set[tuple[int, str]] = set()
    kept = 0
    for entry in entries:
        line = int(getattr(entry, "line", 0) or 0)
        message = str(getattr(entry, "message", entry))
        key = (line, message)
        if key in seen:
            continue
        seen.add(key)
        if kept >= _MAX_XML_ERROR_EVENTS:
            continue
        kept += 1
        rep.events.append(
            RepairEvent(
                kind="xml_recovery_error",
                detail=f"line {line}: {message}"[:400],
                severity=LOSSY,
                line=line or None,
            )
        )

    if len(seen) > kept:
        rep.events.append(
            RepairEvent(
                kind="xml_recovery_error_overflow",
                detail=f"{len(seen) - kept} further distinct recovery errors not itemised",
                severity=LOSSY,
            )
        )


def iter_html(path: Path, tags: tuple[str, ...] | None = None, **kw: Any) -> Iterator[Chunk]:
    """HTML is XML with a permanently-broken well-formedness contract, so it uses
    the same streaming path with libxml2's HTML parser (which recovers by design)."""
    return iter_xml(path, tags=tags, html=True, **kw)


# -------------------------------------------------------------------------- json


#: Keys that conventionally hold the records in an export. Checked against the
#: LAST path segment, so "messages" matches both a top-level key and a nested one.
_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "messages",
        "message",
        "items",
        "records",
        "entries",
        "conversations",
        "chats",
        "threads",
        "data",
        "results",
        "rows",
        "events",
        "logs",
        "posts",
        "comments",
        "calls",
        "sms",
    }
)


def _array_candidates(path: Path) -> list[tuple[str, bool]]:
    """[(ijson prefix, is_empty)] for every array seen in a BOUNDED probe.

    An array still open when the probe budget runs out is non-empty by
    definition — it had content the probe was still walking.
    """
    import ijson

    found: list[tuple[str, bool]] = []
    open_at: dict[str, int] = {}
    n = 0
    try:
        with open_binary(path) as fh:
            for n, (prefix, event, _value) in enumerate(ijson.parse(fh)):
                if event == "start_array":
                    open_at[prefix] = n
                elif event == "end_array" and prefix in open_at:
                    found.append((prefix, n - open_at.pop(prefix) == 1))
                if n > _PREFIX_PROBE_EVENTS:
                    break
    except Exception:  # noqa: BLE001, S110 - malformed probe is a negative signal
        pass
    found.extend((prefix, False) for prefix in open_at)
    return found


def _choose_array_prefix(path: Path) -> tuple[str | None, str]:
    """Pick WHICH array holds the records, and say why.

    Taking the first array in document order is wrong and silently so: a
    Facebook Messenger export opens with `participants` (2 entries) before
    `messages`, so a first-array rule streams the participant list, reports a
    clean run, and hands back two rows that are not messages at all.

    Ranked, lower is better:
      1. last path segment is a conventional record key
      2. array is non-empty            (skips FB's empty `magic_words`)
      3. shallower nesting             (prefers the outer array)
      4. document order                (stable tie-break)

    Returns (ijson item prefix, human-readable reason).
    """
    cands = _array_candidates(path)
    if not cands:
        return None, "no array found in the probe window"

    def rank(item: tuple[int, tuple[str, bool]]) -> tuple[bool, bool, int, int]:
        order, (prefix, empty) = item
        last = prefix.rsplit(".", 1)[-1].lower() if prefix else ""
        return (last not in _RECORD_KEYS, empty, prefix.count("."), order)

    _order, (prefix, _empty) = min(enumerate(cands), key=rank)
    resolved = f"{prefix}.item" if prefix else "item"
    others = [p or "<root>" for p, _ in cands if p != prefix]
    reason = f"selected array {prefix or '<root>'!r}"
    if others:
        reason += f" over {others}"
    return resolved, reason


def iter_json(
    path: Path,
    prefix: str | None = None,
    report: RepairReport | None = None,
) -> Iterator[Chunk]:
    """Stream items out of a JSON array without loading the document.

    `prefix` is an ijson path: "item" for a top-level array, "messages.item" for
    Facebook Messenger's `{"messages": [...]}`. Auto-detected when omitted.

    On a parse failure the whole-document repair fallback runs, but only under
    JSON_REPAIR_MAX_BYTES — see that constant.
    """
    import ijson

    rep = report if report is not None else RepairReport(fmt="json")

    if prefix:
        resolved: str | None = prefix
    else:
        resolved, reason = _choose_array_prefix(path)
        # Which array we picked is a decision, not an implementation detail:
        # picking the wrong one yields a clean-looking run over the wrong data.
        # Record it so it is auditable rather than invisible.
        rep.events.append(RepairEvent(kind="json_array_selected", detail=reason, severity=COSMETIC))

    if resolved is None:
        yield from _json_repair_fallback(path, rep, reason="no array found to stream")
        return

    index = 0
    try:
        with open_binary(path) as fh:
            for obj in ijson.items(fh, resolved):
                chunk = Chunk(index=index, kind="object", node=obj, repairs=[])
                rep.record(chunk)
                yield chunk
                index += 1
    except Exception as exc:  # noqa: BLE001 - optional ijson versions expose different errors
        rep.events.append(
            RepairEvent(
                kind="json_stream_broke",
                detail=f"stream failed after {index} items: {type(exc).__name__}: {exc}",
                severity=STRUCTURAL,
                chunk_index=index,
            )
        )
        # Only the UNREAD remainder is at risk, but json_repair cannot resume
        # mid-document — it re-reads from the top, so already-yielded items are
        # skipped by the caller-visible index to avoid duplicates.
        yield from _json_repair_fallback(path, rep, reason=str(exc), skip=index, start_index=index)


def _json_repair_fallback(
    path: Path,
    rep: RepairReport,
    reason: str,
    skip: int = 0,
    start_index: int = 0,
) -> Iterator[Chunk]:
    """Whole-document repair. NOT streaming — hard-capped, and says so."""
    size = path.stat().st_size
    if size > JSON_REPAIR_MAX_BYTES:
        rep.truncated = True
        rep.events.append(
            RepairEvent(
                kind="json_repair_refused",
                detail=(
                    f"{size:,} bytes exceeds the {JSON_REPAIR_MAX_BYTES:,}-byte "
                    f"non-streaming repair cap; refused rather than load it all "
                    f"({reason})"
                ),
                severity=LOSSY,
            )
        )
        failed = Chunk(index=start_index, kind="object", node=None, ok=False, error="too large to repair")
        rep.record(failed)
        yield failed
        return

    try:
        import json_repair
    except ImportError:
        rep.events.append(
            RepairEvent(kind="json_repair_unavailable", detail="json-repair not installed", severity=LOSSY)
        )
        failed = Chunk(index=start_index, kind="object", node=None, ok=False, error="json-repair not installed")
        rep.record(failed)
        yield failed
        return

    with open_text(path) as fh:
        raw = fh.read()

    # skip_json_loads is deliberately NOT set: this path is also reached when the
    # document is valid but simply has no array to stream, and the repair parser
    # can mutate already-valid JSON.
    data = json_repair.loads(raw)
    rep.events.append(
        RepairEvent(
            kind="json_document_repaired",
            detail=f"whole-document repair applied ({reason})",
            severity=STRUCTURAL,
        )
    )

    items = data if isinstance(data, list) else _first_list_in(data)
    if items is None:
        only = Chunk(index=start_index, kind="object", node=data, repairs=[])
        rep.record(only)
        yield only
        return

    for n, obj in enumerate(items):
        if n < skip:
            continue
        chunk = Chunk(index=start_index + (n - skip), kind="object", node=obj, repairs=[])
        rep.record(chunk)
        yield chunk


def _first_list_in(data: Any) -> list[Any] | None:
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value
    return None


def iter_ndjson(path: Path, report: RepairReport | None = None) -> Iterator[Chunk]:
    """Newline-delimited JSON: naturally chunked, one object per line.

    A broken line costs exactly that line, so each is repaired independently and
    a failure is reported as a failed chunk rather than ending the stream.
    """
    rep = report if report is not None else RepairReport(fmt="ndjson")
    index = 0

    with open_text(path, events=rep.events) as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            repairs: list[RepairEvent] = []
            try:
                import json

                node = json.loads(stripped)
            except ValueError as exc:
                try:
                    import json_repair

                    node = json_repair.loads(stripped, skip_json_loads=True)
                    repairs.append(
                        RepairEvent(
                            kind="ndjson_line_repaired",
                            detail=f"line {lineno}: {exc}",
                            severity=STRUCTURAL,
                            line=lineno,
                            chunk_index=index,
                        )
                    )
                except Exception as exc2:  # noqa: BLE001 - optional json-repair error surface
                    chunk = Chunk(
                        index=index,
                        kind="object",
                        node=None,
                        ok=False,
                        error=f"line {lineno}: {exc2}",
                    )
                    rep.record(chunk)
                    yield chunk
                    index += 1
                    continue
            chunk = Chunk(index=index, kind="object", node=node, repairs=repairs)
            rep.record(chunk)
            yield chunk
            index += 1


# --------------------------------------------------------------------------- csv


def _sniff_dialect(sample: str) -> tuple[Any, list[RepairEvent]]:
    """CleverCSV first, stdlib Sniffer second, excel last.

    CleverCSV exists precisely because `csv.Sniffer` is unreliable on real-world
    files — it is the Turing Institute's consistency-measure detector and is
    markedly better at exports with quoted delimiters inside fields.
    """
    import csv as _csv

    events: list[RepairEvent] = []
    try:
        from clevercsv.detect import Detector
        from clevercsv.wrappers import detect_dialect  # noqa: F401  (import probe)

        simple = Detector().detect(sample)
        if simple is not None:
            return simple.to_csv_dialect(), events
    except Exception as exc:  # noqa: BLE001 - optional CleverCSV versions vary
        events.append(
            RepairEvent(
                kind="dialect_detector_fallback",
                detail=f"CleverCSV unavailable or inconclusive ({type(exc).__name__}); using stdlib",
                severity=COSMETIC,
            )
        )

    try:
        return _csv.Sniffer().sniff(sample, delimiters=",;\t|"), events
    except _csv.Error:
        events.append(
            RepairEvent(
                kind="dialect_defaulted",
                detail="no delimiter could be detected; assuming comma",
                severity=COSMETIC,
            )
        )
        return _csv.excel, events


def iter_csv(
    path: Path,
    report: RepairReport | None = None,
    encoding: str | None = None,
) -> Iterator[Chunk]:
    """Stream rows, repairing ragged ones. NOTHING IS EVER TRUNCATED.

    Row boundaries come from the csv reader, never from splitting on newlines:
    a quoted field may legally contain a newline, and line-splitting shreds
    exactly the multi-line message bodies this corpus is full of.

    Ragged-row policy:
      short row -> pad with "" (structural: no data lost)
      long row  -> extras preserved under "__overflow__" (structural, NOT lossy)

    Dropping the extras would be the easy fix and is the wrong one — an extra
    field usually means an unescaped delimiter inside real message content, so
    discarding it discards evidence.
    """
    import csv as _csv

    rep = report if report is not None else RepairReport(fmt="csv")
    head = read_head_text(path, encoding)
    dialect, dialect_events = _sniff_dialect(head)
    rep.events.extend(dialect_events)

    index = 0
    with open_text(path, encoding=encoding, events=rep.events) as fh:
        reader = _csv.reader(fh, dialect)
        try:
            header = next(reader)
        except StopIteration:
            return

        header = [h.strip() for h in header]
        width = len(header)

        for row in reader:
            repairs: list[RepairEvent] = []
            lineno = reader.line_num

            if len(row) < width:
                repairs.append(
                    RepairEvent(
                        kind="ragged_row_short",
                        detail=f"line {lineno}: {len(row)} fields, header declares {width}; padded",
                        severity=STRUCTURAL,
                        line=lineno,
                        chunk_index=index,
                    )
                )
                row = row + [""] * (width - len(row))

            overflow: list[str] = []
            if len(row) > width:
                overflow = row[width:]
                repairs.append(
                    RepairEvent(
                        kind="ragged_row_long",
                        detail=(
                            f"line {lineno}: {len(row)} fields, header declares {width}; "
                            f"{len(overflow)} extra preserved under __overflow__"
                        ),
                        severity=STRUCTURAL,
                        line=lineno,
                        chunk_index=index,
                    )
                )
                row = row[:width]

            node: dict[str, Any] = dict(zip(header, row))
            if overflow:
                node["__overflow__"] = overflow

            chunk = Chunk(index=index, kind="row", node=node, repairs=repairs)
            rep.record(chunk)
            yield chunk
            index += 1


def read_head_text(path: Path, encoding: str | None = None, limit: int = 65_536) -> str:
    """Decoded head sample for dialect detection — bounded, never the whole file."""
    with open_text(path, encoding=encoding) as fh:
        return fh.read(limit)


# ---------------------------------------------------------------------- pdf


def iter_pdf(
    path: Path,
    report: RepairReport | None = None,
    ocr: bool = True,
    **_kw: Any,
) -> Iterator[Chunk]:
    """One chunk per PAGE, via the existing tiered `extract.text` tool.

    PDF IS THE ONE FORMAT HERE THAT CANNOT STREAM, and that is a property of the
    format rather than a shortcut taken here: a PDF's cross-reference table
    lives at the END of the file, so a reader must seek to the tail before it
    can resolve any object. There is no forward-only parse of a PDF. Page count
    bounds the cost instead of file length.

    The "repair" for a PDF is the tiered fallback already implemented in
    `server/tools/extractors/extract_text.py`: native text layer (pypdf ->
    pdfplumber), then Tesseract OCR when that layer is absent or sparse.

    OCR OUTPUT IS CLASSIFIED LOSSY, DELIBERATELY. Tesseract does not transcribe
    a text layer, it *guesses* glyphs from pixels — the output is a
    reconstruction, and a court-facing pipeline must be able to tell the
    difference between "the document says this" and "a model read this off an
    image". Native-layer extraction stays structural; OCR is lossy. Anything
    else would let a guess inherit the authority of the original.
    """
    from server.tools.registry import registry

    rep = report if report is not None else RepairReport(fmt="pdf")

    try:
        tool = registry.get("documents.extract-text")
    except KeyError:
        from server.tools.registry import load_builtin_tools

        load_builtin_tools()
        tool = registry.get("documents.extract-text")

    try:
        out = tool.run({"path": str(path), "ocr": ocr})
    except Exception as exc:  # noqa: BLE001 - registry tool boundaries may raise any failure
        rep.events.append(
            RepairEvent(
                kind="pdf_extract_failed",
                detail=f"{type(exc).__name__}: {exc}",
                severity=LOSSY,
            )
        )
        yield Chunk(index=0, kind="page", node=None, ok=False, error=str(exc))
        return

    stats = out.get("stats") or {}
    pages: list[str] = out.get("pages") or []
    method = str(stats.get("method") or "unknown")
    ocr_used = bool(stats.get("ocr_used"))

    if ocr_used:
        rep.events.append(
            RepairEvent(
                kind="pdf_ocr_reconstruction",
                detail=(
                    f"no usable native text layer; text was RECONSTRUCTED by OCR "
                    f"({method}) and is a machine reading of pixels, not a transcript"
                ),
                severity=LOSSY,
            )
        )
    if stats.get("low_confidence"):
        rep.events.append(
            RepairEvent(
                kind="pdf_low_confidence",
                detail=f"extractor flagged low confidence (method={method}); escalation advised",
                severity=LOSSY,
            )
        )

    for n, text in enumerate(pages):
        repairs: list[RepairEvent] = []
        if not text.strip():
            repairs.append(
                RepairEvent(
                    kind="pdf_empty_page",
                    detail=f"page {n + 1} yielded no text via {method}",
                    severity=LOSSY,
                    chunk_index=n,
                )
            )
        chunk = Chunk(
            index=n,
            kind="page",
            node={"page": n + 1, "text": text, "method": method, "ocr": ocr_used},
            repairs=repairs,
        )
        rep.record(chunk)
        yield chunk

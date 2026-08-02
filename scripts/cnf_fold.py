"""Fold trailing raw CNF captures into one consolidated block, losslessly.

Keeps every existing `consolidated` block byte-identical. Folds the raw
message/claude_response captures that follow them into a single dated block,
preserving each entry verbatim with its timestamp and speaker. Drops only
note-taker prompt boilerplate (recognisable, contentless, and regenerated every
turn). Backs up first.

Usage: python cnf_fold.py <path-to-project_memory.json> <backup-suffix> <header>

Byline: Claude Code - Opus 5 - 2026-08-01
"""

import json
import pathlib
import shutil
import sys

BOILERPLATE = "You are a third-person note-taker"


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1])
    suffix = argv[2]
    header = argv[3]

    data = json.loads(path.read_text(encoding="utf-8"))
    rm = data.get("realtime_memories") or []

    # Everything up to and including the last consolidated block stays verbatim.
    last_consolidated = -1
    for i, m in enumerate(rm):
        if m.get("type") == "consolidated":
            last_consolidated = i
    keep = rm[: last_consolidated + 1]
    raw = rm[last_consolidated + 1 :]

    if len(raw) < 2:
        print(f"nothing to fold ({len(rm)} entries, {len(raw)} raw)")
        return 0

    backup = path.with_suffix(f".json.bak-{suffix}")
    if not backup.exists():
        shutil.copy2(path, backup)

    parts, dropped = [], 0
    for m in raw:
        content = " ".join((m.get("content") or "").split())
        if not content or BOILERPLATE in content:
            dropped += 1
            continue
        who = "OWNER" if m.get("type") == "message" else "CLAUDE"
        parts.append(f"[{m.get('added_at', '')[:16]} {who}] {content}")

    stamp = raw[-1].get("added_at", "") or "2026-08-01T23:59:00.000000"
    data["realtime_memories"] = keep + [
        {
            "type": "consolidated",
            "source": "consolidation",
            "added_at": stamp,
            "content": header + "\n\n" + "\n\n".join(parts),
        }
    ]
    data["updated_at"] = stamp
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"{len(rm)} -> {len(data['realtime_memories'])} entries; "
        f"folded {len(parts)}, dropped {dropped} boilerplate; backup {backup.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

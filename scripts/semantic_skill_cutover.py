#!/usr/bin/env python3
"""Reversibly move loader-visible standalone skills into a dated quarantine.

Byline: Codex / GPT-5 / 2026-08-29.

This script never deletes. It moves complete top-level bundles, writes an exact
restore map, verifies pre/post tree hashes, and can restore the move.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path


AGENTS_ROOT = Path.home() / ".agents" / "skills"
CODEX_ROOT = Path.home() / ".codex" / "skills"
DEFAULT_QUARANTINE = Path.home() / "to_be_deleted" / "semantic-skills-cutover-20260829-2300"
HOT_AGENT_BUNDLES = {
    ".system",
    "casebible-catalog",
    "env-inventory",
    "graphiti-client",
    "mineru",
    "source-command-env-inventory",
}


def ensure_within(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    base = parent.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"path escapes intended root: {resolved} not under {base}")
    return resolved


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def planned_moves(quarantine: Path) -> list[dict[str, str]]:
    quarantine = ensure_within(quarantine, Path.home() / "to_be_deleted")
    moves: list[dict[str, str]] = []
    roots = (
        (AGENTS_ROOT, quarantine / "agents-skills", HOT_AGENT_BUNDLES),
        (CODEX_ROOT, quarantine / "codex-skills", {".system"}),
    )
    for source_root, destination_root, keep in roots:
        ensure_within(source_root, Path.home())
        for source in sorted((item for item in source_root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
            if source.name in keep:
                continue
            destination = destination_root / source.name
            ensure_within(source, source_root)
            ensure_within(destination, quarantine)
            if destination.exists():
                raise FileExistsError(f"destination already exists: {destination}")
            moves.append(
                {
                    "source": str(source),
                    "destination": str(destination),
                    "tree_sha256": tree_hash(source),
                }
            )
    return moves


def apply_cutover(quarantine: Path) -> dict[str, object]:
    if quarantine.exists():
        raise FileExistsError(f"quarantine already exists: {quarantine}")
    moves = planned_moves(quarantine)
    moved: list[dict[str, str]] = []
    quarantine.mkdir(parents=True)
    try:
        for entry in moves:
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            observed = tree_hash(destination)
            if observed != entry["tree_sha256"]:
                raise RuntimeError(f"post-move hash mismatch: {destination}")
            moved.append(entry)
    except Exception:
        for entry in reversed(moved):
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        raise
    receipt: dict[str, object] = {
        "operation": "semantic-skill-loader-cutover",
        "created_at": datetime.now(UTC).isoformat(),
        "quarantine": str(quarantine),
        "agents_root": str(AGENTS_ROOT),
        "codex_root": str(CODEX_ROOT),
        "hot_agent_bundles": sorted(HOT_AGENT_BUNDLES),
        "moved_bundle_count": len(moved),
        "moves": moved,
        "restore_command": f'uv run python scripts/semantic_skill_cutover.py --restore "{quarantine / "restore-map.json"}"',
        "deletion_policy": "Only the user may delete anything in to_be_deleted.",
    }
    receipt_path = quarantine / "restore-map.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def restore(receipt_path: Path) -> dict[str, object]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    restored = 0
    for entry in reversed(receipt["moves"]):
        source = Path(entry["source"])
        destination = Path(entry["destination"])
        if source.exists():
            if destination.exists():
                raise FileExistsError(f"both restore paths exist: {source} and {destination}")
            continue
        if not destination.exists():
            raise FileNotFoundError(f"restore source missing: {destination}")
        if tree_hash(destination) != entry["tree_sha256"]:
            raise RuntimeError(f"pre-restore hash mismatch: {destination}")
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(source))
        if tree_hash(source) != entry["tree_sha256"]:
            raise RuntimeError(f"post-restore hash mismatch: {source}")
        restored += 1
    return {"restored": restored, "receipt": str(receipt_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--apply", action="store_true")
    action.add_argument("--restore", type=Path)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE)
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(restore(args.restore), indent=2))
        return 0
    if args.plan:
        moves = planned_moves(args.quarantine)
        by_root = {
            "agents": sum(entry["source"].lower().startswith(str(AGENTS_ROOT).lower()) for entry in moves),
            "codex": sum(entry["source"].lower().startswith(str(CODEX_ROOT).lower()) for entry in moves),
        }
        print(
            json.dumps(
                {
                    "quarantine": str(args.quarantine),
                    "moves": len(moves),
                    "by_root": by_root,
                    "hot_agent_bundles": sorted(HOT_AGENT_BUNDLES),
                    "first_source": moves[0]["source"] if moves else None,
                    "last_source": moves[-1]["source"] if moves else None,
                },
                indent=2,
            )
        )
        return 0
    receipt = apply_cutover(args.quarantine)
    print(
        json.dumps(
            {
                "quarantine": receipt["quarantine"],
                "moved_bundle_count": receipt["moved_bundle_count"],
                "restore_map": str(Path(receipt["quarantine"]) / "restore-map.json"),
                "hot_agent_bundles": receipt["hot_agent_bundles"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

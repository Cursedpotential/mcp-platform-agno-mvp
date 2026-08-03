"""Cloud-placeholder detection — never hydrate a OneDrive tree by accident.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

WHY THIS EXISTS
---------------
A sweep of `C:\\Users\\matts\\OneDrive\\Case Bible` (1,903 PDFs, 3.5 GiB) was
started without checking placeholder state. Opening a cloud-only file forces
OneDrive to DOWNLOAD it, so a read-only triage silently began hydrating the
whole corpus onto local disk. It was killed at ~110 files.

The distinction that matters:

    os.stat()   reads metadata only          -> SAFE, never hydrates
    open()      reads content                -> HYDRATES a placeholder

So placeholder state can always be checked for free, and there is no excuse
for a bulk tool to trigger a download it was not asked to trigger.

POLICY: every bulk walker in this package SKIPS cloud-only files by default.
Hydration is opt-in and must be a deliberate flag, because it costs bandwidth,
local disk, and (on a metered or synced machine) real money.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Windows file attributes marking a file whose content is not local.
#: OneDrive "Free up space" sets RECALL_ON_DATA_ACCESS; older/other providers
#: use OFFLINE or RECALL_ON_OPEN. Any of them means reading will fetch.
FILE_ATTRIBUTE_OFFLINE = 0x0000_1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x0004_0000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x0040_0000

_NOT_LOCAL = FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS


def is_cloud_only(path: Path | str) -> bool:
    """True when reading this file would trigger a download.

    Uses `os.stat`, which returns cached metadata and does NOT hydrate. On
    non-Windows (or any filesystem without `st_file_attributes`) this returns
    False, because there is no placeholder concept to honour.
    """
    try:
        attrs = os.stat(path).st_file_attributes  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return False
    return bool(attrs & _NOT_LOCAL)


def partition_by_locality(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """(local, cloud_only) — cheap, and never touches file content."""
    local: list[Path] = []
    cloud: list[Path] = []
    for p in paths:
        (cloud if is_cloud_only(p) else local).append(Path(p))
    return local, cloud


def hydration_summary(root: Path, pattern: str = "*.pdf") -> dict[str, int]:
    """How much of a tree is local vs cloud-only. Metadata only, no downloads."""
    local = cloud = local_bytes = 0
    for f in Path(root).rglob(pattern):
        try:
            st = os.stat(f)
        except OSError:
            continue
        if bool(getattr(st, "st_file_attributes", 0) & _NOT_LOCAL):
            cloud += 1
        else:
            local += 1
            local_bytes += st.st_size
    return {
        "total": local + cloud,
        "local": local,
        "cloud_only": cloud,
        "local_bytes": local_bytes,
    }

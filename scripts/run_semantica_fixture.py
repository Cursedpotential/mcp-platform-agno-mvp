"""Run the governed Semantica Phase-1 fixture against a disposable sink.

This script has no live mode and accepts no database, graph, vector, provider,
or arbitrary source-path argument.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server.analysis.semantica_candidates import InMemoryCandidateRepository  # noqa: E402
from server.analysis.semantica_contracts import ExtractionBatch  # noqa: E402
from server.analysis.semantica_worker import SemanticaPatternWorker  # noqa: E402


def main() -> int:
    fixture_path = _ROOT / "tests/fixtures/semantica_phase1_batch.json"
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    document.pop("_byline", None)
    batch = ExtractionBatch.model_validate(document)
    candidates = SemanticaPatternWorker().extract(batch)
    repository = InMemoryCandidateRepository()
    receipt = repository.submit(candidates)
    print(
        json.dumps(
            {
                "status": receipt.status,
                "batch_id": receipt.batch_id,
                "extractor_version": candidates.extractor_version,
                "config_sha256": candidates.config_sha256,
                "source_count": candidates.source_count,
                "entity_count": receipt.entity_count,
                "fact_count": receipt.fact_count,
                "event_count": receipt.event_count,
                "rejection_count": len(candidates.rejections),
                "failure_count": len(candidates.failures),
                "tables": {name: len(rows) for name, rows in sorted(repository.tables.items())},
                "predicates": sorted({candidate.predicate for candidate in candidates.facts}),
                "event_types": sorted({candidate.event_type for candidate in candidates.events}),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

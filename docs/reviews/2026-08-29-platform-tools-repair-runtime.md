# Platform Tools repair-runtime closure

> _Byline: Codex · GPT-5 · 2026-08-29._

## Result

The production `platform-tools` image now installs the pinned runtime dependencies required by
every repair-engine declaration: XML, HTML, JSON, NDJSON, CSV, PDF, and image. Previously the
Python registry discovered all repair tool IDs, but the image installed only the FastAPI facade
dependencies. Most repair calls therefore failed at execution time because their function-local
libraries were absent.

The image remains a capability service. PostgreSQL and the governed retained source remain the
authority; this change adds no SQLite authority and does not alter the legacy SBV storage-retirement
lane. It also installs no ONNX, transformer, embedding, or other local inference runtime. Tesseract
and Poppler are deterministic document/OCR executables required by the already-declared image/PDF
extraction capability.

## Fail-closed gates

- The Docker build imports the repair manifest and refuses to finish unless all seven declared
  formats report a ready engine.
- The build separately imports `pikepdf`, because structural PDF repair is distinct from the PDF
  text-extraction readiness predicate.
- The build verifies that the `tesseract` and `pdftoppm` executables are present.
- The Coolify healthcheck executes `repair.capabilities` through the actual facade and refuses
  healthy status when any declared engine is unavailable.
- Deployment-contract tests pin the image dependency list to the repository's locked versions and
  preserve the explicit OCR-only pins from `uv.lock`.

## Validation boundary

Source-level tests and formatting checks prove the Docker/deployment contract. The exact image must
still be built by Coolify and the healthcheck plus a real repair execution must pass on the VPS
before this is production-live proof.

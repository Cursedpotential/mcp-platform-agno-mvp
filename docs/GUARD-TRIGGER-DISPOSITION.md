# Guard trigger disposition — which guards get replayed, and when

_Generated 2026-08-30. Governed by D-110: nothing is immutable until evidence is promoted,
behind a dev flag. This file exists so that flipping that flag does NOT mean replaying all 131
triggers blindly._

**Total guard triggers defined across sql/0001-0055: 131 on 84 tables.**

---

## A · REPLAY THESE when the dev flag flips

These guard `evidence.*` — promoted evidence, custody, immutable-by-design. This is the ONLY bucket the flag should turn on.

**0 triggers**

| table | trigger | migration |
|---|---|---|

---

## C · WRONG PLACE — should not exist

A registry / reference table is a LOOKUP table. Append-only on a registry means a format definition you got wrong can never be corrected. Delete these guards rather than deferring them.

**3 triggers**

| table | trigger | migration |
|---|---|---|
| `analysis.case_registry_import_receipt` | `case_registry_import_receipt_immutable` | 0054_platform_case_registry.sql |
| `analysis.case_registry_import_receipt` | `case_registry_import_receipt_no_truncate` | 0054_platform_case_registry.sql |
| `context.raw_format_registry` | `raw_format_registry_append_only` | 0036_context_import_foundation.sql |

---

## D · MOOT — the process they guard is finished

These guard the ai -> platform consolidation, which completed. Remove with the consolidation scaffolding.

**8 triggers**

| table | trigger | migration |
|---|---|---|
| `public.platform_consolidation_checkpoint` | `platform_consolidation_checkpoint_append_only` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_checkpoint` | `platform_consolidation_checkpoint_no_truncate` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_checkpoint` | `platform_consolidation_verified_requires_pass` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_proof_receipt` | `platform_consolidation_bound_receipt_no_supersede` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_proof_receipt` | `platform_consolidation_proof_receipt_append_only` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_proof_receipt` | `platform_consolidation_proof_receipt_no_truncate` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_receipt_claim` | `platform_consolidation_receipt_claim_append_only` | 0049_ai_platform_consolidation_foundation.sql |
| `public.platform_consolidation_receipt_claim` | `platform_consolidation_receipt_claim_no_truncate` | 0049_ai_platform_consolidation_foundation.sql |

---

## B · LEAVE OFF — development layers

These guard `context.*` (intake) and `working.*` (derived work): the layers under active construction. Turning these on freezes development. Revisit only when a lane is finished and its data is real.

**120 triggers**

| table | triggers |
|---|---|
| `context.hash_receipt` | 3 |
| `context.hash_manifest` | 3 |
| `working.first_party_context_thread_source` | 3 |
| `working.third_party_context_thread_source` | 3 |
| `context.uiw_source_context_revision` | 3 |
| `working.realization_event` | 2 |
| `analysis.knowledge_evidence_promotion` | 2 |
| `analysis.matter` | 2 |
| `analysis.court_case` | 2 |
| `timeline.timeline_projection_generation` | 2 |
| `context.raw_record_identity` | 2 |
| `context.source_metadata` | 2 |
| `context.normalized_record_identity` | 2 |
| `context.normalization_lineage` | 2 |
| `context.hash_batch` | 2 |
| `context.hash_batch_member` | 2 |
| `context.reconciliation_receipt` | 2 |
| `context.normalized_generation_publication` | 2 |
| `context.source_version_object` | 2 |
| `context.activity_execution` | 2 |
| `context.raw_generation` | 2 |
| `context.normalized_generation` | 2 |
| `context.hash_manifest_member` | 2 |
| `working.content_chunk_generation` | 2 |
| `context.source_range_locator` | 2 |
| `context.source_object_range_locator` | 2 |
| `context.raw_record_range_locator` | 2 |
| `context.normalized_record_range_locator` | 2 |
| `working.content_chunk` | 2 |
| `working.first_party_context_thread_version` | 2 |
| `working.third_party_context_thread_version` | 2 |
| `working.first_party_context_thread_realization_assertion` | 2 |
| `working.third_party_context_thread_realization_assertion` | 2 |
| `working.first_party_context_thread_message` | 2 |
| `working.third_party_context_thread_message` | 2 |
| `working.claim_assertion` | 2 |
| `analysis.entity_candidate` | 1 |
| `analysis.extraction_candidate` | 1 |
| `working.source_provenance` | 1 |
| `working.review_decision` | 1 |
| `working.promotion` | 1 |
| `ops.audit_ledger` | 1 |
| `working.chat_conversation` | 1 |
| `working.chat_message` | 1 |
| `working.chat_chunk` | 1 |
| `working.chat_chunk_lane` | 1 |
| `working.context_asset` | 1 |
| `ops.workflow_run_review_action` | 1 |
| `working.realization_event_record` | 1 |
| `working.normalized_record_chunk` | 1 |
| `working.message_projection_route` | 1 |
| `working.third_party_conversation_acquisition` | 1 |
| `timeline.event_candidate` | 1 |
| `timeline.timeline_member` | 1 |
| `timeline.timeline_projection_activation` | 1 |
| `timeline.timeline_projection_member` | 1 |
| `timeline.timeline_projection_receipt` | 1 |
| `context.retained_object` | 1 |
| `context.activity_receipt` | 1 |
| `context.source` | 1 |
| `context.source_version` | 1 |
| `working.content_chunk_source_span` | 1 |
| `working.content_chunk_reassembly_receipt` | 1 |
| `timeline.event_candidate_source_range` | 1 |
| `working.content_chunk_classification_decision` | 1 |
| `working.context_review_case` | 1 |
| `working.context_review_decision` | 1 |
| `context.relative_time_anchor` | 1 |
| `working.first_party_context_thread` | 1 |
| `working.first_party_context_thread_realization_source` | 1 |
| `working.first_party_context_thread_realization_message` | 1 |
| `working.third_party_context_thread_realization_source` | 1 |
| `working.third_party_context_thread_realization_message` | 1 |
| `context.uiw_preview_event` | 1 |
| `context.uiw_preview_snapshot` | 1 |
| `context.repair_assessment` | 1 |
| `working.claim_candidate` | 1 |
| `working.claim_assertion_member` | 1 |
| `working.claim_assertion_synthesis_member` | 1 |

---

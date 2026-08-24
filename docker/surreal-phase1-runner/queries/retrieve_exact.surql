-- Exact filtered cosine is the authoritative Phase-1 path.
-- Byline: Codex · GPT-5 · 2026-08-16
-- Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)

LET $eligible = SELECT platform_id, chunk_id, embedding
  FROM embedding_t0_v1
  WHERE matter_id = $matter_id
    AND projection_revision = $projection_revision
    AND policy_version = $policy_version
    AND policy_hash = $policy_hash
    AND authority_state = "approved"
    AND promotion_state = "active"
    AND (
      $mode = "hindsight"
      OR (
        $mode = "as_lived_so_far"
        AND disclosure_tier != "hindsight"
        AND source_available_from IS NOT NONE
        AND source_available_from <= <datetime>$horizon_at
      )
    );

SELECT platform_id, chunk_id,
  vector::similarity::cosine(embedding, $query_vector) AS score
  FROM $eligible
  ORDER BY score DESC
  LIMIT $top_k
  EXPLAIN FULL;

SELECT platform_id, chunk_id,
  vector::similarity::cosine(embedding, $query_vector) AS score
  FROM $eligible
  ORDER BY score DESC
  LIMIT $top_k;

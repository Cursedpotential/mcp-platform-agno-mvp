-- Disposable synthetic-only Phase-1 schema. Never apply to a production database.
-- Byline: Codex · GPT-5 · 2026-08-16

DEFINE ACCESS phase1_record ON DATABASE TYPE RECORD WITH JWT
  ALGORITHM RS256 KEY "__PHASE1_JWT_PUBLIC_KEY__"
  AUTHENTICATE {
    LET $principal = SELECT * FROM ONLY $auth;
    IF $principal.enabled != true { THROW "PRINCIPAL_DISABLED" };
    IF $principal.experiment_id != "phase1-surreal-t0-slice-r1" { THROW "EXPERIMENT_MISMATCH" };
    IF $token.role NOT IN $principal.allowed_roles { THROW "ROLE_MISMATCH" };
    RETURN $auth;
  }
  DURATION FOR TOKEN 5m, FOR SESSION 15m;

DEFINE TABLE service_principal SCHEMAFULL
  PERMISSIONS FOR select WHERE id = $auth;
DEFINE FIELD experiment_id ON TABLE service_principal TYPE string;
DEFINE FIELD allowed_roles ON TABLE service_principal TYPE array<string>;
DEFINE FIELD enabled ON TABLE service_principal TYPE bool;

DEFINE TABLE context SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND experiment_id = $auth.experiment_id
    FOR create WHERE $token.role = "projector" AND experiment_id = $auth.experiment_id;
DEFINE FIELD platform_id ON TABLE context TYPE string;
DEFINE FIELD experiment_id ON TABLE context TYPE string;
DEFINE FIELD environment ON TABLE context TYPE string ASSERT $value = "phase1_t0_disposable";
DEFINE FIELD corpus_tier ON TABLE context TYPE string ASSERT $value = "T0_SYNTHETIC";
DEFINE FIELD created_at ON TABLE context TYPE datetime;

DEFINE TABLE projection_revision SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND platform_id = $token.projection_revision;
DEFINE FIELD platform_id ON TABLE projection_revision TYPE string;
DEFINE FIELD matter_id ON TABLE projection_revision TYPE string;
DEFINE FIELD context_id ON TABLE projection_revision TYPE string;
DEFINE FIELD membership_hash ON TABLE projection_revision TYPE string;
DEFINE FIELD content_hash ON TABLE projection_revision TYPE string;
DEFINE FIELD policy_version ON TABLE projection_revision TYPE string;
DEFINE FIELD policy_hash ON TABLE projection_revision TYPE string;
DEFINE FIELD created_at ON TABLE projection_revision TYPE datetime;
DEFINE INDEX projection_revision_unique ON TABLE projection_revision FIELDS platform_id UNIQUE;

DEFINE TABLE projection_guard SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND revision_id = $token.projection_revision
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND revision_id = $token.projection_revision
    FOR update WHERE $token.role = "projector" AND matter_id = $token.matter_id AND revision_id = $token.projection_revision;
DEFINE FIELD revision_id ON TABLE projection_guard TYPE string;
DEFINE FIELD matter_id ON TABLE projection_guard TYPE string;
DEFINE FIELD status ON TABLE projection_guard TYPE string ASSERT $value IN ["building", "active", "quarantined"];
DEFINE FIELD reconciled_hash ON TABLE projection_guard TYPE option<string>;
DEFINE FIELD quarantine_reason ON TABLE projection_guard TYPE option<string>;
DEFINE FIELD checked_at ON TABLE projection_guard TYPE datetime;
DEFINE INDEX projection_guard_revision_unique ON TABLE projection_guard FIELDS revision_id UNIQUE;

DEFINE TABLE retrieval_chunk SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision AND policy_version = $token.policy_version AND policy_hash = $token.policy_hash AND type::record("projection_guard", $token.projection_revision).status = "active"
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision AND policy_version = $token.policy_version AND policy_hash = $token.policy_hash;
DEFINE FIELD platform_id ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD matter_id ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD projection_revision ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD policy_version ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD policy_hash ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD authority_state ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD promotion_state ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD disclosure_tier ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD visible_from ON TABLE retrieval_chunk TYPE option<datetime>;
DEFINE FIELD content_hash ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD chunker_version ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD source_family_id ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD created_at ON TABLE retrieval_chunk TYPE datetime;
DEFINE INDEX retrieval_chunk_id_unique ON TABLE retrieval_chunk FIELDS platform_id UNIQUE;
DEFINE INDEX retrieval_chunk_eligibility ON TABLE retrieval_chunk FIELDS matter_id, projection_revision, authority_state, promotion_state, disclosure_tier, visible_from;

DEFINE TABLE embedding_t0_v1 SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision AND policy_version = $token.policy_version AND policy_hash = $token.policy_hash AND type::record("projection_guard", $token.projection_revision).status = "active"
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision AND policy_version = $token.policy_version AND policy_hash = $token.policy_hash;
DEFINE FIELD platform_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD chunk_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD matter_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD projection_revision ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD policy_version ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD policy_hash ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD authority_state ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD promotion_state ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD disclosure_tier ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD visible_from ON TABLE embedding_t0_v1 TYPE option<datetime>;
DEFINE FIELD profile_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD input_hash ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD dimensions ON TABLE embedding_t0_v1 TYPE int ASSERT $value = 8;
DEFINE FIELD numeric_type ON TABLE embedding_t0_v1 TYPE string ASSERT $value = "f32";
DEFINE FIELD embedding ON TABLE embedding_t0_v1 TYPE array<float> ASSERT array::len($value) = 8;
DEFINE INDEX embedding_t0_id_unique ON TABLE embedding_t0_v1 FIELDS platform_id UNIQUE;
DEFINE INDEX embedding_t0_eligibility ON TABLE embedding_t0_v1 FIELDS matter_id, projection_revision, authority_state, promotion_state, disclosure_tier, visible_from;

DEFINE TABLE walk SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND (walk_id = $token.walk_id OR $token.role = "auditor")
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND walk_id = $token.walk_id AND projection_revision = $token.projection_revision;
DEFINE FIELD walk_id ON TABLE walk TYPE string;
DEFINE FIELD matter_id ON TABLE walk TYPE string;
DEFINE FIELD run_id ON TABLE walk TYPE string;
DEFINE FIELD mode ON TABLE walk TYPE string ASSERT $value IN ["as_lived_so_far", "hindsight"];
DEFINE FIELD status ON TABLE walk TYPE string ASSERT $value IN ["active", "paused", "sealed"];
DEFINE FIELD projection_revision ON TABLE walk TYPE string;
DEFINE FIELD policy_version ON TABLE walk TYPE string;
DEFINE FIELD policy_hash ON TABLE walk TYPE string;
DEFINE FIELD created_at ON TABLE walk TYPE datetime;
DEFINE INDEX walk_id_unique ON TABLE walk FIELDS walk_id UNIQUE;

DEFINE TABLE walk_snapshot SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND (walk_id = $token.walk_id OR $token.role = "auditor")
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND walk_id = $token.walk_id AND projection_revision = $token.projection_revision;
DEFINE FIELD platform_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD walk_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD matter_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD horizon_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD projection_revision ON TABLE walk_snapshot TYPE string;
DEFINE FIELD eligible_manifest_hash ON TABLE walk_snapshot TYPE string;
DEFINE FIELD state_hash ON TABLE walk_snapshot TYPE string;
DEFINE FIELD failure_reason ON TABLE walk_snapshot TYPE string;
DEFINE FIELD sealed_at ON TABLE walk_snapshot TYPE datetime;
DEFINE FIELD resumable ON TABLE walk_snapshot TYPE bool ASSERT $value = false;
DEFINE INDEX walk_snapshot_id_unique ON TABLE walk_snapshot FIELDS platform_id UNIQUE;

DEFINE TABLE rewalk_of TYPE RELATION IN walk OUT walk ENFORCED SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND out.walk_id = $token.walk_id;
DEFINE FIELD matter_id ON TABLE rewalk_of TYPE string;
DEFINE FIELD reconciliation_id ON TABLE rewalk_of TYPE string;
DEFINE FIELD change_manifest_hash ON TABLE rewalk_of TYPE string;
DEFINE FIELD created_at ON TABLE rewalk_of TYPE datetime;

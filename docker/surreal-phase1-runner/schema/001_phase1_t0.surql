-- Disposable synthetic-only Phase-1 schema. Never apply to a production database.
-- Byline: Codex · GPT-5 · 2026-08-16
-- Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)

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
DEFINE INDEX projection_revision_unique ON TABLE projection_revision FIELDS platform_id, matter_id UNIQUE;

DEFINE TABLE projection_guard SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND revision_id = $token.projection_revision
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND revision_id = $token.projection_revision
    FOR update WHERE $token.role = "projector" AND matter_id = $token.matter_id AND revision_id = $token.projection_revision AND $after.matter_id = $before.matter_id AND $after.revision_id = $before.revision_id AND $before.status IN ["building", "active"] AND (($before.status = "building" AND $after.status IN ["active", "quarantined"]) OR ($before.status = "active" AND $after.status = "quarantined"));
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
DEFINE FIELD source_class ON TABLE retrieval_chunk TYPE string ASSERT $value IN ["first_party", "acquired_third_party"];
DEFINE FIELD conversation_id ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD occurred_at ON TABLE retrieval_chunk TYPE datetime;
DEFINE FIELD acquired_at ON TABLE retrieval_chunk TYPE option<datetime>;
DEFINE FIELD source_available_from ON TABLE retrieval_chunk TYPE datetime;
DEFINE FIELD sender_id ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD recipient_ids ON TABLE retrieval_chunk TYPE array<string>;
DEFINE FIELD participant_ids ON TABLE retrieval_chunk TYPE array<string>;
DEFINE FIELD content_hash ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD chunker_version ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD source_family_id ON TABLE retrieval_chunk TYPE string;
DEFINE FIELD created_at ON TABLE retrieval_chunk TYPE datetime;
DEFINE INDEX retrieval_chunk_id_unique ON TABLE retrieval_chunk FIELDS platform_id, projection_revision UNIQUE;
DEFINE INDEX retrieval_chunk_eligibility ON TABLE retrieval_chunk FIELDS matter_id, projection_revision, authority_state, promotion_state, disclosure_tier, source_available_from;

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
DEFINE FIELD source_class ON TABLE embedding_t0_v1 TYPE string ASSERT $value IN ["first_party", "acquired_third_party"];
DEFINE FIELD conversation_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD occurred_at ON TABLE embedding_t0_v1 TYPE datetime;
DEFINE FIELD acquired_at ON TABLE embedding_t0_v1 TYPE option<datetime>;
DEFINE FIELD source_available_from ON TABLE embedding_t0_v1 TYPE datetime;
DEFINE FIELD sender_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD recipient_ids ON TABLE embedding_t0_v1 TYPE array<string>;
DEFINE FIELD participant_ids ON TABLE embedding_t0_v1 TYPE array<string>;
DEFINE FIELD profile_id ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD input_hash ON TABLE embedding_t0_v1 TYPE string;
DEFINE FIELD dimensions ON TABLE embedding_t0_v1 TYPE int ASSERT $value = 8;
DEFINE FIELD numeric_type ON TABLE embedding_t0_v1 TYPE string ASSERT $value = "f32";
DEFINE FIELD embedding ON TABLE embedding_t0_v1 TYPE array<float> ASSERT array::len($value) = 8;
DEFINE INDEX embedding_t0_id_unique ON TABLE embedding_t0_v1 FIELDS platform_id, projection_revision UNIQUE;
DEFINE INDEX embedding_t0_eligibility ON TABLE embedding_t0_v1 FIELDS matter_id, projection_revision, authority_state, promotion_state, disclosure_tier, source_available_from;

DEFINE TABLE third_party_conversation SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision;
DEFINE FIELD platform_id ON TABLE third_party_conversation TYPE string;
DEFINE FIELD matter_id ON TABLE third_party_conversation TYPE string;
DEFINE FIELD projection_revision ON TABLE third_party_conversation TYPE string;
DEFINE FIELD acquired_at ON TABLE third_party_conversation TYPE datetime;
DEFINE FIELD participant_ids ON TABLE third_party_conversation TYPE array<string>;
DEFINE FIELD subject_id ON TABLE third_party_conversation TYPE string;
DEFINE FIELD source_family_id ON TABLE third_party_conversation TYPE string;
DEFINE FIELD created_at ON TABLE third_party_conversation TYPE datetime;
DEFINE INDEX third_party_conversation_unique ON TABLE third_party_conversation FIELDS platform_id, projection_revision UNIQUE;

DEFINE TABLE third_party_message SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision;
DEFINE FIELD platform_id ON TABLE third_party_message TYPE string;
DEFINE FIELD conversation_id ON TABLE third_party_message TYPE string;
DEFINE FIELD normalized_record_id ON TABLE third_party_message TYPE string;
DEFINE FIELD matter_id ON TABLE third_party_message TYPE string;
DEFINE FIELD projection_revision ON TABLE third_party_message TYPE string;
DEFINE FIELD occurred_at ON TABLE third_party_message TYPE datetime;
DEFINE FIELD acquired_at ON TABLE third_party_message TYPE datetime;
DEFINE FIELD sender_id ON TABLE third_party_message TYPE string;
DEFINE FIELD recipient_ids ON TABLE third_party_message TYPE array<string>;
DEFINE FIELD participant_ids ON TABLE third_party_message TYPE array<string>;
DEFINE FIELD content_hash ON TABLE third_party_message TYPE string;
DEFINE FIELD created_at ON TABLE third_party_message TYPE datetime;
DEFINE INDEX third_party_message_unique ON TABLE third_party_message FIELDS platform_id, projection_revision UNIQUE;

DEFINE TABLE third_party_realization_link SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision
    FOR create WHERE $token.role = "projector" AND matter_id = $token.matter_id AND projection_revision = $token.projection_revision;
DEFINE FIELD platform_id ON TABLE third_party_realization_link TYPE string;
DEFINE FIELD message_id ON TABLE third_party_realization_link TYPE string;
DEFINE FIELD matter_id ON TABLE third_party_realization_link TYPE string;
DEFINE FIELD projection_revision ON TABLE third_party_realization_link TYPE string;
DEFINE FIELD realized_at ON TABLE third_party_realization_link TYPE datetime;
DEFINE FIELD approval_state ON TABLE third_party_realization_link TYPE string ASSERT $value IN ["proposed", "approved", "superseded"];
DEFINE FIELD kind ON TABLE third_party_realization_link TYPE string;
DEFINE FIELD created_at ON TABLE third_party_realization_link TYPE datetime;
DEFINE INDEX third_party_realization_unique ON TABLE third_party_realization_link FIELDS platform_id, projection_revision UNIQUE;

DEFINE TABLE walk SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND (walk_id = $token.walk_id OR $token.role = "auditor")
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND walk_id = $token.walk_id AND projection_revision = $token.projection_revision AND type::record("projection_guard", projection_revision).status = "active"
    FOR update WHERE $token.role = "walk" AND matter_id = $token.matter_id AND walk_id = $token.walk_id AND projection_revision = $token.projection_revision AND $after.matter_id = $before.matter_id AND $after.walk_id = $before.walk_id AND $after.projection_revision = $before.projection_revision AND (($before.status = "active" AND $after.status = "paused" AND type::record("projection_guard", projection_revision).status = "active") OR ($before.status = "paused" AND $after.status = "active" AND type::record("projection_guard", projection_revision).status = "active") OR ($before.status IN ["active", "paused"] AND $after.status = "sealed" AND type::record("projection_guard", projection_revision).status = "quarantined"));
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

DEFINE TABLE walk_checkpoint SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND (walk_id = $token.walk_id OR $token.role = "auditor")
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND walk_id = $token.walk_id AND projection_revision = $token.projection_revision AND type::record("walk", walk_id).status = "paused";
DEFINE FIELD platform_id ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD walk_id ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD matter_id ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD current_step ON TABLE walk_checkpoint TYPE int ASSERT $value > 0;
DEFINE FIELD horizon_id ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD horizon_at ON TABLE walk_checkpoint TYPE datetime;
DEFINE FIELD projection_revision ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD eligible_manifest_hash ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD state_hash ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD trace_hash ON TABLE walk_checkpoint TYPE string;
DEFINE FIELD belief_ids ON TABLE walk_checkpoint TYPE array<string>;
DEFINE FIELD retrieval_ids ON TABLE walk_checkpoint TYPE array<string>;
DEFINE FIELD captured_at ON TABLE walk_checkpoint TYPE datetime;
DEFINE INDEX walk_checkpoint_id_unique ON TABLE walk_checkpoint FIELDS platform_id UNIQUE;

DEFINE TABLE walk_snapshot SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id AND (walk_id = $token.walk_id OR $token.role = "auditor")
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND walk_id = $token.walk_id AND projection_revision = $token.projection_revision AND resumable = false AND type::record("walk", walk_id).status = "sealed";
DEFINE FIELD platform_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD walk_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD matter_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD current_step ON TABLE walk_snapshot TYPE int ASSERT $value > 0;
DEFINE FIELD horizon_id ON TABLE walk_snapshot TYPE string;
DEFINE FIELD horizon_at ON TABLE walk_snapshot TYPE datetime;
DEFINE FIELD projection_revision ON TABLE walk_snapshot TYPE string;
DEFINE FIELD eligible_manifest_hash ON TABLE walk_snapshot TYPE string;
DEFINE FIELD state_hash ON TABLE walk_snapshot TYPE string;
DEFINE FIELD trace_hash ON TABLE walk_snapshot TYPE string;
DEFINE FIELD belief_ids ON TABLE walk_snapshot TYPE array<string>;
DEFINE FIELD retrieval_ids ON TABLE walk_snapshot TYPE array<string>;
DEFINE FIELD failure_reason ON TABLE walk_snapshot TYPE string;
DEFINE FIELD sealed_at ON TABLE walk_snapshot TYPE datetime;
DEFINE FIELD resumable ON TABLE walk_snapshot TYPE bool ASSERT $value = false;
DEFINE INDEX walk_snapshot_id_unique ON TABLE walk_snapshot FIELDS platform_id UNIQUE;

DEFINE TABLE rewalk_of TYPE RELATION IN walk OUT walk ENFORCED SCHEMAFULL
  PERMISSIONS
    FOR select WHERE $auth.enabled = true AND matter_id = $token.matter_id
    FOR create WHERE $token.role = "walk" AND matter_id = $token.matter_id AND in.walk_id = $token.walk_id AND in.status = "active" AND out.status = "sealed" AND in.projection_revision != out.projection_revision;
DEFINE FIELD matter_id ON TABLE rewalk_of TYPE string;
DEFINE FIELD reconciliation_id ON TABLE rewalk_of TYPE string;
DEFINE FIELD change_manifest_hash ON TABLE rewalk_of TYPE string;
DEFINE FIELD created_at ON TABLE rewalk_of TYPE datetime;

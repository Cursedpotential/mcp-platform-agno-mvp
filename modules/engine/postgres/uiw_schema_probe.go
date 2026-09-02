// Byline: Codex · GPT-5.6-Sol · 2026-08-30 (shared UIW schema admission)
// Retarget · Claude Code · Sonnet 5 · 2026-09-02 (BUILD LANE S2): ledger check
// moved from public.schema_version to ops.migration_ledger per D-109 (see
// comment at the ledgerCount subquery below).
package postgres

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
)

// SchemaProbeDB is the read-only database surface needed for startup admission.
type SchemaProbeDB interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

var requiredUIWMigrations = []string{
	"0036", "0037", "0038", "0039", "0042", "0050", "0051", "0053", "0054",
}

var requiredUIWTables = []string{
	"registry.matter", "registry.court_case", "analysis.matter_knowledge_partition", "analysis.case_registry_import_receipt",
	"context.activity_execution", "context.activity_receipt", "context.hash_batch",
	"context.hash_batch_member", "context.hash_manifest", "context.hash_manifest_member",
	"context.hash_receipt", "context.normalization_lineage", "context.normalized_generation",
	"context.normalized_generation_publication", "context.normalized_record_identity",
	"context.raw_format_registry", "context.raw_generation", "context.raw_record_identity",
	"context.reconciliation_receipt", "context.retained_object", "context.source",
	"context.source_metadata", "context.source_version", "context.source_version_object",
	"context.uiw_preview_binding", "context.uiw_preview_snapshot", "context.uiw_preview_receipt",
	"context.uiw_preview_participant", "context.uiw_preview_message", "context.uiw_preview_attachment",
	"context.uiw_preview_event", "context.uiw_preview_decision", "context.repair_assessment",
	"context.repair_decision", "context.repair_resolution", "context.uiw_source_context_revision",
}

var requiredUIWColumns = []string{
	"context.source_version.matter_id", "context.source_version.court_case_id",
	"context.source_version.source_context_ref",
	"context.uiw_source_context_revision.matter_id",
	"context.uiw_source_context_revision.court_case_id",
	"context.uiw_source_context_revision.source_context_ref",
	"analysis.case_registry_import_receipt.source_migration_uri",
	"analysis.case_registry_import_receipt.source_migration_sha256",
	"analysis.case_registry_import_receipt.source_git_commit",
	"analysis.case_registry_import_receipt.payload_schema_version",
	"analysis.case_registry_import_receipt.payload_byte_length",
	"analysis.case_registry_import_receipt.canonical_payload_sha256",
	"analysis.case_registry_import_receipt.api_payload_sha256",
	"analysis.case_registry_import_receipt.source_observed_at",
	"analysis.case_registry_import_receipt.approved_by",
	"analysis.case_registry_import_receipt.approved_on",
}

const authoritativeMatterID = "01a03136-c5cc-71c7-ac77-5c00a29a2ea8"
const authoritativeCourtCaseID = "01a03136-c5cc-76f9-98df-702058d423d9"
const registrySourceMigrationURI = "sql/0030_matter_case_foundation.sql"
const registrySourceMigrationSHA256 = "b19959119c0f040adcdc442aa7772503fd2d1439a90b1565eaa6c17e0883eb70"
const registrySourceGitCommit = "97f48b172b1d31aa5a0005b45170d72af1299773"
const registryPayloadSchemaVersion = "0030-platform-registry-handoff-v1"
const registryCanonicalPayloadSHA256 = "8e0a8e2d86027add31f9470976d1378e039d6efb5312ecae4cfec0ebd10690e6"
const registryAPIPayloadSHA256 = "cd370f6c9c00e620f39f283e2d0d7d1a83a463b14097b99537b886d438618a6d"

// ProbeUIWSchema rejects an incomplete, legacy, over-privileged, or wrongly
// scoped database before any UIW Temporal queue is polled.
func ProbeUIWSchema(ctx context.Context, db SchemaProbeDB) error {
	if db == nil {
		return errors.New("UIW schema admission: database is required")
	}
	var database, currentUser, databaseOwner string
	var ledgerCount, tableCount, columnCount int
	var constraintsExact, substrateExact, roleSafe, grantsExact, receiptExact bool
	err := db.QueryRow(ctx, `
		SELECT current_database(), current_user,
		       pg_get_userbyid((SELECT datdba FROM pg_database WHERE datname=current_database())),
		       -- D-109 (docs/DECISION_LOG.md, 2026-08-30): public.schema_version is
		       -- NOT a migration ledger -- its status vocabulary (active/superseded/
		       -- deprecated) and columns (applies_to/ddl_uri/supersedes) describe
		       -- data-contract versions, not applied migrations; that resemblance
		       -- destroyed migration state once already (2026-08-29 CREATE DATABASE
		       -- ... TEMPLATE ai inherited its rows). ops.migration_ledger (sql/0055
		       -- PART 5) is THE ledger: one row per applied migration_id, no status
		       -- column, so presence alone means "applied" -- no status predicate.
		       (SELECT count(*) FROM ops.migration_ledger
		         WHERE migration_id=ANY($1::text[])),
		       (SELECT count(*) FROM information_schema.tables
		         WHERE format('%s.%s',table_schema,table_name)=ANY($2::text[])),
		       (SELECT count(*) FROM information_schema.columns
		         WHERE format('%s.%s.%s',table_schema,table_name,column_name)=ANY($3::text[])),
		       (NOT EXISTS (
		         SELECT 1 FROM (VALUES
		           ('context.source_version','source_version_matter_fk','registry.matter',ARRAY['matter_id'],ARRAY['id']),
		           ('context.source_version','source_version_court_case_scope_fk','registry.court_case',ARRAY['court_case_id','matter_id'],ARRAY['id','matter_id']),
		           ('context.source_version','source_version_source_context_scope_fk','context.uiw_source_context_revision',ARRAY['source_context_ref','matter_id','court_case_id'],ARRAY['source_context_ref','matter_id','court_case_id']),
		           ('context.uiw_source_context_revision','uiw_source_context_matter_fk','registry.matter',ARRAY['matter_id'],ARRAY['id']),
		           ('context.uiw_source_context_revision','uiw_source_context_court_case_scope_fk','registry.court_case',ARRAY['court_case_id','matter_id'],ARRAY['id','matter_id'])
		         ) AS required(relation_name,constraint_name,referenced_name,columns,referenced_columns)
		         WHERE NOT EXISTS (
		           SELECT 1 FROM pg_constraint c
		           WHERE c.conrelid=required.relation_name::regclass
		             AND c.confrelid=required.referenced_name::regclass AND c.contype='f'
		             AND c.conname=required.constraint_name AND c.convalidated AND c.confdeltype='r'
		             AND ARRAY(SELECT a.attname::text FROM unnest(c.conkey) WITH ORDINALITY k(attnum,ord)
		                       JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum ORDER BY k.ord)=required.columns
		             AND ARRAY(SELECT a.attname::text FROM unnest(c.confkey) WITH ORDINALITY k(attnum,ord)
		                       JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.attnum ORDER BY k.ord)=required.referenced_columns))
		         AND EXISTS (SELECT 1 FROM pg_constraint c
		           WHERE c.conrelid='context.source_version'::regclass
		             AND c.conname='source_version_matter_case_pair_check' AND c.contype='c' AND c.convalidated)
		         AND EXISTS (SELECT 1 FROM pg_constraint c
		           WHERE c.conrelid='context.source_version'::regclass
		             AND c.conname='source_version_source_context_scope_check' AND c.contype='c' AND c.convalidated)
		         AND EXISTS (SELECT 1 FROM pg_constraint c
		           WHERE c.conrelid='context.uiw_source_context_revision'::regclass
		             AND c.conname='uiw_source_context_scope_key' AND c.contype='u' AND c.convalidated
		             AND ARRAY(SELECT a.attname::text FROM unnest(c.conkey) WITH ORDINALITY k(attnum,ord)
		                       JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum ORDER BY k.ord)
		                 =ARRAY['source_context_ref','matter_id','court_case_id'])),
		       (SELECT count(*)=4 FROM pg_constraint WHERE convalidated AND conname=ANY(ARRAY[
		         'raw_record_context_fingerprint_canon_check','hash_batch_context_kind_check',
		         'hash_manifest_context_kind_check','hash_receipt_context_kind_check'])),
		       COALESCE((SELECT rolcanlogin AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
		         AND pg_has_role('platform_runtime','context_import_writer','MEMBER')
		         FROM pg_roles WHERE rolname='platform_runtime'),false),
		       has_schema_privilege('platform_runtime','analysis','USAGE')
		         AND NOT has_schema_privilege('platform_runtime','analysis','CREATE')
		         AND has_table_privilege('platform_runtime','registry.matter','SELECT')
		         AND has_table_privilege('platform_runtime','registry.court_case','SELECT')
		         AND has_table_privilege('platform_runtime','analysis.matter_knowledge_partition','SELECT')
		         AND has_table_privilege('platform_runtime','analysis.case_registry_import_receipt','SELECT')
		         AND NOT has_table_privilege('platform_runtime','registry.matter','INSERT')
		         AND NOT has_table_privilege('platform_runtime','registry.matter','UPDATE')
		         AND NOT has_table_privilege('platform_runtime','registry.matter','DELETE')
		         -- The guard's intent is "platform_runtime must never be able to
		         -- forge ledger history" -- it must track whichever table is
		         -- ACTUALLY the ledger. Retargeted alongside the ledgerCount
		         -- subquery above (D-109): checking INSERT-denial on the old
		         -- data-contract-version table no longer protects anything, since
		         -- platform_runtime writing rows there can no longer masquerade
		         -- as applied-migration state.
		         AND NOT has_table_privilege('platform_runtime','ops.migration_ledger','INSERT')
		         AND (NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agno_app') OR NOT (
		           has_table_privilege('agno_app','registry.matter','INSERT')
		           OR has_table_privilege('agno_app','registry.matter','UPDATE')
		           OR has_table_privilege('agno_app','registry.matter','DELETE')
		           OR has_table_privilege('agno_app','registry.court_case','INSERT')
		           OR has_table_privilege('agno_app','registry.court_case','UPDATE')
		           OR has_table_privilege('agno_app','registry.court_case','DELETE')
		           OR has_table_privilege('agno_app','analysis.matter_knowledge_partition','INSERT')
		           OR has_table_privilege('agno_app','analysis.matter_knowledge_partition','UPDATE')
		           OR has_table_privilege('agno_app','analysis.matter_knowledge_partition','DELETE'))),
		       (SELECT count(*)=1 AND count(*) FILTER (WHERE matter_id=$4::uuid AND court_case_id=$5::uuid
		          AND source_migration_uri=$6 AND encode(source_migration_sha256,'hex')=$7
		          AND source_git_commit=$8 AND payload_schema_version=$9 AND payload_byte_length=1075
		          AND encode(canonical_payload_sha256,'hex')=$10 AND encode(api_payload_sha256,'hex')=$11
		          AND approved_by='owner' AND approved_on=DATE '2026-08-23')=1
		          FROM analysis.case_registry_import_receipt)`,
		requiredUIWMigrations, requiredUIWTables, requiredUIWColumns, authoritativeMatterID, authoritativeCourtCaseID,
		registrySourceMigrationURI, registrySourceMigrationSHA256, registrySourceGitCommit,
		registryPayloadSchemaVersion, registryCanonicalPayloadSHA256, registryAPIPayloadSHA256,
	).Scan(&database, &currentUser, &databaseOwner, &ledgerCount, &tableCount, &columnCount,
		&constraintsExact, &substrateExact, &roleSafe, &grantsExact, &receiptExact)
	if err != nil {
		return errors.New("UIW schema admission: catalog verification unavailable")
	}
	if database != "platform" || currentUser != "platform_runtime" || databaseOwner != "platform_admin" {
		return fmt.Errorf("UIW schema admission: identity rejected: database=%q role=%q owner=%q", database, currentUser, databaseOwner)
	}
	if ledgerCount != len(requiredUIWMigrations) || tableCount != len(requiredUIWTables) || columnCount != len(requiredUIWColumns) || !constraintsExact || !substrateExact || !roleSafe || !grantsExact || !receiptExact {
		return fmt.Errorf("UIW schema admission failed: ledger=%d/%d tables=%d/%d columns=%d/%d constraints=%t substrate=%t role=%t grants=%t receipt=%t",
			ledgerCount, len(requiredUIWMigrations), tableCount, len(requiredUIWTables), columnCount,
			len(requiredUIWColumns), constraintsExact, substrateExact, roleSafe, grantsExact, receiptExact)
	}
	return nil
}

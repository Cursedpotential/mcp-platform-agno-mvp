// Package postgres — this file implements the PostgreSQL/pg_duckdb boundary
// for activities.ExecuteStructuredELT (BUILD LANE E1 / Tweak 4 / H-07 /
// D-080 / D-123). Structured (CSV, NDJSON) sources are read entirely inside
// PostgreSQL via pg_duckdb's duckdb.query() table function — httpfs/R2
// access happens in the database process, never in this Go worker — and
// landed into raw.raw_csv with one set-based INSERT..SELECT per source. No
// row-at-a-time Go loop ever touches a source record.
//
// content_hash / content_canon (READ BEFORE CHANGING): the platform's H2
// custody contract (docs/reference/HASH-TAXONOMY-2026-08-29.md; also
// vendor/github.com/lowcarbdev/sbv/pkg/custodyhash.CanonH2) defines
// "h2-rawelement-v1" as SHA-256 of the exact raw record bytes/span BEFORE
// any decoding. DuckDB's read_csv_auto/read_json_auto already decode each
// row into typed columns before PostgreSQL ever sees it, so this Activity
// cannot honor that byte-exact construction — the hash computed here is
// SHA-256 over the UTF-8 bytes of row_to_json() applied to the
// DuckDB-decoded row: a canonical, deterministic, but POST-decode
// representation, not the platform's pre-decode H2 bytes.
//
// The platform's own hash-chain/canon-tag naming rule — two different
// constructions must never share one tag, exactly the failure mode recorded
// against "h3-chain-v1" (see AGENT_MEMORY.md
// custody-h3-two-chains-not-one.md and the CLAUDE.md hard rule it
// generalizes) — means this construction must NOT be written under
// 'h2-rawelement-v1', even though the BUILD LANE E1 task text named that
// literal tag. This repository writes content_canon =
// eltRawElementDuckDBJSONCanon ("h2-rawelement-duckdb-json-v1") instead.
// This is a deliberate, reported deviation from the task's literal
// instruction — flagged in the BUILD LANE E1 handoff for an owner ruling on
// whether the DuckDB ELT lane needs its own permanent canon-tag family.
//
// OPEN QUESTION (not resolved by any live schema, writer code, or doc found
// 2026-09-02 — reported rather than guessed): live introspection shows every
// raw.<format> table (raw_csv, raw_facebook, raw_sms, ...) shares this exact
// same content_canon default verbatim, with zero existing writers for any of
// them and zero live context.hash_receipt rows to compare against — so it is
// unclear whether raw.<format>.content_hash is meant to belong to (a) the
// custody H1/H2/H3 family (what the literal default text names), (b) the
// separate "context fingerprint" family (context_raw_record_fingerprint,
// construction context-rawrecord-fingerprint-v1, per sql/0048 and
// docs/reference/HASH-TAXONOMY-2026-08-29.md's "everything ingests as
// context ... custody begins only at promotion"), or (c) its own third,
// table-local dedup/integrity concept unrelated to either family. This file
// takes option (c) with its own distinct tag rather than silently reusing
// either existing family's name for an unverified construction; content_canon
// is plain TEXT with no CHECK constraint (live-confirmed), so re-tagging
// later costs zero migration.
//
// Byline: Claude Code · Sonnet 5 · 2026-09-02
package postgres

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

// eltRawElementDuckDBJSONCanon is this Activity's own content_canon tag —
// see the package-level comment above for why it is not "h2-rawelement-v1".
const eltRawElementDuckDBJSONCanon = "h2-rawelement-duckdb-json-v1"

// eltParserVersion tags every row this Activity writes so it is trivially
// distinguishable from parser-produced raw rows sharing the same table.
const eltParserVersion = "elt-duckdb-v1"

// eltDuckDBQuoteTag is the dollar-quote tag wrapping the inner DuckDB SQL
// text passed to duckdb.query(). A distinctive tag (rather than bare "$$")
// avoids collision with any "$$" that could appear inside a pathological
// source URL.
const eltDuckDBQuoteTag = "elt_duckdb_sql"

// StructuredELTRepository implements activities.StructuredELTRepository.
type StructuredELTRepository struct {
	db DB
}

// NewStructuredELTRepository constructs a repository. db must reach a
// PostgreSQL instance with pg_duckdb installed and an R2/S3 secret already
// provisioned (server.core.session.ensure_duckdb_r2_secret at API startup,
// or server.api.runtime_support.ensure_duckdb_r2_secret); this repository
// never provisions a secret itself.
func NewStructuredELTRepository(db DB) (*StructuredELTRepository, error) {
	if db == nil {
		return nil, errors.New("postgres structured elt repository: database is required")
	}
	return &StructuredELTRepository{db: db}, nil
}

// ExecuteStructuredELT implements activities.StructuredELTRepository. The
// DuckDB read and the INSERT execute as one bounded PostgreSQL transaction:
// the httpfs/R2 read happens server-side inside a single SQL statement, so
// this transaction never spans slow client-observed I/O (D-089).
func (r *StructuredELTRepository) ExecuteStructuredELT(ctx context.Context, spec activities.StructuredELTSpec) (activities.StructuredELTResult, error) {
	sourceID, err := uuid.Parse(spec.SourceID)
	if err != nil {
		return activities.StructuredELTResult{}, fmt.Errorf("structured elt source_id: %w", err)
	}
	ingestRunID, err := uuid.Parse(spec.IngestRunID)
	if err != nil {
		return activities.StructuredELTResult{}, fmt.Errorf("structured elt ingest_run_id: %w", err)
	}
	if err := validateOptionalUUID(spec.DeviceID, "device_id"); err != nil {
		return activities.StructuredELTResult{}, err
	}
	if err := validateOptionalUUID(spec.AcquisitionID, "acquisition_id"); err != nil {
		return activities.StructuredELTResult{}, err
	}

	readerExpr, err := duckDBReaderExpr(spec.Format, spec.SourceURL)
	if err != nil {
		return activities.StructuredELTResult{}, err
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return activities.StructuredELTResult{}, fmt.Errorf("begin structured elt transaction: %w", err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback(context.WithoutCancel(ctx))
		}
	}()

	// Idempotent-replay guard: a repeated Temporal attempt for the same
	// ingest_run_id must not double-insert. This is a lightweight,
	// column-only guard against raw.raw_csv itself — NOT the platform's
	// context.activity_execution/activity_receipt idempotency contract used
	// by the parser/raw pipelines (RawPipelineRepository etc.). raw.raw_csv
	// is a plain landing table with no receipt wiring of its own; promoting
	// this guard to the full receipt-keyed contract is future scope, not
	// this lane's (no schema change is required for what is implemented
	// here).
	var alreadyInserted int64
	if err := tx.QueryRow(ctx,
		`SELECT count(*) FROM raw.raw_csv WHERE ingest_run_id = $1::uuid`,
		ingestRunID,
	).Scan(&alreadyInserted); err != nil {
		return activities.StructuredELTResult{}, fmt.Errorf("check structured elt idempotency: %w", err)
	}

	sourceRows, err := r.countSourceRows(ctx, tx, readerExpr)
	if err != nil {
		return activities.StructuredELTResult{}, err
	}

	if alreadyInserted > 0 {
		if err := tx.Commit(ctx); err != nil {
			return activities.StructuredELTResult{}, fmt.Errorf("commit structured elt idempotent replay: %w", err)
		}
		committed = true
		return activities.StructuredELTResult{RowsInserted: alreadyInserted, SourceRows: sourceRows, Skipped: true}, nil
	}

	// raw is built server-side via row_to_json() over the DuckDB result set;
	// content_hash is SHA-256 (pgcrypto digest(), see sql/0001_init_extensions.sql)
	// over that same canonical JSON text — see the package comment for
	// exactly what bytes this hashes and why content_canon is NOT
	// 'h2-rawelement-v1'.
	insertSQL := fmt.Sprintf(`
WITH source_rows AS (
	SELECT row_to_json(t) AS row_data
	FROM duckdb.query($%[2]s$%[1]s$%[2]s$) AS t
),
numbered AS (
	SELECT row_data, (row_number() OVER () - 1)::int AS record_index
	FROM source_rows
),
inserted AS (
	INSERT INTO raw.raw_csv (
		source_id, device_id, acquisition_id, medium, record_index,
		raw, raw_text, content_hash, content_canon, parser_version, ingest_run_id
	)
	SELECT
		$1::uuid,
		NULLIF($2, '')::uuid,
		NULLIF($3, '')::uuid,
		COALESCE(NULLIF($4, ''), 'export')::evidence.record_medium,
		record_index,
		row_data::jsonb,
		NULL,
		encode(digest(convert_to(row_data::text, 'UTF8'), 'sha256'), 'hex'),
		%[3]s,
		%[4]s,
		$5::uuid
	FROM numbered
	RETURNING 1
)
SELECT count(*)::bigint FROM inserted;`,
		readerExpr, eltDuckDBQuoteTag, sqlStringLiteral(eltRawElementDuckDBJSONCanon), sqlStringLiteral(eltParserVersion),
	)

	var rowsInserted int64
	if err := tx.QueryRow(ctx, insertSQL,
		sourceID, spec.DeviceID, spec.AcquisitionID, spec.Medium, ingestRunID,
	).Scan(&rowsInserted); err != nil {
		return activities.StructuredELTResult{}, fmt.Errorf("execute structured elt insert..select: %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return activities.StructuredELTResult{}, fmt.Errorf("commit structured elt: %w", err)
	}
	committed = true

	return activities.StructuredELTResult{RowsInserted: rowsInserted, SourceRows: sourceRows}, nil
}

// countSourceRows is the Tweak 4 reconciliation's independent second count:
// a fresh duckdb.query() over the same reader expression, never derived from
// the INSERT's own row count.
func (r *StructuredELTRepository) countSourceRows(ctx context.Context, tx pgx.Tx, readerExpr string) (int64, error) {
	countSQL := fmt.Sprintf(
		`SELECT * FROM duckdb.query($%[2]s$SELECT count(*) AS row_count FROM (%[1]s) elt_src$%[2]s$) AS c`,
		readerExpr, eltDuckDBQuoteTag,
	)
	var count int64
	if err := tx.QueryRow(ctx, countSQL).Scan(&count); err != nil {
		return 0, fmt.Errorf("count structured elt source rows: %w", err)
	}
	return count, nil
}

// duckDBReaderExpr builds the inner DuckDB SQL text passed to duckdb.query().
// The source URL cannot be bound as a normal PostgreSQL parameter (it lives
// inside a nested SQL string DuckDB itself parses), so it is escaped as a
// SQL string literal (doubled single quotes) before being embedded — the
// same escaping DuckDB's own SQL dialect uses for single-quoted strings.
//
// CSV reads pass all_varchar=true. raw.raw_csv's own live table comment is
// "Verbatim and never edited" (confirmed against the deployed schema, not
// just the sql/ bootstrap file, 2026-09-02): read_csv_auto's default type
// sniffing would coerce e.g. "4.0" to a numeric JSON value or reformat
// dates, which is a decode/normalization step this landing table's own
// contract forbids happening before the row is stored. all_varchar defers
// every type decision to the (separate, later) normalization stage, exactly
// like the platform's H1->H2->H3->normalize hash ordering. NDJSON is not
// given the same treatment: unlike CSV, JSON already carries the source's
// own explicit per-value typing (a JSON number was authored as a number),
// so read_json_auto has no equivalent verbatim-vs-inferred ambiguity to
// correct for.
func duckDBReaderExpr(format activities.StructuredELTFormat, url string) (string, error) {
	if strings.TrimSpace(url) == "" {
		return "", errors.New("structured elt requires a non-empty source url")
	}
	escaped := strings.ReplaceAll(url, "'", "''")
	switch format {
	case activities.StructuredELTFormatCSV:
		return fmt.Sprintf("SELECT * FROM read_csv_auto('%s', all_varchar=true)", escaped), nil
	case activities.StructuredELTFormatNDJSON:
		return fmt.Sprintf("SELECT * FROM read_json_auto('%s', format='newline_delimited')", escaped), nil
	default:
		return "", fmt.Errorf("structured elt format %q is not csv or ndjson", format)
	}
}

// sqlStringLiteral quotes a Go-controlled constant for direct embedding in
// generated SQL text. Only ever called with the two package-level constants
// above — never with caller input.
func sqlStringLiteral(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "''") + "'"
}

func validateOptionalUUID(s, name string) error {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	if _, err := uuid.Parse(s); err != nil {
		return fmt.Errorf("structured elt %s: %w", name, err)
	}
	return nil
}

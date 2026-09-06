// Package activities: this file implements ExecuteStructuredELT, the
// pg_duckdb-backed set-based structured-ELT Activity for BUILD LANE E1
// (Tweak 4 / H-07 / D-080 / D-123). It is deliberately NOT yet registered as
// a stagegraph.StageID member — ProfferWorkflow wiring is a
// follow-up left to the workflow layer (see the BUILD LANE E1 handoff for
// the exact diff profferworker/worker.go still needs).
//
// Byline: Claude Code · Sonnet 5 · 2026-09-02
package activities

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

// StructuredELTFormat is the DuckDB reader family this Activity selects.
// Only the two formats named by the BUILD LANE E1 deliverable are supported;
// any other value is a hard validation error, never a silent no-op.
type StructuredELTFormat string

const (
	StructuredELTFormatCSV    StructuredELTFormat = "csv"
	StructuredELTFormatNDJSON StructuredELTFormat = "ndjson"
)

// ExecuteStructuredELTActivityName is the Temporal registration name for
// this Activity. It intentionally does not live in stagegraph.StageID yet
// (see the package comment above).
const ExecuteStructuredELTActivityName = "execute_structured_elt_activity"

// StructuredELTSpec is the compact, already-resolved input to
// ExecuteStructuredELT, following the same compact-spec-struct shape as
// ParserExecutionSpec / RawGenerationSpec elsewhere in this package.
// SourceURL must be reachable from INSIDE the PostgreSQL server process
// itself (pg_duckdb's httpfs/R2 secret) — the DuckDB read happens in the
// database, never in this Go worker, so no source bytes ever cross into Go
// memory or Temporal history.
type StructuredELTSpec struct {
	RequestID     string
	Attempt       int32
	SourceID      string // evidence.source.id (uuid, required)
	DeviceID      string // registry.device.id (uuid, optional)
	AcquisitionID string // evidence.acquisition.id (uuid, optional)
	IngestRunID   string // idempotent-replay coordinate (uuid, required)
	Medium        string // evidence.record_medium; empty uses the column default ('export')
	SourceURL     string // path/URL passed to read_csv_auto/read_json_auto verbatim
	Format        StructuredELTFormat
}

func (s StructuredELTSpec) validate() error {
	if strings.TrimSpace(s.RequestID) == "" {
		return errors.New("structured elt requires a request id")
	}
	if strings.TrimSpace(s.SourceID) == "" {
		return errors.New("structured elt requires source_id")
	}
	if strings.TrimSpace(s.IngestRunID) == "" {
		return errors.New("structured elt requires ingest_run_id for idempotent retries")
	}
	if strings.TrimSpace(s.SourceURL) == "" {
		return errors.New("structured elt requires a source url readable by read_csv_auto/read_json_auto")
	}
	switch s.Format {
	case StructuredELTFormatCSV, StructuredELTFormatNDJSON:
	default:
		return fmt.Errorf("structured elt format %q is not csv or ndjson", s.Format)
	}
	return nil
}

// StructuredELTResult is the Tweak 4 coverage count-back. RowsInserted and
// SourceRows are both independently derived by the repository (the second
// duckdb.query() count, per the deliverable) so a mismatch is a real,
// surfaced reconciliation finding rather than something silently trusted
// from one side only. Skipped is true when a prior attempt already
// persisted rows for the same IngestRunID (idempotent replay) — see the
// package comment on the scope of that guard.
type StructuredELTResult struct {
	RowsInserted int64
	SourceRows   int64
	Skipped      bool
}

// StructuredELTRepository is the PostgreSQL/pg_duckdb boundary for
// ExecuteStructuredELT. Implementations must resolve the DuckDB read and the
// INSERT as one bounded PostgreSQL transaction — the httpfs/R2 read runs
// server-side inside that one statement, so no Go-held transaction or
// connection spans slow external I/O (D-089's short-transaction discipline;
// see docs/DECISION_LOG.md).
type StructuredELTRepository interface {
	ExecuteStructuredELT(context.Context, StructuredELTSpec) (StructuredELTResult, error)
}

// StructuredELTActivities implements the ExecuteStructuredELT Activity body.
// Attempt is injectable for tests and defaults to one; a Temporal worker
// binds it to activity.GetInfo(ctx).Attempt like every other Activities
// struct in this package (see NewStructuredELTActivities in register.go).
type StructuredELTActivities struct {
	Repository StructuredELTRepository
	Attempt    Attempt
}

func (a StructuredELTActivities) validate() error {
	if a.Repository == nil {
		return errors.New("structured elt activities: repository is required")
	}
	return nil
}

func (a StructuredELTActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

// ExecuteStructuredELT loads one structured (CSV or NDJSON) source through
// pg_duckdb directly into raw.raw_csv as one set-based INSERT..SELECT — no
// row-at-a-time Go loop ever touches a source record — then returns the
// Tweak 4 reconciliation count-back. A rows-inserted/source-rows mismatch is
// a hard error: this Activity never silently under-persists a source.
func (a StructuredELTActivities) ExecuteStructuredELT(ctx context.Context, spec StructuredELTSpec) (StructuredELTResult, error) {
	if err := a.validate(); err != nil {
		return StructuredELTResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return StructuredELTResult{}, err
	}
	spec.Attempt = a.attempt(ctx)
	if err := spec.validate(); err != nil {
		return StructuredELTResult{}, err
	}
	result, err := a.Repository.ExecuteStructuredELT(ctx, spec)
	if err != nil {
		return StructuredELTResult{}, fmt.Errorf("execute structured elt: %w", err)
	}
	if result.RowsInserted != result.SourceRows {
		return StructuredELTResult{}, fmt.Errorf(
			"structured elt coverage mismatch: raw.raw_csv holds %d rows for this run, duckdb counted %d source rows",
			result.RowsInserted, result.SourceRows,
		)
	}
	return result, nil
}

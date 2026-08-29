// Byline: Codex · GPT-5.6 · 2026-08-29 (durable UIW preview store tests)
package postgres

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/runtimeapi/previewmodel"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

type nestedPreviewTestDB struct{ tx pgx.Tx }

func (db nestedPreviewTestDB) BeginTx(ctx context.Context, _ pgx.TxOptions) (pgx.Tx, error) {
	return db.tx.Begin(ctx)
}
func (db nestedPreviewTestDB) Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error) {
	return db.tx.Query(ctx, sql, args...)
}
func (db nestedPreviewTestDB) QueryRow(ctx context.Context, sql string, args ...any) pgx.Row {
	return db.tx.QueryRow(ctx, sql, args...)
}

func TestNewUIWPreviewStoreRequiresDatabase(t *testing.T) {
	if _, err := NewUIWPreviewStore(nil, nil); err == nil {
		t.Fatal("nil database accepted")
	}
	if _, err := NewUIWPreviewStore(testDB{}, strings.NewReader(strings.Repeat("x", 64))); err != nil {
		t.Fatalf("valid preview store rejected: %v", err)
	}
}

func TestPreviewDecisionKeyIsDeterministicAndCoordinateBound(t *testing.T) {
	base := decisionKey("handle", true, "reason", "actor", uiw.Ref("selection"), uiw.Ref("options"))
	if base != decisionKey("handle", true, "reason", "actor", uiw.Ref("selection"), uiw.Ref("options")) {
		t.Fatal("decision key is not deterministic")
	}
	variants := [][6]string{
		{"other", "true", "reason", "actor", "selection", "options"},
		{"handle", "false", "reason", "actor", "selection", "options"},
		{"handle", "true", "other", "actor", "selection", "options"},
		{"handle", "true", "reason", "other", "selection", "options"},
		{"handle", "true", "reason", "actor", "other", "options"},
		{"handle", "true", "reason", "actor", "selection", "other"},
	}
	for _, variant := range variants {
		approved := variant[1] == "true"
		if base == decisionKey(variant[0], approved, variant[2], variant[3], uiw.Ref(variant[4]), uiw.Ref(variant[5])) {
			t.Fatalf("decision key ignored coordinate %+v", variant)
		}
	}
}

func TestMigration0050RollbackOnlyOnPostgreSQL18(t *testing.T) {
	dsn := strings.TrimSpace(os.Getenv("PLATFORM_0050_TEST_DSN"))
	if dsn == "" {
		t.Skip("PLATFORM_0050_TEST_DSN is not configured")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	var major string
	if err := pool.QueryRow(ctx, `SELECT current_setting('server_version_num')::int / 10000`).Scan(&major); err != nil {
		t.Fatal(err)
	}
	if major != "18" {
		t.Fatalf("migration rehearsal requires PostgreSQL 18, got %s", major)
	}
	migrationPath := filepath.Join("..", "..", "sql", "0050_uiw_preview_projection_store.sql")
	body, err := os.ReadFile(migrationPath)
	if err != nil {
		t.Fatal(err)
	}
	sql := strings.TrimSpace(string(body))
	sql = strings.TrimSpace(strings.TrimPrefix(sql, "-- Migration 0050: durable opaque UIW preview projection store.\n-- Reference-only operator projection; no source or normalized payload bytes enter workflow history.\n-- Byline: Codex · GPT-5.6 · 2026-08-29.\n\nBEGIN;"))
	sql = strings.TrimSpace(strings.TrimSuffix(sql, "COMMIT;"))
	tx, err := pool.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if rollbackErr := tx.Rollback(context.Background()); rollbackErr != nil && !errors.Is(rollbackErr, context.Canceled) {
			// pgx reports ErrTxClosed after a test failure that closed the tx.
		}
	}()
	if _, err := tx.Exec(ctx, sql); err != nil {
		t.Fatalf("apply migration 0050 in rollback-only transaction: %v", err)
	}
	var relation string
	if err := tx.QueryRow(ctx, `SELECT to_regclass('context.uiw_preview_binding')::text`).Scan(&relation); err != nil {
		t.Fatal(err)
	}
	if relation != "context.uiw_preview_binding" && relation != "uiw_preview_binding" {
		t.Fatalf("migration relation = %q", relation)
	}
	store, err := NewUIWPreviewStore(nestedPreviewTestDB{tx: tx}, strings.NewReader(strings.Repeat("abcdefghijklmnopqrstuvwx", 8)))
	if err != nil {
		t.Fatal(err)
	}
	binding, err := store.Create(ctx, previewmodel.Binding{
		RequestID: "request-0050", SourceRef: "upload://source", WorkflowID: "workflow-0050",
		RunID: "run-0050", ParserOptionsRef: "options-0050",
	})
	if err != nil {
		t.Fatal(err)
	}
	duplicate, err := store.Create(ctx, previewmodel.Binding{
		RequestID: "request-0050", SourceRef: "upload://source", WorkflowID: "workflow-0050",
		RunID: "run-0050", ParserOptionsRef: "options-0050",
	})
	if err != nil || duplicate.Handle != binding.Handle {
		t.Fatalf("idempotent binding = %+v, %v; want handle %s", duplicate, err, binding.Handle)
	}
	if _, err := store.Snapshot(ctx, binding.Handle); !errors.Is(err, previewmodel.ErrNotReady) {
		t.Fatalf("unpublished snapshot error = %v", err)
	}
	if err := store.RecordDecision(ctx, binding.Handle, false, "repair required", "actor-1", "selection-1", "options-1"); err != nil {
		t.Fatal(err)
	}
	if err := store.RecordDecision(ctx, binding.Handle, false, "repair required", "actor-1", "selection-1", "options-1"); err != nil {
		t.Fatal(err)
	}
	events, err := store.EventsAfter(ctx, binding.Handle, -1)
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 2 || events[0].EventID != 0 || events[1].EventID != 1 {
		t.Fatalf("idempotent event replay = %+v", events)
	}
}

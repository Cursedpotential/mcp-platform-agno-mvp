package postgres

// This file implements the PostgreSQL side of the two parser Activities.  It
// stores only compact immutable Activity receipts: parser output is streamed
// to the injected bundle writer and never enters Temporal history or this
// repository's in-memory state.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

// BundleWriterFactory is the only parser-output persistence dependency.  The
// factory must return a streaming, caller-owned writer; this store never
// buffers a complete extraction bundle.
type BundleWriterFactory func(context.Context, uiw.StageRequest, activities.PersistedParserSelection, parser.ParserInput) (parser.BundleWriter, error)

// ParserStore persists parser selection and execution receipts using the
// tables introduced by SQL 0036.  It intentionally has no parser-output
// tables: the injected BundleWriter owns that immutable bundle store.
type ParserStore struct {
	db      DB
	factory BundleWriterFactory
	clock   func() time.Time
}

func NewParserStore(db DB, factory BundleWriterFactory) (*ParserStore, error) {
	if db == nil {
		return nil, errors.New("postgres parser store: database is required")
	}
	if factory == nil {
		return nil, errors.New("postgres parser store: bundle writer factory is required")
	}
	return &ParserStore{db: db, factory: factory, clock: func() time.Time { return time.Now().UTC() }}, nil
}

// ParserRepository is retained as a descriptive alias for callers that name
// PostgreSQL adapters repositories rather than stores.
type ParserRepository = ParserStore

func NewParserRepository(db DB, factory BundleWriterFactory) (*ParserRepository, error) {
	return NewParserStore(db, factory)
}

func (s *ParserStore) PersistParserSelection(ctx context.Context, spec activities.ParserSelectionSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validateSelectionSpec(spec); err != nil {
		return "", "", err
	}
	sourceID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	tx, err := s.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin parser selection transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	var workflowID, sourceFormat, status string
	if err := tx.QueryRow(ctx, `
		SELECT workflow_id, declared_format, status
		FROM context.source_version WHERE id = $1::uuid`, sourceID).Scan(&workflowID, &sourceFormat, &status); err != nil {
		rollback()
		return "", "", fmt.Errorf("read parser selection source version: %w", err)
	}
	if workflowID != spec.RequestID {
		rollback()
		return "", "", fmt.Errorf("request id %q does not match source workflow id %q", spec.RequestID, workflowID)
	}
	if status != "retained" {
		rollback()
		return "", "", fmt.Errorf("parser selection requires retained source version, got %q", status)
	}
	if sourceFormat != string(spec.DeclaredFormat) {
		rollback()
		return "", "", fmt.Errorf("declared format %q does not match source version format %q", spec.DeclaredFormat, sourceFormat)
	}
	executionID, err := parserEnsureExecution(ctx, tx, sourceID, spec.RequestID, string(stagegraph.SelectParser), selectionIdempotencyKey(spec))
	if err != nil {
		rollback()
		return "", "", err
	}
	var priorID uuid.UUID
	var priorResult []byte
	err = tx.QueryRow(ctx, `
		SELECT id, result_ref
		FROM context.activity_receipt
		WHERE activity_execution_id = $1::uuid AND status = 'success'
		ORDER BY attempt DESC LIMIT 1`, executionID).Scan(&priorID, &priorResult)
	if err == nil {
		selection, err := decodeSelectionReceipt(priorID, priorResult, sourceID)
		if err != nil {
			rollback()
			return "", "", err
		}
		if selection.ParserID != spec.ParserID || selection.ParserVersion != spec.ParserVersion || selection.DeclaredFormat != spec.DeclaredFormat {
			rollback()
			return "", "", errors.New("existing parser selection receipt conflicts with requested selection")
		}
		rollback()
		return uiw.Ref(priorID.String()), uiw.Ref(priorID.String()), nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		rollback()
		return "", "", fmt.Errorf("inspect parser selection receipts: %w", err)
	}
	receiptID := uuid.New()
	result := selectionResultJSON(receiptID, spec.ParserID, spec.ParserVersion, spec.DeclaredFormat)
	now := s.now()
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt
		    (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write parser selection receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit parser selection receipt: %w", err)
	}
	return uiw.Ref(receiptID.String()), uiw.Ref(receiptID.String()), nil
}

func (s *ParserStore) LoadParserSelection(ctx context.Context, ref uiw.Ref) (activities.PersistedParserSelection, error) {
	receiptID, err := parseUUIDRef(ref, "parser selection")
	if err != nil {
		return activities.PersistedParserSelection{}, err
	}
	var sourceID uuid.UUID
	var status, activityName, workflowID string
	var result []byte
	if err := s.db.QueryRow(ctx, `
		SELECT execution.source_version_id, source.status, execution.activity_name,
		       execution.workflow_id, receipt.result_ref
		FROM context.activity_receipt receipt
		JOIN context.activity_execution execution ON execution.id = receipt.activity_execution_id
		JOIN context.source_version source ON source.id = execution.source_version_id
		WHERE receipt.id = $1::uuid AND receipt.status = 'success'`, receiptID).Scan(&sourceID, &status, &activityName, &workflowID, &result); err != nil {
		return activities.PersistedParserSelection{}, fmt.Errorf("load parser selection receipt %q: %w", ref, err)
	}
	if status != "retained" || activityName != string(stagegraph.SelectParser) || strings.TrimSpace(workflowID) == "" {
		return activities.PersistedParserSelection{}, errors.New("parser selection receipt is not a retained select-parser execution")
	}
	return decodeSelectionReceipt(receiptID, result, sourceID)
}

func (s *ParserStore) ResolveParserInput(ctx context.Context, req uiw.StageRequest, selection activities.PersistedParserSelection) (parser.ParserInput, error) {
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return parser.ParserInput{}, errors.New("resolve parser input requires request and source references")
	}
	if selection.SourceVersionRef != req.SourceVersionRef {
		return parser.ParserInput{}, errors.New("parser selection belongs to a different source version")
	}
	original := req.Refs["original"]
	originalID, err := parseUUIDRef(original, "original")
	if err != nil {
		return parser.ParserInput{}, err
	}
	sourceID, err := uuid.Parse(string(req.SourceVersionRef))
	if err != nil {
		return parser.ParserInput{}, fmt.Errorf("source version reference %q: %w", req.SourceVersionRef, err)
	}
	var workflowID, sourceStatus, sourceFormat, storageClass, objectURI, contentHash string
	if err := s.db.QueryRow(ctx, `
		SELECT source.workflow_id, source.status, source.declared_format,
		       object.storage_class, object.object_uri, encode(object.content_sha256, 'hex')
		FROM context.source_version source
		JOIN context.retained_object object ON object.id = source.original_object_id
		WHERE source.id = $1::uuid AND source.original_object_id = $2::uuid`, sourceID, originalID).Scan(
		&workflowID, &sourceStatus, &sourceFormat, &storageClass, &objectURI, &contentHash); err != nil {
		return parser.ParserInput{}, fmt.Errorf("resolve retained parser input: %w", err)
	}
	if workflowID != req.RequestID || sourceStatus != "retained" {
		return parser.ParserInput{}, errors.New("parser input source is not retained by this workflow")
	}
	if sourceFormat != string(selection.DeclaredFormat) || sourceFormat != req.DeclaredFormat {
		return parser.ParserInput{}, errors.New("parser input format does not match source and selection")
	}
	input := parser.ParserInput{
		ContractVersion:  parser.ContractVersion,
		SourceVersionRef: string(req.SourceVersionRef),
		FileOrMember: parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{
			StorageClass: storageClass, URI: objectURI, ContentHash: contentHash,
		}},
		DeclaredFormat:   selection.DeclaredFormat,
		ParserOptionsRef: strings.TrimSpace(string(req.Refs["parser_options"])),
	}
	if err := input.Validate(); err != nil {
		return parser.ParserInput{}, fmt.Errorf("resolved parser input: %w", err)
	}
	return input, nil
}

func (s *ParserStore) OpenParserBundleWriter(ctx context.Context, req uiw.StageRequest, selection activities.PersistedParserSelection, input parser.ParserInput) (parser.BundleWriter, error) {
	if selection.SourceVersionRef != req.SourceVersionRef {
		return nil, errors.New("parser bundle writer selection/source mismatch")
	}
	if input.SourceVersionRef != string(req.SourceVersionRef) || input.DeclaredFormat != selection.DeclaredFormat {
		return nil, errors.New("parser bundle writer input does not match selection")
	}
	if err := input.Validate(); err != nil {
		return nil, err
	}
	writer, err := s.factory(ctx, req, selection, input)
	if err != nil {
		return nil, fmt.Errorf("create parser bundle writer: %w", err)
	}
	if writer == nil {
		return nil, errors.New("bundle writer factory returned nil")
	}
	return writer, nil
}

func (s *ParserStore) PersistParserExecution(ctx context.Context, spec activities.ParserExecutionSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validateExecutionSpec(spec); err != nil {
		return "", "", err
	}
	sourceID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	selectionID, err := parseUUIDRef(spec.ParserSelectionRef, "parser selection")
	if err != nil {
		return "", "", err
	}
	tx, err := s.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin parser execution transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	var workflowID, status string
	if err := tx.QueryRow(ctx, `SELECT workflow_id, status FROM context.source_version WHERE id = $1::uuid`, sourceID).Scan(&workflowID, &status); err != nil {
		rollback()
		return "", "", fmt.Errorf("read parser execution source version: %w", err)
	}
	if workflowID != spec.RequestID || status != "retained" {
		rollback()
		return "", "", errors.New("parser execution requires retained source owned by request")
	}
	if err := verifySelectionTx(ctx, tx, selectionID, sourceID, spec.ParserID, spec.ParserVersion); err != nil {
		rollback()
		return "", "", err
	}
	executionID, err := parserEnsureExecution(ctx, tx, sourceID, spec.RequestID, string(stagegraph.ExecuteParser), executionIdempotencyKey(spec))
	if err != nil {
		rollback()
		return "", "", err
	}
	var priorID uuid.UUID
	var priorResult []byte
	err = tx.QueryRow(ctx, `
		SELECT id, result_ref FROM context.activity_receipt
		WHERE activity_execution_id = $1::uuid AND status = 'success'
		ORDER BY attempt DESC LIMIT 1`, executionID).Scan(&priorID, &priorResult)
	if err == nil {
		bundleRef, err := decodeBundleResult(priorResult)
		if err != nil {
			rollback()
			return "", "", err
		}
		if bundleRef != spec.BundleRef {
			rollback()
			return "", "", errors.New("existing parser execution receipt conflicts with bundle reference")
		}
		rollback()
		return bundleRef, uiw.Ref(priorID.String()), nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		rollback()
		return "", "", fmt.Errorf("inspect parser execution receipts: %w", err)
	}
	receiptID := uuid.New()
	result := bundleResultJSON(spec.BundleRef)
	now := s.now()
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt
		    (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write parser execution receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit parser execution receipt: %w", err)
	}
	return spec.BundleRef, uiw.Ref(receiptID.String()), nil
}

func (s *ParserStore) now() time.Time {
	if s.clock == nil {
		return time.Now().UTC()
	}
	return s.clock().UTC()
}

func parserEnsureExecution(ctx context.Context, tx pgx.Tx, sourceID uuid.UUID, requestID, activityName, key string) (uuid.UUID, error) {
	var id uuid.UUID
	err := tx.QueryRow(ctx, `
		INSERT INTO context.activity_execution (source_version_id, workflow_id, activity_name, idempotency_key)
		VALUES ($1::uuid, $2, $3, $4)
		ON CONFLICT (source_version_id, activity_name, idempotency_key) DO NOTHING
		RETURNING id`, sourceID, requestID, activityName, key).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		err = tx.QueryRow(ctx, `
			SELECT id FROM context.activity_execution
			WHERE source_version_id = $1::uuid AND activity_name = $2 AND idempotency_key = $3`, sourceID, activityName, key).Scan(&id)
	}
	if err != nil {
		return uuid.Nil, fmt.Errorf("ensure %s activity execution: %w", activityName, err)
	}
	return id, nil
}

func verifySelectionTx(ctx context.Context, tx pgx.Tx, receiptID, sourceID uuid.UUID, parserID, parserVersion string) error {
	var sourceFromReceipt uuid.UUID
	var sourceStatus, activityName string
	var result []byte
	if err := tx.QueryRow(ctx, `
		SELECT execution.source_version_id, source.status, execution.activity_name, receipt.result_ref
		FROM context.activity_receipt receipt
		JOIN context.activity_execution execution ON execution.id = receipt.activity_execution_id
		JOIN context.source_version source ON source.id = execution.source_version_id
		WHERE receipt.id = $1::uuid AND receipt.status = 'success'`, receiptID).Scan(&sourceFromReceipt, &sourceStatus, &activityName, &result); err != nil {
		return fmt.Errorf("verify parser selection receipt: %w", err)
	}
	if sourceFromReceipt != sourceID || sourceStatus != "retained" || activityName != string(stagegraph.SelectParser) {
		return errors.New("parser selection receipt is not owned by the execution source")
	}
	selection, err := decodeSelectionReceipt(receiptID, result, sourceID)
	if err != nil {
		return err
	}
	if selection.ParserID != parserID || selection.ParserVersion != parserVersion {
		return errors.New("parser execution identity does not match persisted parser selection")
	}
	return nil
}

type selectionResult struct {
	RefKind        string `json:"ref_kind"`
	RefID          string `json:"ref_id"`
	ParserID       string `json:"parser_id"`
	ParserVersion  string `json:"parser_version"`
	DeclaredFormat string `json:"declared_format"`
}

func selectionResultJSON(receiptID uuid.UUID, parserID, version string, format parser.FormatID) []byte {
	result, _ := json.Marshal(selectionResult{RefKind: "parser_selection", RefID: receiptID.String(), ParserID: parserID, ParserVersion: version, DeclaredFormat: string(format)})
	return result
}

func decodeSelectionReceipt(receiptID uuid.UUID, raw []byte, sourceID uuid.UUID) (activities.PersistedParserSelection, error) {
	var result selectionResult
	if err := json.Unmarshal(raw, &result); err != nil {
		return activities.PersistedParserSelection{}, fmt.Errorf("decode parser selection result: %w", err)
	}
	if result.RefKind != "parser_selection" || result.RefID != receiptID.String() || strings.TrimSpace(result.ParserID) == "" || strings.TrimSpace(result.ParserVersion) == "" {
		return activities.PersistedParserSelection{}, errors.New("parser selection result is incomplete or mutable")
	}
	format := parser.FormatID(result.DeclaredFormat)
	if err := format.Validate(); err != nil {
		return activities.PersistedParserSelection{}, fmt.Errorf("parser selection format: %w", err)
	}
	return activities.PersistedParserSelection{SourceVersionRef: uiw.Ref(sourceID.String()), DeclaredFormat: format, ParserID: result.ParserID, ParserVersion: result.ParserVersion}, nil
}

type bundleResult struct {
	RefKind string `json:"ref_kind"`
	RefID   string `json:"ref_id"`
}

func bundleResultJSON(ref uiw.Ref) []byte {
	result, _ := json.Marshal(bundleResult{RefKind: "parser_bundle", RefID: string(ref)})
	return result
}

func decodeBundleResult(raw []byte) (uiw.Ref, error) {
	var result bundleResult
	if err := json.Unmarshal(raw, &result); err != nil {
		return "", fmt.Errorf("decode parser execution result: %w", err)
	}
	if result.RefKind != "parser_bundle" || strings.TrimSpace(result.RefID) == "" {
		return "", errors.New("parser execution result is incomplete")
	}
	return uiw.Ref(result.RefID), nil
}

func validateSelectionSpec(spec activities.ParserSelectionSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.Attempt < 1 {
		return errors.New("parser selection requires request, source, and positive attempt")
	}
	if strings.TrimSpace(spec.ParserID) == "" || strings.TrimSpace(spec.ParserVersion) == "" {
		return errors.New("parser selection requires parser id and version")
	}
	return spec.DeclaredFormat.Validate()
}

func validateExecutionSpec(spec activities.ParserExecutionSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.ParserSelectionRef == "" || spec.Attempt < 1 {
		return errors.New("parser execution requires request, source, selection, and positive attempt")
	}
	if strings.TrimSpace(spec.ParserID) == "" || strings.TrimSpace(spec.ParserVersion) == "" || strings.TrimSpace(string(spec.BundleRef)) == "" {
		return errors.New("parser execution requires parser identity and bundle reference")
	}
	return nil
}

func parseUUIDRef(ref uiw.Ref, name string) (uuid.UUID, error) {
	id, err := uuid.Parse(strings.TrimSpace(string(ref)))
	if err != nil {
		return uuid.Nil, fmt.Errorf("%s reference %q must be a UUID: %w", name, ref, err)
	}
	return id, nil
}

func selectionIdempotencyKey(spec activities.ParserSelectionSpec) string {
	return fmt.Sprintf("parser-selection:%s:%s:%s", spec.RequestID, spec.SourceVersionRef, spec.DeclaredFormat)
}

func executionIdempotencyKey(spec activities.ParserExecutionSpec) string {
	return fmt.Sprintf("parser-execution:%s:%s:%s", spec.RequestID, spec.SourceVersionRef, spec.ParserSelectionRef)
}

var _ activities.ParserActivityStore = (*ParserStore)(nil)

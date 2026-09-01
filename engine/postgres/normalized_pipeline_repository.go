// This file is the PostgreSQL boundary for the seven normalized-side
// Activities in engine/activities/normalized_pipeline.go. It follows
// hash_repository.go and parser_activity_store.go's existing shape exactly:
// every write goes through context.activity_execution/context.activity_receipt
// for retry-safe idempotency, every generation/lineage write relies on the
// sql/0036 guard triggers as the sole fail-closed authority rather than
// reimplementing their checks, and normalized-record bytes are never
// buffered as a full-generation Go slice — records stream through short,
// bounded transactions one at a time.
package postgres

import (
	"bytes"
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/normalize"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

// NormalizedBundleWriterFactory opens the caller-owned streaming sink that
// normalize_generation_activity writes to. This repository has no
// bundle-bytes persistence authority of its own, mirroring ParserStore's
// BundleWriterFactory in parser_activity_store.go.
type NormalizedBundleWriterFactory func(context.Context, uiw.StageRequest, normalize.NormalizerInput) (normalize.BundleWriter, error)

// NormalizedBundleReader streams the finalized bundle produced by
// normalize_generation_activity, exactly as it was written. Header returns
// the identity persist_normalized_generation_activity needs (its raw
// generation and normalizer identity) without a separate lookup.
type NormalizedBundleReader interface {
	Header() normalize.BundleHeader
	Next(context.Context) (normalize.RecordEnvelope, error)
	Close() error
}

// NormalizedBundleReaderFactory resolves a bundle reference minted by the
// OpenNormalizedBundleWriter writer back to a streaming reader.
type NormalizedBundleReaderFactory func(context.Context, uiw.Ref) (NormalizedBundleReader, error)

// NormalizedPipelineRepository implements activities.NormalizedPipelineStore.
type NormalizedPipelineRepository struct {
	db            DB
	writerFactory NormalizedBundleWriterFactory
	readerFactory NormalizedBundleReaderFactory
	clock         func() time.Time
}

func NewNormalizedPipelineRepository(db DB, writerFactory NormalizedBundleWriterFactory, readerFactory NormalizedBundleReaderFactory) (*NormalizedPipelineRepository, error) {
	if db == nil {
		return nil, errors.New("postgres normalized pipeline repository: database is required")
	}
	if writerFactory == nil {
		return nil, errors.New("postgres normalized pipeline repository: bundle writer factory is required")
	}
	if readerFactory == nil {
		return nil, errors.New("postgres normalized pipeline repository: bundle reader factory is required")
	}
	return &NormalizedPipelineRepository{
		db: db, writerFactory: writerFactory, readerFactory: readerFactory,
		clock: func() time.Time { return time.Now().UTC() },
	}, nil
}

func (r *NormalizedPipelineRepository) now() time.Time {
	if r.clock == nil {
		return time.Now().UTC()
	}
	return r.clock().UTC()
}

// ResolveNormalizerInput opens a streaming view over the already-sealed raw
// generation and resolves the source-version-level facts (provenance class,
// acquired_at) normalize.Adapter needs but must never guess.
func (r *NormalizedPipelineRepository) ResolveNormalizerInput(ctx context.Context, req uiw.StageRequest) (normalize.NormalizerInput, error) {
	sourceVersionID, err := uuid.Parse(string(req.SourceVersionRef))
	if err != nil {
		return normalize.NormalizerInput{}, fmt.Errorf("source version reference %q: %w", req.SourceVersionRef, err)
	}
	rawGenerationRef := req.Refs["raw_generation"]
	rawGenerationID, err := uuid.Parse(string(rawGenerationRef))
	if err != nil {
		return normalize.NormalizerInput{}, fmt.Errorf("raw generation reference %q: %w", rawGenerationRef, err)
	}
	var workflowID, declaredFormat, sourceStatus, provenanceClass, rawStatus string
	var rawSourceVersionID uuid.UUID
	var acquiredAt time.Time
	if err := r.db.QueryRow(ctx, `
		SELECT version.workflow_id, version.declared_format, version.status, source.provenance_class,
		       version.acquired_at, raw.status, raw.source_version_id
		FROM context.source_version version
		JOIN context.source source ON source.id = version.source_id
		JOIN context.raw_generation raw ON raw.id = $2::uuid
		WHERE version.id = $1::uuid`, sourceVersionID, rawGenerationID).Scan(
		&workflowID, &declaredFormat, &sourceStatus, &provenanceClass, &acquiredAt, &rawStatus, &rawSourceVersionID); err != nil {
		return normalize.NormalizerInput{}, fmt.Errorf("resolve normalizer input: %w", err)
	}
	if workflowID != req.RequestID {
		return normalize.NormalizerInput{}, errors.New("normalizer input request id does not own the source version")
	}
	if sourceStatus != "retained" {
		return normalize.NormalizerInput{}, fmt.Errorf("normalizer input requires a retained source version, got %q", sourceStatus)
	}
	if rawStatus != "sealed" {
		return normalize.NormalizerInput{}, fmt.Errorf("normalizer input requires a sealed raw generation, got %q", rawStatus)
	}
	if rawSourceVersionID != sourceVersionID {
		return normalize.NormalizerInput{}, errors.New("raw generation belongs to a different source version")
	}
	rows, err := r.db.Query(ctx, `
		SELECT record_ordinal, format_id, record_status, native_fields, native_metadata
		FROM context.raw_record_identity
		WHERE raw_generation_id = $1::uuid
		ORDER BY record_ordinal`, rawGenerationID)
	if err != nil {
		return normalize.NormalizerInput{}, fmt.Errorf("open raw records for normalize: %w", err)
	}
	return normalize.NormalizerInput{
		ContractVersion:       normalize.ContractVersion,
		SourceVersionRef:      string(req.SourceVersionRef),
		RawGenerationRef:      string(rawGenerationRef),
		DeclaredFormat:        parser.FormatID(declaredFormat),
		SourceProvenanceClass: normalize.ProvenanceClass(provenanceClass),
		AcquiredAt:            acquiredAt,
		Records:               &rawRecordRows{rows: rows},
	}, nil
}

type rawRecordRows struct {
	rows   pgx.Rows
	closed bool
}

func (s *rawRecordRows) Next(ctx context.Context) (normalize.RawRecordView, error) {
	if s.closed {
		return normalize.RawRecordView{}, io.EOF
	}
	if err := ctx.Err(); err != nil {
		return normalize.RawRecordView{}, err
	}
	if !s.rows.Next() {
		if err := s.rows.Err(); err != nil {
			return normalize.RawRecordView{}, err
		}
		return normalize.RawRecordView{}, io.EOF
	}
	var ordinal int64
	var formatID, status string
	var nativeFields, nativeMetadata []byte
	if err := s.rows.Scan(&ordinal, &formatID, &status, &nativeFields, &nativeMetadata); err != nil {
		return normalize.RawRecordView{}, err
	}
	return normalize.RawRecordView{
		RecordOrdinal: uint64(ordinal), FormatID: parser.FormatID(formatID), RecordStatus: parser.RecordStatus(status),
		NativeFields: nativeFields, NativeMetadata: nativeMetadata,
	}, nil
}

func (s *rawRecordRows) Close() error {
	if !s.closed {
		s.closed = true
		s.rows.Close()
	}
	return nil
}

// OpenNormalizedBundleWriter delegates to the injected factory; this
// repository has no bundle-bytes storage engine of its own.
func (r *NormalizedPipelineRepository) OpenNormalizedBundleWriter(ctx context.Context, req uiw.StageRequest, input normalize.NormalizerInput) (normalize.BundleWriter, error) {
	if input.SourceVersionRef != string(req.SourceVersionRef) {
		return nil, errors.New("normalized bundle writer input does not match request")
	}
	if err := input.Validate(); err != nil {
		return nil, err
	}
	writer, err := r.writerFactory(ctx, req, input)
	if err != nil {
		return nil, fmt.Errorf("create normalized bundle writer: %w", err)
	}
	if writer == nil {
		return nil, errors.New("normalized bundle writer factory returned nil")
	}
	return writer, nil
}

func (r *NormalizedPipelineRepository) PersistNormalizeExecution(ctx context.Context, spec activities.NormalizeExecutionSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validateNormalizeExecutionSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	rawGenerationID, err := uuid.Parse(string(spec.RawGenerationRef))
	if err != nil {
		return "", "", fmt.Errorf("raw generation reference %q: %w", spec.RawGenerationRef, err)
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.NormalizeGeneration), normalizeExecutionKey(spec), "normalized_bundle")
	if err != nil {
		return "", "", err
	}
	if found {
		if priorRef != spec.BundleRef {
			return "", "", errors.New("existing normalize execution receipt conflicts with bundle reference")
		}
		return priorRef, priorReceipt, nil
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin normalize execution transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var workflowID, status string
	if err := tx.QueryRow(ctx, `SELECT workflow_id, status FROM context.source_version WHERE id = $1::uuid`, sourceVersionID).Scan(&workflowID, &status); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalize execution source version: %w", err)
	}
	if workflowID != spec.RequestID || status != "retained" {
		rollback()
		return "", "", errors.New("normalize execution requires retained source owned by request")
	}
	var rawStatus string
	var rawSourceVersionID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT status, source_version_id FROM context.raw_generation WHERE id = $1::uuid`, rawGenerationID).Scan(&rawStatus, &rawSourceVersionID); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalize execution raw generation: %w", err)
	}
	if rawStatus != "sealed" || rawSourceVersionID != sourceVersionID {
		rollback()
		return "", "", errors.New("normalize execution requires a sealed raw generation owned by this source version")
	}

	receiptID := uuid.New()
	result := normalizedRefJSON("normalized_bundle", string(spec.BundleRef))
	now := r.now()
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write normalize execution receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit normalize execution receipt: %w", err)
	}
	return spec.BundleRef, uiw.Ref(receiptID.String()), nil
}

// PersistNormalizedGeneration is the only write for
// context.normalized_generation and context.normalized_record_identity.
func (r *NormalizedPipelineRepository) PersistNormalizedGeneration(ctx context.Context, spec activities.PersistNormalizedGenerationSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validatePersistNormalizedGenerationSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}

	reader, err := r.readerFactory(ctx, spec.BundleRef)
	if err != nil {
		return "", "", fmt.Errorf("open normalized bundle reader: %w", err)
	}
	if reader == nil {
		return "", "", errors.New("normalized bundle reader factory returned nil")
	}
	defer reader.Close()
	header := reader.Header()
	if header.ContractVersion != normalize.ContractVersion {
		return "", "", fmt.Errorf("unsupported normalized bundle contract version %q", header.ContractVersion)
	}
	if header.SourceVersionRef != string(spec.SourceVersionRef) {
		return "", "", errors.New("normalized bundle belongs to a different source version")
	}
	if strings.TrimSpace(header.NormalizerID) == "" || strings.TrimSpace(header.NormalizerVersion) == "" {
		return "", "", errors.New("normalized bundle lacks normalizer identity")
	}
	rawGenerationID, err := uuid.Parse(header.RawGenerationRef)
	if err != nil {
		return "", "", fmt.Errorf("normalized bundle raw generation reference %q: %w", header.RawGenerationRef, err)
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.PersistNormalizedGeneration), persistNormalizedGenerationKey(spec), "normalized_generation")
	if err != nil {
		return "", "", err
	}
	if found {
		return priorRef, priorReceipt, nil
	}

	generationID, err := r.ensureOpenNormalizedGeneration(ctx, sourceVersionID, rawGenerationID, header.NormalizerID, header.NormalizerVersion)
	if err != nil {
		return "", "", err
	}

	var count int64
	for {
		if err := ctx.Err(); err != nil {
			return "", "", err
		}
		record, nextErr := reader.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return "", "", fmt.Errorf("read normalized bundle record %d: %w", count, nextErr)
		}
		if int64(record.RecordOrdinal) != count {
			return "", "", fmt.Errorf("normalized bundle record ordinal %d, want %d", record.RecordOrdinal, count)
		}
		if err := r.persistNormalizedRecord(ctx, generationID, sourceVersionID, spec.SourceVersionRef, record); err != nil {
			return "", "", fmt.Errorf("persist normalized record %d: %w", count, err)
		}
		count++
	}
	if count == 0 {
		return "", "", errors.New("persist normalized generation refuses to persist zero records")
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin persist normalized generation completion transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	var durableCount int64
	if err := tx.QueryRow(ctx, `SELECT count(*) FROM context.normalized_record_identity WHERE normalized_generation_id = $1::uuid`, generationID).Scan(&durableCount); err != nil {
		rollback()
		return "", "", fmt.Errorf("count durable normalized records: %w", err)
	}
	if durableCount != count {
		rollback()
		return "", "", fmt.Errorf("durable normalized record count %d disagrees with streamed count %d", durableCount, count)
	}
	receiptID := uuid.New()
	result := normalizedRefJSON("normalized_generation", generationID.String())
	now := r.now()
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write persist normalized generation receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit persist normalized generation receipt: %w", err)
	}
	return uiw.Ref(generationID.String()), uiw.Ref(receiptID.String()), nil
}

// ensureOpenNormalizedGeneration creates or recovers the one open
// normalized_generation row for this exact (source, raw generation,
// normalizer identity) tuple, so a retried persist attempt resumes the same
// generation instead of minting a duplicate.
func (r *NormalizedPipelineRepository) ensureOpenNormalizedGeneration(ctx context.Context, sourceVersionID, rawGenerationID uuid.UUID, normalizerID, normalizerVersion string) (uuid.UUID, error) {
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return uuid.Nil, fmt.Errorf("begin ensure normalized generation transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var id uuid.UUID
	err = tx.QueryRow(ctx, `
		SELECT id FROM context.normalized_generation
		WHERE source_version_id = $1::uuid AND raw_generation_id = $2::uuid
		  AND normalizer_id = $3 AND normalizer_version = $4 AND status = 'open'
		LIMIT 1`, sourceVersionID, rawGenerationID, normalizerID, normalizerVersion).Scan(&id)
	if err == nil {
		rollback()
		return id, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		rollback()
		return uuid.Nil, fmt.Errorf("inspect open normalized generation: %w", err)
	}

	newID := uuid.New()
	err = tx.QueryRow(ctx, `
		INSERT INTO context.normalized_generation
		    (id, source_version_id, raw_generation_id, generation_ordinal, normalizer_id, normalizer_version)
		SELECT $1::uuid, $2::uuid, $3::uuid, COALESCE(MAX(generation_ordinal), 0) + 1, $4, $5
		FROM context.normalized_generation WHERE source_version_id = $2::uuid
		ON CONFLICT (source_version_id, generation_ordinal) DO NOTHING
		RETURNING id`, newID, sourceVersionID, rawGenerationID, normalizerID, normalizerVersion).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		// Lost an ordinal-assignment race; recover the row the winner created.
		rollback()
		return r.recoverOpenNormalizedGeneration(ctx, sourceVersionID, rawGenerationID, normalizerID, normalizerVersion)
	}
	if err != nil {
		rollback()
		return uuid.Nil, fmt.Errorf("create normalized generation: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return uuid.Nil, fmt.Errorf("commit create normalized generation: %w", err)
	}
	return id, nil
}

func (r *NormalizedPipelineRepository) recoverOpenNormalizedGeneration(ctx context.Context, sourceVersionID, rawGenerationID uuid.UUID, normalizerID, normalizerVersion string) (uuid.UUID, error) {
	var id uuid.UUID
	if err := r.db.QueryRow(ctx, `
		SELECT id FROM context.normalized_generation
		WHERE source_version_id = $1::uuid AND raw_generation_id = $2::uuid
		  AND normalizer_id = $3 AND normalizer_version = $4
		ORDER BY generation_ordinal DESC LIMIT 1`, sourceVersionID, rawGenerationID, normalizerID, normalizerVersion).Scan(&id); err != nil {
		return uuid.Nil, fmt.Errorf("recover normalized generation after ordinal race: %w", err)
	}
	return id, nil
}

func (r *NormalizedPipelineRepository) persistNormalizedRecord(ctx context.Context, generationID, sourceVersionID uuid.UUID, sourceVersionRef uiw.Ref, record normalize.RecordEnvelope) error {
	if err := record.Validate(); err != nil {
		return err
	}
	recordID := uuid.New()
	payload, err := buildNormalizedPayload(recordID, sourceVersionRef, record)
	if err != nil {
		return err
	}
	var occurredAt any
	if record.OccurredAt != nil {
		occurredAt = record.OccurredAt.UTC()
	}
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return err
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.normalized_record_identity
		    (id, normalized_generation_id, source_version_id, record_ordinal, record_type, occurred_at,
		     canonical_bytes, canonicalization, normalized_payload)
		VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6,
		        convert_to($7::jsonb::text, 'UTF8'), $8, $7::jsonb)
		ON CONFLICT (normalized_generation_id, record_ordinal) DO NOTHING`,
		recordID, generationID, sourceVersionID, int64(record.RecordOrdinal), string(record.RecordType), occurredAt,
		payload, activities.CanonNormalizedRecord); err != nil {
		rollback()
		return fmt.Errorf("insert normalized record: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return err
	}
	return nil
}

func buildNormalizedPayload(recordID uuid.UUID, sourceVersionRef uiw.Ref, record normalize.RecordEnvelope) ([]byte, error) {
	participants := make([]map[string]any, 0, len(record.Participants))
	for _, p := range record.Participants {
		entry := map[string]any{"role": string(p.Role), "identifier": p.Identifier}
		if p.DisplayName != "" {
			entry["display_name"] = p.DisplayName
		}
		participants = append(participants, entry)
	}
	payload := map[string]any{
		"contract_version":      normalize.ContractVersion,
		"normalized_record_id":  recordID.String(),
		"record_type":           string(record.RecordType),
		"source_version_ref":    string(sourceVersionRef),
		"timestamp_granularity": string(record.TimestampGranularity),
		"timestamp_certainty":   string(record.TimestampCertainty),
		"source_available_from": record.SourceAvailableFrom.UTC().Format(time.RFC3339Nano),
		"provenance_class":      string(record.ProvenanceClass),
		"participants":          participants,
	}
	if record.OccurredAt != nil {
		payload["occurred_at"] = record.OccurredAt.UTC().Format(time.RFC3339Nano)
	} else {
		payload["occurred_at"] = nil
	}
	if record.OccurredAtRaw != "" {
		payload["occurred_at_raw"] = record.OccurredAtRaw
	}
	if len(record.Content) > 0 {
		var content any
		if err := json.Unmarshal(record.Content, &content); err != nil {
			return nil, fmt.Errorf("decode record content: %w", err)
		}
		payload["content"] = content
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("encode normalized payload: %w", err)
	}
	return encoded, nil
}

// PersistLineage is the only write for context.normalization_lineage. It
// derives lineage purely by zipping the ordered parsed-raw-record sequence
// against the ordered normalized-record sequence for this generation — see
// normalize.GenericMessageNormalizer's doc comment for why that
// correspondence is guaranteed 1:1 and order-preserving.
func (r *NormalizedPipelineRepository) PersistLineage(ctx context.Context, spec activities.PersistLineageSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validatePersistLineageSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	normalizedGenerationID, err := uuid.Parse(string(spec.NormalizedGenerationRef))
	if err != nil {
		return "", "", fmt.Errorf("normalized generation reference %q: %w", spec.NormalizedGenerationRef, err)
	}
	rawGenerationID, err := uuid.Parse(string(spec.RawGenerationRef))
	if err != nil {
		return "", "", fmt.Errorf("raw generation reference %q: %w", spec.RawGenerationRef, err)
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.PersistLineage), persistLineageKey(spec), "lineage_set")
	if err != nil {
		return "", "", err
	}
	if found {
		return priorRef, priorReceipt, nil
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin persist lineage transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var normSourceVersionID, normRawGenerationID uuid.UUID
	var normStatus, normalizerID, normalizerVersion string
	if err := tx.QueryRow(ctx, `
		SELECT source_version_id, raw_generation_id, status, normalizer_id, normalizer_version
		FROM context.normalized_generation WHERE id = $1::uuid`, normalizedGenerationID).Scan(
		&normSourceVersionID, &normRawGenerationID, &normStatus, &normalizerID, &normalizerVersion); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation for lineage: %w", err)
	}
	if normSourceVersionID != sourceVersionID || normRawGenerationID != rawGenerationID {
		rollback()
		return "", "", errors.New("normalized generation does not belong to the given source/raw generation")
	}
	if normStatus != "open" {
		rollback()
		return "", "", fmt.Errorf("persist lineage requires an open normalized generation, got %q", normStatus)
	}

	rawIDs, err := queryOrderedIDs(ctx, tx, `
		SELECT id FROM context.raw_record_identity
		WHERE raw_generation_id = $1::uuid AND record_status = 'parsed'
		ORDER BY record_ordinal`, rawGenerationID)
	if err != nil {
		rollback()
		return "", "", fmt.Errorf("read parsed raw records for lineage: %w", err)
	}
	normIDs, err := queryOrderedIDs(ctx, tx, `
		SELECT id FROM context.normalized_record_identity
		WHERE normalized_generation_id = $1::uuid ORDER BY record_ordinal`, normalizedGenerationID)
	if err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized records for lineage: %w", err)
	}
	if len(normIDs) == 0 {
		rollback()
		return "", "", errors.New("persist lineage refuses to run over zero normalized records")
	}
	if len(rawIDs) != len(normIDs) {
		rollback()
		return "", "", fmt.Errorf("parsed raw record count %d does not match normalized record count %d", len(rawIDs), len(normIDs))
	}

	for i := range normIDs {
		if _, err := tx.Exec(ctx, `
			INSERT INTO context.normalization_lineage
			    (normalized_generation_id, raw_generation_id, normalized_record_id, raw_record_id,
			     derivation_role, field_map, normalizer_id, normalizer_version)
			VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'primary_source', '[]'::jsonb, $5, $6)
			ON CONFLICT (normalized_record_id, raw_record_id, derivation_role) DO NOTHING`,
			normalizedGenerationID, rawGenerationID, normIDs[i], rawIDs[i], normalizerID, normalizerVersion); err != nil {
			rollback()
			return "", "", fmt.Errorf("insert lineage edge %d: %w", i, err)
		}
	}

	receiptID := uuid.New()
	result := normalizedRefJSON("lineage_set", normalizedGenerationID.String())
	now := r.now()
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write persist lineage receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit persist lineage receipt: %w", err)
	}
	return uiw.Ref(lineageSetPrefix + normalizedGenerationID.String()), uiw.Ref(receiptID.String()), nil
}

func queryOrderedIDs(ctx context.Context, tx pgx.Tx, query string, arg uuid.UUID) ([]uuid.UUID, error) {
	rows, err := tx.Query(ctx, query, arg)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []uuid.UUID
	for rows.Next() {
		var id uuid.UUID
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return ids, nil
}

const lineageSetPrefix = "lineage_set:"

func parseLineageSetRef(ref uiw.Ref) (uuid.UUID, error) {
	s := string(ref)
	if !strings.HasPrefix(s, lineageSetPrefix) {
		return uuid.Nil, fmt.Errorf("lineage set reference %q must be prefixed %q", ref, lineageSetPrefix)
	}
	id, err := uuid.Parse(strings.TrimPrefix(s, lineageSetPrefix))
	if err != nil {
		return uuid.Nil, fmt.Errorf("lineage set reference %q has an invalid generation id: %w", ref, err)
	}
	return id, nil
}

// ValidateRawLineage independently recomputes lineage coverage (every
// normalized record has at least one edge; every edge's raw record belongs
// to this generation's own raw generation) rather than trusting the sql/0036
// insert-time guard alone, and records a context.reconciliation_receipt of
// kind raw_lineage_validation.
func (r *NormalizedPipelineRepository) ValidateRawLineage(ctx context.Context, spec activities.ValidateRawLineageSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validateValidateRawLineageSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	normalizedGenerationID, err := parseLineageSetRef(spec.LineageSetRef)
	if err != nil {
		return "", "", err
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.ValidateRawLineage), validateRawLineageKey(spec), "reconciliation_receipt")
	if err != nil {
		return "", "", err
	}
	if found {
		return priorRef, priorReceipt, nil
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin validate raw lineage transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var normSourceVersionID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT source_version_id FROM context.normalized_generation WHERE id = $1::uuid`, normalizedGenerationID).Scan(&normSourceVersionID); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation for lineage validation: %w", err)
	}
	if normSourceVersionID != sourceVersionID {
		rollback()
		return "", "", errors.New("normalized generation does not belong to this source version")
	}

	var totalRecords, missingLineage int64
	if err := tx.QueryRow(ctx, `
		SELECT count(*),
		       count(*) FILTER (WHERE NOT EXISTS (
		           SELECT 1 FROM context.normalization_lineage lineage
		           WHERE lineage.normalized_record_id = normalized.id))
		FROM context.normalized_record_identity normalized
		WHERE normalized.normalized_generation_id = $1::uuid`, normalizedGenerationID).Scan(&totalRecords, &missingLineage); err != nil {
		rollback()
		return "", "", fmt.Errorf("count lineage coverage: %w", err)
	}
	var mismatchedRawGeneration int64
	if err := tx.QueryRow(ctx, `
		SELECT count(*)
		FROM context.normalization_lineage lineage
		JOIN context.raw_record_identity raw ON raw.id = lineage.raw_record_id
		JOIN context.normalized_generation generation ON generation.id = lineage.normalized_generation_id
		WHERE lineage.normalized_generation_id = $1::uuid
		  AND raw.raw_generation_id <> generation.raw_generation_id`, normalizedGenerationID).Scan(&mismatchedRawGeneration); err != nil {
		rollback()
		return "", "", fmt.Errorf("count raw generation mismatches: %w", err)
	}

	expected := map[string]any{"normalized_record_count": totalRecords, "records_missing_lineage": int64(0), "raw_generation_mismatches": int64(0)}
	observed := map[string]any{"normalized_record_count": totalRecords, "records_missing_lineage": missingLineage, "raw_generation_mismatches": mismatchedRawGeneration}
	var discrepancies []map[string]any
	status := "success"
	if missingLineage > 0 {
		status = "failed"
		discrepancies = append(discrepancies, map[string]any{
			"field": "records_missing_lineage", "expected": 0, "observed": missingLineage,
			"explanation": "one or more normalized records have no raw lineage edge",
		})
	}
	if mismatchedRawGeneration > 0 {
		status = "failed"
		discrepancies = append(discrepancies, map[string]any{
			"field": "raw_generation_mismatches", "expected": 0, "observed": mismatchedRawGeneration,
			"explanation": "one or more lineage edges reference a raw record outside this normalized generation's own raw generation",
		})
	}

	reconciliationID := uuid.New()
	receiptID := uuid.New()
	now := r.now()
	result := normalizedRefJSON("reconciliation_receipt", reconciliationID.String())
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write validate raw lineage activity receipt: %w", err)
	}
	expectedJSON, _ := json.Marshal(expected)
	observedJSON, _ := json.Marshal(observed)
	discrepanciesJSON, _ := json.Marshal(emptyIfNil(discrepancies))
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.reconciliation_receipt
		    (id, activity_receipt_id, reconciliation_kind, normalized_generation_id, status, expected, observed, discrepancies, verified_at)
		VALUES ($1::uuid, $2::uuid, 'raw_lineage_validation', $3::uuid, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8)`,
		reconciliationID, receiptID, normalizedGenerationID, status, expectedJSON, observedJSON, discrepanciesJSON, now); err != nil {
		rollback()
		return "", "", fmt.Errorf("write raw lineage reconciliation receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit raw lineage reconciliation receipt: %w", err)
	}
	if status != "success" {
		return "", "", fmt.Errorf("raw lineage validation failed: %d record(s) missing lineage, %d mismatched raw generation reference(s)", missingLineage, mismatchedRawGeneration)
	}
	return uiw.Ref(reconciliationID.String()), uiw.Ref(receiptID.String()), nil
}

func emptyIfNil(discrepancies []map[string]any) []map[string]any {
	if discrepancies == nil {
		return []map[string]any{}
	}
	return discrepancies
}

// OpenNormalizedGenerationRecords streams every normalized_record_identity
// row's canonical_bytes, in ordinal order, for the generation named by the
// manifest-digest hash-receipt registry. It never computes or returns a
// digest itself — verify_normalized_generation_activity independently
// rehashes each member.
func (r *NormalizedPipelineRepository) OpenNormalizedGenerationRecords(ctx context.Context, manifestDigestRef uiw.Ref) (activities.ByteMemberStream, error) {
	hashReceiptID, err := uuid.Parse(string(manifestDigestRef))
	if err != nil {
		return nil, fmt.Errorf("normalized generation manifest digest reference %q: %w", manifestDigestRef, err)
	}
	var normalizedGenerationID uuid.UUID
	if err := r.db.QueryRow(ctx, `
		SELECT normalized_generation_id FROM context.hash_receipt
		WHERE id = $1::uuid AND hash_kind = 'normalized_generation_manifest_digest'`, hashReceiptID).Scan(&normalizedGenerationID); err != nil {
		return nil, fmt.Errorf("resolve normalized generation for manifest digest %q: %w", manifestDigestRef, err)
	}
	rows, err := r.db.Query(ctx, `
		SELECT id::text, record_ordinal, canonicalization, canonical_bytes
		FROM context.normalized_record_identity
		WHERE normalized_generation_id = $1::uuid ORDER BY record_ordinal`, normalizedGenerationID)
	if err != nil {
		return nil, fmt.Errorf("open normalized generation records: %w", err)
	}
	return &normalizedGenerationRows{rows: rows}, nil
}

type normalizedGenerationRows struct {
	rows   pgx.Rows
	closed bool
}

func (s *normalizedGenerationRows) Next(ctx context.Context) (activities.ByteMember, error) {
	if s.closed {
		return activities.ByteMember{}, io.EOF
	}
	if err := ctx.Err(); err != nil {
		return activities.ByteMember{}, err
	}
	if !s.rows.Next() {
		if err := s.rows.Err(); err != nil {
			return activities.ByteMember{}, err
		}
		return activities.ByteMember{}, io.EOF
	}
	var ref string
	var ordinal int64
	var canon string
	var canonical []byte
	if err := s.rows.Scan(&ref, &ordinal, &canon, &canonical); err != nil {
		return activities.ByteMember{}, err
	}
	return activities.ByteMember{SubjectRef: uiw.Ref(ref), Ordinal: ordinal, Canon: canon, Reader: io.NopCloser(bytes.NewReader(canonical))}, nil
}

func (s *normalizedGenerationRows) Close() error {
	if !s.closed {
		s.closed = true
		s.rows.Close()
	}
	return nil
}

// VerifyNormalizedGeneration persists the Activity's already-independently-
// recomputed normalized-generation manifest digest against the stored
// hash_receipt, and records a context.reconciliation_receipt of kind
// normalized_generation_verification. It never recomputes a digest itself.
func (r *NormalizedPipelineRepository) VerifyNormalizedGeneration(ctx context.Context, spec activities.VerifyNormalizedGenerationSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validateVerifyNormalizedGenerationSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	lineageValidationID, err := uuid.Parse(string(spec.LineageValidationRef))
	if err != nil {
		return "", "", fmt.Errorf("lineage validation reference %q: %w", spec.LineageValidationRef, err)
	}
	hashReceiptID, err := uuid.Parse(string(spec.ManifestDigestRef))
	if err != nil {
		return "", "", fmt.Errorf("manifest digest reference %q: %w", spec.ManifestDigestRef, err)
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.VerifyNormalizedGeneration), verifyNormalizedGenerationKey(spec), "reconciliation_receipt")
	if err != nil {
		return "", "", err
	}
	if found {
		return priorRef, priorReceipt, nil
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin verify normalized generation transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var lineageGenID uuid.UUID
	var lineageStatus string
	if err := tx.QueryRow(ctx, `
		SELECT normalized_generation_id, status FROM context.reconciliation_receipt
		WHERE id = $1::uuid AND reconciliation_kind = 'raw_lineage_validation'`, lineageValidationID).Scan(&lineageGenID, &lineageStatus); err != nil {
		rollback()
		return "", "", fmt.Errorf("read lineage validation receipt: %w", err)
	}
	if lineageStatus != "success" {
		rollback()
		return "", "", errors.New("verify normalized generation requires a successful raw lineage validation")
	}

	var storedDigestBytes []byte
	var storedConstruction string
	var manifestGenID uuid.UUID
	if err := tx.QueryRow(ctx, `
		SELECT digest, construction, normalized_generation_id FROM context.hash_receipt
		WHERE id = $1::uuid AND hash_kind = 'normalized_generation_manifest_digest'`, hashReceiptID).Scan(
		&storedDigestBytes, &storedConstruction, &manifestGenID); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation manifest digest receipt: %w", err)
	}
	if lineageGenID != manifestGenID {
		rollback()
		return "", "", errors.New("lineage validation and manifest digest receipts reference different normalized generations")
	}
	var genSourceVersionID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT source_version_id FROM context.normalized_generation WHERE id = $1::uuid`, manifestGenID).Scan(&genSourceVersionID); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation for verification: %w", err)
	}
	if genSourceVersionID != sourceVersionID {
		rollback()
		return "", "", errors.New("normalized generation does not belong to this source version")
	}

	storedDigest := hex.EncodeToString(storedDigestBytes)
	status := "success"
	var discrepancies []map[string]any
	if storedDigest != spec.RecomputedDigest || storedConstruction != spec.RecomputedConstruction {
		status = "failed"
		discrepancies = append(discrepancies, map[string]any{
			"field": "normalized_generation_manifest_digest", "expected": spec.RecomputedDigest, "observed": storedDigest,
			"explanation": "independently recomputed normalized generation manifest digest does not match the stored hash receipt",
		})
	}
	expected := map[string]any{
		"normalized_generation_manifest_digest": spec.RecomputedDigest,
		"verification_mode":                     "independent_recomputation",
		"member_count":                          spec.RecomputedMemberCount,
		"construction":                          spec.RecomputedConstruction,
	}
	observed := map[string]any{
		"normalized_generation_manifest_digest": storedDigest,
		"verification_mode":                     "independent_recomputation",
		"construction":                          storedConstruction,
	}

	reconciliationID := uuid.New()
	receiptID := uuid.New()
	now := r.now()
	result := normalizedRefJSON("reconciliation_receipt", reconciliationID.String())
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write verify normalized generation activity receipt: %w", err)
	}
	expectedJSON, _ := json.Marshal(expected)
	observedJSON, _ := json.Marshal(observed)
	discrepanciesJSON, _ := json.Marshal(emptyIfNil(discrepancies))
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.reconciliation_receipt
		    (id, activity_receipt_id, reconciliation_kind, normalized_generation_id, status, expected, observed, discrepancies, verified_at)
		VALUES ($1::uuid, $2::uuid, 'normalized_generation_verification', $3::uuid, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8)`,
		reconciliationID, receiptID, manifestGenID, status, expectedJSON, observedJSON, discrepanciesJSON, now); err != nil {
		rollback()
		return "", "", fmt.Errorf("write normalized generation verification receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit normalized generation verification receipt: %w", err)
	}
	if status != "success" {
		return "", "", fmt.Errorf("normalized generation verification failed: recomputed digest %s does not match stored digest %s", spec.RecomputedDigest, storedDigest)
	}
	return uiw.Ref(reconciliationID.String()), uiw.Ref(receiptID.String()), nil
}

// SealGeneration advances context.normalized_generation open -> sealed. The
// sql/0036 guard_normalized_generation_transition trigger is the sole
// fail-closed authority for every precondition; this method never bypasses
// it with a partial or forced seal.
func (r *NormalizedPipelineRepository) SealGeneration(ctx context.Context, spec activities.SealGenerationSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validateSealGenerationSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	reconciliationID, err := uuid.Parse(string(spec.VerificationRef))
	if err != nil {
		return "", "", fmt.Errorf("verification reference %q: %w", spec.VerificationRef, err)
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.SealGeneration), sealGenerationKey(spec), "normalized_generation")
	if err != nil {
		return "", "", err
	}
	if found {
		return priorRef, priorReceipt, nil
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin seal generation transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var normalizedGenerationID uuid.UUID
	var verifyStatus string
	if err := tx.QueryRow(ctx, `
		SELECT normalized_generation_id, status FROM context.reconciliation_receipt
		WHERE id = $1::uuid AND reconciliation_kind = 'normalized_generation_verification'`, reconciliationID).Scan(&normalizedGenerationID, &verifyStatus); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation verification receipt: %w", err)
	}
	if verifyStatus != "success" {
		rollback()
		return "", "", errors.New("seal generation requires a successful normalized generation verification")
	}
	var genSourceVersionID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT source_version_id FROM context.normalized_generation WHERE id = $1::uuid`, normalizedGenerationID).Scan(&genSourceVersionID); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation for seal: %w", err)
	}
	if genSourceVersionID != sourceVersionID {
		rollback()
		return "", "", errors.New("normalized generation does not belong to this source version")
	}

	receiptID := uuid.New()
	now := r.now()
	result := normalizedRefJSON("normalized_generation", normalizedGenerationID.String())
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write seal generation activity receipt: %w", err)
	}
	tag, err := tx.Exec(ctx, `
		UPDATE context.normalized_generation SET status = 'sealed', sealed_at = $2, sealed_by = $3
		WHERE id = $1::uuid AND status = 'open'`, normalizedGenerationID, now, string(stagegraph.SealGeneration))
	if err != nil {
		rollback()
		return "", "", fmt.Errorf("seal normalized generation: %w", err)
	}
	if tag.RowsAffected() == 0 {
		var status string
		if err := tx.QueryRow(ctx, `SELECT status FROM context.normalized_generation WHERE id = $1::uuid`, normalizedGenerationID).Scan(&status); err != nil {
			rollback()
			return "", "", fmt.Errorf("recheck normalized generation seal status: %w", err)
		}
		if status != "sealed" {
			rollback()
			return "", "", fmt.Errorf("normalized generation seal did not apply, status is %q", status)
		}
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit seal normalized generation: %w", err)
	}
	return uiw.Ref(normalizedGenerationID.String()), uiw.Ref(receiptID.String()), nil
}

// PublishGeneration is the sole successor of seal_generation_activity. It
// never publishes without a durable context.normalized_generation_publication
// row and its successful activity_receipt, matching the sql/0036
// guard_normalized_publication and normalized_generation_seal_publish_gate
// triggers exactly.
func (r *NormalizedPipelineRepository) PublishGeneration(ctx context.Context, spec activities.PublishGenerationSpec) (uiw.Ref, uiw.Ref, error) {
	if err := validatePublishGenerationSpec(spec); err != nil {
		return "", "", err
	}
	sourceVersionID, err := uuid.Parse(string(spec.SourceVersionRef))
	if err != nil {
		return "", "", fmt.Errorf("source version reference %q: %w", spec.SourceVersionRef, err)
	}
	normalizedGenerationID, err := uuid.Parse(string(spec.SealedGenerationRef))
	if err != nil {
		return "", "", fmt.Errorf("sealed generation reference %q: %w", spec.SealedGenerationRef, err)
	}

	executionID, priorRef, priorReceipt, found, err := r.ensureExecutionAndCheckPrior(
		ctx, sourceVersionID, spec.RequestID, string(stagegraph.PublishGeneration), publishGenerationKey(spec), "normalized_generation_publication")
	if err != nil {
		return "", "", err
	}
	if found {
		return priorRef, priorReceipt, nil
	}

	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin publish generation transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }

	var status string
	var genSourceVersionID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT status, source_version_id FROM context.normalized_generation WHERE id = $1::uuid`, normalizedGenerationID).Scan(&status, &genSourceVersionID); err != nil {
		rollback()
		return "", "", fmt.Errorf("read normalized generation for publish: %w", err)
	}
	if genSourceVersionID != sourceVersionID {
		rollback()
		return "", "", errors.New("normalized generation does not belong to this source version")
	}
	if status != "sealed" {
		rollback()
		return "", "", fmt.Errorf("publish generation requires a sealed normalized generation, got %q", status)
	}

	publicationID := uuid.New()
	receiptID := uuid.New()
	now := r.now()
	result := normalizedRefJSON("normalized_generation_publication", publicationID.String())
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, executionID, spec.Attempt, now, now, result); err != nil {
		rollback()
		return "", "", fmt.Errorf("write publish generation activity receipt: %w", err)
	}
	publicationRef, err := json.Marshal(map[string]any{
		"published_by": string(stagegraph.PublishGeneration), "normalized_generation_id": normalizedGenerationID.String(),
	})
	if err != nil {
		rollback()
		return "", "", err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.normalized_generation_publication
		    (id, normalized_generation_id, activity_receipt_id, idempotency_key, publication_ref, published_at)
		VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::jsonb, $6)`,
		publicationID, normalizedGenerationID, receiptID, publishGenerationKey(spec), publicationRef, now); err != nil {
		rollback()
		return "", "", fmt.Errorf("insert normalized generation publication: %w", err)
	}
	tag, err := tx.Exec(ctx, `
		UPDATE context.normalized_generation SET status = 'published', published_at = $2
		WHERE id = $1::uuid AND status = 'sealed'`, normalizedGenerationID, now)
	if err != nil {
		rollback()
		return "", "", fmt.Errorf("publish normalized generation: %w", err)
	}
	if tag.RowsAffected() == 0 {
		rollback()
		return "", "", errors.New("normalized generation publish did not apply")
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return "", "", fmt.Errorf("commit publish normalized generation: %w", err)
	}
	return uiw.Ref(publicationID.String()), uiw.Ref(receiptID.String()), nil
}

// ensureExecutionAndCheckPrior creates or recovers one
// context.activity_execution row and, if a successful receipt already
// exists for it, returns that receipt's decoded (ref_id, receipt id). Every
// one of this repository's seven persistence methods shares this one
// retry-recovery path.
func (r *NormalizedPipelineRepository) ensureExecutionAndCheckPrior(
	ctx context.Context, sourceVersionID uuid.UUID, requestID, activityName, key, expectRefKind string,
) (executionID uuid.UUID, priorRef uiw.Ref, priorReceipt uiw.Ref, found bool, err error) {
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return uuid.Nil, "", "", false, fmt.Errorf("begin %s execution transaction: %w", activityName, err)
	}
	committed := false
	defer func() {
		if !committed {
			cleanupCtx, cancel := boundedCleanup(ctx)
			defer cancel()
			_ = tx.Rollback(cleanupCtx)
		}
	}()

	executionID, err = parserEnsureExecution(ctx, tx, sourceVersionID, requestID, activityName, key)
	if err != nil {
		return uuid.Nil, "", "", false, err
	}
	receiptID, resultJSON, has, err := normalizeLatestReceipt(ctx, tx, executionID)
	if err != nil {
		return uuid.Nil, "", "", false, err
	}
	if !has {
		if err := tx.Commit(ctx); err != nil {
			return uuid.Nil, "", "", false, fmt.Errorf("commit %s execution: %w", activityName, err)
		}
		committed = true
		return executionID, "", "", false, nil
	}
	kind, id, err := decodeNormalizedRef(resultJSON)
	if err != nil {
		return uuid.Nil, "", "", false, err
	}
	if kind != expectRefKind {
		return uuid.Nil, "", "", false, fmt.Errorf("existing %s receipt has unexpected ref kind %q, want %q", activityName, kind, expectRefKind)
	}
	if err := tx.Commit(ctx); err != nil {
		return uuid.Nil, "", "", false, fmt.Errorf("commit %s execution: %w", activityName, err)
	}
	committed = true
	return executionID, uiw.Ref(id), uiw.Ref(receiptID.String()), true, nil
}

func normalizeLatestReceipt(ctx context.Context, tx pgx.Tx, executionID uuid.UUID) (uuid.UUID, []byte, bool, error) {
	var receiptID uuid.UUID
	var resultJSON []byte
	err := tx.QueryRow(ctx, `
		SELECT id, result_ref FROM context.activity_receipt
		WHERE activity_execution_id = $1::uuid AND status = 'success'
		ORDER BY attempt DESC LIMIT 1`, executionID).Scan(&receiptID, &resultJSON)
	if errors.Is(err, pgx.ErrNoRows) {
		return uuid.Nil, nil, false, nil
	}
	if err != nil {
		return uuid.Nil, nil, false, fmt.Errorf("inspect prior activity receipts: %w", err)
	}
	return receiptID, resultJSON, true, nil
}

type normalizedRef struct {
	RefKind string `json:"ref_kind"`
	RefID   string `json:"ref_id"`
}

func normalizedRefJSON(kind, id string) []byte {
	encoded, _ := json.Marshal(normalizedRef{RefKind: kind, RefID: id})
	return encoded
}

func decodeNormalizedRef(raw []byte) (string, string, error) {
	var ref normalizedRef
	if err := json.Unmarshal(raw, &ref); err != nil {
		return "", "", fmt.Errorf("decode result reference: %w", err)
	}
	if strings.TrimSpace(ref.RefKind) == "" || strings.TrimSpace(ref.RefID) == "" {
		return "", "", errors.New("result reference is incomplete")
	}
	return ref.RefKind, ref.RefID, nil
}

func validateNormalizeExecutionSpec(spec activities.NormalizeExecutionSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.RawGenerationRef == "" || spec.Attempt < 1 {
		return errors.New("normalize execution requires request, source, raw generation, and positive attempt")
	}
	if strings.TrimSpace(spec.NormalizerID) == "" || strings.TrimSpace(spec.NormalizerVersion) == "" || strings.TrimSpace(string(spec.BundleRef)) == "" {
		return errors.New("normalize execution requires normalizer identity and bundle reference")
	}
	return nil
}

func validatePersistNormalizedGenerationSpec(spec activities.PersistNormalizedGenerationSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.BundleRef == "" || spec.Attempt < 1 {
		return errors.New("persist normalized generation requires request, source, bundle, and positive attempt")
	}
	return nil
}

func validatePersistLineageSpec(spec activities.PersistLineageSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.NormalizedGenerationRef == "" || spec.RawGenerationRef == "" || spec.Attempt < 1 {
		return errors.New("persist lineage requires request, source, normalized generation, raw generation, and positive attempt")
	}
	return nil
}

func validateValidateRawLineageSpec(spec activities.ValidateRawLineageSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.LineageSetRef == "" || spec.Attempt < 1 {
		return errors.New("validate raw lineage requires request, source, lineage set, and positive attempt")
	}
	return nil
}

func validateVerifyNormalizedGenerationSpec(spec activities.VerifyNormalizedGenerationSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.LineageValidationRef == "" || spec.ManifestDigestRef == "" || spec.Attempt < 1 {
		return errors.New("verify normalized generation requires request, source, lineage validation, manifest digest, and positive attempt")
	}
	if strings.TrimSpace(spec.RecomputedDigest) == "" || strings.TrimSpace(spec.RecomputedConstruction) == "" || spec.RecomputedMemberCount < 1 {
		return errors.New("verify normalized generation requires a recomputed digest, construction, and positive member count")
	}
	return nil
}

func validateSealGenerationSpec(spec activities.SealGenerationSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.VerificationRef == "" || spec.Attempt < 1 {
		return errors.New("seal generation requires request, source, verification, and positive attempt")
	}
	return nil
}

func validatePublishGenerationSpec(spec activities.PublishGenerationSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SourceVersionRef == "" || spec.SealedGenerationRef == "" || spec.Attempt < 1 {
		return errors.New("publish generation requires request, source, sealed generation, and positive attempt")
	}
	return nil
}

func normalizeExecutionKey(spec activities.NormalizeExecutionSpec) string {
	return fmt.Sprintf("normalize-generation:%s:%s:%s", spec.RequestID, spec.SourceVersionRef, spec.RawGenerationRef)
}
func persistNormalizedGenerationKey(spec activities.PersistNormalizedGenerationSpec) string {
	return fmt.Sprintf("persist-normalized-generation:%s:%s:%s", spec.RequestID, spec.SourceVersionRef, spec.BundleRef)
}
func persistLineageKey(spec activities.PersistLineageSpec) string {
	return fmt.Sprintf("persist-lineage:%s:%s:%s", spec.RequestID, spec.NormalizedGenerationRef, spec.RawGenerationRef)
}
func validateRawLineageKey(spec activities.ValidateRawLineageSpec) string {
	return fmt.Sprintf("validate-raw-lineage:%s:%s", spec.RequestID, spec.LineageSetRef)
}
func verifyNormalizedGenerationKey(spec activities.VerifyNormalizedGenerationSpec) string {
	return fmt.Sprintf("verify-normalized-generation:%s:%s:%s", spec.RequestID, spec.LineageValidationRef, spec.ManifestDigestRef)
}
func sealGenerationKey(spec activities.SealGenerationSpec) string {
	return fmt.Sprintf("seal-generation:%s:%s", spec.RequestID, spec.VerificationRef)
}
func publishGenerationKey(spec activities.PublishGenerationSpec) string {
	return fmt.Sprintf("publish-generation:%s:%s", spec.RequestID, spec.SealedGenerationRef)
}

var _ activities.NormalizedPipelineStore = (*NormalizedPipelineRepository)(nil)

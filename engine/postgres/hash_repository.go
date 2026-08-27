// Package postgres implements the PostgreSQL storage boundary used by the
// hashing Activities. It deliberately keeps source bytes and membership out
// of Temporal history and out of Go memory beyond one stream member.
package postgres

import (
	"bytes"
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/lowcarbdev/sbv/pkg/custodyhash"
)

// DB is the small subset implemented by *pgxpool.Pool and used for reads and
// transaction creation. Keeping this seam narrow makes the adapter testable
// with pgx mocks without coupling callers to a particular pool type.
type DB interface {
	BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error)
	Query(context.Context, string, ...any) (pgx.Rows, error)
	QueryRow(context.Context, string, ...any) pgx.Row
}

// ObjectOpener resolves immutable non-inline object references. Inline
// retained objects are read directly from PostgreSQL. The opener must return
// a closer whose lifetime is the returned member reader's lifetime.
type ObjectOpener func(context.Context, string) (io.ReadCloser, error)

// Repository is a PostgreSQL-backed activities.HashRepository.
type Repository struct {
	db    DB
	open  ObjectOpener
	clock func() time.Time
}

// NewRepository constructs a repository. open may be nil when all retained
// objects are inline; non-inline objects fail closed rather than being read
// through an ungoverned path.
func NewRepository(db DB, open ObjectOpener) (*Repository, error) {
	if db == nil {
		return nil, errors.New("postgres hash repository: database is required")
	}
	return &Repository{db: db, open: open, clock: func() time.Time { return time.Now().UTC() }}, nil
}

func (r *Repository) OpenOriginal(ctx context.Context, ref uiw.Ref) (io.ReadCloser, error) {
	if err := requireRef(ref, "original"); err != nil {
		return nil, err
	}
	var storageClass, objectURI string
	var inline []byte
	err := r.db.QueryRow(ctx, `
		SELECT storage_class, object_uri, inline_bytes
		FROM context.retained_object
		WHERE id = $1::uuid`, string(ref)).Scan(&storageClass, &objectURI, &inline)
	if err != nil {
		return nil, fmt.Errorf("open retained object %q: %w", ref, err)
	}
	if storageClass == "inline" {
		return io.NopCloser(bytes.NewReader(inline)), nil
	}
	if r.open == nil {
		return nil, fmt.Errorf("non-inline object %q requires an ObjectOpener", objectURI)
	}
	return r.open(ctx, objectURI)
}

func (r *Repository) OpenRawRecords(ctx context.Context, ref uiw.Ref) (activities.ByteMemberStream, error) {
	if err := requireRef(ref, "raw generation"); err != nil {
		return nil, err
	}
	rows, err := r.db.Query(ctx, `
		SELECT raw.id::text,
		       raw.record_ordinal,
		       raw.raw_hash_construction,
		       raw.stored_bytes,
		       COALESCE(object.storage_class, ''),
		       COALESCE(object.object_uri, ''),
		       CASE WHEN object.storage_class = 'inline'
		            THEN substring(object.inline_bytes FROM raw.byte_offset + 1 FOR raw.byte_length)
		       END,
		       COALESCE(raw.byte_offset, 0),
		       COALESCE(raw.byte_length, 0)
		FROM context.raw_record_identity raw
		LEFT JOIN context.retained_object object ON object.id = raw.locator_object_id
		WHERE raw.raw_generation_id = $1::uuid
		ORDER BY raw.record_ordinal`, string(ref))
	if err != nil {
		return nil, fmt.Errorf("open raw records %q: %w", ref, err)
	}
	return &byteRows{rows: rows, open: r.open, raw: true}, nil
}

func (r *Repository) OpenNormalizedRecords(ctx context.Context, ref uiw.Ref) (activities.ByteMemberStream, error) {
	if err := requireRef(ref, "normalized generation"); err != nil {
		return nil, err
	}
	rows, err := r.db.Query(ctx, `
		SELECT id::text, record_ordinal, canonical_bytes
		FROM context.normalized_record_identity
		WHERE normalized_generation_id = $1::uuid
		ORDER BY record_ordinal`, string(ref))
	if err != nil {
		return nil, fmt.Errorf("open normalized records %q: %w", ref, err)
	}
	return &normalizedRows{rows: rows}, nil
}

func (r *Repository) OpenHashMembers(ctx context.Context, ref uiw.Ref) (activities.DigestMemberStream, error) {
	if err := requireRef(ref, "hash member receipt"); err != nil {
		return nil, err
	}
	setKind, generationID, err := parseSetRef(ref)
	if err != nil {
		return nil, err
	}
	query := `
		SELECT h.raw_record_id::text, raw.record_ordinal,
		       encode(h.digest, 'hex'), h.construction
		FROM context.hash_receipt h
		JOIN context.raw_record_identity raw ON raw.id = h.raw_record_id
		WHERE raw.raw_generation_id = $1::uuid
		  AND h.hash_kind = 'raw_record_digest'
		ORDER BY 2`
	if setKind == "normalized_hash_receipt_set" {
		query = `
			SELECT h.normalized_record_id::text, normalized.record_ordinal,
			       encode(h.digest, 'hex'), h.construction
			FROM context.hash_receipt h
			JOIN context.normalized_record_identity normalized ON normalized.id = h.normalized_record_id
			WHERE normalized.normalized_generation_id = $1::uuid
			  AND h.hash_kind = 'normalized_record_digest'
			ORDER BY 2`
	}
	rows, err := r.db.Query(ctx, query, generationID)
	if err != nil {
		return nil, fmt.Errorf("open hash members %q: %w", ref, err)
	}
	return &digestRows{rows: rows}, nil
}

func (r *Repository) BeginHashBatch(ctx context.Context, spec activities.BatchSpec) (activities.HashBatchWriter, error) {
	if err := validateSpec(spec); err != nil {
		return nil, err
	}
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return nil, fmt.Errorf("begin hash transaction: %w", err)
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	sourceVersionID, err := sourceVersionFor(ctx, tx, spec.Kind, spec.SubjectRef)
	if err != nil {
		rollback()
		return nil, err
	}
	var workflowID string
	if err := tx.QueryRow(ctx, `SELECT workflow_id FROM context.source_version WHERE id = $1::uuid`, sourceVersionID).Scan(&workflowID); err != nil {
		rollback()
		return nil, fmt.Errorf("read source workflow id: %w", err)
	}
	if workflowID != spec.RequestID {
		rollback()
		return nil, fmt.Errorf("request id %q does not match source workflow id %q", spec.RequestID, workflowID)
	}
	key := idempotencyKey(spec)
	var executionID uuid.UUID
	err = tx.QueryRow(ctx, `
		INSERT INTO context.activity_execution
		    (source_version_id, workflow_id, activity_name, idempotency_key)
		VALUES ($1::uuid, $2, $3, $4)
		ON CONFLICT (source_version_id, activity_name, idempotency_key) DO NOTHING
		RETURNING id`, sourceVersionID, spec.RequestID, string(spec.Stage), key).Scan(&executionID)
	if errors.Is(err, pgx.ErrNoRows) {
		err = tx.QueryRow(ctx, `
			SELECT id FROM context.activity_execution
			WHERE source_version_id = $1::uuid
			  AND activity_name = $2
			  AND idempotency_key = $3`, sourceVersionID, string(spec.Stage), key).Scan(&executionID)
	}
	if err != nil {
		rollback()
		return nil, fmt.Errorf("ensure activity execution: %w", err)
	}

	var receiptID uuid.UUID
	var priorKind, priorRef string
	err = tx.QueryRow(ctx, `
		SELECT receipt.id, COALESCE(receipt.result_ref->>'ref_kind', ''),
		       COALESCE(receipt.result_ref->>'ref_id', '')
		FROM context.hash_batch batch
		JOIN context.activity_receipt receipt ON receipt.id = batch.activity_receipt_id
		WHERE batch.activity_execution_id = $1::uuid
		  AND batch.status = 'completed'
		ORDER BY batch.attempt DESC
		LIMIT 1`, executionID).Scan(&receiptID, &priorKind, &priorRef)
	if err == nil {
		rollback()
		if priorKind == "" || priorRef == "" {
			return nil, errors.New("prior successful hash receipt has incomplete result reference")
		}
		return &idempotentWriter{
			db: r.db, spec: spec, priorActivityReceiptID: receiptID,
			priorRefKind: priorKind, priorRefID: priorRef,
			resultRef: priorResultRef(priorKind, priorRef), receiptRef: uiw.Ref(receiptID.String()),
		}, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		rollback()
		return nil, fmt.Errorf("inspect prior activity receipts: %w", err)
	}

	var openBatchID uuid.UUID
	var openStatus string
	var openCreatedAt time.Time
	err = tx.QueryRow(ctx, `
		SELECT id, status, created_at
		FROM context.hash_batch
		WHERE activity_execution_id = $1::uuid AND attempt = $2
		LIMIT 1`, executionID, spec.Attempt).Scan(&openBatchID, &openStatus, &openCreatedAt)
	if err == nil {
		rollback()
		if openStatus != "open" {
			return nil, fmt.Errorf("hash batch attempt %d is already %s", spec.Attempt, openStatus)
		}
		return &batchWriter{db: r.db, batchID: openBatchID, spec: spec, sourceVersionID: sourceVersionID, executionID: executionID, attempt: spec.Attempt, startedAt: openCreatedAt, clock: r.clock}, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		rollback()
		return nil, fmt.Errorf("inspect hash batch attempt: %w", err)
	}
	batchID := uuid.New()
	var rawGenerationID, normalizedGenerationID any
	if spec.Kind == activities.HashKindRawRecordDigest || spec.Kind == activities.HashKindH3RawGeneration {
		rawGenerationID = spec.SubjectRef
	} else if spec.Kind == activities.HashKindNormalizedRecordDigest || spec.Kind == activities.HashKindNormalizedGenerationDigest {
		normalizedGenerationID = spec.SubjectRef
	}
	_, err = tx.Exec(ctx, `
		INSERT INTO context.hash_batch
		    (id, activity_execution_id, source_version_id, attempt, hash_kind, raw_generation_id, normalized_generation_id)
		VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6::uuid, $7::uuid)`,
		batchID, executionID, sourceVersionID, spec.Attempt, string(spec.Kind), rawGenerationID, normalizedGenerationID)
	if err != nil {
		rollback()
		return nil, fmt.Errorf("create hash batch: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		rollback()
		return nil, fmt.Errorf("commit hash batch begin: %w", err)
	}
	return &batchWriter{
		db: r.db, batchID: batchID, spec: spec, sourceVersionID: sourceVersionID, executionID: executionID,
		attempt: spec.Attempt, startedAt: r.clock(), clock: r.clock, count: 0,
	}, nil
}

type batchWriter struct {
	db                                    DB
	spec                                  activities.BatchSpec
	batchID, sourceVersionID, executionID uuid.UUID
	attempt                               int32
	startedAt                             time.Time
	clock                                 func() time.Time
	count                                 int64
	closed                                bool
}

func (w *batchWriter) Append(ctx context.Context, member activities.HashMember) error {
	if w.closed {
		return errors.New("hash batch is closed")
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if member.SubjectRef == "" || member.Ordinal != w.count {
		return fmt.Errorf("hash member ordinal/reference mismatch at %d", w.count)
	}
	if err := validateDigest(member.Digest); err != nil {
		return err
	}
	if err := validateMemberCanon(w.spec.Kind, member.Canon); err != nil {
		return err
	}
	memberID, err := uuid.Parse(string(member.SubjectRef))
	if err != nil {
		return fmt.Errorf("hash member reference %q: %w", member.SubjectRef, err)
	}
	digest, _ := hex.DecodeString(member.Digest)
	tx, err := w.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return err
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	var existingDigest []byte
	var existingCanon string
	var existingRef uuid.UUID
	err = tx.QueryRow(ctx, `SELECT digest, construction, COALESCE(source_version_id, raw_record_id, normalized_record_id) FROM context.hash_batch_member WHERE hash_batch_id = $1::uuid AND ordinal = $2`, w.batchID, member.Ordinal).Scan(&existingDigest, &existingCanon, &existingRef)
	if err == nil {
		if !bytes.Equal(existingDigest, digest) || existingCanon != member.Canon || existingRef != memberID {
			rollback()
			return fmt.Errorf("hash member %d conflicts with durable batch member", member.Ordinal)
		}
		rollback()
		w.count++
		return nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		rollback()
		return err
	}
	column, value := "source_version_id", w.sourceVersionID
	if w.spec.Kind == activities.HashKindRawRecordDigest || w.spec.Kind == activities.HashKindH3RawGeneration {
		column, value = "raw_record_id", memberID
	}
	if w.spec.Kind == activities.HashKindNormalizedRecordDigest || w.spec.Kind == activities.HashKindNormalizedGenerationDigest {
		column, value = "normalized_record_id", memberID
	}
	query := fmt.Sprintf(`INSERT INTO context.hash_batch_member (hash_batch_id, ordinal, %s, digest, construction) VALUES ($1::uuid, $2, $3::uuid, $4, $5)`, column)
	if _, err = tx.Exec(ctx, query, w.batchID, member.Ordinal, value, digest, member.Canon); err != nil {
		rollback()
		return fmt.Errorf("stage hash member %d: %w", member.Ordinal, err)
	}
	if err = tx.Commit(ctx); err != nil {
		rollback()
		return err
	}
	w.count++
	return nil
}

func (w *batchWriter) Commit(ctx context.Context, summary activities.HashSummary) (uiw.Ref, uiw.Ref, error) {
	if w.closed {
		return "", "", errors.New("hash batch is closed")
	}
	if err := ctx.Err(); err != nil {
		return "", "", err
	}
	if w.count == 0 || summary.MemberCount != w.count {
		return "", "", fmt.Errorf("hash summary member count %d does not equal staged count %d", summary.MemberCount, w.count)
	}
	if err := validateSummary(w.spec.Kind, summary); err != nil {
		return "", "", err
	}
	tx, err := w.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", err
	}
	rollback := func() { cleanupCtx, cancel := boundedCleanup(ctx); defer cancel(); _ = tx.Rollback(cleanupCtx) }
	var status string
	var existingResult []byte
	var existingReceipt *uuid.UUID
	err = tx.QueryRow(ctx, `SELECT status, result_ref, activity_receipt_id FROM context.hash_batch WHERE id = $1::uuid FOR UPDATE`, w.batchID).Scan(&status, &existingResult, &existingReceipt)
	if err != nil {
		rollback()
		return "", "", err
	}
	if status != "open" {
		rollback()
		return "", "", fmt.Errorf("hash batch is %s", status)
	}
	var durableCount int64
	if err = tx.QueryRow(ctx, `SELECT count(*) FROM context.hash_batch_member WHERE hash_batch_id = $1::uuid`, w.batchID).Scan(&durableCount); err != nil {
		rollback()
		return "", "", fmt.Errorf("count durable hash members: %w", err)
	}
	if durableCount != w.count {
		rollback()
		return "", "", fmt.Errorf("durable hash batch count %d disagrees with writer count %d", durableCount, w.count)
	}
	receiptID, hashReceiptID := uuid.New(), uuid.New()
	resultRef, refKind, refID := w.resultReference(hashReceiptID)
	completedAt := w.clock().UTC()
	var manifestID uuid.UUID
	if isGenerationKind(w.spec.Kind) {
		manifestID = uuid.New()
		column := "raw_generation_id"
		if w.spec.Kind == activities.HashKindNormalizedGenerationDigest {
			column = "normalized_generation_id"
		}
		createManifest := fmt.Sprintf(`INSERT INTO context.hash_manifest (id, hash_kind, %s) VALUES ($1::uuid, $2, $3::uuid)`, column)
		if _, err := tx.Exec(ctx, createManifest, manifestID, string(w.spec.Kind), w.spec.SubjectRef); err != nil {
			rollback()
			return "", "", fmt.Errorf("create generation hash manifest: %w", err)
		}
		if err := insertManifestMembers(ctx, tx, w.spec, w.batchID, manifestID); err != nil {
			rollback()
			return "", "", err
		}
	}
	resultJSON := jsonbRef(refKind, refID)
	if _, err = tx.Exec(ctx, `INSERT INTO context.activity_receipt (id, activity_execution_id, attempt, status, started_at, completed_at, result_ref) VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`, receiptID, w.executionID, w.attempt, w.startedAt, completedAt, resultJSON); err != nil {
		rollback()
		return "", "", fmt.Errorf("write successful activity receipt: %w", err)
	}
	digest, _ := hex.DecodeString(summary.Digest)
	if err := insertReceipts(ctx, tx, w.spec, w.batchID, manifestID, receiptID, hashReceiptID, digest, summary, completedAt); err != nil {
		rollback()
		return "", "", err
	}
	if _, err = tx.Exec(ctx, `UPDATE context.hash_batch SET status = 'completed', member_count = $2, result_ref = $3::jsonb, activity_receipt_id = $4::uuid, completed_at = $5 WHERE id = $1::uuid`, w.batchID, w.count, resultJSON, receiptID, completedAt); err != nil {
		rollback()
		return "", "", fmt.Errorf("complete hash batch: %w", err)
	}
	if err = tx.Commit(ctx); err != nil {
		rollback()
		return "", "", err
	}
	w.closed = true
	return resultRef, uiw.Ref(receiptID.String()), nil
}

func (w *batchWriter) resultReference(hashReceiptID uuid.UUID) (uiw.Ref, string, string) {
	switch w.spec.Kind {
	case activities.HashKindH1Source, activities.HashKindH3RawGeneration, activities.HashKindNormalizedGenerationDigest:
		return uiw.Ref(hashReceiptID.String()), "hash_receipt", hashReceiptID.String()
	case activities.HashKindRawRecordDigest:
		return uiw.Ref("raw_hash_receipt_set:" + string(w.spec.SubjectRef)), "raw_hash_receipt_set", string(w.spec.SubjectRef)
	default:
		return uiw.Ref("normalized_hash_receipt_set:" + string(w.spec.SubjectRef)), "normalized_hash_receipt_set", string(w.spec.SubjectRef)
	}
}

func (w *batchWriter) Abort(ctx context.Context) error {
	if w.closed {
		return nil
	}
	w.closed = true
	abortCtx, cancel := boundedCleanup(ctx)
	defer cancel()
	tx, err := w.db.BeginTx(abortCtx, pgx.TxOptions{})
	if err != nil {
		return err
	}
	if _, err = tx.Exec(abortCtx, `UPDATE context.hash_batch SET status = 'aborted', completed_at = $2 WHERE id = $1::uuid AND status = 'open'`, w.batchID, w.clock().UTC()); err != nil {
		_ = tx.Rollback(abortCtx)
		return err
	}
	return tx.Commit(abortCtx)
}

func jsonbRef(kind, refID string) []byte {
	return []byte(fmt.Sprintf(`{"ref_kind":%q,"ref_id":%q}`, kind, refID))
}

func insertManifestMembers(ctx context.Context, tx pgx.Tx, spec activities.BatchSpec, batchID, manifestID uuid.UUID) error {
	var query string
	if spec.Kind == activities.HashKindH3RawGeneration {
		query = `INSERT INTO context.hash_manifest_member (hash_manifest_id, ordinal, raw_record_id, member_digest, member_canon) SELECT $1::uuid, member.ordinal, member.raw_record_id, member.digest, member.construction FROM context.hash_batch_member member WHERE member.hash_batch_id = $2::uuid ORDER BY member.ordinal`
	} else {
		query = `INSERT INTO context.hash_manifest_member (hash_manifest_id, ordinal, normalized_record_id, member_digest, member_canon) SELECT $1::uuid, member.ordinal, member.normalized_record_id, member.digest, member.construction FROM context.hash_batch_member member WHERE member.hash_batch_id = $2::uuid ORDER BY member.ordinal`
	}
	if _, err := tx.Exec(ctx, query, manifestID, batchID); err != nil {
		return fmt.Errorf("write generation manifest members: %w", err)
	}
	return nil
}

func insertReceipts(ctx context.Context, tx pgx.Tx, spec activities.BatchSpec, batchID, manifestID, receiptID, hashReceiptID uuid.UUID, digest []byte, summary activities.HashSummary, computedAt time.Time) error {
	kind, stage := string(spec.Kind), string(spec.Stage)
	switch spec.Kind {
	case activities.HashKindH1Source:
		_, err := tx.Exec(ctx, `INSERT INTO context.hash_receipt (id, activity_receipt_id, hash_kind, digest, construction, source_version_id, computed_at, computed_by) VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6::uuid,$7,$8)`, hashReceiptID, receiptID, kind, digest, summary.Canon, spec.SubjectRef, computedAt, stage)
		if err != nil {
			return fmt.Errorf("write H1 receipt: %w", err)
		}
	case activities.HashKindRawRecordDigest:
		_, err := tx.Exec(ctx, `INSERT INTO context.hash_receipt (activity_receipt_id, hash_kind, digest, construction, raw_record_id, computed_at, computed_by) SELECT $1::uuid,$2,digest,construction,raw_record_id,$3,$4 FROM context.hash_batch_member WHERE hash_batch_id=$5::uuid ORDER BY ordinal`, receiptID, kind, computedAt, stage, batchID)
		if err != nil {
			return fmt.Errorf("write H2 receipts: %w", err)
		}
	case activities.HashKindNormalizedRecordDigest:
		_, err := tx.Exec(ctx, `INSERT INTO context.hash_receipt (activity_receipt_id, hash_kind, digest, construction, normalized_record_id, computed_at, computed_by) SELECT $1::uuid,$2,digest,construction,normalized_record_id,$3,$4 FROM context.hash_batch_member WHERE hash_batch_id=$5::uuid ORDER BY ordinal`, receiptID, kind, computedAt, stage, batchID)
		if err != nil {
			return fmt.Errorf("write normalized receipts: %w", err)
		}
	case activities.HashKindH3RawGeneration, activities.HashKindNormalizedGenerationDigest:
		column := "raw_generation_id"
		if spec.Kind == activities.HashKindNormalizedGenerationDigest {
			column = "normalized_generation_id"
		}
		query := fmt.Sprintf(`INSERT INTO context.hash_receipt (id,activity_receipt_id,hash_kind,digest,construction,hash_manifest_id,%s,computed_at,computed_by) VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6::uuid,$7::uuid,$8,$9)`, column)
		if _, err := tx.Exec(ctx, query, hashReceiptID, receiptID, kind, digest, summary.Construction, manifestID, spec.SubjectRef, computedAt, stage); err != nil {
			return fmt.Errorf("write generation receipt: %w", err)
		}
	}
	return nil
}

type idempotentWriter struct {
	db                       DB
	spec                     activities.BatchSpec
	priorActivityReceiptID   uuid.UUID
	priorRefKind, priorRefID string
	resultRef, receiptRef    uiw.Ref
	count                    int64
	closed                   bool
}

func (w *idempotentWriter) Append(ctx context.Context, member activities.HashMember) error {
	if w.closed {
		return errors.New("hash batch is closed")
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if member.SubjectRef == "" || member.Ordinal != w.count {
		return fmt.Errorf("retry hash member ordinal/reference mismatch at %d", w.count)
	}
	if err := validateDigest(member.Digest); err != nil {
		return err
	}
	if err := validateMemberCanon(w.spec.Kind, member.Canon); err != nil {
		return err
	}
	digest, _ := hex.DecodeString(member.Digest)
	memberID, err := uuid.Parse(string(member.SubjectRef))
	if err != nil {
		return fmt.Errorf("retry member reference %q is not a UUID: %w", member.SubjectRef, err)
	}
	var matches bool
	switch w.spec.Kind {
	case activities.HashKindH1Source:
		err = w.db.QueryRow(ctx, `
			SELECT EXISTS (
				SELECT 1 FROM context.hash_receipt
				WHERE id = $1::uuid AND activity_receipt_id = $2::uuid
				  AND hash_kind = 'h1_source' AND source_version_id = $3::uuid
				  AND digest = $4 AND construction = $5)`, w.priorRefID, w.priorActivityReceiptID, memberID, digest, member.Canon).Scan(&matches)
	case activities.HashKindRawRecordDigest:
		err = w.db.QueryRow(ctx, `
			SELECT EXISTS (
				SELECT 1 FROM context.hash_receipt h
				JOIN context.raw_record_identity raw ON raw.id = h.raw_record_id
				WHERE h.activity_receipt_id = $1::uuid AND h.hash_kind = 'raw_record_digest'
				  AND h.raw_record_id = $2::uuid AND raw.raw_generation_id = $3::uuid
				  AND raw.record_ordinal = $4 AND h.digest = $5 AND h.construction = $6)`,
			w.priorActivityReceiptID, memberID, w.priorRefID, member.Ordinal, digest, member.Canon).Scan(&matches)
	case activities.HashKindNormalizedRecordDigest:
		err = w.db.QueryRow(ctx, `
			SELECT EXISTS (
				SELECT 1 FROM context.hash_receipt h
				JOIN context.normalized_record_identity normalized ON normalized.id = h.normalized_record_id
				WHERE h.activity_receipt_id = $1::uuid AND h.hash_kind = 'normalized_record_digest'
				  AND h.normalized_record_id = $2::uuid AND normalized.normalized_generation_id = $3::uuid
				  AND normalized.record_ordinal = $4 AND h.digest = $5 AND h.construction = $6)`,
			w.priorActivityReceiptID, memberID, w.priorRefID, member.Ordinal, digest, member.Canon).Scan(&matches)
	case activities.HashKindH3RawGeneration, activities.HashKindNormalizedGenerationDigest:
		identityColumn, generationColumn, kind := "raw_record_id", "raw_generation_id", "h3_raw_generation"
		if w.spec.Kind == activities.HashKindNormalizedGenerationDigest {
			identityColumn, generationColumn, kind = "normalized_record_id", "normalized_generation_id", "normalized_generation_manifest_digest"
		}
		query := fmt.Sprintf(`
			SELECT EXISTS (
				SELECT 1 FROM context.hash_manifest_member member
				JOIN context.hash_manifest manifest ON manifest.id = member.hash_manifest_id
				JOIN context.hash_receipt receipt ON receipt.hash_manifest_id = manifest.id
				WHERE receipt.id = $1::uuid AND receipt.hash_kind = '%s'
				  AND manifest.%s = $2::uuid AND member.%s = $3::uuid
				  AND member.ordinal = $4 AND member.member_digest = $5
				  AND member.member_canon = $6)`, kind, generationColumn, identityColumn)
		err = w.db.QueryRow(ctx, query, w.priorRefID, w.spec.SubjectRef, memberID, member.Ordinal, digest, member.Canon).Scan(&matches)
	}
	if err != nil {
		return fmt.Errorf("verify retry hash member %d: %w", member.Ordinal, err)
	}
	if !matches {
		return fmt.Errorf("retry hash member %d does not match prior durable receipt", member.Ordinal)
	}
	w.count++
	return nil
}

func (w *idempotentWriter) Commit(ctx context.Context, summary activities.HashSummary) (uiw.Ref, uiw.Ref, error) {
	if w.closed {
		return "", "", errors.New("hash batch is closed")
	}
	w.closed = true
	if w.count == 0 || summary.MemberCount != w.count {
		return "", "", fmt.Errorf("retry summary member count %d does not equal verified count %d", summary.MemberCount, w.count)
	}
	if err := validateSummary(w.spec.Kind, summary); err != nil {
		return "", "", err
	}
	if err := w.verifySummary(ctx, summary); err != nil {
		return "", "", err
	}
	return w.resultRef, w.receiptRef, nil
}

func (w *idempotentWriter) verifySummary(ctx context.Context, summary activities.HashSummary) error {
	if w.spec.Kind == activities.HashKindRawRecordDigest || w.spec.Kind == activities.HashKindNormalizedRecordDigest {
		kind, table, generationColumn := "raw_record_digest", "context.raw_record_identity", "raw_generation_id"
		if w.spec.Kind == activities.HashKindNormalizedRecordDigest {
			kind, table, generationColumn = "normalized_record_digest", "context.normalized_record_identity", "normalized_generation_id"
		}
		var count int64
		query := fmt.Sprintf(`SELECT count(*) FROM context.hash_receipt h JOIN %s identity ON identity.id = h.%s WHERE h.activity_receipt_id = $1::uuid AND h.hash_kind = $2 AND identity.%s = $3::uuid`, table, identityColumnFor(w.spec.Kind), generationColumn)
		if err := w.db.QueryRow(ctx, query, w.priorActivityReceiptID, kind, w.priorRefID).Scan(&count); err != nil {
			return fmt.Errorf("verify retry receipt set: %w", err)
		}
		if count != summary.MemberCount {
			return fmt.Errorf("prior receipt set count %d does not equal summary count %d", count, summary.MemberCount)
		}
		return nil
	}
	var priorDigest, priorCanon string
	var priorCount int64
	query := `SELECT encode(digest, 'hex'), construction, 1::bigint FROM context.hash_receipt WHERE id = $1::uuid AND hash_kind = $2`
	if isGenerationKind(w.spec.Kind) {
		query = `SELECT encode(receipt.digest, 'hex'), receipt.construction,
			(SELECT count(*) FROM context.hash_manifest_member member WHERE member.hash_manifest_id = receipt.hash_manifest_id)
			FROM context.hash_receipt receipt WHERE receipt.id = $1::uuid AND receipt.hash_kind = $2`
	}
	if err := w.db.QueryRow(ctx, query, w.priorRefID, string(w.spec.Kind)).Scan(&priorDigest, &priorCanon, &priorCount); err != nil {
		return fmt.Errorf("verify prior hash receipt: %w", err)
	}
	if priorDigest != summary.Digest || priorCount != summary.MemberCount {
		return errors.New("prior hash receipt does not match retry summary")
	}
	construction := summary.Canon
	if isGenerationKind(w.spec.Kind) {
		construction = summary.Construction
	}
	if priorCanon != construction {
		return fmt.Errorf("prior hash canon %q does not match retry canon %q", priorCanon, construction)
	}
	return nil
}

func (w *idempotentWriter) Abort(context.Context) error { return nil }

func identityColumnFor(kind activities.HashKind) string {
	if kind == activities.HashKindNormalizedRecordDigest {
		return "normalized_record_id"
	}
	return "raw_record_id"
}

func priorResultRef(kind, refID string) uiw.Ref {
	if kind == "raw_hash_receipt_set" || kind == "normalized_hash_receipt_set" {
		return uiw.Ref(kind + ":" + refID)
	}
	return uiw.Ref(refID)
}

func expectedResultKind(kind activities.HashKind) string {
	switch kind {
	case activities.HashKindH1Source, activities.HashKindH3RawGeneration, activities.HashKindNormalizedGenerationDigest:
		return "hash_receipt"
	case activities.HashKindRawRecordDigest:
		return "raw_hash_receipt_set"
	default:
		return "normalized_hash_receipt_set"
	}
}

type byteRows struct {
	rows        pgx.Rows
	open        ObjectOpener
	raw, closed bool
}

func (s *byteRows) Next(ctx context.Context) (activities.ByteMember, error) {
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
	var stored, inline []byte
	var storageClass, objectURI, canon string
	var offset, length int64
	if err := s.rows.Scan(&ref, &ordinal, &canon, &stored, &storageClass, &objectURI, &inline, &offset, &length); err != nil {
		return activities.ByteMember{}, err
	}
	reader, err := openBytes(ctx, s.open, storageClass, objectURI, stored, inline, offset, length)
	if err != nil {
		return activities.ByteMember{}, fmt.Errorf("open raw member %q: %w", ref, err)
	}
	return activities.ByteMember{SubjectRef: uiw.Ref(ref), Ordinal: ordinal, Canon: canon, Reader: reader}, nil
}
func (s *byteRows) Close() error {
	if !s.closed {
		s.closed = true
		s.rows.Close()
	}
	return nil
}

type normalizedRows struct {
	rows   pgx.Rows
	closed bool
}

func (s *normalizedRows) Next(ctx context.Context) (activities.ByteMember, error) {
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
	var canonical []byte
	if err := s.rows.Scan(&ref, &ordinal, &canonical); err != nil {
		return activities.ByteMember{}, err
	}
	return activities.ByteMember{SubjectRef: uiw.Ref(ref), Ordinal: ordinal, Reader: io.NopCloser(bytes.NewReader(canonical))}, nil
}
func (s *normalizedRows) Close() error {
	if !s.closed {
		s.closed = true
		s.rows.Close()
	}
	return nil
}

type digestRows struct {
	rows   pgx.Rows
	closed bool
}

func (s *digestRows) Next(ctx context.Context) (activities.DigestMember, error) {
	if s.closed {
		return activities.DigestMember{}, io.EOF
	}
	if err := ctx.Err(); err != nil {
		return activities.DigestMember{}, err
	}
	if !s.rows.Next() {
		if err := s.rows.Err(); err != nil {
			return activities.DigestMember{}, err
		}
		return activities.DigestMember{}, io.EOF
	}
	var ref, digest, canon string
	var ordinal int64
	if err := s.rows.Scan(&ref, &ordinal, &digest, &canon); err != nil {
		return activities.DigestMember{}, err
	}
	return activities.DigestMember{SubjectRef: uiw.Ref(ref), Ordinal: ordinal, Digest: digest, Canon: canon}, nil
}
func (s *digestRows) Close() error {
	if !s.closed {
		s.closed = true
		s.rows.Close()
	}
	return nil
}

func openBytes(ctx context.Context, open ObjectOpener, storageClass, uri string, stored, inline []byte, offset, length int64) (io.ReadCloser, error) {
	if stored != nil {
		return io.NopCloser(bytes.NewReader(stored)), nil
	}
	if storageClass == "inline" {
		return io.NopCloser(bytes.NewReader(inline)), nil
	}
	if open == nil {
		return nil, fmt.Errorf("non-inline object %q requires an ObjectOpener", uri)
	}
	if offset < 0 || length < 0 {
		return nil, errors.New("invalid object byte range")
	}
	reader, err := open(ctx, uri)
	if err != nil {
		return nil, err
	}
	return &rangeReadCloser{reader: reader, closer: reader, skip: offset, remaining: length}, nil
}

type rangeReadCloser struct {
	reader          io.Reader
	closer          io.Closer
	skip, remaining int64
}

func (r *rangeReadCloser) Read(p []byte) (int, error) {
	if r.remaining == 0 {
		return 0, io.EOF
	}
	if r.skip > 0 {
		n, err := io.CopyN(io.Discard, r.reader, r.skip)
		r.skip -= n
		if err != nil {
			if errors.Is(err, io.EOF) {
				return 0, io.ErrUnexpectedEOF
			}
			return 0, err
		}
	}
	if int64(len(p)) > r.remaining {
		p = p[:r.remaining]
	}
	n, err := r.reader.Read(p)
	r.remaining -= int64(n)
	if errors.Is(err, io.EOF) && r.remaining > 0 {
		return n, io.ErrUnexpectedEOF
	}
	if r.remaining == 0 && err == nil {
		err = io.EOF
	}
	return n, err
}

func (r *rangeReadCloser) Close() error { return r.closer.Close() }

func parseSetRef(ref uiw.Ref) (kind, generationID string, err error) {
	parts := strings.SplitN(string(ref), ":", 2)
	if len(parts) != 2 || (parts[0] != "raw_hash_receipt_set" && parts[0] != "normalized_hash_receipt_set") {
		return "", "", fmt.Errorf("hash member reference %q must be a prefixed receipt set", ref)
	}
	if _, err := uuid.Parse(parts[1]); err != nil {
		return "", "", fmt.Errorf("hash member reference %q has invalid generation id: %w", ref, err)
	}
	return parts[0], parts[1], nil
}

func sourceVersionFor(ctx context.Context, tx pgx.Tx, kind activities.HashKind, ref uiw.Ref) (uuid.UUID, error) {
	var id uuid.UUID
	query := `SELECT id FROM context.source_version WHERE id = $1::uuid`
	if kind == activities.HashKindRawRecordDigest || kind == activities.HashKindH3RawGeneration {
		query = `SELECT source_version_id FROM context.raw_generation WHERE id = $1::uuid`
	} else if kind == activities.HashKindNormalizedRecordDigest || kind == activities.HashKindNormalizedGenerationDigest {
		query = `SELECT source_version_id FROM context.normalized_generation WHERE id = $1::uuid`
	}
	err := tx.QueryRow(ctx, query, string(ref)).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("resolve source version for %q: %w", ref, err)
	}
	return id, nil
}

func validateSpec(spec activities.BatchSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || spec.SubjectRef == "" {
		return errors.New("hash batch requires request and subject references")
	}
	if spec.Attempt < 1 {
		return errors.New("hash batch attempt must be positive")
	}
	expected := map[stagegraph.StageID]activities.HashKind{
		stagegraph.HashSource:               activities.HashKindH1Source,
		stagegraph.HashRawRecords:           activities.HashKindRawRecordDigest,
		stagegraph.HashRawGeneration:        activities.HashKindH3RawGeneration,
		stagegraph.HashNormalizedRecords:    activities.HashKindNormalizedRecordDigest,
		stagegraph.HashNormalizedGeneration: activities.HashKindNormalizedGenerationDigest,
	}
	if expected[spec.Stage] != spec.Kind {
		return fmt.Errorf("stage %q and hash kind %q do not match", spec.Stage, spec.Kind)
	}
	return nil
}
func validateMemberCanon(kind activities.HashKind, canon string) error {
	valid := kind == activities.HashKindH1Source && canon == "h1-rawbytes-v1"
	valid = valid || kind == activities.HashKindRawRecordDigest && (canon == custodyhash.CanonH2 || canon == custodyhash.CanonH2Record || canon == activities.CanonRawSpan)
	valid = valid || kind == activities.HashKindNormalizedRecordDigest && canon == activities.CanonNormalizedRecord
	if !valid && kind == activities.HashKindH3RawGeneration {
		valid = canon == custodyhash.CanonH2 || canon == custodyhash.CanonH2Record || canon == activities.CanonRawSpan
	}
	if !valid && kind == activities.HashKindNormalizedGenerationDigest {
		valid = canon == activities.CanonNormalizedRecord
	}
	if !valid {
		return fmt.Errorf("hash member canon %q is invalid for %s", canon, kind)
	}
	return nil
}
func validateSummary(kind activities.HashKind, summary activities.HashSummary) error {
	if kind == activities.HashKindH1Source && summary.Canon != "h1-rawbytes-v1" {
		return fmt.Errorf("H1 summary canon %q is invalid", summary.Canon)
	}
	if kind == activities.HashKindRawRecordDigest && summary.Canon != activities.CanonRawRecordManifest {
		return fmt.Errorf("H2 summary canon %q is invalid", summary.Canon)
	}
	if kind == activities.HashKindNormalizedRecordDigest && summary.Canon != activities.CanonNormalizedRecordManifest {
		return fmt.Errorf("normalized summary canon %q is invalid", summary.Canon)
	}
	if isGenerationKind(kind) {
		if summary.Digest == "" || summary.Construction == "" {
			return errors.New("generation summary requires digest and construction")
		}
		want := activities.CanonRawGeneration
		if kind == activities.HashKindNormalizedGenerationDigest {
			want = activities.CanonNormalizedGeneration
		}
		if summary.Canon != want || summary.Construction != want {
			return fmt.Errorf("generation summary canon/construction must be %q", want)
		}
	} else if kind == activities.HashKindH1Source && summary.Digest == "" {
		return errors.New("H1 summary requires digest")
	}
	if summary.Digest != "" {
		if err := validateDigest(summary.Digest); err != nil {
			return err
		}
	}
	return nil
}
func isGenerationKind(kind activities.HashKind) bool {
	return kind == activities.HashKindH3RawGeneration || kind == activities.HashKindNormalizedGenerationDigest
}
func validateDigest(value string) error {
	if len(value) != 64 || strings.ToLower(value) != value {
		return errors.New("digest must be lowercase SHA-256 hex")
	}
	if _, err := hex.DecodeString(value); err != nil {
		return errors.New("digest must be lowercase SHA-256 hex")
	}
	return nil
}
func idempotencyKey(spec activities.BatchSpec) string {
	return fmt.Sprintf("hash:%s:%s:%s", spec.RequestID, spec.Stage, spec.SubjectRef)
}
func requireRef(ref uiw.Ref, name string) error {
	if strings.TrimSpace(string(ref)) == "" {
		return fmt.Errorf("%s reference is required", name)
	}
	return nil
}

func boundedCleanup(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
}

var _ activities.HashRepository = (*Repository)(nil)
var _ activities.HashBatchWriter = (*batchWriter)(nil)

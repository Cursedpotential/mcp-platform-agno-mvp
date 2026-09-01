package postgres

// This file is the PostgreSQL boundary for source-observation Activities.
// Metadata rows and Activity receipts are durable PostgreSQL facts. Container
// membership itself is written by an injected immutable manifest writer because
// migration 0036 intentionally has no inventory staging table. The writer is
// called one member at a time; this store never buffers a container in memory
// and never holds a SQL transaction while the writer is reading external data.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

const sourceObservationCleanupTimeout = 5 * time.Second

// InventoryManifestWriter is the external immutable-manifest seam used by
// InventoryContainer. It receives structural members incrementally and returns
// only an opaque compact reference after its immutable manifest is finalized.
// It must not return the manifest payload through Temporal history.
type InventoryManifestWriter interface {
	Append(context.Context, activities.InventoryMember) error
	Commit(context.Context, activities.InventorySummary) (uiw.Ref, error)
	Abort(context.Context) error
}

// InventoryManifestWriterFactory creates a writer for one idempotency
// coordinate. A production implementation should make Commit immutable and
// content-addressed (or otherwise idempotent) so a database failure after an
// external commit can be recovered without changing the manifest's contents.
type InventoryManifestWriterFactory func(context.Context, activities.InventorySpec) (InventoryManifestWriter, error)

// SourceObservationRepository is the concrete PostgreSQL implementation of
// activities.SourceObservationRepository. Metadata is stored in
// context.source_metadata. Since 0036 has no inventory table, the committed
// manifest reference and exact member accounting are retained as one native
// container metadata row bound to the inventory Activity receipt.
type SourceObservationRepository struct {
	db        DB
	manifests InventoryManifestWriterFactory
	clock     func() time.Time
}

func NewSourceObservationRepository(db DB, manifests InventoryManifestWriterFactory) (*SourceObservationRepository, error) {
	if db == nil {
		return nil, errors.New("postgres source observation repository: database is required")
	}
	if manifests == nil {
		return nil, errors.New("postgres source observation repository: inventory manifest writer is required")
	}
	return &SourceObservationRepository{
		db: db, manifests: manifests, clock: func() time.Time { return time.Now().UTC() },
	}, nil
}

// PersistSourceMetadata creates one immutable receipt and source-level rows.
// The receipt is written before source_metadata rows so the 0036 trigger can
// enforce the exact same-source Activity boundary. An empty row set records a
// durable not_applicable receipt and no result registry.
func (r *SourceObservationRepository) PersistSourceMetadata(ctx context.Context, spec activities.MetadataPersistenceSpec) (activities.MetadataPersistenceResult, error) {
	if err := validateMetadataPersistenceSpec(spec); err != nil {
		return activities.MetadataPersistenceResult{}, err
	}
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return activities.MetadataPersistenceResult{}, fmt.Errorf("begin metadata transaction: %w", err)
	}
	rollback := true
	defer func() {
		if rollback {
			cleanupCtx, cancel := sourceObservationCleanup(ctx)
			defer cancel()
			_ = tx.Rollback(cleanupCtx)
		}
	}()

	sourceVersionID, executionID, err := r.ensureRetainedExecution(ctx, tx, spec.SourceVersionRef, spec.RequestID, spec.Stage, spec.IdempotencyKey)
	if err != nil {
		return activities.MetadataPersistenceResult{}, err
	}
	prior, found, err := latestObservationReceipt(ctx, tx, executionID)
	if err != nil {
		return activities.MetadataPersistenceResult{}, err
	}
	resultRef := metadataManifestRef(sourceVersionID, spec.Stage)
	if found {
		if prior.status == "success" {
			if len(spec.Rows) == 0 || prior.refKind != "source_metadata_manifest" || prior.refID != string(resultRef) {
				return activities.MetadataPersistenceResult{}, errors.New("existing metadata receipt has an unexpected result reference")
			}
			if err := tx.Commit(ctx); err != nil {
				return activities.MetadataPersistenceResult{}, fmt.Errorf("commit recovered metadata: %w", err)
			}
			rollback = false
			return activities.MetadataPersistenceResult{ResultRef: resultRef, ReceiptRef: uiw.Ref(prior.id.String())}, nil
		}
		if prior.status == "not_applicable" && len(spec.Rows) == 0 {
			if err := tx.Commit(ctx); err != nil {
				return activities.MetadataPersistenceResult{}, fmt.Errorf("commit recovered metadata not-applicable receipt: %w", err)
			}
			rollback = false
			return activities.MetadataPersistenceResult{ReceiptRef: uiw.Ref(prior.id.String())}, nil
		}
		if prior.status == "not_applicable" {
			return activities.MetadataPersistenceResult{}, errors.New("metadata idempotency coordinate already completed as not-applicable")
		}
	}

	now := r.now()
	receiptID := uuid.New()
	if len(spec.Rows) == 0 {
		if strings.TrimSpace(spec.NotApplicableReason) == "" {
			return activities.MetadataPersistenceResult{}, errors.New("metadata not-applicable result requires a reason")
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO context.activity_receipt
				(id, activity_execution_id, attempt, status, started_at, completed_at, not_applicable_reason)
			VALUES ($1::uuid, $2::uuid, $3, 'not_applicable', $4, $5, $6)`,
			receiptID, executionID, spec.Attempt, now, now, spec.NotApplicableReason); err != nil {
			return activities.MetadataPersistenceResult{}, fmt.Errorf("record metadata not-applicable receipt: %w", err)
		}
	} else {
		resultJSON, err := resultReference("source_metadata_manifest", string(resultRef))
		if err != nil {
			return activities.MetadataPersistenceResult{}, err
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO context.activity_receipt
				(id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
			VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`,
			receiptID, executionID, spec.Attempt, now, now, resultJSON); err != nil {
			return activities.MetadataPersistenceResult{}, fmt.Errorf("record metadata receipt: %w", err)
		}
		for index, row := range spec.Rows {
			if _, err := tx.Exec(ctx, `
				INSERT INTO context.source_metadata
					(source_version_id, metadata_class, metadata, extractor_id, extractor_version,
					 extraction_activity_receipt_id, generated_at)
				VALUES ($1::uuid, $2, $3::jsonb, $4, $5, $6::uuid, $7)`,
				sourceVersionID, row.MetadataClass, []byte(row.Metadata), row.ExtractorID,
				row.ExtractorVersion, receiptID, row.GeneratedAt); err != nil {
				return activities.MetadataPersistenceResult{}, fmt.Errorf("persist metadata row %d: %w", index, err)
			}
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return activities.MetadataPersistenceResult{}, fmt.Errorf("commit source metadata: %w", err)
	}
	rollback = false
	if len(spec.Rows) == 0 {
		return activities.MetadataPersistenceResult{ReceiptRef: uiw.Ref(receiptID.String())}, nil
	}
	return activities.MetadataPersistenceResult{ResultRef: resultRef, ReceiptRef: uiw.Ref(receiptID.String())}, nil
}

// BeginInventory checks retention and creates/reuses the Activity execution,
// then opens the caller-owned manifest writer outside the SQL transaction.
func (r *SourceObservationRepository) BeginInventory(ctx context.Context, spec activities.InventorySpec) (activities.InventoryWriter, error) {
	if err := validateInventorySpec(spec); err != nil {
		return nil, err
	}
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return nil, fmt.Errorf("begin inventory transaction: %w", err)
	}
	rollback := true
	defer func() {
		if rollback {
			cleanupCtx, cancel := sourceObservationCleanup(ctx)
			defer cancel()
			_ = tx.Rollback(cleanupCtx)
		}
	}()
	sourceVersionID, executionID, err := r.ensureRetainedExecution(ctx, tx, spec.SourceVersionRef, spec.RequestID, spec.Stage, spec.IdempotencyKey)
	if err != nil {
		return nil, err
	}
	prior, found, err := latestObservationReceipt(ctx, tx, executionID)
	if err != nil {
		return nil, err
	}
	if found && prior.status == "success" {
		if prior.refKind != "container_manifest" || prior.refID == "" {
			return nil, errors.New("existing inventory receipt has an unexpected result reference")
		}
		if err := tx.Commit(ctx); err != nil {
			return nil, fmt.Errorf("commit recovered inventory: %w", err)
		}
		rollback = false
		return &completedInventoryWriter{resultRef: uiw.Ref(prior.refID), receiptRef: uiw.Ref(prior.id.String())}, nil
	}
	if found && prior.status == "not_applicable" {
		return nil, errors.New("inventory idempotency coordinate already completed as not-applicable")
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit inventory preparation: %w", err)
	}
	rollback = false
	manifest, err := r.manifests(ctx, spec)
	if err != nil {
		return nil, fmt.Errorf("open inventory manifest writer: %w", err)
	}
	if manifest == nil {
		return nil, errors.New("inventory manifest writer factory returned nil writer")
	}
	return &inventoryWriter{
		db: r.db, manifest: manifest, spec: spec, sourceVersionID: sourceVersionID,
		executionID: executionID, clock: r.clock, nextOrdinal: 0,
	}, nil
}

func (r *SourceObservationRepository) RecordInventoryNotApplicable(ctx context.Context, spec activities.InventorySpec, reason string) (uiw.Ref, error) {
	if err := validateInventorySpec(spec); err != nil {
		return "", err
	}
	reason = strings.TrimSpace(reason)
	if reason == "" {
		return "", errors.New("inventory not-applicable result requires a reason")
	}
	tx, err := r.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", fmt.Errorf("begin inventory not-applicable transaction: %w", err)
	}
	rollback := true
	defer func() {
		if rollback {
			cleanupCtx, cancel := sourceObservationCleanup(ctx)
			defer cancel()
			_ = tx.Rollback(cleanupCtx)
		}
	}()
	_, executionID, err := r.ensureRetainedExecution(ctx, tx, spec.SourceVersionRef, spec.RequestID, spec.Stage, spec.IdempotencyKey)
	if err != nil {
		return "", err
	}
	prior, found, err := latestObservationReceipt(ctx, tx, executionID)
	if err != nil {
		return "", err
	}
	if found {
		if prior.status == "not_applicable" {
			if err := tx.Commit(ctx); err != nil {
				return "", fmt.Errorf("commit recovered inventory not-applicable receipt: %w", err)
			}
			rollback = false
			return uiw.Ref(prior.id.String()), nil
		}
		return "", errors.New("inventory already has a successful result")
	}
	receiptID := uuid.New()
	now := r.now()
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt
			(id, activity_execution_id, attempt, status, started_at, completed_at, not_applicable_reason)
		VALUES ($1::uuid, $2::uuid, $3, 'not_applicable', $4, $5, $6)`,
		receiptID, executionID, spec.Attempt, now, now, reason); err != nil {
		return "", fmt.Errorf("record inventory not-applicable receipt: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return "", fmt.Errorf("commit inventory not-applicable receipt: %w", err)
	}
	rollback = false
	return uiw.Ref(receiptID.String()), nil
}

type inventoryWriter struct {
	db              DB
	manifest        InventoryManifestWriter
	spec            activities.InventorySpec
	sourceVersionID uuid.UUID
	executionID     uuid.UUID
	clock           func() time.Time
	nextOrdinal     int64
	closed          bool
}

func (w *inventoryWriter) Append(ctx context.Context, member activities.InventoryMember) error {
	if w.closed {
		return errors.New("inventory writer is closed")
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if member.Ordinal != w.nextOrdinal {
		return fmt.Errorf("inventory member ordinal %d, want %d", member.Ordinal, w.nextOrdinal)
	}
	if strings.TrimSpace(string(member.MemberRef)) == "" {
		return errors.New("inventory member requires a compact member reference")
	}
	if member.ByteLength < 0 {
		return errors.New("inventory member byte length cannot be negative")
	}
	if member.ByteOffset != nil && *member.ByteOffset < 0 {
		return errors.New("inventory member byte offset cannot be negative")
	}
	if member.ParentRef == member.MemberRef {
		return errors.New("inventory member cannot be its own parent")
	}
	if err := w.manifest.Append(ctx, member); err != nil {
		return err
	}
	w.nextOrdinal++
	return nil
}

func (w *inventoryWriter) Commit(ctx context.Context, summary activities.InventorySummary) (uiw.Ref, uiw.Ref, error) {
	if w.closed {
		return "", "", errors.New("inventory writer is closed")
	}
	if err := ctx.Err(); err != nil {
		return "", "", err
	}
	if w.nextOrdinal == 0 || summary.MemberCount != w.nextOrdinal {
		return "", "", fmt.Errorf("inventory summary member count %d does not equal staged count %d", summary.MemberCount, w.nextOrdinal)
	}
	if summary.TotalBytes < 0 || summary.RangeCount < 0 || summary.RangeCount > summary.MemberCount {
		return "", "", errors.New("inventory summary contains invalid accounting")
	}
	manifestRef, err := w.manifest.Commit(ctx, summary)
	if err != nil {
		return "", "", fmt.Errorf("commit immutable inventory manifest: %w", err)
	}
	if strings.TrimSpace(string(manifestRef)) == "" {
		return "", "", errors.New("inventory manifest commit returned an empty reference")
	}
	tx, err := w.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return "", "", fmt.Errorf("begin inventory completion transaction: %w", err)
	}
	rollback := true
	defer func() {
		if rollback {
			cleanupCtx, cancel := sourceObservationCleanup(ctx)
			defer cancel()
			_ = tx.Rollback(cleanupCtx)
		}
	}()
	prior, found, err := latestObservationReceipt(ctx, tx, w.executionID)
	if err != nil {
		return "", "", err
	}
	if found {
		if prior.status != "success" || prior.refKind != "container_manifest" || prior.refID == "" {
			return "", "", errors.New("existing inventory receipt conflicts with successful manifest completion")
		}
		if err := tx.Commit(ctx); err != nil {
			return "", "", fmt.Errorf("commit recovered inventory completion: %w", err)
		}
		rollback = false
		w.closed = true
		return uiw.Ref(prior.refID), uiw.Ref(prior.id.String()), nil
	}
	now := w.clock().UTC()
	receiptID := uuid.New()
	resultJSON, err := resultReference("container_manifest", string(manifestRef))
	if err != nil {
		return "", "", err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.activity_receipt
			(id, activity_execution_id, attempt, status, started_at, completed_at, result_ref)
		VALUES ($1::uuid, $2::uuid, $3, 'success', $4, $5, $6::jsonb)`,
		receiptID, w.executionID, w.spec.Attempt, now, now, resultJSON); err != nil {
		return "", "", fmt.Errorf("record inventory receipt: %w", err)
	}
	containerMetadata, err := json.Marshal(struct {
		ManifestRef string `json:"manifest_ref"`
		MemberCount int64  `json:"member_count"`
		TotalBytes  int64  `json:"total_bytes"`
		RangeCount  int64  `json:"range_count"`
	}{string(manifestRef), summary.MemberCount, summary.TotalBytes, summary.RangeCount})
	if err != nil {
		return "", "", fmt.Errorf("encode inventory metadata: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.source_metadata
			(source_version_id, metadata_class, metadata, extractor_id, extractor_version,
			 extraction_activity_receipt_id, generated_at)
		VALUES ($1::uuid, 'container', $2::jsonb, 'container-inventory', '1.0.0', $3::uuid, $4)`,
		w.sourceVersionID, containerMetadata, receiptID, now); err != nil {
		return "", "", fmt.Errorf("persist container inventory metadata: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return "", "", fmt.Errorf("commit inventory completion: %w", err)
	}
	rollback = false
	w.closed = true
	return manifestRef, uiw.Ref(receiptID.String()), nil
}

func (w *inventoryWriter) Abort(ctx context.Context) error {
	if w.closed {
		return nil
	}
	w.closed = true
	cleanupCtx, cancel := sourceObservationCleanup(ctx)
	defer cancel()
	return w.manifest.Abort(cleanupCtx)
}

type completedInventoryWriter struct {
	resultRef  uiw.Ref
	receiptRef uiw.Ref
}

func (w *completedInventoryWriter) Append(context.Context, activities.InventoryMember) error {
	return errors.New("inventory already completed for this idempotency coordinate")
}

func (w *completedInventoryWriter) Commit(context.Context, activities.InventorySummary) (uiw.Ref, uiw.Ref, error) {
	return w.resultRef, w.receiptRef, nil
}

func (*completedInventoryWriter) Abort(context.Context) error { return nil }

type observationReceipt struct {
	id      uuid.UUID
	status  string
	refKind string
	refID   string
}

func latestObservationReceipt(ctx context.Context, tx pgx.Tx, executionID uuid.UUID) (observationReceipt, bool, error) {
	var receipt observationReceipt
	var resultJSON []byte
	err := tx.QueryRow(ctx, `
		SELECT id, status, result_ref
		FROM context.activity_receipt
		WHERE activity_execution_id = $1::uuid
		ORDER BY attempt DESC
		LIMIT 1`, executionID).Scan(&receipt.id, &receipt.status, &resultJSON)
	if errors.Is(err, pgx.ErrNoRows) {
		return observationReceipt{}, false, nil
	}
	if err != nil {
		return observationReceipt{}, false, fmt.Errorf("read prior observation receipt: %w", err)
	}
	if receipt.status == "success" {
		var ref struct {
			Kind string `json:"ref_kind"`
			ID   string `json:"ref_id"`
		}
		if err := json.Unmarshal(resultJSON, &ref); err != nil || strings.TrimSpace(ref.Kind) == "" || strings.TrimSpace(ref.ID) == "" {
			return observationReceipt{}, false, errors.New("existing observation receipt has an invalid result reference")
		}
		receipt.refKind, receipt.refID = ref.Kind, ref.ID
	}
	return receipt, true, nil
}

func (r *SourceObservationRepository) ensureRetainedExecution(ctx context.Context, tx pgx.Tx, sourceVersionRef uiw.Ref, requestID string, stage stagegraph.StageID, idempotencyKey string) (uuid.UUID, uuid.UUID, error) {
	versionID, err := uuid.Parse(string(sourceVersionRef))
	if err != nil {
		return uuid.Nil, uuid.Nil, fmt.Errorf("source version reference is not a UUID: %w", err)
	}
	var workflowID, status string
	if err := tx.QueryRow(ctx, `
		SELECT workflow_id, status
		FROM context.source_version
		WHERE id = $1::uuid
		FOR UPDATE`, versionID).Scan(&workflowID, &status); err != nil {
		return uuid.Nil, uuid.Nil, fmt.Errorf("resolve source version: %w", err)
	}
	if workflowID != requestID {
		return uuid.Nil, uuid.Nil, fmt.Errorf("request id %q does not match source workflow id %q", requestID, workflowID)
	}
	if status != "retained" {
		return uuid.Nil, uuid.Nil, fmt.Errorf("source version %q is not retained", sourceVersionRef)
	}
	if strings.TrimSpace(idempotencyKey) == "" {
		return uuid.Nil, uuid.Nil, errors.New("source observation idempotency key is required")
	}
	executionID, err := lifecycleEnsureExecution(ctx, tx, versionID, requestID, string(stage), idempotencyKey, nil)
	if err != nil {
		return uuid.Nil, uuid.Nil, err
	}
	var actualWorkflow string
	if err := tx.QueryRow(ctx, `SELECT workflow_id FROM context.activity_execution WHERE id = $1::uuid`, executionID).Scan(&actualWorkflow); err != nil {
		return uuid.Nil, uuid.Nil, fmt.Errorf("verify observation Activity execution: %w", err)
	}
	if actualWorkflow != requestID {
		return uuid.Nil, uuid.Nil, errors.New("existing observation Activity execution has a different workflow id")
	}
	return versionID, executionID, nil
}

func validateMetadataPersistenceSpec(spec activities.MetadataPersistenceSpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || strings.TrimSpace(string(spec.SourceVersionRef)) == "" || strings.TrimSpace(spec.IdempotencyKey) == "" {
		return errors.New("source metadata persistence requires request, source version, and idempotency key")
	}
	if spec.Stage != stagegraph.CaptureFilesystemMetadata && spec.Stage != stagegraph.ExtractEmbeddedMetadata {
		return fmt.Errorf("unsupported source metadata Activity %q", spec.Stage)
	}
	if spec.Attempt < 1 {
		return errors.New("source metadata persistence attempt must be positive")
	}
	switch spec.ProvenanceClass {
	case "first_party_authored", "acquired_third_party", "system_generated", "unknown":
	default:
		return fmt.Errorf("unsupported source metadata provenance class %q", spec.ProvenanceClass)
	}
	for index, row := range spec.Rows {
		if err := validateMetadataRow(row); err != nil {
			return fmt.Errorf("metadata row %d: %w", index, err)
		}
		if spec.Stage == stagegraph.CaptureFilesystemMetadata && row.MetadataClass != activities.MetadataClassFilesystem {
			return fmt.Errorf("filesystem metadata Activity cannot persist %q row", row.MetadataClass)
		}
		if spec.Stage == stagegraph.ExtractEmbeddedMetadata && row.MetadataClass != activities.MetadataClassEmbedded && row.MetadataClass != activities.MetadataClassMediaTool {
			return fmt.Errorf("embedded metadata Activity cannot persist %q row", row.MetadataClass)
		}
	}
	if len(spec.Rows) == 0 && strings.TrimSpace(spec.NotApplicableReason) == "" {
		return errors.New("empty metadata persistence requires a not-applicable reason")
	}
	if len(spec.Rows) > 0 && strings.TrimSpace(spec.NotApplicableReason) != "" {
		return errors.New("metadata persistence cannot combine rows and not-applicable reason")
	}
	return nil
}

func validateMetadataRow(row activities.MetadataRow) error {
	switch row.MetadataClass {
	case activities.MetadataClassFilesystem, activities.MetadataClassEmbedded, activities.MetadataClassContainer, activities.MetadataClassMediaTool:
	default:
		return fmt.Errorf("unsupported source metadata class %q", row.MetadataClass)
	}
	var object map[string]any
	if len(row.Metadata) == 0 || json.Unmarshal(row.Metadata, &object) != nil || object == nil {
		return errors.New("source metadata must be a JSON object")
	}
	if strings.TrimSpace(row.ExtractorID) == "" {
		return errors.New("source metadata row requires an extractor id")
	}
	if row.GeneratedAt.IsZero() {
		return errors.New("source metadata row requires generated_at")
	}
	return nil
}

func validateInventorySpec(spec activities.InventorySpec) error {
	if strings.TrimSpace(spec.RequestID) == "" || strings.TrimSpace(string(spec.SourceVersionRef)) == "" || strings.TrimSpace(spec.IdempotencyKey) == "" {
		return errors.New("inventory requires request, source version, and idempotency key")
	}
	if spec.Stage != stagegraph.InventoryContainer {
		return fmt.Errorf("unsupported inventory Activity %q", spec.Stage)
	}
	if spec.Attempt < 1 {
		return errors.New("inventory attempt must be positive")
	}
	return nil
}

func metadataManifestRef(sourceVersionID uuid.UUID, stage stagegraph.StageID) uiw.Ref {
	return uiw.Ref(fmt.Sprintf("source-metadata:%s:%s", sourceVersionID, stage))
}

func sourceObservationCleanup(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.WithoutCancel(ctx), sourceObservationCleanupTimeout)
}

func (r *SourceObservationRepository) now() time.Time { return r.clock().UTC() }

var _ activities.SourceObservationRepository = (*SourceObservationRepository)(nil)
var _ activities.InventoryWriter = (*inventoryWriter)(nil)

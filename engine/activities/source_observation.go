package activities

// This file owns the source-observation Activities.  They inspect the
// retained source and persist only source-level metadata or container
// structure.  They deliberately do not parse records, normalize values,
// calculate hashes, or make anything evidence.  The persistence interfaces
// below are intentionally narrow: a production implementation must bind each
// call to context.activity_execution and context.activity_receipt from
// migration 0036, and must use short transactions while a stream is open.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

const observationCleanupTimeout = 5 * time.Second

const (
	metadataFilesystem = "filesystem"
	metadataEmbedded   = "embedded"
	metadataContainer  = "container"
	metadataMediaTool  = "media_tool"
)

// Exported aliases keep the source-observation contract usable by external
// parser/tool adapters without making callers duplicate string literals.
const (
	MetadataClassFilesystem = metadataFilesystem
	MetadataClassEmbedded   = metadataEmbedded
	MetadataClassContainer  = metadataContainer
	MetadataClassMediaTool  = metadataMediaTool
)

// SourceObservationInput is the only source identity handed to an extractor
// or enumerator.  Source bytes are resolved by the implementation using the
// compact OriginalRef; they are never placed in Temporal history.
type SourceObservationInput struct {
	RequestID        string
	SourceVersionRef uiw.Ref
	OriginalRef      uiw.Ref
	DeclaredFormat   string
}

func (i SourceObservationInput) validate() error {
	if strings.TrimSpace(i.RequestID) == "" {
		return errors.New("source observation requires a request id")
	}
	if strings.TrimSpace(string(i.SourceVersionRef)) == "" {
		return errors.New("source observation requires a source version reference")
	}
	if strings.TrimSpace(string(i.OriginalRef)) == "" {
		return errors.New("source observation requires an original reference")
	}
	return nil
}

// MetadataRow is one source-level row for context.source_metadata.  A row is
// source-level by construction: there is no raw-record registry.  The native
// JSON object is retained verbatim alongside extractor provenance.
type MetadataRow struct {
	MetadataClass    string
	Metadata         json.RawMessage
	ExtractorID      string
	ExtractorVersion string
	GeneratedAt      time.Time
}

func (r MetadataRow) validate() error {
	switch r.MetadataClass {
	case metadataFilesystem, metadataEmbedded, metadataContainer, metadataMediaTool:
	default:
		return fmt.Errorf("unsupported source metadata class %q", r.MetadataClass)
	}
	if strings.TrimSpace(string(r.Metadata)) == "" {
		return errors.New("source metadata row requires a native JSON object")
	}
	var object map[string]any
	if err := json.Unmarshal(r.Metadata, &object); err != nil {
		return fmt.Errorf("source metadata must be valid JSON: %w", err)
	}
	if object == nil {
		return errors.New("source metadata must be a JSON object")
	}
	if strings.TrimSpace(r.ExtractorID) == "" {
		return errors.New("source metadata row requires an extractor id")
	}
	if r.GeneratedAt.IsZero() {
		return errors.New("source metadata row requires generated_at")
	}
	return nil
}

// MetadataObservation is returned by the extractor.  An empty row set is a
// valid, durable not_applicable result for a source with no applicable
// source-level metadata (for example a format with no embedded metadata).
type MetadataObservation struct {
	ProvenanceClass string
	Rows            []MetadataRow
}

func (o MetadataObservation) validate() error {
	switch o.ProvenanceClass {
	case "first_party_authored", "acquired_third_party", "system_generated", "unknown":
	default:
		return fmt.Errorf("unsupported provenance class %q", o.ProvenanceClass)
	}
	for index, row := range o.Rows {
		if err := row.validate(); err != nil {
			return fmt.Errorf("metadata row %d: %w", index, err)
		}
	}
	return nil
}

// SourceMetadataExtractor may call ExifTool, a PDF/media inspector, or a
// format-specific metadata reader.  It must return native metadata and tool
// provenance only; interpretation belongs to later stages.
type SourceMetadataExtractor interface {
	ExtractSourceMetadata(context.Context, SourceObservationInput) (MetadataObservation, error)
}

// MetadataPersistenceSpec is the durable idempotency coordinate and bounded
// metadata payload for one source-observation attempt.  A repository must
// create/reuse one activity_execution row keyed by IdempotencyKey, write one
// immutable activity_receipt for Attempt, and return its exact compact refs.
type MetadataPersistenceSpec struct {
	RequestID           string
	SourceVersionRef    uiw.Ref
	Stage               stagegraph.StageID
	IdempotencyKey      string
	Attempt             int32
	ProvenanceClass     string
	Rows                []MetadataRow
	NotApplicableReason string
}

type MetadataPersistenceResult struct {
	ResultRef  uiw.Ref
	ReceiptRef uiw.Ref
}

// InventoryMember is structural inventory only.  It names a source member
// and its exact byte accounting; it carries no parsed fields or assertions.
// A nil ByteOffset denotes a whole-object/member registry.  A non-nil offset
// denotes a half-open range [offset, offset+length).
type InventoryMember struct {
	Ordinal    int64
	MemberRef  uiw.Ref
	ParentRef  uiw.Ref
	ByteOffset *int64
	ByteLength int64
}

func (m InventoryMember) validate(previous int64) error {
	if m.Ordinal != previous {
		return fmt.Errorf("inventory member ordinal %d, want %d", m.Ordinal, previous)
	}
	if strings.TrimSpace(string(m.MemberRef)) == "" {
		return errors.New("inventory member requires a compact member reference")
	}
	if m.ByteLength < 0 {
		return errors.New("inventory member byte length cannot be negative")
	}
	if m.ByteOffset != nil && *m.ByteOffset < 0 {
		return errors.New("inventory member byte offset cannot be negative")
	}
	if m.ParentRef == m.MemberRef {
		return errors.New("inventory member cannot be its own parent")
	}
	return nil
}

// MemberStream is deliberately streaming.  A container with millions of
// members must not be materialized in a Temporal result or held in a long
// database transaction.
type MemberStream interface {
	Next(context.Context) (InventoryMember, error)
	Close() error
}

type MemberEnumerator interface {
	EnumerateMembers(context.Context, SourceObservationInput) (MemberStream, error)
}

type InventorySpec struct {
	RequestID        string
	SourceVersionRef uiw.Ref
	Stage            stagegraph.StageID
	IdempotencyKey   string
	Attempt          int32
}

type InventorySummary struct {
	MemberCount int64
	TotalBytes  int64
	RangeCount  int64
}

// InventoryWriter is a durable short-transaction staging boundary.  Begin
// may create context.activity_execution and an open inventory batch; Append
// must commit each bounded write independently; Commit atomically binds the
// completed membership to the ActivityReceipt.  It must never hold a
// PostgreSQL transaction while MemberStream.Next is reading external data.
type InventoryWriter interface {
	Append(context.Context, InventoryMember) error
	Commit(context.Context, InventorySummary) (resultRef uiw.Ref, receiptRef uiw.Ref, err error)
	Abort(context.Context) error
}

type SourceObservationRepository interface {
	PersistSourceMetadata(context.Context, MetadataPersistenceSpec) (MetadataPersistenceResult, error)
	BeginInventory(context.Context, InventorySpec) (InventoryWriter, error)
	RecordInventoryNotApplicable(context.Context, InventorySpec, string) (receiptRef uiw.Ref, err error)
}

// SourceObservationActivities implements the source metadata and member
// inventory bodies.  Attempt defaults to one for direct callers and is bound
// to Temporal activity.Info().Attempt by the worker.
type SourceObservationActivities struct {
	Extractor  SourceMetadataExtractor
	Enumerator MemberEnumerator
	Repository SourceObservationRepository
	Attempt    Attempt
	Heartbeat  Heartbeat
}

func (a SourceObservationActivities) validate() error {
	if a.Repository == nil {
		return errors.New("source observation activities: repository is required")
	}
	return nil
}

func (a SourceObservationActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

func (a SourceObservationActivities) heartbeat(ctx context.Context, stage stagegraph.StageID, members, bytes int64) {
	if a.Heartbeat != nil {
		a.Heartbeat(ctx, Progress{Stage: stage, MembersComplete: members, BytesComplete: bytes})
	}
}

func sourceObservationInput(req uiw.StageRequest) (SourceObservationInput, error) {
	input := SourceObservationInput{
		RequestID:        req.RequestID,
		SourceVersionRef: req.SourceVersionRef,
		OriginalRef:      req.Refs["original"],
		DeclaredFormat:   req.DeclaredFormat,
	}
	if err := input.validate(); err != nil {
		return SourceObservationInput{}, err
	}
	return input, nil
}

// CaptureFilesystemMetadata extracts and durably records the filesystem /
// acquisition metadata for the retained source.  The extractor is expected
// to return only the filesystem class when this body is registered.  It never
// receives raw records and never promotes metadata or tool output into
// evidence.
func (a SourceObservationActivities) CaptureFilesystemMetadata(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.extractSourceMetadata(ctx, req, stagegraph.CaptureFilesystemMetadata)
}

// ExtractEmbeddedMetadata records native embedded/container/media-tool
// metadata after retention. Filesystem acquisition metadata remains owned by
// CaptureFilesystemMetadata so the two Activity receipts cannot overlap.
func (a SourceObservationActivities) ExtractEmbeddedMetadata(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.extractSourceMetadata(ctx, req, stagegraph.ExtractEmbeddedMetadata)
}

func (a SourceObservationActivities) extractSourceMetadata(ctx context.Context, req uiw.StageRequest, stage stagegraph.StageID) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if a.Extractor == nil {
		return uiw.StageResult{}, errors.New("source observation activities: metadata extractor is required")
	}
	input, err := sourceObservationInput(req)
	if err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	observation, err := a.Extractor.ExtractSourceMetadata(ctx, input)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("extract source metadata: %w", err)
	}
	if err := observation.validate(); err != nil {
		return uiw.StageResult{}, fmt.Errorf("validate source metadata: %w", err)
	}
	if stage == stagegraph.CaptureFilesystemMetadata {
		for index, row := range observation.Rows {
			if row.MetadataClass != metadataFilesystem {
				return uiw.StageResult{}, fmt.Errorf("filesystem metadata row %d has non-filesystem class %q", index, row.MetadataClass)
			}
		}
	} else if stage == stagegraph.ExtractEmbeddedMetadata {
		for index, row := range observation.Rows {
			if row.MetadataClass == metadataFilesystem {
				return uiw.StageResult{}, fmt.Errorf("embedded metadata row %d has filesystem class", index)
			}
		}
	}
	spec := MetadataPersistenceSpec{
		RequestID: req.RequestID, SourceVersionRef: req.SourceVersionRef,
		Stage: stage, IdempotencyKey: observationIdempotencyKey(req, stage, req.Refs["original"]),
		Attempt: a.attempt(ctx), ProvenanceClass: observation.ProvenanceClass,
		Rows: append([]MetadataRow(nil), observation.Rows...),
	}
	if len(spec.Rows) == 0 {
		spec.NotApplicableReason = "source has no applicable source-level metadata"
	}
	persisted, err := a.Repository.PersistSourceMetadata(ctx, spec)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("persist source metadata: %w", err)
	}
	if persisted.ReceiptRef == "" {
		return uiw.StageResult{}, errors.New("source metadata persistence returned no Activity receipt reference")
	}
	if len(spec.Rows) == 0 {
		if persisted.ResultRef != "" {
			return uiw.StageResult{}, errors.New("not-applicable metadata persistence returned a usable result reference")
		}
		return uiw.StageResult{Stage: stage, Status: uiw.StatusNotApplicable, ReceiptRef: persisted.ReceiptRef, Reason: spec.NotApplicableReason}, nil
	}
	if persisted.ResultRef == "" {
		return uiw.StageResult{}, errors.New("source metadata persistence returned no result reference")
	}
	return uiw.StageResult{Stage: stage, Status: uiw.StatusSuccess, Ref: persisted.ResultRef, ReceiptRef: persisted.ReceiptRef}, nil
}

// InventoryContainer enumerates only structural members and exact byte/range
// accounting.  It streams through a durable writer, heartbeats compact
// progress, and refuses to commit empty, gapped, negative, or inconsistent
// membership.
func (a SourceObservationActivities) InventoryContainer(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.inventoryMembers(ctx, req, stagegraph.InventoryContainer)
}

func (a SourceObservationActivities) inventoryMembers(ctx context.Context, req uiw.StageRequest, stage stagegraph.StageID) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if a.Enumerator == nil {
		return uiw.StageResult{}, errors.New("source observation activities: member enumerator is required")
	}
	input, err := sourceObservationInput(req)
	if err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	stream, err := a.Enumerator.EnumerateMembers(ctx, input)
	if err != nil {
		if errors.Is(err, ErrNotApplicable) {
			return a.recordInventoryNotApplicable(ctx, req, stage, err.Error())
		}
		return uiw.StageResult{}, fmt.Errorf("enumerate source members: %w", err)
	}
	if stream == nil {
		return uiw.StageResult{}, errors.New("member enumerator returned a nil stream")
	}
	streamClosed := false
	defer func() {
		if !streamClosed {
			_ = stream.Close()
		}
	}()

	spec := InventorySpec{
		RequestID: req.RequestID, SourceVersionRef: req.SourceVersionRef,
		Stage: stage, IdempotencyKey: observationIdempotencyKey(req, stage, req.Refs["original"]),
		Attempt: a.attempt(ctx),
	}
	writer, err := a.Repository.BeginInventory(ctx, spec)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("begin member inventory: %w", err)
	}
	if writer == nil {
		return uiw.StageResult{}, errors.New("member inventory repository returned a nil writer")
	}
	committed := false
	defer func() {
		if !committed {
			cleanupCtx, cancel := observationCleanup(ctx)
			defer cancel()
			_ = writer.Abort(cleanupCtx)
		}
	}()

	var ordinal, totalBytes, rangeCount int64
	for {
		if err := ctx.Err(); err != nil {
			return uiw.StageResult{}, err
		}
		member, nextErr := stream.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return uiw.StageResult{}, fmt.Errorf("read inventory member %d: %w", ordinal, nextErr)
		}
		if err := member.validate(ordinal); err != nil {
			return uiw.StageResult{}, fmt.Errorf("validate inventory member %d: %w", ordinal, err)
		}
		if member.ByteLength > (int64(^uint64(0)>>1) - totalBytes) {
			return uiw.StageResult{}, errors.New("inventory byte accounting overflow")
		}
		if member.ByteOffset != nil {
			rangeCount++
		}
		if err := writer.Append(ctx, member); err != nil {
			return uiw.StageResult{}, fmt.Errorf("persist inventory member %d: %w", ordinal, err)
		}
		totalBytes += member.ByteLength
		ordinal++
		a.heartbeat(ctx, stage, ordinal, totalBytes)
	}
	if err := stream.Close(); err != nil {
		return uiw.StageResult{}, fmt.Errorf("close member inventory stream: %w", err)
	}
	streamClosed = true
	if ordinal == 0 {
		cleanupCtx, cancel := observationCleanup(ctx)
		defer cancel()
		_ = writer.Abort(cleanupCtx)
		return a.recordInventoryNotApplicable(ctx, req, stage, "source has no container members")
	}
	resultRef, receiptRef, err := writer.Commit(ctx, InventorySummary{MemberCount: ordinal, TotalBytes: totalBytes, RangeCount: rangeCount})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("commit member inventory: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return uiw.StageResult{}, errors.New("member inventory commit returned incomplete compact references")
	}
	committed = true
	return uiw.StageResult{Stage: stage, Status: uiw.StatusSuccess, Ref: resultRef, ReceiptRef: receiptRef}, nil
}

var ErrNotApplicable = errors.New("source observation not applicable")

func (a SourceObservationActivities) recordInventoryNotApplicable(ctx context.Context, req uiw.StageRequest, stage stagegraph.StageID, reason string) (uiw.StageResult, error) {
	reason = strings.TrimSpace(reason)
	if reason == "" {
		reason = "source has no container members"
	}
	receiptRef, err := a.Repository.RecordInventoryNotApplicable(ctx, InventorySpec{
		RequestID: req.RequestID, SourceVersionRef: req.SourceVersionRef,
		Stage: stage, IdempotencyKey: observationIdempotencyKey(req, stage, req.Refs["original"]),
		Attempt: a.attempt(ctx),
	}, reason)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("record inventory not-applicable result: %w", err)
	}
	if receiptRef == "" {
		return uiw.StageResult{}, errors.New("inventory not-applicable result returned no Activity receipt reference")
	}
	return uiw.StageResult{Stage: stage, Status: uiw.StatusNotApplicable, ReceiptRef: receiptRef, Reason: reason}, nil
}

func observationIdempotencyKey(req uiw.StageRequest, stage stagegraph.StageID, subject uiw.Ref) string {
	return fmt.Sprintf("source-observation:%s:%s:%s:%s", req.RequestID, req.SourceVersionRef, stage, subject)
}

func observationCleanup(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.WithoutCancel(ctx), observationCleanupTimeout)
}

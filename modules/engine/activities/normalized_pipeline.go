// Package activities: this file owns the seven normalized-side Activities —
// normalize_generation_activity, persist_normalized_generation_activity,
// persist_lineage_activity, validate_raw_lineage_activity,
// verify_normalized_generation_activity, seal_generation_activity, and
// publish_generation_activity. It follows the exact split hashing.go and
// parser_runtime.go already established in this package: an Activity method
// does compute/validation using compact Store-provided streams, and the
// PostgreSQL Store (engine/postgres) owns every SQL 0036 transaction and
// idempotency coordinate. It reuses this package's existing unexported
// helpers (requiredRef, success, newNormalizedAccumulator,
// CanonNormalizedRecord, CanonNormalizedGeneration, ByteMemberStream,
// DigestMember, Attempt) rather than redefining them.
//
// normalize_generation_activity is transform-only: it never writes
// context.normalized_record_identity or context.normalization_lineage.
// persist_normalized_generation_activity is the only write for the former;
// persist_lineage_activity is the only write for the latter. Every write is
// fail-closed on the sql/0036 guard triggers — this file never bypasses them
// (no redaction/masking, no partial seal, no publish without a receipt).
package activities

import (
	"context"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/lowcarbdev/sbv/pkg/custodyhash"

	"github.com/Cursedpotential/probata/engine/normalize"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

// NormalizeExecutionSpec is the compact execution receipt payload persisted
// by normalize_generation_activity. BundleRef was minted by the caller-owned
// normalize.BundleWriter; persist_normalized_generation_activity owns
// canonical normalized-record persistence, not this Activity.
type NormalizeExecutionSpec struct {
	RequestID         string
	SourceVersionRef  proffer.Ref
	RawGenerationRef  proffer.Ref
	NormalizerID      string
	NormalizerVersion string
	BundleRef         proffer.Ref
	Attempt           int32
}

// PersistNormalizedGenerationSpec is resolved entirely from BundleRef: the
// bundle header (written by normalize_generation_activity) names its own raw
// generation and normalizer identity, so this stage receives no separate
// "raw_generation" reference — see engine/proffer/workflow.go stage 15.
type PersistNormalizedGenerationSpec struct {
	RequestID        string
	SourceVersionRef proffer.Ref
	BundleRef        proffer.Ref
	Attempt          int32
}

// PersistLineageSpec derives normalization_lineage purely from the ordered
// correspondence between the already-persisted raw and normalized
// generations (see normalize.GenericMessageNormalizer's doc comment): this
// stage never receives the normalize bundle registry.
type PersistLineageSpec struct {
	RequestID               string
	SourceVersionRef        proffer.Ref
	NormalizedGenerationRef proffer.Ref
	RawGenerationRef        proffer.Ref
	Attempt                 int32
}

type ValidateRawLineageSpec struct {
	RequestID        string
	SourceVersionRef proffer.Ref
	LineageSetRef    proffer.Ref
	Attempt          int32
}

// VerifyNormalizedGenerationSpec carries the Activity-computed independent
// recomputation so the Store need only compare and persist, never recompute
// a hash itself.
type VerifyNormalizedGenerationSpec struct {
	RequestID              string
	SourceVersionRef       proffer.Ref
	LineageValidationRef   proffer.Ref
	ManifestDigestRef      proffer.Ref
	RecomputedDigest       string
	RecomputedConstruction string
	RecomputedMemberCount  int64
	Attempt                int32
}

type SealGenerationSpec struct {
	RequestID        string
	SourceVersionRef proffer.Ref
	VerificationRef  proffer.Ref
	Attempt          int32
}

type PublishGenerationSpec struct {
	RequestID           string
	SourceVersionRef    proffer.Ref
	SealedGenerationRef proffer.Ref
	Attempt             int32
}

// NormalizedPipelineStore is the PostgreSQL/immutable-storage boundary for
// all seven normalized-side Activities. Every write must go through
// context.activity_execution/context.activity_receipt exactly as the other
// Stores in this package do, and every generation/lineage write must satisfy
// the sql/0036 guard triggers rather than reimplement their checks.
type NormalizedPipelineStore interface {
	// ResolveNormalizerInput resolves the source-version-level facts
	// (provenance class, acquired_at) and opens a streaming view over the
	// already-sealed raw generation named by req.Refs["raw_generation"].
	ResolveNormalizerInput(context.Context, proffer.StageRequest) (normalize.NormalizerInput, error)
	// OpenNormalizedBundleWriter opens the caller-owned streaming sink that
	// normalize.Execute writes normalized records to. This Store has no
	// bundle-bytes persistence authority of its own, mirroring
	// postgres.ParserStore's BundleWriterFactory.
	OpenNormalizedBundleWriter(context.Context, proffer.StageRequest, normalize.NormalizerInput) (normalize.BundleWriter, error)
	PersistNormalizeExecution(context.Context, NormalizeExecutionSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)

	PersistNormalizedGeneration(context.Context, PersistNormalizedGenerationSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)

	PersistLineage(context.Context, PersistLineageSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)

	ValidateRawLineage(context.Context, ValidateRawLineageSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)

	// OpenNormalizedGenerationRecords streams every normalized_record_identity
	// row's canonical_bytes, in ordinal order, for the generation named by the
	// hash-receipt reference ref. verify_normalized_generation_activity
	// independently rehashes each member itself; the Store must not compute
	// or return a digest here.
	OpenNormalizedGenerationRecords(ctx context.Context, manifestDigestRef proffer.Ref) (ByteMemberStream, error)
	VerifyNormalizedGeneration(context.Context, VerifyNormalizedGenerationSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)

	SealGeneration(context.Context, SealGenerationSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)

	PublishGeneration(context.Context, PublishGenerationSpec) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)
}

// NormalizedPipelineActivities implements the seven normalized-side Activity
// bodies. Attempt is injectable for direct tests and defaults to one; a
// Temporal worker binds it to activity.GetInfo(ctx).Attempt exactly as the
// other Activities structs in this package do.
type NormalizedPipelineActivities struct {
	Store      NormalizedPipelineStore
	Normalizer normalize.Adapter
	Attempt    Attempt
}

func (a NormalizedPipelineActivities) validate() error {
	if a.Store == nil {
		return errors.New("normalized pipeline activities: store is required")
	}
	if a.Normalizer == nil {
		return errors.New("normalized pipeline activities: normalizer is required")
	}
	return nil
}

func (a NormalizedPipelineActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

func (a NormalizedPipelineActivities) requireRequestAndSource(req proffer.StageRequest, stage stagegraph.StageID) error {
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return fmt.Errorf("%s requires request and source version references", stage)
	}
	return nil
}

// NormalizeGeneration streams the sealed raw generation through the injected
// normalize.Adapter and finalizes exactly one immutable bundle. It never
// touches context.normalized_record_identity or
// context.normalization_lineage.
func (a NormalizedPipelineActivities) NormalizeGeneration(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.NormalizeGeneration); err != nil {
		return proffer.StageResult{}, err
	}
	rawGenerationRef, err := requiredRef(req, "raw_generation")
	if err != nil {
		return proffer.StageResult{}, err
	}
	if _, err := requiredRef(req, "raw_source_verification"); err != nil {
		return proffer.StageResult{}, err
	}
	input, err := a.Store.ResolveNormalizerInput(ctx, req)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("resolve normalizer input: %w", err)
	}
	if input.SourceVersionRef != string(req.SourceVersionRef) || input.RawGenerationRef != string(rawGenerationRef) {
		return proffer.StageResult{}, errors.New("resolved normalizer input does not match request")
	}
	writer, err := a.Store.OpenNormalizedBundleWriter(ctx, req, input)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("open normalized bundle writer: %w", err)
	}
	bundleResult, err := normalize.Execute(ctx, input, a.Normalizer, writer)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("execute normalizer: %w", err)
	}
	capability := a.Normalizer.Capability()
	resultRef, receiptRef, err := a.Store.PersistNormalizeExecution(ctx, NormalizeExecutionSpec{
		RequestID:         req.RequestID,
		SourceVersionRef:  req.SourceVersionRef,
		RawGenerationRef:  rawGenerationRef,
		NormalizerID:      capability.NormalizerID,
		NormalizerVersion: capability.NormalizerVersion,
		BundleRef:         proffer.Ref(bundleResult.BundleRef),
		Attempt:           a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("persist normalize execution: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("persisted normalize execution lacks result or activity receipt reference")
	}
	return success(stagegraph.NormalizeGeneration, resultRef, receiptRef), nil
}

// PersistNormalizedGeneration is the only write for
// context.normalized_generation and context.normalized_record_identity.
func (a NormalizedPipelineActivities) PersistNormalizedGeneration(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.PersistNormalizedGeneration); err != nil {
		return proffer.StageResult{}, err
	}
	bundleRef, err := requiredRef(req, "normalized_bundle")
	if err != nil {
		return proffer.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.PersistNormalizedGeneration(ctx, PersistNormalizedGenerationSpec{
		RequestID:        req.RequestID,
		SourceVersionRef: req.SourceVersionRef,
		BundleRef:        bundleRef,
		Attempt:          a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("persist normalized generation: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("persisted normalized generation lacks result or activity receipt reference")
	}
	return success(stagegraph.PersistNormalizedGeneration, resultRef, receiptRef), nil
}

// PersistLineage is the only write for context.normalization_lineage.
func (a NormalizedPipelineActivities) PersistLineage(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.PersistLineage); err != nil {
		return proffer.StageResult{}, err
	}
	normalizedGenerationRef, err := requiredRef(req, "normalized_generation")
	if err != nil {
		return proffer.StageResult{}, err
	}
	rawGenerationRef, err := requiredRef(req, "raw_generation")
	if err != nil {
		return proffer.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.PersistLineage(ctx, PersistLineageSpec{
		RequestID:               req.RequestID,
		SourceVersionRef:        req.SourceVersionRef,
		NormalizedGenerationRef: normalizedGenerationRef,
		RawGenerationRef:        rawGenerationRef,
		Attempt:                 a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("persist lineage: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("persisted lineage lacks result or activity receipt reference")
	}
	return success(stagegraph.PersistLineage, resultRef, receiptRef), nil
}

// ValidateRawLineage independently verifies every normalized record in the
// generation named by lineage_set has at least one lineage edge and that
// every referenced raw record belongs to the same raw generation, and
// records a context.reconciliation_receipt of kind raw_lineage_validation.
func (a NormalizedPipelineActivities) ValidateRawLineage(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.ValidateRawLineage); err != nil {
		return proffer.StageResult{}, err
	}
	lineageSetRef, err := requiredRef(req, "lineage_set")
	if err != nil {
		return proffer.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.ValidateRawLineage(ctx, ValidateRawLineageSpec{
		RequestID:        req.RequestID,
		SourceVersionRef: req.SourceVersionRef,
		LineageSetRef:    lineageSetRef,
		Attempt:          a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("validate raw lineage: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("raw lineage validation lacks result or activity receipt reference")
	}
	return success(stagegraph.ValidateRawLineage, resultRef, receiptRef), nil
}

// VerifyNormalizedGeneration independently recomputes the ordered
// normalized-generation manifest digest from persisted canonical_bytes —
// never from the already-stored hash_receipt — and records a
// context.reconciliation_receipt of kind normalized_generation_verification
// comparing that fresh recomputation against the stored receipt.
func (a NormalizedPipelineActivities) VerifyNormalizedGeneration(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.VerifyNormalizedGeneration); err != nil {
		return proffer.StageResult{}, err
	}
	lineageValidationRef, err := requiredRef(req, "lineage_validation")
	if err != nil {
		return proffer.StageResult{}, err
	}
	manifestDigestRef, err := requiredRef(req, "normalized_generation_manifest_digest")
	if err != nil {
		return proffer.StageResult{}, err
	}

	stream, err := a.Store.OpenNormalizedGenerationRecords(ctx, manifestDigestRef)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("open normalized generation records: %w", err)
	}
	defer stream.Close()

	acc := newNormalizedAccumulator()
	var count int64
	for {
		if err := ctx.Err(); err != nil {
			return proffer.StageResult{}, err
		}
		member, nextErr := stream.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return proffer.StageResult{}, fmt.Errorf("read normalized record %d: %w", count, nextErr)
		}
		if member.Ordinal != count {
			return proffer.StageResult{}, fmt.Errorf("normalized record ordinal %d, want %d", member.Ordinal, count)
		}
		if member.Canon != CanonNormalizedRecord {
			_ = member.Reader.Close()
			return proffer.StageResult{}, fmt.Errorf("normalized record %q has unexpected canon %q", member.SubjectRef, member.Canon)
		}
		digest, hashErr := custodyhash.HashReaderH1(member.Reader)
		closeErr := member.Reader.Close()
		if hashErr != nil {
			return proffer.StageResult{}, fmt.Errorf("hash normalized record %q: %w", member.SubjectRef, hashErr)
		}
		if closeErr != nil {
			return proffer.StageResult{}, fmt.Errorf("close normalized record %q: %w", member.SubjectRef, closeErr)
		}
		if err := acc.Add(DigestMember{SubjectRef: member.SubjectRef, Ordinal: count, Digest: digest, Canon: member.Canon}); err != nil {
			return proffer.StageResult{}, fmt.Errorf("fold normalized record %q: %w", member.SubjectRef, err)
		}
		count++
	}
	if count == 0 {
		return proffer.StageResult{}, errors.New("verify normalized generation refuses to recompute over zero records")
	}

	resultRef, receiptRef, err := a.Store.VerifyNormalizedGeneration(ctx, VerifyNormalizedGenerationSpec{
		RequestID:              req.RequestID,
		SourceVersionRef:       req.SourceVersionRef,
		LineageValidationRef:   lineageValidationRef,
		ManifestDigestRef:      manifestDigestRef,
		RecomputedDigest:       acc.Sum(),
		RecomputedConstruction: CanonNormalizedGeneration,
		RecomputedMemberCount:  count,
		Attempt:                a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("verify normalized generation: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("normalized generation verification lacks result or activity receipt reference")
	}
	return success(stagegraph.VerifyNormalizedGeneration, resultRef, receiptRef), nil
}

// SealGeneration advances context.normalized_generation open -> sealed. The
// sql/0036 guard trigger, not this Activity, is the fail-closed authority for
// every precondition (raw generation sealed, contiguous ordinals, lineage
// present, digest receipts present, reconciliation receipts present); this
// Activity never bypasses it with a partial or forced seal.
func (a NormalizedPipelineActivities) SealGeneration(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.SealGeneration); err != nil {
		return proffer.StageResult{}, err
	}
	verificationRef, err := requiredRef(req, "normalized_verification")
	if err != nil {
		return proffer.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.SealGeneration(ctx, SealGenerationSpec{
		RequestID:        req.RequestID,
		SourceVersionRef: req.SourceVersionRef,
		VerificationRef:  verificationRef,
		Attempt:          a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("seal generation: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("sealed generation lacks result or activity receipt reference")
	}
	return success(stagegraph.SealGeneration, resultRef, receiptRef), nil
}

// PublishGeneration is the sole successor of seal_generation_activity: the
// sink whose transitive dependency closure is every other stage. It never
// publishes without a durable context.normalized_generation_publication row
// and its successful activity_receipt.
func (a NormalizedPipelineActivities) PublishGeneration(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := a.requireRequestAndSource(req, stagegraph.PublishGeneration); err != nil {
		return proffer.StageResult{}, err
	}
	sealedGenerationRef, err := requiredRef(req, "sealed_generation")
	if err != nil {
		return proffer.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.PublishGeneration(ctx, PublishGenerationSpec{
		RequestID:           req.RequestID,
		SourceVersionRef:    req.SourceVersionRef,
		SealedGenerationRef: sealedGenerationRef,
		Attempt:             a.attempt(ctx),
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("publish generation: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("published generation lacks result or activity receipt reference")
	}
	return success(stagegraph.PublishGeneration, resultRef, receiptRef), nil
}

// Package activities implements the raw-generation Activities for the
// proffer workflow (formerly universal import workflow): persist_raw_generation_activity,
// reconcile_record_accounting_activity, reconcile_byte_coverage_activity, and
// verify_raw_coverage_against_source_activity. Persistence is the only
// Activity that writes raw records; the other three verify only — none of
// them parses, normalizes, or hashes.
package activities

import (
	"context"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/Cursedpotential/probata/engine/parser"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

// RawGenerationSpec is the compact, already-resolved input to
// persist_raw_generation_activity. ParserID/ParserVersion are read from the
// immutable bundle header, not the workflow request, so persistence pins the
// exact parser identity that produced the bundle.
type RawGenerationSpec struct {
	RequestID        string
	Attempt          int32
	SourceVersionRef proffer.Ref
	DeclaredFormat   string
	ParserID         string
	ParserVersion    string
	BundleRef        proffer.Ref
}

// RawBundleReader streams one already-finalized parser bundle back for
// persistence, one record at a time. Header must be called before Next; Next
// returns io.EOF once every record has been consumed, after which Trailer
// becomes valid. No implementation may buffer the full record set in memory.
type RawBundleReader interface {
	Header(context.Context) (parser.BundleHeader, error)
	Next(context.Context) (parser.RawRecordEnvelope, error)
	Trailer(context.Context) (parser.BundleAccounting, error)
	Close() error
}

// RawGenerationWriter incrementally persists exactly the parser-emitted raw
// records — parsed, rejected, malformed, unknown, unparsed, and envelope
// spans alike, contiguous from ordinal 0 — into one raw generation. Append is
// called once per record so no implementation holds more than one record in
// memory at a time; Commit seals the generation's Activity receipt only after
// the caller supplies the bundle's own accounting for cross-check.
type RawGenerationWriter interface {
	Append(context.Context, parser.RawRecordEnvelope) error
	Commit(context.Context, parser.BundleAccounting) (resultRef proffer.Ref, receiptRef proffer.Ref, err error)
	Abort(context.Context) error
}

// RawGenerationChainSpec is the compact input shared by
// reconcile_record_accounting_activity and reconcile_byte_coverage_activity.
// Both key entirely off the raw generation's sealed context fingerprint chain
// reference — the exact result produced by fingerprint_raw_generation_activity
// — because neither may run until the raw generation's integrity chain exists.
type RawGenerationChainSpec struct {
	RequestID             string
	Attempt               int32
	SourceVersionRef      proffer.Ref
	RawGenerationChainRef proffer.Ref
}

// RawSourceVerificationSpec is the compact input to
// verify_raw_coverage_against_source_activity: the two reconciliation
// receipts it joins, the context source fingerprint, and the raw-generation
// context fingerprint chain, which this Activity independently recomputes.
type RawSourceVerificationSpec struct {
	RequestID                   string
	Attempt                     int32
	SourceVersionRef            proffer.Ref
	AccountingRef               proffer.Ref
	CoverageRef                 proffer.Ref
	ContextSourceFingerprintRef proffer.Ref
	RawGenerationChainRef       proffer.Ref
}

// ReconciliationOutcome is the durable result of one reconciliation or
// verification write. Status carries the workflow-facing business outcome —
// success, failed, or not_applicable — and is never inferred from a Go error:
// a discrepancy is a real, receipted finding, not an execution failure.
type ReconciliationOutcome struct {
	Ref        proffer.Ref
	ReceiptRef proffer.Ref
	Status     proffer.Status
	Reason     string
}

func (o ReconciliationOutcome) validate(stage stagegraph.StageID) error {
	if o.ReceiptRef == "" {
		return fmt.Errorf("%s outcome lacks an activity receipt reference", stage)
	}
	switch o.Status {
	case proffer.StatusSuccess:
		if o.Ref == "" {
			return fmt.Errorf("%s success outcome lacks a result reference", stage)
		}
	case proffer.StatusFailed, proffer.StatusNotApplicable:
		if strings.TrimSpace(o.Reason) == "" {
			return fmt.Errorf("%s %s outcome lacks a reason", stage, o.Status)
		}
	default:
		return fmt.Errorf("%s outcome has unsupported status %q", stage, o.Status)
	}
	return nil
}

// RawPipelineRepository is the PostgreSQL storage boundary for the four raw-
// generation Activities. Implementations must make every write retry-safe
// using context.activity_execution and context.activity_receipt: a repeated
// idempotency coordinate returns the existing durable outcome rather than
// writing a second time.
type RawPipelineRepository interface {
	OpenRawBundle(context.Context, proffer.Ref) (RawBundleReader, error)
	BeginRawGeneration(context.Context, RawGenerationSpec) (RawGenerationWriter, error)
	ReconcileRecordAccounting(context.Context, RawGenerationChainSpec) (ReconciliationOutcome, error)
	ReconcileByteCoverage(context.Context, RawGenerationChainSpec) (ReconciliationOutcome, error)
	VerifyRawCoverageAgainstSource(context.Context, RawSourceVerificationSpec) (ReconciliationOutcome, error)
}

// RawPipelineActivities implements the four atomic raw-generation Activities.
// Attempt is injectable for direct tests and defaults to one; a Temporal
// worker binds it to activity.GetInfo(ctx).Attempt alongside every other
// Activities struct in this package.
type RawPipelineActivities struct {
	Repository RawPipelineRepository
	Heartbeat  Heartbeat
	Attempt    Attempt
}

func (a RawPipelineActivities) validate() error {
	if a.Repository == nil {
		return errors.New("raw pipeline activities: repository is required")
	}
	return nil
}

func (a RawPipelineActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

func (a RawPipelineActivities) heartbeat(ctx context.Context, progress Progress) {
	if a.Heartbeat != nil {
		a.Heartbeat(ctx, progress)
	}
}

// PersistRawGeneration streams the immutable bundle referenced by
// "raw_bundle" back into the governed source-format raw generation. It
// re-validates every record against the declared format and re-derives the
// bundle's own accounting from the records it actually persisted before
// trusting the bundle's trailer, so a corrupted or truncated bundle fails
// closed rather than silently under-persisting.
func (a RawPipelineActivities) PersistRawGeneration(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return proffer.StageResult{}, fmt.Errorf("%s requires request and source version references", stagegraph.PersistRawGeneration)
	}
	if strings.TrimSpace(req.DeclaredFormat) == "" {
		return proffer.StageResult{}, fmt.Errorf("%s requires a declared format", stagegraph.PersistRawGeneration)
	}
	bundleRef, err := requiredRawRef(req, stagegraph.PersistRawGeneration, "raw_bundle")
	if err != nil {
		return proffer.StageResult{}, err
	}

	reader, err := a.Repository.OpenRawBundle(ctx, bundleRef)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("open raw bundle %q: %w", bundleRef, err)
	}
	defer reader.Close()

	header, err := reader.Header(ctx)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("read raw bundle header: %w", err)
	}
	if header.ContractVersion != parser.ContractVersion {
		return proffer.StageResult{}, fmt.Errorf("raw bundle contract version %q is unsupported", header.ContractVersion)
	}
	if header.SourceVersionRef != string(req.SourceVersionRef) {
		return proffer.StageResult{}, errors.New("raw bundle belongs to a different source version")
	}
	if string(header.FormatID) != req.DeclaredFormat {
		return proffer.StageResult{}, errors.New("raw bundle format does not match the declared format")
	}
	if strings.TrimSpace(header.ParserID) == "" || strings.TrimSpace(header.ParserVersion) == "" {
		return proffer.StageResult{}, errors.New("raw bundle lacks parser identity")
	}

	writer, err := a.Repository.BeginRawGeneration(ctx, RawGenerationSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), SourceVersionRef: req.SourceVersionRef,
		DeclaredFormat: req.DeclaredFormat, ParserID: header.ParserID, ParserVersion: header.ParserVersion,
		BundleRef: bundleRef,
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("begin raw generation: %w", err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = writer.Abort(context.WithoutCancel(ctx))
		}
	}()

	format := parser.FormatID(req.DeclaredFormat)
	var count uint64
	var tally parser.BundleAccounting
	for {
		if err := ctx.Err(); err != nil {
			return proffer.StageResult{}, err
		}
		record, nextErr := reader.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return proffer.StageResult{}, fmt.Errorf("read raw bundle record %d: %w", count, nextErr)
		}
		if record.RecordOrdinal != count {
			return proffer.StageResult{}, fmt.Errorf("raw bundle record ordinal %d, want contiguous ordinal %d", record.RecordOrdinal, count)
		}
		if err := record.Validate(format); err != nil {
			return proffer.StageResult{}, fmt.Errorf("raw bundle record %d: %w", count, err)
		}
		if err := writer.Append(ctx, record); err != nil {
			return proffer.StageResult{}, fmt.Errorf("persist raw record %d: %w", count, err)
		}
		count++
		tallyRawAccounting(&tally, record)
		a.heartbeat(ctx, Progress{Stage: stagegraph.PersistRawGeneration, MembersComplete: int64(count)})
	}
	if count == 0 {
		return proffer.StageResult{}, errors.New("persist raw generation refuses to seal an empty raw bundle")
	}
	trailer, err := reader.Trailer(ctx)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("read raw bundle trailer: %w", err)
	}
	if trailer != tally {
		return proffer.StageResult{}, fmt.Errorf("raw bundle trailer accounting %+v does not match streamed counts %+v", trailer, tally)
	}
	resultRef, receiptRef, err := writer.Commit(ctx, trailer)
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("commit raw generation: %w", err)
	}
	committed = true
	if resultRef == "" || receiptRef == "" {
		return proffer.StageResult{}, errors.New("persisted raw generation lacks result or activity receipt reference")
	}
	return rawPipelineSuccess(stagegraph.PersistRawGeneration, resultRef, receiptRef), nil
}

// tallyRawAccounting mirrors parser.validatingSink's counting rule: emitted
// counts record_status=parsed, the other four counts mirror their own
// status, and envelope spans have no separate v1 accounting field.
func tallyRawAccounting(tally *parser.BundleAccounting, record parser.RawRecordEnvelope) {
	tally.Attachments += uint64(len(record.Attachments))
	switch record.RecordStatus {
	case parser.StatusParsed:
		tally.Emitted++
	case parser.StatusRejected:
		tally.Rejected++
	case parser.StatusMalformed:
		tally.Malformed++
	case parser.StatusUnknown:
		tally.Unknown++
	case parser.StatusUnparsed:
		tally.Unparsed++
	case parser.StatusEnvelope:
		// Envelope spans deliberately have no separate v1 accounting field.
	}
}

// ReconcileRecordAccounting verifies only that the raw generation's durable
// record/attachment counts and ordering match what persist_raw_generation
// declared. It never re-persists or re-derives raw data.
func (a RawPipelineActivities) ReconcileRecordAccounting(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	return a.reconcileChain(ctx, req, stagegraph.ReconcileRecordAccounting, a.Repository.ReconcileRecordAccounting)
}

// ReconcileByteCoverage verifies only byte/span coverage of the raw
// generation against its original retained object, explaining every gap.
func (a RawPipelineActivities) ReconcileByteCoverage(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	return a.reconcileChain(ctx, req, stagegraph.ReconcileByteCoverage, a.Repository.ReconcileByteCoverage)
}

func (a RawPipelineActivities) reconcileChain(
	ctx context.Context, req proffer.StageRequest, stage stagegraph.StageID,
	call func(context.Context, RawGenerationChainSpec) (ReconciliationOutcome, error),
) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return proffer.StageResult{}, fmt.Errorf("%s requires request and source version references", stage)
	}
	chainRef, err := requiredRawRef(req, stage, "raw_generation_chain")
	if err != nil {
		return proffer.StageResult{}, err
	}
	outcome, err := call(ctx, RawGenerationChainSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), SourceVersionRef: req.SourceVersionRef,
		RawGenerationChainRef: chainRef,
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("%s: %w", stage, err)
	}
	if err := outcome.validate(stage); err != nil {
		return proffer.StageResult{}, err
	}
	return rawPipelineOutcome(stage, outcome), nil
}

// VerifyRawCoverageAgainstSource compares only the raw coverage/recomposition
// proof against the context source fingerprint. It does not normalize and does
// not trust the earlier generation fingerprint computation; the repository
// must independently recompute it.
func (a RawPipelineActivities) VerifyRawCoverageAgainstSource(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	if err := a.validate(); err != nil {
		return proffer.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return proffer.StageResult{}, err
	}
	stage := stagegraph.VerifyRawCoverageAgainstSource
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return proffer.StageResult{}, fmt.Errorf("%s requires request and source version references", stage)
	}
	accountingRef, err := requiredRawRef(req, stage, "accounting")
	if err != nil {
		return proffer.StageResult{}, err
	}
	coverageRef, err := requiredRawRef(req, stage, "coverage")
	if err != nil {
		return proffer.StageResult{}, err
	}
	contextSourceFingerprintRef, err := requiredRawRefWithLegacyAlias(
		req, stage, "context_source_fingerprint", "h1",
	)
	if err != nil {
		return proffer.StageResult{}, err
	}
	chainRef, err := requiredRawRef(req, stage, "raw_generation_chain")
	if err != nil {
		return proffer.StageResult{}, err
	}
	outcome, err := a.Repository.VerifyRawCoverageAgainstSource(ctx, RawSourceVerificationSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), SourceVersionRef: req.SourceVersionRef,
		AccountingRef: accountingRef, CoverageRef: coverageRef,
		ContextSourceFingerprintRef: contextSourceFingerprintRef, RawGenerationChainRef: chainRef,
	})
	if err != nil {
		return proffer.StageResult{}, fmt.Errorf("%s: %w", stage, err)
	}
	if err := outcome.validate(stage); err != nil {
		return proffer.StageResult{}, err
	}
	return rawPipelineOutcome(stage, outcome), nil
}

// requiredRawRefWithLegacyAlias keeps already-open Temporal histories build-
// safe while making canonical new requests unambiguous. New workflows always
// emit canonicalName; legacyName is read-only compatibility and is rejected if
// both names are supplied with different values.
func requiredRawRefWithLegacyAlias(req proffer.StageRequest, stage stagegraph.StageID, canonicalName, legacyName string) (proffer.Ref, error) {
	canonical, legacy := req.Refs[canonicalName], req.Refs[legacyName]
	if canonical != "" && legacy != "" && canonical != legacy {
		return "", fmt.Errorf("%s received conflicting %q and legacy %q references", stage, canonicalName, legacyName)
	}
	if canonical != "" {
		return canonical, nil
	}
	if legacy != "" {
		return legacy, nil
	}
	return "", fmt.Errorf("%s requires non-empty %q reference", stage, canonicalName)
}

func requiredRawRef(req proffer.StageRequest, stage stagegraph.StageID, name string) (proffer.Ref, error) {
	ref := req.Refs[name]
	if strings.TrimSpace(string(ref)) == "" {
		return "", fmt.Errorf("%s requires non-empty %q reference", stage, name)
	}
	return ref, nil
}

func rawPipelineSuccess(stage stagegraph.StageID, resultRef, receiptRef proffer.Ref) proffer.StageResult {
	return proffer.StageResult{Stage: stage, Status: proffer.StatusSuccess, Ref: resultRef, ReceiptRef: receiptRef}
}

func rawPipelineOutcome(stage stagegraph.StageID, outcome ReconciliationOutcome) proffer.StageResult {
	return proffer.StageResult{
		Stage: stage, Status: outcome.Status, Ref: outcome.Ref, ReceiptRef: outcome.ReceiptRef, Reason: outcome.Reason,
	}
}

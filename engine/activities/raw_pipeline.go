// Package activities implements the raw-generation Activities for the
// universal import workflow: persist_raw_generation_activity,
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

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// RawGenerationSpec is the compact, already-resolved input to
// persist_raw_generation_activity. ParserID/ParserVersion are read from the
// immutable bundle header, not the workflow request, so persistence pins the
// exact parser identity that produced the bundle.
type RawGenerationSpec struct {
	RequestID        string
	Attempt          int32
	SourceVersionRef uiw.Ref
	DeclaredFormat   string
	ParserID         string
	ParserVersion    string
	BundleRef        uiw.Ref
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
	Commit(context.Context, parser.BundleAccounting) (resultRef uiw.Ref, receiptRef uiw.Ref, err error)
	Abort(context.Context) error
}

// RawGenerationChainSpec is the compact input shared by
// reconcile_record_accounting_activity and reconcile_byte_coverage_activity.
// Both key entirely off the raw generation's sealed H3 chain reference — the
// exact result produced by hash_raw_generation_activity — because neither may
// run until the raw generation's full custody chain exists.
type RawGenerationChainSpec struct {
	RequestID             string
	Attempt               int32
	SourceVersionRef      uiw.Ref
	RawGenerationChainRef uiw.Ref
}

// RawSourceVerificationSpec is the compact input to
// verify_raw_coverage_against_source_activity: the two reconciliation
// receipts it joins, the raw generation's H1 source digest, and its H3 chain
// reference, which this Activity independently recomputes rather than trusts.
type RawSourceVerificationSpec struct {
	RequestID             string
	Attempt               int32
	SourceVersionRef      uiw.Ref
	AccountingRef         uiw.Ref
	CoverageRef           uiw.Ref
	H1Ref                 uiw.Ref
	RawGenerationChainRef uiw.Ref
}

// ReconciliationOutcome is the durable result of one reconciliation or
// verification write. Status carries the workflow-facing business outcome —
// success, failed, or not_applicable — and is never inferred from a Go error:
// a discrepancy is a real, receipted finding, not an execution failure.
type ReconciliationOutcome struct {
	Ref        uiw.Ref
	ReceiptRef uiw.Ref
	Status     uiw.Status
	Reason     string
}

func (o ReconciliationOutcome) validate(stage stagegraph.StageID) error {
	if o.ReceiptRef == "" {
		return fmt.Errorf("%s outcome lacks an activity receipt reference", stage)
	}
	switch o.Status {
	case uiw.StatusSuccess:
		if o.Ref == "" {
			return fmt.Errorf("%s success outcome lacks a result reference", stage)
		}
	case uiw.StatusFailed, uiw.StatusNotApplicable:
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
	OpenRawBundle(context.Context, uiw.Ref) (RawBundleReader, error)
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
func (a RawPipelineActivities) PersistRawGeneration(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return uiw.StageResult{}, fmt.Errorf("%s requires request and source version references", stagegraph.PersistRawGeneration)
	}
	if strings.TrimSpace(req.DeclaredFormat) == "" {
		return uiw.StageResult{}, fmt.Errorf("%s requires a declared format", stagegraph.PersistRawGeneration)
	}
	bundleRef, err := requiredRawRef(req, stagegraph.PersistRawGeneration, "raw_bundle")
	if err != nil {
		return uiw.StageResult{}, err
	}

	reader, err := a.Repository.OpenRawBundle(ctx, bundleRef)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("open raw bundle %q: %w", bundleRef, err)
	}
	defer reader.Close()

	header, err := reader.Header(ctx)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("read raw bundle header: %w", err)
	}
	if header.ContractVersion != parser.ContractVersion {
		return uiw.StageResult{}, fmt.Errorf("raw bundle contract version %q is unsupported", header.ContractVersion)
	}
	if header.SourceVersionRef != string(req.SourceVersionRef) {
		return uiw.StageResult{}, errors.New("raw bundle belongs to a different source version")
	}
	if string(header.FormatID) != req.DeclaredFormat {
		return uiw.StageResult{}, errors.New("raw bundle format does not match the declared format")
	}
	if strings.TrimSpace(header.ParserID) == "" || strings.TrimSpace(header.ParserVersion) == "" {
		return uiw.StageResult{}, errors.New("raw bundle lacks parser identity")
	}

	writer, err := a.Repository.BeginRawGeneration(ctx, RawGenerationSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), SourceVersionRef: req.SourceVersionRef,
		DeclaredFormat: req.DeclaredFormat, ParserID: header.ParserID, ParserVersion: header.ParserVersion,
		BundleRef: bundleRef,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("begin raw generation: %w", err)
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
			return uiw.StageResult{}, err
		}
		record, nextErr := reader.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return uiw.StageResult{}, fmt.Errorf("read raw bundle record %d: %w", count, nextErr)
		}
		if record.RecordOrdinal != count {
			return uiw.StageResult{}, fmt.Errorf("raw bundle record ordinal %d, want contiguous ordinal %d", record.RecordOrdinal, count)
		}
		if err := record.Validate(format); err != nil {
			return uiw.StageResult{}, fmt.Errorf("raw bundle record %d: %w", count, err)
		}
		if err := writer.Append(ctx, record); err != nil {
			return uiw.StageResult{}, fmt.Errorf("persist raw record %d: %w", count, err)
		}
		count++
		tallyRawAccounting(&tally, record)
		a.heartbeat(ctx, Progress{Stage: stagegraph.PersistRawGeneration, MembersComplete: int64(count)})
	}
	if count == 0 {
		return uiw.StageResult{}, errors.New("persist raw generation refuses to seal an empty raw bundle")
	}
	trailer, err := reader.Trailer(ctx)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("read raw bundle trailer: %w", err)
	}
	if trailer != tally {
		return uiw.StageResult{}, fmt.Errorf("raw bundle trailer accounting %+v does not match streamed counts %+v", trailer, tally)
	}
	resultRef, receiptRef, err := writer.Commit(ctx, trailer)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("commit raw generation: %w", err)
	}
	committed = true
	if resultRef == "" || receiptRef == "" {
		return uiw.StageResult{}, errors.New("persisted raw generation lacks result or activity receipt reference")
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
func (a RawPipelineActivities) ReconcileRecordAccounting(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.reconcileChain(ctx, req, stagegraph.ReconcileRecordAccounting, a.Repository.ReconcileRecordAccounting)
}

// ReconcileByteCoverage verifies only byte/span coverage of the raw
// generation against its original retained object, explaining every gap.
func (a RawPipelineActivities) ReconcileByteCoverage(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.reconcileChain(ctx, req, stagegraph.ReconcileByteCoverage, a.Repository.ReconcileByteCoverage)
}

func (a RawPipelineActivities) reconcileChain(
	ctx context.Context, req uiw.StageRequest, stage stagegraph.StageID,
	call func(context.Context, RawGenerationChainSpec) (ReconciliationOutcome, error),
) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return uiw.StageResult{}, fmt.Errorf("%s requires request and source version references", stage)
	}
	chainRef, err := requiredRawRef(req, stage, "raw_generation_chain")
	if err != nil {
		return uiw.StageResult{}, err
	}
	outcome, err := call(ctx, RawGenerationChainSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), SourceVersionRef: req.SourceVersionRef,
		RawGenerationChainRef: chainRef,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("%s: %w", stage, err)
	}
	if err := outcome.validate(stage); err != nil {
		return uiw.StageResult{}, err
	}
	return rawPipelineOutcome(stage, outcome), nil
}

// VerifyRawCoverageAgainstSource compares only the raw coverage/recomposition
// proof against H1; it does not normalize and does not trust the earlier H3
// hash computation — the repository must independently recompute it.
func (a RawPipelineActivities) VerifyRawCoverageAgainstSource(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	stage := stagegraph.VerifyRawCoverageAgainstSource
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return uiw.StageResult{}, fmt.Errorf("%s requires request and source version references", stage)
	}
	accountingRef, err := requiredRawRef(req, stage, "accounting")
	if err != nil {
		return uiw.StageResult{}, err
	}
	coverageRef, err := requiredRawRef(req, stage, "coverage")
	if err != nil {
		return uiw.StageResult{}, err
	}
	h1Ref, err := requiredRawRef(req, stage, "h1")
	if err != nil {
		return uiw.StageResult{}, err
	}
	chainRef, err := requiredRawRef(req, stage, "raw_generation_chain")
	if err != nil {
		return uiw.StageResult{}, err
	}
	outcome, err := a.Repository.VerifyRawCoverageAgainstSource(ctx, RawSourceVerificationSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), SourceVersionRef: req.SourceVersionRef,
		AccountingRef: accountingRef, CoverageRef: coverageRef, H1Ref: h1Ref, RawGenerationChainRef: chainRef,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("%s: %w", stage, err)
	}
	if err := outcome.validate(stage); err != nil {
		return uiw.StageResult{}, err
	}
	return rawPipelineOutcome(stage, outcome), nil
}

func requiredRawRef(req uiw.StageRequest, stage stagegraph.StageID, name string) (uiw.Ref, error) {
	ref := req.Refs[name]
	if strings.TrimSpace(string(ref)) == "" {
		return "", fmt.Errorf("%s requires non-empty %q reference", stage, name)
	}
	return ref, nil
}

func rawPipelineSuccess(stage stagegraph.StageID, resultRef, receiptRef uiw.Ref) uiw.StageResult {
	return uiw.StageResult{Stage: stage, Status: uiw.StatusSuccess, Ref: resultRef, ReceiptRef: receiptRef}
}

func rawPipelineOutcome(stage stagegraph.StageID, outcome ReconciliationOutcome) uiw.StageResult {
	return uiw.StageResult{
		Stage: stage, Status: outcome.Status, Ref: outcome.Ref, ReceiptRef: outcome.ReceiptRef, Reason: outcome.Reason,
	}
}

package activities

import (
	"context"
	"errors"
	"io"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

func rawEnvelope(ordinal uint64, status parser.RecordStatus) parser.RawRecordEnvelope {
	envelope := parser.RawRecordEnvelope{
		RecordOrdinal: ordinal,
		RecordStatus:  status,
		FormatID:      "sms_xml_backup",
		StoredBytes:   &parser.StoredBytes{Bytes: []byte("x")},
	}
	if status != parser.StatusParsed {
		envelope.StatusReason = "reason"
	}
	return envelope
}

type fakeBundleReader struct {
	header      parser.BundleHeader
	records     []parser.RawRecordEnvelope
	trailer     parser.BundleAccounting
	index       int
	headerErr   error
	nextErr     error
	trailerErr  error
	closeCalled bool
}

func (f *fakeBundleReader) Header(context.Context) (parser.BundleHeader, error) {
	return f.header, f.headerErr
}

func (f *fakeBundleReader) Next(context.Context) (parser.RawRecordEnvelope, error) {
	if f.nextErr != nil {
		return parser.RawRecordEnvelope{}, f.nextErr
	}
	if f.index >= len(f.records) {
		return parser.RawRecordEnvelope{}, io.EOF
	}
	record := f.records[f.index]
	f.index++
	return record, nil
}

func (f *fakeBundleReader) Trailer(context.Context) (parser.BundleAccounting, error) {
	return f.trailer, f.trailerErr
}

func (f *fakeBundleReader) Close() error {
	f.closeCalled = true
	return nil
}

type fakeRawGenerationWriter struct {
	appended  []parser.RawRecordEnvelope
	appendErr error
	commitRef uiw.Ref
	commitRcp uiw.Ref
	commitErr error
	committed bool
	aborted   bool
}

func (w *fakeRawGenerationWriter) Append(_ context.Context, record parser.RawRecordEnvelope) error {
	if w.appendErr != nil {
		return w.appendErr
	}
	w.appended = append(w.appended, record)
	return nil
}

func (w *fakeRawGenerationWriter) Commit(_ context.Context, _ parser.BundleAccounting) (uiw.Ref, uiw.Ref, error) {
	if w.commitErr != nil {
		return "", "", w.commitErr
	}
	w.committed = true
	return w.commitRef, w.commitRcp, nil
}

func (w *fakeRawGenerationWriter) Abort(context.Context) error {
	w.aborted = true
	return nil
}

type fakeRawPipelineRepository struct {
	bundle        *fakeBundleReader
	openBundleErr error
	writer        *fakeRawGenerationWriter
	beginErr      error

	accountingOutcome ReconciliationOutcome
	accountingErr     error
	coverageOutcome   ReconciliationOutcome
	coverageErr       error
	verifyOutcome     ReconciliationOutcome
	verifyErr         error

	lastGenerationSpec RawGenerationSpec
	lastChainSpec      RawGenerationChainSpec
	lastVerifySpec     RawSourceVerificationSpec
}

func (r *fakeRawPipelineRepository) OpenRawBundle(context.Context, uiw.Ref) (RawBundleReader, error) {
	if r.openBundleErr != nil {
		return nil, r.openBundleErr
	}
	return r.bundle, nil
}

func (r *fakeRawPipelineRepository) BeginRawGeneration(_ context.Context, spec RawGenerationSpec) (RawGenerationWriter, error) {
	r.lastGenerationSpec = spec
	if r.beginErr != nil {
		return nil, r.beginErr
	}
	return r.writer, nil
}

func (r *fakeRawPipelineRepository) ReconcileRecordAccounting(_ context.Context, spec RawGenerationChainSpec) (ReconciliationOutcome, error) {
	r.lastChainSpec = spec
	return r.accountingOutcome, r.accountingErr
}

func (r *fakeRawPipelineRepository) ReconcileByteCoverage(_ context.Context, spec RawGenerationChainSpec) (ReconciliationOutcome, error) {
	r.lastChainSpec = spec
	return r.coverageOutcome, r.coverageErr
}

func (r *fakeRawPipelineRepository) VerifyRawCoverageAgainstSource(_ context.Context, spec RawSourceVerificationSpec) (ReconciliationOutcome, error) {
	r.lastVerifySpec = spec
	return r.verifyOutcome, r.verifyErr
}

func baseRawStageRequest() uiw.StageRequest {
	return uiw.StageRequest{
		RequestID: "req-1", SourceVersionRef: "src-1", DeclaredFormat: "sms_xml_backup",
		Refs: map[string]uiw.Ref{"raw_bundle": "bundle-1"},
	}
}

func TestPersistRawGenerationHappyPath(t *testing.T) {
	records := []parser.RawRecordEnvelope{
		rawEnvelope(0, parser.StatusParsed),
		rawEnvelope(1, parser.StatusRejected),
		rawEnvelope(2, parser.StatusEnvelope),
	}
	repo := &fakeRawPipelineRepository{
		bundle: &fakeBundleReader{
			header: parser.BundleHeader{
				ContractVersion: parser.ContractVersion, ParserID: "p", ParserVersion: "1",
				SourceVersionRef: "src-1", FormatID: "sms_xml_backup",
			},
			records: records,
			trailer: parser.BundleAccounting{Emitted: 1, Rejected: 1},
		},
		writer: &fakeRawGenerationWriter{commitRef: "raw-gen-1", commitRcp: "receipt-1"},
	}
	activities := RawPipelineActivities{Repository: repo}
	result, err := activities.PersistRawGeneration(context.Background(), baseRawStageRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != uiw.StatusSuccess || result.Ref != "raw-gen-1" || result.ReceiptRef != "receipt-1" {
		t.Fatalf("result = %+v", result)
	}
	if len(repo.writer.appended) != 3 {
		t.Fatalf("appended %d records, want 3", len(repo.writer.appended))
	}
	if !repo.writer.committed || repo.writer.aborted {
		t.Fatalf("writer committed=%v aborted=%v", repo.writer.committed, repo.writer.aborted)
	}
	if !repo.bundle.closeCalled {
		t.Fatal("bundle reader was not closed")
	}
	if repo.lastGenerationSpec.ParserID != "p" || repo.lastGenerationSpec.ParserVersion != "1" || repo.lastGenerationSpec.BundleRef != "bundle-1" {
		t.Fatalf("generation spec = %+v", repo.lastGenerationSpec)
	}
}

func TestPersistRawGenerationRejectsMissingBundleRef(t *testing.T) {
	req := baseRawStageRequest()
	delete(req.Refs, "raw_bundle")
	activities := RawPipelineActivities{Repository: &fakeRawPipelineRepository{}}
	if _, err := activities.PersistRawGeneration(context.Background(), req); err == nil {
		t.Fatal("missing raw_bundle reference accepted")
	}
}

func TestPersistRawGenerationRejectsHeaderMismatch(t *testing.T) {
	for name, header := range map[string]parser.BundleHeader{
		"wrong contract version":  {ContractVersion: "9.9.9", SourceVersionRef: "src-1", FormatID: "sms_xml_backup", ParserID: "p", ParserVersion: "1"},
		"wrong source":            {ContractVersion: parser.ContractVersion, SourceVersionRef: "other", FormatID: "sms_xml_backup", ParserID: "p", ParserVersion: "1"},
		"wrong format":            {ContractVersion: parser.ContractVersion, SourceVersionRef: "src-1", FormatID: "other_format", ParserID: "p", ParserVersion: "1"},
		"missing parser identity": {ContractVersion: parser.ContractVersion, SourceVersionRef: "src-1", FormatID: "sms_xml_backup"},
	} {
		t.Run(name, func(t *testing.T) {
			repo := &fakeRawPipelineRepository{bundle: &fakeBundleReader{header: header}}
			activities := RawPipelineActivities{Repository: repo}
			if _, err := activities.PersistRawGeneration(context.Background(), baseRawStageRequest()); err == nil {
				t.Fatal("mismatched bundle header accepted")
			}
		})
	}
}

func TestPersistRawGenerationRejectsNonContiguousOrdinal(t *testing.T) {
	repo := &fakeRawPipelineRepository{
		bundle: &fakeBundleReader{
			header: parser.BundleHeader{
				ContractVersion: parser.ContractVersion, SourceVersionRef: "src-1", FormatID: "sms_xml_backup",
				ParserID: "p", ParserVersion: "1",
			},
			records: []parser.RawRecordEnvelope{rawEnvelope(1, parser.StatusParsed)},
		},
		writer: &fakeRawGenerationWriter{},
	}
	activities := RawPipelineActivities{Repository: repo}
	if _, err := activities.PersistRawGeneration(context.Background(), baseRawStageRequest()); err == nil {
		t.Fatal("non-contiguous ordinal accepted")
	}
	if !repo.writer.aborted {
		t.Fatal("writer was not aborted on failure")
	}
}

func TestPersistRawGenerationRejectsAccountingMismatch(t *testing.T) {
	repo := &fakeRawPipelineRepository{
		bundle: &fakeBundleReader{
			header: parser.BundleHeader{
				ContractVersion: parser.ContractVersion, SourceVersionRef: "src-1", FormatID: "sms_xml_backup",
				ParserID: "p", ParserVersion: "1",
			},
			records: []parser.RawRecordEnvelope{rawEnvelope(0, parser.StatusParsed)},
			trailer: parser.BundleAccounting{Emitted: 99},
		},
		writer: &fakeRawGenerationWriter{},
	}
	activities := RawPipelineActivities{Repository: repo}
	if _, err := activities.PersistRawGeneration(context.Background(), baseRawStageRequest()); err == nil {
		t.Fatal("accounting mismatch accepted")
	}
	if repo.writer.committed {
		t.Fatal("mismatched accounting must not commit")
	}
}

func TestPersistRawGenerationRejectsEmptyBundle(t *testing.T) {
	repo := &fakeRawPipelineRepository{
		bundle: &fakeBundleReader{
			header: parser.BundleHeader{
				ContractVersion: parser.ContractVersion, SourceVersionRef: "src-1", FormatID: "sms_xml_backup",
				ParserID: "p", ParserVersion: "1",
			},
		},
		writer: &fakeRawGenerationWriter{},
	}
	activities := RawPipelineActivities{Repository: repo}
	if _, err := activities.PersistRawGeneration(context.Background(), baseRawStageRequest()); err == nil {
		t.Fatal("empty raw bundle accepted")
	}
}

func TestPersistRawGenerationRequiresRepository(t *testing.T) {
	activities := RawPipelineActivities{}
	if _, err := activities.PersistRawGeneration(context.Background(), baseRawStageRequest()); err == nil {
		t.Fatal("missing repository accepted")
	}
}

func reconcileRequest(refName string) uiw.StageRequest {
	return uiw.StageRequest{
		RequestID: "req-1", SourceVersionRef: "src-1",
		Refs: map[string]uiw.Ref{refName: "chain-1"},
	}
}

func TestReconcileRecordAccountingSuccessAndFailure(t *testing.T) {
	for name, outcome := range map[string]ReconciliationOutcome{
		"success":        {Status: uiw.StatusSuccess, Ref: "recon-1", ReceiptRef: "receipt-1"},
		"failed":         {Status: uiw.StatusFailed, Reason: "mismatch", ReceiptRef: "receipt-1"},
		"not_applicable": {Status: uiw.StatusNotApplicable, Reason: "n/a", ReceiptRef: "receipt-1"},
	} {
		t.Run(name, func(t *testing.T) {
			repo := &fakeRawPipelineRepository{accountingOutcome: outcome}
			activities := RawPipelineActivities{Repository: repo}
			result, err := activities.ReconcileRecordAccounting(context.Background(), reconcileRequest("raw_generation_chain"))
			if err != nil {
				t.Fatal(err)
			}
			if result.Status != outcome.Status || result.Ref != outcome.Ref || result.ReceiptRef != outcome.ReceiptRef || result.Reason != outcome.Reason {
				t.Fatalf("result = %+v, want outcome %+v", result, outcome)
			}
			if repo.lastChainSpec.RawGenerationChainRef != "chain-1" {
				t.Fatalf("chain spec = %+v", repo.lastChainSpec)
			}
		})
	}
}

func TestReconcileRecordAccountingRejectsMissingChainRef(t *testing.T) {
	activities := RawPipelineActivities{Repository: &fakeRawPipelineRepository{}}
	req := uiw.StageRequest{RequestID: "req-1", SourceVersionRef: "src-1"}
	if _, err := activities.ReconcileRecordAccounting(context.Background(), req); err == nil {
		t.Fatal("missing raw_generation_chain reference accepted")
	}
}

func TestReconcileRecordAccountingRejectsMalformedOutcome(t *testing.T) {
	repo := &fakeRawPipelineRepository{accountingOutcome: ReconciliationOutcome{Status: uiw.StatusSuccess, ReceiptRef: "receipt-1"}}
	activities := RawPipelineActivities{Repository: repo}
	if _, err := activities.ReconcileRecordAccounting(context.Background(), reconcileRequest("raw_generation_chain")); err == nil {
		t.Fatal("success outcome with empty result ref accepted")
	}
}

func TestReconcileByteCoverageDelegatesToRepository(t *testing.T) {
	repo := &fakeRawPipelineRepository{coverageOutcome: ReconciliationOutcome{Status: uiw.StatusSuccess, Ref: "cov-1", ReceiptRef: "receipt-1"}}
	activities := RawPipelineActivities{Repository: repo}
	result, err := activities.ReconcileByteCoverage(context.Background(), reconcileRequest("raw_generation_chain"))
	if err != nil {
		t.Fatal(err)
	}
	if result.Stage != stagegraph.ReconcileByteCoverage || result.Ref != "cov-1" {
		t.Fatalf("result = %+v", result)
	}
}

func verifyRequest() uiw.StageRequest {
	return uiw.StageRequest{
		RequestID: "req-1", SourceVersionRef: "src-1",
		Refs: map[string]uiw.Ref{
			"accounting": "acc-1", "coverage": "cov-1", "h1": "h1-1", "raw_generation_chain": "chain-1",
		},
	}
}

func TestVerifyRawCoverageAgainstSourceHappyPath(t *testing.T) {
	repo := &fakeRawPipelineRepository{verifyOutcome: ReconciliationOutcome{Status: uiw.StatusSuccess, Ref: "verify-1", ReceiptRef: "receipt-1"}}
	activities := RawPipelineActivities{Repository: repo}
	result, err := activities.VerifyRawCoverageAgainstSource(context.Background(), verifyRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != uiw.StatusSuccess || result.Ref != "verify-1" {
		t.Fatalf("result = %+v", result)
	}
	if repo.lastVerifySpec.AccountingRef != "acc-1" || repo.lastVerifySpec.CoverageRef != "cov-1" ||
		repo.lastVerifySpec.H1Ref != "h1-1" || repo.lastVerifySpec.RawGenerationChainRef != "chain-1" {
		t.Fatalf("verify spec = %+v", repo.lastVerifySpec)
	}
}

func TestVerifyRawCoverageAgainstSourceRequiresEachReference(t *testing.T) {
	for _, missing := range []string{"accounting", "coverage", "h1", "raw_generation_chain"} {
		t.Run(missing, func(t *testing.T) {
			req := verifyRequest()
			delete(req.Refs, missing)
			activities := RawPipelineActivities{Repository: &fakeRawPipelineRepository{}}
			if _, err := activities.VerifyRawCoverageAgainstSource(context.Background(), req); err == nil {
				t.Fatalf("missing %q reference accepted", missing)
			}
		})
	}
}

func TestVerifyRawCoverageAgainstSourcePropagatesFailedOutcome(t *testing.T) {
	repo := &fakeRawPipelineRepository{verifyOutcome: ReconciliationOutcome{Status: uiw.StatusFailed, Reason: "h3 mismatch", ReceiptRef: "receipt-1"}}
	activities := RawPipelineActivities{Repository: repo}
	result, err := activities.VerifyRawCoverageAgainstSource(context.Background(), verifyRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != uiw.StatusFailed || result.Reason != "h3 mismatch" {
		t.Fatalf("result = %+v", result)
	}
}

func TestVerifyRawCoverageAgainstSourcePropagatesRepositoryError(t *testing.T) {
	repo := &fakeRawPipelineRepository{verifyErr: errors.New("boom")}
	activities := RawPipelineActivities{Repository: repo}
	if _, err := activities.VerifyRawCoverageAgainstSource(context.Background(), verifyRequest()); err == nil {
		t.Fatal("repository error swallowed")
	}
}

func TestTallyRawAccounting(t *testing.T) {
	var tally parser.BundleAccounting
	for _, record := range []parser.RawRecordEnvelope{
		rawEnvelope(0, parser.StatusParsed),
		rawEnvelope(1, parser.StatusRejected),
		rawEnvelope(2, parser.StatusMalformed),
		rawEnvelope(3, parser.StatusUnknown),
		rawEnvelope(4, parser.StatusUnparsed),
		rawEnvelope(5, parser.StatusEnvelope),
	} {
		tallyRawAccounting(&tally, record)
	}
	want := parser.BundleAccounting{Emitted: 1, Rejected: 1, Malformed: 1, Unknown: 1, Unparsed: 1}
	if tally != want {
		t.Fatalf("tally = %+v, want %+v", tally, want)
	}
}

func TestReconciliationOutcomeValidate(t *testing.T) {
	stage := stagegraph.ReconcileRecordAccounting
	if err := (ReconciliationOutcome{Status: uiw.StatusSuccess, Ref: "r", ReceiptRef: "rcp"}).validate(stage); err != nil {
		t.Fatal(err)
	}
	if err := (ReconciliationOutcome{Status: uiw.StatusSuccess, ReceiptRef: "rcp"}).validate(stage); err == nil {
		t.Fatal("success outcome without result ref accepted")
	}
	if err := (ReconciliationOutcome{Status: uiw.StatusFailed, ReceiptRef: "rcp"}).validate(stage); err == nil {
		t.Fatal("failed outcome without reason accepted")
	}
	if err := (ReconciliationOutcome{Status: uiw.StatusFailed, Reason: "x"}).validate(stage); err == nil {
		t.Fatal("outcome without receipt ref accepted")
	}
	if err := (ReconciliationOutcome{Status: "bogus", ReceiptRef: "rcp"}).validate(stage); err == nil {
		t.Fatal("unsupported status accepted")
	}
}

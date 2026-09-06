package activities

import (
	"bytes"
	"context"
	"errors"
	"io"
	"strings"
	"testing"
	"time"

	"github.com/lowcarbdev/sbv/pkg/custodyhash"

	"github.com/Cursedpotential/probata/engine/normalize"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

// fakeNormalizedPipelineStore captures the last spec passed to each method
// and returns configured refs/errors, mirroring lifecycleStore in
// source_lifecycle_test.go.
type fakeNormalizedPipelineStore struct {
	resolveInput       normalize.NormalizerInput
	resolveInputErr    error
	openWriter         normalize.BundleWriter
	openWriterErr      error
	persistExecSpec    NormalizeExecutionSpec
	persistExecRef     proffer.Ref
	persistExecReceipt proffer.Ref
	persistExecErr     error

	persistGenSpec    PersistNormalizedGenerationSpec
	persistGenRef     proffer.Ref
	persistGenReceipt proffer.Ref
	persistGenErr     error

	persistLineageSpec    PersistLineageSpec
	persistLineageRef     proffer.Ref
	persistLineageReceipt proffer.Ref
	persistLineageErr     error

	validateLineageSpec    ValidateRawLineageSpec
	validateLineageRef     proffer.Ref
	validateLineageReceipt proffer.Ref
	validateLineageErr     error

	openRecordsStream ByteMemberStream
	openRecordsErr    error

	verifySpec    VerifyNormalizedGenerationSpec
	verifyRef     proffer.Ref
	verifyReceipt proffer.Ref
	verifyErr     error

	sealSpec    SealGenerationSpec
	sealRef     proffer.Ref
	sealReceipt proffer.Ref
	sealErr     error

	publishSpec    PublishGenerationSpec
	publishRef     proffer.Ref
	publishReceipt proffer.Ref
	publishErr     error
}

func (s *fakeNormalizedPipelineStore) ResolveNormalizerInput(context.Context, proffer.StageRequest) (normalize.NormalizerInput, error) {
	return s.resolveInput, s.resolveInputErr
}
func (s *fakeNormalizedPipelineStore) OpenNormalizedBundleWriter(context.Context, proffer.StageRequest, normalize.NormalizerInput) (normalize.BundleWriter, error) {
	return s.openWriter, s.openWriterErr
}
func (s *fakeNormalizedPipelineStore) PersistNormalizeExecution(_ context.Context, spec NormalizeExecutionSpec) (proffer.Ref, proffer.Ref, error) {
	s.persistExecSpec = spec
	return s.persistExecRef, s.persistExecReceipt, s.persistExecErr
}
func (s *fakeNormalizedPipelineStore) PersistNormalizedGeneration(_ context.Context, spec PersistNormalizedGenerationSpec) (proffer.Ref, proffer.Ref, error) {
	s.persistGenSpec = spec
	return s.persistGenRef, s.persistGenReceipt, s.persistGenErr
}
func (s *fakeNormalizedPipelineStore) PersistLineage(_ context.Context, spec PersistLineageSpec) (proffer.Ref, proffer.Ref, error) {
	s.persistLineageSpec = spec
	return s.persistLineageRef, s.persistLineageReceipt, s.persistLineageErr
}
func (s *fakeNormalizedPipelineStore) ValidateRawLineage(_ context.Context, spec ValidateRawLineageSpec) (proffer.Ref, proffer.Ref, error) {
	s.validateLineageSpec = spec
	return s.validateLineageRef, s.validateLineageReceipt, s.validateLineageErr
}
func (s *fakeNormalizedPipelineStore) OpenNormalizedGenerationRecords(context.Context, proffer.Ref) (ByteMemberStream, error) {
	return s.openRecordsStream, s.openRecordsErr
}
func (s *fakeNormalizedPipelineStore) VerifyNormalizedGeneration(_ context.Context, spec VerifyNormalizedGenerationSpec) (proffer.Ref, proffer.Ref, error) {
	s.verifySpec = spec
	return s.verifyRef, s.verifyReceipt, s.verifyErr
}
func (s *fakeNormalizedPipelineStore) SealGeneration(_ context.Context, spec SealGenerationSpec) (proffer.Ref, proffer.Ref, error) {
	s.sealSpec = spec
	return s.sealRef, s.sealReceipt, s.sealErr
}
func (s *fakeNormalizedPipelineStore) PublishGeneration(_ context.Context, spec PublishGenerationSpec) (proffer.Ref, proffer.Ref, error) {
	s.publishSpec = spec
	return s.publishRef, s.publishReceipt, s.publishErr
}

var _ NormalizedPipelineStore = (*fakeNormalizedPipelineStore)(nil)

// fakeNormalizer is a minimal normalize.Adapter that emits exactly one
// message-type record derived from the first raw record it reads.
type fakeNormalizer struct {
	emit    int
	failErr error
}

func (fakeNormalizer) Capability() normalize.Capability {
	return normalize.Capability{ContractVersion: normalize.ContractVersion, NormalizerID: "fake_normalizer", NormalizerVersion: "1.0.0"}
}

func (n fakeNormalizer) Normalize(ctx context.Context, input normalize.NormalizerInput, sink normalize.BundleSink) (normalize.BundleAccounting, error) {
	if n.failErr != nil {
		return normalize.BundleAccounting{}, n.failErr
	}
	for i := 0; i < n.emit; i++ {
		record := normalize.RecordEnvelope{
			RecordOrdinal:        uint64(i),
			RecordType:           normalize.RecordTypeMessage,
			TimestampGranularity: normalize.GranularityUnknown,
			TimestampCertainty:   normalize.CertaintyUnknown,
			SourceAvailableFrom:  input.AcquiredAt,
			ProvenanceClass:      input.SourceProvenanceClass,
			Participants:         []normalize.Participant{{Role: normalize.RoleUnknown, Identifier: "unknown"}},
			Content:              []byte(`{"body":"hi"}`),
			Lineage:              []normalize.LineageEdge{{RawRecordOrdinal: uint64(i), DerivationRole: normalize.DerivationPrimarySource}},
		}
		if err := sink.Emit(ctx, record); err != nil {
			return normalize.BundleAccounting{}, err
		}
	}
	return normalize.BundleAccounting{Emitted: uint64(n.emit)}, nil
}

var _ normalize.Adapter = fakeNormalizer{}

// fakeBundleWriter records every call made to it.
type fakeBundleWriter struct {
	beganHeader normalize.BundleHeader
	emitted     []normalize.RecordEnvelope
	finalized   bool
	aborted     bool
	bundleRef   string
	finalizeErr error
}

func (w *fakeBundleWriter) Begin(_ context.Context, header normalize.BundleHeader) error {
	w.beganHeader = header
	return nil
}
func (w *fakeBundleWriter) Emit(_ context.Context, record normalize.RecordEnvelope) error {
	w.emitted = append(w.emitted, record)
	return nil
}
func (w *fakeBundleWriter) Finalize(_ context.Context, _ normalize.BundleAccounting) (normalize.BundleResult, error) {
	if w.finalizeErr != nil {
		return normalize.BundleResult{}, w.finalizeErr
	}
	w.finalized = true
	return normalize.BundleResult{BundleRef: w.bundleRef}, nil
}
func (w *fakeBundleWriter) Abort(context.Context) error {
	w.aborted = true
	return nil
}

var _ normalize.BundleWriter = (*fakeBundleWriter)(nil)

func baseNormalizerInput() normalize.NormalizerInput {
	return normalize.NormalizerInput{
		ContractVersion:       normalize.ContractVersion,
		SourceVersionRef:      "source-version:1",
		RawGenerationRef:      "raw-generation:1",
		DeclaredFormat:        "generic_chat_export",
		SourceProvenanceClass: normalize.ProvenanceFirstPartyAuthored,
		AcquiredAt:            time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		Records:               emptyRawRecordSource{},
	}
}

type emptyRawRecordSource struct{}

func (emptyRawRecordSource) Next(context.Context) (normalize.RawRecordView, error) {
	return normalize.RawRecordView{}, io.EOF
}
func (emptyRawRecordSource) Close() error { return nil }

func TestNormalizedPipelineActivitiesValidateRequiresStoreAndNormalizer(t *testing.T) {
	if err := (NormalizedPipelineActivities{Normalizer: fakeNormalizer{}}).validate(); err == nil {
		t.Fatal("nil store accepted")
	}
	if err := (NormalizedPipelineActivities{Store: &fakeNormalizedPipelineStore{}}).validate(); err == nil {
		t.Fatal("nil normalizer accepted")
	}
	if err := (NormalizedPipelineActivities{Store: &fakeNormalizedPipelineStore{}, Normalizer: fakeNormalizer{}}).validate(); err != nil {
		t.Fatal(err)
	}
}

func TestNormalizeGenerationHappyPathPersistsExecutionAndReturnsRefs(t *testing.T) {
	input := baseNormalizerInput()
	writer := &fakeBundleWriter{bundleRef: "bundle:1"}
	store := &fakeNormalizedPipelineStore{
		resolveInput:       input,
		openWriter:         writer,
		persistExecRef:     "bundle:1",
		persistExecReceipt: "receipt:normalize",
	}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{emit: 1}, Attempt: func(context.Context) int32 { return 3 }}
	result, err := a.NormalizeGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1",
		Refs: map[string]proffer.Ref{"raw_generation": "raw-generation:1", "raw_source_verification": "verify:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	want := proffer.StageResult{Stage: stagegraph.NormalizeGeneration, Status: proffer.StatusSuccess, Ref: "bundle:1", ReceiptRef: "receipt:normalize"}
	if result != want {
		t.Fatalf("result = %+v, want %+v", result, want)
	}
	if !writer.finalized {
		t.Fatal("bundle writer was not finalized")
	}
	if store.persistExecSpec.NormalizerID != "fake_normalizer" || store.persistExecSpec.BundleRef != "bundle:1" || store.persistExecSpec.Attempt != 3 {
		t.Fatalf("persist execution spec = %+v", store.persistExecSpec)
	}
}

func TestNormalizeGenerationRejectsMissingRefs(t *testing.T) {
	store := &fakeNormalizedPipelineStore{}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	tests := []struct {
		name string
		req  proffer.StageRequest
		want string
	}{
		{"no request id", proffer.StageRequest{SourceVersionRef: "s"}, "request"},
		{"no source", proffer.StageRequest{RequestID: "r"}, "request"},
		{"no raw generation", proffer.StageRequest{RequestID: "r", SourceVersionRef: "s"}, "raw_generation"},
		{"no verification", proffer.StageRequest{RequestID: "r", SourceVersionRef: "s", Refs: map[string]proffer.Ref{"raw_generation": "g"}}, "raw_source_verification"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := a.NormalizeGeneration(context.Background(), test.req)
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("error = %v, want substring %q", err, test.want)
			}
		})
	}
}

func TestNormalizeGenerationRejectsMismatchedResolvedInput(t *testing.T) {
	input := baseNormalizerInput()
	input.RawGenerationRef = "raw-generation:other"
	store := &fakeNormalizedPipelineStore{resolveInput: input, openWriter: &fakeBundleWriter{bundleRef: "b"}}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{emit: 1}}
	_, err := a.NormalizeGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1",
		Refs: map[string]proffer.Ref{"raw_generation": "raw-generation:1", "raw_source_verification": "verify:1"},
	})
	if err == nil || !strings.Contains(err.Error(), "does not match") {
		t.Fatalf("error = %v", err)
	}
}

func TestPersistNormalizedGenerationHappyPathAndMissingRef(t *testing.T) {
	store := &fakeNormalizedPipelineStore{persistGenRef: "generation:1", persistGenReceipt: "receipt:persist"}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}, Attempt: func(context.Context) int32 { return 1 }}
	result, err := a.PersistNormalizedGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"normalized_bundle": "bundle:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	want := proffer.StageResult{Stage: stagegraph.PersistNormalizedGeneration, Status: proffer.StatusSuccess, Ref: "generation:1", ReceiptRef: "receipt:persist"}
	if result != want {
		t.Fatalf("result = %+v, want %+v", result, want)
	}
	if store.persistGenSpec.BundleRef != "bundle:1" {
		t.Fatalf("persist generation spec = %+v", store.persistGenSpec)
	}
	if _, err := a.PersistNormalizedGeneration(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source-version:1"}); err == nil || !strings.Contains(err.Error(), "normalized_bundle") {
		t.Fatalf("error = %v", err)
	}
}

func TestPersistLineageHappyPathAndMissingRefs(t *testing.T) {
	store := &fakeNormalizedPipelineStore{persistLineageRef: "lineage_set:1", persistLineageReceipt: "receipt:lineage"}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	result, err := a.PersistLineage(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1",
		Refs: map[string]proffer.Ref{"normalized_generation": "generation:1", "raw_generation": "raw-generation:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Ref != "lineage_set:1" || result.Stage != stagegraph.PersistLineage {
		t.Fatalf("result = %+v", result)
	}
	if store.persistLineageSpec.NormalizedGenerationRef != "generation:1" || store.persistLineageSpec.RawGenerationRef != "raw-generation:1" {
		t.Fatalf("persist lineage spec = %+v", store.persistLineageSpec)
	}
	if _, err := a.PersistLineage(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"normalized_generation": "g"}}); err == nil || !strings.Contains(err.Error(), "raw_generation") {
		t.Fatalf("error = %v", err)
	}
}

func TestValidateRawLineageHappyPath(t *testing.T) {
	store := &fakeNormalizedPipelineStore{validateLineageRef: "reconciliation:1", validateLineageReceipt: "receipt:validate"}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	result, err := a.ValidateRawLineage(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"lineage_set": "lineage_set:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Ref != "reconciliation:1" || result.Stage != stagegraph.ValidateRawLineage {
		t.Fatalf("result = %+v", result)
	}
	if store.validateLineageSpec.LineageSetRef != "lineage_set:1" {
		t.Fatalf("validate raw lineage spec = %+v", store.validateLineageSpec)
	}
}

func TestSealGenerationHappyPathAndMissingRef(t *testing.T) {
	store := &fakeNormalizedPipelineStore{sealRef: "generation:1", sealReceipt: "receipt:seal"}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	result, err := a.SealGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"normalized_verification": "verify:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Ref != "generation:1" || result.Stage != stagegraph.SealGeneration {
		t.Fatalf("result = %+v", result)
	}
	if _, err := a.SealGeneration(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source-version:1"}); err == nil || !strings.Contains(err.Error(), "normalized_verification") {
		t.Fatalf("error = %v", err)
	}
}

func TestPublishGenerationHappyPathAndMissingRef(t *testing.T) {
	store := &fakeNormalizedPipelineStore{publishRef: "publication:1", publishReceipt: "receipt:publish"}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	result, err := a.PublishGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"sealed_generation": "generation:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Ref != "publication:1" || result.Stage != stagegraph.PublishGeneration {
		t.Fatalf("result = %+v", result)
	}
	if _, err := a.PublishGeneration(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source-version:1"}); err == nil || !strings.Contains(err.Error(), "sealed_generation") {
		t.Fatalf("error = %v", err)
	}
}

// fakeByteMemberStream replays a fixed slice of normalized-record canonical
// bytes so VerifyNormalizedGeneration's independent recomputation can be
// tested against a digest computed the same way hashing.go computes it.
type fakeByteMemberStream struct {
	members []ByteMember
	index   int
}

func (s *fakeByteMemberStream) Next(context.Context) (ByteMember, error) {
	if s.index >= len(s.members) {
		return ByteMember{}, io.EOF
	}
	member := s.members[s.index]
	s.index++
	return member, nil
}
func (s *fakeByteMemberStream) Close() error { return nil }

func TestVerifyNormalizedGenerationRecomputesDigestMatchingHashingConstruction(t *testing.T) {
	payloads := [][]byte{[]byte(`{"a":1}`), []byte(`{"b":2}`)}
	var members []ByteMember
	acc := newNormalizedAccumulator()
	for i, payload := range payloads {
		digest, err := custodyhash.HashReaderH1(bytes.NewReader(payload))
		if err != nil {
			t.Fatal(err)
		}
		members = append(members, ByteMember{
			SubjectRef: proffer.Ref("record:" + string(rune('a'+i))), Ordinal: int64(i),
			Canon: CanonNormalizedRecord, Reader: io.NopCloser(bytes.NewReader(payload)),
		})
		if err := acc.Add(DigestMember{Ordinal: int64(i), Digest: digest, Canon: CanonNormalizedRecord}); err != nil {
			t.Fatal(err)
		}
	}
	wantDigest := acc.Sum()

	store := &fakeNormalizedPipelineStore{
		openRecordsStream: &fakeByteMemberStream{members: members},
		verifyRef:         "reconciliation:1", verifyReceipt: "receipt:verify",
	}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}, Attempt: func(context.Context) int32 { return 2 }}
	result, err := a.VerifyNormalizedGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1",
		Refs: map[string]proffer.Ref{"lineage_validation": "reconciliation:0", "normalized_generation_manifest_digest": "hash-receipt:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Ref != "reconciliation:1" || result.Stage != stagegraph.VerifyNormalizedGeneration {
		t.Fatalf("result = %+v", result)
	}
	if store.verifySpec.RecomputedDigest != wantDigest {
		t.Fatalf("recomputed digest = %q, want %q", store.verifySpec.RecomputedDigest, wantDigest)
	}
	if store.verifySpec.RecomputedConstruction != CanonNormalizedGeneration {
		t.Fatalf("recomputed construction = %q, want %q", store.verifySpec.RecomputedConstruction, CanonNormalizedGeneration)
	}
	if store.verifySpec.RecomputedMemberCount != int64(len(payloads)) {
		t.Fatalf("recomputed member count = %d, want %d", store.verifySpec.RecomputedMemberCount, len(payloads))
	}
	if store.verifySpec.Attempt != 2 {
		t.Fatalf("attempt = %d, want 2", store.verifySpec.Attempt)
	}
}

func TestVerifyNormalizedGenerationRejectsZeroRecordsAndBadOrdinalsAndWrongCanon(t *testing.T) {
	a := NormalizedPipelineActivities{Store: &fakeNormalizedPipelineStore{}, Normalizer: fakeNormalizer{}}
	req := proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1",
		Refs: map[string]proffer.Ref{"lineage_validation": "reconciliation:0", "normalized_generation_manifest_digest": "hash-receipt:1"},
	}

	t.Run("zero records", func(t *testing.T) {
		a.Store = &fakeNormalizedPipelineStore{openRecordsStream: &fakeByteMemberStream{}}
		if _, err := a.VerifyNormalizedGeneration(context.Background(), req); err == nil || !strings.Contains(err.Error(), "zero records") {
			t.Fatalf("error = %v", err)
		}
	})
	t.Run("non-contiguous ordinal", func(t *testing.T) {
		a.Store = &fakeNormalizedPipelineStore{openRecordsStream: &fakeByteMemberStream{members: []ByteMember{
			{Ordinal: 1, Canon: CanonNormalizedRecord, Reader: io.NopCloser(bytes.NewReader(nil))},
		}}}
		if _, err := a.VerifyNormalizedGeneration(context.Background(), req); err == nil || !strings.Contains(err.Error(), "ordinal") {
			t.Fatalf("error = %v", err)
		}
	})
	t.Run("wrong canon", func(t *testing.T) {
		a.Store = &fakeNormalizedPipelineStore{openRecordsStream: &fakeByteMemberStream{members: []ByteMember{
			{Ordinal: 0, Canon: "wrong-canon", Reader: io.NopCloser(bytes.NewReader(nil))},
		}}}
		if _, err := a.VerifyNormalizedGeneration(context.Background(), req); err == nil || !strings.Contains(err.Error(), "canon") {
			t.Fatalf("error = %v", err)
		}
	})
}

func TestVerifyNormalizedGenerationRejectsMissingRefs(t *testing.T) {
	a := NormalizedPipelineActivities{Store: &fakeNormalizedPipelineStore{}, Normalizer: fakeNormalizer{}}
	if _, err := a.VerifyNormalizedGeneration(context.Background(), proffer.StageRequest{RequestID: "r", SourceVersionRef: "s"}); err == nil || !strings.Contains(err.Error(), "lineage_validation") {
		t.Fatalf("error = %v", err)
	}
	if _, err := a.VerifyNormalizedGeneration(context.Background(), proffer.StageRequest{RequestID: "r", SourceVersionRef: "s", Refs: map[string]proffer.Ref{"lineage_validation": "x"}}); err == nil || !strings.Contains(err.Error(), "normalized_generation_manifest_digest") {
		t.Fatalf("error = %v", err)
	}
}

func TestNormalizedPipelineActivitiesPropagateStoreErrors(t *testing.T) {
	sentinel := errors.New("store failure")
	store := &fakeNormalizedPipelineStore{persistGenErr: sentinel}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	if _, err := a.PersistNormalizedGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"normalized_bundle": "b"},
	}); err == nil || !errors.Is(err, sentinel) {
		t.Fatalf("error = %v, want wrapped %v", err, sentinel)
	}
}

func TestNormalizedPipelineActivitiesRejectEmptyResultOrReceiptRefs(t *testing.T) {
	store := &fakeNormalizedPipelineStore{sealRef: "", sealReceipt: "receipt:seal"}
	a := NormalizedPipelineActivities{Store: store, Normalizer: fakeNormalizer{}}
	if _, err := a.SealGeneration(context.Background(), proffer.StageRequest{
		RequestID: "workflow:1", SourceVersionRef: "source-version:1", Refs: map[string]proffer.Ref{"normalized_verification": "v"},
	}); err == nil || !strings.Contains(err.Error(), "lacks result or activity receipt") {
		t.Fatalf("error = %v", err)
	}
}

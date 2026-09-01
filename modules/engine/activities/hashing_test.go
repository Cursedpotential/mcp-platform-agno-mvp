package activities

import (
	"bytes"
	"context"
	"errors"
	"io"
	"testing"

	"github.com/lowcarbdev/sbv/pkg/custodyhash"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

type byteFixture struct {
	ref     uiw.Ref
	ordinal int64
	canon   string
	data    []byte
}

type fakeByteStream struct {
	members []byteFixture
	index   int
}

func (s *fakeByteStream) Next(ctx context.Context) (ByteMember, error) {
	if err := ctx.Err(); err != nil {
		return ByteMember{}, err
	}
	if s.index == len(s.members) {
		return ByteMember{}, io.EOF
	}
	member := s.members[s.index]
	s.index++
	return ByteMember{
		SubjectRef: member.ref,
		Ordinal:    member.ordinal,
		Canon:      member.canon,
		Reader:     io.NopCloser(bytes.NewReader(member.data)),
	}, nil
}

func (*fakeByteStream) Close() error { return nil }

type fakeDigestStream struct {
	members []DigestMember
	index   int
}

func (s *fakeDigestStream) Next(ctx context.Context) (DigestMember, error) {
	if err := ctx.Err(); err != nil {
		return DigestMember{}, err
	}
	if s.index == len(s.members) {
		return DigestMember{}, io.EOF
	}
	member := s.members[s.index]
	s.index++
	return member, nil
}

func (*fakeDigestStream) Close() error { return nil }

type fakeWriter struct {
	spec      BatchSpec
	members   []HashMember
	summary   HashSummary
	committed bool
	aborted   bool
}

func (w *fakeWriter) Append(ctx context.Context, member HashMember) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	w.members = append(w.members, member)
	return nil
}

func (w *fakeWriter) Commit(ctx context.Context, summary HashSummary) (uiw.Ref, uiw.Ref, error) {
	if err := ctx.Err(); err != nil {
		return "", "", err
	}
	w.summary = summary
	w.committed = true
	return "hash-result", "activity-receipt", nil
}

func (w *fakeWriter) Abort(context.Context) error {
	w.aborted = true
	return nil
}

type fakeRepository struct {
	originals  map[uiw.Ref][]byte
	raw        map[uiw.Ref][]byteFixture
	normalized map[uiw.Ref][]byteFixture
	manifests  map[uiw.Ref][]DigestMember
	lastWriter *fakeWriter
}

func (r *fakeRepository) OpenOriginal(_ context.Context, ref uiw.Ref) (io.ReadCloser, error) {
	data, ok := r.originals[ref]
	if !ok {
		return nil, errors.New("missing original")
	}
	return io.NopCloser(bytes.NewReader(data)), nil
}

func (r *fakeRepository) OpenRawRecords(_ context.Context, ref uiw.Ref) (ByteMemberStream, error) {
	return &fakeByteStream{members: r.raw[ref]}, nil
}

func (r *fakeRepository) OpenNormalizedRecords(_ context.Context, ref uiw.Ref) (ByteMemberStream, error) {
	return &fakeByteStream{members: r.normalized[ref]}, nil
}

func (r *fakeRepository) OpenHashMembers(_ context.Context, ref uiw.Ref) (DigestMemberStream, error) {
	return &fakeDigestStream{members: r.manifests[ref]}, nil
}

func (r *fakeRepository) BeginHashBatch(_ context.Context, spec BatchSpec) (HashBatchWriter, error) {
	r.lastWriter = &fakeWriter{spec: spec}
	return r.lastWriter, nil
}

func testRequest(refName string, ref uiw.Ref) uiw.StageRequest {
	return uiw.StageRequest{
		RequestID: "request-1", SourceVersionRef: "source-version-1",
		Refs: map[string]uiw.Ref{refName: ref},
	}
}

func generationRequest(manifestName string, manifestRef, generationRef uiw.Ref) uiw.StageRequest {
	generationName := "raw_generation"
	if manifestName == "normalized_record_digests" {
		generationName = "normalized_generation"
	}
	return uiw.StageRequest{
		RequestID: "request-1", SourceVersionRef: "source-version-1",
		Refs: map[string]uiw.Ref{manifestName: manifestRef, generationName: generationRef},
	}
}

func TestFingerprintSourceComputesCanonicalContextSourceFingerprint(t *testing.T) {
	repo := &fakeRepository{originals: map[uiw.Ref][]byte{"original-1": []byte("exact source bytes\n")}}
	result, err := (HashActivities{Repository: repo, Attempt: func(context.Context) int32 { return 3 }}).FingerprintSource(context.Background(), testRequest("original", "original-1"))
	if err != nil {
		t.Fatal(err)
	}
	if result.Stage != stagegraph.FingerprintSource || result.Status != uiw.StatusSuccess {
		t.Fatalf("unexpected result: %#v", result)
	}
	want := custodyhash.HashBytes([]byte("exact source bytes\n"))
	if repo.lastWriter.summary.Digest != want || repo.lastWriter.summary.Canon != CanonContextSourceFingerprint || repo.lastWriter.summary.Construction != CanonContextSourceFingerprint {
		t.Fatalf("context source fingerprint summary = %#v, want digest %s canon %s", repo.lastWriter.summary, want, CanonContextSourceFingerprint)
	}
	if repo.lastWriter.spec.Attempt != 3 {
		t.Fatalf("batch attempt = %d, want 3", repo.lastWriter.spec.Attempt)
	}
}

func TestLegacyFingerprintRetryPreservesActivityExecutionIdentity(t *testing.T) {
	repo := &fakeRepository{originals: map[uiw.Ref][]byte{"original-1": []byte("exact source bytes\n")}}
	result, err := (HashActivities{Repository: repo}).LegacyHashSource(context.Background(), testRequest("original", "original-1"))
	if err != nil {
		t.Fatal(err)
	}
	legacy := stagegraph.StageID("hash_source_activity")
	if result.Stage != legacy || repo.lastWriter.spec.Stage != legacy {
		t.Fatalf("legacy stage identity changed: result=%q execution=%q", result.Stage, repo.lastWriter.spec.Stage)
	}
	if repo.lastWriter.spec.Kind != HashKindContextSourceFingerprint || repo.lastWriter.summary.Canon != CanonContextSourceFingerprint {
		t.Fatalf("legacy replay did not use corrected fingerprint semantics: %#v %#v", repo.lastWriter.spec, repo.lastWriter.summary)
	}
}

func TestFingerprintRawRecordsUsesExactBytesAndContextRawRecordNames(t *testing.T) {
	repo := &fakeRepository{raw: map[uiw.Ref][]byteFixture{
		"raw-generation": {
			{ref: "raw-1", ordinal: 0, canon: CanonContextRawRecordFingerprint, data: []byte(`<sms body="a" />`)},
			{ref: "raw-2", ordinal: 1, canon: CanonContextRawSpanFingerprint, data: []byte("same logical value, different bytes\n")},
		},
	}}
	result, err := (HashActivities{Repository: repo}).FingerprintRawRecords(context.Background(), testRequest("raw_generation", "raw-generation"))
	if err != nil {
		t.Fatal(err)
	}
	if result.Stage != stagegraph.FingerprintRawRecords || len(repo.lastWriter.members) != 2 {
		t.Fatalf("unexpected result or member count: %#v %#v", result, repo.lastWriter.members)
	}
	if got, want := repo.lastWriter.members[0].Digest, custodyhash.HashRecordH2([]byte(`<sms body="a" />`)); got != want {
		t.Fatalf("first context raw-record fingerprint = %s, want %s", got, want)
	}
	if repo.lastWriter.members[0].Canon != CanonContextRawRecordFingerprint || repo.lastWriter.members[1].Canon != CanonContextRawSpanFingerprint {
		t.Fatalf("raw canons drifted: %#v", repo.lastWriter.members)
	}
}

func TestFingerprintRawGenerationMatchesAuthoritativeChainAndDetectsOrdering(t *testing.T) {
	h2a := custodyhash.HashRecordH2([]byte("a"))
	h2b := custodyhash.HashRecordH2([]byte("b"))
	members := []DigestMember{
		{SubjectRef: "raw-1", Ordinal: 0, Digest: h2a, Canon: CanonContextRawRecordFingerprint},
		{SubjectRef: "raw-2", Ordinal: 1, Digest: h2b, Canon: CanonContextRawRecordFingerprint},
	}
	repo := &fakeRepository{manifests: map[uiw.Ref][]DigestMember{"raw-fingerprint-manifest": members}}
	_, err := (HashActivities{Repository: repo}).FingerprintRawGeneration(context.Background(), generationRequest("raw_fingerprint_manifest", "raw-fingerprint-manifest", "raw-generation"))
	if err != nil {
		t.Fatal(err)
	}
	if got, want := repo.lastWriter.summary.Digest, custodyhash.ChainH3([]string{h2a, h2b}, ""); got != want {
		t.Fatalf("context raw-generation fingerprint chain = %s, want %s", got, want)
	}
	if repo.lastWriter.summary.Canon != CanonContextRawGenerationFingerprint || repo.lastWriter.summary.Construction != CanonContextRawGenerationFingerprint {
		t.Fatalf("context raw-generation fingerprint canon = %q", repo.lastWriter.summary.Canon)
	}
	if repo.lastWriter.spec.SubjectRef != "raw-generation" {
		t.Fatalf("context raw-generation fingerprint subject = %q, want raw generation identity", repo.lastWriter.spec.SubjectRef)
	}

	repo.manifests["raw-fingerprint-manifest"] = []DigestMember{
		{SubjectRef: "raw-2", Ordinal: 0, Digest: h2b, Canon: CanonContextRawRecordFingerprint},
		{SubjectRef: "raw-1", Ordinal: 1, Digest: h2a, Canon: CanonContextRawRecordFingerprint},
	}
	_, err = (HashActivities{Repository: repo}).FingerprintRawGeneration(context.Background(), generationRequest("raw_fingerprint_manifest", "raw-fingerprint-manifest", "raw-generation"))
	if err != nil {
		t.Fatal(err)
	}
	if repo.lastWriter.summary.Digest == custodyhash.ChainH3([]string{h2a, h2b}, "") {
		t.Fatal("reordering context raw-record fingerprint members did not change the fingerprint chain")
	}
}

func TestNormalizedDigestsRemainDistinctFromCustodyH2H3(t *testing.T) {
	repo := &fakeRepository{
		normalized: map[uiw.Ref][]byteFixture{"normalized-generation": {
			{ref: "normalized-1", ordinal: 0, data: []byte(`{"body":"hello"}`)},
			{ref: "normalized-2", ordinal: 1, data: []byte(`{"body":"world"}`)},
		}},
		manifests: make(map[uiw.Ref][]DigestMember),
	}
	_, err := (HashActivities{Repository: repo}).HashNormalizedRecords(context.Background(), testRequest("normalized_generation", "normalized-generation"))
	if err != nil {
		t.Fatal(err)
	}
	if repo.lastWriter.spec.Kind != HashKindNormalizedRecordDigest {
		t.Fatalf("normalized members mislabeled: %q", repo.lastWriter.spec.Kind)
	}
	for _, member := range repo.lastWriter.members {
		if member.Canon != CanonNormalizedRecord || member.Canon == custodyhash.CanonH2 || member.Canon == custodyhash.CanonH2Record {
			t.Fatalf("normalized member used custody H2 canon: %#v", member)
		}
	}

	repo.manifests["normalized-digests"] = []DigestMember{
		{SubjectRef: "normalized-1", Ordinal: 0, Digest: repo.lastWriter.members[0].Digest, Canon: CanonNormalizedRecord},
		{SubjectRef: "normalized-2", Ordinal: 1, Digest: repo.lastWriter.members[1].Digest, Canon: CanonNormalizedRecord},
	}
	_, err = (HashActivities{Repository: repo}).HashNormalizedGeneration(context.Background(), generationRequest("normalized_record_digests", "normalized-digests", "normalized-generation"))
	if err != nil {
		t.Fatal(err)
	}
	firstDigest := repo.lastWriter.summary.Digest
	if repo.lastWriter.spec.Kind != HashKindNormalizedGenerationDigest || repo.lastWriter.summary.Canon != CanonNormalizedGeneration {
		t.Fatalf("normalized generation mislabeled: spec=%#v summary=%#v", repo.lastWriter.spec, repo.lastWriter.summary)
	}
	if repo.lastWriter.summary.Canon == custodyhash.CanonH3 {
		t.Fatal("normalized generation was mislabeled as raw H3")
	}
	if repo.lastWriter.spec.SubjectRef != "normalized-generation" {
		t.Fatalf("normalized manifest subject = %q, want normalized generation identity", repo.lastWriter.spec.SubjectRef)
	}

	repo.manifests["normalized-digests"] = []DigestMember{
		{SubjectRef: "normalized-2", Ordinal: 0, Digest: repo.manifests["normalized-digests"][1].Digest, Canon: CanonNormalizedRecord},
		{SubjectRef: "normalized-1", Ordinal: 1, Digest: repo.manifests["normalized-digests"][0].Digest, Canon: CanonNormalizedRecord},
	}
	_, err = (HashActivities{Repository: repo}).HashNormalizedGeneration(context.Background(), generationRequest("normalized_record_digests", "normalized-digests", "normalized-generation"))
	if err != nil {
		t.Fatal(err)
	}
	if repo.lastWriter.summary.Digest == firstDigest {
		t.Fatal("reordering normalized members did not change the manifest digest")
	}
}

func TestHashActivitiesFailClosedOnEmptyAndCancellation(t *testing.T) {
	repo := &fakeRepository{raw: map[uiw.Ref][]byteFixture{"empty": nil}}
	_, err := (HashActivities{Repository: repo}).FingerprintRawRecords(context.Background(), testRequest("raw_generation", "empty"))
	if err == nil || !repo.lastWriter.aborted || repo.lastWriter.committed {
		t.Fatalf("empty generation did not fail closed: err=%v writer=%#v", err, repo.lastWriter)
	}

	repo.manifests = map[uiw.Ref][]DigestMember{"empty-fingerprint": nil}
	_, err = (HashActivities{Repository: repo}).FingerprintRawGeneration(
		context.Background(), generationRequest("raw_fingerprint_manifest", "empty-fingerprint", "raw-generation"),
	)
	if err == nil || !repo.lastWriter.aborted || repo.lastWriter.committed {
		t.Fatalf("empty context raw-generation fingerprint chain did not fail closed: err=%v writer=%#v", err, repo.lastWriter)
	}

	repo.originals = map[uiw.Ref][]byte{"original-1": []byte("bytes")}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err = (HashActivities{Repository: repo}).FingerprintSource(ctx, testRequest("original", "original-1"))
	if !errors.Is(err, context.Canceled) || !repo.lastWriter.aborted || repo.lastWriter.committed {
		t.Fatalf("cancellation did not abort: err=%v writer=%#v", err, repo.lastWriter)
	}
}

func TestHashActivitiesRejectOrdinalAndCanonDrift(t *testing.T) {
	repo := &fakeRepository{raw: map[uiw.Ref][]byteFixture{"raw-generation": {
		{ref: "raw-1", ordinal: 1, canon: CanonNormalizedRecord, data: []byte("x")},
	}}}
	_, err := (HashActivities{Repository: repo}).FingerprintRawRecords(context.Background(), testRequest("raw_generation", "raw-generation"))
	if err == nil || !repo.lastWriter.aborted {
		t.Fatalf("ordinal/canon drift did not fail closed: err=%v writer=%#v", err, repo.lastWriter)
	}
}

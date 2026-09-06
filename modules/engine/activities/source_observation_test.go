package activities

import (
	"context"
	"encoding/json"
	"io"
	"reflect"
	"testing"
	"time"

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

func observationRequest() proffer.StageRequest {
	return proffer.StageRequest{
		RequestID:        "request-1",
		SourceVersionRef: "source-version-1",
		DeclaredFormat:   "zip",
		Refs:             map[string]proffer.Ref{"original": "object-1"},
	}
}

type fakeMetadataExtractor struct {
	observation MetadataObservation
	err         error
}

func (f fakeMetadataExtractor) ExtractSourceMetadata(context.Context, SourceObservationInput) (MetadataObservation, error) {
	return f.observation, f.err
}

type fakeInventoryEnumerator struct {
	members []InventoryMember
	err     error
}

func (f fakeInventoryEnumerator) EnumerateMembers(context.Context, SourceObservationInput) (MemberStream, error) {
	if f.err != nil {
		return nil, f.err
	}
	return &fakeMemberStream{members: f.members}, nil
}

type fakeMemberStream struct {
	members []InventoryMember
	index   int
}

func (f *fakeMemberStream) Next(context.Context) (InventoryMember, error) {
	if f.index == len(f.members) {
		return InventoryMember{}, io.EOF
	}
	member := f.members[f.index]
	f.index++
	return member, nil
}

func (*fakeMemberStream) Close() error { return nil }

type fakeObservationRepository struct {
	metadata            MetadataPersistenceSpec
	metadataResult      MetadataPersistenceResult
	metadataErr         error
	beginSpec           InventorySpec
	writer              *fakeInventoryWriter
	notApplicableSpec   InventorySpec
	notApplicableReason string
	notApplicableRef    proffer.Ref
}

func (f *fakeObservationRepository) PersistSourceMetadata(_ context.Context, spec MetadataPersistenceSpec) (MetadataPersistenceResult, error) {
	f.metadata = spec
	return f.metadataResult, f.metadataErr
}

func (f *fakeObservationRepository) BeginInventory(_ context.Context, spec InventorySpec) (InventoryWriter, error) {
	f.beginSpec = spec
	if f.writer == nil {
		f.writer = &fakeInventoryWriter{}
	}
	return f.writer, nil
}

func (f *fakeObservationRepository) RecordInventoryNotApplicable(_ context.Context, spec InventorySpec, reason string) (proffer.Ref, error) {
	f.notApplicableSpec = spec
	f.notApplicableReason = reason
	return f.notApplicableRef, nil
}

type fakeInventoryWriter struct {
	members   []InventoryMember
	committed *InventorySummary
	aborted   bool
}

func (f *fakeInventoryWriter) Append(_ context.Context, member InventoryMember) error {
	f.members = append(f.members, member)
	return nil
}

func (f *fakeInventoryWriter) Commit(_ context.Context, summary InventorySummary) (proffer.Ref, proffer.Ref, error) {
	f.committed = &summary
	return "inventory-result-1", "inventory-receipt-1", nil
}

func (f *fakeInventoryWriter) Abort(context.Context) error {
	f.aborted = true
	return nil
}

func TestCaptureFilesystemMetadataPersistsSourceLevelRows(t *testing.T) {
	generated := time.Date(2026, 8, 26, 22, 0, 0, 0, time.UTC)
	repository := &fakeObservationRepository{metadataResult: MetadataPersistenceResult{ResultRef: "metadata-result-1", ReceiptRef: "metadata-receipt-1"}}
	activities := SourceObservationActivities{
		Extractor: fakeMetadataExtractor{observation: MetadataObservation{
			ProvenanceClass: "acquired_third_party",
			Rows:            []MetadataRow{{MetadataClass: metadataFilesystem, Metadata: json.RawMessage(`{"path":"/retained/source"}`), ExtractorID: "os-stat", ExtractorVersion: "1.0", GeneratedAt: generated}},
		}},
		Repository: repository,
	}
	result, err := activities.CaptureFilesystemMetadata(context.Background(), observationRequest())
	if err != nil {
		t.Fatal(err)
	}
	if want := (proffer.StageResult{Stage: stagegraph.CaptureFilesystemMetadata, Status: proffer.StatusSuccess, Ref: "metadata-result-1", ReceiptRef: "metadata-receipt-1"}); !reflect.DeepEqual(result, want) {
		t.Fatalf("result = %#v, want %#v", result, want)
	}
	if repository.metadata.Stage != stagegraph.CaptureFilesystemMetadata || repository.metadata.IdempotencyKey == "" || repository.metadata.Attempt != 1 {
		t.Fatalf("metadata persistence coordinate = %#v", repository.metadata)
	}
	if repository.metadata.Rows[0].MetadataClass != metadataFilesystem {
		t.Fatalf("metadata class = %q", repository.metadata.Rows[0].MetadataClass)
	}
}

func TestCaptureFilesystemMetadataRejectsNonFilesystemRows(t *testing.T) {
	generated := time.Date(2026, 8, 26, 22, 0, 0, 0, time.UTC)
	activities := SourceObservationActivities{
		Extractor: fakeMetadataExtractor{observation: MetadataObservation{
			ProvenanceClass: "unknown",
			Rows:            []MetadataRow{{MetadataClass: metadataEmbedded, Metadata: json.RawMessage(`{"camera":"x"}`), ExtractorID: "exiftool", GeneratedAt: generated}},
		}},
		Repository: &fakeObservationRepository{metadataResult: MetadataPersistenceResult{ResultRef: "r", ReceiptRef: "a"}},
	}
	if _, err := activities.CaptureFilesystemMetadata(context.Background(), observationRequest()); err == nil {
		t.Fatal("expected non-filesystem metadata to fail closed")
	}
}

func TestExtractEmbeddedMetadataRejectsFilesystemRows(t *testing.T) {
	generated := time.Date(2026, 8, 26, 22, 0, 0, 0, time.UTC)
	activities := SourceObservationActivities{
		Extractor: fakeMetadataExtractor{observation: MetadataObservation{
			ProvenanceClass: "unknown",
			Rows: []MetadataRow{{
				MetadataClass: metadataFilesystem,
				Metadata:      json.RawMessage(`{"modified_at":"2026-08-26T22:00:00Z"}`),
				ExtractorID:   "os-stat",
				GeneratedAt:   generated,
			}},
		}},
		Repository: &fakeObservationRepository{metadataResult: MetadataPersistenceResult{ResultRef: "r", ReceiptRef: "a"}},
	}
	if _, err := activities.ExtractEmbeddedMetadata(context.Background(), observationRequest()); err == nil {
		t.Fatal("expected filesystem metadata in embedded stage to fail closed")
	}
}

func TestExtractEmbeddedMetadataPersistsNativeToolMetadata(t *testing.T) {
	generated := time.Date(2026, 8, 26, 22, 0, 0, 0, time.UTC)
	repository := &fakeObservationRepository{metadataResult: MetadataPersistenceResult{ResultRef: "embedded-result", ReceiptRef: "embedded-receipt"}}
	activities := SourceObservationActivities{
		Extractor: fakeMetadataExtractor{observation: MetadataObservation{
			ProvenanceClass: "acquired_third_party",
			Rows: []MetadataRow{{
				MetadataClass: metadataMediaTool,
				Metadata:      json.RawMessage(`{"exif":{"DateTimeOriginal":"2024:01:02 03:04:05"}}`),
				ExtractorID:   "exiftool",
				GeneratedAt:   generated,
			}},
		}},
		Repository: repository,
	}
	result, err := activities.ExtractEmbeddedMetadata(context.Background(), observationRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Stage != stagegraph.ExtractEmbeddedMetadata || result.Ref != "embedded-result" || result.ReceiptRef != "embedded-receipt" {
		t.Fatalf("unexpected result: %#v", result)
	}
	if repository.metadata.Stage != stagegraph.ExtractEmbeddedMetadata || repository.metadata.Rows[0].MetadataClass != metadataMediaTool {
		t.Fatalf("embedded persistence spec = %#v", repository.metadata)
	}
}

func TestCaptureFilesystemMetadataNotApplicableRequiresReceipt(t *testing.T) {
	repository := &fakeObservationRepository{metadataResult: MetadataPersistenceResult{ReceiptRef: "metadata-na-receipt"}}
	activities := SourceObservationActivities{Extractor: fakeMetadataExtractor{observation: MetadataObservation{ProvenanceClass: "unknown"}}, Repository: repository}
	result, err := activities.CaptureFilesystemMetadata(context.Background(), observationRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != proffer.StatusNotApplicable || result.ReceiptRef != "metadata-na-receipt" || result.Reason == "" || result.Ref != "" {
		t.Fatalf("unexpected not-applicable result: %#v", result)
	}
	if repository.metadata.NotApplicableReason == "" {
		t.Fatal("not-applicable reason was not persisted")
	}
}

func TestInventoryContainerStreamsAndCommitsStructuralAccounting(t *testing.T) {
	offset := int64(12)
	repository := &fakeObservationRepository{}
	activities := SourceObservationActivities{
		Enumerator: fakeInventoryEnumerator{members: []InventoryMember{
			{Ordinal: 0, MemberRef: "member-0", ByteLength: 10},
			{Ordinal: 1, MemberRef: "member-1", ParentRef: "member-0", ByteOffset: &offset, ByteLength: 5},
		}},
		Repository: repository,
	}
	result, err := activities.InventoryContainer(context.Background(), observationRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != proffer.StatusSuccess || result.Ref != "inventory-result-1" || result.ReceiptRef != "inventory-receipt-1" {
		t.Fatalf("unexpected result: %#v", result)
	}
	if repository.writer == nil || repository.writer.committed == nil {
		t.Fatal("inventory was not committed")
	}
	if got, want := *repository.writer.committed, (InventorySummary{MemberCount: 2, TotalBytes: 15, RangeCount: 1}); !reflect.DeepEqual(got, want) {
		t.Fatalf("summary = %#v, want %#v", got, want)
	}
}

func TestInventoryContainerRejectsGapAndAborts(t *testing.T) {
	repository := &fakeObservationRepository{}
	activities := SourceObservationActivities{
		Enumerator: fakeInventoryEnumerator{members: []InventoryMember{{Ordinal: 1, MemberRef: "member-1", ByteLength: 1}}},
		Repository: repository,
	}
	if _, err := activities.InventoryContainer(context.Background(), observationRequest()); err == nil {
		t.Fatal("expected gapped inventory to fail closed")
	}
	if repository.writer == nil || !repository.writer.aborted {
		t.Fatal("failed inventory did not abort its durable writer")
	}
}

func TestInventoryContainerNotApplicableRequiresReceipt(t *testing.T) {
	repository := &fakeObservationRepository{notApplicableRef: "inventory-na-receipt"}
	activities := SourceObservationActivities{
		Enumerator: fakeInventoryEnumerator{err: ErrNotApplicable},
		Repository: repository,
	}
	result, err := activities.InventoryContainer(context.Background(), observationRequest())
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != proffer.StatusNotApplicable || result.ReceiptRef != "inventory-na-receipt" || result.Reason == "" {
		t.Fatalf("unexpected result: %#v", result)
	}
}

func TestInventoryContainerRequiresNotApplicableReceipt(t *testing.T) {
	activities := SourceObservationActivities{
		Enumerator: fakeInventoryEnumerator{err: ErrNotApplicable},
		Repository: &fakeObservationRepository{},
	}
	if _, err := activities.InventoryContainer(context.Background(), observationRequest()); err == nil {
		t.Fatal("expected missing not-applicable receipt to fail closed")
	}
}

func TestObservationInputRejectsMissingOriginal(t *testing.T) {
	activities := SourceObservationActivities{
		Enumerator: fakeInventoryEnumerator{},
		Repository: &fakeObservationRepository{},
	}
	request := observationRequest()
	request.Refs = nil
	if _, err := activities.InventoryContainer(context.Background(), request); err == nil {
		t.Fatal("expected missing original reference to fail")
	}
}

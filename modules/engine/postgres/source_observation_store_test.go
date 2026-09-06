package postgres

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/Cursedpotential/probata/engine/activities"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

func TestNewSourceObservationRepositoryRequiresDatabaseAndManifestWriter(t *testing.T) {
	writerFactory := func(context.Context, activities.InventorySpec) (InventoryManifestWriter, error) { return nil, nil }
	if _, err := NewSourceObservationRepository(nil, writerFactory); err == nil {
		t.Fatal("nil database accepted")
	}
	if _, err := NewSourceObservationRepository(fakeObservationDB{}, nil); err == nil {
		t.Fatal("nil manifest writer factory accepted")
	}
}

func TestValidateMetadataPersistenceSpecPinsActivityAndNativeClasses(t *testing.T) {
	base := activities.MetadataPersistenceSpec{
		RequestID: "workflow-1", SourceVersionRef: proffer.Ref(uuid.NewString()),
		Stage: stagegraph.CaptureFilesystemMetadata, IdempotencyKey: "key-1",
		Attempt: 1, ProvenanceClass: "acquired_third_party",
		Rows: []activities.MetadataRow{{
			MetadataClass: activities.MetadataClassFilesystem,
			Metadata:      json.RawMessage(`{"mtime":"2026-08-26T22:00:00Z"}`),
			ExtractorID:   "os-stat", GeneratedAt: time.Now().UTC(),
		}},
	}
	if err := validateMetadataPersistenceSpec(base); err != nil {
		t.Fatal(err)
	}
	wrongClass := base
	wrongClass.Rows = []activities.MetadataRow{{
		MetadataClass: activities.MetadataClassContainer,
		Metadata:      json.RawMessage(`{"member_count":1}`), ExtractorID: "inventory", GeneratedAt: time.Now().UTC(),
	}}
	if err := validateMetadataPersistenceSpec(wrongClass); err == nil {
		t.Fatal("container row accepted by filesystem Activity")
	}
	wrongStage := base
	wrongStage.Stage = stagegraph.InventoryContainer
	if err := validateMetadataPersistenceSpec(wrongStage); err == nil {
		t.Fatal("inventory Activity accepted as metadata persistence stage")
	}
}

func TestValidateInventorySpecRequiresExactContainerActivity(t *testing.T) {
	spec := activities.InventorySpec{
		RequestID: "workflow-1", SourceVersionRef: proffer.Ref(uuid.NewString()),
		Stage: stagegraph.InventoryContainer, IdempotencyKey: "key-1", Attempt: 1,
	}
	if err := validateInventorySpec(spec); err != nil {
		t.Fatal(err)
	}
	spec.Stage = stagegraph.ExtractEmbeddedMetadata
	if err := validateInventorySpec(spec); err == nil {
		t.Fatal("non-inventory Activity accepted")
	}
}

func TestCompletedInventoryWriterOnlyReplaysExactCompactRefs(t *testing.T) {
	w := &completedInventoryWriter{resultRef: "manifest:1", receiptRef: "receipt:1"}
	if err := w.Append(context.Background(), activities.InventoryMember{Ordinal: 0, MemberRef: "member:1"}); err == nil {
		t.Fatal("completed writer accepted an append")
	}
	result, receipt, err := w.Commit(context.Background(), activities.InventorySummary{})
	if err != nil || result != "manifest:1" || receipt != "receipt:1" {
		t.Fatalf("replay = %q/%q/%v", result, receipt, err)
	}
}

func TestMetadataManifestRefIsStableAndStageScoped(t *testing.T) {
	id := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	a := metadataManifestRef(id, stagegraph.CaptureFilesystemMetadata)
	b := metadataManifestRef(id, stagegraph.CaptureFilesystemMetadata)
	c := metadataManifestRef(id, stagegraph.ExtractEmbeddedMetadata)
	if a != b || a == c || a == "" {
		t.Fatalf("metadata references are not stable/stage scoped: %q %q %q", a, b, c)
	}
}

// fakeObservationDB is intentionally incomplete: constructor and validation
// tests must not invent a second SQL mock contract for the 0036 schema.
type fakeObservationDB struct{}

func (fakeObservationDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, nil
}

func (fakeObservationDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, nil
}

func (fakeObservationDB) QueryRow(context.Context, string, ...any) pgx.Row {
	return nil
}

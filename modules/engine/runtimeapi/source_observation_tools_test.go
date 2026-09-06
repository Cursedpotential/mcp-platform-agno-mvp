package runtimeapi

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Cursedpotential/probata/engine/activities"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

var (
	observationSourceVersionID = uuid.MustParse("11111111-1111-1111-1111-111111111111")
	observationOriginalID      = uuid.MustParse("22222222-2222-2222-2222-222222222222")
)

type observationRow struct {
	scan func(dest ...any) error
}

func (r observationRow) Scan(dest ...any) error { return r.scan(dest...) }

type observationTestDB struct {
	sourceVersionID uuid.UUID
	originalID      uuid.UUID
	sourceStatus    string
	storageClass    string
	objectURI       string
	byteLength      int64
	contentSHA256   []byte
	immutableAt     time.Time
	provenance      string
	resolutionErr   error
}

func (observationTestDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, errors.New("not used")
}
func (observationTestDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("not used")
}

func (d observationTestDB) QueryRow(_ context.Context, sql string, args ...any) pgx.Row {
	return observationRow{scan: func(dest ...any) error {
		if d.resolutionErr != nil {
			return d.resolutionErr
		}
		for _, required := range []string{
			"JOIN context.retained_object object ON object.id = version.original_object_id",
			"JOIN context.source_version_object membership",
			"membership.source_version_id = version.id",
			"membership.object_id = object.id",
			"membership.object_role = 'original'",
			"version.id = $1::uuid",
			"object.id = $2::uuid",
			"version.status = 'retained'",
		} {
			if !strings.Contains(sql, required) {
				return errors.New("observation query does not enforce retained original membership")
			}
		}
		if len(args) != 2 {
			return errors.New("observation query requires source version and original object ids")
		}
		sourceVersionID, sourceOK := args[0].(uuid.UUID)
		originalID, objectOK := args[1].(uuid.UUID)
		if !sourceOK || !objectOK || sourceVersionID != d.sourceVersionID || originalID != d.originalID || d.sourceStatus != "retained" {
			return pgx.ErrNoRows
		}
		*dest[0].(*string) = d.storageClass
		*dest[1].(*string) = d.objectURI
		*dest[2].(*int64) = d.byteLength
		*dest[3].(*[]byte) = d.contentSHA256
		*dest[4].(*time.Time) = d.immutableAt
		*dest[5].(*string) = d.provenance
		return nil
	}}
}

func validObservationTestDB() observationTestDB {
	return observationTestDB{
		sourceVersionID: observationSourceVersionID,
		originalID:      observationOriginalID,
		sourceStatus:    "retained",
	}
}

func validObservationInput() activities.SourceObservationInput {
	return activities.SourceObservationInput{
		RequestID:        "workflow-1",
		SourceVersionRef: proffer.Ref(observationSourceVersionID.String()),
		OriginalRef:      proffer.Ref(observationOriginalID.String()),
		DeclaredFormat:   "sms_xml_backup",
	}
}

func TestFilesystemMetadataExtractorReportsFilesystemFacts(t *testing.T) {
	path := filepath.Join(t.TempDir(), "source.xml")
	if err := os.WriteFile(path, []byte("<xml/>"), 0o600); err != nil {
		t.Fatal(err)
	}
	generated := time.Date(2026, 8, 27, 6, 0, 0, 0, time.UTC)
	db := validObservationTestDB()
	db.storageClass, db.objectURI, db.byteLength = "filesystem", fileURI(path), 6
	db.contentSHA256, db.immutableAt, db.provenance = []byte{1, 2, 3, 4}, generated, "acquired_third_party"
	extractorAny, err := NewFilesystemMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	extractor := extractorAny.(*filesystemMetadataExtractor)
	extractor.clock = func() time.Time { return generated }

	input := validObservationInput()
	observation, err := extractor.ExtractSourceMetadata(context.Background(), input)
	if err != nil {
		t.Fatal(err)
	}
	if observation.ProvenanceClass != "acquired_third_party" {
		t.Fatalf("provenance class = %q", observation.ProvenanceClass)
	}
	if len(observation.Rows) != 1 {
		t.Fatalf("row count = %d, want 1", len(observation.Rows))
	}
	row := observation.Rows[0]
	if row.MetadataClass != activities.MetadataClassFilesystem {
		t.Fatalf("metadata class = %q", row.MetadataClass)
	}
	if row.ExtractorID != filesystemMetadataExtractorID || row.ExtractorVersion != filesystemMetadataExtractorVersion {
		t.Fatalf("extractor identity = %q/%q", row.ExtractorID, row.ExtractorVersion)
	}
	if !row.GeneratedAt.Equal(generated) {
		t.Fatalf("generated at = %v, want %v", row.GeneratedAt, generated)
	}
	var fields map[string]any
	if err := json.Unmarshal(row.Metadata, &fields); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"object_uri", "storage_class", "byte_length", "content_sha256", "immutable_at", "name", "size_bytes", "modified_at", "mode", "is_dir"} {
		if _, ok := fields[key]; !ok {
			t.Fatalf("metadata missing key %q: %v", key, fields)
		}
	}
	if fields["size_bytes"].(float64) != 6 {
		t.Fatalf("size_bytes = %v, want 6", fields["size_bytes"])
	}
}

func TestFilesystemMetadataExtractorNonFilesystemStorageClassSkipsStat(t *testing.T) {
	db := validObservationTestDB()
	db.storageClass, db.objectURI, db.byteLength = "immutable_object_store", "s3://bucket/key", 42
	db.contentSHA256, db.immutableAt, db.provenance = []byte{9, 9}, time.Now().UTC(), "unknown"
	extractorAny, err := NewFilesystemMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	input := validObservationInput()
	observation, err := extractorAny.ExtractSourceMetadata(context.Background(), input)
	if err != nil {
		t.Fatal(err)
	}
	if len(observation.Rows) != 1 {
		t.Fatalf("row count = %d, want 1", len(observation.Rows))
	}
	var fields map[string]any
	if err := json.Unmarshal(observation.Rows[0].Metadata, &fields); err != nil {
		t.Fatal(err)
	}
	if _, ok := fields["modified_at"]; ok {
		t.Fatal("non-filesystem storage class must not invent an OS stat timestamp")
	}
}

func TestFilesystemMetadataExtractorRejectsInvalidOriginalRef(t *testing.T) {
	extractorAny, err := NewFilesystemMetadataExtractor(validObservationTestDB())
	if err != nil {
		t.Fatal(err)
	}
	input := activities.SourceObservationInput{
		RequestID: "workflow-1", SourceVersionRef: "11111111-1111-1111-1111-111111111111",
		OriginalRef: "not-a-uuid", DeclaredFormat: "sms_xml_backup",
	}
	if _, err := extractorAny.ExtractSourceMetadata(context.Background(), input); err == nil {
		t.Fatal("expected non-UUID original reference to fail closed")
	}
}

func TestFilesystemMetadataExtractorPropagatesResolutionFailure(t *testing.T) {
	db := validObservationTestDB()
	db.resolutionErr = errors.New("no such retained original membership")
	extractorAny, err := NewFilesystemMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	input := validObservationInput()
	if _, err := extractorAny.ExtractSourceMetadata(context.Background(), input); err == nil {
		t.Fatal("expected retained object resolution failure to propagate")
	}
}

func TestNewFilesystemMetadataExtractorRequiresDatabase(t *testing.T) {
	if _, err := NewFilesystemMetadataExtractor(nil); err == nil {
		t.Fatal("expected nil database to be rejected")
	}
}

func TestFilesystemMetadataExtractorRejectsCrossSourceOriginalSubstitution(t *testing.T) {
	db := validObservationTestDB()
	extractor, err := NewFilesystemMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	input := validObservationInput()
	input.OriginalRef = "33333333-3333-3333-3333-333333333333"
	if _, err := extractor.ExtractSourceMetadata(context.Background(), input); !errors.Is(err, pgx.ErrNoRows) {
		t.Fatalf("cross-source original error = %v, want wrapped pgx.ErrNoRows", err)
	}
}

func TestFilesystemMetadataExtractorRejectsUnretainedSourceVersion(t *testing.T) {
	db := validObservationTestDB()
	db.sourceStatus = "registered"
	extractor, err := NewFilesystemMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := extractor.ExtractSourceMetadata(context.Background(), validObservationInput()); !errors.Is(err, pgx.ErrNoRows) {
		t.Fatalf("unretained source error = %v, want wrapped pgx.ErrNoRows", err)
	}
}

func TestEmbeddedMetadataExtractorReturnsDurableNoRows(t *testing.T) {
	db := validObservationTestDB()
	db.storageClass, db.objectURI, db.byteLength = "filesystem", "file:///retained/source.xml", 10
	db.contentSHA256, db.immutableAt, db.provenance = []byte{1}, time.Now().UTC(), "first_party_authored"
	extractorAny, err := NewEmbeddedMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	input := validObservationInput()
	observation, err := extractorAny.ExtractSourceMetadata(context.Background(), input)
	if err != nil {
		t.Fatal(err)
	}
	if len(observation.Rows) != 0 {
		t.Fatalf("embedded extractor rows = %d, want 0 (durable not-applicable)", len(observation.Rows))
	}
	if observation.ProvenanceClass != "first_party_authored" {
		t.Fatalf("provenance class = %q", observation.ProvenanceClass)
	}
}

func TestEmbeddedMetadataExtractorPropagatesResolutionFailure(t *testing.T) {
	db := validObservationTestDB()
	db.resolutionErr = errors.New("source version not found")
	extractorAny, err := NewEmbeddedMetadataExtractor(db)
	if err != nil {
		t.Fatal(err)
	}
	input := activities.SourceObservationInput{
		RequestID: "workflow-1", SourceVersionRef: "11111111-1111-1111-1111-111111111111",
		OriginalRef: "22222222-2222-2222-2222-222222222222", DeclaredFormat: "sms_xml_backup",
	}
	if _, err := extractorAny.ExtractSourceMetadata(context.Background(), input); err == nil {
		t.Fatal("expected provenance resolution failure to propagate")
	}
}

func TestNewEmbeddedMetadataExtractorRequiresDatabase(t *testing.T) {
	if _, err := NewEmbeddedMetadataExtractor(nil); err == nil {
		t.Fatal("expected nil database to be rejected")
	}
}

func TestNonContainerMemberEnumeratorReportsNotApplicable(t *testing.T) {
	enumerator := NewNonContainerMemberEnumerator()
	input := activities.SourceObservationInput{
		RequestID: "workflow-1", SourceVersionRef: "11111111-1111-1111-1111-111111111111",
		OriginalRef: "22222222-2222-2222-2222-222222222222", DeclaredFormat: "sms_xml_backup",
	}
	stream, err := enumerator.EnumerateMembers(context.Background(), input)
	if stream != nil {
		t.Fatal("non-container enumerator must not invent a member stream")
	}
	if !errors.Is(err, activities.ErrNotApplicable) {
		t.Fatalf("error = %v, want wrapped ErrNotApplicable", err)
	}
	if !strings.Contains(err.Error(), "sms_xml_backup") {
		t.Fatalf("error %q does not name the declared format", err.Error())
	}
}

func TestNonContainerMemberEnumeratorDefaultsUnknownFormat(t *testing.T) {
	enumerator := NewNonContainerMemberEnumerator()
	input := activities.SourceObservationInput{
		RequestID: "workflow-1", SourceVersionRef: "11111111-1111-1111-1111-111111111111",
		OriginalRef: "22222222-2222-2222-2222-222222222222",
	}
	_, err := enumerator.EnumerateMembers(context.Background(), input)
	if !strings.Contains(err.Error(), "unknown") {
		t.Fatalf("error %q does not report unknown format", err.Error())
	}
}

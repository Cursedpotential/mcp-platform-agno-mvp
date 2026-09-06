package runtimeapi

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Cursedpotential/probata/engine/normalize"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgtype"
)

type normalizedBundleTestDB struct{}

func (normalizedBundleTestDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, errors.New("not used")
}
func (normalizedBundleTestDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("not used")
}
func (normalizedBundleTestDB) QueryRow(context.Context, string, ...any) pgx.Row {
	return normalizedBundleTestRow{}
}

type normalizedBundleTestRow struct{}

func (normalizedBundleTestRow) Scan(...any) error { return errors.New("not used") }

type normalizedScanRow func(...any) error

func (row normalizedScanRow) Scan(dest ...any) error { return row(dest...) }

type normalizedPersistDB struct{ tx *normalizedPersistTx }

func (db normalizedPersistDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return db.tx, nil
}
func (normalizedPersistDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("not used")
}
func (normalizedPersistDB) QueryRow(context.Context, string, ...any) pgx.Row {
	return normalizedScanRow(func(...any) error { return errors.New("not used") })
}

type normalizedPersistTx struct {
	pgx.Tx
	objectID, sourceID, parentID uuid.UUID
	digest                       []byte
	length                       int64
	conflict                     bool
	committed                    bool
	membershipWrites             int
}

func (tx *normalizedPersistTx) QueryRow(_ context.Context, query string, args ...any) pgx.Row {
	switch {
	case strings.Contains(query, "INSERT INTO context.retained_object"):
		return normalizedScanRow(func(dest ...any) error {
			tx.digest = append([]byte(nil), args[1].([]byte)...)
			tx.length = args[2].(int64)
			if tx.conflict {
				return pgx.ErrNoRows
			}
			*dest[0].(*uuid.UUID) = tx.objectID
			return nil
		})
	case strings.Contains(query, "SELECT id FROM context.retained_object"):
		return normalizedScanRow(func(dest ...any) error {
			*dest[0].(*uuid.UUID) = tx.objectID
			return nil
		})
	case strings.Contains(query, "SELECT content_sha256, byte_length"):
		return normalizedScanRow(func(dest ...any) error {
			*dest[0].(*[]byte) = append([]byte(nil), tx.digest...)
			*dest[1].(*int64) = tx.length
			return nil
		})
	case strings.Contains(query, "SELECT source_version_id, extraction_bundle_object_id"):
		return normalizedScanRow(func(dest ...any) error {
			*dest[0].(*uuid.UUID) = tx.sourceID
			*dest[1].(*pgtype.UUID) = pgtype.UUID{Bytes: [16]byte(tx.parentID), Valid: true}
			return nil
		})
	case strings.Contains(query, "SELECT object_role, parent_object_id, member_locator"):
		return normalizedScanRow(func(dest ...any) error {
			*dest[0].(*string) = "derived_reference"
			*dest[1].(*pgtype.UUID) = pgtype.UUID{Bytes: [16]byte(tx.parentID), Valid: true}
			*dest[2].(*[]byte) = []byte(`{"kind":"normalized_bundle","contract":"platform-normalized-jsonl-v1"}`)
			return nil
		})
	default:
		return normalizedScanRow(func(...any) error { return errors.New("unexpected query") })
	}
}

func (tx *normalizedPersistTx) Exec(context.Context, string, ...any) (pgconn.CommandTag, error) {
	tx.membershipWrites++
	return pgconn.NewCommandTag("INSERT 0 1"), nil
}
func (tx *normalizedPersistTx) Commit(context.Context) error {
	tx.committed = true
	return nil
}
func (*normalizedPersistTx) Rollback(context.Context) error { return nil }

func normalizedTestRequest() proffer.StageRequest {
	return proffer.StageRequest{RequestID: "workflow-1", SourceVersionRef: "source-1", DeclaredFormat: "sms_xml_backup"}
}

func normalizedTestInput() normalize.NormalizerInput {
	return normalize.NormalizerInput{
		ContractVersion: normalize.ContractVersion, SourceVersionRef: "source-1", RawGenerationRef: "raw-1",
		DeclaredFormat: "sms_xml_backup", SourceProvenanceClass: normalize.ProvenanceAcquiredThirdParty,
		AcquiredAt: time.Date(2026, 8, 27, 6, 0, 0, 0, time.UTC),
	}
}

func normalizedTestHeader() normalize.BundleHeader {
	return normalize.BundleHeader{
		ContractVersion: normalize.ContractVersion, NormalizerID: "generic_message_normalizer", NormalizerVersion: "1.0.0",
		SourceVersionRef: "source-1", RawGenerationRef: "raw-1",
	}
}

func TestFilesystemNormalizedBundleFactoryRequiresDependencies(t *testing.T) {
	if _, err := NewFilesystemNormalizedBundleFactory(nil, t.TempDir()); err == nil {
		t.Fatal("expected nil database to be rejected")
	}
	if _, err := NewFilesystemNormalizedBundleFactory(normalizedBundleTestDB{}, ""); err == nil {
		t.Fatal("expected empty bundle directory to be rejected")
	}
}

func TestFilesystemNormalizedBundleFactoryRejectsMismatchedInput(t *testing.T) {
	factory, err := NewFilesystemNormalizedBundleFactory(normalizedBundleTestDB{}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	input := normalizedTestInput()
	input.SourceVersionRef = "other-source"
	if _, err := factory(context.Background(), normalizedTestRequest(), input); err == nil {
		t.Fatal("expected mismatched source version reference to be rejected")
	}
}

func TestFilesystemNormalizedBundleWriterBeginRejectsWrongHeader(t *testing.T) {
	factory, err := NewFilesystemNormalizedBundleFactory(normalizedBundleTestDB{}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), normalizedTestRequest(), normalizedTestInput())
	if err != nil {
		t.Fatal(err)
	}
	badHeader := normalizedTestHeader()
	badHeader.RawGenerationRef = "different-raw-generation"
	if err := writer.Begin(context.Background(), badHeader); err == nil {
		t.Fatal("expected header/input mismatch to fail closed")
	}
}

func TestFilesystemNormalizedBundleWriterEmitRejectsOutOfOrderOrdinal(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemNormalizedBundleFactory(normalizedBundleTestDB{}, root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), normalizedTestRequest(), normalizedTestInput())
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Begin(context.Background(), normalizedTestHeader()); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = writer.Abort(context.Background()) }()
	record := normalize.RecordEnvelope{
		RecordOrdinal: 1, RecordType: normalize.RecordTypeMessage, TimestampGranularity: normalize.GranularitySecond,
		TimestampCertainty: normalize.CertaintyExact, SourceAvailableFrom: normalizedTestInput().AcquiredAt,
		ProvenanceClass: normalize.ProvenanceAcquiredThirdParty,
	}
	if err := writer.Emit(context.Background(), record); err == nil {
		t.Fatal("expected out-of-order ordinal to fail closed")
	}
}

func TestFilesystemNormalizedBundleWriterStreamsAndQuarantinesAbort(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemNormalizedBundleFactory(normalizedBundleTestDB{}, root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), normalizedTestRequest(), normalizedTestInput())
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Begin(context.Background(), normalizedTestHeader()); err != nil {
		t.Fatal(err)
	}
	record := normalize.RecordEnvelope{
		RecordOrdinal: 0, RecordType: normalize.RecordTypeMessage, TimestampGranularity: normalize.GranularitySecond,
		TimestampCertainty: normalize.CertaintyExact, SourceAvailableFrom: normalizedTestInput().AcquiredAt,
		ProvenanceClass: normalize.ProvenanceAcquiredThirdParty,
	}
	if err := writer.Emit(context.Background(), record); err != nil {
		t.Fatal(err)
	}
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	matches, err := filepath.Glob(filepath.Join(root, "aborted", "*"))
	if err != nil || len(matches) != 1 {
		t.Fatalf("aborted bundle count = %d, err = %v", len(matches), err)
	}
	// Abort is idempotent once the writer is already finished.
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
}

func TestFilesystemNormalizedBundleWriterFinalizeRejectsAccountingMismatch(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemNormalizedBundleFactory(normalizedBundleTestDB{}, root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), normalizedTestRequest(), normalizedTestInput())
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Begin(context.Background(), normalizedTestHeader()); err != nil {
		t.Fatal(err)
	}
	record := normalize.RecordEnvelope{
		RecordOrdinal: 0, RecordType: normalize.RecordTypeMessage, TimestampGranularity: normalize.GranularitySecond,
		TimestampCertainty: normalize.CertaintyExact, SourceAvailableFrom: normalizedTestInput().AcquiredAt,
		ProvenanceClass: normalize.ProvenanceAcquiredThirdParty,
	}
	if err := writer.Emit(context.Background(), record); err != nil {
		t.Fatal(err)
	}
	if _, err := writer.Finalize(context.Background(), normalize.BundleAccounting{Emitted: 2}); err == nil {
		t.Fatal("expected accounting/record count mismatch to fail closed")
	}
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
}

func TestFilesystemNormalizedBundleWriterFinalizePersistsImmutableObject(t *testing.T) {
	root := t.TempDir()
	sourceID := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	rawID := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	tx := &normalizedPersistTx{
		objectID: uuid.MustParse("33333333-3333-3333-3333-333333333333"), sourceID: sourceID,
		parentID: uuid.MustParse("44444444-4444-4444-4444-444444444444"),
	}
	result := finalizeNormalizedTestBundle(t, root, normalizedPersistDB{tx: tx}, sourceID, rawID)
	if result.BundleRef != tx.objectID.String() || !tx.committed || tx.membershipWrites != 1 {
		t.Fatalf("result=%+v committed=%v membership_writes=%d", result, tx.committed, tx.membershipWrites)
	}
	objects, err := filepath.Glob(filepath.Join(root, "objects", "*.jsonl"))
	if err != nil || len(objects) != 1 {
		t.Fatalf("objects=%v err=%v", objects, err)
	}
	info, err := os.Stat(objects[0])
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm()&0o222 != 0 {
		t.Fatalf("published object mode = %v, want read-only", info.Mode().Perm())
	}
}

func TestFilesystemNormalizedBundleWriterRetryReusesVerifiedTarget(t *testing.T) {
	root := t.TempDir()
	sourceID := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	rawID := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	objectID := uuid.MustParse("33333333-3333-3333-3333-333333333333")
	parentID := uuid.MustParse("44444444-4444-4444-4444-444444444444")
	first := &normalizedPersistTx{objectID: objectID, sourceID: sourceID, parentID: parentID}
	firstResult := finalizeNormalizedTestBundle(t, root, normalizedPersistDB{tx: first}, sourceID, rawID)
	second := &normalizedPersistTx{objectID: objectID, sourceID: sourceID, parentID: parentID, conflict: true}
	secondResult := finalizeNormalizedTestBundle(t, root, normalizedPersistDB{tx: second}, sourceID, rawID)
	if firstResult != secondResult || !second.committed {
		t.Fatalf("first=%+v second=%+v committed=%v", firstResult, secondResult, second.committed)
	}
	objects, _ := filepath.Glob(filepath.Join(root, "objects", "*.jsonl"))
	if len(objects) != 1 {
		t.Fatalf("object count = %d, want one content-addressed target", len(objects))
	}
}

func finalizeNormalizedTestBundle(
	t *testing.T, root string, db normalizedPersistDB, sourceID, rawID uuid.UUID,
) normalize.BundleResult {
	t.Helper()
	request := proffer.StageRequest{RequestID: "workflow-1", SourceVersionRef: proffer.Ref(sourceID.String()), DeclaredFormat: "sms_xml_backup"}
	input := normalizedTestInput()
	input.SourceVersionRef, input.RawGenerationRef = sourceID.String(), rawID.String()
	header := normalizedTestHeader()
	header.SourceVersionRef, header.RawGenerationRef = sourceID.String(), rawID.String()
	factory, err := NewFilesystemNormalizedBundleFactory(db, root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), request, input)
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Begin(context.Background(), header); err != nil {
		t.Fatal(err)
	}
	record := normalize.RecordEnvelope{RecordOrdinal: 0, RecordType: normalize.RecordTypeMessage}
	if err := writer.Emit(context.Background(), record); err != nil {
		t.Fatal(err)
	}
	result, err := writer.Finalize(context.Background(), normalize.BundleAccounting{Emitted: 1})
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func TestFileURIRoundTripsForNormalizedBundle(t *testing.T) {
	path := filepath.Join(t.TempDir(), "normalized.jsonl")
	uri := fileURI(path)
	resolved, err := pathFromFileURI(uri)
	if err != nil {
		t.Fatal(err)
	}
	expected, _ := filepath.Abs(path)
	if resolved != filepath.Clean(expected) {
		t.Fatalf("resolved path = %q, want %q", resolved, expected)
	}
}

type inlineRetainedObjectDB struct {
	inline     []byte
	digest     []byte
	byteLength *int64
}

func (inlineRetainedObjectDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, errors.New("not used")
}
func (inlineRetainedObjectDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("not used")
}
func (d inlineRetainedObjectDB) QueryRow(context.Context, string, ...any) pgx.Row {
	return inlineRetainedObjectRow{inline: d.inline, digest: d.digest, byteLength: d.byteLength}
}

type inlineRetainedObjectRow struct {
	inline     []byte
	digest     []byte
	byteLength *int64
}

func (r inlineRetainedObjectRow) Scan(dest ...any) error {
	digest := r.digest
	if digest == nil {
		sum := sha256.Sum256(r.inline)
		digest = sum[:]
	}
	length := int64(len(r.inline))
	if r.byteLength != nil {
		length = *r.byteLength
	}
	*dest[0].(*string) = "inline"
	*dest[1].(*string) = "inline:normalized-bundle"
	*dest[2].(*[]byte) = r.inline
	*dest[3].(*[]byte) = append([]byte(nil), digest...)
	*dest[4].(*int64) = length
	return nil
}

func encodeNormalizedBundleLines(t *testing.T, lines ...normalizedBundleLine) []byte {
	t.Helper()
	var buf []byte
	for _, line := range lines {
		encoded, err := json.Marshal(line)
		if err != nil {
			t.Fatal(err)
		}
		buf = append(buf, encoded...)
		buf = append(buf, '\n')
	}
	return buf
}

func TestFilesystemNormalizedBundleReaderStreamsInlineBundle(t *testing.T) {
	header := normalizedTestHeader()
	record := normalize.RecordEnvelope{
		RecordOrdinal: 0, RecordType: normalize.RecordTypeMessage, TimestampGranularity: normalize.GranularitySecond,
		TimestampCertainty: normalize.CertaintyExact, SourceAvailableFrom: normalizedTestInput().AcquiredAt,
		ProvenanceClass: normalize.ProvenanceAcquiredThirdParty,
	}
	accounting := normalize.BundleAccounting{Emitted: 1}
	inline := encodeNormalizedBundleLines(t,
		normalizedBundleLine{Kind: "header", Contract: normalizedBundleContractVersion, Header: &header},
		normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record},
		normalizedBundleLine{Kind: "accounting", Contract: normalizedBundleContractVersion, Accounting: &accounting},
	)
	factory, err := NewFilesystemNormalizedBundleReaderFactory(inlineRetainedObjectDB{inline: inline}, nil)
	if err != nil {
		t.Fatal(err)
	}
	reader, err := factory(context.Background(), "33333333-3333-3333-3333-333333333333")
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	if reader.Header() != header {
		t.Fatalf("header = %#v, want %#v", reader.Header(), header)
	}
	got, err := reader.Next(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if got.RecordOrdinal != record.RecordOrdinal || got.RecordType != record.RecordType {
		t.Fatalf("record = %#v, want %#v", got, record)
	}
	if _, err := reader.Next(context.Background()); !errors.Is(err, io.EOF) {
		t.Fatalf("expected EOF after accounting trailer, got %v", err)
	}
}

func TestFilesystemNormalizedBundleReaderRejectsMissingHeader(t *testing.T) {
	record := normalize.RecordEnvelope{RecordOrdinal: 0}
	inline := encodeNormalizedBundleLines(t, normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record})
	factory, err := NewFilesystemNormalizedBundleReaderFactory(inlineRetainedObjectDB{inline: inline}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := factory(context.Background(), "33333333-3333-3333-3333-333333333333"); err == nil {
		t.Fatal("expected a bundle without a leading header line to be rejected")
	}
}

func TestFilesystemNormalizedBundleReaderRejectsMissingTrailer(t *testing.T) {
	header := normalizedTestHeader()
	record := normalize.RecordEnvelope{RecordOrdinal: 0}
	inline := encodeNormalizedBundleLines(t,
		normalizedBundleLine{Kind: "header", Contract: normalizedBundleContractVersion, Header: &header},
		normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record},
	)
	factory, err := NewFilesystemNormalizedBundleReaderFactory(inlineRetainedObjectDB{inline: inline}, nil)
	if err != nil {
		t.Fatal(err)
	}
	reader, err := factory(context.Background(), "33333333-3333-3333-3333-333333333333")
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	if _, err := reader.Next(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err := reader.Next(context.Background()); err == nil {
		t.Fatal("expected a bundle without an accounting trailer to fail closed rather than report EOF")
	}
}

func TestFilesystemNormalizedBundleReaderRejectsIntegrityMismatch(t *testing.T) {
	header := normalizedTestHeader()
	accounting := normalize.BundleAccounting{Emitted: 1}
	record := normalize.RecordEnvelope{RecordOrdinal: 0}
	inline := encodeNormalizedBundleLines(t,
		normalizedBundleLine{Kind: "header", Contract: normalizedBundleContractVersion, Header: &header},
		normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record},
		normalizedBundleLine{Kind: "accounting", Contract: normalizedBundleContractVersion, Accounting: &accounting},
	)
	factory, err := NewFilesystemNormalizedBundleReaderFactory(inlineRetainedObjectDB{inline: inline, digest: make([]byte, sha256.Size)}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := factory(context.Background(), "33333333-3333-3333-3333-333333333333"); err == nil {
		t.Fatal("expected retained-object digest mismatch to fail closed")
	}
}

func TestFilesystemNormalizedBundleReaderRejectsTrailerCountMismatch(t *testing.T) {
	header := normalizedTestHeader()
	record := normalize.RecordEnvelope{RecordOrdinal: 0}
	accounting := normalize.BundleAccounting{Emitted: 2}
	inline := encodeNormalizedBundleLines(t,
		normalizedBundleLine{Kind: "header", Contract: normalizedBundleContractVersion, Header: &header},
		normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record},
		normalizedBundleLine{Kind: "accounting", Contract: normalizedBundleContractVersion, Accounting: &accounting},
	)
	factory, _ := NewFilesystemNormalizedBundleReaderFactory(inlineRetainedObjectDB{inline: inline}, nil)
	reader, err := factory(context.Background(), "33333333-3333-3333-3333-333333333333")
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	if _, err := reader.Next(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err := reader.Next(context.Background()); err == nil || !strings.Contains(err.Error(), "does not match") {
		t.Fatalf("error = %v, want trailer count mismatch", err)
	}
}

func TestFilesystemNormalizedBundleReaderRejectsTrailingContent(t *testing.T) {
	header := normalizedTestHeader()
	record := normalize.RecordEnvelope{RecordOrdinal: 0}
	accounting := normalize.BundleAccounting{Emitted: 1}
	inline := encodeNormalizedBundleLines(t,
		normalizedBundleLine{Kind: "header", Contract: normalizedBundleContractVersion, Header: &header},
		normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record},
		normalizedBundleLine{Kind: "accounting", Contract: normalizedBundleContractVersion, Accounting: &accounting},
		normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &record},
	)
	factory, _ := NewFilesystemNormalizedBundleReaderFactory(inlineRetainedObjectDB{inline: inline}, nil)
	reader, err := factory(context.Background(), "33333333-3333-3333-3333-333333333333")
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	if _, err := reader.Next(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err := reader.Next(context.Background()); err == nil || !strings.Contains(err.Error(), "after its accounting trailer") {
		t.Fatalf("error = %v, want trailing content rejection", err)
	}
}

func TestNewFilesystemNormalizedBundleReaderFactoryRequiresDatabase(t *testing.T) {
	if _, err := NewFilesystemNormalizedBundleReaderFactory(nil, nil); err == nil {
		t.Fatal("expected nil database to be rejected")
	}
}

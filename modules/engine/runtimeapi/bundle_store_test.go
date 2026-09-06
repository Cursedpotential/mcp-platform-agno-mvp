package runtimeapi

import (
	"context"
	"errors"
	"path/filepath"
	"testing"

	"github.com/Cursedpotential/probata/engine/activities"
	"github.com/Cursedpotential/probata/engine/parser"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/jackc/pgx/v5"
)

func TestFilesystemBundleWriterStreamsAndQuarantinesAbort(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemBundleFactory(bundleTestDB{}, root)
	if err != nil {
		t.Fatal(err)
	}
	request := proffer.StageRequest{RequestID: "workflow-1", SourceVersionRef: "source-1", DeclaredFormat: "sms_xml_backup"}
	selection := activities.PersistedParserSelection{SourceVersionRef: "source-1", DeclaredFormat: "sms_xml_backup", ParserID: "sbv_sms_xml_backup", ParserVersion: "1.0.0"}
	input := parser.ParserInput{ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1", DeclaredFormat: "sms_xml_backup", FileOrMember: parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{StorageClass: "filesystem", URI: "file:///source.xml", ContentHash: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}}
	writer, err := factory(context.Background(), request, selection, input)
	if err != nil {
		t.Fatal(err)
	}
	header := parser.BundleHeader{ContractVersion: parser.ContractVersion, ParserID: selection.ParserID, ParserVersion: selection.ParserVersion, SourceVersionRef: "source-1", FormatID: "sms_xml_backup"}
	if err := writer.Begin(context.Background(), header); err != nil {
		t.Fatal(err)
	}
	if err := writer.Emit(context.Background(), parser.RawRecordEnvelope{RecordOrdinal: 0, RecordStatus: parser.StatusParsed, StoredBytes: &parser.StoredBytes{Bytes: []byte("exact")}, FormatID: "sms_xml_backup"}); err != nil {
		t.Fatal(err)
	}
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	matches, err := filepath.Glob(filepath.Join(root, "aborted", "*"))
	if err != nil || len(matches) != 1 {
		t.Fatalf("aborted bundle count = %d, err = %v", len(matches), err)
	}
}

func TestFileURIIsAbsoluteAndRoundTrips(t *testing.T) {
	path := filepath.Join(t.TempDir(), "bundle.jsonl")
	uri := fileURI(path)
	resolved, err := pathFromFileURI(uri)
	if err != nil {
		t.Fatal(err)
	}
	expected, _ := filepath.Abs(path)
	if resolved != filepath.Clean(expected) {
		t.Fatalf("resolved path = %q, want %q", resolved, expected)
	}
	if _, err := pathFromFileURI("https://example.invalid/bundle"); err == nil {
		t.Fatal("network URI accepted as retained filesystem object")
	}
}

type bundleTestDB struct{}

func (bundleTestDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, errors.New("not used")
}
func (bundleTestDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("not used")
}
func (bundleTestDB) QueryRow(context.Context, string, ...any) pgx.Row { return bundleTestRow{} }

type bundleTestRow struct{}

func (bundleTestRow) Scan(...any) error { return errors.New("not used") }

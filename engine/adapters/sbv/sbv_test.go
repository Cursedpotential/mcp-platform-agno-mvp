package sbv

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"testing"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/lowcarbdev/sbv/pkg/parseonly"
)

func TestNewAllExcludesEmailFormatsAndUsesCanonicalIDs(t *testing.T) {
	adapters, err := NewAll(func(context.Context, string) (io.ReadCloser, error) { return io.NopCloser(bytes.NewReader(nil)), nil })
	if err != nil {
		t.Fatal(err)
	}
	if len(adapters) != len(parseonly.Formats())-2 {
		t.Fatalf("adapter count = %d, want %d", len(adapters), len(parseonly.Formats())-2)
	}
	for _, adapter := range adapters {
		capability := adapter.Capability()
		if err := capability.Validate(); err != nil {
			t.Fatal(err)
		}
		if len(capability.ParserID) < 4 || capability.ParserID[:4] != "sbv_" {
			t.Fatalf("parser ID = %q", capability.ParserID)
		}
		if capability.ParserVersion != "1.1.0" {
			t.Fatalf("parser version = %q, want 1.1.0", capability.ParserVersion)
		}
	}
}

func TestAdapterStreamsExactChatGPTRecordIntoCommonContract(t *testing.T) {
	source := []byte(`[{"title":"Conversation","create_time":1700000000,"mapping":{"root":{"id":"root","parent":null,"children":["n1"]},"n1":{"id":"n1","parent":"root","children":[],"message":{"id":"m1","author":{"role":"user"},"create_time":1700000001,"content":{"content_type":"text","parts":["hello"]}}}}}]`)
	adapter, err := New(parseonly.FormatChatGPTJSON, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(source)), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1",
		DeclaredFormat: parseonly.FormatChatGPTJSON,
		FileOrMember:   parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://1"}},
	}
	var records []parser.RawRecordEnvelope
	accounting, err := adapter.Parse(context.Background(), input, recordSink{records: &records})
	if err != nil {
		t.Fatal(err)
	}
	if accounting.Emitted != 1 || accounting.Rejected != 0 || len(records) != 2 || records[0].RecordOrdinal != 0 || records[0].StoredBytes == nil || len(records[0].StoredBytes.Bytes) == 0 {
		t.Fatalf("accounting=%+v records=%+v", accounting, records)
	}
	if records[0].FormatID != input.DeclaredFormat || records[0].RecordStatus != parser.StatusParsed {
		t.Fatalf("record = %+v", records[0])
	}
	var fields struct {
		Body       string   `json:"body"`
		Sender     string   `json:"sender"`
		Recipients []string `json:"recipients"`
		OccurredAt string   `json:"occurred_at"`
	}
	if err := json.Unmarshal(records[0].NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if fields.Body != "hello" || fields.OccurredAt == "" {
		t.Fatalf("native fields = %+v", fields)
	}
	if _, err := time.Parse(time.RFC3339, fields.OccurredAt); err != nil {
		t.Fatalf("occurred_at = %q: %v", fields.OccurredAt, err)
	}
	coverage := records[1]
	if coverage.RecordOrdinal != 1 || coverage.RecordStatus != parser.StatusEnvelope || coverage.Locator == nil || coverage.Locator.Type != parser.LocatorWholeObject {
		t.Fatalf("coverage envelope = %+v", coverage)
	}
	if coverage.Locator.ObjectRef.URI != input.FileOrMember.ObjectRef.URI {
		t.Fatalf("coverage locator = %+v, want source locator %+v", coverage.Locator, input.FileOrMember)
	}
}

func TestToEnvelopePromotesSBVMessageFields(t *testing.T) {
	occurredAt := time.Date(2024, 5, 6, 7, 8, 9, 0, time.UTC)
	envelope, err := toEnvelope(parseonly.FormatNDJSON, parseonly.Record{
		Status: parseonly.StatusParsed, Raw: []byte(`{"message":"hello"}`), Content: "hello",
		Sender: "alice", Participants: []string{"alice", "bob"},
		Recipients: []parseonly.Recipient{{Identity: "bob", Role: "to"}}, OccurredAt: &occurredAt,
	})
	if err != nil {
		t.Fatal(err)
	}
	var fields struct {
		Body         string   `json:"body"`
		Sender       string   `json:"sender"`
		Recipients   []string `json:"recipients"`
		Participants []string `json:"participants"`
		OccurredAt   string   `json:"occurred_at"`
	}
	if err := json.Unmarshal(envelope.NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if fields.Body != "hello" || fields.Sender != "alice" || len(fields.Recipients) != 1 || fields.Recipients[0] != "bob" || len(fields.Participants) != 2 || fields.OccurredAt == "" {
		t.Fatalf("native fields = %+v", fields)
	}
}

func TestAdapterHonorsExactByteRangeLocator(t *testing.T) {
	source := []byte(`{"body":"hello"}`)
	adapter, err := New(parseonly.FormatNDJSON, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(append([]byte("prefix"), append(source, []byte("suffix")...)...))), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1",
		DeclaredFormat: parseonly.FormatNDJSON,
		FileOrMember: parser.Locator{
			Type: parser.LocatorByteRange, ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://1"},
			ByteRange: &parser.ByteRange{Offset: uint64(len("prefix")), Length: uint64(len(source))},
		},
	}
	var records []parser.RawRecordEnvelope
	if _, err := adapter.Parse(context.Background(), input, recordSink{records: &records}); err != nil {
		t.Fatal(err)
	}
	if len(records) != 2 || !bytes.Equal(records[0].StoredBytes.Bytes, source) {
		t.Fatalf("records = %+v", records)
	}
	coverage := records[1]
	if coverage.RecordStatus != parser.StatusEnvelope || coverage.Locator == nil || coverage.Locator.ByteRange == nil {
		t.Fatalf("coverage envelope = %+v", coverage)
	}
	if *coverage.Locator.ByteRange != *input.FileOrMember.ByteRange {
		t.Fatalf("coverage range = %+v, want %+v", coverage.Locator.ByteRange, input.FileOrMember.ByteRange)
	}
}

func TestAdapterAccountingSeparatesRejectedRecordsFromParsed(t *testing.T) {
	source := []byte("not valid json\n")
	adapter, err := New(parseonly.FormatNDJSON, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(source)), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1",
		DeclaredFormat: parseonly.FormatNDJSON,
		FileOrMember:   parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://1"}},
	}
	var records []parser.RawRecordEnvelope
	accounting, err := adapter.Parse(context.Background(), input, recordSink{records: &records})
	if err != nil {
		t.Fatal(err)
	}
	if accounting.Emitted != 0 || accounting.Rejected != 1 {
		t.Fatalf("accounting = %+v, want one rejected record", accounting)
	}
	if len(records) != 2 || records[0].RecordStatus != parser.StatusRejected || records[1].RecordStatus != parser.StatusEnvelope {
		t.Fatalf("records = %+v", records)
	}
}

type recordSink struct{ records *[]parser.RawRecordEnvelope }

func (s recordSink) Emit(_ context.Context, record parser.RawRecordEnvelope) error {
	*s.records = append(*s.records, record)
	return nil
}

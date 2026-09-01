package sbv

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"strings"
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
		if capability.ParserVersion != "1.4.0" {
			t.Fatalf("parser version = %q, want 1.4.0", capability.ParserVersion)
		}
		if capability.SupportsAttachments {
			t.Fatal("adapter without an immutable artifact sink claimed attachment support")
		}
	}
}

func TestRegistryMapsOnlySafeWorkbenchDeclaredFormats(t *testing.T) {
	adapters, err := NewAll(func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(nil)), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	registry, err := parser.NewRegistry(adapters...)
	if err != nil {
		t.Fatal(err)
	}
	for _, format := range []parser.FormatID{formatWorkbenchSMSExportXML, formatLegacySMSXML} {
		selected, err := registry.Select(format)
		if err != nil {
			t.Fatalf("select safe SMS alias %q: %v", format, err)
		}
		if selected.Capability().ParserID != "sbv_"+parseonly.FormatSMSBackupXML {
			t.Fatalf("format %q selected %q", format, selected.Capability().ParserID)
		}
	}
	for _, format := range []parser.FormatID{"markdown", "message_export_json", "docx", "html"} {
		if _, err := registry.Select(format); err == nil || !strings.Contains(err.Error(), "no parser adapter declares format") {
			t.Fatalf("ambiguous/unsupported Workbench format %q did not fail closed: %v", format, err)
		}
	}
}

func TestAdapterExecutesWorkbenchSMSAliasWithoutChangingDeclaredFormat(t *testing.T) {
	source := []byte(`<smses count="1"><sms address="+15551234567" date="1700000000000" type="1" body="hello" /></smses>`)
	adapter, err := New(parseonly.FormatSMSBackupXML, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(source)), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1",
		DeclaredFormat: formatWorkbenchSMSExportXML,
		FileOrMember: parser.Locator{Type: parser.LocatorWholeObject,
			ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://sms"}},
	}
	var records []parser.RawRecordEnvelope
	if _, err := adapter.Parse(context.Background(), input, recordSink{records: &records}); err != nil {
		t.Fatal(err)
	}
	if len(records) != 2 || records[0].FormatID != formatWorkbenchSMSExportXML || records[1].FormatID != formatWorkbenchSMSExportXML {
		t.Fatalf("records did not preserve declared format %q: %+v", formatWorkbenchSMSExportXML, records)
	}
}

func TestAdapterPreservesActualSMSXMLCallSemantics(t *testing.T) {
	source := []byte(`<smses count="1"><call number="+15551234567" duration="17" date="1700000000000" type="3" /></smses>`)
	adapter, err := New(parseonly.FormatSMSBackupXML, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(source)), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1",
		DeclaredFormat: parseonly.FormatSMSBackupXML,
		FileOrMember: parser.Locator{Type: parser.LocatorWholeObject,
			ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://calls"}},
	}
	var records []parser.RawRecordEnvelope
	if _, err := adapter.Parse(context.Background(), input, recordSink{records: &records}); err != nil {
		t.Fatal(err)
	}
	if len(records) != 2 {
		t.Fatalf("records = %+v", records)
	}
	var fields parser.CommonNativeFields
	if err := json.Unmarshal(records[0].NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if fields.RecordKind != parser.NativeKindCall || fields.Call == nil ||
		fields.Call.Direction != parser.CallDirectionIncoming ||
		fields.Call.Disposition != parser.CallDispositionMissed || !fields.Call.Missed ||
		fields.Call.DurationSeconds == nil || *fields.Call.DurationSeconds != 17 {
		t.Fatalf("actual XML call fields = %+v; metadata=%s", fields, records[0].NativeMetadata)
	}
}

func TestAdapterPreservesEveryRetainedXMLMMSAttachment(t *testing.T) {
	parts := [][]byte{[]byte("image-one"), []byte("document-two"), []byte("audio-three")}
	source := []byte(`<smses count="1"><mms date="1700000000000" msg_box="1" read="1"><parts>` +
		`<part seq="0" ct="image/png" name="photo.png" data="aW1hZ2Utb25l" />` +
		`<part seq="1" ct="application/pdf" name="filing.pdf" data="ZG9jdW1lbnQtdHdv" />` +
		`<part seq="2" ct="audio/mpeg" name="memo.mp3" data="YXVkaW8tdGhyZWU=" />` +
		`</parts><addrs><addr address="+15551234567" type="137" /></addrs></mms></smses>`)
	artifacts, err := NewFilesystemArtifactSink(t.TempDir(), passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	adapter, err := NewWithArtifactSink(parseonly.FormatSMSBackupXML, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(source)), nil
	}, artifacts)
	if err != nil {
		t.Fatal(err)
	}
	if !adapter.Capability().SupportsAttachments {
		t.Fatal("adapter with immutable artifact sink did not declare attachment support")
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-version-42",
		DeclaredFormat: parseonly.FormatSMSBackupXML,
		FileOrMember: parser.Locator{Type: parser.LocatorWholeObject,
			ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://retained/sms.xml"}},
	}
	var records []parser.RawRecordEnvelope
	accounting, err := adapter.Parse(context.Background(), input, recordSink{records: &records})
	if err != nil {
		t.Fatal(err)
	}
	if accounting.Emitted != 1 || accounting.Attachments != 3 || len(records) != 2 {
		t.Fatalf("accounting=%+v records=%+v", accounting, records)
	}
	record := records[0]
	if err := record.Validate(input.DeclaredFormat); err != nil {
		t.Fatal(err)
	}
	if record.Locator == nil || record.StoredBytes != nil || len(record.Attachments) != 3 {
		t.Fatalf("MMS envelope=%+v", record)
	}
	rawMMS := source[bytes.Index(source, []byte("<mms ")) : bytes.Index(source, []byte("</mms>"))+len("</mms>")]
	assertEngineLocator(t, artifacts.root, record.Locator, rawMMS)
	wantNames := []string{"photo.png", "filing.pdf", "memo.mp3"}
	wantMIME := []string{"image/png", "application/pdf", "audio/mpeg"}
	for index, attachment := range record.Attachments {
		assertEngineLocator(t, artifacts.root, &attachment.Locator, parts[index])
		if attachment.AttachmentOrdinal != uint64(index) {
			t.Fatalf("attachment ordinal=%d want=%d", attachment.AttachmentOrdinal, index)
		}
		var metadata struct {
			SourceAssociation string `json:"source_association"`
			ParentSourcePos   string `json:"parent_source_pos"`
			OriginalName      string `json:"original_name"`
			MIME              string `json:"mime"`
			DigestSHA256      string `json:"digest_sha256"`
			ByteCount         int64  `json:"byte_count"`
		}
		if err := json.Unmarshal(attachment.NativeMetadata, &metadata); err != nil {
			t.Fatal(err)
		}
		if metadata.SourceAssociation != "source-version-42" || metadata.ParentSourcePos != "element:1" || metadata.OriginalName != wantNames[index] ||
			metadata.MIME != wantMIME[index] || metadata.DigestSHA256 != sha256String(parts[index]) ||
			metadata.ByteCount != int64(len(parts[index])) {
			t.Fatalf("attachment metadata=%+v", metadata)
		}
	}
}

func TestAdapterRejectsMalformedAttachmentWithoutCountingItAsPersisted(t *testing.T) {
	source := []byte(`<smses count="1"><mms date="1700000000000" msg_box="1"><parts><part seq="0" ct="image/png" name="broken.png" data="%%%not-base64%%%" /></parts><addrs><addr address="+1555" type="137" /></addrs></mms></smses>`)
	root := t.TempDir()
	artifacts, err := NewFilesystemArtifactSink(root, passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	adapter, err := NewWithArtifactSink(parseonly.FormatSMSBackupXML, func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewReader(source)), nil
	}, artifacts)
	if err != nil {
		t.Fatal(err)
	}
	input := parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-version-42",
		DeclaredFormat: parseonly.FormatSMSBackupXML,
		FileOrMember: parser.Locator{Type: parser.LocatorWholeObject,
			ObjectRef: parser.ObjectRef{StorageClass: "immutable_object_store", URI: "object://retained/sms.xml"}},
	}
	var records []parser.RawRecordEnvelope
	accounting, err := adapter.Parse(context.Background(), input, recordSink{records: &records})
	if err != nil {
		t.Fatal(err)
	}
	if accounting.Rejected != 1 || accounting.Emitted != 0 || accounting.Attachments != 0 || len(records) != 2 {
		t.Fatalf("accounting=%+v records=%+v", accounting, records)
	}
	if len(records[0].Attachments) != 0 || records[0].RecordStatus != parser.StatusRejected {
		t.Fatalf("malformed record=%+v", records[0])
	}
	var metadata struct {
		Captured uint64                        `json:"sbv_captured_attachments"`
		Failures []parseonly.AttachmentFailure `json:"sbv_attachment_failures"`
	}
	if err := json.Unmarshal(records[0].NativeMetadata, &metadata); err != nil {
		t.Fatal(err)
	}
	if metadata.Captured != 1 || len(metadata.Failures) != 1 || metadata.Failures[0].ConversionStatus != "decode_failed" {
		t.Fatalf("failure metadata=%+v", metadata)
	}
	quarantineRoot := filepath.Join(root, "attempts", "quarantine", sha256String([]byte("source-version-42")))
	entries, err := os.ReadDir(quarantineRoot)
	if err != nil || len(entries) != 1 {
		t.Fatalf("quarantine entries=%v err=%v", entries, err)
	}
}

func TestNewWithArtifactSinkRequiresSink(t *testing.T) {
	_, err := NewWithArtifactSink(parseonly.FormatSMSBackupXML,
		func(context.Context, string) (io.ReadCloser, error) { return io.NopCloser(strings.NewReader("")), nil }, nil)
	if err == nil {
		t.Fatal("nil immutable artifact sink was accepted")
	}
}

func TestFilesystemArtifactSinkIsIdempotentSourceScopedAndFailClosed(t *testing.T) {
	if _, err := NewFilesystemArtifactSink(filepath.Join(t.TempDir(), "missing"), passthroughRegistrar{}); err == nil {
		t.Fatal("missing immutable root was accepted")
	}
	sink, err := NewFilesystemArtifactSink(t.TempDir(), passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	attemptID := strings.Repeat("a", 32)
	stage, err := sink.ArtifactDir(context.Background(), "source-version-42", attemptID)
	if err != nil {
		t.Fatal(err)
	}
	staged := filepath.Join(stage, "part.bin")
	data := []byte("lossless attachment")
	if err := os.WriteFile(staged, data, 0600); err != nil {
		t.Fatal(err)
	}
	artifact := parseonly.Artifact{
		Kind: parseonly.ArtifactAttachment, SourceAssociation: "source-version-42",
		AttemptID:       attemptID,
		ParentSourcePos: "element:7", AttachmentOrdinal: 2,
		OriginalName: "part.bin", MIME: "application/octet-stream",
		StagedPath: staged, ByteCount: int64(len(data)),
	}
	first, err := sink.Store(context.Background(), artifact)
	if err != nil {
		t.Fatal(err)
	}
	second, err := sink.Store(context.Background(), artifact)
	if err != nil {
		t.Fatal(err)
	}
	if first != second || first.ContentHash != sha256String(data) {
		t.Fatalf("unstable locators: first=%+v second=%+v", first, second)
	}
	assertEngineLocator(t, sink.root, &parser.Locator{Type: parser.LocatorWholeObject,
		ObjectRef: parser.ObjectRef{StorageClass: first.StorageClass, URI: first.URI, ContentHash: first.ContentHash}}, data)
	escaped := artifact
	escaped.StagedPath = filepath.Join(t.TempDir(), "outside.bin")
	if err := os.WriteFile(escaped.StagedPath, data, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := sink.Store(context.Background(), escaped); err == nil {
		t.Fatal("artifact outside source-scoped staging was accepted")
	}
	conflictPath := filepath.Join(stage, "conflict.bin")
	if err := os.WriteFile(conflictPath, []byte("different bytes"), 0600); err != nil {
		t.Fatal(err)
	}
	conflict := artifact
	conflict.StagedPath = conflictPath
	conflict.ByteCount = int64(len("different bytes"))
	if _, err := sink.Store(context.Background(), conflict); err == nil || !strings.Contains(err.Error(), "different bytes") {
		t.Fatalf("logical identity conflict was not rejected: %v", err)
	}
}

func TestFilesystemArtifactSinkQuarantinesInterruptedAttemptOnStartup(t *testing.T) {
	root := t.TempDir()
	sourceHash := sha256String([]byte("source-version-42"))
	attemptID := strings.Repeat("b", 32)
	inflight := filepath.Join(root, "attempts", "inflight", sourceHash, attemptID)
	if err := os.MkdirAll(filepath.Join(inflight, "decoder"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(inflight, "decoder", "partial.bin"), []byte("partial"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewFilesystemArtifactSink(root, passthroughRegistrar{}); err != nil {
		t.Fatal(err)
	}
	quarantined := filepath.Join(root, "attempts", "quarantine", sourceHash, attemptID)
	if _, err := os.Stat(filepath.Join(quarantined, "decoder", "partial.bin")); err != nil {
		t.Fatalf("interrupted bytes were not preserved in quarantine: %v", err)
	}
	if _, err := os.Stat(filepath.Join(quarantined, "QUARANTINE.txt")); err != nil {
		t.Fatalf("interrupted quarantine reason missing: %v", err)
	}
	if _, err := os.Stat(inflight); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("inflight attempt still exposed: %v", err)
	}
}

func TestFilesystemArtifactSinkRequiresExclusiveRuntimeOwnership(t *testing.T) {
	root := t.TempDir()
	first, err := NewFilesystemArtifactSink(root, passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := NewFilesystemArtifactSink(root, passthroughRegistrar{}); err == nil || !strings.Contains(err.Error(), "runtime lock is held") {
		t.Fatalf("second runtime was not rejected: %v", err)
	}
	if err := first.Close(); err != nil {
		t.Fatal(err)
	}
	second, err := NewFilesystemArtifactSink(root, passthroughRegistrar{})
	if err != nil {
		t.Fatalf("cleanly released runtime lock was not reusable: %v", err)
	}
	if err := second.Close(); err != nil {
		t.Fatal(err)
	}
	released, err := os.ReadDir(filepath.Join(root, "locks", "released"))
	if err != nil || len(released) != 2 {
		t.Fatalf("released locks=%v err=%v", released, err)
	}
}

func TestClosedSinkCannotMutateAfterNewRuntimeAcquiresOwnership(t *testing.T) {
	root := t.TempDir()
	oldSink, err := NewFilesystemArtifactSink(root, passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	if err := oldSink.Close(); err != nil {
		t.Fatal(err)
	}
	newSink, err := NewFilesystemArtifactSink(root, passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = newSink.Close() }()
	attemptID := strings.Repeat("d", 32)
	stage, err := newSink.ArtifactDir(context.Background(), "source-version-42", attemptID)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(stage, "part.bin")
	data := []byte("new owner bytes")
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	artifact := parseonly.Artifact{
		Kind: parseonly.ArtifactAttachment, SourceAssociation: "source-version-42", AttemptID: attemptID,
		ParentSourcePos: "element:9", StagedPath: path, ByteCount: int64(len(data)),
	}
	mutations := []struct {
		name string
		call func() error
	}{
		{"artifact dir", func() error {
			_, err := oldSink.ArtifactDir(context.Background(), "source-version-42", attemptID)
			return err
		}},
		{"store", func() error { _, err := oldSink.Store(context.Background(), artifact); return err }},
		{"complete", func() error { return oldSink.CompleteAttempt(context.Background(), "source-version-42", attemptID) }},
		{"quarantine", func() error {
			return oldSink.QuarantineAttempt(context.Background(), "source-version-42", attemptID, "must not run")
		}},
	}
	for _, mutation := range mutations {
		if err := mutation.call(); err == nil || !strings.Contains(err.Error(), "closed") {
			t.Fatalf("closed sink %s error=%v", mutation.name, err)
		}
	}
	if _, err := newSink.Store(context.Background(), artifact); err != nil {
		t.Fatalf("new runtime lost ownership after stale sink calls: %v", err)
	}
	if err := newSink.CompleteAttempt(context.Background(), "source-version-42", attemptID); err != nil {
		t.Fatalf("new runtime could not complete its attempt: %v", err)
	}
}

func TestSinkMutationRejectsMissingOrMismatchedRuntimeLock(t *testing.T) {
	root := t.TempDir()
	sink, err := NewFilesystemArtifactSink(root, passthroughRegistrar{})
	if err != nil {
		t.Fatal(err)
	}
	attemptID := strings.Repeat("e", 32)
	preserved := filepath.Join(root, "preserved-owner.lock")
	if err := os.Rename(sink.lockPath, preserved); err != nil {
		t.Fatal(err)
	}
	if _, err := sink.ArtifactDir(context.Background(), "source-version-42", attemptID); err == nil || !strings.Contains(err.Error(), "validate active") {
		t.Fatalf("missing runtime lock error=%v", err)
	}
	if err := os.Rename(preserved, sink.lockPath); err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(sink.lockPath, preserved); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(sink.lockPath, []byte("token=other-owner\n"), 0400); err != nil {
		t.Fatal(err)
	}
	if _, err := sink.ArtifactDir(context.Background(), "source-version-42", attemptID); err == nil || !strings.Contains(err.Error(), "does not match") {
		t.Fatalf("mismatched runtime lock error=%v", err)
	}
	if err := os.Rename(sink.lockPath, filepath.Join(root, "preserved-mismatched.lock")); err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(preserved, sink.lockPath); err != nil {
		t.Fatal(err)
	}
	if err := sink.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestFilesystemArtifactSinkPreservesEveryDeduplicatedObjectInDistinctQuarantine(t *testing.T) {
	root := t.TempDir()
	sink, err := NewFilesystemArtifactSink(root, fixedRegistrar{uri: "file:///governed/shared.bin"})
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = sink.Close() }()
	attemptID := strings.Repeat("c", 32)
	stage, err := sink.ArtifactDir(context.Background(), "source-version-42", attemptID)
	if err != nil {
		t.Fatal(err)
	}
	data := []byte("identical bytes")
	for ordinal := uint64(0); ordinal < 2; ordinal++ {
		path := filepath.Join(stage, fmt.Sprintf("part-%d.bin", ordinal))
		if err := os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := sink.Store(context.Background(), parseonly.Artifact{
			Kind: parseonly.ArtifactAttachment, SourceAssociation: "source-version-42", AttemptID: attemptID,
			ParentSourcePos: "element:7", AttachmentOrdinal: ordinal, StagedPath: path, ByteCount: int64(len(data)),
		}); err != nil {
			t.Fatal(err)
		}
	}
	duplicateRoot := filepath.Join(sink.attemptRoot("source-version-42", attemptID), "duplicates")
	entries, err := os.ReadDir(duplicateRoot)
	if err != nil || len(entries) != 2 {
		t.Fatalf("duplicate quarantines=%v err=%v", entries, err)
	}
	for _, entry := range entries {
		got, err := os.ReadFile(filepath.Join(duplicateRoot, entry.Name(), "object.bin"))
		if err != nil || !bytes.Equal(got, data) {
			t.Fatalf("duplicate %q bytes=%q err=%v", entry.Name(), got, err)
		}
	}
}

type passthroughRegistrar struct{}

func (passthroughRegistrar) RegisterArtifact(_ context.Context, registration parseonly.ArtifactRegistration) (parseonly.ArtifactLocator, error) {
	return parseonly.ArtifactLocator{StorageClass: "filesystem", URI: registration.ObjectURI, ContentHash: registration.DigestSHA256}, nil
}

type fixedRegistrar struct{ uri string }

func (registrar fixedRegistrar) RegisterArtifact(_ context.Context, registration parseonly.ArtifactRegistration) (parseonly.ArtifactLocator, error) {
	return parseonly.ArtifactLocator{StorageClass: "filesystem", URI: registrar.uri, ContentHash: registration.DigestSHA256}, nil
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
		Status: parseonly.StatusParsed, Kind: "object", Raw: []byte(`{"message":"hello"}`), Content: "hello",
		Sender: "alice", Participants: []string{"alice", "bob"},
		Recipients: []parseonly.Recipient{{Identity: "bob", Role: "to"}}, OccurredAt: &occurredAt,
	})
	if err != nil {
		t.Fatal(err)
	}
	var fields struct {
		RecordKind   string   `json:"record_kind"`
		Body         string   `json:"body"`
		Sender       string   `json:"sender"`
		Recipients   []string `json:"recipients"`
		Participants []string `json:"participants"`
		OccurredAt   string   `json:"occurred_at"`
	}
	if err := json.Unmarshal(envelope.NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if fields.RecordKind != "object" || fields.Body != "hello" || fields.Sender != "alice" || len(fields.Recipients) != 1 || fields.Recipients[0] != "bob" || len(fields.Participants) != 2 || fields.OccurredAt == "" {
		t.Fatalf("native fields = %+v", fields)
	}
}

func TestToEnvelopePromotesMissedCallSemantics(t *testing.T) {
	envelope, err := toEnvelope(parseonly.FormatSMSBackupXML, parseonly.Record{
		Status: parseonly.StatusParsed, Kind: "call", Raw: []byte(`<call type="3" duration="0" />`),
		Participants: []string{"+15551234567"},
		Metadata:     map[string]any{"Type": "3", "Duration": "0"},
	})
	if err != nil {
		t.Fatal(err)
	}
	var fields parser.CommonNativeFields
	if err := json.Unmarshal(envelope.NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if err := fields.Validate(); err != nil {
		t.Fatal(err)
	}
	if fields.RecordKind != parser.NativeKindCall || fields.Call == nil ||
		fields.Call.Direction != parser.CallDirectionIncoming ||
		fields.Call.Disposition != parser.CallDispositionMissed || !fields.Call.Missed ||
		fields.Call.DurationSeconds == nil || *fields.Call.DurationSeconds != 0 {
		t.Fatalf("missed call fields = %+v", fields)
	}
}

func TestToEnvelopePromotesOutgoingCallDurationAndRejectsInvalidDuration(t *testing.T) {
	record := parseonly.Record{
		Status: parseonly.StatusParsed, Kind: "call", Raw: []byte(`<call type="2" duration="42" />`),
		Metadata: map[string]any{"Type": "2", "Duration": "42"},
	}
	envelope, err := toEnvelope(parseonly.FormatSMSBackupXML, record)
	if err != nil {
		t.Fatal(err)
	}
	var fields parser.CommonNativeFields
	if err := json.Unmarshal(envelope.NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if fields.Call == nil || fields.Call.Direction != parser.CallDirectionOutgoing ||
		fields.Call.Disposition != parser.CallDispositionCompleted || fields.Call.Missed ||
		fields.Call.DurationSeconds == nil || *fields.Call.DurationSeconds != 42 {
		t.Fatalf("outgoing call fields = %+v", fields)
	}
	record.Metadata["Duration"] = "-1"
	if _, err := toEnvelope(parseonly.FormatSMSBackupXML, record); err == nil || !strings.Contains(err.Error(), "non-negative integer") {
		t.Fatalf("negative duration did not fail closed: %v", err)
	}
}

func TestToEnvelopePreservesTranscriptMissedCallAndDirection(t *testing.T) {
	envelope, err := toEnvelope(parseonly.FormatTranscript, parseonly.Record{
		Status: parseonly.StatusParsed, Kind: "call", Raw: []byte("Missed call"), Content: "Missed call",
		Metadata: map[string]any{"direction": "inbound"},
	})
	if err != nil {
		t.Fatal(err)
	}
	var fields parser.CommonNativeFields
	if err := json.Unmarshal(envelope.NativeFields, &fields); err != nil {
		t.Fatal(err)
	}
	if fields.Call == nil || fields.Call.Direction != parser.CallDirectionIncoming ||
		fields.Call.Disposition != parser.CallDispositionMissed || !fields.Call.Missed ||
		fields.Call.DurationSeconds != nil {
		t.Fatalf("transcript missed call fields = %+v", fields)
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

func assertEngineLocator(t *testing.T, root string, locator *parser.Locator, want []byte) {
	t.Helper()
	if locator.Type != parser.LocatorWholeObject || locator.ObjectRef.StorageClass != "filesystem" {
		t.Fatalf("locator=%+v", locator)
	}
	parsed, err := url.Parse(locator.ObjectRef.URI)
	if err != nil || parsed.Scheme != "file" {
		t.Fatalf("invalid filesystem URI %q: %v", locator.ObjectRef.URI, err)
	}
	objectPath := filepath.FromSlash(parsed.Path)
	if filepath.VolumeName(root) != "" && strings.HasPrefix(objectPath, string(filepath.Separator)) {
		objectPath = strings.TrimPrefix(objectPath, string(filepath.Separator))
	}
	relative, err := filepath.Rel(root, objectPath)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
		t.Fatalf("locator escaped immutable root: %q (%v)", locator.ObjectRef.URI, err)
	}
	data, err := os.ReadFile(objectPath)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(data, want) || locator.ObjectRef.ContentHash != sha256String(want) {
		t.Fatalf("locator bytes/hash mismatch: locator=%+v bytes=%q want=%q", locator, data, want)
	}
}

func sha256String(data []byte) string {
	digest := sha256.Sum256(data)
	return hex.EncodeToString(digest[:])
}

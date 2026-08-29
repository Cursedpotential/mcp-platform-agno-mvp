package postgres

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
)

func TestOpenBytesUsesStoredAndInlineBytes(t *testing.T) {
	for name, tc := range map[string]struct {
		storage string
		stored  []byte
		inline  []byte
		want    string
	}{
		"stored": {storage: "", stored: []byte("stored bytes"), want: "stored bytes"},
		"inline": {storage: "inline", inline: []byte("inline bytes"), want: "inline bytes"},
	} {
		t.Run(name, func(t *testing.T) {
			reader, err := openBytes(context.Background(), nil, tc.storage, "", tc.stored, tc.inline, 0, 0)
			if err != nil {
				t.Fatal(err)
			}
			defer reader.Close()
			got, err := io.ReadAll(reader)
			if err != nil {
				t.Fatal(err)
			}
			if string(got) != tc.want {
				t.Fatalf("bytes = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestOpenBytesStreamsExactExternalRange(t *testing.T) {
	closed := false
	reader, err := openBytes(context.Background(), func(context.Context, string) (io.ReadCloser, error) {
		return closeTrackingReader{Reader: bytes.NewBufferString("0123456789"), close: func() { closed = true }}, nil
	}, "filesystem", "file:///immutable", nil, nil, 3, 4)
	if err != nil {
		t.Fatal(err)
	}
	got, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "3456" {
		t.Fatalf("range = %q, want 3456", got)
	}
	if err := reader.Close(); err != nil {
		t.Fatal(err)
	}
	if !closed {
		t.Fatal("external object closer was not called")
	}
}

func TestOpenBytesRejectsTruncatedExternalRange(t *testing.T) {
	reader, err := openBytes(context.Background(), func(context.Context, string) (io.ReadCloser, error) {
		return io.NopCloser(bytes.NewBufferString("short")), nil
	}, "filesystem", "file:///immutable", nil, nil, 3, 4)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	_, err = io.ReadAll(reader)
	if !errors.Is(err, io.ErrUnexpectedEOF) {
		t.Fatalf("truncated range error = %v, want %v", err, io.ErrUnexpectedEOF)
	}
}

type closeTrackingReader struct {
	io.Reader
	close func()
}

func (r closeTrackingReader) Close() error {
	r.close()
	return nil
}

func TestValidateSpecPinsEachStageToItsHashKind(t *testing.T) {
	valid := []struct {
		stage stagegraph.StageID
		kind  activities.HashKind
	}{
		{stagegraph.HashSource, activities.HashKindH1Source},
		{stagegraph.HashRawRecords, activities.HashKindRawRecordDigest},
		{stagegraph.HashRawGeneration, activities.HashKindH3RawGeneration},
		{stagegraph.HashNormalizedRecords, activities.HashKindNormalizedRecordDigest},
		{stagegraph.HashNormalizedGeneration, activities.HashKindNormalizedGenerationDigest},
	}
	for _, tc := range valid {
		if err := validateSpec(activities.BatchSpec{RequestID: "req", Attempt: 1, Stage: tc.stage, Kind: tc.kind, SubjectRef: uiw.Ref("subject")}); err != nil {
			t.Errorf("%s/%s rejected: %v", tc.stage, tc.kind, err)
		}
	}
	if err := validateSpec(activities.BatchSpec{RequestID: "req", Attempt: 1, Stage: stagegraph.HashSource, Kind: activities.HashKindH3RawGeneration, SubjectRef: "subject"}); err == nil {
		t.Fatal("mismatched stage and kind accepted")
	}
}

func TestValidateMemberCanonRejectsCrossLayerCanons(t *testing.T) {
	if err := validateMemberCanon(activities.HashKindRawRecordDigest, activities.CanonNormalizedRecord); err == nil {
		t.Fatal("normalized canon accepted for raw member")
	}
	if err := validateMemberCanon(activities.HashKindNormalizedRecordDigest, "h2-rawrecord-v1"); err == nil {
		t.Fatal("raw canon accepted for normalized member")
	}
	if err := validateMemberCanon(activities.HashKindH3RawGeneration, activities.CanonRawSpan); err != nil {
		t.Fatal(err)
	}
}

func TestParseSetRefRequiresExplicitKindPrefix(t *testing.T) {
	const id = "00000000-0000-0000-0000-000000000001"
	kind, gotID, err := parseSetRef("raw_hash_receipt_set:" + id)
	if err != nil || kind != "raw_hash_receipt_set" || gotID != id {
		t.Fatalf("parsed set ref = %q/%q/%v", kind, gotID, err)
	}
	if _, _, err := parseSetRef(id); err == nil {
		t.Fatal("unprefixed set ref accepted")
	}
}

func TestResultReferenceUsesReceiptOrGenerationSetBinding(t *testing.T) {
	hashID := "00000000-0000-0000-0000-000000000001"
	for _, tc := range []struct {
		name, wantKind, wantRef string
		kind                    activities.HashKind
	}{
		{name: "h1", kind: activities.HashKindH1Source, wantKind: "hash_receipt", wantRef: hashID},
		{name: "h3", kind: activities.HashKindH3RawGeneration, wantKind: "hash_receipt", wantRef: hashID},
		{name: "normalized-generation", kind: activities.HashKindNormalizedGenerationDigest, wantKind: "hash_receipt", wantRef: hashID},
		{name: "raw-set", kind: activities.HashKindRawRecordDigest, wantKind: "raw_hash_receipt_set", wantRef: "raw-generation"},
		{name: "normalized-set", kind: activities.HashKindNormalizedRecordDigest, wantKind: "normalized_hash_receipt_set", wantRef: "normalized-generation"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			w := batchWriter{spec: activities.BatchSpec{Kind: tc.kind, SubjectRef: uiw.Ref(tc.wantRef)}, batchID: uuid.MustParse("00000000-0000-0000-0000-000000000002")}
			result, refKind, refID := w.resultReference(uuid.MustParse(hashID))
			if refKind != tc.wantKind || refID != tc.wantRef {
				t.Fatalf("reference kind/id = %q/%q, want %q/%q", refKind, refID, tc.wantKind, tc.wantRef)
			}
			if tc.wantKind == "hash_receipt" && tc.kind == activities.HashKindH3RawGeneration && result == "" {
				t.Fatal("generation result ref is empty")
			}
		})
	}
}

func TestOpenRawRecordsInlineSliceUsesSafeIntegerArguments(t *testing.T) {
	source, err := os.ReadFile(filepath.Join("hash_repository.go"))
	if err != nil {
		t.Fatal(err)
	}
	query := string(source)
	for _, marker := range []string{
		"(raw.byte_offset + 1)::int4",
		"raw.byte_length::int4",
		"raw.byte_offset >= 0",
		"raw.byte_offset <= 2147483646",
		"raw.byte_length >= 0",
		"raw.byte_length <= 2147483647",
		"raw.byte_offset + raw.byte_length <= octet_length(object.inline_bytes)",
	} {
		if !strings.Contains(query, marker) {
			t.Errorf("OpenRawRecords query is missing safe inline-slice marker %q", marker)
		}
	}
	for _, forbidden := range []string{
		"FROM raw.byte_offset + 1 FOR raw.byte_length",
	} {
		if strings.Contains(query, forbidden) {
			t.Errorf("OpenRawRecords query still contains the unsafe bigint substring form %q", forbidden)
		}
	}
}

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

	"github.com/Cursedpotential/probata/engine/activities"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
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
		{stagegraph.FingerprintSource, activities.HashKindContextSourceFingerprint},
		{stagegraph.FingerprintRawRecords, activities.HashKindContextRawRecordFingerprint},
		{stagegraph.FingerprintRawGeneration, activities.HashKindContextRawGenerationFingerprint},
		{stagegraph.StageID("hash_source_activity"), activities.HashKindContextSourceFingerprint},
		{stagegraph.StageID("hash_raw_records_activity"), activities.HashKindContextRawRecordFingerprint},
		{stagegraph.StageID("hash_raw_generation_activity"), activities.HashKindContextRawGenerationFingerprint},
		{stagegraph.HashNormalizedRecords, activities.HashKindNormalizedRecordDigest},
		{stagegraph.HashNormalizedGeneration, activities.HashKindNormalizedGenerationDigest},
	}
	for _, tc := range valid {
		if err := validateSpec(activities.BatchSpec{RequestID: "req", Attempt: 1, Stage: tc.stage, Kind: tc.kind, SubjectRef: proffer.Ref("subject")}); err != nil {
			t.Errorf("%s/%s rejected: %v", tc.stage, tc.kind, err)
		}
	}
	if err := validateSpec(activities.BatchSpec{RequestID: "req", Attempt: 1, Stage: stagegraph.FingerprintSource, Kind: activities.HashKindContextRawGenerationFingerprint, SubjectRef: "subject"}); err == nil {
		t.Fatal("mismatched stage and kind accepted")
	}
}

func TestValidateMemberCanonRejectsCrossLayerCanons(t *testing.T) {
	if err := validateMemberCanon(activities.HashKindContextRawRecordFingerprint, activities.CanonNormalizedRecord); err == nil {
		t.Fatal("normalized canon accepted for raw member")
	}
	if err := validateMemberCanon(activities.HashKindNormalizedRecordDigest, "h2-rawrecord-v1"); err == nil {
		t.Fatal("raw canon accepted for normalized member")
	}
	if err := validateMemberCanon(activities.HashKindContextRawGenerationFingerprint, activities.CanonContextRawSpanFingerprint); err != nil {
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

func TestParseSetRefAcceptsCanonicalContextFingerprintSet(t *testing.T) {
	id := "00000000-0000-0000-0000-000000000001"
	kind, gotID, err := parseSetRef(proffer.Ref("context_raw_fingerprint_receipt_set:" + id))
	if err != nil || kind != "context_raw_fingerprint_receipt_set" || gotID != id {
		t.Fatalf("parseSetRef canonical context set = %q, %q, %v", kind, gotID, err)
	}
}

func TestResultReferenceUsesReceiptOrGenerationSetBinding(t *testing.T) {
	hashID := "00000000-0000-0000-0000-000000000001"
	for _, tc := range []struct {
		name, wantKind, wantRef string
		kind                    activities.HashKind
	}{
		{name: "context-source-fingerprint", kind: activities.HashKindContextSourceFingerprint, wantKind: "hash_receipt", wantRef: hashID},
		{name: "context-raw-generation-fingerprint", kind: activities.HashKindContextRawGenerationFingerprint, wantKind: "hash_receipt", wantRef: hashID},
		{name: "normalized-generation", kind: activities.HashKindNormalizedGenerationDigest, wantKind: "hash_receipt", wantRef: hashID},
		{name: "context-raw-set", kind: activities.HashKindContextRawRecordFingerprint, wantKind: "context_raw_fingerprint_receipt_set", wantRef: "raw-generation"},
		{name: "normalized-set", kind: activities.HashKindNormalizedRecordDigest, wantKind: "normalized_hash_receipt_set", wantRef: "normalized-generation"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			w := batchWriter{spec: activities.BatchSpec{Kind: tc.kind, SubjectRef: proffer.Ref(tc.wantRef)}, batchID: uuid.MustParse("00000000-0000-0000-0000-000000000002")}
			result, refKind, refID := w.resultReference(uuid.MustParse(hashID))
			if refKind != tc.wantKind || refID != tc.wantRef {
				t.Fatalf("reference kind/id = %q/%q, want %q/%q", refKind, refID, tc.wantKind, tc.wantRef)
			}
			if tc.wantKind == "hash_receipt" && tc.kind == activities.HashKindContextRawGenerationFingerprint && result == "" {
				t.Fatal("generation result ref is empty")
			}
		})
	}
}

func TestLegacyRawRetryKeepsLegacyReceiptSetReference(t *testing.T) {
	w := batchWriter{spec: activities.BatchSpec{
		Stage: stagegraph.StageID("hash_raw_records_activity"), Kind: activities.HashKindContextRawRecordFingerprint,
		SubjectRef: "raw-generation",
	}}
	result, kind, refID := w.resultReference(uuid.MustParse("00000000-0000-0000-0000-000000000001"))
	if result != "raw_hash_receipt_set:raw-generation" || kind != "raw_hash_receipt_set" || refID != "raw-generation" {
		t.Fatalf("legacy result reference = %q/%q/%q", result, kind, refID)
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

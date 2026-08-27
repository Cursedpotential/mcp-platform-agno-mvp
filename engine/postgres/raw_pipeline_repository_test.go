package postgres

import (
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/lowcarbdev/sbv/pkg/custodyhash"
)

func TestNewRawPipelineRepositoryRequiresDatabase(t *testing.T) {
	if _, err := NewRawPipelineRepository(nil, nil); err == nil {
		t.Fatal("nil database accepted")
	}
	repo, err := NewRawPipelineRepository(testDB{}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if repo == nil {
		t.Fatal("expected non-nil repository")
	}
}

func TestRawGenerationResultRoundTrip(t *testing.T) {
	result := rawGenerationResult{
		RefKind: "raw_generation", RefID: "00000000-0000-0000-0000-000000000001",
		Emitted: 3, Rejected: 1, Malformed: 2, Unknown: 4, Unparsed: 5, Attachments: 6, Total: 21,
	}
	encoded, err := encodeJSON(result)
	if err != nil {
		t.Fatal(err)
	}
	decoded, err := decodeRawGenerationResult(encoded)
	if err != nil {
		t.Fatal(err)
	}
	if decoded != result {
		t.Fatalf("decoded = %+v, want %+v", decoded, result)
	}
	want := parser.BundleAccounting{Emitted: 3, Rejected: 1, Malformed: 2, Unknown: 4, Unparsed: 5, Attachments: 6}
	if decoded.BundleAccounting() != want {
		t.Fatalf("bundle accounting = %+v, want %+v", decoded.BundleAccounting(), want)
	}
}

func TestDecodeRawGenerationResultRejectsMutableOrMismatchedReference(t *testing.T) {
	for name, raw := range map[string]string{
		"wrong kind": `{"ref_kind":"raw_bundle","ref_id":"00000000-0000-0000-0000-000000000001"}`,
		"empty id":   `{"ref_kind":"raw_generation","ref_id":""}`,
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := decodeRawGenerationResult([]byte(raw)); err == nil {
				t.Fatal("invalid raw generation result accepted")
			}
		})
	}
}

func TestValidateRawGenerationSpec(t *testing.T) {
	valid := activities.RawGenerationSpec{
		RequestID: "r", SourceVersionRef: "s", DeclaredFormat: "sms_xml_backup",
		ParserID: "p", ParserVersion: "1", BundleRef: "b", Attempt: 1,
	}
	if err := validateRawGenerationSpec(valid); err != nil {
		t.Fatal(err)
	}
	for name, invalid := range map[string]activities.RawGenerationSpec{
		"missing request": {SourceVersionRef: "s", DeclaredFormat: "f", ParserID: "p", ParserVersion: "1", BundleRef: "b", Attempt: 1},
		"missing source":  {RequestID: "r", DeclaredFormat: "f", ParserID: "p", ParserVersion: "1", BundleRef: "b", Attempt: 1},
		"missing bundle":  {RequestID: "r", SourceVersionRef: "s", DeclaredFormat: "f", ParserID: "p", ParserVersion: "1", Attempt: 1},
		"missing format":  {RequestID: "r", SourceVersionRef: "s", ParserID: "p", ParserVersion: "1", BundleRef: "b", Attempt: 1},
		"missing parser":  {RequestID: "r", SourceVersionRef: "s", DeclaredFormat: "f", ParserVersion: "1", BundleRef: "b", Attempt: 1},
		"zero attempt":    {RequestID: "r", SourceVersionRef: "s", DeclaredFormat: "f", ParserID: "p", ParserVersion: "1", BundleRef: "b"},
	} {
		t.Run(name, func(t *testing.T) {
			if err := validateRawGenerationSpec(invalid); err == nil {
				t.Fatal("invalid raw generation spec accepted")
			}
		})
	}
}

func TestValidateChainSpecAndVerificationSpec(t *testing.T) {
	if err := validateChainSpec(activities.RawGenerationChainSpec{RequestID: "r", SourceVersionRef: "s", RawGenerationChainRef: "c", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validateChainSpec(activities.RawGenerationChainSpec{}); err == nil {
		t.Fatal("empty chain spec accepted")
	}
	valid := activities.RawSourceVerificationSpec{
		RequestID: "r", SourceVersionRef: "s", AccountingRef: "a", CoverageRef: "c", H1Ref: "h", RawGenerationChainRef: "g", Attempt: 1,
	}
	if err := validateVerificationSpec(valid); err != nil {
		t.Fatal(err)
	}
	for name, invalid := range map[string]activities.RawSourceVerificationSpec{
		"missing accounting": {RequestID: "r", SourceVersionRef: "s", CoverageRef: "c", H1Ref: "h", RawGenerationChainRef: "g", Attempt: 1},
		"missing coverage":   {RequestID: "r", SourceVersionRef: "s", AccountingRef: "a", H1Ref: "h", RawGenerationChainRef: "g", Attempt: 1},
		"missing h1":         {RequestID: "r", SourceVersionRef: "s", AccountingRef: "a", CoverageRef: "c", RawGenerationChainRef: "g", Attempt: 1},
		"missing chain":      {RequestID: "r", SourceVersionRef: "s", AccountingRef: "a", CoverageRef: "c", H1Ref: "h", Attempt: 1},
		"zero attempt":       {RequestID: "r", SourceVersionRef: "s", AccountingRef: "a", CoverageRef: "c", H1Ref: "h", RawGenerationChainRef: "g"},
	} {
		t.Run(name, func(t *testing.T) {
			if err := validateVerificationSpec(invalid); err == nil {
				t.Fatal("invalid verification spec accepted")
			}
		})
	}
}

func TestRawGenerationKeyReconcileKeyVerifyKeyAreDeterministicAndDistinct(t *testing.T) {
	genSpec := activities.RawGenerationSpec{RequestID: "r", SourceVersionRef: "s", BundleRef: "b"}
	if rawGenerationKey(genSpec) != rawGenerationKey(genSpec) {
		t.Fatal("raw generation key is not deterministic")
	}
	chainSpec := activities.RawGenerationChainSpec{RequestID: "r", RawGenerationChainRef: "c"}
	accountingKey := reconcileKey(stagegraph.ReconcileRecordAccounting, chainSpec)
	coverageKey := reconcileKey(stagegraph.ReconcileByteCoverage, chainSpec)
	if accountingKey == coverageKey {
		t.Fatal("accounting and coverage keys collide across stages")
	}
	if accountingKey != reconcileKey(stagegraph.ReconcileRecordAccounting, chainSpec) {
		t.Fatal("reconcile key is not deterministic")
	}
	verifySpec := activities.RawSourceVerificationSpec{RequestID: "r", AccountingRef: "a", CoverageRef: "c", H1Ref: "h", RawGenerationChainRef: "g"}
	if verifyKey(verifySpec) != verifyKey(verifySpec) {
		t.Fatal("verify key is not deterministic")
	}
	if verifyKey(verifySpec) == accountingKey {
		t.Fatal("verify key collides with a reconcile key")
	}
}

func TestRawHashConstruction(t *testing.T) {
	for status, want := range map[parser.RecordStatus]string{
		parser.StatusEnvelope:  activities.CanonRawSpan,
		parser.StatusUnparsed:  activities.CanonRawSpan,
		parser.StatusParsed:    custodyhash.CanonH2Record,
		parser.StatusRejected:  custodyhash.CanonH2Record,
		parser.StatusMalformed: custodyhash.CanonH2Record,
		parser.StatusUnknown:   custodyhash.CanonH2Record,
	} {
		if got := rawHashConstruction(status); got != want {
			t.Errorf("rawHashConstruction(%s) = %q, want %q", status, got, want)
		}
	}
}

func TestAttachmentsMetadataJSON(t *testing.T) {
	empty, err := attachmentsMetadataJSON(nil)
	if err != nil {
		t.Fatal(err)
	}
	if string(empty) != "{}" {
		t.Fatalf("empty attachments metadata = %s, want {}", empty)
	}
	encoded, err := attachmentsMetadataJSON([]parser.AttachmentRef{
		{
			AttachmentOrdinal: 1,
			Locator: parser.Locator{
				Type:      parser.LocatorByteRange,
				ObjectRef: parser.ObjectRef{StorageClass: "filesystem", URI: "file:///a"},
				ByteRange: &parser.ByteRange{Offset: 10, Length: 5},
			},
			NativeMetadata: []byte(`{"a":1}`),
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if string(encoded) == "{}" {
		t.Fatal("non-empty attachments produced empty metadata")
	}
}

func TestAttachmentsMetadataJSONRejectsInvalidNativeMetadata(t *testing.T) {
	_, err := attachmentsMetadataJSON([]parser.AttachmentRef{
		{
			AttachmentOrdinal: 1,
			Locator:           parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{StorageClass: "filesystem", URI: "file:///a"}},
			NativeMetadata:    []byte(`not json`),
		},
	})
	if err == nil {
		t.Fatal("invalid attachment native metadata accepted")
	}
}

func TestCompareAccounting(t *testing.T) {
	expected := rawGenerationResult{Emitted: 2, Rejected: 1, Malformed: 0, Unknown: 0, Unparsed: 0, Attachments: 0, Total: 3}
	matching := observedRawCounts{Emitted: 2, Rejected: 1, Total: 3, MinOrdinal: 0, MaxOrdinal: 2, DistinctOrdinals: 3}
	if discrepancies := compareAccounting(expected, matching); len(discrepancies) != 0 {
		t.Fatalf("matching accounting produced discrepancies: %+v", discrepancies)
	}
	mismatched := observedRawCounts{Emitted: 1, Rejected: 1, Total: 2, MinOrdinal: 0, MaxOrdinal: 1, DistinctOrdinals: 2}
	discrepancies := compareAccounting(expected, mismatched)
	if len(discrepancies) == 0 {
		t.Fatal("mismatched accounting produced no discrepancies")
	}
	for _, d := range discrepancies {
		if d.Explanation == "" {
			t.Fatalf("discrepancy %+v lacks an explanation", d)
		}
	}
	nonContiguous := observedRawCounts{Emitted: 2, Rejected: 1, Total: 3, MinOrdinal: 0, MaxOrdinal: 5, DistinctOrdinals: 3}
	if discrepancies := compareAccounting(expected, nonContiguous); len(discrepancies) == 0 {
		t.Fatal("non-contiguous ordinals produced no discrepancy")
	}
}

func TestObservedRawCountsContiguous(t *testing.T) {
	if !(observedRawCounts{Total: 3, MinOrdinal: 0, MaxOrdinal: 2, DistinctOrdinals: 3}).contiguous() {
		t.Fatal("contiguous zero-based sequence rejected")
	}
	if (observedRawCounts{Total: 0}).contiguous() {
		t.Fatal("zero total accepted as contiguous")
	}
	if (observedRawCounts{Total: 3, MinOrdinal: 1, MaxOrdinal: 3, DistinctOrdinals: 3}).contiguous() {
		t.Fatal("non-zero-based sequence accepted as contiguous")
	}
	if (observedRawCounts{Total: 3, MinOrdinal: 0, MaxOrdinal: 2, DistinctOrdinals: 2}).contiguous() {
		t.Fatal("duplicate ordinals accepted as contiguous")
	}
}

func TestMergeAndGapRangesExactCoverageHasNoGaps(t *testing.T) {
	covered, gaps := mergeAndGapRanges([]byteRange{{Offset: 0, Length: 5}, {Offset: 5, Length: 5}}, 10)
	if covered != 10 {
		t.Fatalf("covered = %d, want 10", covered)
	}
	if len(gaps) != 0 {
		t.Fatalf("gaps = %+v, want none", gaps)
	}
}

func TestMergeAndGapRangesReportsMiddleGap(t *testing.T) {
	covered, gaps := mergeAndGapRanges([]byteRange{{Offset: 0, Length: 3}, {Offset: 7, Length: 3}}, 10)
	if covered != 6 {
		t.Fatalf("covered = %d, want 6", covered)
	}
	if len(gaps) != 1 || gaps[0] != (gapRange{Offset: 3, Length: 4}) {
		t.Fatalf("gaps = %+v, want [{3 4}]", gaps)
	}
}

func TestMergeAndGapRangesReportsTrailingGap(t *testing.T) {
	covered, gaps := mergeAndGapRanges([]byteRange{{Offset: 0, Length: 4}}, 10)
	if covered != 4 {
		t.Fatalf("covered = %d, want 4", covered)
	}
	if len(gaps) != 1 || gaps[0] != (gapRange{Offset: 4, Length: 6}) {
		t.Fatalf("gaps = %+v, want [{4 6}]", gaps)
	}
}

func TestMergeAndGapRangesMergesOverlappingRanges(t *testing.T) {
	covered, gaps := mergeAndGapRanges([]byteRange{{Offset: 0, Length: 6}, {Offset: 4, Length: 6}}, 10)
	if covered != 10 {
		t.Fatalf("covered = %d, want 10", covered)
	}
	if len(gaps) != 0 {
		t.Fatalf("gaps = %+v, want none", gaps)
	}
}

func TestMergeAndGapRangesHandlesUnsortedInput(t *testing.T) {
	covered, gaps := mergeAndGapRanges([]byteRange{{Offset: 7, Length: 3}, {Offset: 0, Length: 3}}, 10)
	if covered != 6 {
		t.Fatalf("covered = %d, want 6", covered)
	}
	if len(gaps) != 1 || gaps[0] != (gapRange{Offset: 3, Length: 4}) {
		t.Fatalf("gaps = %+v, want [{3 4}]", gaps)
	}
}

func TestMergeAndGapRangesIgnoresZeroLengthRanges(t *testing.T) {
	covered, gaps := mergeAndGapRanges([]byteRange{{Offset: 0, Length: 0}, {Offset: 0, Length: 10}}, 10)
	if covered != 10 || len(gaps) != 0 {
		t.Fatalf("covered = %d, gaps = %+v", covered, gaps)
	}
}

func TestCheckedLocatorRange(t *testing.T) {
	t.Run("whole object", func(t *testing.T) {
		offset, length, err := checkedLocatorRange(nil, 10)
		if err != nil || offset != 0 || length != 10 {
			t.Fatalf("offset=%d length=%d err=%v", offset, length, err)
		}
	})
	t.Run("bounded member", func(t *testing.T) {
		offset, length, err := checkedLocatorRange(&parser.ByteRange{Offset: 3, Length: 7}, 10)
		if err != nil || offset != 3 || length != 7 {
			t.Fatalf("offset=%d length=%d err=%v", offset, length, err)
		}
	})
	for name, bounds := range map[string]parser.ByteRange{
		"past object":     {Offset: 9, Length: 2},
		"offset overflow": {Offset: uint64(1) << 63, Length: 0},
		"length overflow": {Offset: 0, Length: uint64(1) << 63},
	} {
		t.Run(name, func(t *testing.T) {
			if _, _, err := checkedLocatorRange(&bounds, 10); err == nil {
				t.Fatal("invalid locator range accepted")
			}
		})
	}
}

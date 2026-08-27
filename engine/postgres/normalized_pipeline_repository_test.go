package postgres

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/normalize"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
)

func fakeNormalizedBundleWriterFactory(context.Context, uiw.StageRequest, normalize.NormalizerInput) (normalize.BundleWriter, error) {
	return nil, errors.New("not implemented")
}
func fakeNormalizedBundleReaderFactory(context.Context, uiw.Ref) (NormalizedBundleReader, error) {
	return nil, errors.New("not implemented")
}

func TestNewNormalizedPipelineRepositoryRequiresDatabaseAndFactories(t *testing.T) {
	if _, err := NewNormalizedPipelineRepository(nil, fakeNormalizedBundleWriterFactory, fakeNormalizedBundleReaderFactory); err == nil {
		t.Fatal("nil database accepted")
	}
	if _, err := NewNormalizedPipelineRepository(testDB{}, nil, fakeNormalizedBundleReaderFactory); err == nil {
		t.Fatal("nil writer factory accepted")
	}
	if _, err := NewNormalizedPipelineRepository(testDB{}, fakeNormalizedBundleWriterFactory, nil); err == nil {
		t.Fatal("nil reader factory accepted")
	}
	repo, err := NewNormalizedPipelineRepository(testDB{}, fakeNormalizedBundleWriterFactory, fakeNormalizedBundleReaderFactory)
	if err != nil {
		t.Fatal(err)
	}
	var _ activities.NormalizedPipelineStore = repo
}

func TestValidateNormalizedPipelineSpecs(t *testing.T) {
	if err := validateNormalizeExecutionSpec(activities.NormalizeExecutionSpec{
		RequestID: "r", SourceVersionRef: "s", RawGenerationRef: "g", NormalizerID: "n", NormalizerVersion: "1", BundleRef: "b", Attempt: 1,
	}); err != nil {
		t.Fatal(err)
	}
	for _, invalid := range []activities.NormalizeExecutionSpec{
		{SourceVersionRef: "s", RawGenerationRef: "g", NormalizerID: "n", NormalizerVersion: "1", BundleRef: "b", Attempt: 1},
		{RequestID: "r", RawGenerationRef: "g", NormalizerID: "n", NormalizerVersion: "1", BundleRef: "b", Attempt: 1},
		{RequestID: "r", SourceVersionRef: "s", NormalizerID: "n", NormalizerVersion: "1", BundleRef: "b", Attempt: 1},
		{RequestID: "r", SourceVersionRef: "s", RawGenerationRef: "g", NormalizerVersion: "1", BundleRef: "b", Attempt: 1},
		{RequestID: "r", SourceVersionRef: "s", RawGenerationRef: "g", NormalizerID: "n", BundleRef: "b", Attempt: 1},
		{RequestID: "r", SourceVersionRef: "s", RawGenerationRef: "g", NormalizerID: "n", NormalizerVersion: "1", Attempt: 1},
		{RequestID: "r", SourceVersionRef: "s", RawGenerationRef: "g", NormalizerID: "n", NormalizerVersion: "1", BundleRef: "b", Attempt: 0},
	} {
		if err := validateNormalizeExecutionSpec(invalid); err == nil {
			t.Fatalf("invalid normalize execution spec accepted: %+v", invalid)
		}
	}

	if err := validatePersistNormalizedGenerationSpec(activities.PersistNormalizedGenerationSpec{RequestID: "r", SourceVersionRef: "s", BundleRef: "b", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validatePersistNormalizedGenerationSpec(activities.PersistNormalizedGenerationSpec{RequestID: "r", SourceVersionRef: "s", Attempt: 1}); err == nil {
		t.Fatal("missing bundle ref accepted")
	}

	if err := validatePersistLineageSpec(activities.PersistLineageSpec{RequestID: "r", SourceVersionRef: "s", NormalizedGenerationRef: "n", RawGenerationRef: "g", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validatePersistLineageSpec(activities.PersistLineageSpec{RequestID: "r", SourceVersionRef: "s", NormalizedGenerationRef: "n", Attempt: 1}); err == nil {
		t.Fatal("missing raw generation ref accepted")
	}

	if err := validateValidateRawLineageSpec(activities.ValidateRawLineageSpec{RequestID: "r", SourceVersionRef: "s", LineageSetRef: "l", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validateValidateRawLineageSpec(activities.ValidateRawLineageSpec{RequestID: "r", SourceVersionRef: "s", Attempt: 1}); err == nil {
		t.Fatal("missing lineage set ref accepted")
	}

	if err := validateVerifyNormalizedGenerationSpec(activities.VerifyNormalizedGenerationSpec{
		RequestID: "r", SourceVersionRef: "s", LineageValidationRef: "l", ManifestDigestRef: "m",
		RecomputedDigest: "d", RecomputedConstruction: "c", RecomputedMemberCount: 1, Attempt: 1,
	}); err != nil {
		t.Fatal(err)
	}
	if err := validateVerifyNormalizedGenerationSpec(activities.VerifyNormalizedGenerationSpec{
		RequestID: "r", SourceVersionRef: "s", LineageValidationRef: "l", ManifestDigestRef: "m", Attempt: 1,
	}); err == nil {
		t.Fatal("missing recomputed digest accepted")
	}

	if err := validateSealGenerationSpec(activities.SealGenerationSpec{RequestID: "r", SourceVersionRef: "s", VerificationRef: "v", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validateSealGenerationSpec(activities.SealGenerationSpec{RequestID: "r", SourceVersionRef: "s", Attempt: 1}); err == nil {
		t.Fatal("missing verification ref accepted")
	}

	if err := validatePublishGenerationSpec(activities.PublishGenerationSpec{RequestID: "r", SourceVersionRef: "s", SealedGenerationRef: "g", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validatePublishGenerationSpec(activities.PublishGenerationSpec{RequestID: "r", SourceVersionRef: "s", Attempt: 1}); err == nil {
		t.Fatal("missing sealed generation ref accepted")
	}
}

func TestNormalizedPipelineKeysAreDeterministicAndDistinct(t *testing.T) {
	execSpec := activities.NormalizeExecutionSpec{RequestID: "r", SourceVersionRef: "s", RawGenerationRef: "g"}
	if normalizeExecutionKey(execSpec) != normalizeExecutionKey(execSpec) {
		t.Fatal("normalize execution key is not deterministic")
	}
	genSpec := activities.PersistNormalizedGenerationSpec{RequestID: "r", SourceVersionRef: "s", BundleRef: "b"}
	lineageSpec := activities.PersistLineageSpec{RequestID: "r", NormalizedGenerationRef: "n", RawGenerationRef: "g"}
	validateSpec := activities.ValidateRawLineageSpec{RequestID: "r", LineageSetRef: "l"}
	verifySpec := activities.VerifyNormalizedGenerationSpec{RequestID: "r", LineageValidationRef: "l", ManifestDigestRef: "m"}
	sealSpec := activities.SealGenerationSpec{RequestID: "r", VerificationRef: "v"}
	publishSpec := activities.PublishGenerationSpec{RequestID: "r", SealedGenerationRef: "g"}

	keys := map[string]string{
		"normalize":  normalizeExecutionKey(execSpec),
		"persistGen": persistNormalizedGenerationKey(genSpec),
		"lineage":    persistLineageKey(lineageSpec),
		"validate":   validateRawLineageKey(validateSpec),
		"verify":     verifyNormalizedGenerationKey(verifySpec),
		"seal":       sealGenerationKey(sealSpec),
		"publish":    publishGenerationKey(publishSpec),
	}
	seen := make(map[string]string, len(keys))
	for name, key := range keys {
		if other, exists := seen[key]; exists {
			t.Fatalf("keys for %q and %q collide: %q", name, other, key)
		}
		seen[key] = name
	}
}

func TestNormalizedRefJSONRoundTrips(t *testing.T) {
	encoded := normalizedRefJSON("normalized_generation", "abc-123")
	kind, id, err := decodeNormalizedRef(encoded)
	if err != nil {
		t.Fatal(err)
	}
	if kind != "normalized_generation" || id != "abc-123" {
		t.Fatalf("kind=%q id=%q", kind, id)
	}
	if _, _, err := decodeNormalizedRef([]byte(`{"ref_kind":"","ref_id":""}`)); err == nil {
		t.Fatal("empty ref accepted")
	}
	if _, _, err := decodeNormalizedRef([]byte(`not json`)); err == nil {
		t.Fatal("invalid json accepted")
	}
}

func TestParseLineageSetRef(t *testing.T) {
	id := uuid.New()
	got, err := parseLineageSetRef(uiw.Ref(lineageSetPrefix + id.String()))
	if err != nil {
		t.Fatal(err)
	}
	if got != id {
		t.Fatalf("got %s, want %s", got, id)
	}
	if _, err := parseLineageSetRef(uiw.Ref("not-prefixed:" + id.String())); err == nil {
		t.Fatal("unprefixed ref accepted")
	}
	if _, err := parseLineageSetRef(uiw.Ref(lineageSetPrefix + "not-a-uuid")); err == nil {
		t.Fatal("invalid uuid accepted")
	}
}

func TestEmptyIfNilProducesMarshalableEmptySlice(t *testing.T) {
	if got := emptyIfNil(nil); got == nil || len(got) != 0 {
		t.Fatalf("emptyIfNil(nil) = %v", got)
	}
	populated := []map[string]any{{"field": "x"}}
	if got := emptyIfNil(populated); len(got) != 1 {
		t.Fatalf("emptyIfNil(populated) = %v", got)
	}
}

func TestBuildNormalizedPayloadIncludesRequiredContractFields(t *testing.T) {
	recordID := uuid.New()
	record := normalize.RecordEnvelope{
		RecordOrdinal:        0,
		RecordType:           normalize.RecordTypeMessage,
		TimestampGranularity: normalize.GranularityUnknown,
		TimestampCertainty:   normalize.CertaintyUnknown,
		SourceAvailableFrom:  time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		ProvenanceClass:      normalize.ProvenanceFirstPartyAuthored,
		Participants:         []normalize.Participant{{Role: normalize.RoleUnknown, Identifier: "unknown"}},
		Content:              []byte(`{"body":"hi"}`),
		Lineage:              []normalize.LineageEdge{{RawRecordOrdinal: 0, DerivationRole: normalize.DerivationPrimarySource}},
	}
	payload, err := buildNormalizedPayload(recordID, "source-version:1", record)
	if err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{
		`"contract_version"`, `"normalized_record_id"`, `"record_type"`, `"source_version_ref"`,
		`"occurred_at"`, `"timestamp_granularity"`, `"timestamp_certainty"`, `"source_available_from"`,
		`"provenance_class"`, `"participants"`, `"content"`,
	} {
		if !containsString(string(payload), key) {
			t.Fatalf("payload %s missing key %s", payload, key)
		}
	}
}

func containsString(haystack, needle string) bool {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return true
		}
	}
	return false
}

package normalize

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"testing"
	"time"
)

func validRecord() RecordEnvelope {
	return RecordEnvelope{
		RecordOrdinal:        0,
		RecordType:           RecordTypeMessage,
		TimestampGranularity: GranularityUnknown,
		TimestampCertainty:   CertaintyUnknown,
		SourceAvailableFrom:  time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		ProvenanceClass:      ProvenanceFirstPartyAuthored,
		Participants:         []Participant{{Role: RoleUnknown, Identifier: "unknown"}},
		Content:              []byte(`{"body":"hi"}`),
		Lineage:              []LineageEdge{{RawRecordOrdinal: 0, DerivationRole: DerivationPrimarySource}},
	}
}

func TestRecordEnvelopeValidate(t *testing.T) {
	if err := validRecord().Validate(); err != nil {
		t.Fatal(err)
	}

	t.Run("requires lineage", func(t *testing.T) {
		record := validRecord()
		record.Lineage = nil
		if err := record.Validate(); err == nil || !strings.Contains(err.Error(), "lineage") {
			t.Fatalf("error = %v", err)
		}
	})
	t.Run("requires source available from", func(t *testing.T) {
		record := validRecord()
		record.SourceAvailableFrom = time.Time{}
		if err := record.Validate(); err == nil || !strings.Contains(err.Error(), "source_available_from") {
			t.Fatalf("error = %v", err)
		}
	})
	t.Run("unresolved timestamp without raw text requires unknown granularity", func(t *testing.T) {
		record := validRecord()
		record.TimestampGranularity = GranularitySecond
		if err := record.Validate(); err == nil {
			t.Fatal("accepted resolved granularity without occurred_at or raw text")
		}
	})
	t.Run("unresolved timestamp with raw text is fine", func(t *testing.T) {
		record := validRecord()
		record.OccurredAtRaw = "sometime last week"
		if err := record.Validate(); err != nil {
			t.Fatal(err)
		}
	})
	t.Run("content must be a JSON object", func(t *testing.T) {
		record := validRecord()
		record.Content = []byte(`[1,2,3]`)
		if err := record.Validate(); err == nil {
			t.Fatal("accepted non-object content")
		}
	})
	t.Run("invalid participant role rejected", func(t *testing.T) {
		record := validRecord()
		record.Participants = []Participant{{Role: "carrier-pigeon", Identifier: "x"}}
		if err := record.Validate(); err == nil {
			t.Fatal("accepted invalid participant role")
		}
	})
}

type sliceRawRecordSource struct {
	records []RawRecordView
	index   int
}

func (s *sliceRawRecordSource) Next(context.Context) (RawRecordView, error) {
	if s.index >= len(s.records) {
		return RawRecordView{}, io.EOF
	}
	record := s.records[s.index]
	s.index++
	return record, nil
}
func (s *sliceRawRecordSource) Close() error { return nil }

func baseInput(records []RawRecordView) NormalizerInput {
	return NormalizerInput{
		ContractVersion:       ContractVersion,
		SourceVersionRef:      "source-version:1",
		RawGenerationRef:      "raw-generation:1",
		DeclaredFormat:        "generic_chat_export",
		SourceProvenanceClass: ProvenanceFirstPartyAuthored,
		AcquiredAt:            time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		Records:               &sliceRawRecordSource{records: records},
	}
}

type recordingWriter struct {
	beganHeader BundleHeader
	emitted     []RecordEnvelope
	finalized   bool
	aborted     bool
	bundleRef   string
	finalizeErr error
	beginErr    error
}

func (w *recordingWriter) Begin(context.Context, BundleHeader) error {
	if w.beginErr != nil {
		return w.beginErr
	}
	return nil
}
func (w *recordingWriter) Emit(_ context.Context, record RecordEnvelope) error {
	w.emitted = append(w.emitted, record)
	return nil
}
func (w *recordingWriter) Finalize(_ context.Context, _ BundleAccounting) (BundleResult, error) {
	if w.finalizeErr != nil {
		return BundleResult{}, w.finalizeErr
	}
	w.finalized = true
	return BundleResult{BundleRef: w.bundleRef}, nil
}
func (w *recordingWriter) Abort(context.Context) error {
	w.aborted = true
	return nil
}

func TestExecuteHappyPathFinalizesBundle(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{RecordOrdinal: 0, RecordStatus: "parsed", NativeFields: []byte(`{"body":"hi","sender":"a"}`)}})
	result, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer)
	if err != nil {
		t.Fatal(err)
	}
	if result.BundleRef != "bundle:1" {
		t.Fatalf("bundle ref = %q", result.BundleRef)
	}
	if !writer.finalized || writer.aborted {
		t.Fatalf("finalized=%v aborted=%v", writer.finalized, writer.aborted)
	}
	if len(writer.emitted) != 1 {
		t.Fatalf("emitted %d records, want 1", len(writer.emitted))
	}
}

func TestExecuteAbortsOnZeroRecords(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput(nil)
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err == nil || !strings.Contains(err.Error(), "zero records") {
		t.Fatalf("error = %v", err)
	}
	if !writer.aborted || writer.finalized {
		t.Fatalf("finalized=%v aborted=%v", writer.finalized, writer.aborted)
	}
}

type failingAdapter struct{ err error }

func (failingAdapter) Capability() Capability {
	return Capability{ContractVersion: ContractVersion, NormalizerID: "failing", NormalizerVersion: "1.0.0"}
}
func (a failingAdapter) Normalize(context.Context, NormalizerInput, BundleSink) (BundleAccounting, error) {
	return BundleAccounting{}, a.err
}

func TestExecuteAbortsOnAdapterError(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{RecordOrdinal: 0, RecordStatus: "parsed"}})
	sentinel := errors.New("adapter blew up")
	if _, err := Execute(context.Background(), input, failingAdapter{err: sentinel}, writer); err == nil || !errors.Is(err, sentinel) {
		t.Fatalf("error = %v, want wrapped %v", err, sentinel)
	}
	if !writer.aborted || writer.finalized {
		t.Fatalf("finalized=%v aborted=%v", writer.finalized, writer.aborted)
	}
}

func TestExecuteRequiresAdapterAndWriter(t *testing.T) {
	input := baseInput([]RawRecordView{{RecordOrdinal: 0, RecordStatus: "parsed"}})
	if _, err := Execute(context.Background(), input, nil, &recordingWriter{}); err == nil {
		t.Fatal("nil adapter accepted")
	}
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, nil); err == nil {
		t.Fatal("nil writer accepted")
	}
}

func TestGenericMessageNormalizerEmitsOneRecordPerParsedRawRecordInOrder(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{
		{RecordOrdinal: 0, RecordStatus: "parsed", NativeFields: []byte(`{"body":"hello","sender":"alice","recipients":["bob"]}`)},
		{RecordOrdinal: 1, RecordStatus: "rejected", NativeFields: []byte(`{}`)},
		{RecordOrdinal: 2, RecordStatus: "parsed", NativeFields: []byte(`{"unusual_field":"value"}`)},
	})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	if len(writer.emitted) != 2 {
		t.Fatalf("emitted %d records, want 2 (rejected raw record must not become a normalized record)", len(writer.emitted))
	}
	first := writer.emitted[0]
	if first.RecordType != RecordTypeMessage {
		t.Fatalf("first record type = %q, want message", first.RecordType)
	}
	if len(first.Lineage) != 1 || first.Lineage[0].RawRecordOrdinal != 0 {
		t.Fatalf("first lineage = %+v", first.Lineage)
	}
	foundSender, foundRecipient := false, false
	for _, p := range first.Participants {
		if p.Role == RoleSender && p.Identifier == "alice" {
			foundSender = true
		}
		if p.Role == RoleRecipient && p.Identifier == "bob" {
			foundRecipient = true
		}
	}
	if !foundSender || !foundRecipient {
		t.Fatalf("participants = %+v", first.Participants)
	}

	second := writer.emitted[1]
	if second.RecordType != RecordTypeOther {
		t.Fatalf("second record type = %q, want other (no dropped parsed raw record)", second.RecordType)
	}
	if len(second.Lineage) != 1 || second.Lineage[0].RawRecordOrdinal != 2 {
		t.Fatalf("second lineage = %+v, want raw ordinal 2 (the parsed record, skipping the rejected one)", second.Lineage)
	}
	if second.RecordOrdinal != 1 {
		t.Fatalf("second record ordinal = %d, want 1 (contiguous normalized ordinals)", second.RecordOrdinal)
	}
}

func TestGenericMessageNormalizerAcquiredThirdPartyUsesAcquiredAtNotOccurredAt(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{
		{RecordOrdinal: 0, RecordStatus: "parsed", NativeFields: []byte(`{"body":"hi","timestamp":"2020-01-01T00:00:00Z"}`)},
	})
	input.SourceProvenanceClass = ProvenanceAcquiredThirdParty
	input.AcquiredAt = time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	record := writer.emitted[0]
	if !record.SourceAvailableFrom.Equal(input.AcquiredAt) {
		t.Fatalf("source_available_from = %v, want acquired_at %v for acquired_third_party", record.SourceAvailableFrom, input.AcquiredAt)
	}
	if record.OccurredAt == nil || !record.OccurredAt.Equal(time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)) {
		t.Fatalf("occurred_at = %v", record.OccurredAt)
	}
}

func TestGenericMessageNormalizerMapsSBVNativeFields(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{
		RecordOrdinal: 0,
		RecordStatus:  "parsed",
		NativeFields: []byte(
			`{"body":"from sbv","sender":"alice","recipients":["bob"],"occurred_at":"2024-03-02T01:02:03Z"}`,
		),
		NativeMetadata: []byte(`{"sbv_kind":"message","sbv_source_pos":"conversation/1"}`),
	}})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	if len(writer.emitted) != 1 {
		t.Fatalf("emitted %d records, want 1", len(writer.emitted))
	}
	record := writer.emitted[0]
	if record.RecordType != RecordTypeMessage || string(record.Content) != `{"body":"from sbv"}` {
		t.Fatalf("record type/content = %q %s", record.RecordType, record.Content)
	}
	if record.OccurredAt == nil || !record.OccurredAt.Equal(time.Date(2024, 3, 2, 1, 2, 3, 0, time.UTC)) {
		t.Fatalf("occurred_at = %v", record.OccurredAt)
	}
	if !hasParticipant(record.Participants, RoleSender, "alice") || !hasParticipant(record.Participants, RoleRecipient, "bob") {
		t.Fatalf("participants = %+v", record.Participants)
	}
}

func TestGenericMessageNormalizerPreservesTypedMissedCallSemantics(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{
		RecordOrdinal: 0,
		RecordStatus:  "parsed",
		NativeFields: []byte(
			`{"record_kind":"call","body":"Missed call","participants":["+15551234567"],"occurred_at":"2024-03-02T01:02:03Z","call":{"direction":"incoming","disposition":"missed","missed":true,"duration_seconds":0}}`,
		),
	}})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	if len(writer.emitted) != 1 {
		t.Fatalf("emitted %d records, want 1", len(writer.emitted))
	}
	record := writer.emitted[0]
	if record.RecordType != RecordTypeCall {
		t.Fatalf("record type = %q, want call", record.RecordType)
	}
	var content struct {
		Direction       string  `json:"direction"`
		Disposition     string  `json:"disposition"`
		Missed          bool    `json:"missed"`
		DurationSeconds *uint64 `json:"duration_seconds"`
		Body            string  `json:"body"`
	}
	if err := json.Unmarshal(record.Content, &content); err != nil {
		t.Fatal(err)
	}
	if content.Direction != "incoming" || content.Disposition != "missed" || !content.Missed ||
		content.DurationSeconds == nil || *content.DurationSeconds != 0 || content.Body != "Missed call" {
		t.Fatalf("call content = %+v", content)
	}
	if !hasParticipant(record.Participants, RoleUnknown, "+15551234567") {
		t.Fatalf("participants = %+v", record.Participants)
	}
	if record.OccurredAt == nil || !record.OccurredAt.Equal(time.Date(2024, 3, 2, 1, 2, 3, 0, time.UTC)) {
		t.Fatalf("occurred_at = %v", record.OccurredAt)
	}
}

func TestGenericMessageNormalizerPreservesBodylessOutgoingCallDuration(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{
		RecordOrdinal: 0, RecordStatus: "parsed",
		NativeFields: []byte(`{"record_kind":"call","call":{"direction":"outgoing","disposition":"completed","missed":false,"duration_seconds":42}}`),
	}})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	record := writer.emitted[0]
	if record.RecordType != RecordTypeCall || string(record.Content) != `{"direction":"outgoing","disposition":"completed","missed":false,"duration_seconds":42}` {
		t.Fatalf("record type/content = %q %s", record.RecordType, record.Content)
	}
}

func TestGenericMessageNormalizerPreservesBodylessMessageKind(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{
		RecordOrdinal: 0, RecordStatus: "parsed",
		NativeFields: []byte(`{"record_kind":"message","participants":["+15551234567"]}`),
	}})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	if len(writer.emitted) != 1 {
		t.Fatalf("emitted %d records, want 1", len(writer.emitted))
	}
	record := writer.emitted[0]
	if record.RecordType != RecordTypeMessage || string(record.Content) != `{"body":""}` {
		t.Fatalf("record type/content = %q %s", record.RecordType, record.Content)
	}
	if !hasParticipant(record.Participants, RoleUnknown, "+15551234567") {
		t.Fatalf("participants = %+v", record.Participants)
	}
}

func TestGenericMessageNormalizerRejectsInconsistentTypedCall(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{
		RecordOrdinal: 0, RecordStatus: "parsed",
		NativeFields: []byte(`{"record_kind":"call","body":"Missed call","call":{"direction":"incoming","disposition":"missed","missed":false}}`),
	}})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err == nil || !strings.Contains(err.Error(), "missed flag") {
		t.Fatalf("inconsistent call error = %v", err)
	}
	if !writer.aborted || writer.finalized {
		t.Fatalf("finalized=%v aborted=%v", writer.finalized, writer.aborted)
	}
}

func TestGenericMessageNormalizerMapsLegacySBVMetadata(t *testing.T) {
	writer := &recordingWriter{bundleRef: "bundle:1"}
	input := baseInput([]RawRecordView{{
		RecordOrdinal: 0,
		RecordStatus:  "parsed",
		NativeFields:  []byte(`{}`),
		NativeMetadata: []byte(
			`{"sbv_content":"legacy","sbv_sender":"alice","sbv_participants":["carol"],"sbv_recipients":[{"identity":"bob","role":"to"}],"occurred_at":"2023-01-02T03:04:05Z"}`,
		),
	}})
	if _, err := Execute(context.Background(), input, GenericMessageNormalizer{}, writer); err != nil {
		t.Fatal(err)
	}
	record := writer.emitted[0]
	if record.RecordType != RecordTypeMessage || string(record.Content) != `{"body":"legacy"}` {
		t.Fatalf("record type/content = %q %s", record.RecordType, record.Content)
	}
	if !hasParticipant(record.Participants, RoleSender, "alice") || !hasParticipant(record.Participants, RoleRecipient, "bob") || !hasParticipant(record.Participants, RoleUnknown, "carol") {
		t.Fatalf("participants = %+v", record.Participants)
	}
}

func hasParticipant(participants []Participant, role ParticipantRole, identifier string) bool {
	for _, participant := range participants {
		if participant.Role == role && participant.Identifier == identifier {
			return true
		}
	}
	return false
}

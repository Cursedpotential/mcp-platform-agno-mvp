package parser

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

type testAdapter struct {
	capability Capability
	parse      func(context.Context, ParserInput, BundleSink) (BundleAccounting, error)
}

func (a testAdapter) Capability() Capability { return a.capability }

func (a testAdapter) Parse(ctx context.Context, input ParserInput, sink BundleSink) (BundleAccounting, error) {
	return a.parse(ctx, input, sink)
}

type testWriter struct {
	header           BundleHeader
	records          []RawRecordEnvelope
	begins           int
	finalizes        int
	aborts           int
	abortCanceled    bool
	abortHasDeadline bool
	accounting       BundleAccounting
	failure          error
}

func (w *testWriter) Begin(_ context.Context, header BundleHeader) error {
	w.begins++
	w.header = header
	return w.failure
}

func (w *testWriter) Emit(_ context.Context, record RawRecordEnvelope) error {
	w.records = append(w.records, record)
	return w.failure
}

func (w *testWriter) Finalize(_ context.Context, accounting BundleAccounting) (BundleResult, error) {
	w.finalizes++
	w.accounting = accounting
	if w.failure != nil {
		return BundleResult{}, w.failure
	}
	return BundleResult{BundleRef: "bundle:test"}, nil
}

func (w *testWriter) Abort(ctx context.Context) error {
	w.aborts++
	w.abortCanceled = ctx.Err() != nil
	_, w.abortHasDeadline = ctx.Deadline()
	return nil
}

func validCapability(id string, quality Quality) Capability {
	return Capability{
		ContractVersion: ContractVersion,
		ParserID:        id,
		ParserVersion:   "1.0.0",
		Language:        LanguageGo,
		DeclaredFormats: []FormatID{"sms_xml_backup"},
		FormatQuality:   map[FormatID]Quality{"sms_xml_backup": quality},
	}
}

func validInput() ParserInput {
	return ParserInput{
		ContractVersion:  ContractVersion,
		SourceVersionRef: "source:version:1",
		FileOrMember: Locator{
			Type: LocatorByteRange,
			ObjectRef: ObjectRef{
				StorageClass: "immutable_object_store",
				URI:          "s3://originals/source.xml",
			},
			ByteRange: &ByteRange{Offset: 64, Length: 128},
		},
		DeclaredFormat: "sms_xml_backup",
	}
}

func validRecord(ordinal uint64, status RecordStatus) RawRecordEnvelope {
	record := RawRecordEnvelope{
		RecordOrdinal: ordinal,
		RecordStatus:  status,
		Locator: &Locator{
			Type: LocatorByteRange,
			ObjectRef: ObjectRef{
				StorageClass: "immutable_object_store",
				URI:          "s3://originals/source.xml",
			},
			ByteRange: &ByteRange{Offset: ordinal * 10, Length: 10},
		},
		FormatID:     "sms_xml_backup",
		NativeFields: json.RawMessage(`{"body":"source-native"}`),
	}
	if status != StatusParsed {
		record.StatusReason = "preserved source span is not a parsed record"
	}
	return record
}

func executeAdapter(t *testing.T, adapter testAdapter, writer *testWriter) (BundleResult, error) {
	t.Helper()
	registry, err := NewRegistry(adapter)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	return reference.Execute(context.Background(), validInput(), writer)
}

func TestRegistrySelectsDeclaredCoverageAndQualityDeterministically(t *testing.T) {
	primary := testAdapter{capability: validCapability("z-primary", QualityPrimary)}
	fallback := testAdapter{capability: validCapability("a-fallback", QualityFallback)}
	experimental := testAdapter{capability: validCapability("b-experimental", QualityExperimental)}

	registry, err := NewRegistry(experimental, fallback, primary)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	selected, err := reference.Select("sms_xml_backup")
	if err != nil {
		t.Fatalf("Select() error = %v", err)
	}
	if got := selected.Capability().ParserID; got != "z-primary" {
		t.Fatalf("Select() parser id = %q, want primary coverage candidate", got)
	}

	first := testAdapter{capability: validCapability("a-lexical", QualityFallback)}
	second := testAdapter{capability: validCapability("z-lexical", QualityFallback)}
	registry, err = NewRegistry(second, first)
	if err != nil {
		t.Fatalf("NewRegistry() lexical tie = %v", err)
	}
	selected, err = reference.Select("sms_xml_backup")
	if err != nil {
		t.Fatalf("Select() lexical tie = %v", err)
	}
	if got := selected.Capability().ParserID; got != "a-lexical" {
		t.Fatalf("Select() lexical tie = %q, want a-lexical", got)
	}
}

func TestRegistryNeverRoutesOnInputSize(t *testing.T) {
	tinyLimit, hugeLimit := int64(1), int64(1<<40)
	primary := testAdapter{capability: validCapability("primary", QualityPrimary)}
	primary.capability.MaxInputBytes = &tinyLimit
	fallback := testAdapter{capability: validCapability("fallback", QualityFallback)}
	fallback.capability.MaxInputBytes = &hugeLimit
	registry, err := NewRegistry(fallback, primary)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	selected, err := reference.Select("sms_xml_backup")
	if err != nil {
		t.Fatalf("Select() error = %v", err)
	}
	if got := selected.Capability().ParserID; got != "primary" {
		t.Fatalf("Select() considered max_input_bytes: got %q, want primary", got)
	}
}

func TestCapabilityRequiresVersionedCanonicalFormatCoverage(t *testing.T) {
	tests := []struct {
		name       string
		capability Capability
	}{
		{
			name: "unsupported contract version",
			capability: Capability{
				ContractVersion: "2.0.0",
				ParserID:        "parser",
				ParserVersion:   "1.0.0",
				Language:        LanguageGo,
				DeclaredFormats: []FormatID{"sms_xml_backup"},
			},
		},
		{
			name: "non canonical format",
			capability: Capability{
				ContractVersion: ContractVersion,
				ParserID:        "parser",
				ParserVersion:   "1.0.0",
				Language:        LanguageGo,
				DeclaredFormats: []FormatID{"SMS-XML"},
			},
		},
		{
			name: "quality for uncovered format",
			capability: Capability{
				ContractVersion: ContractVersion,
				ParserID:        "parser",
				ParserVersion:   "1.0.0",
				Language:        LanguageGo,
				DeclaredFormats: []FormatID{"sms_xml_backup"},
				FormatQuality:   map[FormatID]Quality{"email_eml": QualityPrimary},
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if err := test.capability.Validate(); err == nil {
				t.Fatal("Capability.Validate() succeeded, want validation failure")
			}
		})
	}
}

func TestCommonNativeFieldsKeepCallsTypedAndInternallyConsistent(t *testing.T) {
	duration := uint64(0)
	valid := CommonNativeFields{RecordKind: NativeKindCall, Call: &NativeCallFields{
		Direction: CallDirectionIncoming, Disposition: CallDispositionMissed,
		Missed: true, DurationSeconds: &duration,
	}}
	if err := valid.Validate(); err != nil {
		t.Fatalf("valid native call fields: %v", err)
	}
	invalid := []CommonNativeFields{
		{RecordKind: NativeKindCall},
		{RecordKind: NativeKindMessage, Call: valid.Call},
		{RecordKind: NativeKindCall, Call: &NativeCallFields{
			Direction: CallDirectionIncoming, Disposition: CallDispositionMissed, Missed: false,
		}},
	}
	for index, fields := range invalid {
		if err := fields.Validate(); err == nil {
			t.Fatalf("invalid native fields case %d passed validation: %+v", index, fields)
		}
	}
}

func TestParserInputPreservesFileOrMemberLocatorAndObjectHashShape(t *testing.T) {
	input := validInput()
	if err := input.Validate(); err != nil {
		t.Fatalf("ParserInput.Validate() error = %v", err)
	}
	if input.FileOrMember.Type != LocatorByteRange || input.FileOrMember.ByteRange == nil {
		t.Fatalf("ParserInput did not retain file/member byte range: %+v", input.FileOrMember)
	}

	validHash := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	object := ObjectRef{StorageClass: "immutable_object_store", URI: "s3://originals/x", ContentHash: validHash}
	if err := object.Validate(); err != nil {
		t.Fatalf("ObjectRef.Validate() valid content hash error = %v", err)
	}
	for _, invalidHash := range []string{"abcd", "0123456789ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef", "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"} {
		object.ContentHash = invalidHash
		if err := object.Validate(); err == nil {
			t.Fatalf("ObjectRef.Validate() accepted invalid content hash %q", invalidHash)
		}
	}
}

func TestExecuteStreamsEnvelopeAndUnparsedRowsWithContractAccounting(t *testing.T) {
	adapter := testAdapter{
		capability: validCapability("external-python-proxy", QualityPrimary),
		parse: func(ctx context.Context, _ ParserInput, sink BundleSink) (BundleAccounting, error) {
			envelope := validRecord(0, StatusEnvelope)
			unparsed := validRecord(1, StatusUnparsed)
			if err := sink.Emit(ctx, envelope); err != nil {
				return BundleAccounting{}, err
			}
			if err := sink.Emit(ctx, unparsed); err != nil {
				return BundleAccounting{}, err
			}
			return BundleAccounting{Unparsed: 1}, nil
		},
	}
	adapter.capability.Language = LanguagePython
	writer := &testWriter{}
	result, err := executeAdapter(t, adapter, writer)
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if result.BundleRef != "bundle:test" || writer.finalizes != 1 || writer.aborts != 0 {
		t.Fatalf("Execute() result=%+v finalizes=%d aborts=%d", result, writer.finalizes, writer.aborts)
	}
	if got := len(writer.records); got != 2 {
		t.Fatalf("streamed records = %d, want 2", got)
	}
	if writer.accounting != (BundleAccounting{Unparsed: 1}) {
		t.Fatalf("final accounting = %+v, want envelope excluded and unparsed counted", writer.accounting)
	}
}

func TestExecuteRejectsCancellationAndAbortsOpenBundle(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	adapter := testAdapter{
		capability: validCapability("cancellable", QualityPrimary),
		parse: func(parseCtx context.Context, _ ParserInput, _ BundleSink) (BundleAccounting, error) {
			cancel()
			return BundleAccounting{}, parseCtx.Err()
		},
	}
	registry, err := NewRegistry(adapter)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	writer := &testWriter{}
	_, err = reference.Execute(ctx, validInput(), writer)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("Execute() error = %v, want context cancellation", err)
	}
	if writer.finalizes != 0 || writer.aborts != 1 {
		t.Fatalf("finalizes=%d aborts=%d, want 0/1", writer.finalizes, writer.aborts)
	}
	if writer.abortCanceled || !writer.abortHasDeadline {
		t.Fatalf("Abort context canceled=%t deadline=%t, want false/true", writer.abortCanceled, writer.abortHasDeadline)
	}
}

func TestExecuteAbortsEvenWhenBeginFails(t *testing.T) {
	adapter := testAdapter{capability: validCapability("begin-failure", QualityPrimary)}
	registry, err := NewRegistry(adapter)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	writer := &testWriter{failure: errors.New("partial allocation failed")}
	_, err = reference.Execute(context.Background(), validInput(), writer)
	if err == nil || !strings.Contains(err.Error(), "begin raw extraction bundle") {
		t.Fatalf("Execute() error = %v", err)
	}
	if writer.aborts != 1 || writer.abortCanceled || !writer.abortHasDeadline {
		t.Fatalf("begin failure cleanup aborts=%d canceled=%t deadline=%t, want 1/false/true", writer.aborts, writer.abortCanceled, writer.abortHasDeadline)
	}
}

func TestExecuteRejectsNonContiguousOrdinalAndZeroOutput(t *testing.T) {
	tests := []struct {
		name  string
		parse func(context.Context, ParserInput, BundleSink) (BundleAccounting, error)
		want  string
	}{
		{
			name: "non-contiguous ordinal",
			parse: func(ctx context.Context, _ ParserInput, sink BundleSink) (BundleAccounting, error) {
				return BundleAccounting{}, sink.Emit(ctx, validRecord(1, StatusParsed))
			},
			want: "contiguous ordinal",
		},
		{
			name: "zero output",
			parse: func(context.Context, ParserInput, BundleSink) (BundleAccounting, error) {
				return BundleAccounting{}, nil
			},
			want: "zero records",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			adapter := testAdapter{capability: validCapability("invalid-"+test.name, QualityPrimary), parse: test.parse}
			writer := &testWriter{}
			_, err := executeAdapter(t, adapter, writer)
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("Execute() error = %v, want %q", err, test.want)
			}
			if writer.finalizes != 0 || writer.aborts != 1 {
				t.Fatalf("finalizes=%d aborts=%d, want 0/1", writer.finalizes, writer.aborts)
			}
		})
	}
}

func TestExecuteRejectsAccountingMismatchAndInvalidRecordShapes(t *testing.T) {
	invalidShapes := []struct {
		name   string
		record RawRecordEnvelope
		want   string
	}{
		{
			name:   "missing exact bytes coordinate",
			record: RawRecordEnvelope{RecordOrdinal: 0, RecordStatus: StatusParsed, FormatID: "sms_xml_backup"},
			want:   "exact locator or stored bytes",
		},
		{
			name: "unparsed without reason",
			record: func() RawRecordEnvelope {
				record := validRecord(0, StatusUnparsed)
				record.StatusReason = ""
				return record
			}(),
			want: "requires a reason",
		},
		{
			name: "wrong format",
			record: func() RawRecordEnvelope {
				record := validRecord(0, StatusParsed)
				record.FormatID = "email_eml"
				return record
			}(),
			want: "does not match bundle format",
		},
		{
			name: "non-object native fields",
			record: func() RawRecordEnvelope {
				record := validRecord(0, StatusParsed)
				record.NativeFields = json.RawMessage(`[]`)
				return record
			}(),
			want: "native fields must be a JSON object",
		},
	}
	for _, test := range invalidShapes {
		t.Run(test.name, func(t *testing.T) {
			adapter := testAdapter{
				capability: validCapability("shape-"+test.name, QualityPrimary),
				parse: func(ctx context.Context, _ ParserInput, sink BundleSink) (BundleAccounting, error) {
					// A bad adapter might ignore Emit's error. The registry keeps the
					// fault and refuses finalization anyway.
					_ = sink.Emit(ctx, test.record)
					return BundleAccounting{}, nil
				},
			}
			writer := &testWriter{}
			_, err := executeAdapter(t, adapter, writer)
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("Execute() error = %v, want %q", err, test.want)
			}
			if writer.finalizes != 0 || writer.aborts != 1 {
				t.Fatalf("finalizes=%d aborts=%d, want 0/1", writer.finalizes, writer.aborts)
			}
		})
	}

	adapter := testAdapter{
		capability: validCapability("mismatched-counts", QualityPrimary),
		parse: func(ctx context.Context, _ ParserInput, sink BundleSink) (BundleAccounting, error) {
			if err := sink.Emit(ctx, validRecord(0, StatusParsed)); err != nil {
				return BundleAccounting{}, err
			}
			return BundleAccounting{}, nil
		},
	}
	writer := &testWriter{}
	_, err := executeAdapter(t, adapter, writer)
	if err == nil || !strings.Contains(err.Error(), "accounting mismatch") {
		t.Fatalf("Execute() accounting error = %v", err)
	}
	if writer.finalizes != 0 || writer.aborts != 1 {
		t.Fatalf("accounting finalizes=%d aborts=%d, want 0/1", writer.finalizes, writer.aborts)
	}
}

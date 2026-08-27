package activities

import (
	"context"
	"encoding/json"
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

type runtimeAdapter struct {
	capability parser.Capability
	parse      func(context.Context, parser.ParserInput, parser.BundleSink) (parser.BundleAccounting, error)
}

func (a runtimeAdapter) Capability() parser.Capability { return a.capability }

func (a runtimeAdapter) Parse(ctx context.Context, input parser.ParserInput, sink parser.BundleSink) (parser.BundleAccounting, error) {
	return a.parse(ctx, input, sink)
}

type runtimeBundleWriter struct {
	header    parser.BundleHeader
	records   int
	aborts    int
	finalizes int
}

func (w *runtimeBundleWriter) Begin(_ context.Context, header parser.BundleHeader) error {
	w.header = header
	return nil
}

func (w *runtimeBundleWriter) Emit(_ context.Context, _ parser.RawRecordEnvelope) error {
	w.records++
	return nil
}

func (w *runtimeBundleWriter) Finalize(_ context.Context, _ parser.BundleAccounting) (parser.BundleResult, error) {
	w.finalizes++
	return parser.BundleResult{BundleRef: "bundle:staged"}, nil
}

func (w *runtimeBundleWriter) Abort(_ context.Context) error {
	w.aborts++
	return nil
}

type runtimeStore struct {
	selectionSpec ParserSelectionSpec
	selection     PersistedParserSelection
	input         parser.ParserInput
	writer        parser.BundleWriter
	executionSpec ParserExecutionSpec

	loadSelectionErr error
	resolveInputErr  error
	openWriterErr    error
	persistSelectErr error
	persistExecErr   error
	persistExecCalls int
}

func (s *runtimeStore) PersistParserSelection(_ context.Context, spec ParserSelectionSpec) (uiw.Ref, uiw.Ref, error) {
	s.selectionSpec = spec
	if s.persistSelectErr != nil {
		return "", "", s.persistSelectErr
	}
	s.selection = PersistedParserSelection{
		SourceVersionRef: spec.SourceVersionRef,
		DeclaredFormat:   spec.DeclaredFormat,
		ParserID:         spec.ParserID,
		ParserVersion:    spec.ParserVersion,
	}
	return "selection:1", "receipt:selection", nil
}

func (s *runtimeStore) LoadParserSelection(_ context.Context, _ uiw.Ref) (PersistedParserSelection, error) {
	if s.loadSelectionErr != nil {
		return PersistedParserSelection{}, s.loadSelectionErr
	}
	return s.selection, nil
}

func (s *runtimeStore) ResolveParserInput(_ context.Context, _ uiw.StageRequest, _ PersistedParserSelection) (parser.ParserInput, error) {
	if s.resolveInputErr != nil {
		return parser.ParserInput{}, s.resolveInputErr
	}
	return s.input, nil
}

func (s *runtimeStore) OpenParserBundleWriter(_ context.Context, _ uiw.StageRequest, _ PersistedParserSelection, _ parser.ParserInput) (parser.BundleWriter, error) {
	if s.openWriterErr != nil {
		return nil, s.openWriterErr
	}
	return s.writer, nil
}

func (s *runtimeStore) PersistParserExecution(_ context.Context, spec ParserExecutionSpec) (uiw.Ref, uiw.Ref, error) {
	s.persistExecCalls++
	s.executionSpec = spec
	if s.persistExecErr != nil {
		return "", "", s.persistExecErr
	}
	return "execution:1", "receipt:execution", nil
}

func runtimeCapability(id, version string, quality parser.Quality) parser.Capability {
	return parser.Capability{
		ContractVersion: parser.ContractVersion,
		ParserID:        id,
		ParserVersion:   version,
		Language:        parser.LanguageGo,
		DeclaredFormats: []parser.FormatID{"sms_xml_backup"},
		FormatQuality:   map[parser.FormatID]parser.Quality{"sms_xml_backup": quality},
	}
}

func runtimeInput() parser.ParserInput {
	return parser.ParserInput{
		ContractVersion:  parser.ContractVersion,
		SourceVersionRef: "source:version:1",
		FileOrMember: parser.Locator{
			Type: parser.LocatorByteRange,
			ObjectRef: parser.ObjectRef{
				StorageClass: "immutable_object_store",
				URI:          "s3://source/original.zip",
			},
			ByteRange: &parser.ByteRange{Offset: 100, Length: 200},
		},
		DeclaredFormat:   "sms_xml_backup",
		ParserOptionsRef: "options:1",
	}
}

func runtimeRecord() parser.RawRecordEnvelope {
	return parser.RawRecordEnvelope{
		RecordOrdinal: 0,
		RecordStatus:  parser.StatusParsed,
		Locator: &parser.Locator{
			Type: parser.LocatorByteRange,
			ObjectRef: parser.ObjectRef{
				StorageClass: "immutable_object_store",
				URI:          "s3://source/original.zip",
			},
			ByteRange: &parser.ByteRange{Offset: 100, Length: 200},
		},
		FormatID:     "sms_xml_backup",
		NativeFields: json.RawMessage(`{"body":"native"}`),
	}
}

func parserStageRequest() uiw.StageRequest {
	return uiw.StageRequest{
		RequestID:        "workflow:1",
		SourceVersionRef: "source:version:1",
		DeclaredFormat:   "sms_xml_backup",
		Refs: map[string]uiw.Ref{
			"parser_selection": "selection:1",
			"original":         "original:1",
			"parser_options":   "options:1",
		},
	}
}

func successfulParser(capability parser.Capability, calls *int) runtimeAdapter {
	return runtimeAdapter{
		capability: capability,
		parse: func(ctx context.Context, _ parser.ParserInput, sink parser.BundleSink) (parser.BundleAccounting, error) {
			*calls++
			if err := sink.Emit(ctx, runtimeRecord()); err != nil {
				return parser.BundleAccounting{}, err
			}
			return parser.BundleAccounting{Emitted: 1}, nil
		},
	}
}

func TestParserActivitiesSelectionPinsExactParserAcrossRegistryDrift(t *testing.T) {
	oldCalls, newCalls := 0, 0
	old := successfulParser(runtimeCapability("old-parser", "1.0.0", parser.QualityPrimary), &oldCalls)
	selectionRegistry, err := parser.NewRegistry(old)
	if err != nil {
		t.Fatalf("NewRegistry(selection) error = %v", err)
	}
	store := &runtimeStore{input: runtimeInput(), writer: &runtimeBundleWriter{}}
	activities := ParserActivities{Registry: selectionRegistry, Store: store, Attempt: func(context.Context) int32 { return 7 }}
	selection, err := activities.SelectParser(context.Background(), parserStageRequest())
	if err != nil {
		t.Fatalf("SelectParser() error = %v", err)
	}
	if selection.Stage != stagegraph.SelectParser || selection.Ref != "selection:1" || selection.ReceiptRef != "receipt:selection" {
		t.Fatalf("selection result = %+v", selection)
	}
	if store.selectionSpec.Attempt != 7 || store.selectionSpec.ParserID != "old-parser" {
		t.Fatalf("persisted selection = %+v", store.selectionSpec)
	}

	new := successfulParser(runtimeCapability("new-parser", "2.0.0", parser.QualityPrimary), &newCalls)
	oldFallback := successfulParser(runtimeCapability("old-parser", "1.0.0", parser.QualityFallback), &oldCalls)
	driftedRegistry, err := parser.NewRegistry(oldFallback, new)
	if err != nil {
		t.Fatalf("NewRegistry(drifted) error = %v", err)
	}
	activities.Registry = driftedRegistry
	execution, err := activities.ExecuteParser(context.Background(), parserStageRequest())
	if err != nil {
		t.Fatalf("ExecuteParser() error = %v", err)
	}
	if newCalls != 0 || oldCalls != 1 {
		t.Fatalf("execution reselected after drift: old calls=%d new calls=%d", oldCalls, newCalls)
	}
	if execution.Stage != stagegraph.ExecuteParser || execution.Status != uiw.StatusSuccess || execution.Ref != "execution:1" || execution.ReceiptRef != "receipt:execution" {
		t.Fatalf("execution result = %+v", execution)
	}
	if store.executionSpec.Attempt != 7 || store.executionSpec.BundleRef != "bundle:staged" || store.executionSpec.ParserID != "old-parser" {
		t.Fatalf("execution receipt spec = %+v", store.executionSpec)
	}
}

func TestExecuteParserFailsClosedForMissingOrWrongPersistedSelection(t *testing.T) {
	calls := 0
	adapter := successfulParser(runtimeCapability("parser", "1.0.0", parser.QualityPrimary), &calls)
	registry, err := parser.NewRegistry(adapter)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	tests := []struct {
		name  string
		store *runtimeStore
		want  string
	}{
		{
			name:  "missing selection",
			store: &runtimeStore{input: runtimeInput(), writer: &runtimeBundleWriter{}, loadSelectionErr: errors.New("selection missing")},
			want:  "selection missing",
		},
		{
			name: "wrong parser identity",
			store: &runtimeStore{
				input:     runtimeInput(),
				writer:    &runtimeBundleWriter{},
				selection: PersistedParserSelection{SourceVersionRef: "source:version:1", DeclaredFormat: "sms_xml_backup", ParserID: "not-registered", ParserVersion: "1.0.0"},
			},
			want: "not registered",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			activities := ParserActivities{Registry: registry, Store: test.store}
			_, err := activities.ExecuteParser(context.Background(), parserStageRequest())
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("ExecuteParser() error = %v, want %q", err, test.want)
			}
			if test.store.persistExecCalls != 0 {
				t.Fatalf("persisted execution calls=%d, want zero", test.store.persistExecCalls)
			}
		})
	}
	if calls != 0 {
		t.Fatalf("parser calls=%d, want zero for failed persisted selections", calls)
	}
}

func TestExecuteParserParseErrorAbortsAndDoesNotPersistReceipt(t *testing.T) {
	adapter := runtimeAdapter{
		capability: runtimeCapability("failing-parser", "1.0.0", parser.QualityPrimary),
		parse: func(context.Context, parser.ParserInput, parser.BundleSink) (parser.BundleAccounting, error) {
			return parser.BundleAccounting{}, errors.New("decoder failed")
		},
	}
	registry, err := parser.NewRegistry(adapter)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	writer := &runtimeBundleWriter{}
	store := &runtimeStore{
		input:     runtimeInput(),
		writer:    writer,
		selection: PersistedParserSelection{SourceVersionRef: "source:version:1", DeclaredFormat: "sms_xml_backup", ParserID: "failing-parser", ParserVersion: "1.0.0"},
	}
	_, err = (ParserActivities{Registry: registry, Store: store}).ExecuteParser(context.Background(), parserStageRequest())
	if err == nil || !strings.Contains(err.Error(), "decoder failed") {
		t.Fatalf("ExecuteParser() error = %v", err)
	}
	if writer.aborts != 1 || writer.finalizes != 0 || store.persistExecCalls != 0 {
		t.Fatalf("aborts=%d finalizes=%d persisted=%d, want 1/0/0", writer.aborts, writer.finalizes, store.persistExecCalls)
	}
}

func TestParserActivitiesSelectionNeverRoutesOnInputSizeAndWireIsCompact(t *testing.T) {
	tiny, huge := int64(1), int64(1<<40)
	primaryCalls, fallbackCalls := 0, 0
	primary := successfulParser(runtimeCapability("primary", "1.0.0", parser.QualityPrimary), &primaryCalls)
	primary.capability.MaxInputBytes = &tiny
	fallback := successfulParser(runtimeCapability("fallback", "1.0.0", parser.QualityFallback), &fallbackCalls)
	fallback.capability.MaxInputBytes = &huge
	registry, err := parser.NewRegistry(fallback, primary)
	if err != nil {
		t.Fatalf("NewRegistry() error = %v", err)
	}
	store := &runtimeStore{input: runtimeInput(), writer: &runtimeBundleWriter{}}
	result, err := (ParserActivities{Registry: registry, Store: store}).SelectParser(context.Background(), parserStageRequest())
	if err != nil {
		t.Fatalf("SelectParser() error = %v", err)
	}
	if result.Ref == "" || store.selectionSpec.ParserID != "primary" || primaryCalls != 0 || fallbackCalls != 0 {
		t.Fatalf("selection result=%+v spec=%+v parse calls primary/fallback=%d/%d", result, store.selectionSpec, primaryCalls, fallbackCalls)
	}

	for _, value := range []any{ParserSelectionSpec{}, PersistedParserSelection{}, ParserExecutionSpec{}, uiw.StageRequest{}, uiw.StageResult{}} {
		typeOfValue := reflect.TypeOf(value)
		for index := 0; index < typeOfValue.NumField(); index++ {
			if typeOfValue.Field(index).Type.Kind() == reflect.Slice {
				t.Fatalf("activity wire type %s field %s carries a slice", typeOfValue.Name(), typeOfValue.Field(index).Name)
			}
		}
	}
}

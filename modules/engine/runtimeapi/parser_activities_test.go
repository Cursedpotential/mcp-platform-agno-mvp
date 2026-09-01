package runtimeapi

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

func TestParserActivityHandlerSelectsThroughAtomicActivity(t *testing.T) {
	registry, err := parser.NewRegistry(httpTestAdapter{})
	if err != nil {
		t.Fatal(err)
	}
	handler, err := NewParserActivityHandler(activities.ParserActivities{
		Registry: registry, Store: httpTestStore{},
	}, "test-token")
	if err != nil {
		t.Fatal(err)
	}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, SelectParserPath, strings.NewReader(`{"request_id":"workflow-1","source_version_ref":"source-1","declared_format":"sms_xml_backup","refs":{"metadata_manifest":"manifest-1"}}`))
	request.Header.Set("Authorization", "Bearer test-token")
	handler.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", recorder.Code, recorder.Body.String())
	}
	var result stageResultResponse
	if err := json.Unmarshal(recorder.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Stage != stagegraph.SelectParser || result.Status != uiw.StatusSuccess || result.Ref != "selection:1" || result.ReceiptRef != "receipt:1" {
		t.Fatalf("result = %+v", result)
	}
}

func TestParserActivityHandlerExecutesThroughPinnedSelection(t *testing.T) {
	registry, err := parser.NewRegistry(httpTestAdapter{})
	if err != nil {
		t.Fatal(err)
	}
	handler, err := NewParserActivityHandler(activities.ParserActivities{
		Registry: registry, Store: httpTestStore{},
	}, "test-token")
	if err != nil {
		t.Fatal(err)
	}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, ExecuteParserPath, strings.NewReader(`{"request_id":"workflow-1","source_version_ref":"source-1","declared_format":"sms_xml_backup","refs":{"parser_selection":"selection:1","original":"original:1","parser_options":"options:1"}}`))
	request.Header.Set("Authorization", "Bearer test-token")
	handler.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", recorder.Code, recorder.Body.String())
	}
	var result stageResultResponse
	if err := json.Unmarshal(recorder.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Stage != stagegraph.ExecuteParser || result.Status != uiw.StatusSuccess || result.Ref != "bundle:1" || result.ReceiptRef != "receipt:2" {
		t.Fatalf("result = %+v", result)
	}
}

func TestParserActivityHandlerRejectsPayloadFieldsAndWrongRoutes(t *testing.T) {
	registry, err := parser.NewRegistry(httpTestAdapter{})
	if err != nil {
		t.Fatal(err)
	}
	handler, err := NewParserActivityHandler(activities.ParserActivities{Registry: registry, Store: httpTestStore{}}, "test-token")
	if err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		name, method, path, body string
		status                   int
	}{
		{"source bytes are not wire data", http.MethodPost, SelectParserPath, `{"request_id":"w","source_version_ref":"s","declared_format":"sms_xml_backup","source_bytes":"abc"}`, http.StatusBadRequest},
		{"record arrays are not wire data", http.MethodPost, SelectParserPath, `{"request_id":"w","source_version_ref":"s","declared_format":"sms_xml_backup","records":[]}`, http.StatusBadRequest},
		{"wrong route", http.MethodPost, "/activities/parser", `{}`, http.StatusNotFound},
		{"wrong method", http.MethodGet, SelectParserPath, `{}`, http.StatusMethodNotAllowed},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			request := httptest.NewRequest(test.method, test.path, strings.NewReader(test.body))
			request.Header.Set("Authorization", "Bearer test-token")
			handler.ServeHTTP(recorder, request)
			if recorder.Code != test.status {
				t.Fatalf("status = %d, want %d, body = %s", recorder.Code, test.status, recorder.Body.String())
			}
		})
	}
}

func TestParserActivityHandlerRejectsMissingDependencies(t *testing.T) {
	if _, err := NewParserActivityHandler(activities.ParserActivities{}, "test-token"); err == nil {
		t.Fatal("missing parser dependencies accepted")
	}
	registry, err := parser.NewRegistry(httpTestAdapter{})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := NewParserActivityHandler(activities.ParserActivities{Registry: registry, Store: httpTestStore{}}, ""); err == nil {
		t.Fatal("empty bearer token accepted")
	}
}

func TestParserActivityHandlerRequiresConstantTimeBearerToken(t *testing.T) {
	if validBearerToken("", []byte("secret")) || validBearerToken("Bearer wrong", []byte("secret")) {
		t.Fatal("invalid bearer token accepted")
	}
	if !validBearerToken("Bearer secret", []byte("secret")) || !validBearerToken("bearer secret", []byte("secret")) {
		t.Fatal("valid bearer token rejected")
	}
}

type httpTestAdapter struct{}

func (httpTestAdapter) Capability() parser.Capability {
	return parser.Capability{
		ContractVersion: parser.ContractVersion, ParserID: "http-test-parser", ParserVersion: "1.0.0",
		Language: parser.LanguageGo, DeclaredFormats: []parser.FormatID{"sms_xml_backup"},
	}
}

func (httpTestAdapter) Parse(ctx context.Context, input parser.ParserInput, sink parser.BundleSink) (parser.BundleAccounting, error) {
	if err := sink.Emit(ctx, parser.RawRecordEnvelope{
		RecordOrdinal: 0, RecordStatus: parser.StatusParsed, FormatID: input.DeclaredFormat,
		Locator:      &parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: input.FileOrMember.ObjectRef},
		NativeFields: json.RawMessage(`{}`), NativeMetadata: json.RawMessage(`{}`),
	}); err != nil {
		return parser.BundleAccounting{}, err
	}
	return parser.BundleAccounting{Emitted: 1}, nil
}

type httpTestStore struct{}

func (httpTestStore) PersistParserSelection(context.Context, activities.ParserSelectionSpec) (uiw.Ref, uiw.Ref, error) {
	return "selection:1", "receipt:1", nil
}

func (httpTestStore) LoadParserSelection(context.Context, uiw.Ref) (activities.PersistedParserSelection, error) {
	return activities.PersistedParserSelection{
		SourceVersionRef: "source-1", DeclaredFormat: "sms_xml_backup",
		ParserID: "http-test-parser", ParserVersion: "1.0.0",
	}, nil
}

func (httpTestStore) ResolveParserInput(context.Context, uiw.StageRequest, activities.PersistedParserSelection) (parser.ParserInput, error) {
	return parser.ParserInput{
		ContractVersion: parser.ContractVersion, SourceVersionRef: "source-1", DeclaredFormat: "sms_xml_backup",
		FileOrMember: parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{StorageClass: "filesystem", URI: "file:///retained/source"}},
	}, nil
}

func (httpTestStore) OpenParserBundleWriter(context.Context, uiw.StageRequest, activities.PersistedParserSelection, parser.ParserInput) (parser.BundleWriter, error) {
	return httpTestBundleWriter{}, nil
}

func (httpTestStore) PersistParserExecution(context.Context, activities.ParserExecutionSpec) (uiw.Ref, uiw.Ref, error) {
	return "bundle:1", "receipt:2", nil
}

type httpTestBundleWriter struct{}

func (httpTestBundleWriter) Begin(context.Context, parser.BundleHeader) error     { return nil }
func (httpTestBundleWriter) Emit(context.Context, parser.RawRecordEnvelope) error { return nil }
func (httpTestBundleWriter) Finalize(context.Context, parser.BundleAccounting) (parser.BundleResult, error) {
	return parser.BundleResult{BundleRef: "bundle:1"}, nil
}
func (httpTestBundleWriter) Abort(context.Context) error { return nil }

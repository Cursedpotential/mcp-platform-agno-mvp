package temporal

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// fakeStarter is a hand-rolled WorkflowStarter for HTTP-layer tests, so they
// never need a real Temporal connection.
type fakeStarter struct {
	startIn       uiw.WorkflowInput
	startErr      error
	decideID      string
	decideArg     uiw.PreviewDecision
	decideErr     error
	previewID     string
	previewResult uiw.PreviewState
	previewErr    error
}

func (f *fakeStarter) Start(_ context.Context, in uiw.WorkflowInput) (string, string, error) {
	f.startIn = in
	if f.startErr != nil {
		return "", "", f.startErr
	}
	return "wf-" + in.RequestID, "run-1", nil
}

func (f *fakeStarter) Decide(_ context.Context, workflowID string, decision uiw.PreviewDecision) error {
	f.decideID = workflowID
	f.decideArg = decision
	return f.decideErr
}

func (f *fakeStarter) Preview(_ context.Context, workflowID string) (uiw.PreviewState, error) {
	f.previewID = workflowID
	if f.previewErr != nil {
		return uiw.PreviewState{}, f.previewErr
	}
	return f.previewResult, nil
}

func newTestHandler(t *testing.T, starter *fakeStarter) http.Handler {
	t.Helper()
	handler, err := NewStarterHTTPHandler(starter, "starter-token")
	if err != nil {
		t.Fatalf("NewStarterHTTPHandler() error = %v", err)
	}
	return handler.Routes()
}

func validStartBody() []byte {
	body, _ := json.Marshal(startRequest{
		RequestID:        "req-1",
		SourceRef:        "acquisition-ref",
		DeclaredFormat:   "whatsapp_export_json",
		ParserOptionsRef: "parser-options-ref",
	})
	return body
}

func TestStartHandlerSuccess(t *testing.T) {
	starter := &fakeStarter{}
	server := httptest.NewServer(newTestHandler(t, starter))
	defer server.Close()

	req, _ := http.NewRequest(http.MethodPost, server.URL+"/reference-import/start", bytes.NewReader(validStartBody()))
	req.Header.Set("Authorization", "Bearer starter-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /reference-import/start: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("status = %d, want 201", resp.StatusCode)
	}
	var out startResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if out.WorkflowID != "wf-req-1" || out.RunID != "run-1" {
		t.Errorf("response = %+v, unexpected", out)
	}
	if starter.startIn.RequestID != "req-1" || starter.startIn.SourceRef != "acquisition-ref" || starter.startIn.ParserOptionsRef != "parser-options-ref" {
		t.Errorf("starter.Start received %+v, unexpected", starter.startIn)
	}
}

func TestStartHandlerRejectsMissingAuth(t *testing.T) {
	starter := &fakeStarter{}
	server := httptest.NewServer(newTestHandler(t, starter))
	defer server.Close()

	resp, err := http.Post(server.URL+"/reference-import/start", "application/json", bytes.NewReader(validStartBody()))
	if err != nil {
		t.Fatalf("POST /reference-import/start: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", resp.StatusCode)
	}
}

func TestStartHandlerRejectsMissingFields(t *testing.T) {
	starter := &fakeStarter{}
	server := httptest.NewServer(newTestHandler(t, starter))
	defer server.Close()

	body, _ := json.Marshal(startRequest{RequestID: "req-1", SourceRef: "acquisition-ref"})
	req, _ := http.NewRequest(http.MethodPost, server.URL+"/reference-import/start", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer starter-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /reference-import/start: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 for a missing declared_format/parser_options_ref", resp.StatusCode)
	}
}

func TestDecisionHandlerSuccess(t *testing.T) {
	starter := &fakeStarter{}
	server := httptest.NewServer(newTestHandler(t, starter))
	defer server.Close()

	body, _ := json.Marshal(decisionRequest{Approved: true, Decider: "operator-1"})
	req, _ := http.NewRequest(http.MethodPost, server.URL+"/reference-import/wf-req-1/decision", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer starter-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST decision: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if starter.decideID != "wf-req-1" || !starter.decideArg.Approved || starter.decideArg.Decider != "operator-1" {
		t.Errorf("starter.Decide received id=%q arg=%+v, unexpected", starter.decideID, starter.decideArg)
	}
}

func TestDecisionHandlerRejectsRejectionWithoutReason(t *testing.T) {
	starter := &fakeStarter{}
	server := httptest.NewServer(newTestHandler(t, starter))
	defer server.Close()

	body, _ := json.Marshal(decisionRequest{Approved: false, Decider: "operator-1"})
	req, _ := http.NewRequest(http.MethodPost, server.URL+"/reference-import/wf-req-1/decision", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer starter-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST decision: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 when a rejection has no reason", resp.StatusCode)
	}
}

func TestPreviewHandlerSuccess(t *testing.T) {
	starter := &fakeStarter{previewResult: uiw.PreviewState{Phase: uiw.PhaseAwaitingDecision, SelectRef: "selection-ref"}}
	server := httptest.NewServer(newTestHandler(t, starter))
	defer server.Close()

	req, _ := http.NewRequest(http.MethodGet, server.URL+"/reference-import/wf-req-1/preview", nil)
	req.Header.Set("Authorization", "Bearer starter-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("GET preview: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	var state previewResponse
	if err := json.NewDecoder(resp.Body).Decode(&state); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if state.Phase != string(uiw.PhaseAwaitingDecision) || state.SelectRef != "selection-ref" {
		t.Errorf("preview state = %+v, unexpected", state)
	}
	if starter.previewID != "wf-req-1" {
		t.Errorf("starter.Preview received id=%q, want wf-req-1", starter.previewID)
	}
}

func TestHealthzIsUnauthenticated(t *testing.T) {
	server := httptest.NewServer(newTestHandler(t, &fakeStarter{}))
	defer server.Close()

	resp, err := http.Get(server.URL + "/healthz")
	if err != nil {
		t.Fatalf("GET /healthz: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
}

func TestNewStarterHTTPHandlerRequiresStarterAndToken(t *testing.T) {
	if _, err := NewStarterHTTPHandler(nil, "token"); err == nil {
		t.Error("NewStarterHTTPHandler() error = nil, want error for nil starter")
	}
	if _, err := NewStarterHTTPHandler(&fakeStarter{}, ""); err == nil {
		t.Error("NewStarterHTTPHandler() error = nil, want error for empty token")
	}
}

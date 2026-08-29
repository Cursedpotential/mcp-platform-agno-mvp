// Byline: Codex · GPT-5.6 · 2026-08-29 (opaque UIW preview HTTP contract tests)
package runtimeapi

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/require"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

type previewWorkflowStub struct {
	started  uiw.WorkflowInput
	decision uiw.PreviewDecision
	repair   uiw.RepairDecision
	state    uiw.PreviewState
	order    *[]string
}

func (s *previewWorkflowStub) Start(_ context.Context, in uiw.WorkflowInput) (string, string, error) {
	s.started = in
	return "workflow-1", "run-1", nil
}
func (s *previewWorkflowStub) Decide(_ context.Context, _ string, decision uiw.PreviewDecision) error {
	s.decision = decision
	return nil
}
func (s *previewWorkflowStub) DecideRepair(_ context.Context, _ string, decision uiw.RepairDecision) error {
	s.repair = decision
	if s.order != nil {
		*s.order = append(*s.order, "signal")
	}
	return nil
}
func (s *previewWorkflowStub) Preview(context.Context, string) (uiw.PreviewState, error) {
	return s.state, nil
}

type countingEntropy struct{ next byte }

type repairWriterStub struct {
	got   uiw.RepairDecisionSpec
	order *[]string
}

func (s *repairWriterStub) PersistRepairDecision(_ context.Context, spec uiw.RepairDecisionSpec) (uiw.Ref, error) {
	s.got = spec
	if s.order != nil {
		*s.order = append(*s.order, "persist")
	}
	return "66666666-6666-6666-6666-666666666666", nil
}

func (r *countingEntropy) Read(dest []byte) (int, error) {
	for index := range dest {
		dest[index] = r.next
		r.next++
	}
	return len(dest), nil
}

func previewTestHandler(t *testing.T) (*PreviewHTTPHandler, *MemoryPreviewStore, *previewWorkflowStub) {
	t.Helper()
	store := NewMemoryPreviewStore(&countingEntropy{next: 1})
	workflow := &previewWorkflowStub{state: uiw.PreviewState{
		Phase: uiw.PhaseAwaitingDecision, SelectRef: "selection-1", ParserOptionsRef: "options-1",
	}}
	handler, err := NewPreviewHTTPHandler(workflow, store, store, bytes.Repeat([]byte("k"), 32))
	require.NoError(t, err)
	return handler, store, workflow
}

func servePreview(handler http.Handler, method, target string, body []byte) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, target, bytes.NewReader(body))
	req.RemoteAddr = "100.64.1.9:3456"
	req.Header.Set("X-authentik-uid", "authentik-user-1")
	req.Header.Set("X-authentik-username", "operator")
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, req)
	return recorder
}

func startPreview(t *testing.T, handler *PreviewHTTPHandler) string {
	t.Helper()
	body := []byte(`{"request_id":"request-1","matter_id":"11111111-1111-1111-1111-111111111111","court_case_id":"22222222-2222-2222-2222-222222222222","source_ref":"upload://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","declared_format":"sms_xml","parser_options_ref":"options-1"}`)
	recorder := servePreview(handler.Routes(), http.MethodPost, "/reference-import/start", body)
	require.Equal(t, http.StatusCreated, recorder.Code, recorder.Body.String())
	var response struct {
		PreviewHandle string `json:"preview_handle"`
	}
	require.NoError(t, json.NewDecoder(recorder.Body).Decode(&response))
	require.Len(t, response.PreviewHandle, 32)
	return response.PreviewHandle
}

func putValidProjection(t *testing.T, store *MemoryPreviewStore, handle string) {
	t.Helper()
	snapshot := PreviewSnapshot{PreviewHandle: handle, Phase: "awaiting_decision", PreviewDigest: strings.Repeat("a", 64)}
	snapshot.Correlation.RequestID = "request-1"
	snapshot.Correlation.SourceVersionID = uuid.MustParse("33333333-3333-3333-3333-333333333333")
	snapshot.Correlation.RawGenerationID = uuid.MustParse("44444444-4444-4444-4444-444444444444")
	snapshot.Correlation.NormalizedGenerationID = uuid.MustParse("55555555-5555-5555-5555-555555555555")
	for i, kind := range receiptTypes {
		digest := sha256.Sum256([]byte(kind))
		snapshot.Receipts = append(snapshot.Receipts, PreviewReceipt{ReceiptType: kind, ReceiptRef: "receipt-" + kind, Status: "completed", Digest: fmtDigest(digest), RecordedAt: time.Unix(int64(i+1), 0).UTC()})
	}
	participant := PreviewParticipant{ParticipantID: "p-1", DisplayName: "Person One"}
	sender := "p-1"
	messages := []PreviewMessage{
		{MessageID: "m-2", Ordinal: 2, SenderParticipantID: &sender, Body: "second", ParticipantIDs: []string{"p-1"}, SourceLocatorRef: "locator-2"},
		{MessageID: "m-1", Ordinal: 1, SenderParticipantID: &sender, Body: "first", ParticipantIDs: []string{"p-1"}, SourceLocatorRef: "locator-1"},
	}
	event := PreviewEvent{EventID: 1, EventType: "messages_available", OccurredAt: time.Unix(10, 0).UTC(), PreviewHandle: handle, Phase: "awaiting_decision"}
	require.NoError(t, store.PutProjection(handle, snapshot, []PreviewParticipant{participant}, messages, []PreviewEvent{event}))
}

func fmtDigest(value [sha256.Size]byte) string {
	const alphabet = "0123456789abcdef"
	output := make([]byte, sha256.Size*2)
	for i, b := range value {
		output[i*2], output[i*2+1] = alphabet[b>>4], alphabet[b&15]
	}
	return string(output)
}

func TestPreviewSurfaceCorrelatesPagesDecisionsAndReplay(t *testing.T) {
	handler, store, workflow := previewTestHandler(t)
	handle := startPreview(t, handler)

	notReady := servePreview(handler.Routes(), http.MethodGet, "/reference-import/previews/"+handle, nil)
	require.Equal(t, http.StatusConflict, notReady.Code)
	putValidProjection(t, store, handle)

	snapshot := servePreview(handler.Routes(), http.MethodGet, "/reference-import/previews/"+handle, nil)
	require.Equal(t, http.StatusOK, snapshot.Code)
	require.Contains(t, snapshot.Body.String(), `"preview_handle":"`+handle+`"`)

	page1 := servePreview(handler.Routes(), http.MethodGet, "/reference-import/previews/"+handle+"/messages?limit=1", nil)
	require.Equal(t, http.StatusOK, page1.Code)
	var page struct {
		Messages   []PreviewMessage `json:"messages"`
		NextCursor string           `json:"next_cursor"`
	}
	require.NoError(t, json.NewDecoder(page1.Body).Decode(&page))
	require.Equal(t, "m-1", page.Messages[0].MessageID)
	require.NotEmpty(t, page.NextCursor)

	other := startPreview(t, handler)
	crossHandle := servePreview(handler.Routes(), http.MethodGet, "/reference-import/previews/"+other+"/messages?cursor="+page.NextCursor, nil)
	require.Equal(t, http.StatusUnprocessableEntity, crossHandle.Code)

	decisionBody := []byte(`{"approved":true,"reason":""}`)
	decision := servePreview(handler.Routes(), http.MethodPost, "/reference-import/previews/"+handle+"/decision", decisionBody)
	require.Equal(t, http.StatusOK, decision.Code, decision.Body.String())
	require.Equal(t, "authentik-user-1", workflow.decision.Decider)

	req := httptest.NewRequest(http.MethodGet, "/reference-import/previews/"+handle+"/events", nil)
	req.RemoteAddr = "100.64.1.9:3456"
	req.Header.Set("Last-Event-ID", "0")
	events := httptest.NewRecorder()
	handler.Routes().ServeHTTP(events, req)
	require.Equal(t, http.StatusOK, events.Code)
	require.Contains(t, events.Header().Get("Content-Type"), "text/event-stream")
	require.Contains(t, events.Body.String(), "id: 1")
	require.Contains(t, events.Body.String(), "id: 2")
}

func TestPreviewSurfaceFailsClosedOnAuthUnknownHandleAndEventGap(t *testing.T) {
	handler, _, _ := previewTestHandler(t)
	unauthorized := httptest.NewRecorder()
	handler.Routes().ServeHTTP(unauthorized, httptest.NewRequest(http.MethodGet, "/reference-import/previews/unknown", nil))
	require.Equal(t, http.StatusUnauthorized, unauthorized.Code)

	unknown := servePreview(handler.Routes(), http.MethodGet, "/reference-import/previews/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", nil)
	require.Equal(t, http.StatusNotFound, unknown.Code)

	handle := startPreview(t, handler)
	req := httptest.NewRequest(http.MethodGet, "/reference-import/previews/"+handle+"/events", nil)
	req.RemoteAddr = "100.64.1.9:3456"
	req.Header.Set("Last-Event-ID", "99")
	recorder := httptest.NewRecorder()
	handler.Routes().ServeHTTP(recorder, req)
	require.Equal(t, http.StatusConflict, recorder.Code)
}

func TestRepairDecisionIsPersistedByUIWBeforeTemporalSignal(t *testing.T) {
	store := NewMemoryPreviewStore(&countingEntropy{next: 1})
	order := []string{}
	workflow := &previewWorkflowStub{order: &order, state: uiw.PreviewState{
		Phase:               uiw.PhaseAwaitingRepairDecision,
		SourceVersionRef:    "33333333-3333-3333-3333-333333333333",
		RepairAssessmentRef: "44444444-4444-4444-4444-444444444444",
	}}
	writer := &repairWriterStub{order: &order}
	handler, err := NewPreviewHTTPHandler(workflow, store, writer, bytes.Repeat([]byte("k"), 32))
	require.NoError(t, err)
	handle := startPreview(t, handler)
	req := httptest.NewRequest(http.MethodPost, "/reference-import/previews/"+handle+"/repair-decision", strings.NewReader(`{"approved":true,"apply_repair":false,"tool_payload":{}}`))
	req.RemoteAddr = "100.64.1.9:3456"
	req.Header.Set("X-authentik-uid", "authentik-subject-1")
	req.Header.Set("X-authentik-username", "operator")
	req.Header.Set("Idempotency-Key", "repair-choice-1")
	recorder := httptest.NewRecorder()
	handler.Routes().ServeHTTP(recorder, req)
	require.Equal(t, http.StatusOK, recorder.Code, recorder.Body.String())
	require.Equal(t, []string{"persist", "signal"}, order)
	require.Equal(t, uiw.Ref("authentik-subject-1"), writer.got.ActorRef)
	require.Equal(t, uiw.Ref("66666666-6666-6666-6666-666666666666"), workflow.repair.DecisionRef)
}

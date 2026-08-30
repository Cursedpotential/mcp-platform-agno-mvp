package temporal

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/mock"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// This file proves this package's real N8NActivities correctly plug into
// the real engine/uiw.UniversalImportWorkflow end to end: the other 21
// stages are mocked (exactly like engine/uiw's own test suite does — this
// package does not own their bodies), but select_parser_activity and
// execute_parser_activity are this package's actual production code,
// exercised against real httptest servers standing in for n8n. That is what
// distinguishes this from engine/uiw/workflow_test.go's own hold tests
// (which mock every stage, including the two n8n-backed ones) and from this
// package's n8n_client_test.go/activities_test.go (which exercise the real
// HTTP client but never inside the real workflow).

// placeholderStageActivity exists only so the TestWorkflowEnvironment has a
// function signature to register the 21 non-parser canon stage names
// against; every test below mocks it via OnActivity before executing the
// workflow (mirrors engine/uiw/workflow_test.go's own placeholderActivity
// pattern, reproduced locally since it is unexported there).
func placeholderStageActivity(_ context.Context, _ uiw.StageRequest) (uiw.StageResult, error) {
	return uiw.StageResult{Status: uiw.StatusFailed, Reason: "integration test: placeholder activity ran unmocked", ReceiptRef: "placeholder-receipt"}, nil
}

func stageStub(id stagegraph.StageID) uiw.StageResult {
	return uiw.StageResult{Status: uiw.StatusSuccess, Ref: uiw.Ref(string(id) + "-ref"), ReceiptRef: uiw.Ref(string(id) + "-receipt")}
}

// registerRealActivities registers this package's real N8NActivities (Client
// pointed at the given fake n8n base URL) under select_parser_activity and
// execute_parser_activity, and every other canon stage against the
// unmocked-is-an-error placeholder, then stubs every non-parser stage to
// succeed via OnActivity.
func registerRealActivities(t *testing.T, env *testsuite.TestWorkflowEnvironment, n8nBaseURL string) {
	t.Helper()
	client, err := NewN8NClient(Config{
		N8NBaseURL: n8nBaseURL, N8NAuthHeader: "Authorization", N8NAuthValue: "Bearer test-token",
		SelectHTTPTimeout: 5 * time.Second, ExecuteHTTPTimeout: 5 * time.Second,
	})
	if err != nil {
		t.Fatalf("NewN8NClient() error = %v", err)
	}
	acts := N8NActivities{Client: client}
	env.RegisterActivityWithOptions(acts.SelectParser, activity.RegisterOptions{Name: string(stagegraph.SelectParser)})
	env.RegisterActivityWithOptions(acts.ExecuteParser, activity.RegisterOptions{Name: string(stagegraph.ExecuteParser)})

	for _, d := range stagegraph.Stages {
		if d.ID == stagegraph.SelectParser || d.ID == stagegraph.ExecuteParser {
			continue
		}
		env.RegisterActivityWithOptions(placeholderStageActivity, activity.RegisterOptions{Name: string(d.ID)})
	}
	for _, d := range stagegraph.Stages {
		if d.ID == stagegraph.SelectParser || d.ID == stagegraph.ExecuteParser {
			continue
		}
		env.OnActivity(string(d.ID), mock.Anything, mock.Anything).Return(stageStub(d.ID), nil).Once()
	}
}

func integrationInput() uiw.WorkflowInput {
	return uiw.WorkflowInput{
		RequestID: "req-1", SourceRef: "acquisition-ref",
		MatterID: "11111111-1111-1111-1111-111111111111", CourtCaseID: "22222222-2222-2222-2222-222222222222",
		DeclaredFormat: "whatsapp_export_json", ParserOptionsRef: "parser-options-ref",
	}
}

// fakeN8N stands in for the two n8n webhooks this package's Activities call.
// selectCalls/executeCalls count real invocations so tests can assert the
// parser HTTP call never happened on rejection.
type fakeN8N struct {
	server       *httptest.Server
	selectCalls  int32
	executeCalls int32
}

func newFakeN8N(t *testing.T) *fakeN8N {
	t.Helper()
	f := &fakeN8N{}
	mux := http.NewServeMux()
	mux.HandleFunc("/universal-import/select-parser-activity", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&f.selectCalls, 1)
		writeFakeStageResult(w, "select_parser_activity", "selection-ref", "selection-receipt")
	})
	mux.HandleFunc("/universal-import/execute-parser-activity", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&f.executeCalls, 1)
		writeFakeStageResult(w, "execute_parser_activity", "execute-ref", "execute-receipt")
	})
	f.server = httptest.NewServer(mux)
	return f
}

func writeFakeStageResult(w http.ResponseWriter, stage, ref, receiptRef string) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"stage": stage, "status": "success", "ref": ref, "receipt_ref": receiptRef,
	})
}

func TestIntegrationApprovedRunsAllStagesAndCallsRealParserHTTP(t *testing.T) {
	n8n := newFakeN8N(t)
	defer n8n.server.Close()

	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	env.RegisterWorkflow(uiw.UniversalImportWorkflow)
	registerRealActivities(t, env, n8n.server.URL)

	env.RegisterDelayedCallback(func() {
		env.SignalWorkflow(uiw.RepairDecisionSignalName, uiw.RepairDecision{DecisionRef: "repair-decision-ref"})
		env.SignalWorkflow(uiw.PreviewDecisionSignalName, uiw.PreviewDecision{Approved: true, Decider: "operator-1"})
	}, time.Millisecond)

	env.ExecuteWorkflow(uiw.UniversalImportWorkflow, integrationInput())

	if !env.IsWorkflowCompleted() {
		t.Fatal("workflow did not complete")
	}
	if err := env.GetWorkflowError(); err != nil {
		t.Fatalf("workflow returned error on the approved path: %v", err)
	}
	var result uiw.WorkflowResult
	if err := env.GetWorkflowResult(&result); err != nil {
		t.Fatalf("GetWorkflowResult failed: %v", err)
	}
	if result.Status != uiw.StatusSuccess {
		t.Errorf("result.Status = %q, want %q", result.Status, uiw.StatusSuccess)
	}
	if len(result.Stages) != len(stagegraph.Stages) {
		t.Errorf("result.Stages has %d entries, want %d (every stage exactly once)", len(result.Stages), len(stagegraph.Stages))
	}
	if got := atomic.LoadInt32(&n8n.selectCalls); got != 1 {
		t.Errorf("fake n8n select endpoint called %d times, want exactly 1", got)
	}
	if got := atomic.LoadInt32(&n8n.executeCalls); got != 1 {
		t.Errorf("fake n8n execute endpoint called %d times, want exactly 1 before normalized preview approval", got)
	}
}

func TestIntegrationRejectedNeverCallsRealParserHTTP(t *testing.T) {
	n8n := newFakeN8N(t)
	defer n8n.server.Close()

	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	env.RegisterWorkflow(uiw.UniversalImportWorkflow)
	registerRealActivities(t, env, n8n.server.URL)

	env.RegisterDelayedCallback(func() {
		env.SignalWorkflow(uiw.RepairDecisionSignalName, uiw.RepairDecision{DecisionRef: "repair-decision-ref"})
		env.SignalWorkflow(uiw.PreviewDecisionSignalName, uiw.PreviewDecision{Approved: false, Reason: "wrong format", Decider: "operator-1"})
	}, time.Millisecond)

	env.ExecuteWorkflow(uiw.UniversalImportWorkflow, integrationInput())

	if !env.IsWorkflowCompleted() {
		t.Fatal("workflow did not complete")
	}
	if err := env.GetWorkflowError(); err == nil {
		t.Fatal("workflow returned nil error after a rejected preview decision; fail-closed requires an error")
	}
	if got := atomic.LoadInt32(&n8n.selectCalls); got != 1 {
		t.Errorf("fake n8n select endpoint called %d times, want exactly 1 (selection must still run before the hold)", got)
	}
	if got := atomic.LoadInt32(&n8n.executeCalls); got != 1 {
		t.Errorf("fake n8n execute endpoint called %d times, want 1 — normalized preview must exist before rejection", got)
	}
}

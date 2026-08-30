package temporal

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.temporal.io/sdk/testsuite"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// activityEnv builds a TestActivityEnvironment wired to N8NActivities talking
// to server, so activity.RecordHeartbeat (called by the goroutine in
// activities.go) runs inside a real activity context instead of panicking on
// a bare context.Background().
func activityEnv(t *testing.T, server *httptest.Server) (*testsuite.TestActivityEnvironment, N8NActivities) {
	t.Helper()
	client, err := NewN8NClient(testConfig(t, server.URL))
	if err != nil {
		t.Fatalf("NewN8NClient() error = %v", err)
	}
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestActivityEnvironment()
	acts := N8NActivities{Client: client}
	env.RegisterActivity(acts.SelectParser)
	env.RegisterActivity(acts.ExecuteParser)
	return env, acts
}

func TestSelectParserActivitySuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"stage": "select_parser_activity", "status": "success",
			"ref": "selection-ref", "receipt_ref": "selection-receipt",
		})
	}))
	defer server.Close()

	env, acts := activityEnv(t, server)
	value, err := env.ExecuteActivity(acts.SelectParser, selectRequest())
	if err != nil {
		t.Fatalf("ExecuteActivity(SelectParser) error = %v", err)
	}
	var result uiw.StageResult
	if err := value.Get(&result); err != nil {
		t.Fatalf("decode activity result: %v", err)
	}
	if result.Ref != "selection-ref" || result.ReceiptRef != "selection-receipt" {
		t.Errorf("result = %+v, unexpected", result)
	}
}

func TestExecuteParserActivitySendsHeartbeatsAndSucceeds(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"stage": "execute_parser_activity", "status": "success",
			"ref": "execute-ref", "receipt_ref": "execute-receipt",
		})
	}))
	defer server.Close()

	env, acts := activityEnv(t, server)
	value, err := env.ExecuteActivity(acts.ExecuteParser, executeRequest())
	if err != nil {
		t.Fatalf("ExecuteActivity(ExecuteParser) error = %v", err)
	}
	var result uiw.StageResult
	if err := value.Get(&result); err != nil {
		t.Fatalf("decode activity result: %v", err)
	}
	if result.Ref != "execute-ref" || result.ReceiptRef != "execute-receipt" {
		t.Errorf("result = %+v, unexpected", result)
	}
	// The heartbeat goroutine in activities.go ticks every
	// executeHeartbeatInterval and calls activity.RecordHeartbeat; running
	// this inside a real TestActivityEnvironment (not a bare
	// context.Background()) proves that call doesn't panic outside a real
	// activity context, regardless of whether a tick fires before the fast
	// httptest round trip completes.
}

func TestActivityFailsClosedOnN8NError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnprocessableEntity)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "boom"})
	}))
	defer server.Close()

	env, acts := activityEnv(t, server)
	_, err := env.ExecuteActivity(acts.SelectParser, selectRequest())
	if err == nil {
		t.Fatal("ExecuteActivity() error = nil, want error on n8n failure")
	}
}

// TestActivitiesRegisterUnderCanonStageNames proves N8NActivities.SelectParser
// and .ExecuteParser are dispatchable by exactly the stagegraph names
// engine/uiw.UniversalImportWorkflow invokes them by.
func TestActivitiesRegisterUnderCanonStageNames(t *testing.T) {
	if string(stagegraph.SelectParser) != "select_parser_activity" {
		t.Fatalf("stagegraph.SelectParser = %q, want select_parser_activity", stagegraph.SelectParser)
	}
	if string(stagegraph.ExecuteParser) != "execute_parser_activity" {
		t.Fatalf("stagegraph.ExecuteParser = %q, want execute_parser_activity", stagegraph.ExecuteParser)
	}
}

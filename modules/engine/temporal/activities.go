package temporal

import (
	"context"
	"time"

	"go.temporal.io/sdk/activity"

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

// executeHeartbeatInterval is how often ExecuteParser records a Temporal
// heartbeat while blocked on the n8n HTTP call. engine/proffer's ActivityOptions
// for execute_parser_activity carry a 1-minute HeartbeatTimeout (its HTTP
// leg can run up to ~31 minutes), so this must stay comfortably under that.
// select_parser_activity carries no HeartbeatTimeout at all, so a heartbeat
// recorded there is simply a no-op.
const executeHeartbeatInterval = 20 * time.Second

// N8NActivities implements the two n8n-backed Temporal Activity bodies for
// engine/proffer.ProfferWorkflow: select_parser_activity and
// execute_parser_activity. Both are plain synchronous Activities — the human
// preview hold between them is a real Signal + Query + Timer inside
// ProfferWorkflow itself (engine/proffer/preview.go,
// engine/proffer/workflow.go), not anything implemented here. By the time
// execute_parser_activity is scheduled, the workflow has already resolved
// the hold: this Activity only ever runs on an approved decision.
type N8NActivities struct {
	Client *N8NClient
}

// SelectParser is the select_parser_activity body: a synchronous HTTP proxy
// to the n8n select workflow.
func (a N8NActivities) SelectParser(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	return a.Client.CallStage(ctx, stagegraph.SelectParser, req)
}

// ExecuteParser is the execute_parser_activity body: a synchronous,
// heartbeating HTTP proxy to the n8n execute workflow.
func (a N8NActivities) ExecuteParser(ctx context.Context, req proffer.StageRequest) (proffer.StageResult, error) {
	stop := make(chan struct{})
	defer close(stop)
	go func() {
		ticker := time.NewTicker(executeHeartbeatInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				activity.RecordHeartbeat(ctx, "waiting on n8n execute_parser_activity")
			case <-stop:
				return
			}
		}
	}()
	return a.Client.CallStage(ctx, stagegraph.ExecuteParser, req)
}

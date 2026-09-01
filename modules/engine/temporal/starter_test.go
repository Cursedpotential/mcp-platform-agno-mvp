package temporal

import (
	"fmt"
	"testing"

	"go.temporal.io/api/serviceerror"
)

func TestAlreadyStartedRunIDRecoversExistingExecution(t *testing.T) {
	runID, ok := alreadyStartedRunID(fmt.Errorf("wrapped: %w", &serviceerror.WorkflowExecutionAlreadyStarted{RunId: "run-existing"}))
	if !ok || runID != "run-existing" {
		t.Fatalf("runID=%q ok=%v", runID, ok)
	}
}

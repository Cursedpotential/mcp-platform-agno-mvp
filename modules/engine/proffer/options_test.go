package uiw

import (
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
)

func TestEveryStageHasExplicitBoundedOptions(t *testing.T) {
	for _, d := range stagegraph.Stages {
		opts, ok := stageOptions[d.ID]
		if !ok {
			t.Fatalf("stage %q has no ActivityOptions entry", d.ID)
		}
		if opts.StartToCloseTimeout <= 0 {
			t.Errorf("stage %q has non-positive StartToCloseTimeout %v", d.ID, opts.StartToCloseTimeout)
		}
		if opts.RetryPolicy == nil {
			t.Fatalf("stage %q has no RetryPolicy", d.ID)
		}
		if opts.RetryPolicy.MaximumAttempts <= 0 {
			t.Errorf("stage %q has MaximumAttempts=%d; 0 means unlimited retries, which is not bounded", d.ID, opts.RetryPolicy.MaximumAttempts)
		}
	}

	if len(stageOptions) != len(stagegraph.Stages) {
		t.Errorf("stageOptions has %d entries, want exactly %d (one per registered stage, no strays)", len(stageOptions), len(stagegraph.Stages))
	}
}

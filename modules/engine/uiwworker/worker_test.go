package uiwworker

import (
	"testing"

	"go.temporal.io/sdk/activity"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
)

type registrationRecorder struct {
	workflowCount int
	names         []string
}

func (r *registrationRecorder) RegisterWorkflow(interface{}) { r.workflowCount++ }

func (r *registrationRecorder) RegisterActivityWithOptions(_ interface{}, options activity.RegisterOptions) {
	r.names = append(r.names, options.Name)
}

func TestRegisterAllRegistersCanonicalStagesAndReplayAliasesExactlyOnce(t *testing.T) {
	recorder := &registrationRecorder{}
	RegisterAll(recorder, Registrations{})
	if recorder.workflowCount != 1 {
		t.Fatalf("workflow registration count = %d, want 1", recorder.workflowCount)
	}
	const replayAliasCount = 3
	if len(recorder.names) != len(stagegraph.Stages)+replayAliasCount || len(stagegraph.Stages) != 26 {
		t.Fatalf("activity registration count = %d, want 26 canonical + 3 replay aliases", len(recorder.names))
	}
	registered := make(map[string]int, len(recorder.names))
	for _, name := range recorder.names {
		registered[name]++
	}
	for _, descriptor := range stagegraph.Stages {
		if registered[string(descriptor.ID)] != 1 {
			t.Errorf("canonical stage %q registered %d times", descriptor.ID, registered[string(descriptor.ID)])
		}
	}
	for _, alias := range []string{"hash_source_activity", "hash_raw_records_activity", "hash_raw_generation_activity"} {
		if registered[alias] != 1 {
			t.Errorf("replay alias %q registered %d times", alias, registered[alias])
		}
	}
	for name, count := range registered {
		if count != 1 {
			t.Errorf("activity name %q registered %d times", name, count)
		}
	}
}

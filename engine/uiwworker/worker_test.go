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

func TestRegisterAllRegistersOneWorkflowAndAllExact23Stages(t *testing.T) {
	recorder := &registrationRecorder{}
	RegisterAll(recorder, Registrations{})
	if recorder.workflowCount != 1 {
		t.Fatalf("workflow registration count = %d, want 1", recorder.workflowCount)
	}
	if len(recorder.names) != len(stagegraph.Stages) || len(recorder.names) != 23 {
		t.Fatalf("activity registration count = %d, want exact 23", len(recorder.names))
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
	for name, count := range registered {
		if count != 1 {
			t.Errorf("activity name %q registered %d times", name, count)
		}
	}
}

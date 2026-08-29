package activities

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

type repairClientStub struct {
	calls    []string
	payloads []map[string]any
}

func (c *repairClientStub) Run(_ context.Context, id string, payload map[string]any) (json.RawMessage, error) {
	c.calls = append(c.calls, id)
	c.payloads = append(c.payloads, payload)
	return json.RawMessage(`{"ok":true}`), nil
}

type repairStoreStub struct {
	decision               RepairDecisionRecord
	assessment, resolution RepairPersistenceResult
}

func (s *repairStoreStub) ResolveOriginalPath(context.Context, uiw.Ref, uiw.Ref) (string, error) {
	return "/r2/source.pdf", nil
}
func (s *repairStoreStub) PersistRepairAssessment(context.Context, RepairAssessmentSpec) (RepairPersistenceResult, error) {
	return s.assessment, nil
}
func (s *repairStoreStub) LoadApprovedRepairDecision(context.Context, uiw.Ref, uiw.Ref, uiw.Ref) (RepairDecisionRecord, error) {
	return s.decision, nil
}
func (s *repairStoreStub) PersistRepairResolution(context.Context, RepairResolutionSpec) (RepairPersistenceResult, error) {
	return s.resolution, nil
}

func repairRequest(refs map[string]uiw.Ref) uiw.StageRequest {
	return uiw.StageRequest{RequestID: "req", SourceVersionRef: "source", DeclaredFormat: "pdf", Refs: refs}
}

func TestAssessSourceRepairCallsExistingCapabilitiesAndReturnsOnlyRefs(t *testing.T) {
	client := &repairClientStub{}
	store := &repairStoreStub{assessment: RepairPersistenceResult{ResultRef: "assessment", ReceiptRef: "receipt"}}
	result, err := (RepairActivities{Client: client, Store: store}).AssessSourceRepair(t.Context(), repairRequest(map[string]uiw.Ref{"original": "original"}))
	if err != nil {
		t.Fatal(err)
	}
	if len(client.calls) != 2 || client.calls[0] != RepairDetectTool || client.calls[1] != RepairPreviewTool {
		t.Fatalf("calls=%v", client.calls)
	}
	if result.Ref != "assessment" || result.ReceiptRef != "receipt" {
		t.Fatalf("result=%+v", result)
	}
}

func TestResolveSourceRepairFailsClosedWithoutExactApproval(t *testing.T) {
	store := &repairStoreStub{decision: RepairDecisionRecord{DecisionRef: "decision", ActorRef: "actor", Approved: false}, resolution: RepairPersistenceResult{ResultRef: "derived", ReceiptRef: "receipt"}}
	_, err := (RepairActivities{Client: &repairClientStub{}, Store: store}).ResolveSourceRepair(t.Context(), repairRequest(map[string]uiw.Ref{"original": "original", "repair_assessment": "assessment", "repair_decision": "decision"}))
	if err == nil {
		t.Fatal("unapproved repair decision was accepted")
	}
}

func TestResolveSourceRepairInjectsManualApprovalOnlyAfterStoredDecision(t *testing.T) {
	client := &repairClientStub{}
	store := &repairStoreStub{decision: RepairDecisionRecord{DecisionRef: "decision", ActorRef: "actor", Approved: true, ApplyRepair: true, ToolID: "repair.pdf-derived", Payload: map[string]any{"path": "/r2/source.pdf", "dest": "/r2/derived.pdf", "artifact_root": "/r2"}}, resolution: RepairPersistenceResult{ResultRef: "derived-original", ReceiptRef: "receipt"}}
	result, err := (RepairActivities{Client: client, Store: store}).ResolveSourceRepair(t.Context(), repairRequest(map[string]uiw.Ref{"original": "original", "repair_assessment": "assessment", "repair_decision": "decision"}))
	if err != nil {
		t.Fatal(err)
	}
	if result.Ref != "derived-original" || len(client.calls) != 1 {
		t.Fatalf("result=%+v calls=%v", result, client.calls)
	}
	if client.payloads[0]["_execution_mode"] != "manual" || client.payloads[0]["approved"] != true {
		t.Fatalf("payload=%v", client.payloads[0])
	}
}

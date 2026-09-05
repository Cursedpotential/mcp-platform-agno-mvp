package activities

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

const (
	RepairDetectTool  = "repair.detect"
	RepairPreviewTool = "repair.preview"
)

var allowedDerivedRepairTools = map[string]bool{
	"repair.write-derived": true,
	"repair.pdf-derived":   true,
}

// RepairToolClient executes an already-registered platform-tools capability
// THROUGH THE TOOL GATEWAY (D-132). The source is named by LOCATOR, never by a
// host path: this Activity and platform-tools run on different hosts, and a
// worker-local path is exactly the defect the gateway was built to remove.
// Results are persisted by RepairActivityStore and never returned to Temporal.
type RepairToolClient interface {
	Run(ctx context.Context, toolID string, sourceRef uiw.Ref, args map[string]any) (json.RawMessage, error)
}

type RepairDecisionRecord struct {
	DecisionRef uiw.Ref
	ActorRef    uiw.Ref
	Approved    bool
	ApplyRepair bool
	ToolID      string
	Payload     map[string]any
}

type RepairAssessmentSpec struct {
	RequestID, DeclaredFormat     string
	SourceVersionRef, OriginalRef uiw.Ref
	Attempt                       int32
	IdempotencyKey                string
	Detection, Preview            json.RawMessage
	ReviewRequired                bool
}

type RepairResolutionSpec struct {
	RequestID, DeclaredFormat                                           string
	SourceVersionRef, OriginalRef, AssessmentRef, DecisionRef, ActorRef uiw.Ref
	Attempt                                                             int32
	IdempotencyKey, ToolID                                              string
	Applied                                                             bool
	ToolResult                                                          json.RawMessage
}

type RepairPersistenceResult struct {
	ResultRef, ReceiptRef uiw.Ref
	ReviewRequired        bool
}

// RepairActivityStore owns locator resolution, immutable assessment storage,
// approval revalidation, and the exact activity receipt/idempotency boundary.
type RepairActivityStore interface {
	LoadPersistedRepairAssessment(context.Context, RepairAssessmentSpec) (RepairPersistenceResult, bool, error)
	PersistRepairAssessment(context.Context, RepairAssessmentSpec) (RepairPersistenceResult, error)
	LoadApprovedRepairDecision(context.Context, uiw.Ref, uiw.Ref, uiw.Ref) (RepairDecisionRecord, error)
	PersistRepairResolution(context.Context, RepairResolutionSpec) (RepairPersistenceResult, error)
	PersistAutomaticRepairResolution(context.Context, RepairResolutionSpec) (RepairPersistenceResult, error)
}

type RepairActivities struct {
	Client  RepairToolClient
	Store   RepairActivityStore
	Attempt Attempt
}

func (a RepairActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

func (a RepairActivities) validate() error {
	if a.Client == nil {
		return errors.New("repair activities: platform-tools client is required")
	}
	if a.Store == nil {
		return errors.New("repair activities: store is required")
	}
	return nil
}

func (a RepairActivities) AssessSourceRepair(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	original, err := repairRef(req, "original")
	if err != nil {
		return uiw.StageResult{}, err
	}
	idempotencyKey := fmt.Sprintf("repair-assessment:%s:%s:%s", req.RequestID, req.SourceVersionRef, original)
	prior, found, err := a.Store.LoadPersistedRepairAssessment(ctx, RepairAssessmentSpec{
		RequestID: req.RequestID, DeclaredFormat: req.DeclaredFormat,
		SourceVersionRef: req.SourceVersionRef, OriginalRef: original, IdempotencyKey: idempotencyKey,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("load persisted repair assessment: %w", err)
	}
	if found {
		return repairAssessmentResult(prior)
	}
	// The retained original travels as a LOCATOR. The gateway resolves it
	// through the shared acquisition router and materializes the bytes where
	// the tool can actually read them.
	detection, err := a.Client.Run(ctx, RepairDetectTool, original, nil)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("run repair detection: %w", err)
	}
	preview, err := a.Client.Run(ctx, RepairPreviewTool, original, map[string]any{"format": req.DeclaredFormat, "sample_limit": 25})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("run repair preview: %w", err)
	}
	reviewRequired := RepairReviewRequired(detection, preview)
	result, err := a.Store.PersistRepairAssessment(ctx, RepairAssessmentSpec{
		RequestID: req.RequestID, DeclaredFormat: req.DeclaredFormat,
		SourceVersionRef: req.SourceVersionRef, OriginalRef: original,
		Attempt: a.attempt(ctx), IdempotencyKey: idempotencyKey,
		Detection: append(json.RawMessage(nil), detection...), Preview: append(json.RawMessage(nil), preview...), ReviewRequired: reviewRequired,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("persist repair assessment: %w", err)
	}
	return repairAssessmentResult(result)
}

func (a RepairActivities) ResolveSourceRepair(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	original, err := repairRef(req, "original")
	if err != nil {
		return uiw.StageResult{}, err
	}
	assessment, err := repairRef(req, "repair_assessment")
	if err != nil {
		return uiw.StageResult{}, err
	}
	if req.Refs["auto_clean_assessment"] == assessment {
		result, persistErr := a.Store.PersistAutomaticRepairResolution(ctx, RepairResolutionSpec{
			RequestID: req.RequestID, DeclaredFormat: req.DeclaredFormat, SourceVersionRef: req.SourceVersionRef,
			OriginalRef: original, AssessmentRef: assessment, ActorRef: "uiw:auto-clean",
			Attempt: a.attempt(ctx), IdempotencyKey: fmt.Sprintf("repair-resolution:auto-clean:%s:%s", req.RequestID, assessment),
		})
		if persistErr != nil {
			return uiw.StageResult{}, fmt.Errorf("persist automatic repair resolution: %w", persistErr)
		}
		return repairSuccess(stagegraph.ResolveSourceRepair, result)
	}
	decisionRef, err := repairRef(req, "repair_decision")
	if err != nil {
		return uiw.StageResult{}, err
	}
	decision, err := a.Store.LoadApprovedRepairDecision(ctx, req.SourceVersionRef, assessment, decisionRef)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("load repair decision: %w", err)
	}
	if !decision.Approved || decision.DecisionRef != decisionRef || decision.ActorRef == "" {
		return uiw.StageResult{}, errors.New("repair decision is not an exact approved actor-bound decision")
	}
	var toolResult json.RawMessage
	if decision.ApplyRepair {
		if !allowedDerivedRepairTools[decision.ToolID] {
			return uiw.StageResult{}, fmt.Errorf("repair tool %q is not an approved derived-write capability", decision.ToolID)
		}
		payload := make(map[string]any, len(decision.Payload)+2)
		for key, value := range decision.Payload {
			payload[key] = value
		}
		// A persisted human decision chooses the operation and safe destination,
		// never a replacement source. The source is rebound to the governed
		// retained-object LOCATOR immediately before execution, so a stored
		// "path" from an older decision can never reach a tool.
		delete(payload, "path")
		payload["_execution_mode"] = "manual"
		payload["approved"] = true
		toolResult, err = a.Client.Run(ctx, decision.ToolID, original, payload)
		if err != nil {
			return uiw.StageResult{}, fmt.Errorf("run approved derived repair: %w", err)
		}
	} else if decision.ToolID != "" || len(decision.Payload) != 0 {
		return uiw.StageResult{}, errors.New("use-original repair decision must not carry a tool or payload")
	}
	result, err := a.Store.PersistRepairResolution(ctx, RepairResolutionSpec{
		RequestID: req.RequestID, DeclaredFormat: req.DeclaredFormat, SourceVersionRef: req.SourceVersionRef,
		OriginalRef: original, AssessmentRef: assessment, DecisionRef: decisionRef, ActorRef: decision.ActorRef,
		Attempt: a.attempt(ctx), IdempotencyKey: fmt.Sprintf("repair-resolution:%s:%s:%s", req.RequestID, req.SourceVersionRef, decisionRef),
		ToolID: decision.ToolID, Applied: decision.ApplyRepair, ToolResult: append(json.RawMessage(nil), toolResult...),
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("persist repair resolution: %w", err)
	}
	return repairSuccess(stagegraph.ResolveSourceRepair, result)
}

func repairRef(req uiw.StageRequest, name string) (uiw.Ref, error) {
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return "", errors.New("repair activity requires request and source version references")
	}
	ref := req.Refs[name]
	if ref == "" {
		return "", fmt.Errorf("repair activity requires non-empty %q reference", name)
	}
	return ref, nil
}

func repairSuccess(stage stagegraph.StageID, result RepairPersistenceResult) (uiw.StageResult, error) {
	return repairResult(stage, result, uiw.StatusSuccess)
}

func repairAssessmentResult(result RepairPersistenceResult) (uiw.StageResult, error) {
	status := uiw.StatusSuccess
	if !result.ReviewRequired {
		status = uiw.StatusNotApplicable
	}
	return repairResult(stagegraph.AssessSourceRepair, result, status)
}

func repairResult(stage stagegraph.StageID, result RepairPersistenceResult, status uiw.Status) (uiw.StageResult, error) {
	if result.ResultRef == "" || result.ReceiptRef == "" {
		return uiw.StageResult{}, errors.New("repair persistence returned incomplete compact references")
	}
	return uiw.StageResult{Stage: stage, Status: status, Ref: result.ResultRef, ReceiptRef: result.ReceiptRef}, nil
}

// RepairReviewRequired derives the fail-closed human-review requirement from
// detector output. The PostgreSQL store deliberately reuses this function
// when an Activity retry encounters an already-persisted assessment so the
// durable assessment, rather than a fresh tool response, remains authoritative.
func RepairReviewRequired(values ...json.RawMessage) bool {
	explicitClean := false
	for _, raw := range values {
		var object map[string]any
		if json.Unmarshal(raw, &object) != nil {
			return true
		}
		for _, key := range []string{"review_required", "needs_repair", "repair_required"} {
			if value, ok := object[key].(bool); ok {
				if value {
					return true
				}
				explicitClean = true
			}
		}
	}
	return !explicitClean
}

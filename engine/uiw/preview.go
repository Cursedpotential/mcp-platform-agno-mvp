package uiw

import "time"

// PreviewDecisionSignalName is the Signal UniversalImportWorkflow listens on
// between select_parser_activity and execute_parser_activity: a human
// operator's approve/reject decision on the persisted parser selection.
// This is a real Temporal Signal, not an Activity-level trick, precisely so
// the hold survives a worker restart or a replica change — Temporal replays
// this workflow's own durable history, not any single worker's in-memory
// state.
const PreviewDecisionSignalName = "preview_decision"

// PreviewQueryName is the Query a caller uses to read the current hold state
// (see PreviewState) while UniversalImportWorkflow is waiting on
// PreviewDecisionSignalName. Queries, like Signals, are served from the
// workflow's own history/state and work against any worker, and even after
// the workflow has closed (within retention).
const PreviewQueryName = "preview"

// previewDecisionTimeout bounds how long the hold waits for
// PreviewDecisionSignalName before failing the run closed. This is a real
// Temporal Timer (workflow.NewTimer), backed by the Temporal server itself —
// not bounded by any Activity's StartToCloseTimeout — so it is independent
// of engine/uiw/options.go's per-stage Activity timeouts.
const previewDecisionTimeout = 24 * time.Hour

// PreviewPhase is the human-readable lifecycle position of the preview
// hold, as reported by PreviewState.
type PreviewPhase string

const (
	PhaseAwaitingDecision PreviewPhase = "awaiting_decision"
	PhaseApproved         PreviewPhase = "approved"
	PhaseRejected         PreviewPhase = "rejected"
	PhaseTimedOut         PreviewPhase = "timed_out"
)

// PreviewDecision is the human operator's approve/reject input, sent as
// PreviewDecisionSignalName's payload.
type PreviewDecision struct {
	Approved bool
	Reason   string
	Decider  string
}

// PreviewState is PreviewQueryName's response: what select_parser_activity
// produced (SelectRef) and where the hold currently stands.
type PreviewState struct {
	Phase     PreviewPhase
	SelectRef Ref
	Reason    string
}

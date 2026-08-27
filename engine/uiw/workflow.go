package uiw

import (
	"errors"
	"fmt"

	"go.temporal.io/sdk/workflow"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
)

// UniversalImportWorkflow is the single Temporal workflow every source runs
// through (boundary document acceptance gate 1). It executes the exact
// engine/stagegraph.Stages graph — all 23 atomic Activities, the documented
// safe parallel fan-outs, and deterministic ordering everywhere else — and
// fails closed: any Activity error or explicit StatusFailed result halts
// every descendant and both seal_generation_activity and
// publish_generation_activity. StatusSuccess and StatusNotApplicable are
// both valid outcomes that let the workflow continue.
//
// This function contains no Activity bodies. Every stage is invoked by its
// canon name (ActivityName, identical to stagegraph.StageID) so a worker in
// a later lane can register real Activities without this file changing.
func UniversalImportWorkflow(ctx workflow.Context, in WorkflowInput) (WorkflowResult, error) {
	r := &run{requestID: in.RequestID}

	// Stage 1: register_source_activity — the root. It creates the
	// identity/idempotency coordinate every later stage keys off.
	sourceVersionRef, err := r.exec(ctx, stagegraph.RegisterSource, in.DeclaredFormat, map[string]Ref{
		"acquisition": in.SourceRef,
	})
	if err != nil {
		return r.result(""), err
	}
	r.sourceVersionRef = sourceVersionRef

	// Stage 2: retain_original_activity — the only stage after
	// register_source that must run before anything touches source bytes.
	originalRef, err := r.exec(ctx, stagegraph.RetainOriginal, "", map[string]Ref{
		"acquisition": in.SourceRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stages 3-6: the named safe parallel fan-out. Each depends only on
	// retain_original, not on one another (proven for the graph itself by
	// stagegraph.TestSafeParallelFanOutAfterRetainOriginal).
	fanOut, err := r.join(ctx,
		r.start(ctx, stagegraph.CaptureFilesystemMetadata, "", map[string]Ref{"original": originalRef}),
		r.start(ctx, stagegraph.HashSource, "", map[string]Ref{"original": originalRef}),
		r.start(ctx, stagegraph.InventoryContainer, "", map[string]Ref{"original": originalRef}),
		r.start(ctx, stagegraph.ExtractEmbeddedMetadata, "", map[string]Ref{"original": originalRef}),
	)
	if err != nil {
		return r.result(""), err
	}
	filesystemMetadataRef := fanOut[stagegraph.CaptureFilesystemMetadata]
	h1Ref := fanOut[stagegraph.HashSource]
	containerManifestRef := fanOut[stagegraph.InventoryContainer]
	metadataManifestRef := fanOut[stagegraph.ExtractEmbeddedMetadata]

	// Stage 7: select_parser_activity joins the fan-out; it needs the
	// container manifest and metadata manifest to pick an adapter. It does
	// NOT receive h1Ref: hash identity must never influence parser
	// selection. The workflow still joins the fan-out (including
	// hash_source) before scheduling select_parser — only the H1 reference
	// itself is withheld from this stage's request.
	parserSelectionRef, err := r.exec(ctx, stagegraph.SelectParser, in.DeclaredFormat, map[string]Ref{
		"filesystem_metadata": filesystemMetadataRef,
		"container_manifest":  containerManifestRef,
		"metadata_manifest":   metadataManifestRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Human preview hold: between selection and execution, the workflow
	// pauses for a human decision on the persisted parser_selection before
	// the actual parse (execute_parser_activity) ever runs. This is a real
	// Signal + Query + Timer (preview.go), not an Activity-level trick,
	// precisely so the hold survives a worker restart or a replica change —
	// Temporal replays this workflow's own durable history, not any single
	// worker's in-memory state.
	preview := PreviewState{Phase: PhaseAwaitingDecision, SelectRef: parserSelectionRef}
	if err := workflow.SetQueryHandler(ctx, PreviewQueryName, func() (PreviewState, error) {
		return preview, nil
	}); err != nil {
		return r.result(""), fmt.Errorf("uiw: register preview query handler: %w", err)
	}

	var decision PreviewDecision
	var decided bool
	signalChan := workflow.GetSignalChannel(ctx, PreviewDecisionSignalName)
	selector := workflow.NewSelector(ctx)
	timer := workflow.NewTimer(ctx, previewDecisionTimeout)
	selector.AddReceive(signalChan, func(c workflow.ReceiveChannel, more bool) {
		c.Receive(ctx, &decision)
		decided = true
	})
	selector.AddFuture(timer, func(f workflow.Future) { _ = f.Get(ctx, nil) })
	selector.Select(ctx)

	if !decided {
		preview.Phase = PhaseTimedOut
		preview.Reason = "preview decision timed out"
		return r.result(""), errors.New("uiw: preview decision timed out")
	}
	if !decision.Approved {
		preview.Phase = PhaseRejected
		preview.Reason = decision.Reason
		return r.result(""), fmt.Errorf("uiw: rejected by operator %s: %s", decision.Decider, decision.Reason)
	}
	preview.Phase = PhaseApproved

	// Stage 8: execute_parser_activity — parse only.
	rawBundleRef, err := r.exec(ctx, stagegraph.ExecuteParser, in.DeclaredFormat, map[string]Ref{
		"parser_selection": parserSelectionRef,
		"original":         originalRef,
		"parser_options":   in.ParserOptionsRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stage 9: persist_raw_generation_activity, then stage 10:
	// hash_raw_records_activity (H2 per raw record/span) — strict sequence
	// (persist before hashing the persisted rows). DeclaredFormat is
	// preserved here (not dropped to "") because the raw generation's own
	// persisted record needs to know what format it was parsed from.
	rawGenerationRef, err := r.exec(ctx, stagegraph.PersistRawGeneration, in.DeclaredFormat, map[string]Ref{
		"raw_bundle": rawBundleRef,
	})
	if err != nil {
		return r.result(""), err
	}
	rawHashManifestRef, err := r.exec(ctx, stagegraph.HashRawRecords, "", map[string]Ref{
		"raw_generation": rawGenerationRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stage 10a: hash_raw_generation_activity — folds the ordered H2
	// membership from hash_raw_records into the raw generation's H3 chain.
	// It reuses the SBV fold formula under the platform raw-all membership tag,
	// because envelope/unparsed spans are members too. Raw custody is not complete until both the
	// per-record digests and their order-sensitive chain exist.
	rawGenerationChainRef, err := r.exec(ctx, stagegraph.HashRawGeneration, "", map[string]Ref{
		"raw_hash_manifest": rawHashManifestRef,
		"raw_generation":    rawGenerationRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stages 11-12: the second parallel pair — both depend only on
	// hash_raw_generation (the completed H2+H3 raw custody chain), not on
	// each other.
	reconcilePair, err := r.join(ctx,
		r.start(ctx, stagegraph.ReconcileRecordAccounting, "", map[string]Ref{"raw_generation_chain": rawGenerationChainRef}),
		r.start(ctx, stagegraph.ReconcileByteCoverage, "", map[string]Ref{"raw_generation_chain": rawGenerationChainRef}),
	)
	if err != nil {
		return r.result(""), err
	}
	accountingRef := reconcilePair[stagegraph.ReconcileRecordAccounting]
	coverageRef := reconcilePair[stagegraph.ReconcileByteCoverage]

	// Stage 13: verify_raw_coverage_against_source_activity joins the
	// reconciliation pair, independently recomputes/verifies the ordered raw
	// generation chain, and checks the accounted byte coverage against H1.
	// Verification remains separate from every hash computation.
	rawSourceVerificationRef, err := r.exec(ctx, stagegraph.VerifyRawCoverageAgainstSource, "", map[string]Ref{
		"accounting":           accountingRef,
		"coverage":             coverageRef,
		"h1":                   h1Ref,
		"raw_generation_chain": rawGenerationChainRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stage 14: normalize_generation_activity, then stage 15:
	// persist_normalized_generation_activity — strict sequence (normalize
	// is transform-only, persist is the only write).
	normalizedBundleRef, err := r.exec(ctx, stagegraph.NormalizeGeneration, "", map[string]Ref{
		"raw_source_verification": rawSourceVerificationRef,
		"raw_generation":          rawGenerationRef,
	})
	if err != nil {
		return r.result(""), err
	}
	normalizedGenerationRef, err := r.exec(ctx, stagegraph.PersistNormalizedGeneration, "", map[string]Ref{
		"normalized_bundle": normalizedBundleRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stages 16-19: the third parallel pair. persist_lineage ->
	// validate_raw_lineage is one branch off persist_normalized_generation;
	// hash_normalized_records (normalized record digests) ->
	// hash_normalized_generation (normalized generation manifest digest) is
	// the other, independent branch. Neither of these is H2 or H3 — those
	// names are reserved for the raw-custody hashes computed by
	// hash_raw_records/hash_raw_generation (vendored/sbv/CUSTODY.md). Both
	// branches are launched via workflow.Go before either is awaited, so
	// they run concurrently.
	lineageBranch := r.branch(ctx, func(gctx workflow.Context) (Ref, error) {
		lineageSetRef, err := r.exec(gctx, stagegraph.PersistLineage, "", map[string]Ref{
			"normalized_generation": normalizedGenerationRef,
			"raw_generation":        rawGenerationRef,
		})
		if err != nil {
			return "", err
		}
		return r.exec(gctx, stagegraph.ValidateRawLineage, "", map[string]Ref{
			"lineage_set": lineageSetRef,
		})
	})
	hashBranch := r.branch(ctx, func(gctx workflow.Context) (Ref, error) {
		normalizedRecordDigestsRef, err := r.exec(gctx, stagegraph.HashNormalizedRecords, "", map[string]Ref{
			"normalized_generation": normalizedGenerationRef,
		})
		if err != nil {
			return "", err
		}
		return r.exec(gctx, stagegraph.HashNormalizedGeneration, "", map[string]Ref{
			"normalized_record_digests": normalizedRecordDigestsRef,
			"normalized_generation":     normalizedGenerationRef,
		})
	})

	var lineageValidationRef Ref
	lineageErr := lineageBranch.Get(ctx, &lineageValidationRef)
	var normalizedGenerationManifestDigestRef Ref
	hashErr := hashBranch.Get(ctx, &normalizedGenerationManifestDigestRef)
	if lineageErr != nil {
		return r.result(""), lineageErr
	}
	if hashErr != nil {
		return r.result(""), hashErr
	}

	// Stage 20: verify_normalized_generation_activity joins the lineage
	// branch and the normalized-digest branch.
	normalizedVerificationRef, err := r.exec(ctx, stagegraph.VerifyNormalizedGeneration, "", map[string]Ref{
		"lineage_validation":                    lineageValidationRef,
		"normalized_generation_manifest_digest": normalizedGenerationManifestDigestRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stage 21: seal_generation_activity.
	sealedGenerationRef, err := r.exec(ctx, stagegraph.SealGeneration, "", map[string]Ref{
		"normalized_verification": normalizedVerificationRef,
	})
	if err != nil {
		return r.result(""), err
	}

	// Stage 22: publish_generation_activity — the sole successor of seal,
	// and therefore the sink whose transitive dependency closure is every
	// other stage.
	publicationRef, err := r.exec(ctx, stagegraph.PublishGeneration, "", map[string]Ref{
		"sealed_generation": sealedGenerationRef,
	})
	if err != nil {
		return r.result(""), err
	}

	return r.result(publicationRef), nil
}

// run accumulates the ordered stage receipts and the running
// source/version reference across one workflow execution.
type run struct {
	requestID        string
	sourceVersionRef Ref
	results          []StageResult
}

// pending is an in-flight Activity future paired with the stage id that
// started it, so join can attribute a failure to the right stage.
type pending struct {
	id  stagegraph.StageID
	fut workflow.Future
}

// exec runs one Activity to completion and returns its compact result Ref.
// Any Activity execution error, or an explicit StatusFailed result, is
// fail-closed: it is recorded in r.results and returned as an error, and
// the caller's control flow simply does not reach the descendant stages —
// no Temporal API call is made to schedule them.
func (r *run) exec(ctx workflow.Context, id stagegraph.StageID, declaredFormat string, refs map[string]Ref) (Ref, error) {
	return r.settle(id, r.start(ctx, id, declaredFormat, refs).fut.Get, ctx)
}

// start schedules one Activity without blocking, for use in parallel
// fan-outs and branches.
func (r *run) start(ctx workflow.Context, id stagegraph.StageID, declaredFormat string, refs map[string]Ref) pending {
	req := StageRequest{
		RequestID:        r.requestID,
		SourceVersionRef: r.sourceVersionRef,
		DeclaredFormat:   declaredFormat,
		Refs:             refs,
	}
	actCtx := workflow.WithActivityOptions(ctx, optionsFor(id))
	return pending{id: id, fut: workflow.ExecuteActivity(actCtx, string(id), req)}
}

// settle awaits one future and records+validates its StageResult. get is
// fut.Get, threaded through so exec and join share exactly one recording
// path. It fails closed on three distinct malformed-result shapes, in
// addition to the ordinary business-failed and Activity-execution-error
// paths:
//   - a nonempty res.Stage that does not equal the invoked stage id (a
//     mismatched identity is never silently accepted);
//   - an empty or unknown res.Status;
//   - a result whose Status doesn't carry the receipt evidence that Status
//     requires — see validateStageResult.
func (r *run) settle(id stagegraph.StageID, get func(workflow.Context, interface{}) error, ctx workflow.Context) (Ref, error) {
	var res StageResult
	if err := get(ctx, &res); err != nil {
		// The Activity may have crashed before producing a receipt at all,
		// so this stays a Temporal execution error — there is no business
		// result here to validate.
		r.results = append(r.results, StageResult{Stage: id, Status: StatusFailed, Reason: err.Error()})
		return "", fmt.Errorf("uiw: stage %q failed: %w", id, err)
	}

	if res.Stage != "" && res.Stage != id {
		mismatchErr := fmt.Errorf("uiw: stage %q returned a result identifying itself as %q", id, res.Stage)
		r.results = append(r.results, StageResult{Stage: id, Status: StatusFailed, Reason: mismatchErr.Error()})
		return "", mismatchErr
	}
	res.Stage = id

	if err := validateStageResult(res); err != nil {
		invalidErr := fmt.Errorf("uiw: stage %q returned an invalid result: %w", id, err)
		r.results = append(r.results, StageResult{Stage: id, Status: StatusFailed, Reason: invalidErr.Error()})
		return "", invalidErr
	}

	r.results = append(r.results, res)
	if res.Status == StatusFailed {
		return "", fmt.Errorf("uiw: stage %q reported failed status: %s", id, res.Reason)
	}

	// A not-applicable stage still produced a durable, independently
	// addressable outcome. Some Activity implementations have a distinct
	// result marker and return it in Ref; source-observation stages instead
	// persist only the N/A receipt. Use that receipt as the dependency Ref
	// when no distinct result exists so descendants never receive an empty
	// reference indistinguishable from an unrecorded outcome. Keep res.Ref
	// untouched in r.results: the workflow receipt must continue to report
	// the Activity's actual StatusNotApplicable result, not rewrite it as a
	// successful materialization.
	if res.Status == StatusNotApplicable && res.Ref == "" {
		return res.ReceiptRef, nil
	}
	return res.Ref, nil
}

// validateStageResult enforces the fail-closed receipt contract: every
// terminal Status must carry the evidence its meaning requires.
// StatusSuccess and StatusNotApplicable both certify that the stage's
// outcome was durably recorded, so both require a non-empty ReceiptRef;
// StatusNotApplicable may have no separate result, so its Ref may be empty;
// settle then uses its required ReceiptRef as the downstream dependency Ref.
// Its Reason and ReceiptRef may not be empty. A business-reported StatusFailed must
// also fail closed with both Reason and ReceiptRef present — it is a real
// receipt, not a bare error string. An empty or unrecognized Status is
// always rejected: there is no default interpretation for "the Activity
// didn't say."
func validateStageResult(res StageResult) error {
	switch res.Status {
	case StatusSuccess:
		if res.Ref == "" {
			return errors.New("success result has an empty result Ref")
		}
		if res.ReceiptRef == "" {
			return errors.New("success result has an empty ReceiptRef")
		}
	case StatusNotApplicable:
		if res.Reason == "" {
			return errors.New("not_applicable result has an empty Reason")
		}
		if res.ReceiptRef == "" {
			return errors.New("not_applicable result has an empty ReceiptRef")
		}
	case StatusFailed:
		if res.Reason == "" {
			return errors.New("failed result has an empty Reason")
		}
		if res.ReceiptRef == "" {
			return errors.New("failed result has an empty ReceiptRef")
		}
	default:
		return fmt.Errorf("unknown or empty Status %q", res.Status)
	}
	return nil
}

// join awaits every pending future, draining all of them deterministically
// before returning, and fails closed if any reported failure (Activity
// error or explicit StatusFailed). It never schedules a descendant stage
// itself — that decision belongs to the caller, which only proceeds past a
// non-nil error return by returning early.
func (r *run) join(ctx workflow.Context, ps ...pending) (map[stagegraph.StageID]Ref, error) {
	out := make(map[stagegraph.StageID]Ref, len(ps))
	var firstErr error
	for _, p := range ps {
		ref, err := r.settle(p.id, p.fut.Get, ctx)
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			continue
		}
		out[p.id] = ref
	}
	if firstErr != nil {
		return nil, firstErr
	}
	return out, nil
}

// branch launches fn on its own workflow coroutine so a multi-stage
// dependency chain (e.g. persist_lineage -> validate_raw_lineage) can run
// concurrently with a sibling chain. The returned Future resolves once fn
// returns; fn itself is responsible for fail-closed behavior within its own
// chain via r.exec.
func (r *run) branch(ctx workflow.Context, fn func(workflow.Context) (Ref, error)) workflow.Future {
	future, settable := workflow.NewFuture(ctx)
	workflow.Go(ctx, func(gctx workflow.Context) {
		ref, err := fn(gctx)
		settable.Set(ref, err)
	})
	return future
}

// result builds the terminal WorkflowResult from everything recorded so
// far. publicationRef is empty on any non-success path.
func (r *run) result(publicationRef Ref) WorkflowResult {
	status := StatusSuccess
	if publicationRef == "" {
		status = StatusFailed
	}
	return WorkflowResult{
		SourceVersionRef: r.sourceVersionRef,
		PublicationRef:   publicationRef,
		Status:           status,
		Stages:           r.results,
	}
}

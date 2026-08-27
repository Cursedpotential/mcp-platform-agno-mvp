// Package activities implements the source-lifecycle Activities for the
// universal import workflow. These Activities own only intake identity and
// retention: they do not read source bytes into Temporal history, parse,
// normalize, hash, or make an evidence-authority decision.
package activities

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// SourceRegistrationSpec is the compact input resolved by
// register_source_activity. AcquisitionRef is an opaque external pointer;
// its bytes and metadata stay outside Temporal history. The store is
// responsible for creating or recovering the source/source_version identity,
// activity execution, and immutable activity receipt in one idempotent
// persistence boundary.
type SourceRegistrationSpec struct {
	RequestID      string
	AcquisitionRef uiw.Ref
	DeclaredFormat string
	Attempt        int32
}

// OriginalRetentionSpec is the compact input resolved by
// retain_original_activity. It binds the already-registered source version to
// one immutable retained object. The store may copy bytes to immutable storage
// or retain an already-governed immutable object reference, but it must not
// return source bytes through this Activity.
type OriginalRetentionSpec struct {
	RequestID        string
	SourceVersionRef uiw.Ref
	AcquisitionRef   uiw.Ref
	Attempt          int32
}

// SourceLifecycleStore is the PostgreSQL/immutable-storage boundary for the
// two source-lifecycle Activities. Implementations must make each operation
// retry-safe using context.activity_execution and context.activity_receipt:
// a repeated idempotency coordinate returns the existing successful result
// and receipt, while a new attempt records its own immutable receipt. A
// successful retention operation must perform the SQL 0036 registered ->
// retained transition and bind source_version.original_object_id to a
// source_version_object row whose role is original.
//
// The interface intentionally returns only compact references. Implementations
// must never put source bytes, metadata, or a full row payload in a result.
type SourceLifecycleStore interface {
	RegisterSource(context.Context, SourceRegistrationSpec) (resultRef uiw.Ref, receiptRef uiw.Ref, err error)
	RetainOriginal(context.Context, OriginalRetentionSpec) (resultRef uiw.Ref, receiptRef uiw.Ref, err error)
}

// SourceLifecycleActivities implements the two atomic intake Activities.
// Attempt is injectable for direct tests and defaults to one; a Temporal
// worker can bind it to activity.GetInfo(ctx).Attempt alongside the hash and
// parser Activities.
type SourceLifecycleActivities struct {
	Store   SourceLifecycleStore
	Attempt Attempt
}

func (a SourceLifecycleActivities) validate() error {
	if a.Store == nil {
		return errors.New("source lifecycle activities: store is required")
	}
	return nil
}

func (a SourceLifecycleActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

// RegisterSource creates or recovers only the durable source/source_version
// identity and workflow idempotency coordinate. Registration intentionally
// happens before retention; no downstream data may be written until
// retain_original_activity succeeds.
func (a SourceLifecycleActivities) RegisterSource(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	if strings.TrimSpace(req.RequestID) == "" {
		return uiw.StageResult{}, errors.New("register source requires a request id")
	}
	if strings.TrimSpace(req.DeclaredFormat) == "" {
		return uiw.StageResult{}, errors.New("register source requires a declared format")
	}
	acquisitionRef, err := requiredSourceRef(req, stagegraph.RegisterSource, "acquisition")
	if err != nil {
		return uiw.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.RegisterSource(ctx, SourceRegistrationSpec{
		RequestID:      req.RequestID,
		AcquisitionRef: acquisitionRef,
		DeclaredFormat: req.DeclaredFormat,
		Attempt:        a.attempt(ctx),
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("register source: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return uiw.StageResult{}, errors.New("registered source lacks result or activity receipt reference")
	}
	return sourceLifecycleSuccess(stagegraph.RegisterSource, resultRef, receiptRef), nil
}

// RetainOriginal binds exactly one immutable retained object to the already
// registered source version and advances only registered -> retained. It does
// not hash, parse, normalize, or infer evidence authority.
func (a SourceLifecycleActivities) RetainOriginal(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	if strings.TrimSpace(req.RequestID) == "" {
		return uiw.StageResult{}, errors.New("retain original requires a request id")
	}
	if strings.TrimSpace(string(req.SourceVersionRef)) == "" {
		return uiw.StageResult{}, errors.New("retain original requires a source version reference")
	}
	acquisitionRef, err := requiredSourceRef(req, stagegraph.RetainOriginal, "acquisition")
	if err != nil {
		return uiw.StageResult{}, err
	}
	resultRef, receiptRef, err := a.Store.RetainOriginal(ctx, OriginalRetentionSpec{
		RequestID:        req.RequestID,
		SourceVersionRef: req.SourceVersionRef,
		AcquisitionRef:   acquisitionRef,
		Attempt:          a.attempt(ctx),
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("retain original: %w", err)
	}
	if resultRef == "" || receiptRef == "" {
		return uiw.StageResult{}, errors.New("retained original lacks result or activity receipt reference")
	}
	return sourceLifecycleSuccess(stagegraph.RetainOriginal, resultRef, receiptRef), nil
}

func requiredSourceRef(req uiw.StageRequest, stage stagegraph.StageID, name string) (uiw.Ref, error) {
	ref := req.Refs[name]
	if strings.TrimSpace(string(ref)) == "" {
		return "", fmt.Errorf("%s requires non-empty %q reference", stage, name)
	}
	return ref, nil
}

func sourceLifecycleSuccess(stage stagegraph.StageID, resultRef, receiptRef uiw.Ref) uiw.StageResult {
	return uiw.StageResult{Stage: stage, Status: uiw.StatusSuccess, Ref: resultRef, ReceiptRef: receiptRef}
}

// boundedCleanup gives abort/rollback paths a short cancellation-independent
// window. It is shared by Activities that must close a durable writer after
// the caller's context has already been canceled.
func boundedCleanup(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
}

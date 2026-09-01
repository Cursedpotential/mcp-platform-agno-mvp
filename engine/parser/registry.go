package parser

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"
	"time"
)

const abortTimeout = 5 * time.Second

// Registry is a deterministic capability registry. It selects only from
// declared format coverage and the declared per-format quality tier; input
// size is deliberately absent from Select and Execute's selection path.
type Registry struct {
	mu       sync.RWMutex
	adapters []registeredAdapter
	keys     map[string]struct{}
}

type registeredAdapter struct {
	adapter    Adapter
	capability Capability
}

func NewRegistry(adapters ...Adapter) (*Registry, error) {
	registry := &Registry{keys: make(map[string]struct{})}
	for _, adapter := range adapters {
		if err := reference.Register(adapter); err != nil {
			return nil, err
		}
	}
	return registry, nil
}

func (r *Registry) Register(adapter Adapter) error {
	if r == nil {
		return errors.New("parser registry is nil")
	}
	if adapter == nil {
		return errors.New("parser adapter is nil")
	}
	capability := adapter.Capability()
	if err := capability.Validate(); err != nil {
		return fmt.Errorf("register parser %q: %w", capability.ParserID, err)
	}
	key := capability.ParserID + "\x00" + capability.ParserVersion
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.keys[key]; exists {
		return fmt.Errorf("parser adapter %q version %q is already registered", capability.ParserID, capability.ParserVersion)
	}
	r.keys[key] = struct{}{}
	r.adapters = append(r.adapters, registeredAdapter{adapter: adapter, capability: cloneCapability(capability)})
	return nil
}

// Select chooses the adapter with declared coverage for format. Quality breaks
// coverage ties, then parser ID/version/language form a stable lexical tie
// break. Neither this method nor its arguments carry source byte length.
func (r *Registry) Select(format FormatID) (Adapter, error) {
	selected, err := r.selectRegistered(format)
	if err != nil {
		return nil, err
	}
	return selected.adapter, nil
}

// SelectCapability returns the immutable capability snapshot used for a
// deterministic selection. Callers that persist a selection receipt must use
// this snapshot rather than re-reading a potentially mutable Adapter value.
func (r *Registry) SelectCapability(format FormatID) (Capability, error) {
	selected, err := r.selectRegistered(format)
	if err != nil {
		return Capability{}, err
	}
	return cloneCapability(selected.capability), nil
}

// Lookup returns the exact parser id/version registered in this process. It
// never falls back to another adapter: a persisted selection receipt remains
// the authority even if later registry contents or qualities differ.
func (r *Registry) Lookup(parserID, parserVersion string) (Adapter, Capability, error) {
	if r == nil {
		return nil, Capability{}, errors.New("parser registry is nil")
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	for _, candidate := range r.adapters {
		if candidate.capability.ParserID == parserID && candidate.capability.ParserVersion == parserVersion {
			return candidate.adapter, cloneCapability(candidate.capability), nil
		}
	}
	return nil, Capability{}, fmt.Errorf("parser adapter %q version %q is not registered", parserID, parserVersion)
}

func (r *Registry) selectRegistered(format FormatID) (registeredAdapter, error) {
	if r == nil {
		return registeredAdapter{}, errors.New("parser registry is nil")
	}
	if err := format.Validate(); err != nil {
		return registeredAdapter{}, err
	}
	r.mu.RLock()
	candidates := make([]registeredAdapter, 0, len(r.adapters))
	for _, candidate := range r.adapters {
		if covers(candidate.capability, format) {
			candidates = append(candidates, candidate)
		}
	}
	r.mu.RUnlock()
	if len(candidates) == 0 {
		return registeredAdapter{}, fmt.Errorf("no parser adapter declares format %q", format)
	}
	sort.Slice(candidates, func(left, right int) bool {
		leftCapability, rightCapability := candidates[left].capability, candidates[right].capability
		leftPriority := leftCapability.QualityFor(format).priority()
		rightPriority := rightCapability.QualityFor(format).priority()
		if leftPriority != rightPriority {
			return leftPriority < rightPriority
		}
		if leftCapability.ParserID != rightCapability.ParserID {
			return leftCapability.ParserID < rightCapability.ParserID
		}
		if leftCapability.ParserVersion != rightCapability.ParserVersion {
			return leftCapability.ParserVersion < rightCapability.ParserVersion
		}
		return leftCapability.Language < rightCapability.Language
	})
	return candidates[0], nil
}

// Execute owns streaming bundle lifecycle around one adapter invocation.
// Adapters can emit records but cannot finalize/commit the bundle. Any parse,
// shape, cancellation, or accounting failure aborts the caller-owned writer.
func (r *Registry) Execute(ctx context.Context, input ParserInput, writer BundleWriter) (result BundleResult, err error) {
	if err := input.Validate(); err != nil {
		return BundleResult{}, err
	}
	if writer == nil {
		return BundleResult{}, errors.New("parser execution requires bundle writer")
	}
	if err := ctx.Err(); err != nil {
		return BundleResult{}, err
	}
	selected, err := r.selectRegistered(input.DeclaredFormat)
	if err != nil {
		return BundleResult{}, err
	}
	return executeRegistered(ctx, input, writer, selected)
}

// ExecuteSelected runs precisely the parser named by an immutable persisted
// selection receipt. It rejects missing, stale, or format-ineligible identity
// rather than reselecting after registry drift.
func (r *Registry) ExecuteSelected(ctx context.Context, input ParserInput, parserID, parserVersion string, writer BundleWriter) (BundleResult, error) {
	if err := input.Validate(); err != nil {
		return BundleResult{}, err
	}
	if writer == nil {
		return BundleResult{}, errors.New("parser execution requires bundle writer")
	}
	if err := ctx.Err(); err != nil {
		return BundleResult{}, err
	}
	adapter, capability, err := r.Lookup(parserID, parserVersion)
	if err != nil {
		return BundleResult{}, err
	}
	if !covers(capability, input.DeclaredFormat) {
		return BundleResult{}, fmt.Errorf("persisted parser %q version %q does not declare format %q", parserID, parserVersion, input.DeclaredFormat)
	}
	return executeRegistered(ctx, input, writer, registeredAdapter{adapter: adapter, capability: capability})
}

func executeRegistered(ctx context.Context, input ParserInput, writer BundleWriter, selected registeredAdapter) (result BundleResult, err error) {
	adapter, capability := selected.adapter, selected.capability
	header := BundleHeader{
		ContractVersion:  ContractVersion,
		ParserID:         capability.ParserID,
		ParserVersion:    capability.ParserVersion,
		SourceVersionRef: input.SourceVersionRef,
		FormatID:         input.DeclaredFormat,
	}
	if err := writer.Begin(ctx, header); err != nil {
		_ = abortBundle(ctx, writer)
		return BundleResult{}, fmt.Errorf("begin raw extraction bundle: %w", err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = abortBundle(ctx, writer)
		}
	}()

	sink := &validatingSink{downstream: writer, format: input.DeclaredFormat}
	accounting, err := adapter.Parse(ctx, input, sink)
	if err != nil {
		return BundleResult{}, fmt.Errorf("parse with %s: %w", capability.ParserID, err)
	}
	if sink.fault != nil {
		return BundleResult{}, fmt.Errorf("parse with %s emitted invalid bundle data: %w", capability.ParserID, sink.fault)
	}
	if err := ctx.Err(); err != nil {
		return BundleResult{}, err
	}
	if err := sink.validateFinalization(accounting); err != nil {
		return BundleResult{}, err
	}
	result, err = writer.Finalize(ctx, accounting)
	if err != nil {
		return BundleResult{}, fmt.Errorf("finalize raw extraction bundle: %w", err)
	}
	if result.BundleRef == "" {
		return BundleResult{}, errors.New("finalized raw extraction bundle lacks compact bundle reference")
	}
	committed = true
	return result, nil
}

// abortBundle intentionally ignores a caller's cancellation while bounding
// cleanup itself. A writer may need the cleanup call after a parse context has
// expired, but must respect this short deadline rather than block retries.
func abortBundle(ctx context.Context, writer BundleWriter) error {
	cleanupContext, cancel := context.WithTimeout(context.WithoutCancel(ctx), abortTimeout)
	defer cancel()
	return writer.Abort(cleanupContext)
}

type observedAccounting struct {
	BundleAccounting
	records uint64
}

type validatingSink struct {
	downstream BundleSink
	format     FormatID
	next       uint64
	observed   observedAccounting
	fault      error
}

func (s *validatingSink) Emit(ctx context.Context, record RawRecordEnvelope) error {
	if s.fault != nil {
		return s.fault
	}
	if err := ctx.Err(); err != nil {
		s.fault = err
		return err
	}
	if record.RecordOrdinal != s.next {
		s.fault = fmt.Errorf("raw record ordinal %d, want contiguous ordinal %d", record.RecordOrdinal, s.next)
		return s.fault
	}
	if err := record.Validate(s.format); err != nil {
		s.fault = err
		return err
	}
	if err := s.downstream.Emit(ctx, record); err != nil {
		s.fault = fmt.Errorf("write raw record ordinal %d: %w", record.RecordOrdinal, err)
		return s.fault
	}
	s.next++
	s.observed.records++
	s.observed.Attachments += uint64(len(record.Attachments))
	switch record.RecordStatus {
	case StatusParsed:
		s.observed.Emitted++
	case StatusRejected:
		s.observed.Rejected++
	case StatusMalformed:
		s.observed.Malformed++
	case StatusUnknown:
		s.observed.Unknown++
	case StatusUnparsed:
		s.observed.Unparsed++
	case StatusEnvelope:
		// Envelope spans deliberately have no separate v1 accounting field.
	}
	return nil
}

func (s *validatingSink) validateFinalization(accounting BundleAccounting) error {
	if s.fault != nil {
		return s.fault
	}
	if s.observed.records == 0 {
		return errors.New("raw extraction bundle cannot finalize with zero records")
	}
	if accounting != s.observed.BundleAccounting {
		return fmt.Errorf("raw extraction bundle accounting mismatch: got %+v, observed %+v", accounting, s.observed.BundleAccounting)
	}
	return nil
}

func covers(capability Capability, format FormatID) bool {
	for _, declared := range capability.DeclaredFormats {
		if declared == format {
			return true
		}
	}
	return false
}

func cloneCapability(capability Capability) Capability {
	clone := capability
	clone.DeclaredFormats = append([]FormatID(nil), capability.DeclaredFormats...)
	clone.FormatQuality = make(map[FormatID]Quality, len(capability.FormatQuality))
	for format, quality := range capability.FormatQuality {
		clone.FormatQuality[format] = quality
	}
	return clone
}

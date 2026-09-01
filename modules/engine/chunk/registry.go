package chunk

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
)

// Adapter is the atomic chunk-stage seam. It deliberately does not emit
// parser.RawRecordEnvelope values: chunk coordinates and completeness proof
// belong to the independently replayable chunk result.
type Adapter interface {
	Capability() Capability
	Chunk(source []byte, signature Signature) (Result, error)
}

// Selection is the compact immutable receipt persisted before execution.
// ExecuteSelected replays exactly this identity and never silently substitutes
// another registered chunker after registry drift.
type Selection struct {
	ContractVersion string
	ChunkerID       string
	ChunkerVersion  string
	Signature       Signature
	Quality         parser.Quality
}

type registeredAdapter struct {
	adapter    Adapter
	capability Capability
}

// Registry applies the same coverage -> quality -> lexical identity ordering
// as the parser coordinator, but retains a separate chunk-stage contract.
type Registry struct {
	mu       sync.RWMutex
	adapters []registeredAdapter
	keys     map[string]struct{}
}

func NewRegistry(adapters ...Adapter) (*Registry, error) {
	registry := &Registry{keys: make(map[string]struct{})}
	for _, adapter := range adapters {
		if err := registry.Register(adapter); err != nil {
			return nil, err
		}
	}
	return registry, nil
}

func (r *Registry) Register(adapter Adapter) error {
	if r == nil {
		return errors.New("chunk registry is nil")
	}
	if adapter == nil {
		return errors.New("chunk adapter is nil")
	}
	capability := adapter.Capability()
	if err := capability.Validate(); err != nil {
		return fmt.Errorf("register chunker %q: %w", capability.ChunkerID, err)
	}
	key := capability.ChunkerID + "\x00" + capability.ChunkerVersion
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.keys[key]; exists {
		return fmt.Errorf("chunk adapter %q version %q is already registered", capability.ChunkerID, capability.ChunkerVersion)
	}
	r.keys[key] = struct{}{}
	r.adapters = append(r.adapters, registeredAdapter{adapter: adapter, capability: cloneCapability(capability)})
	return nil
}

// Select returns an immutable receipt rather than an adapter whose mutable
// Capability method could later report different identity or quality.
func (r *Registry) Select(signature Signature) (Selection, error) {
	selected, err := r.selectRegistered(signature)
	if err != nil {
		return Selection{}, err
	}
	return Selection{
		ContractVersion: ContractVersion,
		ChunkerID:       selected.capability.ChunkerID,
		ChunkerVersion:  selected.capability.ChunkerVersion,
		Signature:       signature,
		Quality:         selected.capability.QualityFor(signature),
	}, nil
}

func (r *Registry) SelectCapability(signature Signature) (Capability, error) {
	selected, err := r.selectRegistered(signature)
	if err != nil {
		return Capability{}, err
	}
	return cloneCapability(selected.capability), nil
}

func (r *Registry) Lookup(chunkerID, chunkerVersion string) (Adapter, Capability, error) {
	if r == nil {
		return nil, Capability{}, errors.New("chunk registry is nil")
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	for _, candidate := range r.adapters {
		if candidate.capability.ChunkerID == chunkerID && candidate.capability.ChunkerVersion == chunkerVersion {
			return candidate.adapter, cloneCapability(candidate.capability), nil
		}
	}
	return nil, Capability{}, fmt.Errorf("chunk adapter %q version %q is not registered", chunkerID, chunkerVersion)
}

func (r *Registry) Execute(ctx context.Context, source []byte, signature Signature) (Result, error) {
	if err := ctx.Err(); err != nil {
		return Result{}, err
	}
	selected, err := r.selectRegistered(signature)
	if err != nil {
		return Result{}, err
	}
	return executeRegistered(ctx, source, signature, selected)
}

// ExecuteSelected executes precisely the persisted chunker identity. Coverage
// mismatch and stale identity fail closed; neither causes reselection.
func (r *Registry) ExecuteSelected(ctx context.Context, source []byte, selection Selection) (Result, error) {
	if selection.ContractVersion != ContractVersion {
		return Result{}, fmt.Errorf("unsupported chunk selection contract version %q", selection.ContractVersion)
	}
	if err := selection.Signature.Validate(); err != nil {
		return Result{}, err
	}
	if err := ctx.Err(); err != nil {
		return Result{}, err
	}
	adapter, capability, err := r.Lookup(selection.ChunkerID, selection.ChunkerVersion)
	if err != nil {
		return Result{}, err
	}
	if !covers(capability, selection.Signature) {
		return Result{}, fmt.Errorf("persisted chunker %q version %q does not declare signature %q", selection.ChunkerID, selection.ChunkerVersion, selection.Signature)
	}
	if capability.QualityFor(selection.Signature) != selection.Quality {
		return Result{}, errors.New("persisted chunk selection quality does not match registered capability snapshot")
	}
	return executeRegistered(ctx, source, selection.Signature, registeredAdapter{adapter: adapter, capability: capability})
}

func (r *Registry) selectRegistered(signature Signature) (registeredAdapter, error) {
	if r == nil {
		return registeredAdapter{}, errors.New("chunk registry is nil")
	}
	if err := signature.Validate(); err != nil {
		return registeredAdapter{}, err
	}
	r.mu.RLock()
	candidates := make([]registeredAdapter, 0, len(r.adapters))
	for _, candidate := range r.adapters {
		if covers(candidate.capability, signature) {
			candidates = append(candidates, candidate)
		}
	}
	r.mu.RUnlock()
	if len(candidates) == 0 {
		return registeredAdapter{}, fmt.Errorf("no chunk adapter declares signature %q", signature)
	}
	sort.Slice(candidates, func(left, right int) bool {
		leftCapability, rightCapability := candidates[left].capability, candidates[right].capability
		leftPriority := qualityPriority(leftCapability.QualityFor(signature))
		rightPriority := qualityPriority(rightCapability.QualityFor(signature))
		if leftPriority != rightPriority {
			return leftPriority < rightPriority
		}
		if leftCapability.ChunkerID != rightCapability.ChunkerID {
			return leftCapability.ChunkerID < rightCapability.ChunkerID
		}
		return leftCapability.ChunkerVersion < rightCapability.ChunkerVersion
	})
	return candidates[0], nil
}

func executeRegistered(ctx context.Context, source []byte, signature Signature, selected registeredAdapter) (Result, error) {
	result, err := selected.adapter.Chunk(source, signature)
	if err != nil {
		return Result{}, fmt.Errorf("chunk with %s: %w", selected.capability.ChunkerID, err)
	}
	if err := ctx.Err(); err != nil {
		return Result{}, err
	}
	if result.Signature != signature || result.ChunkerID != selected.capability.ChunkerID || result.ChunkerVersion != selected.capability.ChunkerVersion {
		return Result{}, errors.New("chunk result identity does not match selected capability")
	}
	if err := result.Validate(source); err != nil {
		return Result{}, fmt.Errorf("chunk completeness proof failed: %w", err)
	}
	return result, nil
}

func covers(capability Capability, signature Signature) bool {
	for _, declared := range capability.Signatures {
		if declared == signature {
			return true
		}
	}
	return false
}

func cloneCapability(capability Capability) Capability {
	clone := capability
	clone.Signatures = append([]Signature(nil), capability.Signatures...)
	clone.SignatureQuality = make(map[Signature]parser.Quality, len(capability.SignatureQuality))
	for signature, quality := range capability.SignatureQuality {
		clone.SignatureQuality[signature] = quality
	}
	return clone
}

func qualityPriority(quality parser.Quality) int {
	switch quality {
	case parser.QualityPrimary:
		return 0
	case parser.QualityFallback:
		return 1
	default:
		return 2
	}
}

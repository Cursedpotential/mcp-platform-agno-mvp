package chunk

import (
	"context"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
)

type testAdapter struct {
	capability Capability
	result     Result
	err        error
}

func (a *testAdapter) Capability() Capability { return a.capability }
func (a *testAdapter) Chunk([]byte, Signature) (Result, error) {
	return a.result, a.err
}

func testCapability(id, version string, quality parser.Quality) Capability {
	return Capability{
		ContractVersion: ContractVersion,
		ChunkerID:       id,
		ChunkerVersion:  version,
		Signatures:      []Signature{SignatureStrategyMemo},
		SignatureQuality: map[Signature]parser.Quality{
			SignatureStrategyMemo: quality,
		},
	}
}

func TestRegistrySelectsCoverageQualityThenIdentity(t *testing.T) {
	fallback := &testAdapter{capability: testCapability("a-fallback", "1", parser.QualityFallback)}
	primaryZ := &testAdapter{capability: testCapability("z-primary", "1", parser.QualityPrimary)}
	primaryA := &testAdapter{capability: testCapability("a-primary", "1", parser.QualityPrimary)}
	registry, err := NewRegistry(fallback, primaryZ, primaryA)
	if err != nil {
		t.Fatal(err)
	}
	selection, err := reference.Select(SignatureStrategyMemo)
	if err != nil {
		t.Fatal(err)
	}
	if selection.ChunkerID != "a-primary" || selection.Quality != parser.QualityPrimary {
		t.Fatalf("selection = %#v", selection)
	}
}

func TestRegistryCapabilitySnapshotIsImmutable(t *testing.T) {
	adapter := &testAdapter{capability: testCapability("stable", "1", parser.QualityPrimary)}
	registry, err := NewRegistry(adapter)
	if err != nil {
		t.Fatal(err)
	}
	adapter.capability.ChunkerID = "mutated"
	adapter.capability.Signatures[0] = SignatureChronology
	adapter.capability.SignatureQuality[SignatureStrategyMemo] = parser.QualityExperimental
	selection, err := reference.Select(SignatureStrategyMemo)
	if err != nil {
		t.Fatal(err)
	}
	if selection.ChunkerID != "stable" || selection.Quality != parser.QualityPrimary {
		t.Fatalf("registered snapshot mutated: %#v", selection)
	}
	capability, err := reference.SelectCapability(SignatureStrategyMemo)
	if err != nil {
		t.Fatal(err)
	}
	capability.Signatures[0] = SignatureChronology
	again, err := reference.SelectCapability(SignatureStrategyMemo)
	if err != nil || again.Signatures[0] != SignatureStrategyMemo {
		t.Fatalf("returned snapshot aliases registry: %#v, %v", again, err)
	}
}

func TestRegistryExecuteSelectedReplaysExactIdentity(t *testing.T) {
	markdown := DefaultMarkdown()
	registry, err := NewRegistry(markdown)
	if err != nil {
		t.Fatal(err)
	}
	selection, err := reference.Select(SignatureChronology)
	if err != nil {
		t.Fatal(err)
	}
	source := []byte("intro\n\n> * **2020** event\n")
	result, err := reference.ExecuteSelected(context.Background(), source, selection)
	if err != nil {
		t.Fatal(err)
	}
	if result.SourceHash != result.ReassemblyHash || len(result.Chunks) != 2 {
		t.Fatalf("completeness proof not surfaced: %#v", result)
	}
	selection.ChunkerVersion = "stale"
	if _, err := reference.ExecuteSelected(context.Background(), source, selection); err == nil {
		t.Fatal("stale selection identity was silently substituted")
	}
}

func TestRegistryRejectsQualityDriftAndFalseCompleteness(t *testing.T) {
	markdown := DefaultMarkdown()
	registry, err := NewRegistry(markdown)
	if err != nil {
		t.Fatal(err)
	}
	selection, _ := reference.Select(SignatureStrategyMemo)
	selection.Quality = parser.QualityFallback
	if _, err := reference.ExecuteSelected(context.Background(), []byte("text"), selection); err == nil {
		t.Fatal("quality drift was accepted")
	}

	source := []byte("text")
	bad := &testAdapter{
		capability: testCapability("bad", "1", parser.QualityPrimary),
		result: Result{
			Signature:       SignatureStrategyMemo,
			ChunkerID:       "bad",
			ChunkerVersion:  "1",
			SchemaID:        SchemaID,
			SchemaVersion:   SchemaVersion,
			SourceByteCount: len(source),
			SourceCharCount: len(source),
			SourceHash:      digest(source),
			ReassemblyHash:  digest([]byte("wrong")),
		},
	}
	badRegistry, _ := NewRegistry(bad)
	if _, err := badRegistry.Execute(context.Background(), source, SignatureStrategyMemo); err == nil {
		t.Fatal("false completeness proof was accepted")
	}
}

func TestRegistryRejectsDuplicateAndUncoveredCapabilities(t *testing.T) {
	adapter := &testAdapter{capability: testCapability("same", "1", parser.QualityPrimary)}
	if _, err := NewRegistry(adapter, adapter); err == nil {
		t.Fatal("duplicate adapter identity accepted")
	}
	registry, err := NewRegistry(adapter)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := reference.Select(SignatureChronology); err == nil {
		t.Fatal("uncovered signature selected")
	}
}

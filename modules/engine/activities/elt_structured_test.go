// Byline: Claude Code · Sonnet 5 · 2026-09-02
package activities

import (
	"context"
	"errors"
	"testing"
)

type fakeStructuredELTRepository struct {
	spec   StructuredELTSpec
	result StructuredELTResult
	err    error
	calls  int
}

func (f *fakeStructuredELTRepository) ExecuteStructuredELT(_ context.Context, spec StructuredELTSpec) (StructuredELTResult, error) {
	f.calls++
	f.spec = spec
	if f.err != nil {
		return StructuredELTResult{}, f.err
	}
	return f.result, nil
}

func validELTSpec() StructuredELTSpec {
	return StructuredELTSpec{
		RequestID:   "req-1",
		SourceID:    "8c8c2c9e-1c1a-4a1a-9b1a-1c1a4a1a9b1a",
		IngestRunID: "3d3d2c9e-1c1a-4a1a-9b1a-1c1a4a1a9b1a",
		SourceURL:   "https://example.invalid/data.csv",
		Format:      StructuredELTFormatCSV,
	}
}

func TestStructuredELTActivitiesRequiresRepository(t *testing.T) {
	a := StructuredELTActivities{}
	if _, err := a.ExecuteStructuredELT(context.Background(), validELTSpec()); err == nil {
		t.Fatal("expected error when repository is nil")
	}
}

func TestStructuredELTActivitiesValidatesSpec(t *testing.T) {
	tests := []struct {
		name string
		spec StructuredELTSpec
	}{
		{"missing request id", StructuredELTSpec{SourceID: "s", IngestRunID: "i", SourceURL: "u", Format: StructuredELTFormatCSV}},
		{"missing source id", StructuredELTSpec{RequestID: "r", IngestRunID: "i", SourceURL: "u", Format: StructuredELTFormatCSV}},
		{"missing ingest run id", StructuredELTSpec{RequestID: "r", SourceID: "s", SourceURL: "u", Format: StructuredELTFormatCSV}},
		{"missing source url", StructuredELTSpec{RequestID: "r", SourceID: "s", IngestRunID: "i", Format: StructuredELTFormatCSV}},
		{"bad format", StructuredELTSpec{RequestID: "r", SourceID: "s", IngestRunID: "i", SourceURL: "u", Format: "xml"}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			repo := &fakeStructuredELTRepository{}
			a := StructuredELTActivities{Repository: repo}
			if _, err := a.ExecuteStructuredELT(context.Background(), test.spec); err == nil {
				t.Fatal("expected validation error")
			}
			if repo.calls != 0 {
				t.Fatalf("repository should not be called on validation failure, got %d calls", repo.calls)
			}
		})
	}
}

func TestStructuredELTActivitiesSuccessReturnsResult(t *testing.T) {
	repo := &fakeStructuredELTRepository{result: StructuredELTResult{RowsInserted: 32, SourceRows: 32}}
	a := StructuredELTActivities{Repository: repo, Attempt: func(context.Context) int32 { return 2 }}
	result, err := a.ExecuteStructuredELT(context.Background(), validELTSpec())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.RowsInserted != 32 || result.SourceRows != 32 {
		t.Fatalf("unexpected result: %+v", result)
	}
	if repo.spec.Attempt != 2 {
		t.Fatalf("attempt not threaded to repository spec: got %d", repo.spec.Attempt)
	}
}

func TestStructuredELTActivitiesDefaultsAttemptToOne(t *testing.T) {
	repo := &fakeStructuredELTRepository{result: StructuredELTResult{RowsInserted: 1, SourceRows: 1}}
	a := StructuredELTActivities{Repository: repo}
	if _, err := a.ExecuteStructuredELT(context.Background(), validELTSpec()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.spec.Attempt != 1 {
		t.Fatalf("expected default attempt 1, got %d", repo.spec.Attempt)
	}
}

func TestStructuredELTActivitiesPropagatesRepositoryError(t *testing.T) {
	repo := &fakeStructuredELTRepository{err: errors.New("boom")}
	a := StructuredELTActivities{Repository: repo}
	if _, err := a.ExecuteStructuredELT(context.Background(), validELTSpec()); err == nil {
		t.Fatal("expected repository error to propagate")
	}
}

func TestStructuredELTActivitiesFailsClosedOnCoverageMismatch(t *testing.T) {
	repo := &fakeStructuredELTRepository{result: StructuredELTResult{RowsInserted: 31, SourceRows: 32}}
	a := StructuredELTActivities{Repository: repo}
	result, err := a.ExecuteStructuredELT(context.Background(), validELTSpec())
	if err == nil {
		t.Fatal("expected coverage mismatch error")
	}
	if result != (StructuredELTResult{}) {
		t.Fatalf("expected zero-value result on mismatch, got %+v", result)
	}
}

func TestStructuredELTActivitiesSkippedReplayStillReconciles(t *testing.T) {
	repo := &fakeStructuredELTRepository{result: StructuredELTResult{RowsInserted: 32, SourceRows: 32, Skipped: true}}
	a := StructuredELTActivities{Repository: repo}
	result, err := a.ExecuteStructuredELT(context.Background(), validELTSpec())
	if err != nil {
		t.Fatalf("unexpected error on matching skipped replay: %v", err)
	}
	if !result.Skipped {
		t.Fatal("expected Skipped to be threaded through")
	}
}

func TestStructuredELTActivitiesSkippedReplayStillFailsOnMismatch(t *testing.T) {
	repo := &fakeStructuredELTRepository{result: StructuredELTResult{RowsInserted: 30, SourceRows: 32, Skipped: true}}
	a := StructuredELTActivities{Repository: repo}
	if _, err := a.ExecuteStructuredELT(context.Background(), validELTSpec()); err == nil {
		t.Fatal("expected coverage mismatch to be reported even on an idempotent replay")
	}
}

func TestStructuredELTFormatConstants(t *testing.T) {
	if StructuredELTFormatCSV != "csv" {
		t.Fatalf("csv format constant changed value: %q", StructuredELTFormatCSV)
	}
	if StructuredELTFormatNDJSON != "ndjson" {
		t.Fatalf("ndjson format constant changed value: %q", StructuredELTFormatNDJSON)
	}
}

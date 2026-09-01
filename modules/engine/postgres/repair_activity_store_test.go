package postgres

import (
	"encoding/json"
	"path/filepath"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
)

func TestRepairStoreRejectsPathsOutsideSharedRoots(t *testing.T) {
	root := t.TempDir()
	store, err := NewRepairActivityStore(&artifactRegistrationDB{}, []string{root})
	if err != nil {
		t.Fatal(err)
	}
	if !store.pathAllowed(filepath.Join(root, "source.xml")) {
		t.Fatal("shared-root child was rejected")
	}
	if store.pathAllowed(filepath.Join(filepath.Dir(root), "outside.xml")) {
		t.Fatal("path outside shared root was accepted")
	}
}

func TestFileURIPathRejectsNetworkAndNonFileLocators(t *testing.T) {
	for _, raw := range []string{"https://example.invalid/a", "file://remote/share/a", "relative.xml"} {
		if _, err := fileURIPath(raw); err == nil {
			t.Fatalf("fileURIPath(%q) accepted", raw)
		}
	}
}

func TestValidatePriorRepairAssessmentReturnsDurableReviewRequirement(t *testing.T) {
	assessmentID := uuid.MustParse("00000000-0000-0000-0000-000000000051")
	sourceID := uuid.MustParse("00000000-0000-0000-0000-000000000052")
	originalID := uuid.MustParse("00000000-0000-0000-0000-000000000053")
	detection := []byte(`{"needs_repair":true,"details":{"count":2}}`)
	preview := []byte(`{"sample":[]}`)
	spec := activities.RepairAssessmentSpec{
		SourceVersionRef: uiw.Ref(sourceID.String()), OriginalRef: uiw.Ref(originalID.String()),
		DeclaredFormat: "pdf", Detection: json.RawMessage(`{"details":{"count":2},"needs_repair":true}`),
		Preview: json.RawMessage(`{"sample":[]}`), ReviewRequired: false,
	}
	resultRef, _ := json.Marshal(map[string]string{"ref_kind": "repair_assessment", "ref_id": assessmentID.String()})
	result, err := validatePriorRepairAssessment(spec, assessmentID, sourceID, originalID, "pdf", resultRef, detection, preview)
	if err != nil {
		t.Fatal(err)
	}
	if result.ResultRef != uiw.Ref(assessmentID.String()) || !result.ReviewRequired {
		t.Fatalf("prior assessment did not preserve durable review requirement: %+v", result)
	}
}

func TestValidatePriorRepairAssessmentDiscardsChangedRetryContent(t *testing.T) {
	assessmentID := uuid.MustParse("00000000-0000-0000-0000-000000000061")
	sourceID := uuid.MustParse("00000000-0000-0000-0000-000000000062")
	originalID := uuid.MustParse("00000000-0000-0000-0000-000000000063")
	resultRef, _ := json.Marshal(map[string]string{"ref_kind": "repair_assessment", "ref_id": assessmentID.String()})
	spec := activities.RepairAssessmentSpec{
		SourceVersionRef: uiw.Ref(sourceID.String()), OriginalRef: uiw.Ref(originalID.String()),
		DeclaredFormat: "pdf", Detection: json.RawMessage(`{"needs_repair":false}`), Preview: json.RawMessage(`{"sample":[]}`),
	}
	result, err := validatePriorRepairAssessment(spec, assessmentID, sourceID, originalID, "pdf", resultRef,
		[]byte(`{"needs_repair":true}`), []byte(`{"sample":[]}`))
	if err != nil {
		t.Fatal(err)
	}
	if !result.ReviewRequired || result.ResultRef != uiw.Ref(assessmentID.String()) {
		t.Fatalf("changed retry content replaced the persisted assessment: %+v", result)
	}
}

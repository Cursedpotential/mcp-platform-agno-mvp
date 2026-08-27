package postgres

import (
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
)

func TestSelectionReceiptResultRoundTrip(t *testing.T) {
	receiptID := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	sourceID := uuid.MustParse("00000000-0000-0000-0000-000000000002")
	raw := selectionResultJSON(receiptID, "sms-parser", "2.1.0", "sms_xml_backup")
	selection, err := decodeSelectionReceipt(receiptID, raw, sourceID)
	if err != nil {
		t.Fatal(err)
	}
	if selection.SourceVersionRef != uiw.Ref(sourceID.String()) ||
		selection.ParserID != "sms-parser" || selection.ParserVersion != "2.1.0" ||
		selection.DeclaredFormat != parser.FormatID("sms_xml_backup") {
		t.Fatalf("selection = %+v", selection)
	}
}

func TestSelectionReceiptRejectsMutableOrMismatchedReference(t *testing.T) {
	receiptID := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	sourceID := uuid.MustParse("00000000-0000-0000-0000-000000000002")
	for name, raw := range map[string][]byte{
		"wrong kind":     []byte(`{"ref_kind":"parser_bundle","ref_id":"00000000-0000-0000-0000-000000000001","parser_id":"p","parser_version":"1","declared_format":"sms_xml_backup"}`),
		"wrong receipt":  selectionResultJSON(uuid.MustParse("00000000-0000-0000-0000-000000000003"), "p", "1", "sms_xml_backup"),
		"missing parser": []byte(`{"ref_kind":"parser_selection","ref_id":"00000000-0000-0000-0000-000000000001","parser_version":"1","declared_format":"sms_xml_backup"}`),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := decodeSelectionReceipt(receiptID, raw, sourceID); err == nil {
				t.Fatal("mutable or incomplete selection accepted")
			}
		})
	}
}

func TestBundleResultRoundTrip(t *testing.T) {
	ref, err := decodeBundleResult(bundleResultJSON("bundle:immutable:1"))
	if err != nil {
		t.Fatal(err)
	}
	if ref != "bundle:immutable:1" {
		t.Fatalf("bundle ref = %q", ref)
	}
	if _, err := decodeBundleResult([]byte(`{"ref_kind":"parser_selection","ref_id":"x"}`)); err == nil {
		t.Fatal("non-bundle result accepted")
	}
}

func TestParserStoreValidationRejectsIncompleteSpecs(t *testing.T) {
	if err := validateSelectionSpec(activities.ParserSelectionSpec{}); err == nil {
		t.Fatal("empty selection spec accepted")
	}
	if err := validateExecutionSpec(activities.ParserExecutionSpec{}); err == nil {
		t.Fatal("empty execution spec accepted")
	}
	validSelection := activities.ParserSelectionSpec{
		RequestID: "req", SourceVersionRef: "00000000-0000-0000-0000-000000000001",
		DeclaredFormat: "sms_xml_backup", ParserID: "p", ParserVersion: "1", Attempt: 1,
	}
	if err := validateSelectionSpec(validSelection); err != nil {
		t.Fatal(err)
	}
}

package postgres

import (
	"bytes"
	"context"
	"encoding/hex"
	"errors"
	"strings"
	"testing"

	"github.com/Cursedpotential/probata/engine/activities"
	"github.com/Cursedpotential/probata/engine/parser"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/lowcarbdev/sbv/pkg/parseonly"
)

func TestSelectionReceiptResultRoundTrip(t *testing.T) {
	receiptID := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	sourceID := uuid.MustParse("00000000-0000-0000-0000-000000000002")
	raw := selectionResultJSON(receiptID, "sms-parser", "2.1.0", "sms_xml_backup")
	selection, err := decodeSelectionReceipt(receiptID, raw, sourceID)
	if err != nil {
		t.Fatal(err)
	}
	if selection.SourceVersionRef != proffer.Ref(sourceID.String()) ||
		selection.ParserID != "sms-parser" || selection.ParserVersion != "2.1.0" ||
		selection.DeclaredFormat != parser.FormatID("sms_xml_backup") {
		t.Fatalf("selection = %+v", selection)
	}
}

func TestParserStoreRegistersArtifactThroughRetainedMembership(t *testing.T) {
	digest := strings.Repeat("ab", 32)
	db := &artifactRegistrationDB{}
	store, err := NewParserStore(db, func(context.Context, proffer.StageRequest, activities.PersistedParserSelection, parser.ParserInput) (parser.BundleWriter, error) {
		return nil, errors.New("unused")
	})
	if err != nil {
		t.Fatal(err)
	}
	locator, err := store.RegisterArtifact(context.Background(), parseonly.ArtifactRegistration{
		Artifact: parseonly.Artifact{
			Kind: parseonly.ArtifactAttachment, SourceAssociation: "00000000-0000-0000-0000-000000000042",
			AttemptID: strings.Repeat("a", 32), ParentSourcePos: "element:7", AttachmentOrdinal: 2,
			OriginalName: "photo.jpg", MIME: "image/jpeg", ByteCount: 19,
		},
		ObjectURI: "file:///data/proffer/parser-artifacts/object.bin", DigestSHA256: digest,
	})
	if err != nil {
		t.Fatal(err)
	}
	if locator.URI != "file:///data/proffer/parser-artifacts/object.bin" || locator.ContentHash != digest || !db.called {
		t.Fatalf("locator=%+v called=%v", locator, db.called)
	}
	if strings.Contains(db.logicalIdentity, digest) {
		t.Fatal("logical identity improperly includes content digest")
	}
	for _, required := range []string{"pg_advisory_xact_lock", "context.retained_object", "context.source_version_object", "artifact_occurrences", "status = 'retained'"} {
		if !strings.Contains(db.query, required) {
			t.Fatalf("registration query lacks %q", required)
		}
	}
}

func TestParserStoreRejectsDifferentBytesAtExistingLogicalIdentity(t *testing.T) {
	db := &artifactRegistrationDB{returnedDigest: strings.Repeat("cd", 32), identityExisted: true}
	store, err := NewParserStore(db, func(context.Context, proffer.StageRequest, activities.PersistedParserSelection, parser.ParserInput) (parser.BundleWriter, error) {
		return nil, errors.New("unused")
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = store.RegisterArtifact(context.Background(), parseonly.ArtifactRegistration{
		Artifact: parseonly.Artifact{
			Kind: parseonly.ArtifactAttachment, SourceAssociation: "00000000-0000-0000-0000-000000000042",
			ParentSourcePos: "element:7", AttachmentOrdinal: 2, ByteCount: 19,
		},
		ObjectURI: "file:///data/proffer/parser-artifacts/object.bin", DigestSHA256: strings.Repeat("ab", 32),
	})
	if err == nil || !strings.Contains(err.Error(), "logical identity conflicts") {
		t.Fatalf("conflicting logical identity error=%v", err)
	}
}

func TestParserStoreIdenticalBytesKeepDistinctSourceOccurrences(t *testing.T) {
	db := &artifactRegistrationDB{}
	store, err := NewParserStore(db, func(context.Context, proffer.StageRequest, activities.PersistedParserSelection, parser.ParserInput) (parser.BundleWriter, error) {
		return nil, errors.New("unused")
	})
	if err != nil {
		t.Fatal(err)
	}
	digest := strings.Repeat("ab", 32)
	for ordinal := uint64(0); ordinal < 2; ordinal++ {
		locator, err := store.RegisterArtifact(context.Background(), parseonly.ArtifactRegistration{
			Artifact: parseonly.Artifact{
				Kind: parseonly.ArtifactAttachment, SourceAssociation: "00000000-0000-0000-0000-000000000042",
				ParentSourcePos: "element:7", AttachmentOrdinal: ordinal, ByteCount: 19,
			},
			ObjectURI: "file:///data/proffer/parser-artifacts/shared.bin", DigestSHA256: digest,
		})
		if err != nil {
			t.Fatal(err)
		}
		if locator.ContentHash != digest {
			t.Fatalf("locator=%+v", locator)
		}
	}
	if len(db.logicalIdentities) != 2 || db.logicalIdentities[0] == db.logicalIdentities[1] {
		t.Fatalf("logical identities=%q", db.logicalIdentities)
	}
	if len(db.memberLocators) != 2 || bytes.Equal(db.memberLocators[0], db.memberLocators[1]) {
		t.Fatalf("member occurrences=%s", db.memberLocators)
	}
	for _, required := range []string{"jsonb_array_elements", "artifact_occurrences", "DO UPDATE"} {
		if !strings.Contains(db.query, required) {
			t.Fatalf("registrar SQL lacks repeated-occurrence contract %q", required)
		}
	}
}

type artifactRegistrationDB struct {
	called            bool
	query             string
	logicalIdentity   string
	logicalIdentities []string
	memberLocators    [][]byte
	returnedDigest    string
	identityExisted   bool
}

func (*artifactRegistrationDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, errors.New("unexpected transaction")
}
func (*artifactRegistrationDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("unexpected query")
}
func (db *artifactRegistrationDB) QueryRow(_ context.Context, query string, args ...any) pgx.Row {
	db.called = true
	db.query = query
	db.logicalIdentity = args[0].(string)
	db.logicalIdentities = append(db.logicalIdentities, args[0].(string))
	db.memberLocators = append(db.memberLocators, append([]byte(nil), args[9].([]byte)...))
	digest := db.returnedDigest
	if digest == "" {
		digest = hex.EncodeToString(args[6].([]byte))
	}
	return artifactRegistrationRow{uri: args[5].(string), digest: digest, size: args[7].(int64), identityExisted: db.identityExisted}
}

type artifactRegistrationRow struct {
	uri             string
	digest          string
	size            int64
	identityExisted bool
}

func (row artifactRegistrationRow) Scan(destinations ...any) error {
	*destinations[0].(*string) = "filesystem"
	*destinations[1].(*string) = row.uri
	*destinations[2].(*string) = row.digest
	*destinations[3].(*int64) = row.size
	*destinations[4].(*bool) = row.identityExisted
	*destinations[5].(*bool) = true
	return nil
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

package postgres

import (
	"context"
	"errors"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
)

func TestNewSourceLifecycleRepositoryRequiresDatabaseAndResolver(t *testing.T) {
	resolver := func(context.Context, uiw.Ref) (ImmutableAcquisition, error) {
		return ImmutableAcquisition{}, nil
	}
	if _, err := NewSourceLifecycleRepository(nil, resolver); err == nil {
		t.Fatal("nil database accepted")
	}
	if _, err := NewSourceLifecycleRepository(testDB{}, nil); err == nil {
		t.Fatal("nil resolver accepted")
	}
}

func TestImmutableAcquisitionValidationRequiresSuppliedDigestAndExactInlineBytes(t *testing.T) {
	valid := ImmutableAcquisition{
		StorageClass:  "inline",
		ObjectURI:     "upload:1",
		ContentSHA256: make([]byte, 32),
		ByteLength:    3,
		InlineBytes:   []byte("abc"),
	}
	if err := valid.validate(); err != nil {
		t.Fatal(err)
	}
	for name, object := range map[string]ImmutableAcquisition{
		"missing digest": {StorageClass: "filesystem", ObjectURI: "upload:1", ByteLength: 0},
		"bad digest":     {StorageClass: "filesystem", ObjectURI: "upload:1", ContentSHA256: make([]byte, 31)},
		"bad class":      {StorageClass: "mutable", ObjectURI: "upload:1", ContentSHA256: make([]byte, 32)},
		"inline length":  {StorageClass: "inline", ObjectURI: "upload:1", ContentSHA256: make([]byte, 32), ByteLength: 4, InlineBytes: []byte("abc")},
		"external bytes": {StorageClass: "filesystem", ObjectURI: "upload:1", ContentSHA256: make([]byte, 32), ByteLength: 3, InlineBytes: []byte("abc")},
	} {
		t.Run(name, func(t *testing.T) {
			if err := object.validate(); err == nil {
				t.Fatal("invalid immutable object accepted")
			}
		})
	}
}

func TestLifecycleKeysAreDeterministicAndDistinct(t *testing.T) {
	registration := activities.SourceRegistrationSpec{RequestID: "request-1", AcquisitionRef: "upload:1", DeclaredFormat: "zip"}
	if registrationKey(registration) != registrationKey(registration) {
		t.Fatal("registration key is not deterministic")
	}
	retention := activities.OriginalRetentionSpec{RequestID: "request-1", SourceVersionRef: "00000000-0000-0000-0000-000000000001", AcquisitionRef: "upload:1"}
	if retentionKey(retention) != retentionKey(retention) {
		t.Fatal("retention key is not deterministic")
	}
	if registrationKey(registration) == retentionKey(retention) {
		t.Fatal("registration and retention keys collide")
	}
}

func TestLifecycleSpecValidation(t *testing.T) {
	if err := validateRegistrationSpec(activities.SourceRegistrationSpec{RequestID: "r", AcquisitionRef: "a", DeclaredFormat: "zip", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	if err := validateRetentionSpec(activities.OriginalRetentionSpec{RequestID: "r", SourceVersionRef: "v", AcquisitionRef: "a", Attempt: 1}); err != nil {
		t.Fatal(err)
	}
	for _, invalid := range []activities.SourceRegistrationSpec{
		{RequestID: "", AcquisitionRef: "a", DeclaredFormat: "zip", Attempt: 1},
		{RequestID: "r", AcquisitionRef: "", DeclaredFormat: "zip", Attempt: 1},
		{RequestID: "r", AcquisitionRef: "a", DeclaredFormat: "", Attempt: 1},
		{RequestID: "r", AcquisitionRef: "a", DeclaredFormat: "zip", Attempt: 0},
	} {
		if err := validateRegistrationSpec(invalid); err == nil {
			t.Fatal("invalid registration accepted")
		}
	}
}

func TestUUIDOrEmptyHandlesNullAndValue(t *testing.T) {
	if got := uuidOrEmpty(pgtype.UUID{}); got != "" {
		t.Fatalf("null UUID = %q", got)
	}
	id := uuid.New()
	var value pgtype.UUID
	if err := value.Scan(id.String()); err != nil {
		t.Fatal(err)
	}
	if got := uuidOrEmpty(value); got != id.String() {
		t.Fatalf("UUID = %q, want %q", got, id)
	}
}

func TestLifecycleCleanupIgnoresCallerCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	cleanup, cleanupCancel := lifecycleCleanup(ctx)
	defer cleanupCancel()
	if err := cleanup.Err(); err != nil {
		t.Fatalf("cleanup context already canceled: %v", err)
	}
	if _, ok := cleanup.Deadline(); !ok {
		t.Fatal("cleanup context has no bounded deadline")
	}
}

// testDB only exercises constructor validation and deliberately cannot start
// a transaction. Database behavior is covered by the production SQL contract
// and the live migration/integration gate, without adding a second fake pgx
// implementation that could drift from PostgreSQL.
type testDB struct{}

func (testDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) {
	return nil, errors.New("not implemented")
}
func (testDB) Query(context.Context, string, ...any) (pgx.Rows, error) {
	return nil, errors.New("not implemented")
}
func (testDB) QueryRow(context.Context, string, ...any) pgx.Row { return nil }

package activities

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

type lifecycleStore struct {
	registerSpec SourceRegistrationSpec
	retainSpec   OriginalRetentionSpec
	registerRef  proffer.Ref
	registerRcpt proffer.Ref
	retainRef    proffer.Ref
	retainRcpt   proffer.Ref
	registerErr  error
	retainErr    error
}

func (s *lifecycleStore) RegisterSource(_ context.Context, spec SourceRegistrationSpec) (proffer.Ref, proffer.Ref, error) {
	s.registerSpec = spec
	return s.registerRef, s.registerRcpt, s.registerErr
}

func (s *lifecycleStore) RetainOriginal(_ context.Context, spec OriginalRetentionSpec) (proffer.Ref, proffer.Ref, error) {
	s.retainSpec = spec
	return s.retainRef, s.retainRcpt, s.retainErr
}

func TestRegisterSourceIsIdentityOnlyAndReturnsDurableRefs(t *testing.T) {
	store := &lifecycleStore{registerRef: "source-version:1", registerRcpt: "receipt:register"}
	activities := SourceLifecycleActivities{Store: store, Attempt: func(context.Context) int32 { return 4 }}
	result, err := activities.RegisterSource(context.Background(), proffer.StageRequest{
		RequestID:      "workflow:1",
		MatterID:       "11111111-1111-1111-1111-111111111111",
		CourtCaseID:    "22222222-2222-2222-2222-222222222222",
		DeclaredFormat: "zip_archive",
		Refs:           map[string]proffer.Ref{"acquisition": "upload:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result != (proffer.StageResult{Stage: stagegraph.RegisterSource, Status: proffer.StatusSuccess, Ref: "source-version:1", ReceiptRef: "receipt:register"}) {
		t.Fatalf("result = %+v", result)
	}
	want := SourceRegistrationSpec{RequestID: "workflow:1", MatterID: "11111111-1111-1111-1111-111111111111", CourtCaseID: "22222222-2222-2222-2222-222222222222", AcquisitionRef: "upload:1", DeclaredFormat: "zip_archive", Attempt: 4}
	if store.registerSpec != want {
		t.Fatalf("registration spec = %+v, want %+v", store.registerSpec, want)
	}
}

func TestRetainOriginalBindsRegisteredVersionAndReturnsDurableRefs(t *testing.T) {
	store := &lifecycleStore{retainRef: "retained-object:1", retainRcpt: "receipt:retain"}
	activities := SourceLifecycleActivities{Store: store, Attempt: func(context.Context) int32 { return 2 }}
	result, err := activities.RetainOriginal(context.Background(), proffer.StageRequest{
		RequestID:        "workflow:1",
		SourceVersionRef: "source-version:1",
		Refs:             map[string]proffer.Ref{"acquisition": "upload:1"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result != (proffer.StageResult{Stage: stagegraph.RetainOriginal, Status: proffer.StatusSuccess, Ref: "retained-object:1", ReceiptRef: "receipt:retain"}) {
		t.Fatalf("result = %+v", result)
	}
	want := OriginalRetentionSpec{RequestID: "workflow:1", SourceVersionRef: "source-version:1", AcquisitionRef: "upload:1", Attempt: 2}
	if store.retainSpec != want {
		t.Fatalf("retention spec = %+v, want %+v", store.retainSpec, want)
	}
}

func TestSourceLifecycleRejectsMissingCompactInputsBeforeStore(t *testing.T) {
	store := &lifecycleStore{registerRef: "source-version:1", registerRcpt: "receipt:register", retainRef: "object:1", retainRcpt: "receipt:retain"}
	activities := SourceLifecycleActivities{Store: store}
	tests := []struct {
		name string
		call func() error
		want string
	}{
		{
			name: "register request",
			call: func() error {
				_, err := activities.RegisterSource(context.Background(), proffer.StageRequest{DeclaredFormat: "zip_archive", Refs: map[string]proffer.Ref{"acquisition": "upload:1"}})
				return err
			},
			want: "request id",
		},
		{
			name: "register acquisition",
			call: func() error {
				_, err := activities.RegisterSource(context.Background(), proffer.StageRequest{RequestID: "workflow:1", DeclaredFormat: "zip_archive"})
				return err
			},
			want: "acquisition",
		},
		{
			name: "retain source version",
			call: func() error {
				_, err := activities.RetainOriginal(context.Background(), proffer.StageRequest{RequestID: "workflow:1", Refs: map[string]proffer.Ref{"acquisition": "upload:1"}})
				return err
			},
			want: "source version",
		},
		{
			name: "retain acquisition",
			call: func() error {
				_, err := activities.RetainOriginal(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source-version:1"})
				return err
			},
			want: "acquisition",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := test.call()
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("error = %v, want substring %q", err, test.want)
			}
		})
	}
}

func TestSourceLifecyclePropagatesStoreFailureAndRequiresBothRefs(t *testing.T) {
	store := &lifecycleStore{registerErr: errors.New("duplicate workflow"), retainErr: errors.New("source is not registered")}
	activities := SourceLifecycleActivities{Store: store}
	request := proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source-version:1", DeclaredFormat: "zip_archive", Refs: map[string]proffer.Ref{"acquisition": "upload:1"}}
	if _, err := activities.RegisterSource(context.Background(), request); err == nil || !strings.Contains(err.Error(), "duplicate workflow") {
		t.Fatalf("register error = %v", err)
	}
	if _, err := activities.RetainOriginal(context.Background(), request); err == nil || !strings.Contains(err.Error(), "not registered") {
		t.Fatalf("retain error = %v", err)
	}

	for _, test := range []struct {
		name string
		call func() (proffer.StageResult, error)
	}{
		{name: "register missing result", call: func() (proffer.StageResult, error) {
			return (SourceLifecycleActivities{Store: &lifecycleStore{registerRcpt: "receipt"}}).RegisterSource(context.Background(), proffer.StageRequest{RequestID: "workflow:1", DeclaredFormat: "zip", Refs: map[string]proffer.Ref{"acquisition": "upload"}})
		}},
		{name: "register missing receipt", call: func() (proffer.StageResult, error) {
			return (SourceLifecycleActivities{Store: &lifecycleStore{registerRef: "source"}}).RegisterSource(context.Background(), proffer.StageRequest{RequestID: "workflow:1", DeclaredFormat: "zip", Refs: map[string]proffer.Ref{"acquisition": "upload"}})
		}},
		{name: "retain missing result", call: func() (proffer.StageResult, error) {
			return (SourceLifecycleActivities{Store: &lifecycleStore{retainRcpt: "receipt"}}).RetainOriginal(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source", Refs: map[string]proffer.Ref{"acquisition": "upload"}})
		}},
		{name: "retain missing receipt", call: func() (proffer.StageResult, error) {
			return (SourceLifecycleActivities{Store: &lifecycleStore{retainRef: "object"}}).RetainOriginal(context.Background(), proffer.StageRequest{RequestID: "workflow:1", SourceVersionRef: "source", Refs: map[string]proffer.Ref{"acquisition": "upload"}})
		}},
	} {
		t.Run(test.name, func(t *testing.T) {
			if _, err := test.call(); err == nil {
				t.Fatal("missing durable reference accepted")
			}
		})
	}
}

func TestSourceLifecycleHonorsCancellationBeforeStore(t *testing.T) {
	store := &lifecycleStore{registerRef: "source", registerRcpt: "receipt"}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := (SourceLifecycleActivities{Store: store}).RegisterSource(ctx, proffer.StageRequest{
		RequestID: "workflow:1", DeclaredFormat: "zip", Refs: map[string]proffer.Ref{"acquisition": "upload"},
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("error = %v, want context canceled", err)
	}
	if store.registerSpec != (SourceRegistrationSpec{}) {
		t.Fatal("store was called after cancellation")
	}
}

// Package sourcecontext defines the framework-neutral, reference-producing
// contract for actor-bound intake metadata submissions.
package sourcecontext

import (
	"context"
	"crypto/sha256"
	"time"
)

type ObservedSource struct {
	Key               string `json:"key"`
	Name              string `json:"name"`
	ByteLength        int64  `json:"byte_length"`
	ETag              string `json:"etag"`
	PreviewSHA256     string `json:"preview_sha256"`
	VerificationState string `json:"verification_state"`
}

type HumanAssertions struct {
	SourceClass          string `json:"source_class"`
	SourcePrincipal      string `json:"source_principal,omitempty"`
	OtherParty           string `json:"other_party,omitempty"`
	AcquiredAt           string `json:"acquired_at,omitempty"`
	AcquisitionMethod    string `json:"acquisition_method,omitempty"`
	AcquisitionAuthority string `json:"acquisition_authority,omitempty"`
	SourceDevice         string `json:"source_device,omitempty"`
	DeviceCustodian      string `json:"device_custodian,omitempty"`
	OccurredStart        string `json:"occurred_start,omitempty"`
	OccurredEnd          string `json:"occurred_end,omitempty"`
	DateCertainty        string `json:"date_certainty,omitempty"`
	Context              string `json:"context,omitempty"`
	Notes                string `json:"notes,omitempty"`
}

type Spec struct {
	RequestID, MatterID, CourtCaseID, SourceRef  string
	SupersedesRef                                string
	ObservedSource                               ObservedSource
	Assertions                                   HumanAssertions
	ChangeReason, ActorSubjectUID, ActorUsername string
	IdempotencyKey                               string
	ContentDigest                                [sha256.Size]byte
}

type Receipt struct {
	SourceContextRef string    `json:"source_context_ref"`
	ReceiptRef       string    `json:"receipt_ref"`
	ContentDigest    string    `json:"content_digest"`
	Revision         int       `json:"revision"`
	RecordedAt       time.Time `json:"recorded_at"`
}

type Writer interface {
	PersistSourceContext(context.Context, Spec) (Receipt, error)
}

type Validator interface {
	ValidateSourceContext(context.Context, string, string, string, string, string) error
}

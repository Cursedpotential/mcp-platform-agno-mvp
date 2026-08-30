package parser

import (
	"errors"
	"fmt"
	"time"
)

// NativeRecordKind is the parser-boundary record kind. It preserves a
// decoder's factual classification before normalization decides how to map
// the record into the platform's normalized record types.
type NativeRecordKind string

const (
	NativeKindMessage   NativeRecordKind = "message"
	NativeKindCall      NativeRecordKind = "call"
	NativeKindRow       NativeRecordKind = "row"
	NativeKindObject    NativeRecordKind = "object"
	NativeKindVoicemail NativeRecordKind = "voicemail"
	NativeKindEmail     NativeRecordKind = "email"
	NativeKindOther     NativeRecordKind = "other"
)

func (k NativeRecordKind) Validate() error {
	switch k {
	case NativeKindMessage, NativeKindCall, NativeKindRow, NativeKindObject,
		NativeKindVoicemail, NativeKindEmail, NativeKindOther:
		return nil
	default:
		return fmt.Errorf("unsupported native record kind %q", k)
	}
}

type CallDirection string

const (
	CallDirectionIncoming CallDirection = "incoming"
	CallDirectionOutgoing CallDirection = "outgoing"
	CallDirectionUnknown  CallDirection = "unknown"
)

func (d CallDirection) Validate() error {
	switch d {
	case CallDirectionIncoming, CallDirectionOutgoing, CallDirectionUnknown:
		return nil
	default:
		return fmt.Errorf("unsupported call direction %q", d)
	}
}

type CallDisposition string

const (
	CallDispositionCompleted CallDisposition = "completed"
	CallDispositionMissed    CallDisposition = "missed"
	CallDispositionVoicemail CallDisposition = "voicemail"
	CallDispositionRejected  CallDisposition = "rejected"
	CallDispositionRefused   CallDisposition = "refused"
	CallDispositionUnknown   CallDisposition = "unknown"
)

func (d CallDisposition) Validate() error {
	switch d {
	case CallDispositionCompleted, CallDispositionMissed, CallDispositionVoicemail,
		CallDispositionRejected, CallDispositionRefused, CallDispositionUnknown:
		return nil
	default:
		return fmt.Errorf("unsupported call disposition %q", d)
	}
}

// NativeCallFields keeps call semantics out of a generic message body.
// DurationSeconds is a pointer because an explicitly reported zero-second
// call is different from a source that reported no duration at all.
type NativeCallFields struct {
	Direction       CallDirection   `json:"direction"`
	Disposition     CallDisposition `json:"disposition"`
	Missed          bool            `json:"missed"`
	DurationSeconds *uint64         `json:"duration_seconds,omitempty"`
}

func (c NativeCallFields) Validate() error {
	if err := c.Direction.Validate(); err != nil {
		return err
	}
	if err := c.Disposition.Validate(); err != nil {
		return err
	}
	if c.Missed != (c.Disposition == CallDispositionMissed) {
		return errors.New("call missed flag must agree with missed disposition")
	}
	return nil
}

// CommonNativeFields is the import-light, source-native shape emitted by
// adapters that can promote common messaging/call coordinates. NativeFields
// remains an open JSON object for format-specific adapters; this type prevents
// the shared SBV boundary from flattening calls into message content.
type CommonNativeFields struct {
	RecordKind   NativeRecordKind  `json:"record_kind"`
	Body         string            `json:"body,omitempty"`
	Sender       string            `json:"sender,omitempty"`
	Recipients   []string          `json:"recipients,omitempty"`
	Participants []string          `json:"participants,omitempty"`
	OccurredAt   *time.Time        `json:"occurred_at,omitempty"`
	Call         *NativeCallFields `json:"call,omitempty"`
}

func (f CommonNativeFields) Validate() error {
	if err := f.RecordKind.Validate(); err != nil {
		return err
	}
	if f.RecordKind == NativeKindCall {
		if f.Call == nil {
			return errors.New("native call record requires call fields")
		}
		return f.Call.Validate()
	}
	if f.Call != nil {
		return fmt.Errorf("native record kind %q cannot carry call fields", f.RecordKind)
	}
	return nil
}

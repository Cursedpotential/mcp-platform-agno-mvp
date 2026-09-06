package normalize

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/Cursedpotential/probata/engine/parser"
)

const (
	GenericMessageNormalizerID      = "generic_message_normalizer"
	GenericMessageNormalizerVersion = "1.1.0"
)

// GenericMessageNormalizer is the platform's baseline, format-agnostic
// normalizer. It is adequate for representative message-shaped ingest, not a
// per-format specialist: it inspects only native_fields shape, never a
// declared format identity.
//
// It emits exactly one normalized record per parsed raw record, in raw
// ordinal order, and never skips a parsed raw record — a normalizer that
// silently drops parsed records reproduces the exact bug already found and
// fixed once in this platform's parsers (a bodyless-MMS parser silently
// dropping 516 records). A raw record whose native fields do not look like a
// message still becomes one record_type=other normalized record wrapping the
// native fields verbatim, so no parsed raw record is ever lost.
//
// persist_lineage_activity depends on this 1:1, order-preserving
// correspondence: it derives normalization_lineage purely by zipping the
// ordered parsed-raw-record sequence against the ordered normalized-record
// sequence, since normalize_generation_activity's bundle reference is not
// itself passed to persist_lineage_activity (see engine/proffer/workflow.go).
type GenericMessageNormalizer struct{}

func (GenericMessageNormalizer) Capability() Capability {
	return Capability{
		ContractVersion:   ContractVersion,
		NormalizerID:      GenericMessageNormalizerID,
		NormalizerVersion: GenericMessageNormalizerVersion,
	}
}

// genericMessageFields covers the common shapes a generic chat/message/SMS
// export's native_fields take. Any field this normalizer does not recognize
// remains fully preserved: unrecognized native fields are never dropped, only
// left out of the derived Participants/body convenience fields.
type genericMessageFields struct {
	RecordKind   parser.NativeRecordKind  `json:"record_kind"`
	Call         *parser.NativeCallFields `json:"call"`
	Body         *string                  `json:"body"`
	Text         *string                  `json:"text"`
	Message      *string                  `json:"message"`
	Sender       *string                  `json:"sender"`
	From         *string                  `json:"from"`
	Recipient    *string                  `json:"recipient"`
	Recipients   []string                 `json:"recipients"`
	To           []string                 `json:"to"`
	Timestamp    *string                  `json:"timestamp"`
	OccurredAt   *string                  `json:"occurred_at"`
	SentAt       *string                  `json:"sent_at"`
	Participants []string                 `json:"participants"`
}

// genericMessageMetadata recognizes the lossless SBV adapter metadata shape
// as a compatibility path for bundles written before SBV message values were
// promoted into native_fields. New bundles use native_fields directly; the
// metadata fallback prevents those already-retained raw rows from becoming
// empty normalized messages.
type genericMessageMetadata struct {
	SBVContent      *string  `json:"sbv_content"`
	SBVSender       *string  `json:"sbv_sender"`
	SBVParticipants []string `json:"sbv_participants"`
	SBVRecipients   []struct {
		Identity string `json:"identity"`
		Role     string `json:"role"`
	} `json:"sbv_recipients"`
	OccurredAt *string `json:"occurred_at"`
}

func (GenericMessageNormalizer) Normalize(ctx context.Context, input NormalizerInput, sink BundleSink) (BundleAccounting, error) {
	if err := input.Validate(); err != nil {
		return BundleAccounting{}, err
	}
	var emitted uint64
	for {
		if err := ctx.Err(); err != nil {
			return BundleAccounting{}, err
		}
		raw, err := input.Records.Next(ctx)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return BundleAccounting{}, fmt.Errorf("read raw record: %w", err)
		}
		if raw.RecordStatus != parser.StatusParsed {
			// Non-parsed spans (rejected/malformed/unknown/unparsed/envelope)
			// are raw-custody rows, not semantic content; they never become a
			// normalized record.
			continue
		}
		record, err := normalizeOne(input, raw, emitted)
		if err != nil {
			return BundleAccounting{}, fmt.Errorf("normalize raw record ordinal %d: %w", raw.RecordOrdinal, err)
		}
		if err := sink.Emit(ctx, record); err != nil {
			return BundleAccounting{}, fmt.Errorf("emit normalized record %d: %w", emitted, err)
		}
		emitted++
	}
	return BundleAccounting{Emitted: emitted}, nil
}

func normalizeOne(input NormalizerInput, raw RawRecordView, outputOrdinal uint64) (RecordEnvelope, error) {
	var fields genericMessageFields
	if len(raw.NativeFields) > 0 {
		if err := json.Unmarshal(raw.NativeFields, &fields); err != nil {
			return RecordEnvelope{}, fmt.Errorf("decode native fields: %w", err)
		}
	}
	if len(raw.NativeMetadata) > 0 {
		var metadata genericMessageMetadata
		if err := json.Unmarshal(raw.NativeMetadata, &metadata); err != nil {
			return RecordEnvelope{}, fmt.Errorf("decode native metadata: %w", err)
		}
		mergeMessageMetadata(&fields, metadata)
	}
	if fields.RecordKind != "" || fields.Call != nil {
		if err := (parser.CommonNativeFields{RecordKind: fields.RecordKind, Call: fields.Call}).Validate(); err != nil {
			return RecordEnvelope{}, fmt.Errorf("validate typed native fields: %w", err)
		}
	}

	body := firstNonNil(fields.Body, fields.Text, fields.Message)
	occurredAtRaw := firstNonEmpty(fields.Timestamp, fields.OccurredAt, fields.SentAt)

	var occurredAt *time.Time
	granularity := GranularityUnknown
	certainty := CertaintyUnknown
	if occurredAtRaw != "" {
		if parsed, err := time.Parse(time.RFC3339, occurredAtRaw); err == nil {
			occurredAt = &parsed
			granularity = GranularitySecond
			certainty = CertaintyExact
		}
	}

	recordType := RecordTypeOther
	content := raw.NativeFields
	if fields.RecordKind == parser.NativeKindCall {
		recordType = RecordTypeCall
		encoded, err := encodeCallContent(*fields.Call, body)
		if err != nil {
			return RecordEnvelope{}, err
		}
		content = encoded
	} else if fields.RecordKind == parser.NativeKindMessage || body != nil {
		recordType = RecordTypeMessage
		bodyText := ""
		if body != nil {
			bodyText = *body
		}
		encoded, err := json.Marshal(map[string]any{"body": bodyText})
		if err != nil {
			return RecordEnvelope{}, fmt.Errorf("encode message content: %w", err)
		}
		content = encoded
	} else if len(content) == 0 {
		encoded, err := json.Marshal(map[string]any{})
		if err != nil {
			return RecordEnvelope{}, fmt.Errorf("encode empty content: %w", err)
		}
		content = encoded
	} else {
		encoded, err := json.Marshal(map[string]any{"native_fields": json.RawMessage(content)})
		if err != nil {
			return RecordEnvelope{}, fmt.Errorf("encode passthrough content: %w", err)
		}
		content = encoded
	}

	participants := deriveParticipants(fields)

	sourceAvailableFrom := input.AcquiredAt
	if input.SourceProvenanceClass == ProvenanceFirstPartyAuthored && occurredAt != nil {
		sourceAvailableFrom = *occurredAt
	}

	return RecordEnvelope{
		RecordOrdinal:        outputOrdinal,
		RecordType:           recordType,
		OccurredAt:           occurredAt,
		OccurredAtRaw:        occurredAtRaw,
		TimestampGranularity: granularity,
		TimestampCertainty:   certainty,
		SourceAvailableFrom:  sourceAvailableFrom,
		ProvenanceClass:      input.SourceProvenanceClass,
		Participants:         participants,
		Content:              content,
		Lineage: []LineageEdge{{
			RawRecordOrdinal: raw.RecordOrdinal,
			DerivationRole:   DerivationPrimarySource,
		}},
	}, nil
}

type normalizedCallContent struct {
	Direction       parser.CallDirection   `json:"direction"`
	Disposition     parser.CallDisposition `json:"disposition"`
	Missed          bool                   `json:"missed"`
	DurationSeconds *uint64                `json:"duration_seconds,omitempty"`
	Body            *string                `json:"body,omitempty"`
}

func encodeCallContent(call parser.NativeCallFields, body *string) (json.RawMessage, error) {
	if err := call.Validate(); err != nil {
		return nil, fmt.Errorf("validate native call fields: %w", err)
	}
	encoded, err := json.Marshal(normalizedCallContent{
		Direction: call.Direction, Disposition: call.Disposition, Missed: call.Missed,
		DurationSeconds: call.DurationSeconds, Body: body,
	})
	if err != nil {
		return nil, fmt.Errorf("encode call content: %w", err)
	}
	return encoded, nil
}

func deriveParticipants(fields genericMessageFields) []Participant {
	var participants []Participant
	if sender := firstNonEmpty(fields.Sender, fields.From); sender != "" {
		participants = append(participants, Participant{Role: RoleSender, Identifier: sender})
	}
	seen := make(map[string]struct{})
	addRecipient := func(identifier string) {
		if identifier == "" {
			return
		}
		if _, exists := seen[identifier]; exists {
			return
		}
		seen[identifier] = struct{}{}
		participants = append(participants, Participant{Role: RoleRecipient, Identifier: identifier})
	}
	if fields.Recipient != nil {
		addRecipient(*fields.Recipient)
	}
	for _, recipient := range fields.Recipients {
		addRecipient(recipient)
	}
	for _, recipient := range fields.To {
		addRecipient(recipient)
	}
	for _, participant := range fields.Participants {
		identifier := participant
		if identifier == "" {
			continue
		}
		if _, exists := seen[identifier]; exists {
			continue
		}
		seen[identifier] = struct{}{}
		participants = append(participants, Participant{Role: RoleUnknown, Identifier: identifier})
	}
	if len(participants) == 0 {
		participants = []Participant{{Role: RoleUnknown, Identifier: "unknown"}}
	}
	return participants
}

func mergeMessageMetadata(fields *genericMessageFields, metadata genericMessageMetadata) {
	if fields.Body == nil && fields.Text == nil && fields.Message == nil {
		fields.Body = metadata.SBVContent
	}
	if fields.Sender == nil && fields.From == nil {
		fields.Sender = metadata.SBVSender
	}
	if fields.Timestamp == nil && fields.OccurredAt == nil && fields.SentAt == nil {
		fields.OccurredAt = metadata.OccurredAt
	}
	if len(fields.Recipients) == 0 && len(fields.To) == 0 && fields.Recipient == nil {
		for _, recipient := range metadata.SBVRecipients {
			if recipient.Identity != "" {
				fields.Recipients = append(fields.Recipients, recipient.Identity)
			}
		}
	}
	if len(fields.Participants) == 0 {
		fields.Participants = append(fields.Participants, metadata.SBVParticipants...)
	}
}

func firstNonNil(values ...*string) *string {
	for _, value := range values {
		if value != nil {
			return value
		}
	}
	return nil
}

func firstNonEmpty(values ...*string) string {
	for _, value := range values {
		if value != nil && *value != "" {
			return *value
		}
	}
	return ""
}

var _ Adapter = GenericMessageNormalizer{}

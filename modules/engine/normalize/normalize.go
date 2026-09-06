// Package normalize defines the platform-owned, normalize-only adapter
// boundary consumed by normalize_generation_activity. It mirrors
// engine/parser's shape deliberately: it has no Temporal, database, hash, or
// persistence dependency, and an Adapter streams already-persisted raw
// records to a caller-owned BundleWriter and returns only compact results.
//
// Persisting context.normalized_record_identity and
// context.normalization_lineage rows is NOT this package's job — that is
// persist_normalized_generation_activity and persist_lineage_activity, per
// engine/stagegraph's single-responsibility split ("normalize is
// transform-only, persist is the only write").
package normalize

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Cursedpotential/probata/engine/parser"
)

const ContractVersion = "1.0.0"

// RecordType mirrors NormalizedRecord (v1) record_type.
type RecordType string

const (
	RecordTypeMessage  RecordType = "message"
	RecordTypeCall     RecordType = "call"
	RecordTypeEvent    RecordType = "event"
	RecordTypeMedia    RecordType = "media"
	RecordTypeDocument RecordType = "document"
	RecordTypeOther    RecordType = "other"
)

func (t RecordType) Validate() error {
	switch t {
	case RecordTypeMessage, RecordTypeCall, RecordTypeEvent, RecordTypeMedia, RecordTypeDocument, RecordTypeOther:
		return nil
	default:
		return fmt.Errorf("unsupported normalized record type %q", t)
	}
}

// TimestampGranularity mirrors NormalizedRecord (v1) timestamp_granularity.
type TimestampGranularity string

const (
	GranularitySubsecond TimestampGranularity = "subsecond"
	GranularitySecond    TimestampGranularity = "second"
	GranularityMinute    TimestampGranularity = "minute"
	GranularityHour      TimestampGranularity = "hour"
	GranularityDay       TimestampGranularity = "day"
	GranularityMonth     TimestampGranularity = "month"
	GranularityYear      TimestampGranularity = "year"
	GranularityUnknown   TimestampGranularity = "unknown"
)

func (g TimestampGranularity) Validate() error {
	switch g {
	case GranularitySubsecond, GranularitySecond, GranularityMinute, GranularityHour,
		GranularityDay, GranularityMonth, GranularityYear, GranularityUnknown:
		return nil
	default:
		return fmt.Errorf("unsupported timestamp granularity %q", g)
	}
}

// TimestampCertainty mirrors NormalizedRecord (v1) timestamp_certainty.
type TimestampCertainty string

const (
	CertaintyExact       TimestampCertainty = "exact"
	CertaintyApproximate TimestampCertainty = "approximate"
	CertaintyInferred    TimestampCertainty = "inferred"
	CertaintyUncertain   TimestampCertainty = "uncertain"
	CertaintyUnknown     TimestampCertainty = "unknown"
)

func (c TimestampCertainty) Validate() error {
	switch c {
	case CertaintyExact, CertaintyApproximate, CertaintyInferred, CertaintyUncertain, CertaintyUnknown:
		return nil
	default:
		return fmt.Errorf("unsupported timestamp certainty %q", c)
	}
}

// ProvenanceClass mirrors common.schema.json's ProvenanceClass. It is a
// source-version-level fact resolved by the Store from context.source, never
// guessed per-record by an Adapter.
type ProvenanceClass string

const (
	ProvenanceFirstPartyAuthored ProvenanceClass = "first_party_authored"
	ProvenanceAcquiredThirdParty ProvenanceClass = "acquired_third_party"
	ProvenanceSystemGenerated    ProvenanceClass = "system_generated"
	ProvenanceUnknown            ProvenanceClass = "unknown"
)

func (p ProvenanceClass) Validate() error {
	switch p {
	case ProvenanceFirstPartyAuthored, ProvenanceAcquiredThirdParty, ProvenanceSystemGenerated, ProvenanceUnknown:
		return nil
	default:
		return fmt.Errorf("unsupported provenance class %q", p)
	}
}

// ParticipantRole mirrors normalized-record.schema.json's Participant.role.
type ParticipantRole string

const (
	RoleSender      ParticipantRole = "sender"
	RoleRecipient   ParticipantRole = "recipient"
	RoleCC          ParticipantRole = "cc"
	RoleBCC         ParticipantRole = "bcc"
	RoleParticipant ParticipantRole = "participant"
	RoleUnknown     ParticipantRole = "unknown"
)

func (r ParticipantRole) Validate() error {
	switch r {
	case RoleSender, RoleRecipient, RoleCC, RoleBCC, RoleParticipant, RoleUnknown:
		return nil
	default:
		return fmt.Errorf("unsupported participant role %q", r)
	}
}

// Participant mirrors normalized-record.schema.json's Participant. The
// acquired conversation's actual participants only; AGENTS.md forbids
// inventing the owner as a participant on an acquired_third_party record.
type Participant struct {
	Role        ParticipantRole
	Identifier  string
	DisplayName string
}

func (p Participant) Validate() error {
	if err := p.Role.Validate(); err != nil {
		return err
	}
	if strings.TrimSpace(p.Identifier) == "" {
		return errors.New("participant requires a non-empty identifier")
	}
	return nil
}

// DerivationRole mirrors normalization-lineage.schema.json's derivation_role.
type DerivationRole string

const (
	DerivationPrimarySource    DerivationRole = "primary_source"
	DerivationSupplementary    DerivationRole = "supplementary"
	DerivationMergeSource      DerivationRole = "merge_source"
	DerivationAttachmentSource DerivationRole = "attachment_source"
	DerivationCorrectionSource DerivationRole = "correction_source"
)

func (d DerivationRole) Validate() error {
	switch d {
	case DerivationPrimarySource, DerivationSupplementary, DerivationMergeSource,
		DerivationAttachmentSource, DerivationCorrectionSource:
		return nil
	default:
		return fmt.Errorf("unsupported derivation role %q", d)
	}
}

// FieldMapping mirrors normalization-lineage.schema.json's field_map entries.
type FieldMapping struct {
	NormalizedField string
	RawFieldPath    string
	Transform       string
}

func (m FieldMapping) Validate() error {
	if strings.TrimSpace(m.NormalizedField) == "" || strings.TrimSpace(m.RawFieldPath) == "" {
		return errors.New("field mapping requires normalized_field and raw_field_path")
	}
	return nil
}

// LineageEdge names one raw record, by its ordinal within the same raw
// generation, that a normalized record derives from. persist_lineage_activity
// resolves RawRecordOrdinal to the durable raw_record_id at persistence time;
// this package never receives or mints a raw_record_id itself.
type LineageEdge struct {
	RawRecordOrdinal uint64
	DerivationRole   DerivationRole
	FieldMap         []FieldMapping
}

func (e LineageEdge) Validate() error {
	if err := e.DerivationRole.Validate(); err != nil {
		return err
	}
	for index, mapping := range e.FieldMap {
		if err := mapping.Validate(); err != nil {
			return fmt.Errorf("field map %d: %w", index, err)
		}
	}
	return nil
}

// RecordEnvelope is one normalize_generation_activity output record, prior to
// persistence. It carries no normalized_record_id (assigned only at persist
// time), no knowledge_time (row-write audit time belongs to persistence), and
// no disclosure_tier or realization_refs (out of the import contract's
// boundary per AGENTS.md and normalized-record.schema.json).
type RecordEnvelope struct {
	RecordOrdinal        uint64
	RecordType           RecordType
	OccurredAt           *time.Time
	OccurredAtRaw        string
	TimestampGranularity TimestampGranularity
	TimestampCertainty   TimestampCertainty
	SourceAvailableFrom  time.Time
	ProvenanceClass      ProvenanceClass
	Participants         []Participant
	Content              json.RawMessage
	Lineage              []LineageEdge
}

func (r RecordEnvelope) Validate() error {
	if err := r.RecordType.Validate(); err != nil {
		return err
	}
	if err := r.TimestampGranularity.Validate(); err != nil {
		return err
	}
	if err := r.TimestampCertainty.Validate(); err != nil {
		return err
	}
	if r.OccurredAt == nil && strings.TrimSpace(r.OccurredAtRaw) == "" && r.TimestampGranularity != GranularityUnknown {
		return errors.New("record without a resolved occurred_at and without raw text must declare unknown granularity")
	}
	if r.SourceAvailableFrom.IsZero() {
		return errors.New("record requires a non-zero source_available_from")
	}
	if err := r.ProvenanceClass.Validate(); err != nil {
		return err
	}
	for index, participant := range r.Participants {
		if err := participant.Validate(); err != nil {
			return fmt.Errorf("participant %d: %w", index, err)
		}
	}
	if len(r.Content) > 0 {
		var decoded any
		if !json.Valid(r.Content) {
			return errors.New("content must be valid JSON")
		}
		if err := json.Unmarshal(r.Content, &decoded); err != nil {
			return fmt.Errorf("content must be valid JSON: %w", err)
		}
		if _, ok := decoded.(map[string]any); !ok {
			return errors.New("content must be a JSON object")
		}
	}
	if len(r.Lineage) == 0 {
		return errors.New("normalized record requires at least one lineage edge")
	}
	for index, edge := range r.Lineage {
		if err := edge.Validate(); err != nil {
			return fmt.Errorf("lineage edge %d: %w", index, err)
		}
	}
	return nil
}

// RawRecordView is the read-only projection of one persisted, sealed raw
// record handed to a normalizer. It carries no raw bytes and no locator: an
// Adapter reasons about native_fields/native_metadata shape only.
type RawRecordView struct {
	RecordOrdinal  uint64
	FormatID       parser.FormatID
	RecordStatus   parser.RecordStatus
	NativeFields   json.RawMessage
	NativeMetadata json.RawMessage
}

// RawRecordSource streams a sealed raw generation's records in ordinal order.
// It is deliberately streaming: a generation is never materialized as a Go
// slice in an Activity or Adapter.
type RawRecordSource interface {
	Next(context.Context) (RawRecordView, error)
	Close() error
}

// NormalizerInput is a reference-only normalize request. AcquiredAt and
// SourceProvenanceClass are source-version-level facts the Store resolves
// from context.source/context.source_version; an Adapter must not guess them.
type NormalizerInput struct {
	ContractVersion       string
	SourceVersionRef      string
	RawGenerationRef      string
	DeclaredFormat        parser.FormatID
	SourceProvenanceClass ProvenanceClass
	AcquiredAt            time.Time
	Records               RawRecordSource
}

func (i NormalizerInput) Validate() error {
	if i.ContractVersion != ContractVersion {
		return fmt.Errorf("unsupported normalizer input contract version %q", i.ContractVersion)
	}
	if strings.TrimSpace(i.SourceVersionRef) == "" {
		return errors.New("normalizer input requires source version reference")
	}
	if strings.TrimSpace(i.RawGenerationRef) == "" {
		return errors.New("normalizer input requires raw generation reference")
	}
	if err := i.DeclaredFormat.Validate(); err != nil {
		return err
	}
	if err := i.SourceProvenanceClass.Validate(); err != nil {
		return err
	}
	if i.AcquiredAt.IsZero() {
		return errors.New("normalizer input requires a non-zero acquired_at")
	}
	if i.Records == nil {
		return errors.New("normalizer input requires a raw record source")
	}
	return nil
}

// BundleHeader is sent to storage once, before streamed records.
type BundleHeader struct {
	ContractVersion   string
	NormalizerID      string
	NormalizerVersion string
	SourceVersionRef  string
	RawGenerationRef  string
}

// BundleAccounting is the deterministic count persist_normalized_generation
// verifies against durable membership.
type BundleAccounting struct {
	Emitted uint64
}

// BundleSink receives one normalized record at a time. It has no finalize
// method so an Adapter cannot commit an incomplete bundle.
type BundleSink interface {
	Emit(context.Context, RecordEnvelope) error
}

// BundleWriter is a caller-owned streaming persistence seam, exactly mirroring
// parser.BundleWriter. This package has no persistence authority of its own.
type BundleWriter interface {
	BundleSink
	Begin(context.Context, BundleHeader) error
	Finalize(context.Context, BundleAccounting) (BundleResult, error)
	Abort(context.Context) error
}

// BundleResult contains only a compact, caller-minted registry.
type BundleResult struct {
	BundleRef string
}

// Capability names one normalizer's identity. SupportedFormats is advisory
// only: normalize_generation_activity has no separate selection stage, so
// nothing in this package chooses among multiple registered adapters by
// format coverage today.
type Capability struct {
	ContractVersion   string
	NormalizerID      string
	NormalizerVersion string
	SupportedFormats  []parser.FormatID
}

func (c Capability) Validate() error {
	if c.ContractVersion != ContractVersion {
		return fmt.Errorf("unsupported normalizer capability contract version %q", c.ContractVersion)
	}
	if strings.TrimSpace(c.NormalizerID) == "" || strings.TrimSpace(c.NormalizerVersion) == "" {
		return errors.New("normalizer capability requires normalizer id and version")
	}
	return nil
}

// Adapter is the normalize-only transform boundary. It streams normalized
// records to sink but never persists, hashes, or decides evidence authority.
type Adapter interface {
	Capability() Capability
	Normalize(context.Context, NormalizerInput, BundleSink) (BundleAccounting, error)
}

const abortTimeout = 5 * time.Second

// Execute owns the streaming bundle lifecycle around one Adapter invocation,
// mirroring parser.Registry's executeRegistered: the Adapter can emit records
// but cannot finalize/commit the bundle, and any normalize, shape, or
// accounting failure aborts the caller-owned writer.
func Execute(ctx context.Context, input NormalizerInput, adapter Adapter, writer BundleWriter) (result BundleResult, err error) {
	if err := input.Validate(); err != nil {
		return BundleResult{}, err
	}
	if adapter == nil {
		return BundleResult{}, errors.New("normalize execution requires an adapter")
	}
	if writer == nil {
		return BundleResult{}, errors.New("normalize execution requires a bundle writer")
	}
	if err := ctx.Err(); err != nil {
		return BundleResult{}, err
	}
	capability := adapter.Capability()
	if err := capability.Validate(); err != nil {
		return BundleResult{}, fmt.Errorf("normalizer capability: %w", err)
	}
	header := BundleHeader{
		ContractVersion:   ContractVersion,
		NormalizerID:      capability.NormalizerID,
		NormalizerVersion: capability.NormalizerVersion,
		SourceVersionRef:  input.SourceVersionRef,
		RawGenerationRef:  input.RawGenerationRef,
	}
	if err := writer.Begin(ctx, header); err != nil {
		_ = abortBundle(ctx, writer)
		return BundleResult{}, fmt.Errorf("begin normalized bundle: %w", err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = abortBundle(ctx, writer)
		}
	}()

	sink := &validatingSink{downstream: writer}
	accounting, err := adapter.Normalize(ctx, input, sink)
	if err != nil {
		return BundleResult{}, fmt.Errorf("normalize with %s: %w", capability.NormalizerID, err)
	}
	if sink.fault != nil {
		return BundleResult{}, fmt.Errorf("normalize with %s emitted invalid bundle data: %w", capability.NormalizerID, sink.fault)
	}
	if err := ctx.Err(); err != nil {
		return BundleResult{}, err
	}
	if accounting.Emitted == 0 || sink.count == 0 {
		return BundleResult{}, errors.New("normalized bundle refuses to finalize with zero records")
	}
	if accounting.Emitted != sink.count {
		return BundleResult{}, fmt.Errorf("normalized bundle accounting mismatch: got %d, observed %d", accounting.Emitted, sink.count)
	}
	result, err = writer.Finalize(ctx, accounting)
	if err != nil {
		return BundleResult{}, fmt.Errorf("finalize normalized bundle: %w", err)
	}
	if result.BundleRef == "" {
		return BundleResult{}, errors.New("finalized normalized bundle lacks a compact bundle reference")
	}
	committed = true
	return result, nil
}

type validatingSink struct {
	downstream BundleSink
	next       uint64
	count      uint64
	fault      error
}

func (s *validatingSink) Emit(ctx context.Context, record RecordEnvelope) error {
	if s.fault != nil {
		return s.fault
	}
	if err := ctx.Err(); err != nil {
		s.fault = err
		return err
	}
	if record.RecordOrdinal != s.next {
		s.fault = fmt.Errorf("normalized record ordinal %d, want contiguous ordinal %d", record.RecordOrdinal, s.next)
		return s.fault
	}
	if err := record.Validate(); err != nil {
		s.fault = err
		return err
	}
	if err := s.downstream.Emit(ctx, record); err != nil {
		s.fault = fmt.Errorf("write normalized record ordinal %d: %w", record.RecordOrdinal, err)
		return s.fault
	}
	s.next++
	s.count++
	return nil
}

func abortBundle(ctx context.Context, writer BundleWriter) error {
	cleanupCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), abortTimeout)
	defer cancel()
	return writer.Abort(cleanupCtx)
}

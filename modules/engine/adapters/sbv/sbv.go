// Package sbv adapts SBV's parse-only importers to the platform parser
// contract. It owns no persistence, hashing, normalization, or custody.
package sbv

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"

	"github.com/Cursedpotential/probata/engine/parser"
	"github.com/lowcarbdev/sbv/pkg/parseonly"
)

// 1.4.0 adds explicit Workbench SMS declared-format aliases and promotes call
// kind/direction/disposition/duration into typed native fields. Pinning the
// change prevents retries from silently claiming the prior generic projection.
const adapterVersion = "1.4.0"

const (
	formatWorkbenchSMSExportXML parser.FormatID = "sms_export_xml"
	formatLegacySMSXML          parser.FormatID = "sms_xml"
)

// ObjectOpener resolves the immutable object URI in ParserInput. The parser
// package supplies only coordinates; this seam keeps object access outside
// the decoder and outside Temporal history.
type ObjectOpener func(context.Context, string) (io.ReadCloser, error)

// Adapter is one canonical SBV format adapter. A separate adapter is returned
// per format so Registry selection remains coverage-based and deterministic.
type Adapter struct {
	format    parser.FormatID
	open      ObjectOpener
	artifacts parseonly.ImmutableArtifactSink
}

// New constructs one format adapter after validating the canonical format and
// the required immutable-object opener.
func New(format parser.FormatID, open ObjectOpener) (*Adapter, error) {
	return newAdapter(format, open, nil)
}

// NewWithArtifactSink constructs an adapter that can truthfully preserve
// streamed source records and attachments. The sink owns immutable storage;
// the adapter owns only mapping its returned locators into the parser contract.
func NewWithArtifactSink(format parser.FormatID, open ObjectOpener, artifacts parseonly.ImmutableArtifactSink) (*Adapter, error) {
	if artifacts == nil {
		return nil, errors.New("SBV attachment support requires an immutable artifact sink")
	}
	return newAdapter(format, open, artifacts)
}

func newAdapter(format parser.FormatID, open ObjectOpener, artifacts parseonly.ImmutableArtifactSink) (*Adapter, error) {
	if err := format.Validate(); err != nil {
		return nil, err
	}
	if open == nil {
		return nil, errors.New("SBV adapter requires an immutable object opener")
	}
	if _, err := parseonly.New(string(format)); err != nil {
		return nil, err
	}
	return &Adapter{format: format, open: open, artifacts: artifacts}, nil
}

// NewAll returns adapters for every SBV format whose public importer can
// satisfy the platform contract. Email EML/MBOX are deliberately excluded
// because their importer only exposes streamed hashes, not exact raw bytes.
// Other formats fail closed at the record boundary if an attachment locator
// cannot be represented as an immutable platform ObjectRef.
func NewAll(open ObjectOpener) ([]parser.Adapter, error) {
	return newAll(open, nil)
}

// NewAllWithArtifactSink returns the complete SBV adapter set with immutable
// attachment support enabled end to end.
func NewAllWithArtifactSink(open ObjectOpener, artifacts parseonly.ImmutableArtifactSink) ([]parser.Adapter, error) {
	if artifacts == nil {
		return nil, errors.New("SBV attachment support requires an immutable artifact sink")
	}
	return newAll(open, artifacts)
}

func newAll(open ObjectOpener, artifacts parseonly.ImmutableArtifactSink) ([]parser.Adapter, error) {
	if open == nil {
		return nil, errors.New("SBV adapters require an immutable object opener")
	}
	formats := []parser.FormatID{
		parseonly.FormatSMSBackupXML, parseonly.FormatNDJSON, parseonly.FormatCSV,
		parseonly.FormatTranscript, parseonly.FormatIMessageTXT, parseonly.FormatIMessageHTML,
		parseonly.FormatFacebookHTML, parseonly.FormatGoogleVoice, parseonly.FormatGoogleChat,
		parseonly.FormatFacebookJSON, parseonly.FormatChatGPTJSON,
	}
	result := make([]parser.Adapter, 0, len(formats))
	for _, format := range formats {
		adapter, err := newAdapter(format, open, artifacts)
		if err != nil {
			return nil, fmt.Errorf("create SBV adapter %q: %w", format, err)
		}
		result = append(result, adapter)
	}
	return result, nil
}

func (a *Adapter) Capability() parser.Capability {
	formats := []parser.FormatID{a.format}
	if a != nil && a.format == parseonly.FormatSMSBackupXML {
		// These labels describe the same SMS Backup & Restore XML grammar. The
		// generic Workbench JSON/Markdown/HTML/DOCX labels are deliberately not
		// aliases: each is ambiguous or unsupported by this fixed decoder.
		formats = append(formats, formatWorkbenchSMSExportXML, formatLegacySMSXML)
	}
	quality := make(map[parser.FormatID]parser.Quality, len(formats))
	for _, format := range formats {
		quality[format] = parser.QualityPrimary
	}
	return parser.Capability{
		ContractVersion:     parser.ContractVersion,
		ParserID:            "sbv_" + string(a.format),
		ParserVersion:       adapterVersion,
		Language:            parser.LanguageGo,
		DeclaredFormats:     formats,
		FormatQuality:       quality,
		SupportsAttachments: a != nil && a.artifacts != nil,
		SupportsStreaming:   true,
	}
}

func (a *Adapter) Parse(ctx context.Context, input parser.ParserInput, sink parser.BundleSink) (parser.BundleAccounting, error) {
	if a == nil || a.open == nil {
		return parser.BundleAccounting{}, errors.New("SBV adapter is not configured")
	}
	if err := input.Validate(); err != nil {
		return parser.BundleAccounting{}, err
	}
	if !a.accepts(input.DeclaredFormat) {
		return parser.BundleAccounting{}, fmt.Errorf("SBV adapter format %q cannot parse %q", a.format, input.DeclaredFormat)
	}
	if sink == nil {
		return parser.BundleAccounting{}, errors.New("SBV adapter requires a bundle sink")
	}
	reader, err := a.open(ctx, input.FileOrMember.ObjectRef.URI)
	if err != nil {
		return parser.BundleAccounting{}, fmt.Errorf("open immutable source object: %w", err)
	}
	if reader == nil {
		return parser.BundleAccounting{}, errors.New("immutable source opener returned nil reader")
	}
	defer reader.Close()
	var exactRange *rangeReader
	var parseSource io.Reader = reader
	if input.FileOrMember.Type == parser.LocatorByteRange {
		exactRange, err = newRangeReader(ctx, reader, input.FileOrMember.ByteRange)
		if err != nil {
			return parser.BundleAccounting{}, fmt.Errorf("open immutable source range: %w", err)
		}
		parseSource = exactRange
	}
	importer, err := parseonly.New(string(a.format))
	if err != nil {
		return parser.BundleAccounting{}, err
	}
	var accounting parser.BundleAccounting
	var ordinal uint64
	emit := func(emitCtx context.Context, record parseonly.Record) error {
		if err := emitCtx.Err(); err != nil {
			return err
		}
		envelope, err := toEnvelope(input.DeclaredFormat, record)
		if err != nil {
			return err
		}
		envelope.RecordOrdinal = ordinal
		if err := sink.Emit(emitCtx, envelope); err != nil {
			return err
		}
		ordinal++
		switch record.Status {
		case parseonly.StatusParsed:
			accounting.Emitted++
		case parseonly.StatusRejected:
			accounting.Rejected++
		}
		accounting.Attachments += uint64(len(record.Attachments))
		return nil
	}
	if a.artifacts != nil {
		err = importer.ParseWithArtifacts(ctx, parseSource, input.SourceVersionRef, a.artifacts, emit)
	} else {
		err = importer.Parse(ctx, parseSource, emit)
	}
	if err != nil {
		return parser.BundleAccounting{}, err
	}
	if exactRange != nil && exactRange.remaining != 0 {
		return parser.BundleAccounting{}, fmt.Errorf("SBV parser did not consume declared source range: %w", io.ErrUnexpectedEOF)
	}
	if ordinal == 0 {
		return parser.BundleAccounting{}, errors.New("SBV parser emitted no contract records")
	}

	// SBV's native decoders expose exact bytes for each logical record but do
	// not expose trustworthy byte offsets for every format. Preserve the exact
	// immutable input locator as a separate envelope span instead of guessing
	// per-record offsets. This makes full-source byte coverage provable while
	// keeping the logical records' exact StoredBytes unchanged.
	coverageEnvelope := parser.RawRecordEnvelope{
		RecordOrdinal: ordinal,
		RecordStatus:  parser.StatusEnvelope,
		StatusReason:  "exact immutable parser input retained as source coverage envelope",
		Locator:       cloneLocator(input.FileOrMember),
		FormatID:      input.DeclaredFormat,
		NativeFields:  json.RawMessage(`{}`),
		NativeMetadata: json.RawMessage(
			`{"sbv_kind":"source_coverage_envelope","coverage_basis":"input_locator"}`,
		),
	}
	if err := sink.Emit(ctx, coverageEnvelope); err != nil {
		return parser.BundleAccounting{}, fmt.Errorf("emit SBV source coverage envelope: %w", err)
	}
	return accounting, nil
}

func (a *Adapter) accepts(format parser.FormatID) bool {
	if a == nil {
		return false
	}
	if format == a.format {
		return true
	}
	return a.format == parseonly.FormatSMSBackupXML &&
		(format == formatWorkbenchSMSExportXML || format == formatLegacySMSXML)
}

func cloneLocator(source parser.Locator) *parser.Locator {
	cloned := source
	if source.ByteRange != nil {
		bounds := *source.ByteRange
		cloned.ByteRange = &bounds
	}
	return &cloned
}

// rangeReader exposes exactly one immutable member range to a decoder. The
// opener deliberately returns only an io.Reader, so the adapter seeks by
// bounded reads and fails closed when the object is shorter than requested.
type rangeReader struct {
	ctx       context.Context
	source    io.Reader
	remaining uint64
}

func newRangeReader(ctx context.Context, source io.Reader, bounds *parser.ByteRange) (*rangeReader, error) {
	if source == nil {
		return nil, errors.New("source range requires a reader")
	}
	if bounds == nil {
		return nil, errors.New("byte-range locator has no bounds")
	}
	if err := discardContext(ctx, source, bounds.Offset); err != nil {
		return nil, fmt.Errorf("skip source range offset: %w", err)
	}
	return &rangeReader{ctx: ctx, source: source, remaining: bounds.Length}, nil
}

func discardContext(ctx context.Context, source io.Reader, count uint64) error {
	buffer := make([]byte, 32*1024)
	for count > 0 {
		if err := ctx.Err(); err != nil {
			return err
		}
		want := uint64(len(buffer))
		if count < want {
			want = count
		}
		n, err := source.Read(buffer[:int(want)])
		if n > 0 {
			count -= uint64(n)
		}
		if err != nil {
			if errors.Is(err, io.EOF) && count > 0 {
				return io.ErrUnexpectedEOF
			}
			return err
		}
		if n == 0 {
			return io.ErrNoProgress
		}
	}
	return nil
}

func (r *rangeReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	if r.remaining == 0 {
		return 0, io.EOF
	}
	if uint64(len(p)) > r.remaining {
		p = p[:int(r.remaining)]
	}
	n, err := r.source.Read(p)
	if n > 0 {
		r.remaining -= uint64(n)
	}
	if err == io.EOF && r.remaining > 0 {
		return n, io.ErrUnexpectedEOF
	}
	if n == 0 && err == nil {
		return 0, io.ErrNoProgress
	}
	return n, err
}

func toEnvelope(format parser.FormatID, record parseonly.Record) (parser.RawRecordEnvelope, error) {
	if (len(record.Raw) == 0) == (record.RawLocator == nil) {
		return parser.RawRecordEnvelope{}, errors.New("SBV record requires exactly one exact raw byte value or immutable raw locator")
	}
	if uint64(len(record.Attachments)+len(record.AttachmentFailures)) != record.CapturedAttachments {
		return parser.RawRecordEnvelope{}, errors.New("SBV record attachment accounting is not one-to-one")
	}
	recipientIdentities := make([]string, 0, len(record.Recipients))
	for _, recipient := range record.Recipients {
		if identity := strings.TrimSpace(recipient.Identity); identity != "" {
			recipientIdentities = append(recipientIdentities, identity)
		}
	}
	nativeKind := parser.NativeRecordKind(strings.TrimSpace(record.Kind))
	if err := nativeKind.Validate(); err != nil {
		nativeKind = parser.NativeKindOther
	}
	fields := parser.CommonNativeFields{
		RecordKind: nativeKind, Body: record.Content, Sender: record.Sender,
		Recipients: recipientIdentities, Participants: record.Participants,
		OccurredAt: record.OccurredAt,
	}
	if nativeKind == parser.NativeKindCall {
		call, err := callFields(record)
		if err != nil {
			return parser.RawRecordEnvelope{}, fmt.Errorf("project SBV call fields: %w", err)
		}
		fields.Call = &call
	}
	if err := fields.Validate(); err != nil {
		return parser.RawRecordEnvelope{}, fmt.Errorf("validate SBV native fields: %w", err)
	}
	nativeFields, err := json.Marshal(fields)
	if err != nil {
		return parser.RawRecordEnvelope{}, fmt.Errorf("encode SBV native fields: %w", err)
	}
	nativeMetadata, err := json.Marshal(struct {
		Kind                 string                          `json:"sbv_kind"`
		SourcePos            string                          `json:"sbv_source_pos"`
		Participants         []string                        `json:"sbv_participants"`
		Recipients           []parseonly.Recipient           `json:"sbv_recipients,omitempty"`
		AttachmentReferences []parseonly.AttachmentReference `json:"sbv_attachment_references,omitempty"`
		AttachmentFailures   []parseonly.AttachmentFailure   `json:"sbv_attachment_failures,omitempty"`
		CapturedAttachments  uint64                          `json:"sbv_captured_attachments"`
		Metadata             map[string]any                  `json:"source_metadata,omitempty"`
	}{record.Kind, record.SourcePos, record.Participants, record.Recipients, record.AttachmentReferences, record.AttachmentFailures, record.CapturedAttachments, record.Metadata})
	if err != nil {
		return parser.RawRecordEnvelope{}, fmt.Errorf("encode SBV native metadata: %w", err)
	}
	envelope := parser.RawRecordEnvelope{
		RecordStatus: parser.RecordStatus(record.Status),
		StatusReason: strings.TrimSpace(record.StatusReason),
		FormatID:     format,
		NativeFields: nativeFields, NativeMetadata: nativeMetadata,
	}
	if record.RawLocator != nil {
		envelope.Locator = &parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{
			StorageClass: record.RawLocator.StorageClass,
			URI:          record.RawLocator.URI, ContentHash: record.RawLocator.ContentHash,
		}}
	} else {
		envelope.StoredBytes = &parser.StoredBytes{Bytes: append([]byte(nil), record.Raw...)}
	}
	for _, attachment := range record.Attachments {
		metadata, err := json.Marshal(struct {
			SourceAssociation string `json:"source_association"`
			ParentSourcePos   string `json:"parent_source_pos"`
			OriginalName      string `json:"original_name"`
			MIME              string `json:"mime"`
			DigestSHA256      string `json:"digest_sha256"`
			ByteCount         int64  `json:"byte_count"`
			ConversionStatus  string `json:"conversion_status,omitempty"`
			ConversionError   string `json:"conversion_error,omitempty"`
		}{attachment.SourceAssociation, attachment.ParentSourcePos, attachment.OriginalName, attachment.MIME, attachment.DigestSHA256, attachment.ByteCount, attachment.ConversionStatus, attachment.ConversionError})
		if err != nil {
			return parser.RawRecordEnvelope{}, fmt.Errorf("encode SBV attachment %d metadata: %w", attachment.AttachmentOrdinal, err)
		}
		envelope.Attachments = append(envelope.Attachments, parser.AttachmentRef{
			AttachmentOrdinal: attachment.AttachmentOrdinal,
			Locator: parser.Locator{Type: parser.LocatorWholeObject, ObjectRef: parser.ObjectRef{
				StorageClass: attachment.Locator.StorageClass,
				URI:          attachment.Locator.URI, ContentHash: attachment.Locator.ContentHash,
			}},
			NativeMetadata: metadata,
		})
	}
	return envelope, nil
}

func callFields(record parseonly.Record) (parser.NativeCallFields, error) {
	typeCode, typePresent, err := nonNegativeMetadataUint(record.Metadata, "Type", "type")
	if err != nil {
		return parser.NativeCallFields{}, fmt.Errorf("call type: %w", err)
	}
	duration, durationPresent, err := nonNegativeMetadataUint(record.Metadata, "Duration", "duration")
	if err != nil {
		return parser.NativeCallFields{}, fmt.Errorf("call duration: %w", err)
	}
	call := parser.NativeCallFields{
		Direction: parser.CallDirectionUnknown, Disposition: parser.CallDispositionUnknown,
	}
	if durationPresent {
		call.DurationSeconds = &duration
	}
	if direction := normalizedMetadataText(record.Metadata, "direction", "Direction"); direction != "" {
		switch direction {
		case "incoming", "inbound", "received":
			call.Direction = parser.CallDirectionIncoming
		case "outgoing", "outbound", "sent":
			call.Direction = parser.CallDirectionOutgoing
		}
	}
	if strings.Contains(strings.ToLower(record.Content), "missed call") {
		call.Disposition, call.Missed = parser.CallDispositionMissed, true
	}
	if typePresent {
		switch typeCode {
		case 1:
			call.Direction, call.Disposition = parser.CallDirectionIncoming, parser.CallDispositionCompleted
		case 2:
			call.Direction, call.Disposition = parser.CallDirectionOutgoing, parser.CallDispositionCompleted
		case 3:
			call.Direction, call.Disposition, call.Missed = parser.CallDirectionIncoming, parser.CallDispositionMissed, true
		case 4:
			call.Direction, call.Disposition = parser.CallDirectionIncoming, parser.CallDispositionVoicemail
		case 5:
			call.Direction, call.Disposition = parser.CallDirectionIncoming, parser.CallDispositionRejected
		case 6:
			call.Direction, call.Disposition = parser.CallDirectionIncoming, parser.CallDispositionRefused
		}
	}
	if err := call.Validate(); err != nil {
		return parser.NativeCallFields{}, err
	}
	return call, nil
}

func normalizedMetadataText(metadata map[string]any, keys ...string) string {
	for _, key := range keys {
		if value, exists := metadata[key]; exists && value != nil {
			return strings.ToLower(strings.TrimSpace(fmt.Sprint(value)))
		}
	}
	return ""
}

func nonNegativeMetadataUint(metadata map[string]any, keys ...string) (uint64, bool, error) {
	for _, key := range keys {
		value, exists := metadata[key]
		if !exists || value == nil {
			continue
		}
		text := strings.TrimSpace(fmt.Sprint(value))
		if text == "" {
			return 0, false, nil
		}
		parsed, err := strconv.ParseUint(text, 10, 64)
		if err != nil {
			return 0, true, fmt.Errorf("metadata field %q must be a non-negative integer", key)
		}
		return parsed, true, nil
	}
	return 0, false, nil
}

var _ parser.Adapter = (*Adapter)(nil)

// Package sbv adapts SBV's parse-only importers to the platform parser
// contract. It owns no persistence, hashing, normalization, or custody.
package sbv

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	"github.com/lowcarbdev/sbv/pkg/parseonly"
)

// 1.1.0 adds the exact input-locator coverage envelope and promotes native
// message values into native_fields. Pinning the change prevents a retry or
// re-import from silently claiming the prior 1.0.0 output contract.
const adapterVersion = "1.1.0"

// ObjectOpener resolves the immutable object URI in ParserInput. The parser
// package supplies only coordinates; this seam keeps object access outside
// the decoder and outside Temporal history.
type ObjectOpener func(context.Context, string) (io.ReadCloser, error)

// Adapter is one canonical SBV format adapter. A separate adapter is returned
// per format so Registry selection remains coverage-based and deterministic.
type Adapter struct {
	format parser.FormatID
	open   ObjectOpener
}

// New constructs one format adapter after validating the canonical format and
// the required immutable-object opener.
func New(format parser.FormatID, open ObjectOpener) (*Adapter, error) {
	if err := format.Validate(); err != nil {
		return nil, err
	}
	if open == nil {
		return nil, errors.New("SBV adapter requires an immutable object opener")
	}
	if _, err := parseonly.New(string(format)); err != nil {
		return nil, err
	}
	return &Adapter{format: format, open: open}, nil
}

// NewAll returns adapters for every SBV format whose public importer can
// satisfy the platform contract. Email EML/MBOX are deliberately excluded
// because their importer only exposes streamed hashes, not exact raw bytes.
// Other formats fail closed at the record boundary if an attachment locator
// cannot be represented as an immutable platform ObjectRef.
func NewAll(open ObjectOpener) ([]parser.Adapter, error) {
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
		adapter, err := New(format, open)
		if err != nil {
			return nil, fmt.Errorf("create SBV adapter %q: %w", format, err)
		}
		result = append(result, adapter)
	}
	return result, nil
}

func (a *Adapter) Capability() parser.Capability {
	return parser.Capability{
		ContractVersion:     parser.ContractVersion,
		ParserID:            "sbv_" + string(a.format),
		ParserVersion:       adapterVersion,
		Language:            parser.LanguageGo,
		DeclaredFormats:     []parser.FormatID{a.format},
		FormatQuality:       map[parser.FormatID]parser.Quality{a.format: parser.QualityPrimary},
		SupportsAttachments: false,
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
	if input.DeclaredFormat != a.format {
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
	err = importer.Parse(ctx, parseSource, func(emitCtx context.Context, record parseonly.Record) error {
		if err := emitCtx.Err(); err != nil {
			return err
		}
		envelope, err := toEnvelope(a.format, record)
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
		return nil
	})
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
		FormatID:      a.format,
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
	if len(record.Raw) == 0 {
		return parser.RawRecordEnvelope{}, errors.New("SBV record has no exact raw bytes")
	}
	recipientIdentities := make([]string, 0, len(record.Recipients))
	for _, recipient := range record.Recipients {
		if identity := strings.TrimSpace(recipient.Identity); identity != "" {
			recipientIdentities = append(recipientIdentities, identity)
		}
	}
	nativeFields, err := json.Marshal(struct {
		Body         string     `json:"body"`
		Sender       string     `json:"sender,omitempty"`
		Recipients   []string   `json:"recipients,omitempty"`
		Participants []string   `json:"participants,omitempty"`
		OccurredAt   *time.Time `json:"occurred_at,omitempty"`
	}{record.Content, record.Sender, recipientIdentities, record.Participants, record.OccurredAt})
	if err != nil {
		return parser.RawRecordEnvelope{}, fmt.Errorf("encode SBV native fields: %w", err)
	}
	nativeMetadata, err := json.Marshal(struct {
		Kind         string                `json:"sbv_kind"`
		SourcePos    string                `json:"sbv_source_pos"`
		Participants []string              `json:"sbv_participants"`
		Recipients   []parseonly.Recipient `json:"sbv_recipients,omitempty"`
		Metadata     map[string]any        `json:"source_metadata,omitempty"`
	}{record.Kind, record.SourcePos, record.Participants, record.Recipients, record.Metadata})
	if err != nil {
		return parser.RawRecordEnvelope{}, fmt.Errorf("encode SBV native metadata: %w", err)
	}
	return parser.RawRecordEnvelope{
		RecordStatus: parser.RecordStatus(record.Status),
		StatusReason: strings.TrimSpace(record.StatusReason),
		StoredBytes:  &parser.StoredBytes{Bytes: append([]byte(nil), record.Raw...)},
		FormatID:     format,
		NativeFields: nativeFields, NativeMetadata: nativeMetadata,
	}, nil
}

var _ parser.Adapter = (*Adapter)(nil)

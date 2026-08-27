// Package parseonly exposes SBV's importer decoders without exposing SBV's
// scheduler, SQLite engine, hashing, normalization, or custody side effects.
// It is intentionally a narrow facade for platform-owned adapters.
package parseonly

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/lowcarbdev/sbv/internal"
)

// Canonical platform format identifiers. The values deliberately use the
// platform's snake_case convention instead of SBV's legacy hyphenated names.
const (
	FormatSMSBackupXML = "smsbackuprestore_xml"
	FormatNDJSON       = "ndjson"
	FormatCSV          = "csv"
	FormatTranscript   = "messages_transcript"
	FormatIMessageTXT  = "imessage_txt"
	FormatIMessageHTML = "imessage_html"
	FormatFacebookHTML = "facebook_messenger_html"
	FormatGoogleVoice  = "google_voice_html"
	FormatEML          = "email_eml"
	FormatMBOX         = "email_mbox"
	FormatGoogleChat   = "google_chat_json"
	FormatFacebookJSON = "facebook_messenger_json"
	FormatChatGPTJSON  = "chatgpt_official_json"
)

type formatMapping struct {
	Canonical string
	SBV       string
}

var formatMappings = []formatMapping{
	{FormatSMSBackupXML, internal.FormatSMSBackupXML},
	{FormatNDJSON, internal.FormatNDJSON},
	{FormatCSV, internal.FormatCSV},
	{FormatTranscript, internal.FormatTranscript},
	{FormatIMessageTXT, internal.FormatIMessageTXT},
	{FormatIMessageHTML, internal.FormatIMessageHTML},
	{FormatFacebookHTML, internal.FormatFacebookHTML},
	{FormatGoogleVoice, internal.FormatGoogleVoice},
	{FormatEML, internal.FormatEML},
	{FormatMBOX, internal.FormatMBOX},
	{FormatGoogleChat, internal.FormatGoogleChat},
	{FormatFacebookJSON, internal.FormatFacebookJSON},
	{FormatChatGPTJSON, "chatgpt-official-json"},
}

// Formats returns every explicitly mapped SBV format in canonical platform
// spelling. Email importers remain mapped for inventory/documentation, but
// New rejects them because their importer contract only returns streamed hashes
// and does not expose exact record bytes through SourceRecord.Raw.
func Formats() []string {
	formats := make([]string, 0, len(formatMappings))
	for _, mapping := range formatMappings {
		formats = append(formats, mapping.Canonical)
	}
	return formats
}

// Importer is a parse-only facade around one registered SBV importer.
type Importer struct {
	canonical string
	inner     internal.Importer
}

// New resolves one mapped importer. It refuses the email importers because
// their public importer output cannot provide exact raw record bytes required
// by RawRecordEnvelope.
func New(format string) (*Importer, error) {
	canonical := strings.TrimSpace(format)
	for _, mapping := range formatMappings {
		if mapping.Canonical != canonical {
			continue
		}
		if canonical == FormatEML || canonical == FormatMBOX {
			return nil, fmt.Errorf("SBV format %q is excluded: importer only exposes streamed hashes, not exact raw record bytes", canonical)
		}
		inner, ok := internal.ImporterByFormat(mapping.SBV)
		if !ok {
			return nil, fmt.Errorf("SBV importer %q is not registered", mapping.SBV)
		}
		return &Importer{canonical: canonical, inner: inner}, nil
	}
	return nil, fmt.Errorf("unsupported SBV platform format %q", format)
}

// Record is the lossless parse-only projection of an SBV SourceRecord. Raw
// bytes are required for accepted/rejected records; no hash is calculated here.
type Record struct {
	Status       Status
	StatusReason string
	Kind         string
	SourcePos    string
	Raw          []byte
	OccurredAt   *time.Time
	Participants []string
	Sender       string
	Recipients   []Recipient
	Content      string
	Metadata     map[string]any
}

type Status string

const (
	StatusParsed   Status = "parsed"
	StatusRejected Status = "rejected"
)

type Recipient struct {
	Identity string `json:"identity"`
	Role     string `json:"role"`
}

// Parse runs only the selected decoder and emits records in exact decoder
// order. It does not call SBV's engine, write SQLite, hash, normalize, or grant
// authority. SBV has one generic Reject callback, so rejects are represented as
// rejected; malformed/unparsed distinctions are never guessed. A reject with
// incomplete bytes or a RejectHashed callback fails closed because it cannot
// satisfy the platform raw-span contract.
func (i *Importer) Parse(ctx context.Context, source io.Reader, emit func(context.Context, Record) error) error {
	if i == nil || i.inner == nil {
		return errors.New("parse-only SBV importer is nil")
	}
	if source == nil {
		return errors.New("parse-only SBV importer requires a source reader")
	}
	if emit == nil {
		return errors.New("parse-only SBV importer requires an emit callback")
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	sink := &parseSink{ctx: ctx, emit: emit}
	if err := i.inner.Run(sink, bufio.NewReader(&contextReader{ctx: ctx, source: source})); err != nil {
		return fmt.Errorf("SBV %s parse: %w", i.canonical, err)
	}
	return ctx.Err()
}

type contextReader struct {
	ctx    context.Context
	source io.Reader
}

func (r *contextReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	n, err := r.source.Read(p)
	if ctxErr := r.ctx.Err(); ctxErr != nil {
		return n, ctxErr
	}
	return n, err
}

type parseSink struct {
	ctx  context.Context
	emit func(context.Context, Record) error
}

func (s *parseSink) ImportID() int64 { return 0 }

func (*parseSink) ArtifactDir() (string, error) {
	return "", errors.New("SBV attachment artifacts are excluded from parse-only facade: no immutable attachment locator is available")
}

func (*parseSink) Claim(int) {}

func (s *parseSink) Record(record *internal.SourceRecord) error {
	if record == nil {
		return errors.New("SBV importer emitted a nil record")
	}
	if err := s.ctx.Err(); err != nil {
		return err
	}
	if len(record.Raw) == 0 {
		return errors.New("SBV record has no exact raw bytes; streamed-only record cannot satisfy parse-only contract")
	}
	if len(record.Attachments) > 0 || len(record.AttachmentReferences) > 0 {
		return errors.New("SBV record has attachment data without an immutable platform locator")
	}
	return s.emit(s.ctx, convertRecord(record, StatusParsed, ""))
}

func (s *parseSink) Reject(sourcePos, reason string, raw []byte, rawComplete bool) error {
	if err := s.ctx.Err(); err != nil {
		return err
	}
	if !rawComplete || len(raw) == 0 {
		return errors.New("SBV rejected span lacks complete raw bytes; malformed/unparsed status cannot be inferred safely")
	}
	return s.emit(s.ctx, Record{Status: StatusRejected, StatusReason: strings.TrimSpace(reason), SourcePos: sourcePos, Raw: append([]byte(nil), raw...)})
}

func (*parseSink) RejectHashed(_, _, _, _ string, _ int64) error {
	return errors.New("SBV RejectHashed cannot satisfy parse-only raw-span contract without exact bytes")
}

func convertRecord(record *internal.SourceRecord, status Status, reason string) Record {
	metadata := make(map[string]any, len(record.Metadata)+1)
	for key, value := range record.Metadata {
		metadata[key] = value
	}
	return Record{
		Status: status, StatusReason: reason, Kind: record.Kind, SourcePos: record.SourcePos,
		Raw: append([]byte(nil), record.Raw...), OccurredAt: record.OccurredAt,
		Participants: append([]string(nil), record.Participants...), Sender: record.Sender,
		Recipients: convertRecipients(record.Recipients), Content: record.Content, Metadata: metadata,
	}
}

func convertRecipients(values []internal.SourceParty) []Recipient {
	result := make([]Recipient, 0, len(values))
	for _, value := range values {
		result = append(result, Recipient{Identity: value.Identity, Role: value.Role})
	}
	return result
}

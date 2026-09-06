// Package parser defines the platform-owned, parse-only adapter boundary for
// ProfferWorkflow. It deliberately has no Temporal, database, hash,
// normalization, or custody dependency: adapters stream raw source-native
// records to a caller-owned BundleWriter and return only compact results.
package parser

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

const ContractVersion = "1.0.0"

// FormatID is the canonical, portable snake_case identifier used for declared
// parser coverage. Its 59-character limit also permits a PostgreSQL raw_
// subtype-table name within PostgreSQL's 63-byte identifier limit.
type FormatID string

func (f FormatID) Validate() error {
	if len(f) == 0 || len(f) > 59 {
		return fmt.Errorf("format id must be 1 through 59 characters")
	}
	for index, character := range string(f) {
		if character >= 'a' && character <= 'z' {
			continue
		}
		if index > 0 && character >= '0' && character <= '9' {
			continue
		}
		if index > 0 && character == '_' {
			if string(f)[index-1] == '_' || index == len(f)-1 {
				return fmt.Errorf("format id %q is not canonical snake_case", f)
			}
			continue
		}
		return fmt.Errorf("format id %q is not canonical snake_case", f)
	}
	return nil
}

// Language is the implementation language declared by an adapter. A
// non-Go implementation can be represented by a process/RPC adapter behind
// the same Adapter interface.
type Language string

const (
	LanguageGo         Language = "go"
	LanguagePython     Language = "python"
	LanguageJavaScript Language = "javascript"
	LanguageTypeScript Language = "typescript"
	LanguageOther      Language = "other"
)

func (l Language) Validate() error {
	switch l {
	case LanguageGo, LanguagePython, LanguageJavaScript, LanguageTypeScript, LanguageOther:
		return nil
	default:
		return fmt.Errorf("unsupported parser language %q", l)
	}
}

// Quality breaks a coverage tie only. Higher-priority tiers are selected
// first, then parser identity provides a stable deterministic tie-break.
type Quality string

const (
	QualityPrimary      Quality = "primary"
	QualityFallback     Quality = "fallback"
	QualityExperimental Quality = "experimental"
)

func (q Quality) Validate() error {
	switch q {
	case QualityPrimary, QualityFallback, QualityExperimental:
		return nil
	default:
		return fmt.Errorf("unsupported parser quality %q", q)
	}
}

func (q Quality) priority() int {
	switch q {
	case QualityPrimary:
		return 0
	case QualityFallback:
		return 1
	default:
		return 2
	}
}

// Capability is the Go representation of ParserCapability (v1). MaxInputBytes
// describes an adapter's own practical constraint; Registry never receives or
// considers an input size when choosing an adapter.
type Capability struct {
	ContractVersion     string
	ParserID            string
	ParserVersion       string
	Language            Language
	DeclaredFormats     []FormatID
	FormatQuality       map[FormatID]Quality
	SupportsAttachments bool
	SupportsStreaming   bool
	MaxInputBytes       *int64
}

func (c Capability) Validate() error {
	if c.ContractVersion != ContractVersion {
		return fmt.Errorf("unsupported parser capability contract version %q", c.ContractVersion)
	}
	if strings.TrimSpace(c.ParserID) == "" || strings.TrimSpace(c.ParserVersion) == "" {
		return errors.New("parser capability requires parser id and parser version")
	}
	if err := c.Language.Validate(); err != nil {
		return err
	}
	if len(c.DeclaredFormats) == 0 {
		return errors.New("parser capability requires at least one declared format")
	}
	formats := make(map[FormatID]struct{}, len(c.DeclaredFormats))
	for _, format := range c.DeclaredFormats {
		if err := format.Validate(); err != nil {
			return err
		}
		if _, exists := formats[format]; exists {
			return fmt.Errorf("parser capability repeats declared format %q", format)
		}
		formats[format] = struct{}{}
	}
	for format, quality := range c.FormatQuality {
		if _, exists := formats[format]; !exists {
			return fmt.Errorf("format quality declares uncovered format %q", format)
		}
		if err := quality.Validate(); err != nil {
			return err
		}
	}
	if c.MaxInputBytes != nil && *c.MaxInputBytes < 0 {
		return errors.New("max input bytes must be non-negative when declared")
	}
	return nil
}

// QualityFor returns the explicit per-format quality, or fallback when the
// optional contract field is absent.
func (c Capability) QualityFor(format FormatID) Quality {
	if quality, exists := c.FormatQuality[format]; exists {
		return quality
	}
	return QualityFallback
}

// ObjectRef and Locator preserve only immutable source coordinates. They do
// not open bytes, calculate hashes, or assert custody.
type ObjectRef struct {
	StorageClass string
	URI          string
	ContentHash  string
}

func (o ObjectRef) Validate() error {
	switch o.StorageClass {
	case "immutable_object_store", "filesystem", "inline":
	default:
		return fmt.Errorf("unsupported object storage class %q", o.StorageClass)
	}
	if strings.TrimSpace(o.URI) == "" {
		return errors.New("object reference requires a URI")
	}
	if o.ContentHash != "" {
		if len(o.ContentHash) != 64 {
			return errors.New("object content hash must be 64 lowercase SHA-256 hexadecimal characters")
		}
		decoded, err := hex.DecodeString(o.ContentHash)
		if err != nil || hex.EncodeToString(decoded) != o.ContentHash {
			return errors.New("object content hash must be 64 lowercase SHA-256 hexadecimal characters")
		}
	}
	return nil
}

type LocatorType string

const (
	LocatorByteRange   LocatorType = "byte_range"
	LocatorWholeObject LocatorType = "whole_object"
)

type ByteRange struct {
	Offset uint64
	Length uint64
}

// Locator identifies either a whole immutable object or an exact half-open
// byte range within one. Byte ranges are deliberately integer coordinates,
// not parser-specific character offsets.
type Locator struct {
	Type      LocatorType
	ObjectRef ObjectRef
	ByteRange *ByteRange
}

func (l Locator) Validate() error {
	if err := l.ObjectRef.Validate(); err != nil {
		return err
	}
	switch l.Type {
	case LocatorWholeObject:
		if l.ByteRange != nil {
			return errors.New("whole-object locator cannot carry a byte range")
		}
	case LocatorByteRange:
		if l.ByteRange == nil {
			return errors.New("byte-range locator requires an exact byte range")
		}
	default:
		return fmt.Errorf("unsupported locator type %q", l.Type)
	}
	return nil
}

// RecordStatus values match RawRecord (v1). Every source span is represented
// by one RawRecordEnvelope, including envelope and unparsed spans.
type RecordStatus string

const (
	StatusParsed    RecordStatus = "parsed"
	StatusRejected  RecordStatus = "rejected"
	StatusMalformed RecordStatus = "malformed"
	StatusUnknown   RecordStatus = "unknown"
	StatusUnparsed  RecordStatus = "unparsed"
	StatusEnvelope  RecordStatus = "envelope"
)

func (s RecordStatus) Validate() error {
	switch s {
	case StatusParsed, StatusRejected, StatusMalformed, StatusUnknown, StatusUnparsed, StatusEnvelope:
		return nil
	default:
		return fmt.Errorf("unsupported raw record status %q", s)
	}
}

// StoredBytes is distinct from a locator so a zero-length exact stored value
// remains representable (the pointer, rather than len(Bytes), establishes
// that stored bytes were supplied).
type StoredBytes struct {
	Bytes []byte
}

type AttachmentRef struct {
	AttachmentOrdinal uint64
	Locator           Locator
	NativeMetadata    json.RawMessage
}

// RawRecordEnvelope is one parser-emitted, source-native record/span. It has
// no hash, database, normalized, custody, workflow, or generated-id field.
// Bytes, when used, are handed to the caller-owned sink immediately rather
// than accumulated in a Temporal Activity result.
type RawRecordEnvelope struct {
	RecordOrdinal  uint64
	RecordStatus   RecordStatus
	StatusReason   string
	Locator        *Locator
	StoredBytes    *StoredBytes
	FormatID       FormatID
	NativeFields   json.RawMessage
	NativeMetadata json.RawMessage
	Attachments    []AttachmentRef
}

func (r RawRecordEnvelope) Validate(expectedFormat FormatID) error {
	if r.FormatID != expectedFormat {
		return fmt.Errorf("raw record format %q does not match bundle format %q", r.FormatID, expectedFormat)
	}
	if err := r.FormatID.Validate(); err != nil {
		return err
	}
	if err := r.RecordStatus.Validate(); err != nil {
		return err
	}
	if r.RecordStatus != StatusParsed && strings.TrimSpace(r.StatusReason) == "" {
		return fmt.Errorf("raw record ordinal %d status %q requires a reason", r.RecordOrdinal, r.RecordStatus)
	}
	if (r.Locator == nil) == (r.StoredBytes == nil) {
		return fmt.Errorf("raw record ordinal %d requires exactly one exact locator or stored bytes", r.RecordOrdinal)
	}
	if r.Locator != nil {
		if err := r.Locator.Validate(); err != nil {
			return fmt.Errorf("raw record ordinal %d locator: %w", r.RecordOrdinal, err)
		}
	}
	if err := validateJSONObject("native fields", r.NativeFields); err != nil {
		return fmt.Errorf("raw record ordinal %d: %w", r.RecordOrdinal, err)
	}
	if err := validateJSONObject("native metadata", r.NativeMetadata); err != nil {
		return fmt.Errorf("raw record ordinal %d: %w", r.RecordOrdinal, err)
	}
	attachments := make(map[uint64]struct{}, len(r.Attachments))
	for _, attachment := range r.Attachments {
		if _, exists := attachments[attachment.AttachmentOrdinal]; exists {
			return fmt.Errorf("raw record ordinal %d repeats attachment ordinal %d", r.RecordOrdinal, attachment.AttachmentOrdinal)
		}
		attachments[attachment.AttachmentOrdinal] = struct{}{}
		if err := attachment.Locator.Validate(); err != nil {
			return fmt.Errorf("raw record ordinal %d attachment %d: %w", r.RecordOrdinal, attachment.AttachmentOrdinal, err)
		}
		if err := validateJSONObject("attachment native metadata", attachment.NativeMetadata); err != nil {
			return fmt.Errorf("raw record ordinal %d attachment %d: %w", r.RecordOrdinal, attachment.AttachmentOrdinal, err)
		}
	}
	return nil
}

func validateJSONObject(name string, value json.RawMessage) error {
	if len(value) == 0 {
		return nil
	}
	var decoded any
	if !json.Valid(value) || json.Unmarshal(value, &decoded) != nil {
		return fmt.Errorf("%s must be valid JSON", name)
	}
	if _, ok := decoded.(map[string]any); !ok {
		return fmt.Errorf("%s must be a JSON object", name)
	}
	return nil
}

// ParserInput is a reference-only parse request. FileOrMember preserves the
// exact whole-file or archive/member byte-range locator selected upstream;
// parser inputs never carry source bytes. ParserOptionsRef points to out-of-
// band configuration rather than carrying it through workflow history.
type ParserInput struct {
	ContractVersion  string
	SourceVersionRef string
	FileOrMember     Locator
	DeclaredFormat   FormatID
	ParserOptionsRef string
}

func (i ParserInput) Validate() error {
	if i.ContractVersion != ContractVersion {
		return fmt.Errorf("unsupported parser input contract version %q", i.ContractVersion)
	}
	if strings.TrimSpace(i.SourceVersionRef) == "" {
		return errors.New("parser input requires source version reference")
	}
	if err := i.FileOrMember.Validate(); err != nil {
		return fmt.Errorf("parser input file or member locator: %w", err)
	}
	return i.DeclaredFormat.Validate()
}

// BundleHeader is sent to storage once, before streamed records. It mirrors
// RawExtractionBundle (v1)'s identity fields without materializing its records
// array.
type BundleHeader struct {
	ContractVersion  string
	ParserID         string
	ParserVersion    string
	SourceVersionRef string
	FormatID         FormatID
}

// BundleAccounting is RawExtractionBundle (v1)'s deterministic counts. The
// contract intentionally does not count envelope rows separately; envelopes
// remain persisted raw records and are included in the streamed total.
type BundleAccounting struct {
	Emitted     uint64
	Rejected    uint64
	Malformed   uint64
	Unknown     uint64
	Unparsed    uint64
	Attachments uint64
}

// BundleSink receives one record at a time. It intentionally has no finalize
// method, so an adapter cannot commit an incomplete bundle or mint its result
// registry. Registry owns finalization after it validates accounting.
type BundleSink interface {
	Emit(context.Context, RawRecordEnvelope) error
}

// BundleWriter is a caller-owned streaming persistence seam. It may write
// records to an immutable bundle/object store or a staged database batch, but
// the parser package itself has no persistence authority.
type BundleWriter interface {
	BundleSink
	Begin(context.Context, BundleHeader) error
	Finalize(context.Context, BundleAccounting) (BundleResult, error)
	Abort(context.Context) error
}

// BundleResult contains only compact, caller-minted references suitable for
// an Activity result. It never contains the streamed records themselves.
type BundleResult struct {
	BundleRef string
}

// Adapter is intentionally language-neutral. A Go parser, an RPC proxy for a
// Python parser, or a future external-language bridge all receive the same
// cancellable input and stream through the same sink.
type Adapter interface {
	Capability() Capability
	Parse(context.Context, ParserInput, BundleSink) (BundleAccounting, error)
}

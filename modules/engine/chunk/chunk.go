// Package chunk defines the deterministic, lossless chunk-stage boundary.
//
// Chunkers operate on already-retained source text. They do not parse,
// normalize, extract artifacts, persist rows, or assert evidence custody.
package chunk

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"unicode/utf8"

	"github.com/Cursedpotential/probata/engine/parser"
)

const (
	ContractVersion = "1.0.0"
	ChunkerID       = "chunk.document_markdown.offsets"
	ChunkerVersion  = "1.0.0"
	SchemaID        = "document-markdown"
	SchemaVersion   = "1.0.0"
)

type Signature string

const (
	SignatureChronology     Signature = "chronology"
	SignatureResearchReport Signature = "research_report"
	SignatureStatuteExtract Signature = "statute_extract"
	SignatureStrategyMemo   Signature = "strategy_memo"
)

func (s Signature) Validate() error {
	switch s {
	case SignatureChronology, SignatureResearchReport, SignatureStatuteExtract, SignatureStrategyMemo:
		return nil
	default:
		return fmt.Errorf("unsupported document markdown signature %q", s)
	}
}

// Capability is an immutable coordinator-facing declaration. The execution
// coordinator can select this implementation by signature without treating a
// chunker as a parser capability.
type Capability struct {
	ContractVersion  string
	ChunkerID        string
	ChunkerVersion   string
	Signatures       []Signature
	SignatureQuality map[Signature]parser.Quality
}

func (c Capability) Validate() error {
	if c.ContractVersion != ContractVersion {
		return fmt.Errorf("unsupported chunk capability contract version %q", c.ContractVersion)
	}
	if c.ChunkerID == "" || c.ChunkerVersion == "" {
		return errors.New("chunk capability requires chunker id and version")
	}
	if len(c.Signatures) == 0 {
		return errors.New("chunk capability requires at least one signature")
	}
	seen := make(map[Signature]struct{}, len(c.Signatures))
	for _, signature := range c.Signatures {
		if err := signature.Validate(); err != nil {
			return err
		}
		if _, exists := seen[signature]; exists {
			return fmt.Errorf("chunk capability repeats signature %q", signature)
		}
		seen[signature] = struct{}{}
	}
	for signature, quality := range c.SignatureQuality {
		if _, exists := seen[signature]; !exists {
			return fmt.Errorf("signature quality declares unsupported signature %q", signature)
		}
		if err := quality.Validate(); err != nil {
			return err
		}
	}
	return nil
}

// QualityFor uses the parser coordinator's established quality vocabulary,
// while keeping chunk selection and execution in a distinct atomic seam.
func (c Capability) QualityFor(signature Signature) parser.Quality {
	if quality, exists := c.SignatureQuality[signature]; exists {
		return quality
	}
	return parser.QualityFallback
}

// Chunk carries half-open byte and Unicode code-point ranges into Source.
// Text is always Source[ByteStart:ByteEnd], never rebuilt or normalized.
type Chunk struct {
	Index       int
	ByteStart   int
	ByteEnd     int
	CharStart   int
	CharEnd     int
	Text        string
	ContentHash string
}

// Result includes an independently calculated completeness receipt. Equal
// source and reassembly hashes prove content preservation; ranges prove that
// the locator space is contiguous, gap-free, and non-overlapping.
type Result struct {
	Signature       Signature
	ChunkerID       string
	ChunkerVersion  string
	SchemaID        string
	SchemaVersion   string
	SourceByteCount int
	SourceCharCount int
	SourceHash      string
	ReassemblyHash  string
	Chunks          []Chunk
}

func (r Result) Validate(source []byte) error {
	if !utf8.Valid(source) {
		return errors.New("source is not valid UTF-8")
	}
	if r.ChunkerID == "" || r.ChunkerVersion == "" || r.SchemaID == "" || r.SchemaVersion == "" {
		return errors.New("result requires pinned chunker and schema identity")
	}
	if r.SourceByteCount != len(source) || r.SourceCharCount != utf8.RuneCount(source) {
		return errors.New("result source counts do not match source")
	}
	if r.SourceHash != digest(source) || r.ReassemblyHash != r.SourceHash {
		return errors.New("completeness hash does not match source")
	}
	if len(source) == 0 {
		if len(r.Chunks) != 0 {
			return errors.New("empty source must produce zero chunks")
		}
		return nil
	}
	if len(r.Chunks) == 0 {
		return errors.New("non-empty source produced zero chunks")
	}
	nextByte, nextChar := 0, 0
	for index, piece := range r.Chunks {
		if piece.Index != index || piece.ByteStart != nextByte || piece.CharStart != nextChar {
			return fmt.Errorf("chunk %d is not contiguous", index)
		}
		if piece.ByteEnd <= piece.ByteStart || piece.CharEnd <= piece.CharStart || piece.ByteEnd > len(source) {
			return fmt.Errorf("chunk %d has invalid non-empty bounds", index)
		}
		if piece.Text != string(source[piece.ByteStart:piece.ByteEnd]) {
			return fmt.Errorf("chunk %d is not an original-source slice", index)
		}
		if piece.CharEnd-piece.CharStart != utf8.RuneCountInString(piece.Text) || piece.ContentHash != digest([]byte(piece.Text)) {
			return fmt.Errorf("chunk %d character bounds or content hash mismatch", index)
		}
		nextByte, nextChar = piece.ByteEnd, piece.CharEnd
	}
	if nextByte != len(source) || nextChar != utf8.RuneCount(source) {
		return errors.New("chunk ranges do not cover the complete source")
	}
	return nil
}

func digest(value []byte) string {
	sum := sha256.Sum256(value)
	return hex.EncodeToString(sum[:])
}

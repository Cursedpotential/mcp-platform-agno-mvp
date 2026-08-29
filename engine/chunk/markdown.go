package chunk

import (
	"bytes"
	"errors"
	"regexp"
	"sort"
	"unicode/utf8"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
)

const (
	// StructuredMaxChars is pinned from the adopted bake-off: the two
	// over-cap structural units measured 9,925 and 4,043 characters.
	StructuredMaxChars = 4000
	// StatuteMaxChars preserves the measured 4,969-character statute extract
	// as one unit while still bounding unexpectedly large heading-less input.
	StatuteMaxChars = 6000
)

var (
	headingBoundary    = regexp.MustCompile(`(?m)^#{1,6}[\t ]+\S`)
	chronologyBoundary = regexp.MustCompile(`(?m)^>[\t ]*\*[\t ]*\*\*`)
)

// Markdown is the Go-native document-markdown chunk capability adopted in
// the derived-document handoff. MaxChars is a code-point cap, not a byte cap.
type Markdown struct {
	// maxChars is a test-only override. It is intentionally unexported so a
	// production caller cannot produce different boundaries under the same
	// pinned chunker version.
	maxChars int
}

func DefaultMarkdown() Markdown { return Markdown{} }

func (Markdown) Capability() Capability {
	return Capability{
		ContractVersion: ContractVersion,
		ChunkerID:       ChunkerID,
		ChunkerVersion:  ChunkerVersion,
		Signatures: []Signature{
			SignatureChronology,
			SignatureResearchReport,
			SignatureStatuteExtract,
			SignatureStrategyMemo,
		},
		SignatureQuality: map[Signature]parser.Quality{
			SignatureChronology:     parser.QualityPrimary,
			SignatureResearchReport: parser.QualityPrimary,
			SignatureStatuteExtract: parser.QualityPrimary,
			SignatureStrategyMemo:   parser.QualityPrimary,
		},
	}
}

func (m Markdown) Chunk(source []byte, signature Signature) (Result, error) {
	if err := signature.Validate(); err != nil {
		return Result{}, err
	}
	if !utf8.Valid(source) {
		return Result{}, errors.New("document markdown source is not valid UTF-8")
	}

	cutPoints := []int{0}
	switch signature {
	case SignatureChronology:
		cutPoints = appendMatchStarts(cutPoints, chronologyBoundary, source)
	case SignatureResearchReport, SignatureStrategyMemo:
		cutPoints = appendMatchStarts(cutPoints, headingBoundary, source)
	case SignatureStatuteExtract:
		// Whole when under cap. Oversized input is handled by the common
		// paragraph/line/hard-cap splitter below.
	}
	cutPoints = append(cutPoints, len(source))
	cutPoints = normalizedCuts(cutPoints, len(source))
	maxChars := maxCharsFor(signature)
	if m.maxChars > 0 {
		maxChars = m.maxChars
	}

	ranges := make([]byteRange, 0, len(cutPoints))
	for index := 0; index+1 < len(cutPoints); index++ {
		start, end := cutPoints[index], cutPoints[index+1]
		if start < end {
			ranges = append(ranges, splitToCap(source, start, end, maxChars)...)
		}
	}

	result := buildResult(source, signature, ranges)
	if err := result.Validate(source); err != nil {
		return Result{}, err
	}
	return result, nil
}

func maxCharsFor(signature Signature) int {
	if signature == SignatureStatuteExtract {
		return StatuteMaxChars
	}
	return StructuredMaxChars
}

type byteRange struct{ start, end int }

func appendMatchStarts(cuts []int, expression *regexp.Regexp, source []byte) []int {
	for _, match := range expression.FindAllIndex(source, -1) {
		cuts = append(cuts, match[0])
	}
	return cuts
}

func normalizedCuts(cuts []int, sourceLength int) []int {
	sort.Ints(cuts)
	result := cuts[:0]
	last := -1
	for _, cut := range cuts {
		if cut < 0 || cut > sourceLength || cut == last {
			continue
		}
		result = append(result, cut)
		last = cut
	}
	return result
}

// splitToCap prefers the last paragraph boundary, then the last line
// boundary, within the cap. Only a structure unit with neither can trigger the
// rune-safe hard fallback. In every case all separator bytes remain assigned
// to the preceding chunk and no source content is altered or omitted.
func splitToCap(source []byte, start, end, maxChars int) []byteRange {
	result := make([]byteRange, 0, 1)
	for utf8.RuneCount(source[start:end]) > maxChars {
		limit := byteIndexAfterRunes(source, start, end, maxChars)
		cut := lastBoundary(source, start, limit, []byte("\n\n"))
		if cut <= start {
			cut = lastBoundary(source, start, limit, []byte("\n"))
		}
		if cut <= start {
			cut = limit
		}
		result = append(result, byteRange{start: start, end: cut})
		start = cut
	}
	if start < end {
		result = append(result, byteRange{start: start, end: end})
	}
	return result
}

func byteIndexAfterRunes(source []byte, start, end, count int) int {
	position := start
	for range count {
		_, size := utf8.DecodeRune(source[position:end])
		position += size
	}
	return position
}

func lastBoundary(source []byte, start, limit int, separator []byte) int {
	index := bytes.LastIndex(source[start:limit], separator)
	if index < 0 {
		return -1
	}
	return start + index + len(separator)
}

func buildResult(source []byte, signature Signature, ranges []byteRange) Result {
	pieces := make([]Chunk, 0, len(ranges))
	charStart := 0
	reassembled := make([]byte, 0, len(source))
	for index, bounds := range ranges {
		text := source[bounds.start:bounds.end]
		charEnd := charStart + utf8.RuneCount(text)
		pieces = append(pieces, Chunk{
			Index:       index,
			ByteStart:   bounds.start,
			ByteEnd:     bounds.end,
			CharStart:   charStart,
			CharEnd:     charEnd,
			Text:        string(text),
			ContentHash: digest(text),
		})
		reassembled = append(reassembled, text...)
		charStart = charEnd
	}
	return Result{
		Signature:       signature,
		ChunkerID:       ChunkerID,
		ChunkerVersion:  ChunkerVersion,
		SchemaID:        SchemaID,
		SchemaVersion:   SchemaVersion,
		SourceByteCount: len(source),
		SourceCharCount: utf8.RuneCount(source),
		SourceHash:      digest(source),
		ReassemblyHash:  digest(reassembled),
		Chunks:          pieces,
	}
}

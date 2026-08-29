package chunk

import (
	"strings"
	"testing"
	"unicode/utf8"
)

func TestMarkdownCapability(t *testing.T) {
	capability := DefaultMarkdown().Capability()
	if err := capability.Validate(); err != nil {
		t.Fatalf("capability validation: %v", err)
	}
	if capability.ChunkerID != ChunkerID || capability.ChunkerVersion != ChunkerVersion {
		t.Fatalf("unpinned capability identity: %#v", capability)
	}
}

func TestSignatureCutRulesAreLossless(t *testing.T) {
	tests := []struct {
		name      string
		signature Signature
		source    string
		starts    []string
	}{
		{
			name:      "heading sections",
			signature: SignatureResearchReport,
			source:    "preamble\n\n# One\nalpha\n\n## Two\nbeta\n",
			starts:    []string{"preamble", "# One", "## Two"},
		},
		{
			name:      "dated chronology entries",
			signature: SignatureChronology,
			source:    "### Era\nintro\n\n> * **Jan 1, 2020** first\n\n> * **Later** second\n",
			starts:    []string{"### Era", "> * **Jan", "> * **Later"},
		},
		{
			name:      "statute whole under cap",
			signature: SignatureStatuteExtract,
			source:    "`MCL 1`\n\n`MCL 2`\n",
			starts:    []string{"`MCL 1`"},
		},
		{
			name:      "strategy heading offsets",
			signature: SignatureStrategyMemo,
			source:    "title\n\n### Move one\n> proposed words\n\n### Move two\nclose\n",
			starts:    []string{"title", "### Move one", "### Move two"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			chunker := Markdown{maxChars: 1000}
			result, err := chunker.Chunk([]byte(test.source), test.signature)
			if err != nil {
				t.Fatal(err)
			}
			if len(result.Chunks) != len(test.starts) {
				t.Fatalf("got %d chunks, want %d: %#v", len(result.Chunks), len(test.starts), result.Chunks)
			}
			for index, prefix := range test.starts {
				if !strings.HasPrefix(result.Chunks[index].Text, prefix) {
					t.Fatalf("chunk %d = %q, want prefix %q", index, result.Chunks[index].Text, prefix)
				}
			}
			assertComplete(t, []byte(test.source), result)
		})
	}
}

func TestSeparatorAssignmentIsPinnedToPrecedingChunk(t *testing.T) {
	source := []byte("# One\nbody\n\n\n## Two\nbody")
	result, err := DefaultMarkdown().Chunk(source, SignatureResearchReport)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Chunks) != 2 {
		t.Fatalf("chunks = %d", len(result.Chunks))
	}
	if !strings.HasSuffix(result.Chunks[0].Text, "\n\n\n") {
		t.Fatalf("separator not assigned to preceding chunk: %q", result.Chunks[0].Text)
	}
	if !strings.HasPrefix(result.Chunks[1].Text, "## Two") {
		t.Fatalf("next chunk did not begin at heading: %q", result.Chunks[1].Text)
	}
}

func TestHardCapFallbackIsRuneSafeAndLossless(t *testing.T) {
	source := []byte("### Long\n" + strings.Repeat("évidence", 9))
	chunker := Markdown{maxChars: 13}
	first, err := chunker.Chunk(source, SignatureStrategyMemo)
	if err != nil {
		t.Fatal(err)
	}
	second, err := chunker.Chunk(source, SignatureStrategyMemo)
	if err != nil {
		t.Fatal(err)
	}
	if len(first.Chunks) < 2 {
		t.Fatalf("hard fallback did not split: %#v", first.Chunks)
	}
	for _, piece := range first.Chunks {
		if !utf8.ValidString(piece.Text) {
			t.Fatalf("invalid UTF-8 chunk: %q", piece.Text)
		}
		if utf8.RuneCountInString(piece.Text) > 13 {
			t.Fatalf("chunk exceeds cap: %q", piece.Text)
		}
	}
	if first.SourceHash != second.SourceHash || first.ReassemblyHash != second.ReassemblyHash || len(first.Chunks) != len(second.Chunks) {
		t.Fatal("replay is not deterministic")
	}
	for index := range first.Chunks {
		if first.Chunks[index] != second.Chunks[index] {
			t.Fatalf("chunk %d changed on replay", index)
		}
	}
	assertComplete(t, source, first)
}

func TestParagraphAndLineFallbackKeepDelimitersPreceding(t *testing.T) {
	source := []byte("one one\n\ntwo two\nthree three\nfour four")
	chunker := Markdown{maxChars: 12}
	result, err := chunker.Chunk(source, SignatureStatuteExtract)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(result.Chunks[0].Text, "\n\n") {
		t.Fatalf("paragraph separator not retained by preceding chunk: %q", result.Chunks[0].Text)
	}
	assertComplete(t, source, result)
}

func TestEmptyInvalidAndUnsupportedInputs(t *testing.T) {
	chunker := DefaultMarkdown()
	empty, err := chunker.Chunk(nil, SignatureStatuteExtract)
	if err != nil {
		t.Fatal(err)
	}
	if len(empty.Chunks) != 0 || empty.SourceHash != empty.ReassemblyHash {
		t.Fatalf("bad empty result: %#v", empty)
	}
	if _, err := chunker.Chunk([]byte{0xff}, SignatureStatuteExtract); err == nil {
		t.Fatal("invalid UTF-8 accepted")
	}
	if _, err := chunker.Chunk([]byte("text"), Signature("unknown")); err == nil {
		t.Fatal("unknown signature accepted")
	}
}

func assertComplete(t *testing.T, source []byte, result Result) {
	t.Helper()
	if err := result.Validate(source); err != nil {
		t.Fatalf("invalid result: %v", err)
	}
	var reassembled strings.Builder
	for _, piece := range result.Chunks {
		reassembled.WriteString(piece.Text)
	}
	if reassembled.String() != string(source) {
		t.Fatal("chunks do not reassemble source")
	}
}

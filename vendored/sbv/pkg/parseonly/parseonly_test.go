package parseonly

import (
	"context"
	"strings"
	"testing"
)

func TestChatGPTFacadePreservesOrderRawBytesAndTimestamp(t *testing.T) {
	input := `[{"title":"Conversation","create_time":1700000000,"mapping":{"root":{"id":"root","parent":null,"children":["n1"]},"n1":{"id":"n1","parent":"root","children":[],"message":{"id":"m1","author":{"role":"user"},"create_time":1700000001,"content":{"content_type":"text","parts":["hello"]}}}}}]`
	importer, err := New(FormatChatGPTJSON)
	if err != nil {
		t.Fatal(err)
	}
	var records []Record
	if err := importer.Parse(context.Background(), strings.NewReader(input), func(_ context.Context, record Record) error {
		records = append(records, record)
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if len(records) != 1 || records[0].Status != StatusParsed || string(records[0].Raw) == "" {
		t.Fatalf("records = %+v", records)
	}
	if records[0].Content != "hello" || records[0].OccurredAt == nil || records[0].OccurredAt.Unix() != 1700000001 {
		t.Fatalf("record projection = %+v", records[0])
	}
	if !strings.Contains(string(records[0].Raw), `"id":"m1"`) {
		t.Fatalf("raw message bytes were not preserved: %s", records[0].Raw)
	}
}

func TestEmailFormatsAreExplicitlyExcludedWhenRawBytesAreUnavailable(t *testing.T) {
	for _, format := range []string{FormatEML, FormatMBOX} {
		if _, err := New(format); err == nil {
			t.Fatalf("%s was accepted despite missing exact raw-byte output", format)
		}
	}
}

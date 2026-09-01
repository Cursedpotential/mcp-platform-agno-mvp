package runtimeapi

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
)

func inventoryTestSpec() activities.InventorySpec {
	return activities.InventorySpec{
		RequestID: "workflow-1", SourceVersionRef: "source-1",
		Stage: stagegraph.InventoryContainer, IdempotencyKey: "source-observation:workflow-1:source-1:inventory_container_activity:object-1",
		Attempt: 1,
	}
}

func TestNewFilesystemInventoryManifestFactoryRequiresRoot(t *testing.T) {
	if _, err := NewFilesystemInventoryManifestFactory(""); err == nil {
		t.Fatal("expected empty manifest directory to be rejected")
	}
	if _, err := NewFilesystemInventoryManifestFactory("   "); err == nil {
		t.Fatal("expected blank manifest directory to be rejected")
	}
}

func TestFilesystemInventoryManifestFactoryRequiresSpecIdentity(t *testing.T) {
	factory, err := NewFilesystemInventoryManifestFactory(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	spec := inventoryTestSpec()
	spec.RequestID = ""
	if _, err := factory(context.Background(), spec); err == nil {
		t.Fatal("expected missing request id to be rejected")
	}
	spec = inventoryTestSpec()
	spec.SourceVersionRef = ""
	if _, err := factory(context.Background(), spec); err == nil {
		t.Fatal("expected missing source version reference to be rejected")
	}
	spec = inventoryTestSpec()
	spec.IdempotencyKey = ""
	if _, err := factory(context.Background(), spec); err == nil {
		t.Fatal("expected missing idempotency key to be rejected")
	}
}

func TestFilesystemInventoryManifestWriterAppendRejectsOutOfOrderOrdinal(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = writer.Abort(context.Background()) }()
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 1, MemberRef: "member-1", ByteLength: 4}); err == nil {
		t.Fatal("expected out-of-order ordinal to fail closed")
	}
}

func TestFilesystemInventoryManifestWriterAppendRejectsNegativeAccounting(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = writer.Abort(context.Background()) }()
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 0, MemberRef: "member-0", ByteLength: -1}); err == nil {
		t.Fatal("expected negative byte length to fail closed")
	}
}

func TestFilesystemInventoryManifestWriterAbortBeforeAppendIsNoop(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	matches, err := filepath.Glob(filepath.Join(root, "aborted", "*"))
	if err != nil || len(matches) != 0 {
		t.Fatalf("aborted count = %d, err = %v, want 0 for a writer that never started", len(matches), err)
	}
}

func TestFilesystemInventoryManifestWriterAbortQuarantinesPartial(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 0, MemberRef: "member-0", ByteLength: 4}); err != nil {
		t.Fatal(err)
	}
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	matches, err := filepath.Glob(filepath.Join(root, "aborted", "*"))
	if err != nil || len(matches) != 1 {
		t.Fatalf("aborted count = %d, err = %v, want 1 preserved partial", len(matches), err)
	}
	inflight, err := filepath.Glob(filepath.Join(root, "inflight", "*"))
	if err != nil || len(inflight) != 0 {
		t.Fatalf("inflight count = %d, err = %v, want 0 after quarantine", len(inflight), err)
	}
	// Abort is idempotent once already finished.
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 1, MemberRef: "member-1", ByteLength: 1}); err == nil {
		t.Fatal("expected append after abort to fail closed")
	}
}

func TestFilesystemInventoryManifestWriterCommitRejectsSummaryMismatch(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 0, MemberRef: "member-0", ByteLength: 4}); err != nil {
		t.Fatal(err)
	}
	if _, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 2, TotalBytes: 4, RangeCount: 0}); err == nil {
		t.Fatal("expected member count mismatch to fail closed")
	}
	if _, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 1, TotalBytes: 999, RangeCount: 0}); err == nil {
		t.Fatal("expected total bytes mismatch to fail closed")
	}
	if _, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 1, TotalBytes: 4, RangeCount: 1}); err == nil {
		t.Fatal("expected range count mismatch to fail closed")
	}
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	matches, err := filepath.Glob(filepath.Join(root, "aborted", "*"))
	if err != nil || len(matches) != 1 {
		t.Fatalf("aborted count = %d, err = %v, want the rejected commit's partial preserved", len(matches), err)
	}
}

func TestFilesystemInventoryManifestWriterCommitRejectsEmptyManifest(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := writer.Commit(context.Background(), activities.InventorySummary{}); err == nil {
		t.Fatal("expected commit with zero staged members to fail closed")
	}
}

func appendStandardMembers(t *testing.T, writer interface {
	Append(context.Context, activities.InventoryMember) error
}) {
	t.Helper()
	offset := int64(12)
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 0, MemberRef: "member-0", ByteLength: 10}); err != nil {
		t.Fatal(err)
	}
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 1, MemberRef: "member-1", ParentRef: "member-0", ByteOffset: &offset, ByteLength: 5}); err != nil {
		t.Fatal(err)
	}
}

func TestFilesystemInventoryManifestWriterStreamsAndPublishesContentAddressed(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	appendStandardMembers(t, writer)
	ref, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 2, TotalBytes: 15, RangeCount: 1})
	if err != nil {
		t.Fatal(err)
	}
	if string(ref) == "" {
		t.Fatal("commit returned an empty reference")
	}
	path, err := pathFromFileURI(string(ref))
	if err != nil {
		t.Fatalf("commit did not return a valid file URI: %v", err)
	}
	if filepath.Dir(path) != filepath.Join(root, "objects") {
		t.Fatalf("published object path = %q, want under %q", path, filepath.Join(root, "objects"))
	}
	assertManifestContents(t, path)

	// Both the inflight and aborted directories must be empty: the file moved
	// straight from inflight to its content-addressed home.
	inflight, err := filepath.Glob(filepath.Join(root, "inflight", "*"))
	if err != nil || len(inflight) != 0 {
		t.Fatalf("inflight count = %d, err = %v, want 0 after a successful commit", len(inflight), err)
	}

	// A later Abort on an already-committed writer must not touch the
	// published object.
	if err := writer.Abort(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("published object disappeared after Abort: %v", err)
	}
}

func assertManifestContents(t *testing.T, path string) {
	t.Helper()
	file, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	var lines []inventoryManifestLine
	for scanner.Scan() {
		var line inventoryManifestLine
		if err := json.Unmarshal(scanner.Bytes(), &line); err != nil {
			t.Fatal(err)
		}
		lines = append(lines, line)
	}
	if err := scanner.Err(); err != nil {
		t.Fatal(err)
	}
	if len(lines) != 4 {
		t.Fatalf("manifest line count = %d, want 4 (header + 2 members + summary)", len(lines))
	}
	if lines[0].Kind != "header" || lines[0].Header == nil || lines[0].Header.RequestID != "workflow-1" {
		t.Fatalf("header line = %#v", lines[0])
	}
	if lines[1].Kind != "member" || lines[1].Member == nil || lines[1].Member.Ordinal != 0 {
		t.Fatalf("first member line = %#v", lines[1])
	}
	if lines[2].Kind != "member" || lines[2].Member == nil || lines[2].Member.Ordinal != 1 || lines[2].Member.ByteOffset == nil {
		t.Fatalf("second member line = %#v", lines[2])
	}
	if lines[3].Kind != "summary" || lines[3].Summary == nil || lines[3].Summary.MemberCount != 2 {
		t.Fatalf("summary line = %#v", lines[3])
	}
}

func TestFilesystemInventoryManifestWriterIsIdempotentAcrossRetries(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}

	commitOnce := func() string {
		writer, err := factory(context.Background(), inventoryTestSpec())
		if err != nil {
			t.Fatal(err)
		}
		appendStandardMembers(t, writer)
		ref, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 2, TotalBytes: 15, RangeCount: 1})
		if err != nil {
			t.Fatal(err)
		}
		return string(ref)
	}

	first := commitOnce()
	second := commitOnce()
	if first != second {
		t.Fatalf("retry produced a different reference: %q vs %q", first, second)
	}
	objects, err := filepath.Glob(filepath.Join(root, "objects", "*"))
	if err != nil || len(objects) != 1 {
		t.Fatalf("objects count = %d, err = %v, want exactly 1 content-addressed manifest", len(objects), err)
	}
	duplicates, err := filepath.Glob(filepath.Join(root, "duplicates", "*"))
	if err != nil || len(duplicates) != 1 {
		t.Fatalf("duplicates count = %d, err = %v, want the second retry's byte-identical write archived", len(duplicates), err)
	}
}

func TestFilesystemInventoryManifestWriterCommitAndAppendAfterFinishFailClosed(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	appendStandardMembers(t, writer)
	if _, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 2, TotalBytes: 15, RangeCount: 1}); err != nil {
		t.Fatal(err)
	}
	if err := writer.Append(context.Background(), activities.InventoryMember{Ordinal: 2, MemberRef: "member-2", ByteLength: 1}); err == nil {
		t.Fatal("expected append after commit to fail closed")
	}
	if _, err := writer.Commit(context.Background(), activities.InventorySummary{MemberCount: 2, TotalBytes: 15, RangeCount: 1}); err == nil {
		t.Fatal("expected a second commit to fail closed")
	}
}

func TestFilesystemInventoryManifestWriterCommitCanceledContext(t *testing.T) {
	root := t.TempDir()
	factory, err := NewFilesystemInventoryManifestFactory(root)
	if err != nil {
		t.Fatal(err)
	}
	writer, err := factory(context.Background(), inventoryTestSpec())
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = writer.Abort(context.Background()) }()
	appendStandardMembers(t, writer)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := writer.Commit(ctx, activities.InventorySummary{MemberCount: 2, TotalBytes: 15, RangeCount: 1}); !errors.Is(err, context.Canceled) {
		t.Fatalf("error = %v, want context.Canceled", err)
	}
}

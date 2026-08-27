// This file implements NewFilesystemInventoryManifestFactory, a filesystem
// content-addressed postgres.InventoryManifestWriterFactory. It mirrors
// bundle_store.go's and normalized_bundle_store.go's write path: members
// stream to a staging file under "inflight", the finished manifest is hashed
// and atomically published under "objects" keyed by its own content digest,
// and any partial or duplicate file is quarantined/archived rather than
// deleted. It has no PostgreSQL dependency: migration 0036 intentionally has
// no inventory staging table (see postgres/source_observation_store.go), so
// the only durable trace of a committed manifest is the compact,
// content-addressed file:// reference this factory returns — the manifest
// payload itself never enters a Temporal result.
package runtimeapi

import (
	"bufio"
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
)

// inventoryManifestContractVersion pins this file's own JSONL storage-format
// wrapper (header/member/summary lines), independent of any activities-level
// contract.
const inventoryManifestContractVersion = "platform-inventory-manifest-jsonl-v1"

// NewFilesystemInventoryManifestFactory creates durable, content-addressed
// inventory manifest writers under root, mirroring NewFilesystemBundleFactory
// and NewFilesystemNormalizedBundleFactory exactly.
func NewFilesystemInventoryManifestFactory(root string) (platformpostgres.InventoryManifestWriterFactory, error) {
	root = strings.TrimSpace(root)
	if root == "" {
		return nil, errors.New("inventory manifest store: manifest directory is required")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return nil, fmt.Errorf("resolve inventory manifest directory: %w", err)
	}
	for _, directory := range []string{"inflight", "objects", "aborted", "duplicates"} {
		if err := os.MkdirAll(filepath.Join(absolute, directory), 0o750); err != nil {
			return nil, fmt.Errorf("create inventory manifest %s directory: %w", directory, err)
		}
	}
	return func(_ context.Context, spec activities.InventorySpec) (platformpostgres.InventoryManifestWriter, error) {
		if strings.TrimSpace(spec.RequestID) == "" || strings.TrimSpace(string(spec.SourceVersionRef)) == "" || strings.TrimSpace(spec.IdempotencyKey) == "" {
			return nil, errors.New("inventory manifest writer requires request, source version, and idempotency key")
		}
		return &filesystemInventoryManifestWriter{root: absolute, spec: spec}, nil
	}, nil
}

type filesystemInventoryManifestWriter struct {
	root        string
	spec        activities.InventorySpec
	file        *os.File
	buffer      *bufio.Writer
	path        string
	started     bool
	finished    bool
	published   bool
	nextOrdinal int64
	totalBytes  int64
	rangeCount  int64
}

type inventoryManifestHeader struct {
	RequestID        string `json:"request_id"`
	SourceVersionRef string `json:"source_version_ref"`
	Stage            string `json:"stage"`
	IdempotencyKey   string `json:"idempotency_key"`
}

type inventoryManifestLine struct {
	Kind     string                       `json:"kind"`
	Contract string                       `json:"contract"`
	Header   *inventoryManifestHeader     `json:"header,omitempty"`
	Member   *activities.InventoryMember  `json:"member,omitempty"`
	Summary  *activities.InventorySummary `json:"summary,omitempty"`
}

// ensureStarted lazily opens the staging file on the first Append: the
// InventoryManifestWriter interface has no separate Begin step.
func (w *filesystemInventoryManifestWriter) ensureStarted() error {
	if w.started {
		return nil
	}
	if w.finished {
		return errors.New("inventory manifest writer has already finished")
	}
	path := filepath.Join(w.root, "inflight", uuid.NewString()+".jsonl.partial")
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create inventory manifest: %w", err)
	}
	w.file, w.buffer, w.path, w.started = file, bufio.NewWriterSize(file, 64*1024), path, true
	header := inventoryManifestHeader{
		RequestID: w.spec.RequestID, SourceVersionRef: string(w.spec.SourceVersionRef),
		Stage: string(w.spec.Stage), IdempotencyKey: w.spec.IdempotencyKey,
	}
	if err := w.writeLine(inventoryManifestLine{Kind: "header", Contract: inventoryManifestContractVersion, Header: &header}); err != nil {
		_ = w.quarantine("aborted")
		return err
	}
	return nil
}

// Append validates the member's ordinal is exactly the next contiguous
// position and its byte accounting is well-formed before streaming it,
// mirroring the double-check already performed by
// postgres.inventoryWriter.Append one layer up.
func (w *filesystemInventoryManifestWriter) Append(ctx context.Context, member activities.InventoryMember) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if w.finished {
		return errors.New("inventory manifest writer has already finished")
	}
	if err := w.ensureStarted(); err != nil {
		return err
	}
	if member.Ordinal != w.nextOrdinal {
		return fmt.Errorf("inventory manifest member ordinal %d, expected %d", member.Ordinal, w.nextOrdinal)
	}
	if member.ByteLength < 0 {
		return errors.New("inventory manifest member byte length cannot be negative")
	}
	if member.ByteOffset != nil && *member.ByteOffset < 0 {
		return errors.New("inventory manifest member byte offset cannot be negative")
	}
	if member.ByteLength > (int64(^uint64(0)>>1) - w.totalBytes) {
		return errors.New("inventory manifest byte accounting overflow")
	}
	copyMember := member
	if err := w.writeLine(inventoryManifestLine{Kind: "member", Contract: inventoryManifestContractVersion, Member: &copyMember}); err != nil {
		return err
	}
	w.nextOrdinal++
	w.totalBytes += member.ByteLength
	if member.ByteOffset != nil {
		w.rangeCount++
	}
	return nil
}

// Commit validates the caller's summary against the accounting streamed
// through Append, fsyncs and closes the staging file, hashes it, and
// atomically publishes it under root/objects keyed by its own content digest.
// Two writers that stream byte-identical members and commit the identical
// summary always converge on the identical published object and therefore the
// identical returned Ref: that convergence, not any database row, is what
// makes a Temporal retry or a concurrent duplicate attempt idempotent here.
func (w *filesystemInventoryManifestWriter) Commit(ctx context.Context, summary activities.InventorySummary) (uiw.Ref, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	if w.finished || !w.started || w.file == nil || w.nextOrdinal == 0 {
		return "", errors.New("inventory manifest writer cannot commit its current state")
	}
	if summary.MemberCount != w.nextOrdinal {
		return "", fmt.Errorf("inventory manifest summary member count %d does not match %d staged members", summary.MemberCount, w.nextOrdinal)
	}
	if summary.TotalBytes != w.totalBytes {
		return "", fmt.Errorf("inventory manifest summary total bytes %d does not match %d staged bytes", summary.TotalBytes, w.totalBytes)
	}
	if summary.RangeCount != w.rangeCount {
		return "", fmt.Errorf("inventory manifest summary range count %d does not match %d staged ranges", summary.RangeCount, w.rangeCount)
	}
	copySummary := summary
	if err := w.writeLine(inventoryManifestLine{Kind: "summary", Contract: inventoryManifestContractVersion, Summary: &copySummary}); err != nil {
		return "", err
	}
	if err := w.buffer.Flush(); err != nil {
		return "", fmt.Errorf("flush inventory manifest: %w", err)
	}
	if err := w.file.Sync(); err != nil {
		return "", fmt.Errorf("sync inventory manifest: %w", err)
	}
	if err := w.file.Close(); err != nil {
		return "", fmt.Errorf("close inventory manifest: %w", err)
	}
	w.file, w.buffer = nil, nil

	digest, byteLength, err := hashFile(ctx, w.path)
	if err != nil {
		return "", err
	}
	objectPath := filepath.Join(w.root, "objects", hex.EncodeToString(digest)+".jsonl")
	if err := publishContentAddressed(w.path, objectPath, digest, byteLength, w.root); err != nil {
		return "", err
	}
	w.path = objectPath
	w.published = true
	w.finished = true
	return uiw.Ref(fileURI(objectPath)), nil
}

func (w *filesystemInventoryManifestWriter) Abort(_ context.Context) error {
	if w.finished {
		return nil
	}
	w.finished = true
	// Mirrors the parser/normalized bundle writers: once the content-addressed
	// object is published, never move it on a later error, and never delete a
	// partial — quarantine it so it survives for inspection.
	if w.published || !w.started {
		return nil
	}
	return w.quarantine("aborted")
}

func (w *filesystemInventoryManifestWriter) writeLine(line inventoryManifestLine) error {
	if err := json.NewEncoder(w.buffer).Encode(line); err != nil {
		return fmt.Errorf("encode inventory manifest line: %w", err)
	}
	return nil
}

func (w *filesystemInventoryManifestWriter) quarantine(directory string) error {
	if w.buffer != nil {
		_ = w.buffer.Flush()
	}
	if w.file != nil {
		_ = w.file.Close()
	}
	w.file, w.buffer = nil, nil
	if strings.TrimSpace(w.path) == "" {
		return nil
	}
	target := filepath.Join(w.root, directory, uuid.NewString()+filepath.Ext(w.path))
	if err := os.Rename(w.path, target); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("quarantine inventory manifest: %w", err)
	}
	w.path = target
	return nil
}

var _ platformpostgres.InventoryManifestWriter = (*filesystemInventoryManifestWriter)(nil)

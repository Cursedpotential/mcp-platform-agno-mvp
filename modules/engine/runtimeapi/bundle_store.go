package runtimeapi

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/parser"
	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

const bundleContractVersion = "platform-raw-extraction-jsonl-v1"

// NewFilesystemBundleFactory creates durable, content-addressed parser bundle
// writers. The resulting retained-object UUID is the only value returned to
// the Activity caller; source-native records never enter HTTP or Temporal
// results.
func NewFilesystemBundleFactory(db platformpostgres.DB, root string) (platformpostgres.BundleWriterFactory, error) {
	if db == nil {
		return nil, errors.New("parser bundle store: database is required")
	}
	root = strings.TrimSpace(root)
	if root == "" {
		return nil, errors.New("parser bundle store: bundle directory is required")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return nil, fmt.Errorf("resolve parser bundle directory: %w", err)
	}
	for _, directory := range []string{"inflight", "objects", "aborted", "duplicates"} {
		if err := os.MkdirAll(filepath.Join(absolute, directory), 0o750); err != nil {
			return nil, fmt.Errorf("create parser bundle %s directory: %w", directory, err)
		}
	}
	return func(_ context.Context, req uiw.StageRequest, selection activities.PersistedParserSelection, input parser.ParserInput) (parser.BundleWriter, error) {
		if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
			return nil, errors.New("parser bundle writer requires request and source references")
		}
		return &filesystemBundleWriter{
			db: db, root: absolute, request: req, selection: selection, input: input,
		}, nil
	}, nil
}

type filesystemBundleWriter struct {
	db        platformpostgres.DB
	root      string
	request   uiw.StageRequest
	selection activities.PersistedParserSelection
	input     parser.ParserInput
	file      *os.File
	buffer    *bufio.Writer
	path      string
	started   bool
	finished  bool
	published bool
	records   uint64
}

type bundleLine struct {
	Kind       string                    `json:"kind"`
	Contract   string                    `json:"contract"`
	Header     *parser.BundleHeader      `json:"header,omitempty"`
	Record     *parser.RawRecordEnvelope `json:"record,omitempty"`
	Accounting *parser.BundleAccounting  `json:"accounting,omitempty"`
}

func (w *filesystemBundleWriter) Begin(ctx context.Context, header parser.BundleHeader) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if w.started || w.finished {
		return errors.New("parser bundle writer has already started")
	}
	if header.ContractVersion != parser.ContractVersion || header.SourceVersionRef != string(w.request.SourceVersionRef) ||
		header.ParserID != w.selection.ParserID || header.ParserVersion != w.selection.ParserVersion ||
		header.FormatID != w.selection.DeclaredFormat || header.FormatID != w.input.DeclaredFormat {
		return errors.New("parser bundle header does not match the persisted parser selection")
	}
	path := filepath.Join(w.root, "inflight", uuid.NewString()+".jsonl.partial")
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create parser bundle: %w", err)
	}
	w.file, w.buffer, w.path, w.started = file, bufio.NewWriterSize(file, 64*1024), path, true
	if err := w.writeLine(bundleLine{Kind: "header", Contract: bundleContractVersion, Header: &header}); err != nil {
		_ = w.quarantine("aborted")
		return err
	}
	return nil
}

func (w *filesystemBundleWriter) Emit(ctx context.Context, record parser.RawRecordEnvelope) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if !w.started || w.finished || w.file == nil {
		return errors.New("parser bundle writer is not open")
	}
	if record.RecordOrdinal != w.records {
		return fmt.Errorf("parser bundle record ordinal %d, expected %d", record.RecordOrdinal, w.records)
	}
	copyRecord := record
	if err := w.writeLine(bundleLine{Kind: "record", Contract: bundleContractVersion, Record: &copyRecord}); err != nil {
		return err
	}
	w.records++
	return nil
}

func (w *filesystemBundleWriter) Finalize(ctx context.Context, accounting parser.BundleAccounting) (parser.BundleResult, error) {
	if err := ctx.Err(); err != nil {
		return parser.BundleResult{}, err
	}
	if !w.started || w.finished || w.file == nil || w.records == 0 {
		return parser.BundleResult{}, errors.New("parser bundle writer cannot finalize its current state")
	}
	copyAccounting := accounting
	if err := w.writeLine(bundleLine{Kind: "accounting", Contract: bundleContractVersion, Accounting: &copyAccounting}); err != nil {
		return parser.BundleResult{}, err
	}
	if err := w.buffer.Flush(); err != nil {
		return parser.BundleResult{}, fmt.Errorf("flush parser bundle: %w", err)
	}
	if err := w.file.Sync(); err != nil {
		return parser.BundleResult{}, fmt.Errorf("sync parser bundle: %w", err)
	}
	if err := w.file.Close(); err != nil {
		return parser.BundleResult{}, fmt.Errorf("close parser bundle: %w", err)
	}
	w.file, w.buffer = nil, nil

	digest, byteLength, err := hashFile(ctx, w.path)
	if err != nil {
		return parser.BundleResult{}, err
	}
	objectPath := filepath.Join(w.root, "objects", hex.EncodeToString(digest)+".jsonl")
	if err := publishContentAddressed(w.path, objectPath, digest, byteLength, w.root); err != nil {
		return parser.BundleResult{}, err
	}
	w.path = objectPath
	w.published = true
	objectID, err := w.persistObject(ctx, objectPath, digest, byteLength)
	if err != nil {
		return parser.BundleResult{}, err
	}
	w.finished = true
	return parser.BundleResult{BundleRef: objectID.String()}, nil
}

func (w *filesystemBundleWriter) Abort(_ context.Context) error {
	if w.finished {
		return nil
	}
	w.finished = true
	// Once the content-addressed file is published, never move it on a
	// database error: a failed Commit can be outcome-ambiguous. Leaving the
	// immutable bytes at their URI keeps any committed row valid and lets an
	// idempotent retry reconcile or register the same digest.
	if w.published {
		return nil
	}
	return w.quarantine("aborted")
}

func (w *filesystemBundleWriter) writeLine(line bundleLine) error {
	if err := json.NewEncoder(w.buffer).Encode(line); err != nil {
		return fmt.Errorf("encode parser bundle line: %w", err)
	}
	return nil
}

func (w *filesystemBundleWriter) quarantine(directory string) error {
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
		return fmt.Errorf("quarantine parser bundle: %w", err)
	}
	w.path = target
	return nil
}

func (w *filesystemBundleWriter) persistObject(ctx context.Context, path string, digest []byte, byteLength int64) (uuid.UUID, error) {
	tx, err := w.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return uuid.Nil, fmt.Errorf("begin parser bundle transaction: %w", err)
	}
	rollback := true
	defer func() {
		if rollback {
			cleanup, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
			defer cancel()
			_ = tx.Rollback(cleanup)
		}
	}()
	objectURI := fileURI(path)
	var objectID uuid.UUID
	err = tx.QueryRow(ctx, `
		INSERT INTO context.retained_object
		    (storage_class, object_uri, content_sha256, byte_length)
		VALUES ('filesystem', $1, $2, $3)
		ON CONFLICT (content_sha256, byte_length) DO NOTHING
		RETURNING id`, objectURI, digest, byteLength).Scan(&objectID)
	if errors.Is(err, pgx.ErrNoRows) {
		err = tx.QueryRow(ctx, `
			SELECT id FROM context.retained_object
			WHERE content_sha256 = $1 AND byte_length = $2`, digest, byteLength).Scan(&objectID)
	}
	if err != nil {
		return uuid.Nil, fmt.Errorf("persist parser bundle object: %w", err)
	}
	var originalID uuid.UUID
	if err := tx.QueryRow(ctx, `
		SELECT original_object_id FROM context.source_version
		WHERE id = $1::uuid AND status = 'retained'`, string(w.request.SourceVersionRef)).Scan(&originalID); err != nil {
		return uuid.Nil, fmt.Errorf("resolve parser bundle source membership: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.source_version_object
		    (source_version_id, object_id, object_role, parent_object_id, member_locator)
		VALUES ($1::uuid, $2::uuid, 'derived_reference', $3::uuid,
		        jsonb_build_object('kind', 'raw_extraction_bundle', 'contract', $4::text))
		ON CONFLICT (source_version_id, object_id) DO NOTHING`, string(w.request.SourceVersionRef), objectID, originalID, bundleContractVersion); err != nil {
		return uuid.Nil, fmt.Errorf("bind parser bundle to source version: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return uuid.Nil, fmt.Errorf("commit parser bundle object: %w", err)
	}
	rollback = false
	return objectID, nil
}

// NewRetainedObjectOpener resolves inline bytes through PostgreSQL and permits
// only file:// URIs for non-inline objects. Network object-store retrieval is
// intentionally a separate adapter rather than an implicit HTTP fetch.
func NewRetainedObjectOpener(db platformpostgres.DB) (func(context.Context, string) (io.ReadCloser, error), error) {
	if db == nil {
		return nil, errors.New("retained object opener: database is required")
	}
	return func(ctx context.Context, objectURI string) (io.ReadCloser, error) {
		var storageClass string
		var inline []byte
		if err := db.QueryRow(ctx, `
			SELECT storage_class, inline_bytes FROM context.retained_object
			WHERE object_uri = $1`, objectURI).Scan(&storageClass, &inline); err != nil {
			return nil, fmt.Errorf("resolve retained object: %w", err)
		}
		if storageClass == "inline" {
			return io.NopCloser(bytes.NewReader(inline)), nil
		}
		path, err := pathFromFileURI(objectURI)
		if err != nil {
			return nil, fmt.Errorf("open %s retained object: %w", storageClass, err)
		}
		file, err := os.Open(path)
		if err != nil {
			return nil, fmt.Errorf("open retained object file: %w", err)
		}
		return file, nil
	}, nil
}

func hashFile(ctx context.Context, path string) ([]byte, int64, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, 0, fmt.Errorf("open finalized parser bundle: %w", err)
	}
	defer file.Close()
	hash := sha256.New()
	buffer := make([]byte, 128*1024)
	var count int64
	for {
		if err := ctx.Err(); err != nil {
			return nil, 0, err
		}
		n, readErr := file.Read(buffer)
		if n > 0 {
			count += int64(n)
			_, _ = hash.Write(buffer[:n])
		}
		if errors.Is(readErr, io.EOF) {
			break
		}
		if readErr != nil {
			return nil, 0, fmt.Errorf("hash parser bundle: %w", readErr)
		}
	}
	return hash.Sum(nil), count, nil
}

func publishContentAddressed(source, target string, digest []byte, length int64, root string) error {
	if info, err := os.Stat(target); err == nil {
		actualDigest, actualLength, hashErr := hashFile(context.Background(), target)
		if hashErr != nil || actualLength != length || !bytes.Equal(actualDigest, digest) || info.IsDir() {
			return errors.New("parser bundle content-addressed target conflicts with existing content")
		}
		duplicate := filepath.Join(root, "duplicates", uuid.NewString()+".jsonl")
		if err := os.Rename(source, duplicate); err != nil {
			return fmt.Errorf("archive duplicate parser bundle: %w", err)
		}
		return nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("inspect parser bundle target: %w", err)
	}
	if err := os.Rename(source, target); err != nil {
		return fmt.Errorf("publish parser bundle: %w", err)
	}
	return nil
}

func fileURI(path string) string {
	absolute, _ := filepath.Abs(path)
	uriPath := filepath.ToSlash(absolute)
	if runtime.GOOS == "windows" && !strings.HasPrefix(uriPath, "/") {
		uriPath = "/" + uriPath
	}
	return (&url.URL{Scheme: "file", Path: uriPath}).String()
}

func pathFromFileURI(value string) (string, error) {
	parsed, err := url.Parse(value)
	if err != nil || parsed.Scheme != "file" || parsed.Host != "" {
		return "", errors.New("non-inline retained objects require a local file URI")
	}
	path := filepath.FromSlash(parsed.Path)
	if runtime.GOOS == "windows" && len(path) >= 3 && (path[0] == '\\' || path[0] == '/') && path[2] == ':' {
		path = path[1:]
	}
	if !filepath.IsAbs(path) {
		return "", errors.New("retained object file URI must be absolute")
	}
	return filepath.Clean(path), nil
}

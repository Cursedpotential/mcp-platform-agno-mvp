// This file implements the filesystem/content-addressed normalized bundle
// writer and reader factories, satisfying postgres.NormalizedBundleWriterFactory
// and postgres.NormalizedBundleReaderFactory exactly as bundle_store.go does
// for the parser side. It reuses that file's content-addressing helpers
// (hashFile, publishContentAddressed, fileURI, pathFromFileURI) rather than
// duplicating them, and it never places normalized record bytes in a Temporal
// result: only a compact retained_object id ever leaves this file.
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
	"hash"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/normalize"
	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
)

// normalizedBundleContractVersion pins this file's own JSONL storage-format
// wrapper. It is independent of normalize.ContractVersion, which pins the
// header/record/accounting payload shape carried inside each line.
const normalizedBundleContractVersion = "platform-normalized-jsonl-v1"

// NewFilesystemNormalizedBundleFactory creates durable, content-addressed
// normalized bundle writers, mirroring NewFilesystemBundleFactory exactly.
func NewFilesystemNormalizedBundleFactory(db platformpostgres.DB, root string) (platformpostgres.NormalizedBundleWriterFactory, error) {
	if db == nil {
		return nil, errors.New("normalized bundle store: database is required")
	}
	root = strings.TrimSpace(root)
	if root == "" {
		return nil, errors.New("normalized bundle store: bundle directory is required")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return nil, fmt.Errorf("resolve normalized bundle directory: %w", err)
	}
	absolute = filepath.Clean(absolute)
	for _, directory := range []string{"", "inflight", "objects", "aborted", "duplicates"} {
		path := filepath.Join(absolute, directory)
		if err := os.MkdirAll(path, 0o750); err != nil {
			return nil, fmt.Errorf("create normalized bundle %s directory: %w", directory, err)
		}
		if err := requireRealDirectory(path); err != nil {
			return nil, fmt.Errorf("unsafe normalized bundle %s directory: %w", directory, err)
		}
	}
	return func(_ context.Context, req uiw.StageRequest, input normalize.NormalizerInput) (normalize.BundleWriter, error) {
		if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
			return nil, errors.New("normalized bundle writer requires request and source references")
		}
		if input.SourceVersionRef != string(req.SourceVersionRef) {
			return nil, errors.New("normalized bundle writer input does not match request")
		}
		return &filesystemNormalizedBundleWriter{db: db, root: absolute, request: req, input: input}, nil
	}, nil
}

type filesystemNormalizedBundleWriter struct {
	db        platformpostgres.DB
	root      string
	request   uiw.StageRequest
	input     normalize.NormalizerInput
	file      *os.File
	buffer    *bufio.Writer
	path      string
	started   bool
	finished  bool
	published bool
	records   uint64
}

type normalizedBundleLine struct {
	Kind       string                      `json:"kind"`
	Contract   string                      `json:"contract"`
	Header     *normalize.BundleHeader     `json:"header,omitempty"`
	Record     *normalize.RecordEnvelope   `json:"record,omitempty"`
	Accounting *normalize.BundleAccounting `json:"accounting,omitempty"`
}

func (w *filesystemNormalizedBundleWriter) Begin(ctx context.Context, header normalize.BundleHeader) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if w.started || w.finished {
		return errors.New("normalized bundle writer has already started")
	}
	if header.ContractVersion != normalize.ContractVersion ||
		header.SourceVersionRef != w.input.SourceVersionRef ||
		header.RawGenerationRef != w.input.RawGenerationRef ||
		strings.TrimSpace(header.NormalizerID) == "" || strings.TrimSpace(header.NormalizerVersion) == "" {
		return errors.New("normalized bundle header does not match the normalizer input")
	}
	inflight := filepath.Join(w.root, "inflight")
	if err := requireRealDirectory(inflight); err != nil {
		return fmt.Errorf("unsafe normalized bundle inflight directory: %w", err)
	}
	path := filepath.Join(inflight, uuid.NewString()+".jsonl.partial")
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create normalized bundle: %w", err)
	}
	w.file, w.buffer, w.path, w.started = file, bufio.NewWriterSize(file, 64*1024), path, true
	if err := w.writeLine(normalizedBundleLine{Kind: "header", Contract: normalizedBundleContractVersion, Header: &header}); err != nil {
		_ = w.quarantine("aborted")
		return err
	}
	return nil
}

func (w *filesystemNormalizedBundleWriter) Emit(ctx context.Context, record normalize.RecordEnvelope) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if !w.started || w.finished || w.file == nil {
		return errors.New("normalized bundle writer is not open")
	}
	if record.RecordOrdinal != w.records {
		return fmt.Errorf("normalized bundle record ordinal %d, expected %d", record.RecordOrdinal, w.records)
	}
	copyRecord := record
	if err := w.writeLine(normalizedBundleLine{Kind: "record", Contract: normalizedBundleContractVersion, Record: &copyRecord}); err != nil {
		return err
	}
	w.records++
	return nil
}

func (w *filesystemNormalizedBundleWriter) Finalize(ctx context.Context, accounting normalize.BundleAccounting) (normalize.BundleResult, error) {
	if err := ctx.Err(); err != nil {
		return normalize.BundleResult{}, err
	}
	if !w.started || w.finished || w.file == nil || w.records == 0 {
		return normalize.BundleResult{}, errors.New("normalized bundle writer cannot finalize its current state")
	}
	if accounting.Emitted != w.records {
		return normalize.BundleResult{}, fmt.Errorf("normalized bundle accounting emitted %d does not match %d written records", accounting.Emitted, w.records)
	}
	copyAccounting := accounting
	if err := w.writeLine(normalizedBundleLine{Kind: "accounting", Contract: normalizedBundleContractVersion, Accounting: &copyAccounting}); err != nil {
		return normalize.BundleResult{}, err
	}
	if err := w.buffer.Flush(); err != nil {
		return normalize.BundleResult{}, fmt.Errorf("flush normalized bundle: %w", err)
	}
	if err := w.file.Sync(); err != nil {
		return normalize.BundleResult{}, fmt.Errorf("sync normalized bundle: %w", err)
	}
	if err := w.file.Close(); err != nil {
		return normalize.BundleResult{}, fmt.Errorf("close normalized bundle: %w", err)
	}
	w.file, w.buffer = nil, nil

	digest, byteLength, err := hashNormalizedBundleFile(ctx, w.path)
	if err != nil {
		return normalize.BundleResult{}, err
	}
	objectsDirectory := filepath.Join(w.root, "objects")
	if err := requireRealDirectory(objectsDirectory); err != nil {
		return normalize.BundleResult{}, fmt.Errorf("unsafe normalized bundle objects directory: %w", err)
	}
	objectPath := filepath.Join(objectsDirectory, hex.EncodeToString(digest)+".jsonl")
	published, err := publishNormalizedBundleObject(ctx, w.path, objectPath, digest, byteLength)
	if err != nil {
		return normalize.BundleResult{}, err
	}
	// Once a verified object exists at the content address it must never be
	// moved by Abort, even if the following database transaction has an
	// outcome-ambiguous failure.
	w.published = true
	if err := w.quarantine("duplicates"); err != nil {
		return normalize.BundleResult{}, err
	}
	if err := makeNormalizedBundleReadOnly(objectPath); err != nil {
		return normalize.BundleResult{}, err
	}
	if err := verifyAcquisitionObject(ctx, objectPath, digest, byteLength); err != nil {
		return normalize.BundleResult{}, fmt.Errorf("verify published normalized bundle: %w", err)
	}
	if published {
		if err := syncAcquisitionDirectory(objectsDirectory); err != nil {
			return normalize.BundleResult{}, fmt.Errorf("sync normalized bundle objects directory: %w", err)
		}
	}
	w.path = objectPath
	objectID, err := w.persistObject(ctx, objectPath, digest, byteLength)
	if err != nil {
		return normalize.BundleResult{}, err
	}
	w.finished = true
	return normalize.BundleResult{BundleRef: objectID.String()}, nil
}

func (w *filesystemNormalizedBundleWriter) Abort(_ context.Context) error {
	if w.finished {
		return nil
	}
	w.finished = true
	// Mirrors filesystemBundleWriter.Abort: once the content-addressed file
	// is published, never move it on a later database error. A failed
	// Commit can be outcome-ambiguous; leaving the immutable bytes at their
	// URI keeps any committed row valid and lets an idempotent retry
	// reconcile or register the same digest.
	if w.published {
		return nil
	}
	return w.quarantine("aborted")
}

func (w *filesystemNormalizedBundleWriter) writeLine(line normalizedBundleLine) error {
	if err := json.NewEncoder(w.buffer).Encode(line); err != nil {
		return fmt.Errorf("encode normalized bundle line: %w", err)
	}
	return nil
}

func (w *filesystemNormalizedBundleWriter) quarantine(directory string) error {
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
	quarantine := filepath.Join(w.root, directory)
	if err := requireRealDirectory(quarantine); err != nil {
		return fmt.Errorf("unsafe normalized bundle quarantine directory: %w", err)
	}
	target := filepath.Join(quarantine, uuid.NewString()+filepath.Ext(w.path))
	if err := os.Rename(w.path, target); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("quarantine normalized bundle: %w", err)
	}
	w.path = target
	return nil
}

func hashNormalizedBundleFile(ctx context.Context, path string) ([]byte, int64, error) {
	file, err := openRegularNonAliasFile(path)
	if err != nil {
		return nil, 0, fmt.Errorf("open finalized normalized bundle: %w", err)
	}
	defer file.Close()
	digest := sha256.New()
	length, err := copyAcquisition(ctx, digest, file)
	if err != nil {
		return nil, 0, fmt.Errorf("hash finalized normalized bundle: %w", err)
	}
	return digest.Sum(nil), length, nil
}

// publishNormalizedBundleObject uses the acquisition boundary's hard-link
// primitive instead of Rename. Link is atomic and no-clobber on every
// supported platform: an existing target is reverified, never replaced.
func publishNormalizedBundleObject(ctx context.Context, source, target string, digest []byte, length int64) (bool, error) {
	published, err := publishAcquisitionObject(ctx, source, target, digest, length)
	if err != nil {
		return false, fmt.Errorf("publish normalized bundle: %w", err)
	}
	return published, nil
}

func makeNormalizedBundleReadOnly(path string) error {
	file, err := openRegularNonAliasFile(path)
	if err != nil {
		return fmt.Errorf("open normalized bundle for immutable mode: %w", err)
	}
	if runtime.GOOS == "windows" {
		// Windows cannot change the read-only attribute through the read-only
		// handle returned by os.Open. Close the already identity-checked handle,
		// apply the path operation, then the caller reopens and reverifies the
		// exact digest before accepting publication.
		if err := file.Close(); err != nil {
			return fmt.Errorf("close normalized bundle before immutable mode: %w", err)
		}
		if err := os.Chmod(path, 0o440); err != nil {
			return fmt.Errorf("make normalized bundle read-only: %w", err)
		}
		return nil
	}
	defer file.Close()
	if err := file.Chmod(0o440); err != nil {
		return fmt.Errorf("make normalized bundle read-only: %w", err)
	}
	return nil
}

// persistObject records the finalized bundle as a context.retained_object and
// binds it to the source version as a 'derived_reference' whose parent is the
// raw generation's own sealed extraction bundle object, exactly mirroring how
// filesystemBundleWriter binds a parser bundle to its source's original
// object. A raw generation without a sealed extraction bundle object fails
// closed rather than inserting a parentless derived registry.
func (w *filesystemNormalizedBundleWriter) persistObject(ctx context.Context, path string, digest []byte, byteLength int64) (uuid.UUID, error) {
	tx, err := w.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return uuid.Nil, fmt.Errorf("begin normalized bundle transaction: %w", err)
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
		return uuid.Nil, fmt.Errorf("persist normalized bundle object: %w", err)
	}
	var storedDigest []byte
	var storedLength int64
	if err := tx.QueryRow(ctx, `
		SELECT content_sha256, byte_length
		FROM context.retained_object WHERE id = $1::uuid`, objectID).Scan(&storedDigest, &storedLength); err != nil {
		return uuid.Nil, fmt.Errorf("verify normalized bundle object row: %w", err)
	}
	if storedLength != byteLength || !bytes.Equal(storedDigest, digest) {
		return uuid.Nil, errors.New("normalized bundle object row does not match finalized bytes")
	}

	sourceVersionID, err := uuid.Parse(w.input.SourceVersionRef)
	if err != nil {
		return uuid.Nil, fmt.Errorf("normalized bundle source version reference %q: %w", w.input.SourceVersionRef, err)
	}
	rawGenerationID, err := uuid.Parse(w.input.RawGenerationRef)
	if err != nil {
		return uuid.Nil, fmt.Errorf("normalized bundle raw generation reference %q: %w", w.input.RawGenerationRef, err)
	}
	var rawSourceVersionID uuid.UUID
	var parentObjectID pgtype.UUID
	if err := tx.QueryRow(ctx, `
		SELECT source_version_id, extraction_bundle_object_id FROM context.raw_generation
		WHERE id = $1::uuid AND status = 'sealed'`, rawGenerationID).Scan(&rawSourceVersionID, &parentObjectID); err != nil {
		return uuid.Nil, fmt.Errorf("resolve normalized bundle raw generation membership: %w", err)
	}
	if rawSourceVersionID != sourceVersionID {
		return uuid.Nil, errors.New("normalized bundle raw generation does not belong to this source version")
	}
	if !parentObjectID.Valid {
		return uuid.Nil, errors.New("normalized bundle raw generation has no extraction bundle object to derive from")
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO context.source_version_object
		    (source_version_id, object_id, object_role, parent_object_id, member_locator)
		VALUES ($1::uuid, $2::uuid, 'derived_reference', $3::uuid,
		        jsonb_build_object('kind', 'normalized_bundle', 'contract', $4::text))
		ON CONFLICT (source_version_id, object_id) DO NOTHING`,
		sourceVersionID, objectID, parentObjectID, normalizedBundleContractVersion); err != nil {
		return uuid.Nil, fmt.Errorf("bind normalized bundle to source version: %w", err)
	}
	var storedRole string
	var storedParent pgtype.UUID
	var storedLocator []byte
	if err := tx.QueryRow(ctx, `
		SELECT object_role, parent_object_id, member_locator
		FROM context.source_version_object
		WHERE source_version_id = $1::uuid AND object_id = $2::uuid`,
		sourceVersionID, objectID).Scan(&storedRole, &storedParent, &storedLocator); err != nil {
		return uuid.Nil, fmt.Errorf("verify normalized bundle source membership: %w", err)
	}
	var locator struct {
		Kind     string `json:"kind"`
		Contract string `json:"contract"`
	}
	if err := json.Unmarshal(storedLocator, &locator); err != nil {
		return uuid.Nil, fmt.Errorf("decode normalized bundle source membership: %w", err)
	}
	if storedRole != "derived_reference" || !storedParent.Valid || storedParent.Bytes != parentObjectID.Bytes ||
		locator.Kind != "normalized_bundle" || locator.Contract != normalizedBundleContractVersion {
		return uuid.Nil, errors.New("existing normalized bundle source membership conflicts with required lineage")
	}
	if err := tx.Commit(ctx); err != nil {
		return uuid.Nil, fmt.Errorf("commit normalized bundle object: %w", err)
	}
	rollback = false
	return objectID, nil
}

// NewFilesystemNormalizedBundleReaderFactory resolves a normalized bundle
// reference minted by the writer above back to a streaming reader. open
// resolves any non-inline retained object (typically runtimeapi.NewRetainedObjectOpener);
// it may be nil only when every normalized bundle this runtime ever reads is
// stored inline, matching NewRawPipelineRepository's ObjectOpener contract.
func NewFilesystemNormalizedBundleReaderFactory(db platformpostgres.DB, open platformpostgres.ObjectOpener) (platformpostgres.NormalizedBundleReaderFactory, error) {
	if db == nil {
		return nil, errors.New("normalized bundle reader: database is required")
	}
	return func(ctx context.Context, ref uiw.Ref) (platformpostgres.NormalizedBundleReader, error) {
		if strings.TrimSpace(string(ref)) == "" {
			return nil, errors.New("normalized bundle reference is required")
		}
		objectID, err := uuid.Parse(string(ref))
		if err != nil {
			return nil, fmt.Errorf("normalized bundle reference %q: %w", ref, err)
		}
		var storageClass, objectURI string
		var inline, expectedDigest []byte
		var expectedLength int64
		if err := db.QueryRow(ctx, `
			SELECT storage_class, object_uri, inline_bytes, content_sha256, byte_length
			FROM context.retained_object WHERE id = $1::uuid`, objectID).Scan(
			&storageClass, &objectURI, &inline, &expectedDigest, &expectedLength,
		); err != nil {
			return nil, fmt.Errorf("resolve normalized bundle object %q: %w", ref, err)
		}
		if len(expectedDigest) != sha256.Size || expectedLength < 0 {
			return nil, errors.New("normalized bundle object has invalid digest or byte-length metadata")
		}
		openObject := func(openCtx context.Context) (io.ReadCloser, error) {
			switch storageClass {
			case "inline":
				return io.NopCloser(bytes.NewReader(inline)), nil
			case "filesystem":
				path, pathErr := pathFromFileURI(objectURI)
				if pathErr != nil {
					return nil, fmt.Errorf("resolve normalized bundle filesystem object: %w", pathErr)
				}
				file, openErr := openRegularNonAliasFile(path)
				if openErr != nil {
					return nil, fmt.Errorf("open normalized bundle filesystem object: %w", openErr)
				}
				info, statErr := file.Stat()
				if statErr != nil {
					_ = file.Close()
					return nil, fmt.Errorf("inspect normalized bundle filesystem object: %w", statErr)
				}
				if info.Mode().Perm()&0o222 != 0 {
					_ = file.Close()
					return nil, errors.New("normalized bundle filesystem object is writable")
				}
				return file, nil
			default:
				if open == nil {
					return nil, fmt.Errorf("non-inline normalized bundle %q requires an object opener", objectURI)
				}
				opened, openErr := open(openCtx, objectURI)
				if openErr != nil {
					return nil, fmt.Errorf("open normalized bundle object: %w", openErr)
				}
				if opened == nil {
					return nil, errors.New("normalized bundle object opener returned nil")
				}
				return opened, nil
			}
		}

		// Verify the entire retained object before exposing even its header.
		// The streaming reader below verifies it again at the accounting
		// trailer, preventing a mutable external object from changing between
		// the preflight verification and actual consumption.
		preflight, err := openObject(ctx)
		if err != nil {
			return nil, err
		}
		if err := verifyNormalizedBundleContent(ctx, preflight, expectedDigest, expectedLength); err != nil {
			_ = preflight.Close()
			return nil, err
		}
		if err := preflight.Close(); err != nil {
			return nil, fmt.Errorf("close verified normalized bundle object: %w", err)
		}
		reader, err := openObject(ctx)
		if err != nil {
			return nil, err
		}
		integrity := newNormalizedIntegrityReader(reader, expectedDigest, expectedLength)
		decoder := json.NewDecoder(integrity)
		var line normalizedBundleLine
		if err := decoder.Decode(&line); err != nil {
			_ = integrity.Close()
			return nil, fmt.Errorf("decode normalized bundle header: %w", err)
		}
		if line.Kind != "header" || line.Contract != normalizedBundleContractVersion || line.Header == nil {
			_ = integrity.Close()
			return nil, errors.New("normalized bundle does not begin with a valid header line")
		}
		return &filesystemNormalizedBundleReader{closer: integrity, integrity: integrity, dec: decoder, header: *line.Header}, nil
	}, nil
}

func verifyNormalizedBundleContent(ctx context.Context, reader io.Reader, expectedDigest []byte, expectedLength int64) error {
	digest := sha256.New()
	actualLength, err := copyAcquisition(ctx, digest, reader)
	if err != nil {
		return fmt.Errorf("verify normalized bundle content: %w", err)
	}
	if actualLength != expectedLength || !bytes.Equal(digest.Sum(nil), expectedDigest) {
		return errors.New("normalized bundle digest or byte length does not match retained-object metadata")
	}
	return nil
}

type normalizedIntegrityReader struct {
	closer         io.ReadCloser
	digest         hash.Hash
	expectedDigest []byte
	expectedLength int64
	actualLength   int64
}

func newNormalizedIntegrityReader(source io.ReadCloser, expectedDigest []byte, expectedLength int64) *normalizedIntegrityReader {
	return &normalizedIntegrityReader{
		closer: source, digest: sha256.New(), expectedDigest: bytes.Clone(expectedDigest), expectedLength: expectedLength,
	}
}

func (r *normalizedIntegrityReader) Read(buffer []byte) (int, error) {
	count, err := r.closer.Read(buffer)
	if count > 0 {
		r.actualLength += int64(count)
		_, _ = r.digest.Write(buffer[:count])
	}
	return count, err
}

func (r *normalizedIntegrityReader) Verify() error {
	if r.actualLength != r.expectedLength || !bytes.Equal(r.digest.Sum(nil), r.expectedDigest) {
		return errors.New("normalized bundle changed during streaming read")
	}
	return nil
}

func (r *normalizedIntegrityReader) Close() error { return r.closer.Close() }

type filesystemNormalizedBundleReader struct {
	closer    io.Closer
	integrity *normalizedIntegrityReader
	dec       *json.Decoder
	header    normalize.BundleHeader
	records   uint64
	closed    bool
	done      bool
}

func (r *filesystemNormalizedBundleReader) Header() normalize.BundleHeader { return r.header }

func (r *filesystemNormalizedBundleReader) Next(ctx context.Context) (normalize.RecordEnvelope, error) {
	if r.done {
		return normalize.RecordEnvelope{}, io.EOF
	}
	if err := ctx.Err(); err != nil {
		return normalize.RecordEnvelope{}, err
	}
	var line normalizedBundleLine
	if err := r.dec.Decode(&line); err != nil {
		if errors.Is(err, io.EOF) {
			return normalize.RecordEnvelope{}, errors.New("normalized bundle ended before its accounting trailer")
		}
		return normalize.RecordEnvelope{}, fmt.Errorf("decode normalized bundle line: %w", err)
	}
	if line.Contract != normalizedBundleContractVersion {
		return normalize.RecordEnvelope{}, fmt.Errorf("normalized bundle line has unsupported contract %q", line.Contract)
	}
	switch line.Kind {
	case "record":
		if line.Record == nil {
			return normalize.RecordEnvelope{}, errors.New("normalized bundle record line is empty")
		}
		if line.Record.RecordOrdinal != r.records {
			return normalize.RecordEnvelope{}, fmt.Errorf(
				"normalized bundle record ordinal %d, expected %d", line.Record.RecordOrdinal, r.records,
			)
		}
		r.records++
		return *line.Record, nil
	case "accounting":
		if line.Accounting == nil {
			return normalize.RecordEnvelope{}, errors.New("normalized bundle accounting line is empty")
		}
		if r.records == 0 || line.Accounting.Emitted != r.records {
			return normalize.RecordEnvelope{}, fmt.Errorf(
				"normalized bundle trailer emitted %d does not match %d streamed records", line.Accounting.Emitted, r.records,
			)
		}
		var trailing json.RawMessage
		if err := r.dec.Decode(&trailing); !errors.Is(err, io.EOF) {
			if err == nil {
				return normalize.RecordEnvelope{}, errors.New("normalized bundle has content after its accounting trailer")
			}
			return normalize.RecordEnvelope{}, fmt.Errorf("normalized bundle has invalid trailing content: %w", err)
		}
		if err := r.integrity.Verify(); err != nil {
			return normalize.RecordEnvelope{}, err
		}
		r.done = true
		return normalize.RecordEnvelope{}, io.EOF
	default:
		return normalize.RecordEnvelope{}, fmt.Errorf("normalized bundle line has unsupported kind %q", line.Kind)
	}
}

func (r *filesystemNormalizedBundleReader) Close() error {
	if r.closed {
		return nil
	}
	r.closed = true
	return r.closer.Close()
}

var _ platformpostgres.NormalizedBundleReader = (*filesystemNormalizedBundleReader)(nil)

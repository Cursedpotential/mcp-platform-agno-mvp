package internal

// custody.go — forensic hashing for the SBV forensic fork.
//
// This file adds the H1/H2/H3 chain-of-custody hashes that the Python custody
// gate (server/evidence/custody.py + server/evidence/tools/sbv_sms.py) records
// into the append-only `evidence` schema. SBV holds NO database credentials for
// that Postgres store: it only COMPUTES these hashes over the RAW source bytes
// and exposes them over its REST API. The Python side re-computes H1 independently
// and cross-checks, then writes the evidence_hash / custody_event rows.
//
// ORDERING CONTRACT (owner-verified — hashing MUST precede normalization):
//
//	H1 (raw file)  ->  H2 (raw per-record)  ->  H3 (chain)  ->  (only then) normalize
//
// All three hashes are computed over the ORIGINAL source bytes, BEFORE any field
// decoding / transcoding / NormalizedRecord mapping, so they prove the source
// content is unaltered. See CUSTODY.md for the full, auditable specification.

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"time"
)

// Canonicalization version tags — carried alongside every hash so a future
// change to the byte layout is detectable and auditable. MUST stay in lockstep
// with the strings the Python side stores (server/evidence/custody.py):
//
//	h1-rawbytes-v1   : H1 == sha256(raw file bytes)          — matches custody.py _sha256_file
//	h2-rawelement-v1 : H2 == sha256(raw XML element bytes)   — pre-normalization source record
//	h3-chain-v1      : H3 == left-fold sha256 chain over H2s — per import batch
const (
	FileHashCanonVersion   = "h1-rawbytes-v1"
	RecordHashCanonVersion = "h2-rawelement-v1"
	ChainCanonVersion      = "h3-chain-v1"
)

// HashFileH1 computes the H1 file-level custody hash: the lowercase hex SHA-256
// of the RAW file bytes, streamed in 1 MiB chunks. This MUST be byte-for-byte
// equal to server/evidence/custody.py::_sha256_file for the same file (both are
// a plain SHA-256 over the unmodified bytes — no reformatting, no canonicalization).
func HashFileH1(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	buf := make([]byte, 1024*1024)
	if _, err := io.CopyBuffer(h, f, buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// HashBytesSHA256 is the shared primitive: lowercase hex SHA-256 of raw bytes.
func HashBytesSHA256(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

// HashRecordH2 computes the H2 per-record custody hash over the RAW SOURCE
// element bytes — the exact bytes of a single <sms .../>, <mms>...</mms>, or
// <call .../> element as they appear in the uploaded XML, from the opening '<'
// through the closing '>' inclusive, with surrounding inter-element whitespace
// excluded. It is hashed BEFORE any parsing/normalization so it proves the
// original record content is unaltered. (h2-rawelement-v1)
//
// Determinism: identical raw element bytes always yield the identical hash;
// any change to the source bytes — including whitespace or formatting our
// normalizer would later strip — changes the hash. That is the point.
func HashRecordH2(rawElement []byte) string {
	return HashBytesSHA256(rawElement)
}

// ChainH3 computes the H3 batch chain digest over the ordered per-record H2
// hashes, in source (parse) order. It is a left fold:
//
//	chain_0 = prevChain                                  (prevChain == "" for a fresh batch)
//	chain_i = hex(sha256( chain_{i-1} + "\n" + H2_i ))
//	H3      = chain_n
//
// The "\n" separator and the running-hex-then-append construction are fixed by
// h3-chain-v1. prevChain lets successive import batches be chained end-to-end
// if ever desired; pass "" for an independent per-import chain.
func ChainH3(orderedH2s []string, prevChain string) string {
	chain := prevChain
	for _, h2 := range orderedH2s {
		chain = HashBytesSHA256([]byte(chain + "\n" + h2))
	}
	return chain
}

// trimLeadingXMLSpace drops leading XML insignificant whitespace (space, tab,
// CR, LF) so a captured raw span begins exactly at the element's '<'. There is
// never trailing whitespace to trim: the capture ends at the element's '>'.
func trimLeadingXMLSpace(b []byte) []byte {
	i := 0
	for i < len(b) {
		switch b[i] {
		case ' ', '\t', '\r', '\n':
			i++
		default:
			return b[i:]
		}
	}
	return b[i:]
}

// rawCaptureReader wraps an io.Reader and retains a sliding buffer of the bytes
// the xml.Decoder pulls, so the RAW byte span of each element (identified by
// absolute input offset via xml.Decoder.InputOffset) can be extracted AFTER the
// decoder has consumed it. Memory stays bounded: discardBefore drops buffered
// bytes that precede a committed offset, so at most one element (plus the
// decoder read-ahead) is retained at a time — the same streaming footprint the
// decoder already has.
type rawCaptureReader struct {
	src  io.Reader
	buf  []byte
	base int64 // absolute input offset of buf[0]
	end  int64 // absolute input offset one past buf[len(buf)-1] == bytes read from src
}

func newRawCaptureReader(src io.Reader) *rawCaptureReader {
	return &rawCaptureReader{src: src}
}

func (c *rawCaptureReader) Read(p []byte) (int, error) {
	n, err := c.src.Read(p)
	if n > 0 {
		c.buf = append(c.buf, p[:n]...)
		c.end += int64(n)
	}
	return n, err
}

// slice returns a COPY of the raw bytes in absolute offsets [start, stop).
// Returns nil if the range is not fully buffered (should not happen given the
// decoder consumes sequentially and we only discard already-processed prefixes).
func (c *rawCaptureReader) slice(start, stop int64) []byte {
	if start < c.base || stop > c.end || start > stop {
		return nil
	}
	out := make([]byte, stop-start)
	copy(out, c.buf[start-c.base:stop-c.base])
	return out
}

// discardBefore drops buffered bytes preceding absolute offset off.
func (c *rawCaptureReader) discardBefore(off int64) {
	if off <= c.base {
		return
	}
	if off >= c.end {
		c.buf = c.buf[:0]
		c.base = c.end
		return
	}
	n := off - c.base
	c.buf = append(c.buf[:0], c.buf[n:]...)
	c.base = off
}

// -----------------------------------------------------------------------------
// imports table — one row per upload batch, holding H1 (file_hash) + H3
// (chain_hash) + record_count. Exposed over GET /api/hashes/{importID}.
// -----------------------------------------------------------------------------

// ImportRecord is the persisted + API-serialized custody summary for one import.
type ImportRecord struct {
	ID              int64  `json:"import_id"`
	FileHash        string `json:"file_hash"`  // H1 (raw file sha256 hex)
	ChainHash       string `json:"chain_hash"` // H3 (chain digest over ordered H2s)
	RecordCount     int    `json:"record_count"`
	ImportedAt      int64  `json:"imported_at"` // unix seconds
	FileHashCanon   string `json:"file_hash_canon"`
	RecordHashCanon string `json:"record_hash_canon"`
	ChainCanon      string `json:"chain_canon"`
}

// RecordImport inserts one custody summary row and returns its id.
func RecordImport(userDB *sql.DB, fileHash string, recordCount int, chainHash string) (int64, error) {
	res, err := userDB.Exec(
		`INSERT INTO imports (file_hash, record_count, chain_hash, canon_version, imported_at)
		 VALUES (?, ?, ?, ?, ?)`,
		fileHash, recordCount, chainHash, ChainCanonVersion, time.Now().Unix(),
	)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func scanImport(row *sql.Row) (*ImportRecord, error) {
	var r ImportRecord
	err := row.Scan(&r.ID, &r.FileHash, &r.RecordCount, &r.ChainHash, &r.ImportedAt)
	if err != nil {
		return nil, err
	}
	r.FileHashCanon = FileHashCanonVersion
	r.RecordHashCanon = RecordHashCanonVersion
	r.ChainCanon = ChainCanonVersion
	return &r, nil
}

// GetImport fetches one import row by id.
func GetImport(userDB *sql.DB, id int64) (*ImportRecord, error) {
	return scanImport(userDB.QueryRow(
		`SELECT id, file_hash, record_count, chain_hash, imported_at FROM imports WHERE id = ?`, id))
}

// GetLatestImport fetches the most recent import row (highest id). Because SBV
// processes one upload at a time, this is the batch a just-completed upload
// produced — the anchor the Python cross-check reads via GET /api/hashes/latest.
func GetLatestImport(userDB *sql.DB) (*ImportRecord, error) {
	return scanImport(userDB.QueryRow(
		`SELECT id, file_hash, record_count, chain_hash, imported_at FROM imports ORDER BY id DESC LIMIT 1`))
}

// ensureCustodyColumns is an idempotent migration: it adds the H2 content_hash
// column to an existing messages table and creates the imports table. Fresh DBs
// get content_hash from the CREATE TABLE definition; this backfills upgraded DBs.
func ensureCustodyColumns(db *sql.DB) error {
	has, err := columnExists(db, "messages", "content_hash")
	if err != nil {
		return err
	}
	if !has {
		if _, err := db.Exec(`ALTER TABLE messages ADD COLUMN content_hash TEXT`); err != nil {
			return fmt.Errorf("add content_hash column: %w", err)
		}
	}
	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS imports (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		file_hash TEXT NOT NULL,
		record_count INTEGER NOT NULL,
		chain_hash TEXT NOT NULL,
		canon_version TEXT NOT NULL DEFAULT 'h3-chain-v1',
		imported_at INTEGER NOT NULL
	)`)
	return err
}

func columnExists(db *sql.DB, table, col string) (bool, error) {
	// #nosec G202 — table is an internal constant, never user input.
	rows, err := db.Query(fmt.Sprintf("PRAGMA table_info(%s)", table))
	if err != nil {
		return false, err
	}
	defer rows.Close()
	for rows.Next() {
		var (
			cid, notnull, pk int
			name, ctype      string
			dflt             sql.NullString
		)
		if err := rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err != nil {
			return false, err
		}
		if name == col {
			return true, nil
		}
	}
	return false, rows.Err()
}

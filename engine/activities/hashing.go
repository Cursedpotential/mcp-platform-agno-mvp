// Package activities implements atomic Activity bodies for the universal
// import workflow. This file owns hashing only: it never parses, normalizes,
// reconciles, verifies, promotes, or decides retries.
package activities

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"io"

	"github.com/lowcarbdev/sbv/pkg/custodyhash"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// HashKind values match contracts/import/v1/schemas/hash-receipt.schema.json.
type HashKind string

const (
	HashKindH1Source                   HashKind = "h1_source"
	HashKindRawRecordDigest            HashKind = "raw_record_digest"
	HashKindH3RawGeneration            HashKind = "h3_raw_generation"
	HashKindNormalizedRecordDigest     HashKind = "normalized_record_digest"
	HashKindNormalizedGenerationDigest HashKind = "normalized_generation_manifest_digest"

	// Universal-import raw rows include otherwise-unparsed and envelope spans,
	// so their membership tag is distinct from legacy SBV logical-record H3.
	// Normalized hashes deliberately do not reuse the custody H2/H3 labels.
	CanonRawSpan                  = "h2-rawspan-v1"
	CanonRawGeneration            = "h3-chain-platform-rawall-genesisempty-v1"
	CanonNormalizedRecord         = "normalized-record-postgresql18-jsonb-text-utf8-sha256-v1"
	CanonNormalizedGeneration     = "normalized-generation-ordered-digests-lengthframed-sha256-v1"
	CanonRawRecordManifest        = "raw-record-digest-manifest-v1"
	CanonNormalizedRecordManifest = "normalized-record-digest-manifest-v1"
)

// ByteMember is one persisted raw or normalized record resolved outside
// Temporal history. Bytes must be the exact representation named by Canon.
type ByteMember struct {
	SubjectRef uiw.Ref
	Ordinal    int64
	Canon      string
	Reader     io.ReadCloser
}

// DigestMember is one already-computed digest in deterministic source order.
type DigestMember struct {
	SubjectRef uiw.Ref
	Ordinal    int64
	Digest     string
	Canon      string
}

// ByteMemberStream and DigestMemberStream are deliberately streaming. A
// generation is never materialized as a record or digest slice in an Activity.
type ByteMemberStream interface {
	Next(context.Context) (ByteMember, error)
	Close() error
}

type DigestMemberStream interface {
	Next(context.Context) (DigestMember, error)
	Close() error
}

// BatchSpec is the idempotency coordinate supplied when beginning a durable
// hash result. Repository implementations key it by RequestID+Stage+SubjectRef.
type BatchSpec struct {
	RequestID  string
	Attempt    int32
	Stage      stagegraph.StageID
	Kind       HashKind
	SubjectRef uiw.Ref
}

// HashMember is appended as soon as it is computed or consumed. This keeps
// even very large generations bounded in memory.
type HashMember struct {
	SubjectRef uiw.Ref
	Ordinal    int64
	Digest     string
	Canon      string
}

// HashSummary seals a batch. Digest is populated for H1 and generation-level
// results; member batches are represented by their durable manifest reference.
type HashSummary struct {
	Digest       string
	Canon        string
	Construction string
	MemberCount  int64
}

// HashBatchWriter persists ordered membership incrementally. Commit must
// atomically seal the hash batch and its Activity receipt and return compact
// references for Temporal. Abort must leave no publishable partial result.
type HashBatchWriter interface {
	Append(context.Context, HashMember) error
	Commit(context.Context, HashSummary) (resultRef uiw.Ref, receiptRef uiw.Ref, err error)
	Abort(context.Context) error
}

// HashRepository is the storage boundary used by the five hash Activities.
// The PostgreSQL implementation owns queries and transactions; this package
// owns only byte/digest computation and fail-closed validation.
type HashRepository interface {
	OpenOriginal(context.Context, uiw.Ref) (io.ReadCloser, error)
	OpenRawRecords(context.Context, uiw.Ref) (ByteMemberStream, error)
	OpenNormalizedRecords(context.Context, uiw.Ref) (ByteMemberStream, error)
	OpenHashMembers(context.Context, uiw.Ref) (DigestMemberStream, error)
	BeginHashBatch(context.Context, BatchSpec) (HashBatchWriter, error)
}

// Progress is compact heartbeat data; it never contains source content.
type Progress struct {
	Stage           stagegraph.StageID
	MembersComplete int64
	BytesComplete   int64
}

type Heartbeat func(context.Context, Progress)

// Attempt resolves the current durable Activity attempt. Production binds it
// to Temporal's activity.Info; direct unit callers fall back to attempt 1.
type Attempt func(context.Context) int32

// HashActivities implements the five separately registered Activity bodies.
type HashActivities struct {
	Repository HashRepository
	Heartbeat  Heartbeat
	Attempt    Attempt
}

func (a HashActivities) heartbeat(ctx context.Context, progress Progress) {
	if a.Heartbeat != nil {
		a.Heartbeat(ctx, progress)
	}
}

func (a HashActivities) validate() error {
	if a.Repository == nil {
		return errors.New("hash activities: repository is required")
	}
	return nil
}

func (a HashActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

// HashSource computes raw-source H1 over the retained original bytes.
func (a HashActivities) HashSource(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	const refName = "original"
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	originalRef, err := requiredRef(req, refName)
	if err != nil {
		return uiw.StageResult{}, err
	}
	reader, err := a.Repository.OpenOriginal(ctx, originalRef)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("open original %q: %w", originalRef, err)
	}
	defer reader.Close()

	writer, err := a.Repository.BeginHashBatch(ctx, BatchSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), Stage: stagegraph.HashSource,
		Kind: HashKindH1Source, SubjectRef: req.SourceVersionRef,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("begin H1 batch: %w", err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = writer.Abort(context.WithoutCancel(ctx))
		}
	}()

	progress := &progressReader{ctx: ctx, reader: reader, stage: stagegraph.HashSource, heartbeat: a.heartbeat}
	digest, err := custodyhash.HashReaderH1(progress)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("compute H1: %w", err)
	}
	member := HashMember{SubjectRef: req.SourceVersionRef, Ordinal: 0, Digest: digest, Canon: custodyhash.CanonH1}
	if err := writer.Append(ctx, member); err != nil {
		return uiw.StageResult{}, fmt.Errorf("persist H1 member: %w", err)
	}
	resultRef, receiptRef, err := writer.Commit(ctx, HashSummary{
		Digest: digest, Canon: custodyhash.CanonH1, Construction: custodyhash.CanonH1, MemberCount: 1,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("commit H1: %w", err)
	}
	committed = true
	return success(stagegraph.HashSource, resultRef, receiptRef), nil
}

// HashRawRecords computes raw-custody H2 for each exact logical record/span.
func (a HashActivities) HashRawRecords(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	return a.hashRecordBytes(ctx, req, recordHashConfig{
		stage: stagegraph.HashRawRecords, refName: "raw_generation",
		kind: HashKindRawRecordDigest, manifestCanon: CanonRawRecordManifest, open: a.Repository.OpenRawRecords,
		canon: func(member ByteMember) (string, error) {
			if member.Canon != custodyhash.CanonH2 && member.Canon != custodyhash.CanonH2Record && member.Canon != CanonRawSpan {
				return "", fmt.Errorf("raw member %q has unsupported H2 canon %q", member.SubjectRef, member.Canon)
			}
			return member.Canon, nil
		},
	})
}

// HashNormalizedRecords computes distinct normalized-record digests. They are
// reproducibility hashes and must never be labelled custody H2.
func (a HashActivities) HashNormalizedRecords(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	return a.hashRecordBytes(ctx, req, recordHashConfig{
		stage: stagegraph.HashNormalizedRecords, refName: "normalized_generation",
		kind: HashKindNormalizedRecordDigest, manifestCanon: CanonNormalizedRecordManifest, open: a.Repository.OpenNormalizedRecords,
		canon: func(ByteMember) (string, error) { return CanonNormalizedRecord, nil },
	})
}

type recordHashConfig struct {
	stage         stagegraph.StageID
	refName       string
	kind          HashKind
	manifestCanon string
	open          func(context.Context, uiw.Ref) (ByteMemberStream, error)
	canon         func(ByteMember) (string, error)
}

func (a HashActivities) hashRecordBytes(ctx context.Context, req uiw.StageRequest, cfg recordHashConfig) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	generationRef, err := requiredRef(req, cfg.refName)
	if err != nil {
		return uiw.StageResult{}, err
	}
	stream, err := cfg.open(ctx, generationRef)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("open %s members: %w", cfg.stage, err)
	}
	defer stream.Close()
	writer, err := a.Repository.BeginHashBatch(ctx, BatchSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), Stage: cfg.stage, Kind: cfg.kind, SubjectRef: generationRef,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("begin %s batch: %w", cfg.stage, err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = writer.Abort(context.WithoutCancel(ctx))
		}
	}()

	var count int64
	for {
		if err := ctx.Err(); err != nil {
			return uiw.StageResult{}, err
		}
		member, nextErr := stream.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return uiw.StageResult{}, fmt.Errorf("read %s member: %w", cfg.stage, nextErr)
		}
		if member.Reader == nil || member.SubjectRef == "" {
			return uiw.StageResult{}, fmt.Errorf("%s member %d lacks reader or subject reference", cfg.stage, count)
		}
		if member.Ordinal != count {
			_ = member.Reader.Close()
			return uiw.StageResult{}, fmt.Errorf("%s member ordinal %d, want %d", cfg.stage, member.Ordinal, count)
		}
		canon, canonErr := cfg.canon(member)
		if canonErr != nil {
			_ = member.Reader.Close()
			return uiw.StageResult{}, canonErr
		}
		progress := &progressReader{ctx: ctx, reader: member.Reader, stage: cfg.stage, members: count, heartbeat: a.heartbeat}
		digest, hashErr := custodyhash.HashReaderH1(progress)
		closeErr := member.Reader.Close()
		if hashErr != nil {
			return uiw.StageResult{}, fmt.Errorf("hash %s member %q: %w", cfg.stage, member.SubjectRef, hashErr)
		}
		if closeErr != nil {
			return uiw.StageResult{}, fmt.Errorf("close %s member %q: %w", cfg.stage, member.SubjectRef, closeErr)
		}
		if err := writer.Append(ctx, HashMember{SubjectRef: member.SubjectRef, Ordinal: count, Digest: digest, Canon: canon}); err != nil {
			return uiw.StageResult{}, fmt.Errorf("persist %s member %q: %w", cfg.stage, member.SubjectRef, err)
		}
		count++
		a.heartbeat(ctx, Progress{Stage: cfg.stage, MembersComplete: count, BytesComplete: progress.total})
	}
	if count == 0 {
		return uiw.StageResult{}, fmt.Errorf("%s refuses to seal an empty member manifest", cfg.stage)
	}
	resultRef, receiptRef, err := writer.Commit(ctx, HashSummary{Canon: cfg.manifestCanon, MemberCount: count})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("commit %s: %w", cfg.stage, err)
	}
	committed = true
	return success(cfg.stage, resultRef, receiptRef), nil
}

// HashRawGeneration computes raw-custody H3 over the ordered H2 manifest.
func (a HashActivities) HashRawGeneration(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.hashDigestGeneration(ctx, req, generationHashConfig{
		stage: stagegraph.HashRawGeneration, refName: "raw_hash_manifest", subjectRefName: "raw_generation",
		kind: HashKindH3RawGeneration, canon: CanonRawGeneration,
		acceptCanon: func(canon string) bool {
			return canon == custodyhash.CanonH2 || canon == custodyhash.CanonH2Record || canon == CanonRawSpan
		},
		newAccumulator: func() digestAccumulator { return &rawH3Accumulator{chain: custodyhash.NewChain("")} },
	})
}

// HashNormalizedGeneration computes the ordered normalized-generation manifest
// digest. Its construction and label are deliberately distinct from H3.
func (a HashActivities) HashNormalizedGeneration(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	return a.hashDigestGeneration(ctx, req, generationHashConfig{
		stage: stagegraph.HashNormalizedGeneration, refName: "normalized_record_digests", subjectRefName: "normalized_generation",
		kind: HashKindNormalizedGenerationDigest, canon: CanonNormalizedGeneration,
		acceptCanon:    func(canon string) bool { return canon == CanonNormalizedRecord },
		newAccumulator: func() digestAccumulator { return newNormalizedAccumulator() },
	})
}

type generationHashConfig struct {
	stage          stagegraph.StageID
	refName        string
	subjectRefName string
	kind           HashKind
	canon          string
	acceptCanon    func(string) bool
	newAccumulator func() digestAccumulator
}

func (a HashActivities) hashDigestGeneration(ctx context.Context, req uiw.StageRequest, cfg generationHashConfig) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	manifestRef, err := requiredRef(req, cfg.refName)
	if err != nil {
		return uiw.StageResult{}, err
	}
	subjectRef, err := requiredRef(req, cfg.subjectRefName)
	if err != nil {
		return uiw.StageResult{}, err
	}
	stream, err := a.Repository.OpenHashMembers(ctx, manifestRef)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("open %s digest members: %w", cfg.stage, err)
	}
	defer stream.Close()
	writer, err := a.Repository.BeginHashBatch(ctx, BatchSpec{
		RequestID: req.RequestID, Attempt: a.attempt(ctx), Stage: cfg.stage, Kind: cfg.kind, SubjectRef: subjectRef,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("begin %s batch: %w", cfg.stage, err)
	}
	committed := false
	defer func() {
		if !committed {
			_ = writer.Abort(context.WithoutCancel(ctx))
		}
	}()

	acc := cfg.newAccumulator()
	var count int64
	for {
		if err := ctx.Err(); err != nil {
			return uiw.StageResult{}, err
		}
		member, nextErr := stream.Next(ctx)
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			return uiw.StageResult{}, fmt.Errorf("read %s digest member: %w", cfg.stage, nextErr)
		}
		if member.Ordinal != count {
			return uiw.StageResult{}, fmt.Errorf("%s digest ordinal %d, want %d", cfg.stage, member.Ordinal, count)
		}
		if !cfg.acceptCanon(member.Canon) {
			return uiw.StageResult{}, fmt.Errorf("%s member %q has incompatible canon %q", cfg.stage, member.SubjectRef, member.Canon)
		}
		if err := validateDigest(member.Digest); err != nil {
			return uiw.StageResult{}, fmt.Errorf("%s member %q: %w", cfg.stage, member.SubjectRef, err)
		}
		if err := acc.Add(member); err != nil {
			return uiw.StageResult{}, fmt.Errorf("fold %s member %q: %w", cfg.stage, member.SubjectRef, err)
		}
		if err := writer.Append(ctx, HashMember{SubjectRef: member.SubjectRef, Ordinal: count, Digest: member.Digest, Canon: member.Canon}); err != nil {
			return uiw.StageResult{}, fmt.Errorf("persist %s membership %q: %w", cfg.stage, member.SubjectRef, err)
		}
		count++
		a.heartbeat(ctx, Progress{Stage: cfg.stage, MembersComplete: count})
	}
	if count == 0 {
		return uiw.StageResult{}, fmt.Errorf("%s refuses to seal an empty ordered membership", cfg.stage)
	}
	digest := acc.Sum()
	resultRef, receiptRef, err := writer.Commit(ctx, HashSummary{
		Digest: digest, Canon: cfg.canon, Construction: cfg.canon, MemberCount: count,
	})
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("commit %s: %w", cfg.stage, err)
	}
	committed = true
	return success(cfg.stage, resultRef, receiptRef), nil
}

type digestAccumulator interface {
	Add(DigestMember) error
	Sum() string
}

type rawH3Accumulator struct{ chain *custodyhash.Chain }

func (a *rawH3Accumulator) Add(member DigestMember) error {
	a.chain.Add(member.Digest)
	return nil
}

func (a *rawH3Accumulator) Sum() string { return a.chain.Value() }

type normalizedHash struct {
	hashState interface {
		io.Writer
		Sum([]byte) []byte
	}
}

func newNormalizedAccumulator() digestAccumulator {
	h := sha256.New()
	_, _ = io.WriteString(h, CanonNormalizedGeneration)
	_, _ = h.Write([]byte{0})
	return &normalizedHash{hashState: h}
}

func (a *normalizedHash) Add(member DigestMember) error {
	digestBytes, err := hex.DecodeString(member.Digest)
	if err != nil {
		return err
	}
	var frame [8]byte
	binary.BigEndian.PutUint64(frame[:], uint64(member.Ordinal))
	if _, err := a.hashState.Write(frame[:]); err != nil {
		return err
	}
	if _, err := a.hashState.Write(digestBytes); err != nil {
		return err
	}
	return nil
}

func (a *normalizedHash) Sum() string {
	return hex.EncodeToString(a.hashState.Sum(nil))
}

func requiredRef(req uiw.StageRequest, name string) (uiw.Ref, error) {
	ref := req.Refs[name]
	if ref == "" {
		return "", fmt.Errorf("%s requires non-empty %q reference", req.RequestID, name)
	}
	return ref, nil
}

func success(stage stagegraph.StageID, resultRef, receiptRef uiw.Ref) uiw.StageResult {
	return uiw.StageResult{Stage: stage, Status: uiw.StatusSuccess, Ref: resultRef, ReceiptRef: receiptRef}
}

func validateDigest(digest string) error {
	if len(digest) != sha256.Size*2 {
		return fmt.Errorf("digest must be %d lowercase hexadecimal characters", sha256.Size*2)
	}
	decoded, err := hex.DecodeString(digest)
	if err != nil || hex.EncodeToString(decoded) != digest {
		return errors.New("digest must be lowercase hexadecimal SHA-256")
	}
	return nil
}

type progressReader struct {
	ctx       context.Context
	reader    io.Reader
	stage     stagegraph.StageID
	members   int64
	total     int64
	heartbeat Heartbeat
}

func (r *progressReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	n, err := r.reader.Read(p)
	r.total += int64(n)
	if n > 0 && r.heartbeat != nil {
		r.heartbeat(r.ctx, Progress{Stage: r.stage, MembersComplete: r.members, BytesComplete: r.total})
	}
	return n, err
}

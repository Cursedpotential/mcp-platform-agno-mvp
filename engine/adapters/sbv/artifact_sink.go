package sbv

// Byline: Codex · GPT-5.6 · 2026-08-29.

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/lowcarbdev/sbv/pkg/parseonly"
)

// FilesystemArtifactSink is a caller-constructed, source-scoped write-once
// store for exact parse outputs. It does not create its configured root,
// calculate custody H1/H2/H3, or persist canonical platform records.
type FilesystemArtifactSink struct {
	root        string
	registrar   parseonly.ArtifactRegistrar
	lockPath    string
	lockToken   string
	lockOwner   string
	operationMu sync.RWMutex
	closed      bool
}

// NewFilesystemArtifactSink binds a pre-provisioned protected root. Requiring
// the root to exist makes missing deployment storage fail closed.
func NewFilesystemArtifactSink(root string, registrar parseonly.ArtifactRegistrar) (*FilesystemArtifactSink, error) {
	if registrar == nil {
		return nil, errors.New("SBV artifact registrar is required")
	}
	trimmed := strings.TrimSpace(root)
	if trimmed == "" {
		return nil, errors.New("SBV immutable artifact root is required")
	}
	abs, err := filepath.Abs(trimmed)
	if err != nil {
		return nil, fmt.Errorf("resolve SBV immutable artifact root: %w", err)
	}
	resolved, err := filepath.EvalSymlinks(abs)
	if err != nil {
		return nil, fmt.Errorf("resolve SBV immutable artifact root links: %w", err)
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return nil, fmt.Errorf("stat SBV immutable artifact root: %w", err)
	}
	if !info.IsDir() {
		return nil, errors.New("SBV immutable artifact root is not a directory")
	}
	sink := &FilesystemArtifactSink{root: resolved, registrar: registrar}
	if err := sink.acquireRuntimeLock(); err != nil {
		return nil, err
	}
	if err := sink.recoverInterruptedAttempts(); err != nil {
		_ = sink.Close()
		return nil, err
	}
	return sink, nil
}

// Close releases the cross-process runtime lock by moving it into an
// append-only released-lock archive. A crash leaves the active lock in place,
// forcing an operator to verify the dead owner before moving it; no second
// process can guess that inflight attempts are stale.
func (s *FilesystemArtifactSink) Close() error {
	if s == nil {
		return nil
	}
	s.operationMu.Lock()
	defer s.operationMu.Unlock()
	if s.closed {
		return nil
	}
	lockBytes, err := os.ReadFile(s.lockPath)
	if err != nil {
		return fmt.Errorf("read SBV runtime lock before release: %w", err)
	}
	if string(lockBytes) != s.lockOwner {
		return errors.New("SBV runtime lock ownership changed; refusing release")
	}
	releasedDir := filepath.Join(s.root, "locks", "released", s.lockToken)
	if err := os.MkdirAll(filepath.Dir(releasedDir), 0700); err != nil {
		return fmt.Errorf("create SBV released-lock archive: %w", err)
	}
	if err := os.Mkdir(releasedDir, 0700); err != nil {
		return fmt.Errorf("reserve SBV released-lock archive: %w", err)
	}
	if err := os.Rename(s.lockPath, filepath.Join(releasedDir, "runtime.lock")); err != nil {
		return fmt.Errorf("archive released SBV runtime lock: %w", err)
	}
	s.closed = true
	return nil
}

func (s *FilesystemArtifactSink) acquireRuntimeLock() error {
	token, err := randomID()
	if err != nil {
		return err
	}
	lockPath := filepath.Join(s.root, ".sbv-artifact-runtime.lock")
	lock, err := os.OpenFile(lockPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0400)
	if errors.Is(err, os.ErrExist) {
		return errors.New("SBV artifact runtime lock is held; verify the recorded owner is dead and archive the lock before restart")
	}
	if err != nil {
		return fmt.Errorf("acquire SBV artifact runtime lock: %w", err)
	}
	hostname, _ := os.Hostname()
	owner := fmt.Sprintf("token=%s\npid=%d\nhostname=%s\nstarted_at=%s\n", token, os.Getpid(), hostname, time.Now().UTC().Format(time.RFC3339Nano))
	if _, err := io.WriteString(lock, owner); err != nil {
		_ = lock.Close()
		return fmt.Errorf("write SBV artifact runtime lock: %w", err)
	}
	if err := lock.Sync(); err != nil {
		_ = lock.Close()
		return fmt.Errorf("sync SBV artifact runtime lock: %w", err)
	}
	if err := lock.Close(); err != nil {
		return fmt.Errorf("close SBV artifact runtime lock: %w", err)
	}
	s.lockPath = lockPath
	s.lockToken = token
	s.lockOwner = owner
	return nil
}

func (s *FilesystemArtifactSink) ArtifactDir(ctx context.Context, sourceAssociation, attemptID string) (string, error) {
	release, err := s.beginMutation(ctx, sourceAssociation, attemptID)
	if err != nil {
		return "", err
	}
	defer release()
	return s.artifactDir(sourceAssociation, attemptID)
}

func (s *FilesystemArtifactSink) artifactDir(sourceAssociation, attemptID string) (string, error) {
	dir := filepath.Join(s.attemptRoot(sourceAssociation, attemptID), "decoder")
	if err := os.MkdirAll(dir, 0700); err != nil {
		return "", fmt.Errorf("create SBV attempt staging: %w", err)
	}
	return dir, nil
}

func (s *FilesystemArtifactSink) Store(ctx context.Context, artifact parseonly.Artifact) (parseonly.ArtifactLocator, error) {
	release, err := s.beginMutation(ctx, artifact.SourceAssociation, artifact.AttemptID)
	if err != nil {
		return parseonly.ArtifactLocator{}, err
	}
	defer release()
	if strings.TrimSpace(artifact.ParentSourcePos) == "" {
		return parseonly.ArtifactLocator{}, errors.New("SBV immutable artifact requires a parent-record association")
	}
	switch artifact.Kind {
	case parseonly.ArtifactRawRecord, parseonly.ArtifactAttachment:
	default:
		return parseonly.ArtifactLocator{}, fmt.Errorf("unsupported SBV artifact kind %q", artifact.Kind)
	}
	if artifact.ByteCount < 0 {
		return parseonly.ArtifactLocator{}, errors.New("SBV immutable artifact byte count cannot be negative")
	}
	stage, err := s.artifactDir(artifact.SourceAssociation, artifact.AttemptID)
	if err != nil {
		return parseonly.ArtifactLocator{}, err
	}
	if err := requirePathWithin(stage, artifact.StagedPath); err != nil {
		return parseonly.ArtifactLocator{}, err
	}
	digest, size, err := digestFile(ctx, artifact.StagedPath)
	if err != nil {
		return parseonly.ArtifactLocator{}, err
	}
	if size != artifact.ByteCount {
		return parseonly.ArtifactLocator{}, fmt.Errorf("SBV immutable artifact size %d does not match declared %d", size, artifact.ByteCount)
	}
	// Digest is deliberately excluded from logical identity. Different bytes at
	// the same source position are a conflict, not another object version.
	target := filepath.Join(s.root, "objects", sha256Text(artifact.SourceAssociation), string(artifact.Kind), sha256Text(artifact.ParentSourcePos), fmt.Sprintf("%06d.bin", artifact.AttachmentOrdinal))
	newObject, err := s.publish(ctx, artifact, target, size, digest)
	if err != nil {
		return parseonly.ArtifactLocator{}, err
	}
	objectURI := fileURI(target)
	locator, err := s.registrar.RegisterArtifact(ctx, parseonly.ArtifactRegistration{Artifact: artifact, ObjectURI: objectURI, DigestSHA256: digest})
	if err != nil {
		return parseonly.ArtifactLocator{}, fmt.Errorf("register governed SBV artifact: %w", err)
	}
	if strings.TrimSpace(locator.StorageClass) == "" || strings.TrimSpace(locator.URI) == "" || locator.ContentHash != digest {
		return parseonly.ArtifactLocator{}, errors.New("artifact registrar returned an incomplete or conflicting locator")
	}
	if newObject && locator.URI != objectURI {
		if err := s.quarantineDuplicate(artifact, target); err != nil {
			return parseonly.ArtifactLocator{}, fmt.Errorf("quarantine content-deduplicated object: %w", err)
		}
	}
	return locator, nil
}

func (s *FilesystemArtifactSink) quarantineDuplicate(artifact parseonly.Artifact, target string) error {
	root := filepath.Join(s.attemptRoot(artifact.SourceAssociation, artifact.AttemptID), "duplicates")
	if err := os.MkdirAll(root, 0700); err != nil {
		return err
	}
	for attempts := 0; attempts < 8; attempts++ {
		identity, err := randomID()
		if err != nil {
			return err
		}
		dir := filepath.Join(root, identity)
		if err := os.Mkdir(dir, 0700); errors.Is(err, os.ErrExist) {
			continue
		} else if err != nil {
			return err
		}
		// The freshly and exclusively created directory makes object.bin an
		// impossible replacement target. Every duplicate survives separately.
		return os.Rename(target, filepath.Join(dir, "object.bin"))
	}
	return errors.New("could not reserve collision-free duplicate quarantine")
}

func (s *FilesystemArtifactSink) CompleteAttempt(ctx context.Context, sourceAssociation, attemptID string) error {
	release, err := s.beginMutation(ctx, sourceAssociation, attemptID)
	if err != nil {
		return err
	}
	defer release()
	return s.finishAttempt(ctx, sourceAssociation, attemptID, "completed", "")
}

func (s *FilesystemArtifactSink) QuarantineAttempt(ctx context.Context, sourceAssociation, attemptID, reason string) error {
	release, err := s.beginMutation(ctx, sourceAssociation, attemptID)
	if err != nil {
		return err
	}
	defer release()
	return s.finishAttempt(ctx, sourceAssociation, attemptID, "quarantine", reason)
}

func (s *FilesystemArtifactSink) finishAttempt(ctx context.Context, sourceAssociation, attemptID, disposition, reason string) error {
	if err := s.validateAttempt(ctx, sourceAssociation, attemptID); err != nil {
		return err
	}
	from := s.attemptRoot(sourceAssociation, attemptID)
	if _, err := os.Stat(from); errors.Is(err, os.ErrNotExist) {
		return nil
	} else if err != nil {
		return fmt.Errorf("stat SBV artifact attempt: %w", err)
	}
	if disposition == "quarantine" {
		reasonText := fmt.Sprintf("quarantined_at=%s\nreason=%s\n", time.Now().UTC().Format(time.RFC3339Nano), strings.TrimSpace(reason))
		if err := os.WriteFile(filepath.Join(from, "QUARANTINE.txt"), []byte(reasonText), 0600); err != nil {
			return fmt.Errorf("record SBV quarantine reason: %w", err)
		}
	}
	destination := filepath.Join(s.root, "attempts", disposition, sha256Text(sourceAssociation), attemptID)
	if err := os.MkdirAll(filepath.Dir(destination), 0700); err != nil {
		return fmt.Errorf("create SBV attempt disposition directory: %w", err)
	}
	if _, err := os.Stat(destination); err == nil {
		return errors.New("SBV attempt disposition already exists")
	} else if !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("inspect SBV attempt disposition: %w", err)
	}
	if err := os.Rename(from, destination); err != nil {
		return fmt.Errorf("move SBV artifact attempt to %s: %w", disposition, err)
	}
	return nil
}

// recoverInterruptedAttempts runs before the sink is exposed. No parse can be
// active yet, so every prior inflight directory is a process-interrupted
// attempt and is moved intact to protected quarantine.
func (s *FilesystemArtifactSink) recoverInterruptedAttempts() error {
	inflight := filepath.Join(s.root, "attempts", "inflight")
	sources, err := os.ReadDir(inflight)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect interrupted SBV attempts: %w", err)
	}
	for _, source := range sources {
		if !source.IsDir() || source.Type()&os.ModeSymlink != 0 {
			return errors.New("invalid entry in SBV inflight attempt root")
		}
		attempts, err := os.ReadDir(filepath.Join(inflight, source.Name()))
		if err != nil {
			return fmt.Errorf("inspect interrupted SBV source attempts: %w", err)
		}
		for _, attempt := range attempts {
			if !attempt.IsDir() || attempt.Type()&os.ModeSymlink != 0 || len(attempt.Name()) != 32 {
				return errors.New("invalid SBV inflight attempt entry")
			}
			from := filepath.Join(inflight, source.Name(), attempt.Name())
			reason := fmt.Sprintf("quarantined_at=%s\nreason=runtime restart recovered interrupted attempt\n", time.Now().UTC().Format(time.RFC3339Nano))
			if err := os.WriteFile(filepath.Join(from, "QUARANTINE.txt"), []byte(reason), 0600); err != nil {
				return fmt.Errorf("record interrupted SBV attempt: %w", err)
			}
			destination := filepath.Join(s.root, "attempts", "quarantine", source.Name(), attempt.Name())
			if err := os.MkdirAll(filepath.Dir(destination), 0700); err != nil {
				return fmt.Errorf("create interrupted SBV quarantine: %w", err)
			}
			if _, err := os.Stat(destination); err == nil {
				return errors.New("interrupted SBV attempt quarantine already exists")
			} else if !errors.Is(err, os.ErrNotExist) {
				return fmt.Errorf("inspect interrupted SBV quarantine: %w", err)
			}
			if err := os.Rename(from, destination); err != nil {
				return fmt.Errorf("quarantine interrupted SBV attempt: %w", err)
			}
		}
	}
	return nil
}

func requirePathWithin(root, candidate string) error {
	rootResolved, err := filepath.EvalSymlinks(root)
	if err != nil {
		return fmt.Errorf("resolve SBV artifact staging root: %w", err)
	}
	candidateResolved, err := filepath.EvalSymlinks(strings.TrimSpace(candidate))
	if err != nil {
		return fmt.Errorf("resolve SBV staged artifact: %w", err)
	}
	relative, err := filepath.Rel(rootResolved, candidateResolved)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
		return errors.New("SBV staged artifact escapes its source-scoped root")
	}
	return nil
}

func (s *FilesystemArtifactSink) publish(ctx context.Context, artifact parseonly.Artifact, target string, expectedSize int64, expectedDigest string) (bool, error) {
	if err := os.MkdirAll(filepath.Dir(target), 0700); err != nil {
		return false, fmt.Errorf("create SBV immutable artifact directory: %w", err)
	}
	if _, err := os.Stat(target); err == nil {
		return false, verifyExact(ctx, target, expectedSize, expectedDigest)
	} else if !errors.Is(err, os.ErrNotExist) {
		return false, fmt.Errorf("inspect immutable artifact identity: %w", err)
	}
	publishDir := filepath.Join(s.attemptRoot(artifact.SourceAssociation, artifact.AttemptID), "publish")
	if err := os.MkdirAll(publishDir, 0700); err != nil {
		return false, fmt.Errorf("create SBV publish staging: %w", err)
	}
	temp, err := os.CreateTemp(publishDir, "artifact-*.partial")
	if err != nil {
		return false, fmt.Errorf("create SBV publish candidate: %w", err)
	}
	if err := temp.Chmod(0400); err != nil {
		_ = temp.Close()
		return false, fmt.Errorf("protect SBV publish candidate: %w", err)
	}
	input, err := os.Open(artifact.StagedPath)
	if err != nil {
		_ = temp.Close()
		return false, fmt.Errorf("open staged SBV artifact: %w", err)
	}
	_, copyErr := copyWithContext(ctx, temp, input, make([]byte, 128<<10))
	closeInputErr := input.Close()
	syncErr := temp.Sync()
	closeTempErr := temp.Close()
	for _, operationErr := range []error{copyErr, closeInputErr, syncErr, closeTempErr} {
		if operationErr != nil {
			return false, fmt.Errorf("prepare immutable SBV artifact: %w", operationErr)
		}
	}
	if err := verifyExact(ctx, temp.Name(), expectedSize, expectedDigest); err != nil {
		return false, err
	}
	// Linking a closed, verified candidate publishes all bytes atomically and
	// refuses to overwrite an existing logical identity.
	if err := os.Link(temp.Name(), target); errors.Is(err, os.ErrExist) {
		return false, verifyExact(ctx, target, expectedSize, expectedDigest)
	} else if err != nil {
		return false, fmt.Errorf("atomically publish immutable SBV artifact: %w", err)
	}
	return true, nil
}

func verifyExact(ctx context.Context, path string, expectedSize int64, expectedDigest string) error {
	digest, size, err := digestFile(ctx, path)
	if err != nil {
		return err
	}
	if size != expectedSize || digest != expectedDigest {
		return errors.New("immutable artifact logical identity already contains different bytes")
	}
	return nil
}

func (s *FilesystemArtifactSink) beginMutation(ctx context.Context, sourceAssociation, attemptID string) (func(), error) {
	if s == nil {
		return nil, errors.New("SBV immutable artifact sink is not configured")
	}
	s.operationMu.RLock()
	release := func() { s.operationMu.RUnlock() }
	if err := s.validateAttempt(ctx, sourceAssociation, attemptID); err != nil {
		release()
		return nil, err
	}
	if s.closed {
		release()
		return nil, errors.New("SBV immutable artifact sink is closed")
	}
	lockBytes, err := os.ReadFile(s.lockPath)
	if err != nil {
		release()
		return nil, fmt.Errorf("validate active SBV runtime ownership: %w", err)
	}
	if string(lockBytes) != s.lockOwner {
		release()
		return nil, errors.New("active SBV runtime lock owner does not match this sink")
	}
	return release, nil
}

func (s *FilesystemArtifactSink) validateAttempt(ctx context.Context, sourceAssociation, attemptID string) error {
	if s == nil || s.root == "" || s.registrar == nil {
		return errors.New("SBV immutable artifact sink is not configured")
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if strings.TrimSpace(sourceAssociation) == "" {
		return errors.New("SBV artifact attempt requires a source association")
	}
	if len(attemptID) != 32 {
		return errors.New("SBV artifact attempt identity is invalid")
	}
	if _, err := hex.DecodeString(attemptID); err != nil || strings.ToLower(attemptID) != attemptID {
		return errors.New("SBV artifact attempt identity is invalid")
	}
	return nil
}

func (s *FilesystemArtifactSink) attemptRoot(sourceAssociation, attemptID string) string {
	return filepath.Join(s.root, "attempts", "inflight", sha256Text(sourceAssociation), attemptID)
}

func digestFile(ctx context.Context, path string) (string, int64, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", 0, fmt.Errorf("open artifact for digest: %w", err)
	}
	defer file.Close()
	hash := sha256.New()
	written, err := copyWithContext(ctx, hash, file, make([]byte, 128<<10))
	if err != nil {
		return "", 0, fmt.Errorf("digest artifact: %w", err)
	}
	return hex.EncodeToString(hash.Sum(nil)), written, nil
}

func copyWithContext(ctx context.Context, destination io.Writer, source io.Reader, buffer []byte) (int64, error) {
	var total int64
	for {
		if err := ctx.Err(); err != nil {
			return total, err
		}
		read, readErr := source.Read(buffer)
		if read > 0 {
			written, writeErr := destination.Write(buffer[:read])
			total += int64(written)
			if writeErr != nil {
				return total, writeErr
			}
			if written != read {
				return total, io.ErrShortWrite
			}
		}
		if errors.Is(readErr, io.EOF) {
			return total, nil
		}
		if readErr != nil {
			return total, readErr
		}
		if read == 0 {
			return total, io.ErrNoProgress
		}
	}
}

func sha256Text(value string) string {
	digest := sha256.Sum256([]byte(value))
	return hex.EncodeToString(digest[:])
}

func randomID() (string, error) {
	var value [16]byte
	if _, err := rand.Read(value[:]); err != nil {
		return "", fmt.Errorf("create SBV storage identity: %w", err)
	}
	return hex.EncodeToString(value[:]), nil
}

func fileURI(path string) string {
	slashPath := filepath.ToSlash(path)
	if runtime.GOOS == "windows" && !strings.HasPrefix(slashPath, "/") {
		slashPath = "/" + slashPath
	}
	return (&url.URL{Scheme: "file", Path: slashPath}).String()
}

var _ parseonly.ImmutableArtifactSink = (*FilesystemArtifactSink)(nil)

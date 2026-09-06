// Byline: Codex · GPT-5 · 2026-08-28 (content-addressed acquisition sealing)
package acquisition

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	platformpostgres "github.com/Cursedpotential/probata/engine/postgres"
	"github.com/google/uuid"
)

const sealCopyBufferSize = 128 * 1024

// storageClassSealed is the retained_object.storage_class value every
// resolver in this package publishes under. It is distinct from
// "filesystem" (engine/runtimeapi's local-file resolver) so provenance
// stays visible: this object arrived through the acquisition boundary
// rather than being discovered directly on the worker's local disk. Both
// values name objects addressed by the same on-disk layout and are opened
// identically downstream (engine/runtimeapi.NewRetainedObjectOpener treats
// any non-inline storage_class as a file:// URI).
const storageClassSealed = "immutable_object_store"

// prepareSealRoot creates (or verifies) the durable directory layout a seal
// root needs: inflight staging, content-addressed objects, and a quarantine
// for partial/failed writes. It refuses symlink or reparse-point roots for
// the same reason engine/runtimeapi/acquisition_resolver.go does: an
// acquisition boundary must not publish through an aliased path.
func prepareSealRoot(root string) (string, error) {
	root = strings.TrimSpace(root)
	if root == "" {
		return "", errors.New("acquisition: seal root is required")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", fmt.Errorf("acquisition: resolve seal root: %w", err)
	}
	absolute = filepath.Clean(absolute)
	for _, directory := range []string{
		absolute,
		filepath.Join(absolute, "inflight"),
		filepath.Join(absolute, "objects", "sha256"),
		filepath.Join(absolute, "quarantine"),
	} {
		if err := os.MkdirAll(directory, 0o750); err != nil {
			return "", fmt.Errorf("acquisition: create seal directory: %w", err)
		}
		if err := requireRealDirectory(directory); err != nil {
			return "", fmt.Errorf("acquisition: unsafe seal directory: %w", err)
		}
	}
	return absolute, nil
}

// sealStream stages source into root's inflight area, hashes it while
// copying, then atomically publishes it under its SHA-256 in
// root/objects/sha256. It never trusts a caller-declared length or digest;
// both are computed from the bytes actually read. Concurrent callers
// sealing identical content converge on the same published object: exactly
// one link wins and every loser verifies the winner before returning.
func sealStream(ctx context.Context, root string, source io.Reader) (platformpostgres.ImmutableAcquisition, error) {
	if err := ctx.Err(); err != nil {
		return platformpostgres.ImmutableAcquisition{}, err
	}
	absolute, err := prepareSealRoot(root)
	if err != nil {
		return platformpostgres.ImmutableAcquisition{}, err
	}

	partialPath := filepath.Join(absolute, "inflight", uuid.NewString()+".acquisition.partial")
	partial, err := os.OpenFile(partialPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: create staging object: %w", err)
	}
	partialOpen := true
	preserved := false
	defer func() {
		if partialOpen {
			_ = partial.Close()
		}
		if !preserved {
			_ = preservePartial(absolute, partialPath, "interrupted")
		}
	}()

	digest := sha256.New()
	byteLength, copyErr := sealCopy(ctx, io.MultiWriter(partial, digest), source)
	if copyErr == nil {
		copyErr = partial.Sync()
	}
	if closeErr := partial.Close(); copyErr == nil && closeErr != nil {
		copyErr = closeErr
	}
	partialOpen = false
	if copyErr != nil {
		preserveErr := preservePartial(absolute, partialPath, "copy-failed")
		preserved = preserveErr == nil
		if preserveErr != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: copy source: %v; preserve partial: %w", copyErr, preserveErr)
		}
		return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: copy source: %w", copyErr)
	}
	if byteLength == 0 {
		preserveErr := preservePartial(absolute, partialPath, "empty-source")
		preserved = preserveErr == nil
		return platformpostgres.ImmutableAcquisition{}, errors.New("acquisition: refusing to seal an empty source")
	}

	digestBytes := digest.Sum(nil)
	digestHex := hex.EncodeToString(digestBytes)
	objectDirectory := filepath.Join(absolute, "objects", "sha256", digestHex[:2])
	if err := os.MkdirAll(objectDirectory, 0o750); err != nil {
		return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: create digest directory: %w", err)
	}
	if err := requireRealDirectory(objectDirectory); err != nil {
		return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: unsafe digest directory: %w", err)
	}
	objectPath := filepath.Join(objectDirectory, digestHex+".source")

	published, err := publishObject(ctx, partialPath, objectPath, digestBytes, byteLength)
	if err != nil {
		preserveErr := preservePartial(absolute, partialPath, "publish-failed")
		preserved = preserveErr == nil
		if preserveErr != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("%v; preserve partial: %w", err, preserveErr)
		}
		return platformpostgres.ImmutableAcquisition{}, err
	}
	if err := os.Chmod(objectPath, 0o440); err != nil {
		return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: make object read-only: %w", err)
	}
	if published {
		if err := syncDirectory(objectDirectory); err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: sync published object directory: %w", err)
		}
	}
	if err := verifyObject(ctx, objectPath, digestBytes, byteLength); err != nil {
		return platformpostgres.ImmutableAcquisition{}, err
	}
	if err := preservePartial(absolute, partialPath, "published"); err != nil {
		return platformpostgres.ImmutableAcquisition{}, err
	}
	preserved = true

	return platformpostgres.ImmutableAcquisition{
		StorageClass:  storageClassSealed,
		ObjectURI:     fileURI(objectPath),
		ContentSHA256: bytes.Clone(digestBytes),
		ByteLength:    byteLength,
	}, nil
}

// digestObjectPath returns the content-addressed path a SHA-256 digest
// would publish under, without touching the filesystem. Resolvers that
// receive an already-sealed digest as their Ref (the upload-ingress
// resolver) use this to locate the object sealStream already published.
func digestObjectPath(root string, digestHex string) (string, error) {
	absolute, err := prepareSealRoot(root)
	if err != nil {
		return "", err
	}
	if len(digestHex) != sha256.Size*2 {
		return "", errors.New("acquisition: digest must be a 64-character hex SHA-256")
	}
	for _, r := range digestHex {
		if !((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f')) {
			return "", errors.New("acquisition: digest must be lowercase hex")
		}
	}
	return filepath.Join(absolute, "objects", "sha256", digestHex[:2], digestHex+".source"), nil
}

func sealCopy(ctx context.Context, destination io.Writer, source io.Reader) (int64, error) {
	buffer := make([]byte, sealCopyBufferSize)
	var total int64
	for {
		if err := ctx.Err(); err != nil {
			return total, err
		}
		count, readErr := source.Read(buffer)
		if count > 0 {
			written, writeErr := destination.Write(buffer[:count])
			total += int64(written)
			if writeErr != nil {
				return total, writeErr
			}
			if written != count {
				return total, io.ErrShortWrite
			}
		}
		if errors.Is(readErr, io.EOF) {
			return total, nil
		}
		if readErr != nil {
			return total, readErr
		}
	}
}

func publishObject(ctx context.Context, partialPath, objectPath string, digest []byte, byteLength int64) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}
	if err := os.Link(partialPath, objectPath); err == nil {
		return true, nil
	} else if !errors.Is(err, os.ErrExist) {
		return false, fmt.Errorf("acquisition: atomically publish object: %w", err)
	}
	if err := verifyObject(ctx, objectPath, digest, byteLength); err != nil {
		return false, fmt.Errorf("acquisition: content-addressed target conflict: %w", err)
	}
	return false, nil
}

func verifyObject(ctx context.Context, path string, expectedDigest []byte, expectedLength int64) error {
	file, err := openRegularNonAliasFile(path)
	if err != nil {
		return fmt.Errorf("acquisition: verify object: %w", err)
	}
	defer file.Close()
	hash := sha256.New()
	actualLength, err := sealCopy(ctx, hash, file)
	if err != nil {
		return fmt.Errorf("acquisition: verify object content: %w", err)
	}
	if actualLength != expectedLength || !bytes.Equal(hash.Sum(nil), expectedDigest) {
		return errors.New("acquisition: object digest or byte length does not match its address")
	}
	return nil
}

func preservePartial(root, partialPath, reason string) error {
	if strings.TrimSpace(partialPath) == "" {
		return nil
	}
	if _, err := os.Lstat(partialPath); errors.Is(err, os.ErrNotExist) {
		return nil
	} else if err != nil {
		return fmt.Errorf("acquisition: inspect staging object: %w", err)
	}
	quarantine := filepath.Join(root, "quarantine")
	if err := requireRealDirectory(quarantine); err != nil {
		return fmt.Errorf("acquisition: unsafe quarantine directory: %w", err)
	}
	reason = strings.Map(func(character rune) rune {
		if character >= 'a' && character <= 'z' || character >= '0' && character <= '9' || character == '-' {
			return character
		}
		return '-'
	}, strings.ToLower(reason))
	target := filepath.Join(quarantine, reason+"-"+uuid.NewString()+".acquisition.partial")
	if err := os.Rename(partialPath, target); err != nil {
		return fmt.Errorf("acquisition: preserve staging object: %w", err)
	}
	return syncDirectory(quarantine)
}

func syncDirectory(path string) error {
	// Go cannot open Windows directories with the semantics File.Sync
	// requires. The staged file itself is always synced before publication;
	// directory fsync adds the rename/link durability barrier on Unix.
	if runtime.GOOS == "windows" {
		return nil
	}
	directory, err := os.Open(path)
	if err != nil {
		return err
	}
	defer directory.Close()
	return directory.Sync()
}

func openRegularNonAliasFile(path string) (*os.File, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, err
	}
	if info.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("symlink acquisition paths are forbidden")
	}
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return nil, fmt.Errorf("resolve acquisition path aliases: %w", err)
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return nil, fmt.Errorf("resolve acquisition path: %w", err)
	}
	resolvedAbsolute, err := filepath.Abs(resolved)
	if err != nil {
		return nil, fmt.Errorf("resolve canonical acquisition path: %w", err)
	}
	if !sameCanonicalPath(absolute, resolvedAbsolute) {
		return nil, errors.New("symlink or reparse-point acquisition paths are forbidden")
	}
	if !info.Mode().IsRegular() {
		return nil, errors.New("acquisition path must identify a regular file")
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	openedInfo, err := file.Stat()
	if err != nil {
		_ = file.Close()
		return nil, err
	}
	if !openedInfo.Mode().IsRegular() || !os.SameFile(info, openedInfo) {
		_ = file.Close()
		return nil, errors.New("acquisition file changed while it was being opened")
	}
	return file, nil
}

func requireRealDirectory(path string) error {
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return errors.New("path is not a real directory")
	}
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return err
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return err
	}
	resolvedAbsolute, err := filepath.Abs(resolved)
	if err != nil {
		return err
	}
	if !sameCanonicalPath(absolute, resolvedAbsolute) {
		return errors.New("directory path traverses a symlink or reparse point")
	}
	return nil
}

func sameCanonicalPath(left, right string) bool {
	left, right = filepath.Clean(left), filepath.Clean(right)
	if runtime.GOOS == "windows" {
		return strings.EqualFold(left, right)
	}
	return left == right
}

func fileURI(path string) string {
	absolute, err := filepath.Abs(path)
	if err != nil {
		absolute = path
	}
	slashed := filepath.ToSlash(absolute)
	if runtime.GOOS == "windows" && len(slashed) >= 2 && slashed[1] == ':' {
		slashed = "/" + slashed
	}
	return "file://" + slashed
}

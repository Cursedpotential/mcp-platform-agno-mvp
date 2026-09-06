package runtimeapi

import (
	"bytes"
	"context"
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

	platformpostgres "github.com/Cursedpotential/probata/engine/postgres"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/google/uuid"
)

const acquisitionCopyBufferSize = 128 * 1024

// NewFilesystemImmutableAcquisitionResolver returns an acquisition boundary
// that accepts only absolute local file:// references. Each source is copied
// byte-for-byte into root and published under its SHA-256 without ever moving
// or mutating the caller's source file. Only the immutable object's locator
// and measurements leave this boundary; source bytes never enter Temporal
// history or a PostgreSQL activity request.
//
// The root must be a real directory rather than a symlink/junction alias. The
// resolver uses a hard-link as its atomic, no-clobber publish primitive. That
// makes concurrent processes idempotent: exactly one link wins, and every
// loser verifies the winning object before returning the same locator.
func NewFilesystemImmutableAcquisitionResolver(root string) (platformpostgres.ImmutableAcquisitionResolver, error) {
	root = strings.TrimSpace(root)
	if root == "" {
		return nil, errors.New("immutable acquisition resolver: source-object root is required")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return nil, fmt.Errorf("immutable acquisition resolver: resolve source-object root: %w", err)
	}
	absolute = filepath.Clean(absolute)
	for _, directory := range []string{
		absolute,
		filepath.Join(absolute, "inflight"),
		filepath.Join(absolute, "objects", "sha256"),
		filepath.Join(absolute, "quarantine"),
	} {
		if err := os.MkdirAll(directory, 0o750); err != nil {
			return nil, fmt.Errorf("immutable acquisition resolver: create durable directory: %w", err)
		}
		if err := requireRealDirectory(directory); err != nil {
			return nil, fmt.Errorf("immutable acquisition resolver: unsafe durable directory: %w", err)
		}
	}

	return func(ctx context.Context, ref proffer.Ref) (platformpostgres.ImmutableAcquisition, error) {
		if err := ctx.Err(); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		sourcePath, err := strictAcquisitionFilePath(string(ref))
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		source, err := openRegularNonAliasFile(sourcePath)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: open source: %w", err)
		}
		defer source.Close()

		partialPath := filepath.Join(absolute, "inflight", uuid.NewString()+".source.partial")
		partial, err := os.OpenFile(partialPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: create staging object: %w", err)
		}
		partialOpen := true
		preserved := false
		defer func() {
			if partialOpen {
				_ = partial.Close()
			}
			if !preserved {
				_ = preserveAcquisitionPartial(absolute, partialPath, "interrupted")
			}
		}()

		digest := sha256.New()
		byteLength, copyErr := copyAcquisition(ctx, io.MultiWriter(partial, digest), source)
		if copyErr == nil {
			copyErr = partial.Sync()
		}
		if closeErr := partial.Close(); copyErr == nil && closeErr != nil {
			copyErr = closeErr
		}
		partialOpen = false
		if copyErr != nil {
			preserveErr := preserveAcquisitionPartial(absolute, partialPath, "copy-failed")
			preserved = preserveErr == nil
			if preserveErr != nil {
				return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: copy source: %v; preserve partial: %w", copyErr, preserveErr)
			}
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: copy source: %w", copyErr)
		}

		digestBytes := digest.Sum(nil)
		digestHex := hex.EncodeToString(digestBytes)
		objectDirectory := filepath.Join(absolute, "objects", "sha256", digestHex[:2])
		if err := os.MkdirAll(objectDirectory, 0o750); err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: create digest directory: %w", err)
		}
		if err := requireRealDirectory(objectDirectory); err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: unsafe digest directory: %w", err)
		}
		objectPath := filepath.Join(objectDirectory, digestHex+".source")

		published, err := publishAcquisitionObject(ctx, partialPath, objectPath, digestBytes, byteLength)
		if err != nil {
			preserveErr := preserveAcquisitionPartial(absolute, partialPath, "publish-failed")
			preserved = preserveErr == nil
			if preserveErr != nil {
				return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("%v; preserve partial: %w", err, preserveErr)
			}
			return platformpostgres.ImmutableAcquisition{}, err
		}
		// A winning retry may find an older, correctly addressed object that
		// predates the read-only mode. Re-assert the immutable filesystem
		// posture on both the publish and reuse paths.
		if err := os.Chmod(objectPath, 0o440); err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: make object read-only: %w", err)
		}
		if published {
			if err := syncAcquisitionDirectory(objectDirectory); err != nil {
				return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("immutable acquisition resolver: sync published object directory: %w", err)
			}
		}
		if err := verifyAcquisitionObject(ctx, objectPath, digestBytes, byteLength); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		if err := preserveAcquisitionPartial(absolute, partialPath, "published"); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		preserved = true

		return platformpostgres.ImmutableAcquisition{
			StorageClass:  "filesystem",
			ObjectURI:     fileURI(objectPath),
			ContentSHA256: bytes.Clone(digestBytes),
			ByteLength:    byteLength,
		}, nil
	}, nil
}

func strictAcquisitionFilePath(value string) (string, error) {
	value = strings.TrimSpace(value)
	if !strings.HasPrefix(strings.ToLower(value), "file://") {
		return "", errors.New("immutable acquisition resolver: acquisition reference must be a file:// URI")
	}
	parsed, err := url.Parse(value)
	if err != nil {
		return "", fmt.Errorf("immutable acquisition resolver: parse acquisition reference: %w", err)
	}
	if parsed.Scheme != "file" || parsed.Host != "" || parsed.User != nil || parsed.Opaque != "" || parsed.RawQuery != "" || parsed.Fragment != "" || parsed.ForceQuery {
		return "", errors.New("immutable acquisition resolver: acquisition reference must identify one local file")
	}
	path := filepath.FromSlash(parsed.Path)
	if runtime.GOOS == "windows" && len(path) >= 3 && (path[0] == '\\' || path[0] == '/') && path[2] == ':' {
		path = path[1:]
	}
	if !filepath.IsAbs(path) {
		return "", errors.New("immutable acquisition resolver: acquisition file path must be absolute")
	}
	return filepath.Clean(path), nil
}

func openRegularNonAliasFile(path string) (*os.File, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, err
	}
	if info.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("symlink acquisition references are forbidden")
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
		return nil, errors.New("acquisition reference must identify a regular file")
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

func copyAcquisition(ctx context.Context, destination io.Writer, source io.Reader) (int64, error) {
	buffer := make([]byte, acquisitionCopyBufferSize)
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

func publishAcquisitionObject(ctx context.Context, partialPath, objectPath string, digest []byte, byteLength int64) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}
	if err := os.Link(partialPath, objectPath); err == nil {
		return true, nil
	} else if !errors.Is(err, os.ErrExist) {
		return false, fmt.Errorf("immutable acquisition resolver: atomically publish object: %w", err)
	}
	if err := verifyAcquisitionObject(ctx, objectPath, digest, byteLength); err != nil {
		return false, fmt.Errorf("immutable acquisition resolver: content-addressed target conflict: %w", err)
	}
	return false, nil
}

func verifyAcquisitionObject(ctx context.Context, path string, expectedDigest []byte, expectedLength int64) error {
	file, err := openRegularNonAliasFile(path)
	if err != nil {
		return fmt.Errorf("immutable acquisition resolver: verify object: %w", err)
	}
	defer file.Close()
	hash := sha256.New()
	actualLength, err := copyAcquisition(ctx, hash, file)
	if err != nil {
		return fmt.Errorf("immutable acquisition resolver: verify object content: %w", err)
	}
	if actualLength != expectedLength || !bytes.Equal(hash.Sum(nil), expectedDigest) {
		return errors.New("immutable acquisition resolver: object digest or byte length does not match its address")
	}
	return nil
}

func preserveAcquisitionPartial(root, partialPath, reason string) error {
	if strings.TrimSpace(partialPath) == "" {
		return nil
	}
	if _, err := os.Lstat(partialPath); errors.Is(err, os.ErrNotExist) {
		return nil
	} else if err != nil {
		return fmt.Errorf("immutable acquisition resolver: inspect staging object: %w", err)
	}
	quarantine := filepath.Join(root, "quarantine")
	if err := requireRealDirectory(quarantine); err != nil {
		return fmt.Errorf("immutable acquisition resolver: unsafe quarantine directory: %w", err)
	}
	reason = strings.Map(func(character rune) rune {
		if character >= 'a' && character <= 'z' || character >= '0' && character <= '9' || character == '-' {
			return character
		}
		return '-'
	}, strings.ToLower(reason))
	target := filepath.Join(quarantine, reason+"-"+uuid.NewString()+".source.partial")
	if err := os.Rename(partialPath, target); err != nil {
		return fmt.Errorf("immutable acquisition resolver: preserve staging object: %w", err)
	}
	return syncAcquisitionDirectory(quarantine)
}

func syncAcquisitionDirectory(path string) error {
	// Go cannot open Windows directories with the semantics required by
	// File.Sync. The staged file itself is always synced before publication;
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

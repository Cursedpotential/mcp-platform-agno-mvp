package runtimeapi

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"testing"

	platformpostgres "github.com/Cursedpotential/probata/engine/postgres"
	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/stretchr/testify/require"
)

func TestFilesystemImmutableAcquisitionResolverCopiesAndMeasures(t *testing.T) {
	root := t.TempDir()
	sourceDirectory := t.TempDir()
	sourcePath := filepath.Join(sourceDirectory, "source with spaces.bin")
	content := bytes.Repeat([]byte("immutable-source\x00"), 20_000)
	require.NoError(t, os.WriteFile(sourcePath, content, 0o600))

	resolver, err := NewFilesystemImmutableAcquisitionResolver(root)
	require.NoError(t, err)
	var typed platformpostgres.ImmutableAcquisitionResolver = resolver
	result, err := typed(context.Background(), proffer.Ref(fileURI(sourcePath)))
	require.NoError(t, err)

	wantDigest := sha256.Sum256(content)
	require.Equal(t, "filesystem", result.StorageClass)
	require.Equal(t, wantDigest[:], result.ContentSHA256)
	require.Equal(t, int64(len(content)), result.ByteLength)
	require.Nil(t, result.InlineBytes)
	objectPath, err := pathFromFileURI(result.ObjectURI)
	require.NoError(t, err)
	require.NotEqual(t, filepath.Clean(sourcePath), objectPath)
	require.FileExists(t, objectPath)
	actual, err := os.ReadFile(objectPath)
	require.NoError(t, err)
	require.Equal(t, content, actual)

	// Retention copies; it never mutates or consumes the acquisition source.
	sourceAfter, err := os.ReadFile(sourcePath)
	require.NoError(t, err)
	require.Equal(t, content, sourceAfter)
	quarantined, err := filepath.Glob(filepath.Join(root, "quarantine", "published-*.source.partial"))
	require.NoError(t, err)
	require.Len(t, quarantined, 1)
}

func TestFilesystemImmutableAcquisitionResolverIsConcurrentAndIdempotent(t *testing.T) {
	root := t.TempDir()
	sourcePath := filepath.Join(t.TempDir(), "source.bin")
	require.NoError(t, os.WriteFile(sourcePath, bytes.Repeat([]byte("same"), 50_000), 0o600))
	resolver, err := NewFilesystemImmutableAcquisitionResolver(root)
	require.NoError(t, err)

	const callers = 8
	results := make([]platformpostgres.ImmutableAcquisition, callers)
	errorsFound := make([]error, callers)
	var wait sync.WaitGroup
	for index := range callers {
		wait.Add(1)
		go func() {
			defer wait.Done()
			results[index], errorsFound[index] = resolver(context.Background(), proffer.Ref(fileURI(sourcePath)))
		}()
	}
	wait.Wait()
	for index := range callers {
		require.NoError(t, errorsFound[index])
		require.Equal(t, results[0].ObjectURI, results[index].ObjectURI)
		require.Equal(t, results[0].ContentSHA256, results[index].ContentSHA256)
		require.Equal(t, results[0].ByteLength, results[index].ByteLength)
	}
	objects, err := filepath.Glob(filepath.Join(root, "objects", "sha256", "*", "*.source"))
	require.NoError(t, err)
	require.Len(t, objects, 1)
	quarantined, err := filepath.Glob(filepath.Join(root, "quarantine", "published-*.source.partial"))
	require.NoError(t, err)
	require.Len(t, quarantined, callers)
}

func TestFilesystemImmutableAcquisitionResolverAllowsContractValidEmptyFile(t *testing.T) {
	sourcePath := filepath.Join(t.TempDir(), "empty")
	require.NoError(t, os.WriteFile(sourcePath, nil, 0o600))
	resolver, err := NewFilesystemImmutableAcquisitionResolver(t.TempDir())
	require.NoError(t, err)
	result, err := resolver(context.Background(), proffer.Ref(fileURI(sourcePath)))
	require.NoError(t, err)
	require.Zero(t, result.ByteLength)
	want := sha256.Sum256(nil)
	require.Equal(t, want[:], result.ContentSHA256)
}

func TestFilesystemImmutableAcquisitionResolverRejectsUnsafeReferences(t *testing.T) {
	root := t.TempDir()
	resolver, err := NewFilesystemImmutableAcquisitionResolver(root)
	require.NoError(t, err)
	directory := t.TempDir()

	values := []proffer.Ref{
		"https://example.test/file",
		"file:relative.txt",
		"file://server/share/file.txt",
		proffer.Ref(fileURI(directory)),
		proffer.Ref(fileURI(filepath.Join(directory, "missing"))),
	}
	for _, value := range values {
		_, resolveErr := resolver(context.Background(), value)
		require.Error(t, resolveErr, value)
	}
}

func TestFilesystemImmutableAcquisitionResolverRejectsSymlinkAlias(t *testing.T) {
	target := filepath.Join(t.TempDir(), "target")
	require.NoError(t, os.WriteFile(target, []byte("target"), 0o600))
	alias := filepath.Join(t.TempDir(), "alias")
	if err := os.Symlink(target, alias); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}
	resolver, err := NewFilesystemImmutableAcquisitionResolver(t.TempDir())
	require.NoError(t, err)
	_, err = resolver(context.Background(), proffer.Ref(fileURI(alias)))
	require.ErrorContains(t, err, "symlink")
}

func TestFilesystemImmutableAcquisitionResolverRejectsAliasedRoot(t *testing.T) {
	root := t.TempDir()
	alias := filepath.Join(t.TempDir(), "alias")
	if err := os.Symlink(root, alias); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}
	_, err := NewFilesystemImmutableAcquisitionResolver(alias)
	require.ErrorContains(t, err, "unsafe durable directory")
}

func TestFilesystemImmutableAcquisitionResolverRejectsCorruptDigestTarget(t *testing.T) {
	root := t.TempDir()
	sourcePath := filepath.Join(t.TempDir(), "source")
	content := []byte("expected source bytes")
	require.NoError(t, os.WriteFile(sourcePath, content, 0o600))
	digest := sha256.Sum256(content)
	digestHex := hex.EncodeToString(digest[:])
	targetDirectory := filepath.Join(root, "objects", "sha256", digestHex[:2])
	require.NoError(t, os.MkdirAll(targetDirectory, 0o750))
	require.NoError(t, os.WriteFile(filepath.Join(targetDirectory, digestHex+".source"), []byte("wrong"), 0o600))

	resolver, err := NewFilesystemImmutableAcquisitionResolver(root)
	require.NoError(t, err)
	_, err = resolver(context.Background(), proffer.Ref(fileURI(sourcePath)))
	require.ErrorContains(t, err, "content-addressed target conflict")
	quarantined, globErr := filepath.Glob(filepath.Join(root, "quarantine", "publish-failed-*.source.partial"))
	require.NoError(t, globErr)
	require.Len(t, quarantined, 1)
	actual, readErr := os.ReadFile(sourcePath)
	require.NoError(t, readErr)
	require.Equal(t, content, actual)
}

func TestFilesystemImmutableAcquisitionResolverHonorsCancellation(t *testing.T) {
	resolver, err := NewFilesystemImmutableAcquisitionResolver(t.TempDir())
	require.NoError(t, err)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err = resolver(ctx, proffer.Ref("file:///does/not/matter"))
	require.ErrorIs(t, err, context.Canceled)
}

func TestStrictAcquisitionFilePathRejectsDecoratedURI(t *testing.T) {
	path := filepath.Join(t.TempDir(), "source")
	for _, suffix := range []string{"?query=1", "#fragment"} {
		_, err := strictAcquisitionFilePath(fileURI(path) + suffix)
		require.Error(t, err)
	}
	if runtime.GOOS != "windows" {
		_, err := strictAcquisitionFilePath("file://host/tmp/source")
		require.Error(t, err)
	}
}

func TestNewFilesystemImmutableAcquisitionResolverRequiresRoot(t *testing.T) {
	_, err := NewFilesystemImmutableAcquisitionResolver(" ")
	require.Error(t, err)
}

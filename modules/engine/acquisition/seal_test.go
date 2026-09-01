// Byline: Codex · GPT-5 · 2026-08-28 (acquisition sealing tests)
package acquisition

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sync"
	"testing"

	"github.com/stretchr/testify/require"
)

type flakyReader struct {
	data   []byte
	failAt int
}

func (f *flakyReader) Read(p []byte) (int, error) {
	if f.failAt <= 0 {
		return 0, errors.New("simulated read failure")
	}
	n := min(len(p), f.failAt)
	copy(p, f.data[:n])
	f.data = f.data[n:]
	f.failAt -= n
	if len(f.data) == 0 {
		return n, io.EOF
	}
	return n, nil
}

func TestSealStreamComputesDigestAndPublishes(t *testing.T) {
	root := t.TempDir()
	content := bytes.Repeat([]byte("acquisition-boundary\x00"), 15_000)

	sealed, err := sealStream(context.Background(), root, bytes.NewReader(content))
	require.NoError(t, err)

	wantDigest := sha256.Sum256(content)
	require.Equal(t, storageClassSealed, sealed.StorageClass)
	require.Equal(t, wantDigest[:], sealed.ContentSHA256)
	require.Equal(t, int64(len(content)), sealed.ByteLength)
	require.Nil(t, sealed.InlineBytes)

	objectPath, err := digestObjectPath(root, hex.EncodeToString(wantDigest[:]))
	require.NoError(t, err)
	require.FileExists(t, objectPath)
	actual, err := os.ReadFile(objectPath)
	require.NoError(t, err)
	require.Equal(t, content, actual)

	info, err := os.Lstat(objectPath)
	require.NoError(t, err)
	require.Zero(t, info.Mode().Perm()&0o200, "sealed object must be read-only")
}

func TestSealStreamRefusesEmptySource(t *testing.T) {
	root := t.TempDir()
	_, err := sealStream(context.Background(), root, bytes.NewReader(nil))
	require.Error(t, err)
	require.Contains(t, err.Error(), "empty")

	remaining, err := filepath.Glob(filepath.Join(root, "inflight", "*"))
	require.NoError(t, err)
	require.Empty(t, remaining, "empty-source staging file must not linger in inflight")
}

func TestSealStreamQuarantinesOnReadFailure(t *testing.T) {
	root := t.TempDir()
	reader := &flakyReader{data: []byte("partial-bytes-before-failure"), failAt: 10}

	_, err := sealStream(context.Background(), root, reader)
	require.Error(t, err)

	quarantined, err := filepath.Glob(filepath.Join(root, "quarantine", "copy-failed-*.acquisition.partial"))
	require.NoError(t, err)
	require.Len(t, quarantined, 1)

	remaining, err := filepath.Glob(filepath.Join(root, "inflight", "*"))
	require.NoError(t, err)
	require.Empty(t, remaining)
}

func TestSealStreamIsConcurrentAndIdempotent(t *testing.T) {
	root := t.TempDir()
	content := bytes.Repeat([]byte("same-object"), 40_000)

	const callers = 8
	results := make([]bool, callers)
	errorsFound := make([]error, callers)
	var wait sync.WaitGroup
	for index := range callers {
		wait.Add(1)
		go func() {
			defer wait.Done()
			sealed, err := sealStream(context.Background(), root, bytes.NewReader(content))
			errorsFound[index] = err
			results[index] = err == nil && sealed.ByteLength == int64(len(content))
		}()
	}
	wait.Wait()
	for index := range callers {
		require.NoError(t, errorsFound[index])
		require.True(t, results[index])
	}

	objects, err := filepath.Glob(filepath.Join(root, "objects", "sha256", "*", "*.source"))
	require.NoError(t, err)
	require.Len(t, objects, 1, "identical content must publish to exactly one object")
}

func TestDigestObjectPathRejectsMalformedDigests(t *testing.T) {
	root := t.TempDir()
	_, err := digestObjectPath(root, "not-hex")
	require.Error(t, err)
	_, err = digestObjectPath(root, "AB"+string(make([]byte, 62)))
	require.Error(t, err)
}

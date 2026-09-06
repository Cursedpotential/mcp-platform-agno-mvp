// Byline: Codex · GPT-5 · 2026-08-28 (object-storage acquisition tests)
package acquisition

import (
	"bytes"
	"context"
	"crypto/sha256"
	"errors"
	"io"
	"testing"

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/stretchr/testify/require"
)

type fakeObjectStorage struct {
	wantBucket, wantKey string
	body                []byte
	contentLength       *int64
	err                 error
	calls               int
}

func (f *fakeObjectStorage) GetObject(_ context.Context, in *s3.GetObjectInput, _ ...func(*s3.Options)) (*s3.GetObjectOutput, error) {
	f.calls++
	if f.err != nil {
		return nil, f.err
	}
	if aws.ToString(in.Bucket) != f.wantBucket || aws.ToString(in.Key) != f.wantKey {
		return nil, errors.New("unexpected bucket/key requested")
	}
	return &s3.GetObjectOutput{
		Body:          io.NopCloser(bytes.NewReader(f.body)),
		ContentLength: f.contentLength,
	}, nil
}

func TestObjectStorageResolverSealsFetchedObject(t *testing.T) {
	root := t.TempDir()
	content := bytes.Repeat([]byte("r2-and-b2-share-this-path"), 5_000)
	length := int64(len(content))
	client := &fakeObjectStorage{wantBucket: "case-bible", wantKey: "intake/export.zip", body: content, contentLength: &length}

	resolver, err := newObjectStorageAcquisitionResolver(root, "r2", client)
	require.NoError(t, err)

	result, err := resolver(context.Background(), CloudflareR2Ref("case-bible", "intake/export.zip"))
	require.NoError(t, err)

	wantDigest := sha256.Sum256(content)
	require.Equal(t, storageClassSealed, result.StorageClass)
	require.Equal(t, wantDigest[:], result.ContentSHA256)
	require.Equal(t, length, result.ByteLength)
	require.Equal(t, 1, client.calls)
}

func TestObjectStorageResolverRejectsWrongScheme(t *testing.T) {
	root := t.TempDir()
	client := &fakeObjectStorage{wantBucket: "b", wantKey: "k", body: []byte("x")}
	resolver, err := newObjectStorageAcquisitionResolver(root, "r2", client)
	require.NoError(t, err)

	_, err = resolver(context.Background(), BackblazeB2Ref("b", "k"))
	require.Error(t, err)
	require.Zero(t, client.calls, "resolver must reject a mismatched scheme before ever calling GetObject")
}

func TestObjectStorageResolverRejectsMalformedRef(t *testing.T) {
	root := t.TempDir()
	client := &fakeObjectStorage{}
	resolver, err := newObjectStorageAcquisitionResolver(root, "b2", client)
	require.NoError(t, err)

	for _, ref := range []proffer.Ref{"", "b2://bucket-only", "b2:///no-bucket", "file:///etc/passwd"} {
		_, err := resolver(context.Background(), ref)
		require.Errorf(t, err, "ref %q should have been rejected", ref)
	}
}

func TestObjectStorageResolverFailsClosedOnContentLengthMismatch(t *testing.T) {
	root := t.TempDir()
	wrongLength := int64(999_999)
	client := &fakeObjectStorage{wantBucket: "bucket", wantKey: "key", body: []byte("actual-bytes"), contentLength: &wrongLength}
	resolver, err := newObjectStorageAcquisitionResolver(root, "b2", client)
	require.NoError(t, err)

	_, err = resolver(context.Background(), BackblazeB2Ref("bucket", "key"))
	require.Error(t, err)
	require.Contains(t, err.Error(), "reported")
}

func TestObjectStorageResolverPropagatesFetchError(t *testing.T) {
	root := t.TempDir()
	client := &fakeObjectStorage{err: errors.New("access denied")}
	resolver, err := newObjectStorageAcquisitionResolver(root, "r2", client)
	require.NoError(t, err)

	_, err = resolver(context.Background(), CloudflareR2Ref("bucket", "key"))
	require.Error(t, err)
	require.Contains(t, err.Error(), "access denied")
}

func TestObjectStorageConfigValidation(t *testing.T) {
	_, err := NewCloudflareR2AcquisitionResolver(t.TempDir(), ObjectStorageConfig{})
	require.Error(t, err)

	_, err = NewBackblazeB2AcquisitionResolver(t.TempDir(), ObjectStorageConfig{
		Endpoint: "https://s3.us-west-004.backblazeb2.com",
		Region:   "us-west-004",
		// missing credentials
	})
	require.Error(t, err)
}

func TestObjectStorageResolverConstructorsProduceUsablePathStyleClients(t *testing.T) {
	resolver, err := NewCloudflareR2AcquisitionResolver(t.TempDir(), ObjectStorageConfig{
		Endpoint:        "https://example.r2.cloudflarestorage.com",
		Region:          "auto",
		AccessKeyID:     "ak",
		SecretAccessKey: "sk",
	})
	require.NoError(t, err)
	require.NotNil(t, resolver)

	resolver, err = NewBackblazeB2AcquisitionResolver(t.TempDir(), ObjectStorageConfig{
		Endpoint:        "https://s3.us-west-004.backblazeb2.com",
		Region:          "us-west-004",
		AccessKeyID:     "ak",
		SecretAccessKey: "sk",
	})
	require.NoError(t, err)
	require.NotNil(t, resolver)
}

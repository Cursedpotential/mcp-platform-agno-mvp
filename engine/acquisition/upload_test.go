// Byline: Codex · GPT-5 · 2026-08-28 (authenticated upload tests)
package acquisition

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/stretchr/testify/require"
)

func TestUploadIngressAcceptsAuthorizedUpload(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1 << 20, BearerToken: "windows-desktop-token"})
	require.NoError(t, err)

	content := bytes.Repeat([]byte("windows-upload-ingress"), 3_000)
	req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader(content))
	req.Header.Set("Authorization", "Bearer windows-desktop-token")
	recorder := httptest.NewRecorder()

	ingress.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusCreated, recorder.Code)

	var response uploadAcceptedResponse
	require.NoError(t, json.NewDecoder(recorder.Body).Decode(&response))
	wantDigest := sha256.Sum256(content)
	require.Equal(t, hex.EncodeToString(wantDigest[:]), response.SHA256)
	require.Equal(t, "upload://"+hex.EncodeToString(wantDigest[:]), response.AcquisitionRef)
	require.Equal(t, int64(len(content)), response.ByteLength)

	resolver, err := NewUploadIngressResolver(root)
	require.NoError(t, err)
	result, err := resolver(context.Background(), uiw.Ref(response.AcquisitionRef))
	require.NoError(t, err)
	require.Equal(t, wantDigest[:], result.ContentSHA256)
	require.Equal(t, int64(len(content)), result.ByteLength)
}

func TestUploadIngressRejectsMissingOrWrongToken(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1024, BearerToken: "correct-token"})
	require.NoError(t, err)

	for _, header := range []string{"", "Bearer wrong-token", "correct-token"} {
		req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader([]byte("payload")))
		if header != "" {
			req.Header.Set("Authorization", header)
		}
		recorder := httptest.NewRecorder()
		ingress.ServeHTTP(recorder, req)
		require.Equal(t, http.StatusUnauthorized, recorder.Code)
	}
}

func TestUploadIngressRejectsWrongMethod(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1024, BearerToken: "token"})
	require.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "/uploads", nil)
	req.Header.Set("Authorization", "Bearer token")
	recorder := httptest.NewRecorder()
	ingress.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusMethodNotAllowed, recorder.Code)
}

func TestUploadIngressRejectsOversizedBody(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 16, BearerToken: "token"})
	require.NoError(t, err)

	req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader(bytes.Repeat([]byte("x"), 1024)))
	req.Header.Set("Authorization", "Bearer token")
	recorder := httptest.NewRecorder()
	ingress.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusRequestEntityTooLarge, recorder.Code)
}

func TestUploadIngressResolverRejectsMalformedRef(t *testing.T) {
	root := t.TempDir()
	resolver, err := NewUploadIngressResolver(root)
	require.NoError(t, err)

	for _, ref := range []uiw.Ref{"", "upload://not-hex", "upload://" + "ab", "file:///etc/passwd"} {
		_, err := resolver(context.Background(), ref)
		require.Errorf(t, err, "ref %q should have been rejected", ref)
	}
}

func TestUploadIngressResolverFailsClosedOnTamperedObject(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1 << 20, BearerToken: "token"})
	require.NoError(t, err)

	content := bytes.Repeat([]byte("tamper-me"), 2_000)
	req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader(content))
	req.Header.Set("Authorization", "Bearer token")
	recorder := httptest.NewRecorder()
	ingress.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusCreated, recorder.Code)

	var response uploadAcceptedResponse
	require.NoError(t, json.NewDecoder(recorder.Body).Decode(&response))

	objectPath, err := digestObjectPath(root, response.SHA256)
	require.NoError(t, err)
	require.NoError(t, os.Chmod(objectPath, 0o600))
	require.NoError(t, os.WriteFile(objectPath, []byte("corrupted"), 0o600))

	resolver, err := NewUploadIngressResolver(root)
	require.NoError(t, err)
	_, err = resolver(context.Background(), uiw.Ref(response.AcquisitionRef))
	require.Error(t, err)
}

func TestUploadIngressResolverRejectsMissingObject(t *testing.T) {
	root := t.TempDir()
	resolver, err := NewUploadIngressResolver(root)
	require.NoError(t, err)

	neverUploaded := "upload://" + hex.EncodeToString(bytes.Repeat([]byte{0xab}, sha256.Size))
	_, err = resolver(context.Background(), uiw.Ref(neverUploaded))
	require.Error(t, err)
}

func TestUploadIngressConfigValidation(t *testing.T) {
	_, err := NewUploadIngress(UploadIngressConfig{})
	require.Error(t, err)
	_, err = NewUploadIngress(UploadIngressConfig{Root: t.TempDir(), MaxBytes: 0, BearerToken: "t"})
	require.Error(t, err)
	_, err = NewUploadIngress(UploadIngressConfig{Root: t.TempDir(), MaxBytes: 10, BearerToken: ""})
	require.Error(t, err)
}

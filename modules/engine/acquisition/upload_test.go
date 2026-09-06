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

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/stretchr/testify/require"
)

func TestUploadIngressAcceptsAuthorizedUpload(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1 << 20})
	require.NoError(t, err)

	content := bytes.Repeat([]byte("windows-upload-ingress"), 3_000)
	req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader(content))
	req.RemoteAddr = "100.64.1.2:1234"
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
	result, err := resolver(context.Background(), proffer.Ref(response.AcquisitionRef))
	require.NoError(t, err)
	require.Equal(t, wantDigest[:], result.ContentSHA256)
	require.Equal(t, int64(len(content)), result.ByteLength)
}

func TestUploadIngressRejectsNonTailnetPeerAndIgnoresForwardedHeaders(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1024})
	require.NoError(t, err)

	for _, addr := range []string{"192.0.2.1:1234", "100.63.1.2:1234", "100.128.1.2:1234"} {
		req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader([]byte("payload")))
		req.RemoteAddr = addr
		req.Header.Set("Forwarded", "for=100.64.1.2")
		req.Header.Set("X-Forwarded-For", "100.64.1.2")
		req.Header.Set("X-Real-IP", "100.64.1.2")
		recorder := httptest.NewRecorder()
		ingress.ServeHTTP(recorder, req)
		require.Equal(t, http.StatusUnauthorized, recorder.Code)
	}
}

func TestUploadIngressRejectsWrongMethod(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1024})
	require.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "/uploads", nil)
	req.RemoteAddr = "100.64.1.2:1234"
	recorder := httptest.NewRecorder()
	ingress.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusMethodNotAllowed, recorder.Code)
}

func TestUploadIngressRejectsOversizedBody(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 16})
	require.NoError(t, err)

	req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader(bytes.Repeat([]byte("x"), 1024)))
	req.RemoteAddr = "100.64.1.2:1234"
	recorder := httptest.NewRecorder()
	ingress.ServeHTTP(recorder, req)
	require.Equal(t, http.StatusRequestEntityTooLarge, recorder.Code)
}

func TestUploadIngressResolverRejectsMalformedRef(t *testing.T) {
	root := t.TempDir()
	resolver, err := NewUploadIngressResolver(root)
	require.NoError(t, err)

	for _, ref := range []proffer.Ref{"", "upload://not-hex", "upload://" + "ab", "file:///etc/passwd"} {
		_, err := resolver(context.Background(), ref)
		require.Errorf(t, err, "ref %q should have been rejected", ref)
	}
}

func TestUploadIngressResolverFailsClosedOnTamperedObject(t *testing.T) {
	root := t.TempDir()
	ingress, err := NewUploadIngress(UploadIngressConfig{Root: root, MaxBytes: 1 << 20})
	require.NoError(t, err)

	content := bytes.Repeat([]byte("tamper-me"), 2_000)
	req := httptest.NewRequest(http.MethodPost, "/uploads", bytes.NewReader(content))
	req.RemoteAddr = "100.64.1.2:1234"
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
	_, err = resolver(context.Background(), proffer.Ref(response.AcquisitionRef))
	require.Error(t, err)
}

func TestUploadIngressResolverRejectsMissingObject(t *testing.T) {
	root := t.TempDir()
	resolver, err := NewUploadIngressResolver(root)
	require.NoError(t, err)

	neverUploaded := "upload://" + hex.EncodeToString(bytes.Repeat([]byte{0xab}, sha256.Size))
	_, err = resolver(context.Background(), proffer.Ref(neverUploaded))
	require.Error(t, err)
}

func TestUploadIngressConfigValidation(t *testing.T) {
	_, err := NewUploadIngress(UploadIngressConfig{})
	require.Error(t, err)
	_, err = NewUploadIngress(UploadIngressConfig{Root: t.TempDir(), MaxBytes: 0})
	require.Error(t, err)
	_, err = NewUploadIngress(UploadIngressConfig{Root: t.TempDir(), MaxBytes: 10})
	require.NoError(t, err)
}

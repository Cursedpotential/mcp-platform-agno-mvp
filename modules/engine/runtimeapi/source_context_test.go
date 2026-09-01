package runtimeapi

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/require"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/sourcecontext"
)

type sourceContextWriterStub struct {
	spec sourcecontext.Spec
}

func (s *sourceContextWriterStub) PersistSourceContext(_ context.Context, spec sourcecontext.Spec) (sourcecontext.Receipt, error) {
	s.spec = spec
	return sourcecontext.Receipt{
		SourceContextRef: "33333333-3333-3333-3333-333333333333",
		ReceiptRef:       "uiw-source-context://33333333-3333-3333-3333-333333333333",
		ContentDigest:    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		Revision:         1,
		RecordedAt:       time.Unix(1, 0).UTC(),
	}, nil
}

func TestSourceContextHandlerBindsActorAndReturnsReferenceOnlyReceipt(t *testing.T) {
	writer := &sourceContextWriterStub{}
	handler, err := NewSourceContextHTTPHandler(writer, serviceTokenPath(t))
	require.NoError(t, err)
	body := []byte(`{
		"request_id":"request-1",
		"matter_id":"11111111-1111-1111-1111-111111111111",
		"court_case_id":"22222222-2222-2222-2222-222222222222",
		"source_ref":"r2://casebible-sorted/filing.pdf",
		"supersedes_ref":"44444444-4444-4444-4444-444444444444",
		"observed_source":{"key":"filing.pdf","name":"filing.pdf","byte_length":12,"etag":"etag-1","preview_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","verification_state":"preview_only"},
		"assertions":{"source_class":"acquired_third_party","other_party":"Other party","occurred_start":"2025-01-02","context":"Known filing context"},
		"change_reason":"Operator supplied source context during intake"
	}`)
	req := newPreviewRequest(http.MethodPost, "/reference-import/source-contexts", body)
	req.Header.Set("Idempotency-Key", "source-context-request-1")
	recorder := servePreviewRequest(handler.Routes(), req)

	require.Equal(t, http.StatusCreated, recorder.Code, recorder.Body.String())
	require.Equal(t, "authentik-user-1", writer.spec.ActorSubjectUID)
	require.Equal(t, "operator", writer.spec.ActorUsername)
	require.Equal(t, "Other party", writer.spec.Assertions.OtherParty)
	require.Equal(t, "source-context-request-1", writer.spec.IdempotencyKey)
	require.Equal(t, "44444444-4444-4444-4444-444444444444", writer.spec.SupersedesRef)
	var response map[string]any
	require.NoError(t, json.Unmarshal(recorder.Body.Bytes(), &response))
	require.Equal(t, "33333333-3333-3333-3333-333333333333", response["source_context_ref"])
	require.NotContains(t, response, "assertions")
	require.NotContains(t, response, "observed_source")
}

func TestSourceContextHandlerRejectsSourceObservationThatDoesNotMatchTheAuthorizedReference(t *testing.T) {
	writer := &sourceContextWriterStub{}
	handler, err := NewSourceContextHTTPHandler(writer, serviceTokenPath(t))
	require.NoError(t, err)
	body := []byte(`{
		"request_id":"request-1",
		"matter_id":"11111111-1111-1111-1111-111111111111",
		"court_case_id":"22222222-2222-2222-2222-222222222222",
		"source_ref":"r2://casebible-sorted/filing.pdf",
		"observed_source":{"key":"other.pdf","name":"other.pdf","byte_length":12,"etag":"etag-1","preview_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","verification_state":"preview_only"},
		"assertions":{"source_class":"unknown"},
		"change_reason":"Operator supplied source context during intake"
	}`)
	req := newPreviewRequest(http.MethodPost, "/reference-import/source-contexts", body)
	req.Header.Set("Idempotency-Key", "source-context-mismatch")
	recorder := servePreviewRequest(handler.Routes(), req)
	require.Equal(t, http.StatusUnprocessableEntity, recorder.Code, recorder.Body.String())
	require.Empty(t, writer.spec.RequestID)
}

func newPreviewRequest(method, target string, body []byte) *http.Request {
	req := httptest.NewRequest(method, target, bytes.NewReader(body))
	req.RemoteAddr = "100.64.1.9:3456"
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-authentik-uid", "authentik-user-1")
	req.Header.Set("X-authentik-username", "operator")
	req.Header.Set("Authorization", "Bearer "+strings.Repeat("s", 32))
	return req
}

func servePreviewRequest(handler http.Handler, req *http.Request) *httptest.ResponseRecorder {
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, req)
	return recorder
}

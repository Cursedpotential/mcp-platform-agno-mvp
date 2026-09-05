// Byline: Claude Code · Opus 5 · 2026-09-05.
package runtimeapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const testServiceToken = "0123456789abcdef0123456789abcdef"

func TestNewToolGatewayClientFailsClosedWithoutAServiceToken(t *testing.T) {
	if _, err := NewToolGatewayClient("http://gateway.example:8099", ""); err == nil {
		t.Fatal("a tokenless gateway client was accepted; every call would 401")
	}
	if _, err := NewToolGatewayClient("gateway.example", testServiceToken); err == nil {
		t.Fatal("a relative base URL was accepted")
	}
}

func TestToolGatewayClientSendsLocatorSchemaAndBearerToken(t *testing.T) {
	var (
		gotPath string
		gotAuth string
		gotBody map[string]any
	)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotAuth = r.Header.Get("Authorization")
		// DisallowUnknownFields on the real gateway: decode into the exact
		// shape it accepts so an extra top-level key fails here too.
		var strict struct {
			SourceRef string         `json:"source_ref"`
			Args      map[string]any `json:"args"`
		}
		decoder := json.NewDecoder(r.Body)
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&strict); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		gotBody = map[string]any{"source_ref": strict.SourceRef, "args": strict.Args}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"needs_repair":false}`))
	}))
	defer server.Close()

	client, err := NewToolGatewayClient(server.URL, testServiceToken)
	if err != nil {
		t.Fatal(err)
	}
	result, err := client.Run(t.Context(), "repair.preview", "r2://bucket/object", map[string]any{"format": "pdf"})
	if err != nil {
		t.Fatal(err)
	}
	if string(result) != `{"needs_repair":false}` {
		t.Fatalf("result=%s", result)
	}
	if gotPath != "/tools/repair.preview/run" {
		t.Fatalf("path=%q", gotPath)
	}
	if gotAuth != "Bearer "+testServiceToken {
		t.Fatalf("authorization header was not a bearer service token (len=%d)", len(gotAuth))
	}
	if gotBody["source_ref"] != "r2://bucket/object" {
		t.Fatalf("body=%v", gotBody)
	}
	args, _ := gotBody["args"].(map[string]any)
	if args["format"] != "pdf" {
		t.Fatalf("args=%v", args)
	}
}

func TestToolGatewayClientRejectsHostPathsAndEmptyLocators(t *testing.T) {
	client, err := NewToolGatewayClient("http://gateway.example:8099", testServiceToken)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.Run(t.Context(), "repair.detect", "", nil); err == nil {
		t.Fatal("an empty locator was accepted")
	}
	_, err = client.Run(t.Context(), "repair.detect", "r2://bucket/object", map[string]any{"path": "/r2/source.pdf"})
	if err == nil || !strings.Contains(err.Error(), "host path") {
		t.Fatalf("a host path reached the gateway: %v", err)
	}
}

func TestToolGatewayClientSurfacesUnauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"detail":"tool gateway: service token required"}`))
	}))
	defer server.Close()
	client, err := NewToolGatewayClient(server.URL, testServiceToken)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.Run(t.Context(), "repair.detect", "r2://bucket/object", nil); err == nil ||
		!strings.Contains(err.Error(), "401") {
		t.Fatalf("401 was not surfaced: %v", err)
	}
}

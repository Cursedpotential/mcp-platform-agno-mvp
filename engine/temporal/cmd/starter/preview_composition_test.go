package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestMountPreviewRoutesOwnsOpaqueStartAndPreservesLegacyFallback(t *testing.T) {
	existing := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write([]byte("legacy")) })
	preview := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write([]byte(`{"preview_handle":"opaque"}`)) })
	routes, err := mountPreviewRoutes(existing, preview)
	if err != nil {
		t.Fatal(err)
	}
	start := httptest.NewRecorder()
	routes.ServeHTTP(start, httptest.NewRequest(http.MethodPost, "/reference-import/start", nil))
	if !strings.Contains(start.Body.String(), "preview_handle") {
		t.Fatalf("opaque start response = %q", start.Body.String())
	}
	legacy := httptest.NewRecorder()
	routes.ServeHTTP(legacy, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if legacy.Body.String() != "legacy" {
		t.Fatalf("legacy fallback response = %q", legacy.Body.String())
	}
}

func TestPreviewCursorKeyFailsClosedAndAcceptsBoundedSecret(t *testing.T) {
	shortPath := filepath.Join(t.TempDir(), "short")
	if err := os.WriteFile(shortPath, []byte("short"), 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv(previewCursorKeyFileEnv, shortPath)
	if _, err := previewCursorKey(); err == nil {
		t.Fatal("short cursor key was accepted")
	}
	keyPath := filepath.Join(t.TempDir(), "key")
	if err := os.WriteFile(keyPath, []byte(strings.Repeat("k", 32)), 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv(previewCursorKeyFileEnv, keyPath)
	key, err := previewCursorKey()
	if err != nil || len(key) < 32 {
		t.Fatalf("cursor key length=%d err=%v", len(key), err)
	}
}

// Byline: Codex · GPT-5.6-Terra · 2026-08-30.
package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPlatformDatabaseURLReadsRuntimeFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "database-url")
	const dsn = "postgresql://runtime:secret@postgres/platform"
	if err := os.WriteFile(path, []byte(dsn+"\r\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv(platformDatabaseURLFileEnv, path)
	got, err := platformDatabaseURL()
	if err != nil || got != dsn {
		t.Fatalf("platformDatabaseURL() = %q, %v", got, err)
	}
}

func TestPlatformDatabaseURLFailsClosedWithoutLeaking(t *testing.T) {
	path := filepath.Join(t.TempDir(), "missing-secret")
	t.Setenv(platformDatabaseURLFileEnv, path)
	_, err := platformDatabaseURL()
	if err == nil || strings.Contains(err.Error(), path) {
		t.Fatalf("platformDatabaseURL() error = %v, want generic non-leaking failure", err)
	}
}

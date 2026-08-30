package main

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

const (
	previewCursorKeyFileEnv        = "UIW_PREVIEW_CURSOR_KEY_FILE"
	previewServiceTokenFileEnv     = "UIW_SERVICE_TOKEN_FILE"
	defaultPreviewCursorKeyFile    = "/run/secrets/uiw-preview-cursor-key"
	defaultPreviewServiceTokenFile = "/run/secrets/uiw-service-token"
)

func previewCursorKey() ([]byte, error) {
	return readRuntimeSecret(previewCursorKeyFileEnv, defaultPreviewCursorKeyFile)
}

func previewServiceTokenFile() (string, error) {
	path := strings.TrimSpace(os.Getenv(previewServiceTokenFileEnv))
	if path == "" {
		path = defaultPreviewServiceTokenFile
	}
	if _, err := readRuntimeSecret(previewServiceTokenFileEnv, defaultPreviewServiceTokenFile); err != nil {
		return "", err
	}
	return path, nil
}

func readRuntimeSecret(envName, defaultPath string) ([]byte, error) {
	path := strings.TrimSpace(os.Getenv(envName))
	if path == "" {
		path = defaultPath
	}
	if !filepath.IsAbs(path) {
		return nil, fmt.Errorf("%s must name an absolute file", envName)
	}
	info, err := os.Lstat(path)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", envName, err)
	}
	if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 || info.Size() < 32 || info.Size() > 4098 {
		return nil, fmt.Errorf("%s must be a safe regular file of 32-4098 bytes", envName)
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	raw, err := io.ReadAll(io.LimitReader(file, 4099))
	if err != nil {
		return nil, err
	}
	raw = bytes.TrimRight(raw, "\r\n")
	if len(raw) < 32 || len(raw) > 4096 || bytes.IndexByte(raw, 0) >= 0 {
		return nil, fmt.Errorf("%s contains an invalid bounded secret", envName)
	}
	return append([]byte(nil), raw...), nil
}

// mountPreviewRoutes gives the opaque preview contract ownership of the new
// start/read/decision surface while preserving the legacy workflow-id routes
// as an internal compatibility fallback.
func mountPreviewRoutes(existing, preview http.Handler) (http.Handler, error) {
	if existing == nil || preview == nil {
		return nil, errors.New("preview routes require existing and preview handlers")
	}
	mux := http.NewServeMux()
	mux.Handle("POST /reference-import/start", preview)
	mux.Handle("GET /reference-import/previews/", preview)
	mux.Handle("POST /reference-import/previews/", preview)
	mux.Handle("/", existing)
	return mux, nil
}

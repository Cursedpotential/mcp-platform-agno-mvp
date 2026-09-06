// Byline: Codex · GPT-5 · 2026-08-28 (authenticated Proffer upload ingress mount)
package main

import (
	"errors"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/Cursedpotential/probata/engine/acquisition"
)

const (
	uploadIngressPath = "/acquisition/upload"
	uploadMaxBytesEnv = "PROFFER_UPLOAD_MAX_BYTES"
)

// newUploadIngress builds the starter's bounded upload surface from deployment
// configuration. The root is deliberately SOURCE_OBJECT_DIR: the worker and
// starter must resolve the same content-addressed object store.
func newUploadIngress() (*acquisition.UploadIngress, error) {
	root := strings.TrimSpace(os.Getenv("SOURCE_OBJECT_DIR"))
	maxBytes, err := positiveEnvInt64(uploadMaxBytesEnv)
	if err != nil {
		return nil, err
	}
	ingress, err := acquisition.NewUploadIngress(acquisition.UploadIngressConfig{
		Root:     root,
		MaxBytes: maxBytes,
	})
	if err != nil {
		return nil, err
	}
	return ingress, nil
}

func positiveEnvInt64(name string) (int64, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return 0, fmt.Errorf("%s is required", name)
	}
	value, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || value <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", name)
	}
	return value, nil
}

// starterRoutes preserves the existing Temporal routes and adds one exact,
// tailnet-authorized upload route. UploadIngress owns peer checking and body
// limits; the starter only mounts it, so no token or bytes enter workflow
// payloads.
func starterRoutes(existing http.Handler, ingress *acquisition.UploadIngress) (http.Handler, error) {
	if existing == nil {
		return nil, errors.New("starter routes require the existing handler")
	}
	if ingress == nil {
		return nil, errors.New("starter routes require an upload ingress")
	}
	mux := http.NewServeMux()
	mux.Handle("POST "+uploadIngressPath, ingress)
	mux.Handle("/", existing)
	return mux, nil
}

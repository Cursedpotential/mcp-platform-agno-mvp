// Object-storage credential loading from the platform's existing secret file.
//
// The Python side (modules/workbench/api/app/repo/object_store_client.py) already
// reads this exact JSON shape from CASEBIBLE_R2_CONFIG_PATH. Go reads the SAME
// file rather than inventing a second credential format — until now no Go code
// read it at all, which is why the worker could not resolve r2:// references
// even though the resolver existed (see D-132).
//
// Byline: Claude Code · Opus 5 · 2026-09-02.
package acquisition

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// maxObjectStorageConfigBytes bounds the credential file. A credential document
// is small; anything larger is a misconfiguration, not a secret.
const maxObjectStorageConfigBytes = 64 << 10

// objectStorageConfigFile mirrors the field names the Python client already
// requires: endpoint_url, region, access_key_id, secret_access_key, and the
// optional session_token.
type objectStorageConfigFile struct {
	EndpointURL     string `json:"endpoint_url"`
	Region          string `json:"region"`
	AccessKeyID     string `json:"access_key_id"`
	SecretAccessKey string `json:"secret_access_key"`
	SessionToken    string `json:"session_token"`
}

// LoadObjectStorageConfigFile reads an S3-compatible credential document from an
// absolute path and returns it as an ObjectStorageConfig.
//
// Errors never quote the file's contents: a malformed credential file must not
// spill key material into a log line.
func LoadObjectStorageConfigFile(path string) (ObjectStorageConfig, error) {
	trimmed := strings.TrimSpace(path)
	if trimmed == "" {
		return ObjectStorageConfig{}, errors.New("acquisition: object storage config path is required")
	}
	if trimmed != path || !filepath.IsAbs(path) {
		return ObjectStorageConfig{}, errors.New("acquisition: object storage config path must be absolute and unpadded")
	}
	info, err := os.Stat(path)
	if err != nil {
		return ObjectStorageConfig{}, fmt.Errorf("acquisition: stat object storage config: %w", err)
	}
	if !info.Mode().IsRegular() {
		return ObjectStorageConfig{}, errors.New("acquisition: object storage config must be a regular file")
	}
	if info.Size() > maxObjectStorageConfigBytes {
		return ObjectStorageConfig{}, errors.New("acquisition: object storage config file is implausibly large")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return ObjectStorageConfig{}, fmt.Errorf("acquisition: read object storage config: %w", err)
	}
	var parsed objectStorageConfigFile
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&parsed); err != nil {
		return ObjectStorageConfig{}, errors.New("acquisition: object storage config is not a JSON object with the expected fields")
	}
	cfg := ObjectStorageConfig{
		Endpoint:        strings.TrimSpace(parsed.EndpointURL),
		Region:          strings.TrimSpace(parsed.Region),
		AccessKeyID:     strings.TrimSpace(parsed.AccessKeyID),
		SecretAccessKey: strings.TrimSpace(parsed.SecretAccessKey),
		SessionToken:    strings.TrimSpace(parsed.SessionToken),
		UsePathStyle:    true,
	}
	if err := cfg.validate("configured"); err != nil {
		return ObjectStorageConfig{}, err
	}
	return cfg, nil
}

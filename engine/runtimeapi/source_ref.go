// Byline: Codex · GPT-5.6-Sol · 2026-08-30 (fixed UIW source authority)
package runtimeapi

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/url"
	"strings"
)

func validateAuthorizedSourceRef(value string) (string, string, error) {
	parsed, err := url.Parse(strings.TrimSpace(value))
	if err != nil || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return "", "", errors.New("source_ref must be an upload reference or a Case Bible Sorted object")
	}
	if parsed.Scheme == "upload" && parsed.Path == "" {
		digest := strings.ToLower(parsed.Host)
		raw, decodeErr := hex.DecodeString(digest)
		if decodeErr == nil && len(raw) == sha256.Size {
			return "upload", digest, nil
		}
	}
	if parsed.Scheme == "r2" && parsed.Host == "casebible-sorted" {
		key, unescapeErr := url.PathUnescape(strings.TrimPrefix(parsed.EscapedPath(), "/"))
		if unescapeErr == nil && key != "" && !strings.HasPrefix(key, "/") && !strings.Contains(key, `\`) {
			valid := true
			for _, segment := range strings.Split(key, "/") {
				if segment == ".." {
					valid = false
					break
				}
			}
			if valid {
				return "r2", key, nil
			}
		}
	}
	return "", "", errors.New("source_ref must be an upload reference or a Case Bible Sorted object")
}

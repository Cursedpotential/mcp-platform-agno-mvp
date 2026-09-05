// Byline: Codex · GPT-5.6-Sol · 2026-08-30 (fixed UIW source authority)
package runtimeapi

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/url"
	"os"
	"strings"
)

// devFixtureBucket / devFixturePrefix name the ONLY non-canonical R2 location a
// UIW run may start from, and only while PLATFORM_DEV_AUTH_BYPASS is set
// (D-125/D-127: the dev flag is the single switch for every dev-only
// admission). Synthetic rehearsal fixtures live there so they never touch
// casebible-sorted (owner rule: test data must never become canonical).
// Live finding 2026-09-05: the tool gateway's R2 resolver is proven against
// r2://nexus/uiw/test-fixtures/…, but this allowlist rejected it at the API.
// Production source authority (upload:// or Case Bible Sorted) is unchanged.
const (
	devFixtureBucket = "nexus"
	devFixturePrefix = "uiw/test-fixtures/"
)

func devFixtureSourcesEnabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("PLATFORM_DEV_AUTH_BYPASS"))) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

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
	devFixture := parsed.Scheme == "r2" && parsed.Host == devFixtureBucket && devFixtureSourcesEnabled()
	if parsed.Scheme == "r2" && (parsed.Host == "casebible-sorted" || devFixture) {
		key, unescapeErr := url.PathUnescape(strings.TrimPrefix(parsed.EscapedPath(), "/"))
		if devFixture && !strings.HasPrefix(key, devFixturePrefix) {
			return "", "", errors.New("source_ref must be an upload reference or a Case Bible Sorted object")
		}
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

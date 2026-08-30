// Byline: Codex · GPT-5.6-Terra · 2026-08-30.
package temporal

import (
	"errors"
	"io"
	"os"
	"strings"
	"unicode"
	"unicode/utf8"
)

const runtimeSecretError = "temporal: runtime secret file is unavailable or invalid"

// ReadRuntimeSecretFile reads one bounded UTF-8 runtime secret without
// following a symlink. Only trailing CR/LF record separators are removed;
// whitespace that is part of the secret is preserved.
func ReadRuntimeSecretFile(path string, maxBytes int) (string, error) {
	invalid := func() (string, error) { return "", errors.New(runtimeSecretError) }
	if maxBytes <= 0 || !isAbsoluteRuntimePath(path) {
		return invalid()
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
		return invalid()
	}
	file, err := os.Open(path)
	if err != nil {
		return invalid()
	}
	defer file.Close()
	openedInfo, err := file.Stat()
	if err != nil || !openedInfo.Mode().IsRegular() || !os.SameFile(info, openedInfo) {
		return invalid()
	}
	raw, err := io.ReadAll(io.LimitReader(file, int64(maxBytes+3)))
	if err != nil || len(raw) == 0 || len(raw) > maxBytes+2 || !utf8.Valid(raw) {
		return invalid()
	}
	value := strings.TrimRight(string(raw), "\r\n")
	if value == "" || len(value) > maxBytes {
		return invalid()
	}
	for _, r := range value {
		if unicode.IsControl(r) {
			return invalid()
		}
	}
	return value, nil
}

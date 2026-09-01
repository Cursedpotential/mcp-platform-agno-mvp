// Byline: Codex · GPT-5.6-Terra · 2026-08-30.
package main

import (
	"errors"
	"os"
	"strings"

	platformtemporal "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/temporal"
)

const (
	platformDatabaseURLFileEnv     = "PLATFORM_DATABASE_URL_FILE"
	defaultPlatformDatabaseURLFile = "/run/secrets/platform-database-url"
	maxPlatformDatabaseURLBytes    = 16 << 10
)

func platformDatabaseURL() (string, error) {
	path := strings.TrimSpace(os.Getenv(platformDatabaseURLFileEnv))
	if path == "" {
		path = defaultPlatformDatabaseURLFile
	}
	value, err := platformtemporal.ReadRuntimeSecretFile(path, maxPlatformDatabaseURLBytes)
	if err != nil {
		return "", errors.New("configure platform preview database: unavailable or invalid")
	}
	return value, nil
}

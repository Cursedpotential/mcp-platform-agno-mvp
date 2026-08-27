// Package uiwworker composes the production Temporal worker for the single
// UniversalImportWorkflow. It is the only Go process allowed to poll the
// dedicated UIW task queue, and it registers every canonical stage body.
package uiwworker

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	platformtemporal "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/temporal"
)

const legacyEvidenceTaskQueue = "evidence-pipeline"

// Config contains only production worker settings. Secrets are held in
// memory and are never included in validation errors or log fields.
type Config struct {
	TemporalHostPort  string
	TemporalNamespace string
	TemporalTaskQueue string
	DatabaseURL       string

	SourceObjectDir      string
	ParserBundleDir      string
	NormalizedBundleDir  string
	InventoryManifestDir string

	N8NBaseURL         string
	N8NAuthHeader      string
	N8NAuthValue       string
	SelectHTTPTimeout  time.Duration
	ExecuteHTTPTimeout time.Duration
}

// LoadConfig reads the fail-closed worker environment contract. The worker
// intentionally uses TEMPORAL_TASK_QUEUE too, so the separately deployed HTTP
// starter can target the same queue without a second naming convention.
func LoadConfig() (Config, error) {
	var problems []string
	require := func(name string) string {
		value := strings.TrimSpace(os.Getenv(name))
		if value == "" {
			problems = append(problems, name+" is required")
		}
		return value
	}

	cfg := Config{
		TemporalHostPort:     require("TEMPORAL_HOST_PORT"),
		TemporalNamespace:    require("TEMPORAL_NAMESPACE"),
		TemporalTaskQueue:    require("TEMPORAL_TASK_QUEUE"),
		DatabaseURL:          firstEnvironment("PLATFORM_DATABASE_URL", "DATABASE_URL"),
		SourceObjectDir:      require("SOURCE_OBJECT_DIR"),
		ParserBundleDir:      require("PARSER_BUNDLE_DIR"),
		NormalizedBundleDir:  require("NORMALIZED_BUNDLE_DIR"),
		InventoryManifestDir: require("INVENTORY_MANIFEST_DIR"),
		N8NBaseURL:           strings.TrimRight(require("N8N_UNIVERSAL_IMPORT_BASE_URL"), "/"),
		N8NAuthHeader:        require("N8N_UNIVERSAL_IMPORT_AUTH_HEADER"),
		N8NAuthValue:         require("N8N_UNIVERSAL_IMPORT_AUTH_VALUE"),
		SelectHTTPTimeout:    35 * time.Second,
		ExecuteHTTPTimeout:   31 * time.Minute,
	}
	if cfg.DatabaseURL == "" {
		problems = append(problems, "PLATFORM_DATABASE_URL or DATABASE_URL is required")
	}
	if cfg.TemporalTaskQueue == legacyEvidenceTaskQueue {
		problems = append(problems, "TEMPORAL_TASK_QUEUE must be dedicated to universal import and cannot be evidence-pipeline")
	}
	if timeout, err := optionalDuration("SELECT_PARSER_HTTP_TIMEOUT", cfg.SelectHTTPTimeout); err != nil {
		problems = append(problems, err.Error())
	} else {
		cfg.SelectHTTPTimeout = timeout
	}
	if timeout, err := optionalDuration("EXECUTE_PARSER_HTTP_TIMEOUT", cfg.ExecuteHTTPTimeout); err != nil {
		problems = append(problems, err.Error())
	} else {
		cfg.ExecuteHTTPTimeout = timeout
	}
	if len(problems) > 0 {
		return Config{}, fmt.Errorf("uiw worker: invalid configuration: %s", strings.Join(problems, "; "))
	}
	return cfg, nil
}

func firstEnvironment(names ...string) string {
	for _, name := range names {
		if value := strings.TrimSpace(os.Getenv(name)); value != "" {
			return value
		}
	}
	return ""
}

func optionalDuration(name string, fallback time.Duration) (time.Duration, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	value, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be a valid Go duration: %w", name, err)
	}
	if value <= 0 {
		return 0, errors.New(name + " must be a positive duration")
	}
	return value, nil
}

func (c Config) temporalConfig() platformtemporal.Config {
	return platformtemporal.Config{
		TemporalHostPort:   c.TemporalHostPort,
		TemporalNamespace:  c.TemporalNamespace,
		TemporalTaskQueue:  c.TemporalTaskQueue,
		N8NBaseURL:         c.N8NBaseURL,
		N8NAuthHeader:      c.N8NAuthHeader,
		N8NAuthValue:       c.N8NAuthValue,
		SelectHTTPTimeout:  c.SelectHTTPTimeout,
		ExecuteHTTPTimeout: c.ExecuteHTTPTimeout,
	}
}

// validateSharedPaths requires four explicit, non-overlapping absolute roots.
// Coolify mounts these exact paths into both the parser runtime and this
// worker; relative or nested roots would make stored file:// references
// ambiguous across services and are rejected before Temporal polling begins.
func validateSharedPaths(c Config) error {
	paths := map[string]string{
		"SOURCE_OBJECT_DIR":      c.SourceObjectDir,
		"PARSER_BUNDLE_DIR":      c.ParserBundleDir,
		"NORMALIZED_BUNDLE_DIR":  c.NormalizedBundleDir,
		"INVENTORY_MANIFEST_DIR": c.InventoryManifestDir,
	}
	clean := make(map[string]string, len(paths))
	for name, path := range paths {
		if !filepath.IsAbs(path) {
			return fmt.Errorf("uiw worker: %s must be an absolute shared path", name)
		}
		clean[name] = filepath.Clean(path)
	}
	for leftName, left := range clean {
		for rightName, right := range clean {
			if leftName >= rightName {
				continue
			}
			if sameOrNestedPath(left, right) || sameOrNestedPath(right, left) {
				return fmt.Errorf("uiw worker: shared paths %s and %s must be separate non-nested roots", leftName, rightName)
			}
		}
	}
	return nil
}

func sameOrNestedPath(parent, candidate string) bool {
	relative, err := filepath.Rel(parent, candidate)
	if err != nil {
		return false
	}
	return relative == "." || (relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator)))
}

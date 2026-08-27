package temporal

import (
	"strings"
	"testing"
)

func clearConfigEnv(t *testing.T) {
	t.Helper()
	names := []string{
		"TEMPORAL_HOST_PORT", "TEMPORAL_NAMESPACE", "TEMPORAL_TASK_QUEUE",
		"N8N_UNIVERSAL_IMPORT_BASE_URL", "N8N_UNIVERSAL_IMPORT_AUTH_HEADER", "N8N_UNIVERSAL_IMPORT_AUTH_VALUE",
		"REFERENCE_STARTER_TOKEN", "REFERENCE_STARTER_ADDR",
		"SELECT_PARSER_HTTP_TIMEOUT", "EXECUTE_PARSER_HTTP_TIMEOUT",
	}
	for _, name := range names {
		t.Setenv(name, "")
	}
}

func setRequiredConfigEnv(t *testing.T) {
	t.Helper()
	t.Setenv("TEMPORAL_HOST_PORT", "temporal-frontend:7233")
	t.Setenv("TEMPORAL_NAMESPACE", "default")
	t.Setenv("TEMPORAL_TASK_QUEUE", "universal-import-reference")
	t.Setenv("N8N_UNIVERSAL_IMPORT_BASE_URL", "https://n8n.example.com/webhook/")
	t.Setenv("N8N_UNIVERSAL_IMPORT_AUTH_HEADER", "Authorization")
	t.Setenv("N8N_UNIVERSAL_IMPORT_AUTH_VALUE", "Bearer test-token")
	t.Setenv("REFERENCE_STARTER_TOKEN", "starter-token")
}

func TestLoadConfigSucceedsWithAllRequiredVars(t *testing.T) {
	clearConfigEnv(t)
	setRequiredConfigEnv(t)

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig() error = %v, want nil", err)
	}
	if cfg.N8NBaseURL != "https://n8n.example.com/webhook" {
		t.Errorf("N8NBaseURL = %q, want trailing slash trimmed", cfg.N8NBaseURL)
	}
	if cfg.StarterAddr != defaultStarterAddr {
		t.Errorf("StarterAddr = %q, want default %q", cfg.StarterAddr, defaultStarterAddr)
	}
	if cfg.SelectHTTPTimeout != defaultSelectHTTPTimeout {
		t.Errorf("SelectHTTPTimeout = %v, want default %v", cfg.SelectHTTPTimeout, defaultSelectHTTPTimeout)
	}
	if cfg.ExecuteHTTPTimeout != defaultExecuteHTTPTimeout {
		t.Errorf("ExecuteHTTPTimeout = %v, want default %v", cfg.ExecuteHTTPTimeout, defaultExecuteHTTPTimeout)
	}
}

func TestLoadConfigCollectsEveryMissingVar(t *testing.T) {
	clearConfigEnv(t)

	_, err := LoadConfig()
	if err == nil {
		t.Fatal("LoadConfig() error = nil, want a combined error naming every missing var")
	}
	for _, name := range []string{
		"TEMPORAL_HOST_PORT", "TEMPORAL_NAMESPACE", "TEMPORAL_TASK_QUEUE",
		"N8N_UNIVERSAL_IMPORT_BASE_URL", "N8N_UNIVERSAL_IMPORT_AUTH_HEADER", "N8N_UNIVERSAL_IMPORT_AUTH_VALUE",
		"REFERENCE_STARTER_TOKEN",
	} {
		if !strings.Contains(err.Error(), name) {
			t.Errorf("LoadConfig() error %q does not mention missing var %q", err.Error(), name)
		}
	}
}

func TestLoadConfigRejectsInvalidDuration(t *testing.T) {
	clearConfigEnv(t)
	setRequiredConfigEnv(t)
	t.Setenv("SELECT_PARSER_HTTP_TIMEOUT", "not-a-duration")

	_, err := LoadConfig()
	if err == nil {
		t.Fatal("LoadConfig() error = nil, want an error for an invalid duration")
	}
	if !strings.Contains(err.Error(), "SELECT_PARSER_HTTP_TIMEOUT") {
		t.Errorf("LoadConfig() error %q does not name the invalid var", err.Error())
	}
}

func TestLoadConfigRejectsNonPositiveDuration(t *testing.T) {
	clearConfigEnv(t)
	setRequiredConfigEnv(t)
	t.Setenv("EXECUTE_PARSER_HTTP_TIMEOUT", "0s")

	_, err := LoadConfig()
	if err == nil {
		t.Fatal("LoadConfig() error = nil, want an error for a non-positive duration")
	}
}

func TestLoadConfigHonorsOverrides(t *testing.T) {
	clearConfigEnv(t)
	setRequiredConfigEnv(t)
	t.Setenv("REFERENCE_STARTER_ADDR", ":9999")
	t.Setenv("SELECT_PARSER_HTTP_TIMEOUT", "10s")
	t.Setenv("EXECUTE_PARSER_HTTP_TIMEOUT", "5m")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig() error = %v, want nil", err)
	}
	if cfg.StarterAddr != ":9999" {
		t.Errorf("StarterAddr = %q, want override", cfg.StarterAddr)
	}
	if cfg.SelectHTTPTimeout.String() != "10s" {
		t.Errorf("SelectHTTPTimeout = %v, want 10s", cfg.SelectHTTPTimeout)
	}
	if cfg.ExecuteHTTPTimeout.String() != "5m0s" {
		t.Errorf("ExecuteHTTPTimeout = %v, want 5m", cfg.ExecuteHTTPTimeout)
	}
}

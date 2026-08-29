package temporal

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"time"
)

// Config is every environment-derived setting this package's worker and
// starter HTTP service need. LoadConfig fails closed: it collects every
// missing or invalid variable into one error rather than letting a process
// start half-configured and fail confusingly later.
type Config struct {
	// TemporalHostPort is the Temporal frontend address, e.g.
	// "temporal-frontend:7233".
	TemporalHostPort string
	// TemporalNamespace is the Temporal namespace this worker and starter
	// operate in.
	TemporalNamespace string
	// TemporalTaskQueue is the task queue engine/uiw.UniversalImportWorkflow
	// and this package's two Activities are registered and dispatched on.
	TemporalTaskQueue string

	// N8NBaseURL is the n8n webhook base, e.g. "https://n8n.example.com/webhook".
	// The two stage paths are appended to it verbatim (no trailing slash
	// assumed either way).
	N8NBaseURL string
	// N8NAuthHeader/N8NAuthValue are the header name/value this package sends
	// on every call to the n8n webhooks, matching the headerAuth credential
	// the two existing n8n workflows now require on their Webhook trigger
	// nodes (docker/n8n/workflows/universal-import/README.md).
	N8NAuthHeader string
	N8NAuthValue  string

	// StarterAddr is the HTTP listen address for the starter service n8n's
	// start/decision/preview workflows call.
	StarterAddr string

	// SelectHTTPTimeout/ExecuteHTTPTimeout bound this package's own HTTP call
	// to n8n for each stage. They are sized slightly above the corresponding
	// n8n HTTP node timeout (30s / 1,800,000ms) so a slow-but-honest n8n
	// response is not cut off first by our own leg of the call.
	SelectHTTPTimeout  time.Duration
	ExecuteHTTPTimeout time.Duration
}

const (
	defaultSelectHTTPTimeout  = 35 * time.Second
	defaultExecuteHTTPTimeout = 31 * time.Minute
	defaultStarterAddr        = ":8091"
)

// LoadConfig reads every required environment variable, trims it, and
// returns a combined error naming every problem at once — never just the
// first one found — so a misconfigured deployment can be fixed in one pass.
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
		TemporalHostPort:  require("TEMPORAL_HOST_PORT"),
		TemporalNamespace: require("TEMPORAL_NAMESPACE"),
		TemporalTaskQueue: require("TEMPORAL_TASK_QUEUE"),
		N8NBaseURL:        strings.TrimRight(require("N8N_UNIVERSAL_IMPORT_BASE_URL"), "/"),
		N8NAuthHeader:     require("N8N_UNIVERSAL_IMPORT_AUTH_HEADER"),
		N8NAuthValue:      require("N8N_UNIVERSAL_IMPORT_AUTH_VALUE"),
	}

	cfg.StarterAddr = strings.TrimSpace(os.Getenv("REFERENCE_STARTER_ADDR"))
	if cfg.StarterAddr == "" {
		cfg.StarterAddr = defaultStarterAddr
	}

	var err error
	cfg.SelectHTTPTimeout, err = optionalDuration("SELECT_PARSER_HTTP_TIMEOUT", defaultSelectHTTPTimeout)
	if err != nil {
		problems = append(problems, err.Error())
	}
	cfg.ExecuteHTTPTimeout, err = optionalDuration("EXECUTE_PARSER_HTTP_TIMEOUT", defaultExecuteHTTPTimeout)
	if err != nil {
		problems = append(problems, err.Error())
	}

	if len(problems) > 0 {
		return Config{}, fmt.Errorf("temporal: invalid configuration: %s", strings.Join(problems, "; "))
	}
	return cfg, nil
}

func optionalDuration(name string, fallback time.Duration) (time.Duration, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	d, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be a valid Go duration (e.g. \"30s\"): %w", name, err)
	}
	if d <= 0 {
		return 0, errors.New(name + " must be a positive duration")
	}
	return d, nil
}

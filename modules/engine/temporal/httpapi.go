// Byline: Claude Code · Sonnet 5 · 2026-09-02 (BUILD LANE N2, D-125/D-127):
// PLATFORM_DEV_AUTH_BYPASS now honored by withAuth. Flag OFF (default,
// unset, or any non-truthy value) is unchanged strict behavior -- only a
// tailnet-ranged r.RemoteAddr is authorized. Flag ON does not remove the
// tailnet check; it relaxes what happens when that check fails: the request
// is admitted, but every admission logs a WARN line naming the flag, the
// rejected RemoteAddr, and the route, so a flag-relaxed request is never
// silent (D-127 Rule 5). See engine/postgres/uiw_schema_probe.go for the
// sibling admission surface this flag also governs (D-126).
package temporal

import (
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"strings"

	"github.com/google/uuid"

	"github.com/Cursedpotential/probata/engine/proffer"
)

const maxStarterRequestBytes int64 = 16 << 10

// StarterHTTPHandler is the HTTP surface n8n's start/decision/preview
// workflows call, since n8n has no native Temporal client. It is a thin,
// tailnet-authorized shim over WorkflowStarter: it decodes/validates JSON,
// delegates to Temporal, and reports back — it holds no business logic and
// no Temporal SDK dependency of its own beyond what WorkflowStarter exposes.
type StarterHTTPHandler struct {
	starter WorkflowStarter
}

// NewStarterHTTPHandler constructs a fail-closed handler: a nil starter is
// rejected rather than creating an endpoint that cannot do anything.
func NewStarterHTTPHandler(starter WorkflowStarter) (*StarterHTTPHandler, error) {
	if starter == nil {
		return nil, errors.New("temporal: starter HTTP handler requires a WorkflowStarter")
	}
	if devAuthBypassEnabled() {
		slog.Warn("Proffer starter HTTP auth: PLATFORM_DEV_AUTH_BYPASS is set -- non-tailnet peers will be admitted to reference-import routes, each admission logged individually (D-125, D-127); remove this flag before go-live",
			"flag", platformDevAuthBypassEnv)
	}
	return &StarterHTTPHandler{starter: starter}, nil
}

// Routes returns the mux n8n's three workflows call:
//
//	POST /reference-import/start                    -- begin a run
//	POST /reference-import/{workflow_id}/decision    -- approve/reject a held run
//	GET  /reference-import/{workflow_id}/preview     -- read the current preview state
//	GET  /healthz                                    -- unauthenticated liveness probe
func (h *StarterHTTPHandler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeStarterJSON(w, http.StatusOK, map[string]any{"status": "ok"})
	})
	mux.HandleFunc("POST /reference-import/start", h.withAuth(h.handleStart))
	mux.HandleFunc("POST /reference-import/{workflow_id}/decision", h.withAuth(h.handleDecision))
	mux.HandleFunc("GET /reference-import/{workflow_id}/preview", h.withAuth(h.handlePreview))
	return securityHeaders(mux)
}

func (h *StarterHTTPHandler) withAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// D-127 Rule 4: the tailnet check itself stays intact and is always
		// evaluated -- the flag never deletes it, it only decides what
		// happens when it fails.
		if authorizedTailnetPeer(r) {
			next(w, r)
			return
		}
		if devAuthBypassEnabled() {
			// D-127 Rule 5: never suppress a relaxed check into silence.
			// One WARN line per admitted-but-would-have-been-rejected
			// request, naming the flag, the rejected peer, and the route.
			slog.Warn("Proffer starter HTTP auth: PLATFORM_DEV_AUTH_BYPASS admitted a non-tailnet peer (D-125, D-127) -- remove this flag before go-live",
				"flag", platformDevAuthBypassEnv,
				"remote_addr", r.RemoteAddr,
				"method", r.Method,
				"path", r.URL.Path)
			next(w, r)
			return
		}
		writeStarterError(w, http.StatusUnauthorized, errors.New("reference import starter authorization required"))
	}
}

// startRequest mirrors engine/proffer.WorkflowInput exactly: this starts the
// real ProfferWorkflow from its actual root input (the raw,
// not-yet-retained acquisition reference), not a partially-observed
// mid-pipeline state.
type startRequest struct {
	RequestID        string `json:"request_id"`
	MatterID         string `json:"matter_id"`
	CourtCaseID      string `json:"court_case_id"`
	SourceRef        string `json:"source_ref"`
	DeclaredFormat   string `json:"declared_format"`
	ParserOptionsRef string `json:"parser_options_ref"`
}

type startResponse struct {
	WorkflowID string `json:"workflow_id"`
	RunID      string `json:"run_id"`
}

func (h *StarterHTTPHandler) handleStart(w http.ResponseWriter, r *http.Request) {
	var req startRequest
	if err := decodeStarterJSON(w, r, maxStarterRequestBytes, &req); err != nil {
		writeStarterError(w, http.StatusBadRequest, err)
		return
	}
	if err := validateStartRequest(req); err != nil {
		writeStarterError(w, http.StatusBadRequest, err)
		return
	}

	in := proffer.WorkflowInput{
		RequestID:        req.RequestID,
		MatterID:         req.MatterID,
		CourtCaseID:      req.CourtCaseID,
		SourceRef:        proffer.Ref(req.SourceRef),
		DeclaredFormat:   req.DeclaredFormat,
		ParserOptionsRef: proffer.Ref(req.ParserOptionsRef),
	}
	workflowID, runID, err := h.starter.Start(r.Context(), in)
	if err != nil {
		writeStarterError(w, http.StatusUnprocessableEntity, err)
		return
	}
	writeStarterJSON(w, http.StatusCreated, startResponse{WorkflowID: workflowID, RunID: runID})
}

func validateStartRequest(req startRequest) error {
	if strings.TrimSpace(req.RequestID) == "" {
		return errors.New("start request requires request_id")
	}
	if strings.TrimSpace(req.SourceRef) == "" {
		return errors.New("start request requires source_ref")
	}
	if strings.TrimSpace(req.DeclaredFormat) == "" {
		return errors.New("start request requires declared_format")
	}
	if strings.TrimSpace(req.ParserOptionsRef) == "" {
		return errors.New("start request requires parser_options_ref")
	}
	if _, err := uuid.Parse(strings.TrimSpace(req.MatterID)); err != nil {
		return errors.New("start request requires a valid matter_id UUID")
	}
	if _, err := uuid.Parse(strings.TrimSpace(req.CourtCaseID)); err != nil {
		return errors.New("start request requires a valid court_case_id UUID")
	}
	return nil
}

type decisionRequest struct {
	Approved bool   `json:"approved"`
	Reason   string `json:"reason"`
	Decider  string `json:"decider"`
}

func (h *StarterHTTPHandler) handleDecision(w http.ResponseWriter, r *http.Request) {
	workflowID := r.PathValue("workflow_id")
	if strings.TrimSpace(workflowID) == "" {
		writeStarterError(w, http.StatusBadRequest, errors.New("decision request requires a workflow_id path segment"))
		return
	}
	var req decisionRequest
	if err := decodeStarterJSON(w, r, maxStarterRequestBytes, &req); err != nil {
		writeStarterError(w, http.StatusBadRequest, err)
		return
	}
	if strings.TrimSpace(req.Decider) == "" {
		writeStarterError(w, http.StatusBadRequest, errors.New("decision request requires decider"))
		return
	}
	if !req.Approved && strings.TrimSpace(req.Reason) == "" {
		writeStarterError(w, http.StatusBadRequest, errors.New("a rejection decision requires a non-empty reason"))
		return
	}
	if err := h.starter.Decide(r.Context(), workflowID, proffer.PreviewDecision{
		Approved: req.Approved,
		Reason:   req.Reason,
		Decider:  req.Decider,
	}); err != nil {
		writeStarterError(w, http.StatusUnprocessableEntity, err)
		return
	}
	writeStarterJSON(w, http.StatusOK, map[string]any{"status": "signaled"})
}

func (h *StarterHTTPHandler) handlePreview(w http.ResponseWriter, r *http.Request) {
	workflowID := r.PathValue("workflow_id")
	if strings.TrimSpace(workflowID) == "" {
		writeStarterError(w, http.StatusBadRequest, errors.New("preview request requires a workflow_id path segment"))
		return
	}
	state, err := h.starter.Preview(r.Context(), workflowID)
	if err != nil {
		writeStarterError(w, http.StatusUnprocessableEntity, err)
		return
	}
	writeStarterJSON(w, http.StatusOK, previewResponse{
		Phase:     string(state.Phase),
		SelectRef: string(state.SelectRef),
		Reason:    state.Reason,
	})
}

type previewResponse struct {
	Phase     string `json:"phase"`
	SelectRef string `json:"select_ref"`
	Reason    string `json:"reason,omitempty"`
}

func authorizedTailnetPeer(r *http.Request) bool {
	host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
	if err != nil {
		return false
	}
	ip := net.ParseIP(host).To4()
	return ip != nil && ip[0] == 100 && ip[1] >= 64 && ip[1] <= 127
}

// platformDevAuthBypassEnv is the one flag D-125 defines for every ingest
// surface (this starter HTTP layer, the Workbench BFF, and -- per D-126 --
// engine/postgres's schema-admission probe). Default OFF, fail-closed:
// unset or anything but a truthy value means STRICT, i.e. unchanged
// tailnet-only behavior.
const platformDevAuthBypassEnv = "PLATFORM_DEV_AUTH_BYPASS"

// devAuthBypassEnabled reads PLATFORM_DEV_AUTH_BYPASS directly rather than
// taking a parameter, mirroring engine/postgres.devAuthBypassEnabled: D-125
// defines one process-wide flag, not a value threaded through every caller.
// Truthy values match D-125's own documented example
// (PLATFORM_DEV_AUTH_BYPASS=1) plus the usual spellings; anything else,
// including unset, is OFF (fail-closed default).
func devAuthBypassEnabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv(platformDevAuthBypassEnv))) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		next.ServeHTTP(w, r)
	})
}

func decodeStarterJSON(w http.ResponseWriter, r *http.Request, maxBytes int64, dest any) error {
	if r.ContentLength > maxBytes {
		return errors.New("request exceeds maximum allowed size")
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxBytes))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dest); err != nil {
		return err
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			return errors.New("request must contain exactly one JSON object")
		}
		return err
	}
	return nil
}

func writeStarterJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func writeStarterError(w http.ResponseWriter, status int, err error) {
	writeStarterJSON(w, status, struct {
		Error string `json:"error"`
	}{Error: err.Error()})
}

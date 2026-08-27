package temporal

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

const maxStarterRequestBytes int64 = 16 << 10

// StarterHTTPHandler is the HTTP surface n8n's start/decision/preview
// workflows call, since n8n has no native Temporal client. It is a thin,
// authenticated shim over WorkflowStarter: it decodes/validates JSON,
// delegates to Temporal, and reports back — it holds no business logic and
// no Temporal SDK dependency of its own beyond what WorkflowStarter exposes.
type StarterHTTPHandler struct {
	starter     WorkflowStarter
	bearerToken []byte
}

// NewStarterHTTPHandler constructs a fail-closed handler: a nil starter or
// blank bearer token is rejected rather than creating an endpoint that can't
// actually authenticate or do anything.
func NewStarterHTTPHandler(starter WorkflowStarter, bearerToken string) (*StarterHTTPHandler, error) {
	if starter == nil {
		return nil, errors.New("temporal: starter HTTP handler requires a WorkflowStarter")
	}
	if strings.TrimSpace(bearerToken) == "" {
		return nil, errors.New("temporal: starter HTTP handler requires a bearer token")
	}
	return &StarterHTTPHandler{starter: starter, bearerToken: []byte(bearerToken)}, nil
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
		if !validStarterBearerToken(r.Header.Get("Authorization"), h.bearerToken) {
			w.Header().Set("WWW-Authenticate", `Bearer realm="reference-import-starter"`)
			writeStarterError(w, http.StatusUnauthorized, errors.New("reference import starter authorization required"))
			return
		}
		next(w, r)
	}
}

// startRequest mirrors engine/uiw.WorkflowInput exactly: this starts the
// real UniversalImportWorkflow from its actual root input (the raw,
// not-yet-retained acquisition reference), not a partially-observed
// mid-pipeline state.
type startRequest struct {
	RequestID        string `json:"request_id"`
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

	in := uiw.WorkflowInput{
		RequestID:        req.RequestID,
		SourceRef:        uiw.Ref(req.SourceRef),
		DeclaredFormat:   req.DeclaredFormat,
		ParserOptionsRef: uiw.Ref(req.ParserOptionsRef),
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
	if err := h.starter.Decide(r.Context(), workflowID, uiw.PreviewDecision{
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

func validStarterBearerToken(header string, expected []byte) bool {
	const prefix = "Bearer "
	if len(header) <= len(prefix) || !strings.EqualFold(header[:len(prefix)], prefix) {
		return false
	}
	provided := strings.TrimSpace(header[len(prefix):])
	if provided == "" || len(expected) == 0 {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(provided), expected) == 1
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

package runtimeapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	"github.com/Cursedpotential/probata/engine/parser"
)

const (
	HealthPath       = "/healthz"
	ReadinessPath    = "/readyz"
	CapabilitiesPath = "/capabilities"
)

// HealthProbe verifies the runtime's production dependencies without moving
// source bytes or parser output through the health response.
type HealthProbe func(context.Context) error

// NewRouter exposes the parser Activity transport plus operational health and
// the immutable capability inventory registered by this process.
func NewRouter(handler *ParserActivityHandler, capabilities []parser.Capability, readiness HealthProbe) (http.Handler, error) {
	if handler == nil {
		return nil, errors.New("parser runtime router: Activity handler is required")
	}
	if len(capabilities) == 0 {
		return nil, errors.New("parser runtime router: at least one parser capability is required")
	}
	if readiness == nil {
		return nil, errors.New("parser runtime router: readiness probe is required")
	}
	snapshot := make([]parser.Capability, len(capabilities))
	copy(snapshot, capabilities)

	mux := http.NewServeMux()
	mux.Handle(SelectParserPath, handler)
	mux.Handle(ExecuteParserPath, handler)
	mux.HandleFunc(HealthPath, func(response http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet {
			response.Header().Set("Allow", http.MethodGet)
			writeError(response, http.StatusMethodNotAllowed, errors.New("health endpoint requires GET"))
			return
		}
		writeJSON(response, http.StatusOK, map[string]any{"status": "ok"})
	})
	mux.HandleFunc(ReadinessPath, func(response http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet {
			response.Header().Set("Allow", http.MethodGet)
			writeError(response, http.StatusMethodNotAllowed, errors.New("readiness endpoint requires GET"))
			return
		}
		if err := readiness(request.Context()); err != nil {
			writeError(response, http.StatusServiceUnavailable, errors.New("parser runtime dependency is unavailable"))
			return
		}
		writeJSON(response, http.StatusOK, map[string]any{"status": "ready", "parser_count": len(snapshot)})
	})
	mux.HandleFunc(CapabilitiesPath, func(response http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet {
			response.Header().Set("Allow", http.MethodGet)
			writeError(response, http.StatusMethodNotAllowed, errors.New("capabilities endpoint requires GET"))
			return
		}
		if !validBearerToken(request.Header.Get("Authorization"), handler.bearerToken) {
			response.Header().Set("WWW-Authenticate", `Bearer realm="parser-activities"`)
			writeError(response, http.StatusUnauthorized, errors.New("parser Activity authorization required"))
			return
		}
		writeJSON(response, http.StatusOK, map[string]any{"contract_version": parser.ContractVersion, "parsers": snapshot})
	})
	return securityHeaders(mux), nil
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		response.Header().Set("Cache-Control", "no-store")
		response.Header().Set("X-Content-Type-Options", "nosniff")
		response.Header().Set("Referrer-Policy", "no-referrer")
		next.ServeHTTP(response, request)
	})
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(value)
}

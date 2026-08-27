// Package runtimeapi exposes the parser Activities to an external Activity
// body such as n8n. The transport carries only compact references and delegates
// all parsing, selection pinning, streaming, and receipt persistence to the
// already-atomic activities.ParserActivities implementation.
package runtimeapi

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

const defaultMaxParserRequestBytes int64 = 64 << 10

const (
	SelectParserPath  = "/activities/select_parser_activity"
	ExecuteParserPath = "/activities/execute_parser_activity"
)

// ParserActivityHandler is a small HTTP adapter for the two parser Activity
// bodies. It does not create a second parser path or a second persistence
// implementation: callers inject the production registry and ParserStore.
type ParserActivityHandler struct {
	parserActivities activities.ParserActivities
	maxBodyBytes     int64
	bearerToken      []byte
}

// NewParserActivityHandler constructs a fail-closed handler. Registry and
// Store must be production dependencies; a nil dependency is rejected rather
// than creating an HTTP endpoint that can report placeholder success.
func NewParserActivityHandler(parserActivities activities.ParserActivities, bearerToken string) (*ParserActivityHandler, error) {
	if parserActivities.Registry == nil {
		return nil, errors.New("parser Activity HTTP handler: registry is required")
	}
	if parserActivities.Store == nil {
		return nil, errors.New("parser Activity HTTP handler: store is required")
	}
	if strings.TrimSpace(bearerToken) == "" {
		return nil, errors.New("parser Activity HTTP handler: bearer token is required")
	}
	return &ParserActivityHandler{
		parserActivities: parserActivities,
		maxBodyBytes:     defaultMaxParserRequestBytes,
		bearerToken:      []byte(bearerToken),
	}, nil
}

// ServeHTTP dispatches only the exact canon Activity paths. JSON request keys
// are explicit and unknown keys are rejected, so source bytes, record arrays,
// or accidental payload fields cannot enter the parser Activity boundary.
func (h *ParserActivityHandler) ServeHTTP(response http.ResponseWriter, request *http.Request) {
	if h == nil {
		writeError(response, http.StatusInternalServerError, errors.New("parser Activity HTTP handler is nil"))
		return
	}
	if !validBearerToken(request.Header.Get("Authorization"), h.bearerToken) {
		response.Header().Set("WWW-Authenticate", `Bearer realm="parser-activities"`)
		writeError(response, http.StatusUnauthorized, errors.New("parser Activity authorization required"))
		return
	}
	if request.Method != http.MethodPost {
		response.Header().Set("Allow", http.MethodPost)
		writeError(response, http.StatusMethodNotAllowed, errors.New("parser Activity endpoint requires POST"))
		return
	}
	var stage stagegraph.StageID
	switch request.URL.Path {
	case SelectParserPath:
		stage = stagegraph.SelectParser
	case ExecuteParserPath:
		stage = stagegraph.ExecuteParser
	default:
		writeError(response, http.StatusNotFound, errors.New("unknown parser Activity endpoint"))
		return
	}

	input, err := decodeParserRequest(response, request, h.maxBodyBytes)
	if err != nil {
		writeError(response, http.StatusBadRequest, err)
		return
	}
	var result uiw.StageResult
	if stage == stagegraph.SelectParser {
		result, err = h.parserActivities.SelectParser(request.Context(), input)
	} else {
		result, err = h.parserActivities.ExecuteParser(request.Context(), input)
	}
	if err != nil {
		// The Activity body owns the detailed failure. HTTP reports it as a
		// non-success response so an n8n caller cannot mistake a failed body
		// for a usable compact result.
		writeError(response, http.StatusUnprocessableEntity, err)
		return
	}
	if err := validateHTTPResult(stage, result); err != nil {
		writeError(response, http.StatusInternalServerError, err)
		return
	}
	writeStageResult(response, result)
}

func validBearerToken(header string, expected []byte) bool {
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

type parserRequest struct {
	RequestID        string             `json:"request_id"`
	SourceVersionRef uiw.Ref            `json:"source_version_ref"`
	DeclaredFormat   string             `json:"declared_format"`
	Refs             map[string]uiw.Ref `json:"refs"`
}

func decodeParserRequest(response http.ResponseWriter, request *http.Request, maxBytes int64) (uiw.StageRequest, error) {
	if maxBytes <= 0 {
		maxBytes = defaultMaxParserRequestBytes
	}
	if request.ContentLength > maxBytes {
		return uiw.StageRequest{}, fmt.Errorf("parser Activity request exceeds %d bytes", maxBytes)
	}
	decoder := json.NewDecoder(http.MaxBytesReader(response, request.Body, maxBytes))
	decoder.DisallowUnknownFields()
	var wire parserRequest
	if err := decoder.Decode(&wire); err != nil {
		return uiw.StageRequest{}, fmt.Errorf("decode parser Activity request: %w", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return uiw.StageRequest{}, errors.New("parser Activity request must contain one JSON object")
		}
		return uiw.StageRequest{}, fmt.Errorf("decode trailing parser Activity request data: %w", err)
	}
	if strings.TrimSpace(wire.RequestID) == "" {
		return uiw.StageRequest{}, errors.New("parser Activity request requires request_id")
	}
	if strings.TrimSpace(string(wire.SourceVersionRef)) == "" {
		return uiw.StageRequest{}, errors.New("parser Activity request requires source_version_ref")
	}
	if strings.TrimSpace(wire.DeclaredFormat) == "" {
		return uiw.StageRequest{}, errors.New("parser Activity request requires declared_format")
	}
	refs := make(map[string]uiw.Ref, len(wire.Refs))
	for name, ref := range wire.Refs {
		if strings.TrimSpace(name) == "" || strings.TrimSpace(string(ref)) == "" {
			return uiw.StageRequest{}, errors.New("parser Activity request refs require non-empty names and compact references")
		}
		refs[name] = ref
	}
	return uiw.StageRequest{
		RequestID: wire.RequestID, SourceVersionRef: wire.SourceVersionRef,
		DeclaredFormat: wire.DeclaredFormat, Refs: refs,
	}, nil
}

func validateHTTPResult(stage stagegraph.StageID, result uiw.StageResult) error {
	if result.Stage != stage {
		return fmt.Errorf("parser Activity returned stage %q for endpoint %q", result.Stage, stage)
	}
	if strings.TrimSpace(string(result.ReceiptRef)) == "" {
		return errors.New("parser Activity returned no receipt reference")
	}
	if result.Status != uiw.StatusSuccess {
		return fmt.Errorf("parser Activity returned non-success status %q", result.Status)
	}
	if strings.TrimSpace(string(result.Ref)) == "" {
		return errors.New("parser Activity returned no result reference")
	}
	if strings.TrimSpace(result.Reason) != "" {
		return errors.New("successful parser Activity returned a failure reason")
	}
	return nil
}

type stageResultResponse struct {
	Stage      uiw.ActivityName `json:"stage"`
	Status     uiw.Status       `json:"status"`
	Ref        uiw.Ref          `json:"ref"`
	ReceiptRef uiw.Ref          `json:"receipt_ref"`
	Reason     string           `json:"reason,omitempty"`
}

func writeStageResult(response http.ResponseWriter, result uiw.StageResult) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(response).Encode(stageResultResponse{
		Stage: result.Stage, Status: result.Status, Ref: result.Ref,
		ReceiptRef: result.ReceiptRef, Reason: result.Reason,
	})
}

func writeError(response http.ResponseWriter, status int, err error) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(struct {
		Error string `json:"error"`
	}{Error: err.Error()})
}

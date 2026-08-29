package runtimeapi

import (
	"errors"
	"net/http"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

const (
	AssessSourceRepairPath  = "/activities/assess_source_repair_activity"
	ResolveSourceRepairPath = "/activities/resolve_source_repair_activity"
)

// RepairActivityHandler reuses the parser runtime's existing bearer boundary.
// Requests and responses contain references only.
type RepairActivityHandler struct {
	activities   activities.RepairActivities
	maxBodyBytes int64
	bearerToken  []byte
}

func NewRepairActivityHandler(a activities.RepairActivities, bearerToken string) (*RepairActivityHandler, error) {
	if a.Client == nil || a.Store == nil {
		return nil, errors.New("repair Activity HTTP handler requires client and durable store")
	}
	if strings.TrimSpace(bearerToken) == "" {
		return nil, errors.New("repair Activity HTTP handler requires bearer token")
	}
	return &RepairActivityHandler{activities: a, maxBodyBytes: defaultMaxParserRequestBytes, bearerToken: []byte(bearerToken)}, nil
}

func (h *RepairActivityHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if h == nil || !validBearerToken(r.Header.Get("Authorization"), h.bearerToken) {
		w.Header().Set("WWW-Authenticate", `Bearer realm="parser-activities"`)
		writeError(w, http.StatusUnauthorized, errors.New("repair Activity authorization required"))
		return
	}
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		writeError(w, http.StatusMethodNotAllowed, errors.New("repair Activity endpoint requires POST"))
		return
	}
	var stage stagegraph.StageID
	switch r.URL.Path {
	case AssessSourceRepairPath:
		stage = stagegraph.AssessSourceRepair
	case ResolveSourceRepairPath:
		stage = stagegraph.ResolveSourceRepair
	default:
		writeError(w, http.StatusNotFound, errors.New("unknown repair Activity endpoint"))
		return
	}
	req, err := decodeParserRequest(w, r, h.maxBodyBytes)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	var result uiw.StageResult
	if stage == stagegraph.AssessSourceRepair {
		result, err = h.activities.AssessSourceRepair(r.Context(), req)
	} else {
		result, err = h.activities.ResolveSourceRepair(r.Context(), req)
	}
	if err != nil {
		writeError(w, http.StatusUnprocessableEntity, err)
		return
	}
	if err = validateHTTPResult(stage, result); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeStageResult(w, result)
}

// Byline: Codex · GPT-5.6 · 2026-08-29 (opaque UIW preview HTTP surface)
package runtimeapi

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/runtimeapi/previewmodel"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

const (
	maxPreviewRequestBytes int64 = 16 << 10
	maxPreviewPage               = 250
	maxReasonBytes               = 4000
)

var (
	ErrPreviewNotFound = previewmodel.ErrNotFound
	ErrPreviewNotReady = previewmodel.ErrNotReady
	ErrPreviewEventGap = previewmodel.ErrEventGap
)

// PreviewWorkflow is the compact Temporal boundary used by the preview HTTP
// surface. It never transports source or normalized bytes.
type PreviewWorkflow interface {
	Start(context.Context, uiw.WorkflowInput) (workflowID, runID string, err error)
	Decide(context.Context, string, uiw.PreviewDecision) error
	DecideRepair(context.Context, string, uiw.RepairDecision) error
	Preview(context.Context, string) (uiw.PreviewState, error)
}

type RepairDecisionWriter interface {
	PersistRepairDecision(context.Context, uiw.RepairDecisionSpec) (uiw.Ref, error)
}

type PreviewBinding = previewmodel.Binding
type PreviewReceipt = previewmodel.Receipt
type PreviewParser = previewmodel.Parser
type PreviewSnapshot = previewmodel.Snapshot
type PreviewParticipant = previewmodel.Participant
type PreviewAttachment = previewmodel.Attachment
type PreviewMessage = previewmodel.Message
type PreviewEvent = previewmodel.Event
type PreviewPage = previewmodel.Page
type PreviewStore = previewmodel.Store

type memoryPreview struct {
	binding      PreviewBinding
	snapshot     *PreviewSnapshot
	participants []PreviewParticipant
	messages     []PreviewMessage
	events       []PreviewEvent
}

type MemoryPreviewStore struct {
	mu      sync.RWMutex
	entries map[string]*memoryPreview
	entropy io.Reader
}

func NewMemoryPreviewStore(entropy io.Reader) *MemoryPreviewStore {
	if entropy == nil {
		entropy = rand.Reader
	}
	return &MemoryPreviewStore{entries: make(map[string]*memoryPreview), entropy: entropy}
}

func (s *MemoryPreviewStore) PersistRepairDecision(_ context.Context, spec uiw.RepairDecisionSpec) (uiw.Ref, error) {
	if spec.SourceVersionRef == "" || spec.AssessmentRef == "" || spec.ActorRef == "" || spec.IdempotencyKey == "" {
		return "", errors.New("memory repair decision is incomplete")
	}
	id := uuid.NewSHA1(uuid.NameSpaceOID, []byte(spec.IdempotencyKey))
	return uiw.Ref(id.String()), nil
}

func (s *MemoryPreviewStore) Create(_ context.Context, binding PreviewBinding) (PreviewBinding, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for attempts := 0; attempts < 4; attempts++ {
		raw := make([]byte, 24)
		if _, err := io.ReadFull(s.entropy, raw); err != nil {
			return PreviewBinding{}, fmt.Errorf("generate preview handle: %w", err)
		}
		binding.Handle = base64.RawURLEncoding.EncodeToString(raw)
		if _, exists := s.entries[binding.Handle]; exists {
			continue
		}
		s.entries[binding.Handle] = &memoryPreview{binding: binding, events: []PreviewEvent{{
			EventID: 0, EventType: "phase_changed", OccurredAt: time.Unix(0, 0).UTC(),
			PreviewHandle: binding.Handle, Phase: "starting",
		}}}
		return binding, nil
	}
	return PreviewBinding{}, errors.New("generate unique preview handle")
}

func (s *MemoryPreviewStore) Binding(_ context.Context, handle string) (PreviewBinding, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	entry := s.entries[handle]
	if entry == nil {
		return PreviewBinding{}, ErrPreviewNotFound
	}
	return entry.binding, nil
}

func (s *MemoryPreviewStore) Snapshot(_ context.Context, handle string) (PreviewSnapshot, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	entry := s.entries[handle]
	if entry == nil {
		return PreviewSnapshot{}, ErrPreviewNotFound
	}
	if entry.snapshot == nil {
		return PreviewSnapshot{}, ErrPreviewNotReady
	}
	return *entry.snapshot, nil
}

func (s *MemoryPreviewStore) Page(_ context.Context, handle string, offset, limit int) (PreviewPage, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	entry := s.entries[handle]
	if entry == nil {
		return PreviewPage{}, ErrPreviewNotFound
	}
	if entry.snapshot == nil {
		return PreviewPage{}, ErrPreviewNotReady
	}
	if offset < 0 || offset > len(entry.messages) {
		return PreviewPage{}, ErrPreviewEventGap
	}
	end := offset + limit
	if end > len(entry.messages) {
		end = len(entry.messages)
	}
	page := PreviewPage{
		Participants: append([]PreviewParticipant(nil), entry.participants...),
		Messages:     append([]PreviewMessage(nil), entry.messages[offset:end]...),
	}
	if end < len(entry.messages) {
		page.NextOffset = &end
	}
	return page, nil
}

func (s *MemoryPreviewStore) EventsAfter(_ context.Context, handle string, after int64) ([]PreviewEvent, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	entry := s.entries[handle]
	if entry == nil {
		return nil, ErrPreviewNotFound
	}
	latest := entry.events[len(entry.events)-1].EventID
	if after > latest {
		return nil, ErrPreviewEventGap
	}
	first := entry.events[0].EventID
	if after >= 0 && after+1 < first {
		return nil, ErrPreviewEventGap
	}
	result := make([]PreviewEvent, 0, len(entry.events))
	for _, event := range entry.events {
		if event.EventID > after {
			result = append(result, event)
		}
	}
	return result, nil
}

func (s *MemoryPreviewStore) RecordDecision(_ context.Context, handle string, approved bool, reason, actor string, selection, options uiw.Ref) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	entry := s.entries[handle]
	if entry == nil {
		return ErrPreviewNotFound
	}
	entry.binding.SelectionRef = selection
	entry.binding.ParserOptionsRef = options
	status := "rejected"
	if approved {
		status = "approved"
	}
	entry.events = append(entry.events, PreviewEvent{
		EventID: int64(len(entry.events)), EventType: "decision_recorded", OccurredAt: time.Now().UTC(),
		PreviewHandle: handle, Phase: status, Detail: strings.TrimSpace(actor + ": " + reason),
	})
	return nil
}

// PutProjection is intentionally test/importer-only scaffolding. A durable
// PostgreSQL store will populate these same projections from receipt refs.
func (s *MemoryPreviewStore) PutProjection(handle string, snapshot PreviewSnapshot, participants []PreviewParticipant, messages []PreviewMessage, events []PreviewEvent) error {
	if err := previewmodel.Validate(handle, snapshot, participants, messages); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	entry := s.entries[handle]
	if entry == nil {
		return ErrPreviewNotFound
	}
	if snapshot.Correlation.RequestID != entry.binding.RequestID {
		return errors.New("preview projection request correlation does not match its server binding")
	}
	sort.SliceStable(messages, func(i, j int) bool { return messages[i].Ordinal < messages[j].Ordinal })
	entry.binding.SourceVersionID = snapshot.Correlation.SourceVersionID
	entry.binding.RawGenerationID = snapshot.Correlation.RawGenerationID
	entry.binding.NormalizedGenerationID = snapshot.Correlation.NormalizedGenerationID
	entry.snapshot = &snapshot
	entry.participants = append([]PreviewParticipant(nil), participants...)
	entry.messages = append([]PreviewMessage(nil), messages...)
	for _, event := range events {
		if event.PreviewHandle != handle || event.EventID != int64(len(entry.events)) {
			return errors.New("preview events must be contiguous and handle-bound")
		}
		entry.events = append(entry.events, event)
	}
	return nil
}

var receiptTypes = previewmodel.ReceiptTypes

// ValidatePreviewProjection is the shared fail-closed gate used by durable
// projection writers before any snapshot/message rows become visible.
func ValidatePreviewProjection(handle string, snapshot PreviewSnapshot, participants []PreviewParticipant, messages []PreviewMessage) error {
	return previewmodel.Validate(handle, snapshot, participants, messages)
}

type PreviewHTTPHandler struct {
	workflow  PreviewWorkflow
	store     PreviewStore
	repairs   RepairDecisionWriter
	cursorKey []byte
}

func NewPreviewHTTPHandler(workflow PreviewWorkflow, store PreviewStore, repairs RepairDecisionWriter, cursorKey []byte) (*PreviewHTTPHandler, error) {
	if workflow == nil || store == nil || repairs == nil {
		return nil, errors.New("uiw preview handler requires workflow, preview store, and repair decision writer")
	}
	if len(cursorKey) < 32 {
		return nil, errors.New("uiw preview cursor key must be at least 32 bytes")
	}
	return &PreviewHTTPHandler{workflow: workflow, store: store, repairs: repairs, cursorKey: append([]byte(nil), cursorKey...)}, nil
}

func (h *PreviewHTTPHandler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /reference-import/start", h.auth(h.start))
	mux.HandleFunc("GET /reference-import/previews/{preview_handle}", h.auth(h.snapshot))
	mux.HandleFunc("GET /reference-import/previews/{preview_handle}/messages", h.auth(h.messages))
	mux.HandleFunc("GET /reference-import/previews/{preview_handle}/events", h.auth(h.events))
	mux.HandleFunc("POST /reference-import/previews/{preview_handle}/decision", h.auth(h.decide))
	mux.HandleFunc("POST /reference-import/previews/{preview_handle}/repair-decision", h.auth(h.decideRepair))
	return mux
}

func (h *PreviewHTTPHandler) auth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
		ip := net.ParseIP(host).To4()
		if err != nil || ip == nil || ip[0] != 100 || ip[1] < 64 || ip[1] > 127 {
			previewError(w, http.StatusUnauthorized, errors.New("uiw preview tailnet authorization required"))
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		next(w, r)
	}
}

type previewStartRequest struct {
	RequestID, MatterID, CourtCaseID, SourceRef, DeclaredFormat, ParserOptionsRef string
}

func (r *previewStartRequest) UnmarshalJSON(data []byte) error {
	type wire struct {
		RequestID        string `json:"request_id"`
		MatterID         string `json:"matter_id"`
		CourtCaseID      string `json:"court_case_id"`
		SourceRef        string `json:"source_ref"`
		DeclaredFormat   string `json:"declared_format"`
		ParserOptionsRef string `json:"parser_options_ref"`
	}
	var value wire
	if err := json.Unmarshal(data, &value); err != nil {
		return err
	}
	*r = previewStartRequest{value.RequestID, value.MatterID, value.CourtCaseID, value.SourceRef, value.DeclaredFormat, value.ParserOptionsRef}
	return nil
}

func (h *PreviewHTTPHandler) start(w http.ResponseWriter, r *http.Request) {
	var req previewStartRequest
	if err := decodePreviewJSON(w, r, &req); err != nil {
		previewError(w, 400, err)
		return
	}
	if strings.TrimSpace(req.RequestID) == "" || strings.TrimSpace(req.SourceRef) == "" || strings.TrimSpace(req.DeclaredFormat) == "" || strings.TrimSpace(req.ParserOptionsRef) == "" {
		previewError(w, 400, errors.New("start request is incomplete"))
		return
	}
	if _, err := uuid.Parse(req.MatterID); err != nil {
		previewError(w, 400, errors.New("matter_id must be a UUID"))
		return
	}
	if _, err := uuid.Parse(req.CourtCaseID); err != nil {
		previewError(w, 400, errors.New("court_case_id must be a UUID"))
		return
	}
	in := uiw.WorkflowInput{RequestID: req.RequestID, MatterID: req.MatterID, CourtCaseID: req.CourtCaseID, SourceRef: uiw.Ref(req.SourceRef), DeclaredFormat: req.DeclaredFormat, ParserOptionsRef: uiw.Ref(req.ParserOptionsRef)}
	workflowID, runID, err := h.workflow.Start(r.Context(), in)
	if err != nil {
		previewError(w, 422, err)
		return
	}
	binding, err := h.store.Create(r.Context(), PreviewBinding{RequestID: req.RequestID, SourceRef: in.SourceRef, WorkflowID: workflowID, RunID: runID, ParserOptionsRef: in.ParserOptionsRef})
	if err != nil {
		previewError(w, 503, err)
		return
	}
	previewJSON(w, 201, map[string]string{"preview_handle": binding.Handle})
}

func (h *PreviewHTTPHandler) snapshot(w http.ResponseWriter, r *http.Request) {
	handle := r.PathValue("preview_handle")
	snapshot, err := h.store.Snapshot(r.Context(), handle)
	if err != nil {
		h.storeError(w, err)
		return
	}
	previewJSON(w, 200, snapshot)
}

func (h *PreviewHTTPHandler) messages(w http.ResponseWriter, r *http.Request) {
	handle := r.PathValue("preview_handle")
	limit := 100
	if raw := r.URL.Query().Get("limit"); raw != "" {
		value, err := strconv.Atoi(raw)
		if err != nil || value < 1 || value > maxPreviewPage {
			previewError(w, 422, errors.New("limit must be between 1 and 250"))
			return
		}
		limit = value
	}
	offset := 0
	if raw := r.URL.Query().Get("cursor"); raw != "" {
		value, err := h.decodeCursor(handle, raw)
		if err != nil {
			previewError(w, 422, err)
			return
		}
		offset = value
	}
	page, err := h.store.Page(r.Context(), handle, offset, limit)
	if err != nil {
		h.storeError(w, err)
		return
	}
	var next *string
	if page.NextOffset != nil {
		encoded := h.encodeCursor(handle, *page.NextOffset)
		next = &encoded
	}
	previewJSON(w, 200, struct {
		PreviewHandle string               `json:"preview_handle"`
		Participants  []PreviewParticipant `json:"participants"`
		Messages      []PreviewMessage     `json:"messages"`
		NextCursor    *string              `json:"next_cursor,omitempty"`
	}{handle, page.Participants, page.Messages, next})
}

type previewDecisionRequest struct {
	Approved bool   `json:"approved"`
	Reason   string `json:"reason"`
}

func (h *PreviewHTTPHandler) decide(w http.ResponseWriter, r *http.Request) {
	handle := r.PathValue("preview_handle")
	var req previewDecisionRequest
	if err := decodePreviewJSON(w, r, &req); err != nil {
		previewError(w, 400, err)
		return
	}
	actor, _, err := authenticatedActor(r)
	if err != nil {
		previewError(w, http.StatusUnauthorized, err)
		return
	}
	if len(req.Reason) > maxReasonBytes || (!req.Approved && strings.TrimSpace(req.Reason) == "") {
		previewError(w, 422, errors.New("rejection requires a bounded reason"))
		return
	}
	binding, err := h.store.Binding(r.Context(), handle)
	if err != nil {
		h.storeError(w, err)
		return
	}
	if _, err := h.store.Snapshot(r.Context(), handle); err != nil {
		h.storeError(w, err)
		return
	}
	state, err := h.workflow.Preview(r.Context(), binding.WorkflowID)
	if err != nil {
		previewError(w, 422, err)
		return
	}
	if state.Phase != uiw.PhaseAwaitingDecision && state.Phase != uiw.PhaseRejected {
		previewError(w, 409, errors.New("workflow is not awaiting a preview decision"))
		return
	}
	selection, options := state.SelectRef, state.ParserOptionsRef
	decision := uiw.PreviewDecision{Approved: req.Approved, Reason: req.Reason, Decider: actor}
	if state.Phase == uiw.PhaseRejected && req.Approved {
		if selection == binding.SelectionRef && options == binding.ParserOptionsRef {
			previewError(w, http.StatusConflict, errors.New("approval after rejection requires changed repair selection or options refs"))
			return
		}
		decision.RepairedSelectionRef = selection
		decision.RepairedParserOptionsRef = options
	}
	if err := h.store.RecordDecision(r.Context(), handle, req.Approved, req.Reason, actor, selection, options); err != nil {
		previewError(w, 503, err)
		return
	}
	if err := h.workflow.Decide(r.Context(), binding.WorkflowID, decision); err != nil {
		previewError(w, 422, err)
		return
	}
	status := "rejected"
	if req.Approved {
		status = "approved"
	}
	previewJSON(w, 200, map[string]string{"preview_handle": handle, "status": status})
}

type repairDecisionRequest struct {
	Approved    bool           `json:"approved"`
	ApplyRepair bool           `json:"apply_repair"`
	ToolID      string         `json:"tool_id"`
	ToolPayload map[string]any `json:"tool_payload"`
}

func (h *PreviewHTTPHandler) decideRepair(w http.ResponseWriter, r *http.Request) {
	handle := r.PathValue("preview_handle")
	var req repairDecisionRequest
	if err := decodePreviewJSON(w, r, &req); err != nil {
		previewError(w, http.StatusBadRequest, err)
		return
	}
	actor, _, err := authenticatedActor(r)
	if err != nil {
		previewError(w, http.StatusUnauthorized, err)
		return
	}
	idempotencyKey := strings.TrimSpace(r.Header.Get("Idempotency-Key"))
	if idempotencyKey == "" || len(idempotencyKey) > 256 {
		previewError(w, http.StatusBadRequest, errors.New("bounded Idempotency-Key is required"))
		return
	}
	binding, err := h.store.Binding(r.Context(), handle)
	if err != nil {
		h.storeError(w, err)
		return
	}
	state, err := h.workflow.Preview(r.Context(), binding.WorkflowID)
	if err != nil {
		previewError(w, http.StatusUnprocessableEntity, err)
		return
	}
	if state.Phase != uiw.PhaseAwaitingRepairDecision || state.SourceVersionRef == "" || state.RepairAssessmentRef == "" {
		previewError(w, http.StatusConflict, errors.New("workflow is not awaiting an identified repair decision"))
		return
	}
	decisionRef, err := h.repairs.PersistRepairDecision(r.Context(), uiw.RepairDecisionSpec{
		SourceVersionRef: state.SourceVersionRef, AssessmentRef: state.RepairAssessmentRef,
		ActorRef: uiw.Ref(actor), Approved: req.Approved, ApplyRepair: req.ApplyRepair,
		ToolID: strings.TrimSpace(req.ToolID), ToolPayload: req.ToolPayload,
		IdempotencyKey: "uiw:" + handle + ":" + idempotencyKey,
	})
	if err != nil {
		previewError(w, http.StatusUnprocessableEntity, err)
		return
	}
	if err := h.workflow.DecideRepair(r.Context(), binding.WorkflowID, uiw.RepairDecision{DecisionRef: decisionRef}); err != nil {
		previewError(w, http.StatusServiceUnavailable, err)
		return
	}
	previewJSON(w, http.StatusOK, map[string]string{"preview_handle": handle, "decision_ref": string(decisionRef), "status": "signaled"})
}

func authenticatedActor(r *http.Request) (subjectUID, username string, err error) {
	subjectUID = strings.TrimSpace(r.Header.Get("X-authentik-uid"))
	username = strings.TrimSpace(r.Header.Get("X-authentik-username"))
	if subjectUID == "" || username == "" || len(subjectUID) > 512 || len(username) > 512 || strings.ContainsAny(subjectUID+username, "\x00\r\n") {
		return "", "", errors.New("Authentik actor headers are required")
	}
	return subjectUID, username, nil
}

func (h *PreviewHTTPHandler) events(w http.ResponseWriter, r *http.Request) {
	handle := r.PathValue("preview_handle")
	after := int64(-1)
	if raw := r.Header.Get("Last-Event-ID"); raw != "" {
		value, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || value < 0 {
			previewError(w, 422, errors.New("Last-Event-ID must be a non-negative integer"))
			return
		}
		after = value
	}
	events, err := h.store.EventsAfter(r.Context(), handle, after)
	if err != nil {
		h.storeError(w, err)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-store")
	for _, event := range events {
		payload, _ := json.Marshal(event)
		_, _ = fmt.Fprintf(w, "id: %d\nevent: uiw.preview\ndata: %s\n\n", event.EventID, payload)
	}
}

func (h *PreviewHTTPHandler) encodeCursor(handle string, offset int) string {
	payload := fmt.Sprintf("%s:%d", handle, offset)
	mac := hmac.New(sha256.New, h.cursorKey)
	_, _ = mac.Write([]byte(payload))
	return base64.RawURLEncoding.EncodeToString([]byte(payload + ":" + hex.EncodeToString(mac.Sum(nil))))
}

func (h *PreviewHTTPHandler) decodeCursor(handle, cursor string) (int, error) {
	decoded, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil || len(decoded) > 512 {
		return 0, errors.New("cursor is malformed")
	}
	parts := strings.Split(string(decoded), ":")
	if len(parts) != 3 || parts[0] != handle {
		return 0, errors.New("cursor does not belong to this preview")
	}
	payload := parts[0] + ":" + parts[1]
	mac := hmac.New(sha256.New, h.cursorKey)
	_, _ = mac.Write([]byte(payload))
	actual, err := hex.DecodeString(parts[2])
	if err != nil || !hmac.Equal(actual, mac.Sum(nil)) {
		return 0, errors.New("cursor signature is invalid")
	}
	offset, err := strconv.Atoi(parts[1])
	if err != nil || offset < 0 {
		return 0, errors.New("cursor offset is invalid")
	}
	return offset, nil
}

func (h *PreviewHTTPHandler) storeError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, ErrPreviewNotFound):
		previewError(w, 404, err)
	case errors.Is(err, ErrPreviewNotReady):
		previewError(w, 409, err)
	case errors.Is(err, ErrPreviewEventGap):
		previewError(w, 409, err)
	default:
		previewError(w, 503, err)
	}
}

func decodePreviewJSON(w http.ResponseWriter, r *http.Request, dest any) error {
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxPreviewRequestBytes))
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

func previewJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
func previewError(w http.ResponseWriter, status int, err error) {
	previewJSON(w, status, map[string]string{"detail": err.Error()})
}

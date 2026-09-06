// Byline: Codex · GPT-5.6-Sol · 2026-08-30 (durable inline source context)
package runtimeapi

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/Cursedpotential/probata/engine/sourcecontext"
)

const maxSourceContextRequestBytes int64 = 64 << 10

type SourceContextHTTPHandler struct {
	writer           sourcecontext.Writer
	serviceTokenPath string
}

func NewSourceContextHTTPHandler(writer sourcecontext.Writer, serviceTokenPath string) (*SourceContextHTTPHandler, error) {
	if writer == nil {
		return nil, errors.New("source context handler requires a durable writer")
	}
	if _, err := loadServiceToken(serviceTokenPath); err != nil {
		return nil, err
	}
	return &SourceContextHTTPHandler{writer: writer, serviceTokenPath: serviceTokenPath}, nil
}

func (h *SourceContextHTTPHandler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /reference-import/source-contexts", h.auth(h.create))
	return mux
}

func (h *SourceContextHTTPHandler) auth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
		ip := net.ParseIP(host).To4()
		serviceToken, tokenErr := loadServiceToken(h.serviceTokenPath)
		auth := strings.TrimSpace(r.Header.Get("Authorization"))
		provided := strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
		trusted := tokenErr == nil && strings.HasPrefix(auth, "Bearer ") && hmac.Equal([]byte(provided), serviceToken)
		if err != nil || ip == nil || ip[0] != 100 || ip[1] < 64 || ip[1] > 127 || !trusted {
			previewError(w, http.StatusUnauthorized, errors.New("proffer source context tailnet authorization required"))
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		next(w, r)
	}
}

type sourceContextRequest struct {
	RequestID      string                        `json:"request_id"`
	MatterID       string                        `json:"matter_id"`
	CourtCaseID    string                        `json:"court_case_id"`
	SourceRef      string                        `json:"source_ref"`
	SupersedesRef  string                        `json:"supersedes_ref"`
	ObservedSource sourcecontext.ObservedSource  `json:"observed_source"`
	Assertions     sourcecontext.HumanAssertions `json:"assertions"`
	ChangeReason   string                        `json:"change_reason"`
}

func (h *SourceContextHTTPHandler) create(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxSourceContextRequestBytes)
	var req sourceContextRequest
	if err := decodePreviewJSON(w, r, &req); err != nil {
		previewError(w, http.StatusBadRequest, err)
		return
	}
	actor, username, err := authenticatedActor(r)
	if err != nil {
		previewError(w, http.StatusUnauthorized, err)
		return
	}
	idempotencyKey := strings.TrimSpace(r.Header.Get("Idempotency-Key"))
	if idempotencyKey == "" || len(idempotencyKey) > 512 {
		previewError(w, http.StatusBadRequest, errors.New("a bounded Idempotency-Key is required"))
		return
	}
	if err := validateSourceContextRequest(req); err != nil {
		previewError(w, http.StatusUnprocessableEntity, err)
		return
	}
	canonical, err := json.Marshal(req)
	if err != nil {
		previewError(w, http.StatusUnprocessableEntity, errors.New("source context is not canonical JSON"))
		return
	}
	spec := sourcecontext.Spec{
		RequestID: req.RequestID, MatterID: req.MatterID, CourtCaseID: req.CourtCaseID,
		SourceRef: req.SourceRef, SupersedesRef: req.SupersedesRef,
		ObservedSource: req.ObservedSource, Assertions: req.Assertions,
		ChangeReason: req.ChangeReason, ActorSubjectUID: actor, ActorUsername: username,
		IdempotencyKey: idempotencyKey, ContentDigest: sha256.Sum256(canonical),
	}
	receipt, err := h.writer.PersistSourceContext(r.Context(), spec)
	if err != nil {
		previewError(w, http.StatusServiceUnavailable, err)
		return
	}
	previewJSON(w, http.StatusCreated, receipt)
}

func validateSourceContextRequest(req sourceContextRequest) error {
	if strings.TrimSpace(req.RequestID) == "" || len(req.RequestID) > 512 || strings.TrimSpace(req.SourceRef) == "" {
		return errors.New("source context request identity is incomplete")
	}
	if _, err := uuid.Parse(req.MatterID); err != nil {
		return errors.New("matter_id must be a UUID")
	}
	if _, err := uuid.Parse(req.CourtCaseID); err != nil {
		return errors.New("court_case_id must be a UUID")
	}
	if req.SupersedesRef != "" {
		if _, err := uuid.Parse(req.SupersedesRef); err != nil {
			return errors.New("supersedes_ref must be a UUID")
		}
	}
	sourceKind, sourceIdentity, err := validateAuthorizedSourceRef(req.SourceRef)
	if err != nil {
		return err
	}
	observed := req.ObservedSource
	if strings.TrimSpace(observed.Key) == "" || strings.TrimSpace(observed.Name) == "" || observed.ByteLength < 0 || strings.TrimSpace(observed.ETag) == "" {
		return errors.New("observed source identity is incomplete")
	}
	if len(observed.PreviewSHA256) != sha256.Size*2 {
		return errors.New("preview_sha256 must be a SHA-256 digest")
	}
	if _, err := hex.DecodeString(observed.PreviewSHA256); err != nil {
		return errors.New("preview_sha256 must be a SHA-256 digest")
	}
	if observed.VerificationState != "preview_only" {
		return errors.New("observed source must be labeled preview_only until custody acquisition verifies it")
	}
	if (sourceKind == "r2" && observed.Key != sourceIdentity) ||
		(sourceKind == "upload" && observed.PreviewSHA256 != sourceIdentity) {
		return errors.New("observed source identity does not match source_ref")
	}
	if req.Assertions.SourceClass != "first_party" && req.Assertions.SourceClass != "acquired_third_party" && req.Assertions.SourceClass != "unknown" {
		return errors.New("source_class must be first_party, acquired_third_party, or unknown")
	}
	if err := validateBoundedAssertionText(req.Assertions); err != nil {
		return err
	}
	if req.Assertions.AcquiredAt != "" {
		if _, err := time.Parse(time.RFC3339, req.Assertions.AcquiredAt); err != nil {
			return errors.New("acquired_at must be an RFC3339 timestamp")
		}
	}
	if req.Assertions.OccurredStart != "" && !validKnownDate(req.Assertions.OccurredStart) {
		return errors.New("occurred_start must be an ISO date or RFC3339 timestamp")
	}
	if req.Assertions.OccurredEnd != "" && !validKnownDate(req.Assertions.OccurredEnd) {
		return errors.New("occurred_end must be an ISO date or RFC3339 timestamp")
	}
	if strings.TrimSpace(req.ChangeReason) == "" || len(req.ChangeReason) > 4000 {
		return errors.New("change_reason is required and must be at most 4000 characters")
	}
	return nil
}

func validateBoundedAssertionText(value sourcecontext.HumanAssertions) error {
	fields := []string{value.SourcePrincipal, value.OtherParty, value.AcquisitionMethod, value.AcquisitionAuthority,
		value.SourceDevice, value.DeviceCustodian, value.DateCertainty, value.Context, value.Notes}
	for _, field := range fields {
		if strings.ContainsAny(field, "\x00\r") || len(field) > 4000 {
			return errors.New("source assertion text exceeds its allowed boundary")
		}
	}
	return nil
}

func validKnownDate(value string) bool {
	if _, err := time.Parse("2006-01-02", value); err == nil {
		return true
	}
	_, err := time.Parse(time.RFC3339, value)
	return err == nil
}

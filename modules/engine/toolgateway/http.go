// HTTP surface for the tool gateway.
//
// The contract callers see is deliberately narrow: name a TOOL and a LOCATOR.
// There is no way to name a host path, because handing a host path across a
// host boundary is the defect this component exists to eliminate (D-132).
//
// Byline: Claude Code · Opus 5 · 2026-09-02.
package toolgateway

import (
	"crypto/hmac"
	"encoding/json"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// maxRequestBytes bounds a run request. Payloads are options, never content:
// source bytes travel as locators, so no legitimate request is large.
const maxRequestBytes = 64 << 10

// HTTPHandler serves the gateway.
//
// ServiceToken, when non-empty, is required as `Authorization: Bearer <token>`.
// The tailnet check always applies: this service is never internet-facing.
type HTTPHandler struct {
	Gateway      *Gateway
	Index        func() (json.RawMessage, error)
	ServiceToken string
	// TrustForwardedFromLoopback is set ONLY when the listener is a tsnet
	// service/node listener: tailscale's in-process serve proxy delivers the
	// request over loopback with the tailnet peer in X-Forwarded-For.
	TrustForwardedFromLoopback bool
}

type runRequest struct {
	SourceRef string         `json:"source_ref"`
	Args      map[string]any `json:"args"`
}

// Routes returns the mux. Tool ids contain dots but no slashes, so a single
// path segment holds them.
func (h *HTTPHandler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("GET /tools", h.auth(h.handleIndex))
	mux.HandleFunc("POST /tools/{tool_id}/run", h.auth(h.handleRun))
	return mux
}

// authorizedTailnetPeer mirrors the check used by the UIW starter: only
// Tailscale CGNAT space (100.64.0.0/10) is admitted.
//
// Both Tailscale address families are admitted: the IPv4 CGNAT range
// 100.64.0.0/10 and the IPv6 ULA range fd7a:115c:a1e0::/48. Live finding
// 2026-09-05: a VIP-service connection (svc:tool-gateway) reaches the tsnet
// listener with an IPv6 tailnet RemoteAddr, and the IPv4-only check rejected
// every worker call with 401 before the token was even compared.
//
// Second live finding, same day: in tsnet's HTTPS service mode the connection
// is terminated by tailscale's serve proxy inside the process and handed to
// this handler over loopback, so RemoteAddr is 127.0.0.1 and the real peer
// travels in X-Forwarded-For (vendor/tailscale.com/ipn/ipnlocal/serve.go:1074).
// That header is trusted ONLY when the handler was built for a tsnet listener
// (TrustForwardedFromLoopback) AND the direct peer is loopback — never on the
// plain TOOL_GATEWAY_BIND_IP listener, where a client could forge it.
func (h *HTTPHandler) authorizedTailnetPeer(r *http.Request) bool {
	host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
	if err != nil {
		return false
	}
	direct := net.ParseIP(host)
	if tailnetAddress(direct) {
		return true
	}
	if h.TrustForwardedFromLoopback && direct != nil && direct.IsLoopback() {
		fwd := strings.TrimSpace(strings.Split(r.Header.Get("X-Forwarded-For"), ",")[0])
		return tailnetAddress(net.ParseIP(fwd))
	}
	return false
}

var tailscaleULA = func() *net.IPNet {
	_, n, _ := net.ParseCIDR("fd7a:115c:a1e0::/48")
	return n
}()

func tailnetAddress(ip net.IP) bool {
	if ip == nil {
		return false
	}
	if v4 := ip.To4(); v4 != nil {
		return v4[0] == 100 && v4[1] >= 64 && v4[1] <= 127
	}
	return tailscaleULA.Contains(ip)
}

func (h *HTTPHandler) auth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !h.authorizedTailnetPeer(r) {
			slog.Warn("tool gateway: rejected non-tailnet peer", "remote_addr", r.RemoteAddr, "path", r.URL.Path)
			writeError(w, http.StatusUnauthorized, errors.New("tool gateway: tailnet authorization required"))
			return
		}
		if strings.TrimSpace(h.ServiceToken) != "" {
			provided := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(r.Header.Get("Authorization")), "Bearer "))
			if !hmac.Equal([]byte(provided), []byte(h.ServiceToken)) {
				writeError(w, http.StatusUnauthorized, errors.New("tool gateway: service token required"))
				return
			}
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		next(w, r)
	}
}

func (h *HTTPHandler) handleIndex(w http.ResponseWriter, _ *http.Request) {
	if h.Index == nil {
		writeError(w, http.StatusServiceUnavailable, errors.New("tool gateway: tool index is unavailable"))
		return
	}
	body, err := h.Index()
	if err != nil {
		writeError(w, http.StatusBadGateway, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}

func (h *HTTPHandler) handleRun(w http.ResponseWriter, r *http.Request) {
	toolID := r.PathValue("tool_id")
	if err := ValidateToolID(toolID); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxRequestBytes))
	decoder.DisallowUnknownFields()
	var req runRequest
	if err := decoder.Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, errors.New("tool gateway: request body must be {\"source_ref\":\"...\",\"args\":{...}}"))
		return
	}
	if strings.TrimSpace(req.SourceRef) == "" {
		writeError(w, http.StatusBadRequest, errors.New("tool gateway: source_ref locator is required"))
		return
	}
	result, err := h.Gateway.Run(r.Context(), toolID, uiw.Ref(req.SourceRef), req.Args)
	if err != nil {
		slog.Warn("tool gateway run failed", "tool_id", toolID, "error", err.Error())
		writeError(w, http.StatusUnprocessableEntity, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(result)
}

func writeError(w http.ResponseWriter, status int, err error) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"detail": err.Error()})
}

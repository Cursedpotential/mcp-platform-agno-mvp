package runtimeapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

const maxPlatformToolsResponseBytes int64 = 2 << 20

type PlatformToolsClient struct {
	baseURL string
	client  *http.Client
}

func NewPlatformToolsClient(baseURL string) (*PlatformToolsClient, error) {
	baseURL = strings.TrimRight(strings.TrimSpace(baseURL), "/")
	parsed, err := url.Parse(baseURL)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
		return nil, errors.New("platform-tools client requires an absolute HTTP(S) base URL")
	}
	return &PlatformToolsClient{baseURL: baseURL, client: &http.Client{}}, nil
}

func (c *PlatformToolsClient) Run(ctx context.Context, toolID string, payload map[string]any) (json.RawMessage, error) {
	if c == nil || c.client == nil {
		return nil, errors.New("platform-tools client is not configured")
	}
	if strings.TrimSpace(toolID) == "" || strings.ContainsAny(toolID, "/?#") {
		return nil, errors.New("platform-tools client requires a safe exact tool id")
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("encode platform-tools payload: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/tools/"+url.PathEscape(toolID)+"/run", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("call platform-tools %q: %w", toolID, err)
	}
	defer resp.Body.Close()
	limited := io.LimitReader(resp.Body, maxPlatformToolsResponseBytes+1)
	data, err := io.ReadAll(limited)
	if err != nil {
		return nil, fmt.Errorf("read platform-tools %q response: %w", toolID, err)
	}
	if int64(len(data)) > maxPlatformToolsResponseBytes {
		return nil, fmt.Errorf("platform-tools %q response exceeds limit", toolID)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("platform-tools %q returned %d", toolID, resp.StatusCode)
	}
	var object map[string]any
	if err := json.Unmarshal(data, &object); err != nil || object == nil {
		return nil, fmt.Errorf("platform-tools %q returned invalid JSON object", toolID)
	}
	return append(json.RawMessage(nil), data...), nil
}

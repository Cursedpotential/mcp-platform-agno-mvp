#!/usr/bin/with-contenv bash
# =============================================================================
# AgentOS localhost bridge for the in-VPS browser (linuxserver/chromium).
# -----------------------------------------------------------------------------
# os.agno.com's FREE tier only connects to a LOCAL endpoint (localhost / local
# IP); remote/public endpoints are Pro-gated. This browser runs ON the VPS, so we
# expose the platform at THIS container's 127.0.0.1:8000 via socat. Then, inside
# this browser, os.agno.com -> http://localhost:8000 is accepted (localhost is a
# browser "secure context": no Pro gate, no mixed-content block) and you get the
# FULL control plane for free. The platform itself stays gated by OS_SECURITY_KEY
# (entered once in the os.agno.com "Add AgentOS" dialog).
#
# 100.72.169.40:8000 = agentos-api published on the OVH-1 tailnet IP (reachable
# from any container on the box; verified).
# =============================================================================
set -e

if ! command -v socat >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq socat || true
fi

# kill any stale forwarder, then bridge localhost:8000 -> platform
pkill -f "TCP-LISTEN:8000" 2>/dev/null || true
nohup socat TCP-LISTEN:8000,fork,reuseaddr,bind=127.0.0.1 TCP:100.72.169.40:8000 \
  >/config/agentos-bridge.log 2>&1 &

echo "[agentos-bridge] socat 127.0.0.1:8000 -> 100.72.169.40:8000 started"

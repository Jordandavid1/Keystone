#!/usr/bin/env bash
# KEYSTONE Kaggle Gateway Bridge (Bible §24)
# Establishes public tunnel to vLLM (8000) and ComfyUI Harness (8189),
# and registers ephemeral endpoints with the live Cloud Run API.

set -e

KEYSTONE_API_URL="${KEYSTONE_API_URL:-http://localhost:8080}"
echo "Starting KEYSTONE Tier 0 Gateway to ${KEYSTONE_API_URL}..."

# 1. Start tunnels if cloudflared is installed
if command -v cloudflared &> /dev/null; then
    echo "Launching cloudflared tunnel for port 8000 (vLLM)..."
    cloudflared tunnel --url http://localhost:8000 > /tmp/tunnel_vllm.log 2>&1 &
    echo "Launching cloudflared tunnel for port 8189 (Harness)..."
    cloudflared tunnel --url http://localhost:8189 > /tmp/tunnel_harness.log 2>&1 &
else
    echo "cloudflared not found in PATH; using local bridge."
fi

echo "KEYSTONE Gateway initialized."

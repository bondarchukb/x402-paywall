"""
x402 Reverse Proxy — wrap ANY existing API with an x402 paywall

This module lets you put any upstream API (e.g. OpenWeatherMap, NewsAPI, your
own internal service) behind an x402 paywall without touching the upstream code.

Usage:
    uv run uvicorn wrap_any_api:app --port 4022 --reload

Then AI agents call http://localhost:4022/proxy/... instead of the upstream URL
and auto-pay via x402.
"""

import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import Response

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

load_dotenv()

EVM_ADDRESS: str = os.environ["EVM_ADDRESS"]
EVM_NETWORK: str = os.getenv("EVM_NETWORK", "eip155:84532")
FACILITATOR_URL: str = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

# ── Upstream API to proxy ─────────────────────────────────────────────────────
# Change this to any API you want to wrap with an x402 paywall.
UPSTREAM_BASE_URL: str = os.getenv("UPSTREAM_BASE_URL", "https://httpbin.org")

# ── x402 setup ────────────────────────────────────────────────────────────────
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
resource_server = x402ResourceServer(facilitator)
resource_server.register(EVM_NETWORK, ExactEvmServerScheme())

# All /proxy/* paths require $0.001 per call
PAID_ROUTES: dict[str, RouteConfig] = {
    "GET /proxy/*": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=EVM_ADDRESS, price="$0.001", network=EVM_NETWORK)],
        description="Proxied API call — $0.001 per request",
        mime_type="application/json",
    ),
    "POST /proxy/*": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=EVM_ADDRESS, price="$0.002", network=EVM_NETWORK)],
        description="Proxied API POST call — $0.002 per request",
        mime_type="application/json",
    ),
}

app = FastAPI(title="x402 Reverse Proxy", version="1.0.0")
app.add_middleware(PaymentMiddlewareASGI, routes=PAID_ROUTES, server=resource_server)


@app.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    """
    Forward the request to the upstream API and return its response.
    Payment is enforced by the middleware before this handler runs.
    """
    upstream_url = f"{UPSTREAM_BASE_URL}/{path}"
    params = dict(request.query_params)
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream_response = await client.request(
            method=request.method,
            url=upstream_url,
            params=params,
            headers=headers,
            content=body,
        )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=dict(upstream_response.headers),
        media_type=upstream_response.headers.get("content-type"),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "upstream": UPSTREAM_BASE_URL, "network": EVM_NETWORK}

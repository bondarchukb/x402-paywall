"""
x402 Paywall — FastAPI server

Any route decorated with x402 will return HTTP 402 to non-paying clients
and automatically collect USDC from AI agents that use the x402 client.

Quickstart:
    cp .env.example .env        # fill in EVM_ADDRESS
    uv run uvicorn server:app --host 0.0.0.0 --port 4021 --reload
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

EVM_ADDRESS: str = os.environ["EVM_ADDRESS"]
EVM_NETWORK: str = os.getenv("EVM_NETWORK", "eip155:84532")       # Base Sepolia by default
FACILITATOR_URL: str = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

# ── Build x402 resource server ────────────────────────────────────────────────

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
resource_server = x402ResourceServer(facilitator)
resource_server.register(EVM_NETWORK, ExactEvmServerScheme())

# ── Define which routes require payment and how much ─────────────────────────
#
# Key format:  "METHOD /path"
# Glob paths:  "GET /docs/*"  matches /docs/foo, /docs/foo/bar, etc.
# Price:       "$0.001"  →  parsed automatically to USDC atomic units
#
PAID_ROUTES: dict[str, RouteConfig] = {

    # ── Example 1: simple per-call pricing ────────────────────────────────────
    "GET /api/weather": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=EVM_ADDRESS,
                price="$0.001",
                network=EVM_NETWORK,
            )
        ],
        description="Current weather data — $0.001 per call",
        mime_type="application/json",
    ),

    # ── Example 2: slightly more expensive endpoint ────────────────────────────
    "GET /api/analysis": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=EVM_ADDRESS,
                price="$0.01",
                network=EVM_NETWORK,
            )
        ],
        description="Deep analysis endpoint — $0.01 per call",
        mime_type="application/json",
    ),

    # ── Example 3: POST endpoint (agent sends data, pays for processing) ───────
    "POST /api/process": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=EVM_ADDRESS,
                price="$0.005",
                network=EVM_NETWORK,
            )
        ],
        description="Process data — $0.005 per call",
        mime_type="application/json",
    ),

    # ── Example 4: wildcard — pay for any /api/premium/* sub-path ─────────────
    "GET /api/premium/*": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=EVM_ADDRESS,
                price="$0.05",
                network=EVM_NETWORK,
            )
        ],
        description="Premium content — $0.05 per call",
        mime_type="application/json",
    ),
}

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="x402 Paywall API",
    description="Any endpoint here requires USDC payment via the x402 protocol.",
    version="1.0.0",
)

# Register the x402 middleware — order matters: add before routes are hit
app.add_middleware(PaymentMiddlewareASGI, routes=PAID_ROUTES, server=resource_server)


# ── Free routes ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health():
    """No payment required."""
    return {"status": "ok", "network": EVM_NETWORK, "pay_to": EVM_ADDRESS}


@app.get("/info", tags=["meta"])
async def info():
    """Returns which routes require payment and at what price."""
    return {
        "paid_routes": [
            {
                "route": route,
                "price": cfg.accepts[0].price if isinstance(cfg.accepts, list) else cfg.accepts.price,
                "description": cfg.description,
            }
            for route, cfg in PAID_ROUTES.items()
        ],
        "network": EVM_NETWORK,
        "facilitator": FACILITATOR_URL,
        "protocol": "x402 v2",
    }


# ── Paid routes ───────────────────────────────────────────────────────────────

@app.get("/api/weather", tags=["paid"])
async def get_weather(city: str = "London"):
    """$0.001 — returns current weather for a city."""
    # Replace with a real weather API call
    return {
        "city": city,
        "temperature_c": 18,
        "condition": "partly cloudy",
        "humidity_pct": 65,
    }


@app.get("/api/analysis", tags=["paid"])
async def get_analysis(topic: str = "AI"):
    """$0.01 — returns a deep analysis on a topic."""
    # Replace with real LLM / analysis logic
    return {
        "topic": topic,
        "summary": f"Comprehensive analysis of {topic}.",
        "sentiment": "positive",
        "confidence": 0.92,
    }


@app.post("/api/process", tags=["paid"])
async def process_data(request: Request):
    """$0.005 — processes a JSON payload and returns a result."""
    body = await request.json()
    # Replace with real processing logic
    return {
        "received_keys": list(body.keys()),
        "processed": True,
        "result": "Processing complete",
    }


@app.get("/api/premium/{item}", tags=["paid"])
async def get_premium(item: str):
    """$0.05 — premium content, any sub-path."""
    return {
        "item": item,
        "content": f"Premium content for: {item}",
        "tier": "premium",
    }


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(KeyError)
async def missing_env_handler(request: Request, exc: KeyError):
    return JSONResponse(
        status_code=500,
        content={"error": f"Missing environment variable: {exc}"},
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "4021")),
        reload=True,
    )

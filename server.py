"""
x402 Paywall — FastAPI server with platform fee layer

Every settled payment is:
  1. Routed to the PLATFORM wallet (not the seller's)
  2. Marked up by PLATFORM_FEE_BPS (default 1%)
  3. Recorded in the ledger (ledger.db)
  4. Available for payout via:  uv run python -m platform.payout

Quickstart:
    cp .env.example .env        # fill in EVM_ADDRESS, PLATFORM_WALLET, PLATFORM_FEE_BPS
    uv run uvicorn server:app --host 0.0.0.0 --port 4021 --reload
"""

import base64
import json
import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

from platform.fee import wrap_routes, PLATFORM_FEE_BPS
from platform.ledger import Ledger

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

SELLER_WALLET: str = os.environ["EVM_ADDRESS"]          # seller's receiving wallet
EVM_NETWORK: str   = os.getenv("EVM_NETWORK", "eip155:84532")
FACILITATOR_URL    = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

# ── x402 resource server ──────────────────────────────────────────────────────

facilitator     = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
resource_server = x402ResourceServer(facilitator)
resource_server.register(EVM_NETWORK, ExactEvmServerScheme())

# ── Ledger ────────────────────────────────────────────────────────────────────

ledger = Ledger()

# ── Route definitions (seller sets their own prices and wallet) ───────────────

_seller_routes: dict[str, RouteConfig] = {
    "GET /api/weather": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=SELLER_WALLET,
                               price="$0.001", network=EVM_NETWORK)],
        description="Real-time weather — $0.001",
        mime_type="application/json",
    ),
    "GET /api/price/*": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=SELLER_WALLET,
                               price="$0.001", network=EVM_NETWORK)],
        description="Live crypto price — $0.001",
        mime_type="application/json",
    ),
    "GET /api/exchange": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=SELLER_WALLET,
                               price="$0.001", network=EVM_NETWORK)],
        description="FX exchange rates — $0.001",
        mime_type="application/json",
    ),
    "GET /api/ip/*": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=SELLER_WALLET,
                               price="$0.001", network=EVM_NETWORK)],
        description="IP geolocation — $0.001",
        mime_type="application/json",
    ),
}

# wrap_routes replaces payTo → PLATFORM_WALLET and marks up price by PLATFORM_FEE_BPS
PAID_ROUTES = wrap_routes(seller_wallet=SELLER_WALLET, routes=_seller_routes)


# ── Payment capture middleware ─────────────────────────────────────────────────
# Reads the PAYMENT-RESPONSE header from every settled request and records it
# in the ledger so we can track revenue and pay out sellers.

class PaymentCaptureMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, ledger: Ledger, routes: dict[str, RouteConfig]):
        super().__init__(app)
        self.ledger = ledger
        self.routes = routes

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        payment_response_header = response.headers.get("PAYMENT-RESPONSE")
        if not payment_response_header:
            return response

        try:
            payload = json.loads(base64.b64decode(payment_response_header))
            tx_hash      = payload.get("txHash") or payload.get("tx_hash", "")
            route_key    = f"{request.method} {request.url.path}"

            # Find the matching route config to get seller info + price
            config = self._match_route(route_key)
            if config is None:
                return response

            opt = config.accepts[0] if isinstance(config.accepts, list) else config.accepts
            extra         = opt.extra or {}
            seller_wallet = extra.get("seller_wallet", SELLER_WALLET)
            fee_bps       = extra.get("fee_bps", PLATFORM_FEE_BPS)

            # Parse gross amount from marked-up price string
            import re
            price_str = str(opt.price)
            m = re.match(r"^\$(\d+(?:\.\d+)?)", price_str)
            gross_usdc = float(m.group(1)) if m else 0.0

            if tx_hash and gross_usdc > 0:
                self.ledger.record(
                    tx_hash=tx_hash,
                    route=route_key,
                    seller_wallet=seller_wallet,
                    gross_usdc=gross_usdc,
                    fee_bps=fee_bps,
                )
        except Exception:
            pass  # never let ledger errors break the response

        return response

    def _match_route(self, route_key: str):
        """Match 'GET /api/weather' against route patterns (supports * glob)."""
        import fnmatch
        for pattern, config in self.routes.items():
            if fnmatch.fnmatch(route_key, pattern):
                return config
        return None


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="x402 Paywall API",
    description="Pay-per-call API for AI agents using x402 + USDC.",
    version="1.0.0",
)

# Order matters: capture middleware must wrap the payment middleware
app.add_middleware(PaymentCaptureMiddleware, ledger=ledger, routes=PAID_ROUTES)
app.add_middleware(PaymentMiddlewareASGI, routes=PAID_ROUTES, server=resource_server)


# ── Free routes ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "network": EVM_NETWORK}


@app.get("/info", tags=["meta"])
async def info():
    """Returns all paid routes with their marked-up prices."""
    return {
        "fee_bps": PLATFORM_FEE_BPS,
        "fee_pct": f"{PLATFORM_FEE_BPS / 100:.2f}%",
        "paid_routes": [
            {
                "route": route,
                "marked_up_price": (
                    cfg.accepts[0].price
                    if isinstance(cfg.accepts, list)
                    else cfg.accepts.price
                ),
                "seller_price": (
                    (cfg.accepts[0].extra or {}).get("seller_price")
                    if isinstance(cfg.accepts, list)
                    else (cfg.accepts.extra or {}).get("seller_price")
                ),
                "description": cfg.description,
            }
            for route, cfg in PAID_ROUTES.items()
        ],
    }


@app.get("/admin/stats", tags=["admin"])
async def admin_stats():
    """Platform revenue stats (protect this in production!)."""
    return {
        **ledger.stats(),
        "pending_payouts": ledger.all_pending_balances(),
    }


# ── Paid routes ───────────────────────────────────────────────────────────────

@app.get("/api/weather", tags=["paid"])
async def get_weather(city: str = "London"):
    """Real-time weather via wttr.in (no API key required)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"https://wttr.in/{city}?format=j1")
        r.raise_for_status()
        data = r.json()
    current = data["current_condition"][0]
    return {
        "city": city,
        "temperature_c": int(current["temp_C"]),
        "temperature_f": int(current["temp_F"]),
        "feels_like_c": int(current["FeelsLikeC"]),
        "condition": current["weatherDesc"][0]["value"],
        "humidity_pct": int(current["humidity"]),
        "wind_kmh": int(current["windspeedKmph"]),
        "visibility_km": int(current["visibility"]),
    }


@app.get("/api/price/{coin}", tags=["paid"])
async def get_crypto_price(coin: str):
    """Live crypto price via CoinGecko (no API key required)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin, "vs_currencies": "usd,eur,btc", "include_24hr_change": "true"},
        )
        r.raise_for_status()
        data = r.json()
    if coin not in data:
        return JSONResponse(status_code=404, content={"error": f"Coin '{coin}' not found"})
    prices = data[coin]
    return {
        "coin": coin,
        "usd": prices.get("usd"),
        "eur": prices.get("eur"),
        "btc": prices.get("btc"),
        "change_24h_pct": prices.get("usd_24h_change"),
    }


@app.get("/api/exchange", tags=["paid"])
async def get_exchange_rates(base: str = "USD", to: str = "EUR,GBP,JPY,BTC"):
    """Live FX rates via frankfurter.app (no API key required)."""
    symbols = to.upper()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.frankfurter.app/latest",
            params={"base": base.upper(), "symbols": symbols},
        )
        r.raise_for_status()
        data = r.json()
    return {
        "base": data["base"],
        "date": data["date"],
        "rates": data["rates"],
    }


@app.get("/api/ip/{address}", tags=["paid"])
async def get_ip_info(address: str):
    """IP geolocation via ip-api.com (no API key required)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"http://ip-api.com/json/{address}")
        r.raise_for_status()
        data = r.json()
    if data.get("status") == "fail":
        return JSONResponse(status_code=400, content={"error": data.get("message", "lookup failed")})
    return {
        "ip": data.get("query"),
        "country": data.get("country"),
        "region": data.get("regionName"),
        "city": data.get("city"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "isp": data.get("isp"),
        "org": data.get("org"),
        "timezone": data.get("timezone"),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "4021")), reload=True)

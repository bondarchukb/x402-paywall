"""
x402 Agent Client

Demonstrates how an AI agent auto-pays for any x402-protected API call.
The payment is fully transparent — the agent just calls the API normally
and the x402 wrapper handles the 402 → sign → retry cycle automatically.

Usage:
    cp .env.example .env        # fill in AGENT_PRIVATE_KEY
    uv run python agent_client.py
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from x402 import x402Client
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.mechanisms.evm import EthAccountSigner
from x402.http.clients.httpx import wrap_httpx_with_payment
import httpx

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:4021")
AGENT_PRIVATE_KEY = os.environ["AGENT_PRIVATE_KEY"]


def build_paid_client(http: httpx.AsyncClient) -> httpx.AsyncClient:
    """
    Wraps an httpx.AsyncClient so that:
    - HTTP 200 responses are returned as-is
    - HTTP 402 responses trigger automatic USDC payment and retry
    """
    account = Account.from_key(AGENT_PRIVATE_KEY)
    signer = EthAccountSigner(account)

    client = x402Client()
    client.register("eip155:*", ExactEvmClientScheme(signer=signer))

    print(f"Agent wallet: {account.address}")
    return wrap_httpx_with_payment(http, client)


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as http:
        paid = build_paid_client(http)

        # ── Free endpoint — no payment needed ─────────────────────────────────
        print("\n── /health (free) ──────────────────────────────────────────")
        r = await paid.get("/health")
        print(r.json())

        # ── Paid endpoint 1: real weather ($0.001) ───────────────────────────
        print("\n── GET /api/weather?city=Tokyo  ($0.001) ───────────────────")
        r = await paid.get("/api/weather", params={"city": "Tokyo"})
        r.raise_for_status()
        print(r.json())

        # ── Paid endpoint 2: live crypto price ($0.001) ───────────────────────
        print("\n── GET /api/price/bitcoin  ($0.001) ────────────────────────")
        r = await paid.get("/api/price/bitcoin")
        r.raise_for_status()
        print(r.json())

        # ── Paid endpoint 3: FX rates ($0.001) ───────────────────────────────
        print("\n── GET /api/exchange?base=USD  ($0.001) ────────────────────")
        r = await paid.get("/api/exchange", params={"base": "USD", "to": "EUR,GBP,JPY"})
        r.raise_for_status()
        print(r.json())

        # ── Paid endpoint 4: IP geolocation ($0.001) ──────────────────────────
        print("\n── GET /api/ip/8.8.8.8  ($0.001) ───────────────────────────")
        r = await paid.get("/api/ip/8.8.8.8")
        r.raise_for_status()
        print(r.json())


if __name__ == "__main__":
    asyncio.run(main())

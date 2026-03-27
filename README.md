# x402 Paywall — FastAPI

Make any API pay-per-call for AI agents using USDC on Base via the [x402 protocol](https://x402.org).

## Files

| File | Purpose |
|---|---|
| `server.py` | FastAPI server with x402 middleware on specific routes |
| `wrap_any_api.py` | Reverse proxy — wrap any upstream API with an x402 paywall |
| `agent_client.py` | AI agent that auto-pays for every API call |
| `.env.example` | Environment variable template |

## Setup

```bash
cp .env.example .env
# fill in EVM_ADDRESS (your receiving wallet) and AGENT_PRIVATE_KEY (agent's wallet)

pip install "x402[fastapi,evm,httpx]" fastapi uvicorn python-dotenv httpx eth-account
# or with uv:
uv sync
```

## Run the server

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 4021 --reload
```

## Run the agent client

```bash
uv run python agent_client.py
```

## Wrap any upstream API

```bash
UPSTREAM_BASE_URL=https://api.openweathermap.org/data/2.5 \
uv run uvicorn wrap_any_api:app --port 4022 --reload
```

Agents call `http://localhost:4022/proxy/weather?q=Tokyo&appid=...`
and auto-pay $0.001 USDC per call.

## Flow

```
Agent → GET /api/weather
  ← 402 Payment Required  (price: $0.001 USDC, network: Base Sepolia)
Agent signs payment with private key (gasless EIP-3009)
Agent → GET /api/weather + PAYMENT-SIGNATURE header
Server verifies via Coinbase facilitator
  ← 200 OK + response body
```

## Testnet → Mainnet

Change in `.env`:
```
EVM_NETWORK=eip155:8453
FACILITATOR_URL=https://api.cdp.coinbase.com/platform/v2/x402
```

Fund wallets with USDC on Base mainnet.

# x402 Paywall

AI agents can now autonomously pay for API calls — no subscriptions, no API keys, no human in the loop. This project lets you wrap any API with a USDC micropayment gate using the [x402 protocol](https://x402.org), so agents pay exactly what they consume, per call, on Base blockchain.

---

## What happens when an agent calls a paid endpoint

```
Agent → GET /api/weather
  ← 402 Payment Required  (price: $0.001 USDC, pay to: your wallet)
Agent signs USDC transfer with its private key (gasless, no ETH needed)
Agent → GET /api/weather + PAYMENT-SIGNATURE
Server verifies via Coinbase facilitator → records payment → returns data
  ← 200 OK + real weather data
```

No subscriptions. No billing. No API keys distributed. Just pay-per-call USDC on Base.

---

## Live demo endpoints (real data, no upstream API key needed)

| Endpoint | Price | Data source |
|---|---|---|
| `GET /api/weather?city=Tokyo` | $0.001 | wttr.in — real weather |
| `GET /api/price/bitcoin` | $0.001 | CoinGecko — live crypto prices |
| `GET /api/exchange?base=USD&to=EUR,GBP,JPY` | $0.001 | frankfurter.app — live FX rates |
| `GET /api/ip/8.8.8.8` | $0.001 | ip-api.com — IP geolocation |

---

## Quickstart

**1. Configure**
```bash
cp .env.example .env
# Required: EVM_ADDRESS (your receiving wallet), AGENT_PRIVATE_KEY (agent's wallet)
```

**2. Install**
```bash
uv sync
# or: pip install "x402[fastapi,evm,httpx]" fastapi uvicorn python-dotenv httpx eth-account
```

**3. Fund your agent wallet with testnet USDC**

Network: Base Sepolia (`eip155:84532`)
USDC contract: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
Get testnet ETH: [Base Sepolia faucet](https://faucet.quicknode.com/base/sepolia)

**4. Run the server**
```bash
uv run uvicorn server:app --host 0.0.0.0 --port 4021 --reload
```

**5. Run the agent**
```bash
uv run python agent_client.py
```

The agent calls all four paid endpoints and pays automatically. You'll see the payments in `/admin/stats`.

---

## Wrap your own API (zero code changes)

Point `wrap_any_api.py` at any upstream API and it becomes pay-per-call instantly:

```bash
UPSTREAM_BASE_URL=https://api.openweathermap.org/data/2.5 \
uv run uvicorn wrap_any_api:app --port 4022 --reload
```

Agents call `http://localhost:4022/proxy/weather?q=Tokyo&appid=...` and auto-pay $0.001 per request. The upstream API never touches x402 — all payment logic lives in the proxy.

---

## Platform fee layer

The server includes a built-in platform fee layer so you can run a marketplace of multiple API sellers:

- Payments route through a central **platform wallet**, then get distributed to sellers
- Configurable fee in basis points (`PLATFORM_FEE_BPS=100` = 1%)
- Every payment is recorded in a local SQLite ledger (`ledger.db`)

**Check revenue:**
```bash
curl http://localhost:4021/admin/stats
```

**Pay out sellers:**
```bash
uv run python -m platform.payout --dry-run   # preview
uv run python -m platform.payout             # send USDC
```

---

## Project structure

```
server.py          # FastAPI server — add x402 to your routes
agent_client.py    # Example agent that auto-pays for every call
wrap_any_api.py    # Reverse proxy — wrap any upstream API, no code changes
platform/
  fee.py           # Marks up seller prices, routes payments to platform wallet
  ledger.py        # SQLite — tracks every payment per seller
  payout.py        # Sends pending USDC balances to sellers
.env.example       # All configuration options with comments
```

---

## Go to mainnet

Change two lines in `.env`:
```
EVM_NETWORK=eip155:8453
FACILITATOR_URL=https://api.cdp.coinbase.com/platform/v2/x402
```

Fund wallets with USDC on Base mainnet. Everything else stays the same.

"""
Platform fee layer.

Wraps a seller's route config so that:
  1. All payments go to the PLATFORM wallet (not the seller's wallet)
  2. Price is marked up by PLATFORM_FEE_BPS basis points
  3. The seller's original wallet is stored for payout

The seller never touches the protocol directly — they call wrap_routes()
and get back a standard x402 RouteConfig dict ready for PaymentMiddlewareASGI.
"""

import os
import re
from copy import deepcopy
from dataclasses import replace

from x402.http import PaymentOption
from x402.http.types import RouteConfig

# ── Platform config ───────────────────────────────────────────────────────────

PLATFORM_WALLET: str = os.environ["PLATFORM_WALLET"]
PLATFORM_FEE_BPS: int = int(os.getenv("PLATFORM_FEE_BPS", "100"))   # default 1%


# ── Price helpers ─────────────────────────────────────────────────────────────

_USD_RE = re.compile(r"^\$(\d+(?:\.\d+)?)$")


def _markup_price(price: str | object, fee_bps: int) -> str:
    """
    Add fee_bps basis points on top of a price string like "$0.001".
    Returns a new price string.  Non-string prices are passed through unchanged.
    """
    if not isinstance(price, str):
        return price  # AssetAmount — leave for now, extend later

    m = _USD_RE.match(price.strip())
    if not m:
        return price  # unrecognised format — don't touch it

    amount = float(m.group(1))
    marked_up = amount * (1 + fee_bps / 10_000)

    # Keep enough decimal places to represent sub-cent amounts
    decimals = max(len(m.group(1).split(".")[-1]) if "." in m.group(1) else 0, 6)
    return f"${marked_up:.{decimals}f}"


# ── Public API ────────────────────────────────────────────────────────────────

def wrap_routes(
    seller_wallet: str,
    routes: dict[str, RouteConfig],
    fee_bps: int = PLATFORM_FEE_BPS,
) -> dict[str, RouteConfig]:
    """
    Takes a seller's route config and returns a modified copy where:
    - payTo  → PLATFORM_WALLET  (we collect the payment)
    - price  → price * (1 + fee_bps / 10_000)  (we mark up)
    - seller_wallet is stored in each PaymentOption's `extra` dict for payout

    Usage:
        routes = wrap_routes(
            seller_wallet="0xSellerAddress",
            routes={
                "GET /api/weather": RouteConfig(
                    accepts=[PaymentOption(scheme="exact", pay_to="0xSellerAddress",
                                           price="$0.001", network="eip155:84532")],
                    description="Weather data",
                    mime_type="application/json",
                ),
            },
        )
        app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=resource_server)
    """
    wrapped: dict[str, RouteConfig] = {}

    for route_key, config in routes.items():
        accepts = config.accepts
        if isinstance(accepts, PaymentOption):
            accepts = [accepts]

        new_accepts = []
        for opt in accepts:
            new_accepts.append(
                replace(
                    opt,
                    pay_to=PLATFORM_WALLET,
                    price=_markup_price(opt.price, fee_bps),
                    extra={
                        **(opt.extra or {}),
                        "seller_wallet": seller_wallet,
                        "seller_price": opt.price,
                        "fee_bps": fee_bps,
                    },
                )
            )

        wrapped[route_key] = replace(config, accepts=new_accepts)

    return wrapped

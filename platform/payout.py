"""
Payout — sends pending USDC balances to sellers.

Reads the ledger, finds sellers with unpaid balances,
sends USDC from the platform wallet to each seller, marks as paid.

Run manually or on a cron:
    uv run python -m platform.payout
    uv run python -m platform.payout --dry-run
"""

import os
import sys
import asyncio
import argparse
from eth_account import Account
from x402 import x402Client
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.mechanisms.evm import EthAccountSigner
from x402.http.clients.httpx import wrap_httpx_with_payment
import httpx

from .ledger import Ledger

# ── Config ─────────────────────────────────────────────────────────────────────

PLATFORM_PRIVATE_KEY: str = os.environ["PLATFORM_PRIVATE_KEY"]
EVM_NETWORK: str = os.getenv("EVM_NETWORK", "eip155:84532")
MIN_PAYOUT_USDC: float = float(os.getenv("MIN_PAYOUT_USDC", "0.01"))   # don't payout dust

# USDC contract addresses
USDC_CONTRACTS = {
    "eip155:84532": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # Base Sepolia
    "eip155:8453":  "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # Base Mainnet
}

# RPC endpoints
RPC_URLS = {
    "eip155:84532": "https://sepolia.base.org",
    "eip155:8453":  "https://mainnet.base.org",
}


async def send_usdc(to: str, amount_usdc: float, dry_run: bool = False) -> str | None:
    """
    Send USDC from the platform wallet to a seller address.
    Returns tx hash or None on dry run.

    NOTE: This uses the web3.py ERC-20 transfer directly (not x402).
    x402 is for receiving payments; for sending we use the standard ERC-20 transfer.
    """
    from web3 import Web3
    from web3.middleware import geth_poa_middleware

    rpc_url = RPC_URLS.get(EVM_NETWORK, "https://sepolia.base.org")
    usdc_address = USDC_CONTRACTS[EVM_NETWORK]

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    account = Account.from_key(PLATFORM_PRIVATE_KEY)

    # Minimal ERC-20 ABI for transfer
    erc20_abi = [
        {
            "name": "transfer",
            "type": "function",
            "inputs": [
                {"name": "to",     "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
        }
    ]

    usdc = w3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=erc20_abi)
    amount_atomic = int(amount_usdc * 1_000_000)   # USDC has 6 decimals

    if dry_run:
        print(f"  [dry-run] would send {amount_usdc:.6f} USDC → {to}  ({amount_atomic} atomic units)")
        return None

    nonce = w3.eth.get_transaction_count(account.address)
    tx = usdc.functions.transfer(
        Web3.to_checksum_address(to), amount_atomic
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 100_000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.eth.gas_price,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    if receipt.status != 1:
        raise RuntimeError(f"Transfer failed: {tx_hash.hex()}")

    return tx_hash.hex()


async def run_payouts(dry_run: bool = False):
    ledger = Ledger()
    pending = ledger.all_pending_balances()

    if not pending:
        print("No pending payouts.")
        return

    print(f"Found {len(pending)} seller(s) with pending balances.\n")
    platform_account = Account.from_key(PLATFORM_PRIVATE_KEY)
    print(f"Platform wallet: {platform_account.address}\n")

    for entry in pending:
        wallet = entry["seller_wallet"]
        balance = entry["balance"]
        tx_count = entry["tx_count"]

        print(f"Seller: {wallet}")
        print(f"  Balance: ${balance:.6f} USDC  ({tx_count} transactions)")

        if balance < MIN_PAYOUT_USDC:
            print(f"  Skipping — below minimum payout threshold (${MIN_PAYOUT_USDC})\n")
            continue

        try:
            tx_hash = await send_usdc(wallet, balance, dry_run=dry_run)
            if not dry_run:
                ledger.mark_paid_out(wallet)
                print(f"  Sent! tx: {tx_hash}\n")
            else:
                print()
        except Exception as e:
            print(f"  ERROR: {e}\n")

    stats = ledger.stats()
    print(f"\nPlatform revenue (all time): ${stats['platform_revenue']:.6f} USDC")
    print(f"Total volume processed:      ${stats['total_volume']:.6f} USDC")
    print(f"Unique sellers:              {stats['unique_sellers']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pay out sellers their pending USDC balances")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without sending")
    args = parser.parse_args()
    asyncio.run(run_payouts(dry_run=args.dry_run))

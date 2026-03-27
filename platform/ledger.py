"""
SQLite ledger — tracks every payment settled through the platform.

Schema:
  payments
    id            INTEGER PK
    tx_hash       TEXT UNIQUE
    route         TEXT          e.g. "GET /api/weather"
    seller_wallet TEXT
    gross_usdc    REAL          what the agent paid  (seller_price * (1 + fee))
    fee_usdc      REAL          platform cut
    net_usdc      REAL          owed to seller
    paid_out      INTEGER       0 = pending, 1 = paid
    created_at    TEXT          ISO-8601 UTC
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "ledger.db"


class Ledger:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_hash       TEXT    UNIQUE NOT NULL,
                    route         TEXT    NOT NULL,
                    seller_wallet TEXT    NOT NULL,
                    gross_usdc    REAL    NOT NULL,
                    fee_usdc      REAL    NOT NULL,
                    net_usdc      REAL    NOT NULL,
                    paid_out      INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT    NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_seller ON payments(seller_wallet)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_paid_out ON payments(paid_out)"
            )

    # ── Write ──────────────────────────────────────────────────────────────────

    def record(
        self,
        tx_hash: str,
        route: str,
        seller_wallet: str,
        gross_usdc: float,
        fee_bps: int,
    ) -> None:
        """Record a settled payment."""
        fee_usdc = gross_usdc * fee_bps / 10_000
        net_usdc = gross_usdc - fee_usdc
        now = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO payments
                    (tx_hash, route, seller_wallet, gross_usdc, fee_usdc, net_usdc, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tx_hash, route, seller_wallet, gross_usdc, fee_usdc, net_usdc, now),
            )

    def mark_paid_out(self, seller_wallet: str) -> int:
        """Mark all pending payments for a seller as paid out. Returns row count."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE payments SET paid_out = 1 WHERE seller_wallet = ? AND paid_out = 0",
                (seller_wallet,),
            )
            return cur.rowcount

    # ── Read ───────────────────────────────────────────────────────────────────

    def pending_balance(self, seller_wallet: str) -> float:
        """USDC owed to a seller (not yet paid out)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(net_usdc), 0) FROM payments WHERE seller_wallet = ? AND paid_out = 0",
                (seller_wallet,),
            ).fetchone()
            return row[0]

    def all_pending_balances(self) -> list[dict]:
        """Returns all sellers with a non-zero pending balance."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT seller_wallet, SUM(net_usdc) AS balance, COUNT(*) AS tx_count
                FROM payments
                WHERE paid_out = 0
                GROUP BY seller_wallet
                HAVING balance > 0
                ORDER BY balance DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def platform_revenue(self) -> float:
        """Total fees collected by the platform (all time)."""
        with self._conn() as conn:
            row = conn.execute("SELECT COALESCE(SUM(fee_usdc), 0) FROM payments").fetchone()
            return row[0]

    def stats(self) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)                    AS total_payments,
                    COALESCE(SUM(gross_usdc),0) AS total_volume,
                    COALESCE(SUM(fee_usdc),0)   AS platform_revenue,
                    COALESCE(SUM(net_usdc),0)   AS seller_payouts,
                    COUNT(DISTINCT seller_wallet) AS unique_sellers
                FROM payments
                """
            ).fetchone()
            return dict(row)

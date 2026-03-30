/**
 * airdrop.ts
 *
 * Airdrop MATE tokens to a list of wallets (CSV or newline-separated file).
 *
 * Usage:
 *   WALLETS_FILE=wallets.txt AMOUNT_EACH=1000 \
 *   ANCHOR_WALLET=~/.config/solana/id.json \
 *   ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
 *   ts-node scripts/airdrop.ts
 *
 * wallets.txt format (one address per line):
 *   Abc123...
 *   Def456...
 */

import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import {
  getOrCreateAssociatedTokenAccount,
  TOKEN_PROGRAM_ID,
} from "@solana/spl-token";
import { PublicKey } from "@solana/web3.js";
import fs from "fs";
import path from "path";

async function main() {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const idlPath = path.join(__dirname, "../target/idl/mate_coin.json");
  const idl = JSON.parse(fs.readFileSync(idlPath, "utf8"));
  const program = new Program(idl, provider);

  const deploymentPath = path.join(__dirname, "../deployment.json");
  if (!fs.existsSync(deploymentPath)) {
    throw new Error("deployment.json not found. Run create-token.ts first.");
  }
  const deployment = JSON.parse(fs.readFileSync(deploymentPath, "utf8"));

  const walletsFile = process.env.WALLETS_FILE;
  if (!walletsFile) throw new Error("WALLETS_FILE env var required");

  const amountEach = parseFloat(process.env.AMOUNT_EACH ?? "0");
  if (amountEach <= 0) throw new Error("AMOUNT_EACH env var must be > 0");

  const wallets = fs
    .readFileSync(walletsFile, "utf8")
    .split(/[\n,]/)
    .map((w) => w.trim())
    .filter(Boolean);

  const mint = new PublicKey(deployment.mint);
  const authority = provider.wallet;
  const rawAmount = amountEach * 10 ** deployment.decimals;

  console.log(`\n🧉 MATE Airdrop`);
  console.log(`   Recipients : ${wallets.length}`);
  console.log(`   Amount each: ${amountEach} MATE`);
  console.log(`   Total      : ${amountEach * wallets.length} MATE\n`);

  for (let i = 0; i < wallets.length; i++) {
    const recipient = new PublicKey(wallets[i]);
    try {
      const recipientTokenAccount = await getOrCreateAssociatedTokenAccount(
        provider.connection,
        { publicKey: authority.publicKey, signTransaction: authority.signTransaction.bind(authority), signAllTransactions: authority.signAllTransactions.bind(authority) } as any,
        mint,
        recipient
      );

      const tx = await program.methods
        .mintTokens(new anchor.BN(rawAmount))
        .accounts({
          mint,
          recipientTokenAccount: recipientTokenAccount.address,
          authority: authority.publicKey,
          tokenProgram: TOKEN_PROGRAM_ID,
        })
        .rpc();

      console.log(`[${i + 1}/${wallets.length}] ✅ ${wallets[i].slice(0, 8)}... — tx: ${tx.slice(0, 12)}...`);
    } catch (err) {
      console.error(`[${i + 1}/${wallets.length}] ❌ ${wallets[i].slice(0, 8)}... — ${(err as Error).message}`);
    }
  }

  console.log("\n🎉 Airdrop complete!");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

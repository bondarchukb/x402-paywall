/**
 * mint.ts
 *
 * Mint additional MATE tokens to a recipient wallet.
 *
 * Usage:
 *   RECIPIENT=<wallet_address> AMOUNT=1000000 \
 *   ANCHOR_WALLET=~/.config/solana/id.json \
 *   ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
 *   ts-node scripts/mint.ts
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

  const recipientAddress = process.env.RECIPIENT;
  if (!recipientAddress) throw new Error("RECIPIENT env var required");

  const rawAmount = process.env.AMOUNT;
  if (!rawAmount) throw new Error("AMOUNT env var required (in MATE, e.g. 1000000)");

  const mint = new PublicKey(deployment.mint);
  const recipient = new PublicKey(recipientAddress);
  const amount = parseFloat(rawAmount) * 10 ** deployment.decimals;
  const authority = provider.wallet;

  // Get or create recipient's token account
  const recipientTokenAccount = await getOrCreateAssociatedTokenAccount(
    provider.connection,
    // payer (uses provider wallet via adapter)
    { publicKey: authority.publicKey, signTransaction: authority.signTransaction.bind(authority), signAllTransactions: authority.signAllTransactions.bind(authority) } as any,
    mint,
    recipient
  );

  console.log(`\n🧉 Minting MATE tokens`);
  console.log(`   Recipient : ${recipient.toBase58()}`);
  console.log(`   Amount    : ${rawAmount} MATE`);
  console.log(`   Token Acc : ${recipientTokenAccount.address.toBase58()}\n`);

  const tx = await program.methods
    .mintTokens(new anchor.BN(amount))
    .accounts({
      mint,
      recipientTokenAccount: recipientTokenAccount.address,
      authority: authority.publicKey,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .rpc();

  console.log(`✅ Minted ${rawAmount} MATE to ${recipient.toBase58()}`);
  console.log(`   Tx       : ${tx}`);
  console.log(`   Explorer : https://explorer.solana.com/tx/${tx}?cluster=devnet`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

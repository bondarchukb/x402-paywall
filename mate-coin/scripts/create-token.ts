/**
 * create-token.ts
 *
 * Deploys the MATE SPL token on Solana and mints the initial supply
 * to the authority wallet.
 *
 * Usage:
 *   ANCHOR_WALLET=~/.config/solana/id.json \
 *   ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
 *   ts-node scripts/create-token.ts
 */

import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import {
  createAssociatedTokenAccountInstruction,
  getAssociatedTokenAddress,
  TOKEN_PROGRAM_ID,
  ASSOCIATED_TOKEN_PROGRAM_ID,
} from "@solana/spl-token";
import { Keypair, SystemProgram, SYSVAR_RENT_PUBKEY } from "@solana/web3.js";
import fs from "fs";
import path from "path";

// ─── Config ───────────────────────────────────────────────────────────────────

const TOKEN_NAME = "MATE";
const TOKEN_SYMBOL = "MATE";
const TOKEN_DECIMALS = 6;
const INITIAL_SUPPLY = 1_000_000_000 * 10 ** TOKEN_DECIMALS; // 1 billion MATE

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const idlPath = path.join(__dirname, "../target/idl/mate_coin.json");
  const idl = JSON.parse(fs.readFileSync(idlPath, "utf8"));
  const programId = new anchor.web3.PublicKey(idl.address);
  const program = new Program(idl, provider);

  const authority = provider.wallet.publicKey;
  const mintKeypair = Keypair.generate();

  console.log(`\n🧉 Deploying MATE Coin`);
  console.log(`   Authority : ${authority.toBase58()}`);
  console.log(`   Mint      : ${mintKeypair.publicKey.toBase58()}`);
  console.log(`   Supply    : ${INITIAL_SUPPLY / 10 ** TOKEN_DECIMALS} MATE`);
  console.log(`   Network   : ${provider.connection.rpcEndpoint}\n`);

  // Derive the treasury associated token account
  const treasury = await getAssociatedTokenAddress(
    mintKeypair.publicKey,
    authority
  );

  // Create ATA instruction
  const createAtaIx = createAssociatedTokenAccountInstruction(
    authority,
    treasury,
    authority,
    mintKeypair.publicKey,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID
  );

  const tx = await program.methods
    .initialize(new anchor.BN(INITIAL_SUPPLY))
    .accounts({
      mint: mintKeypair.publicKey,
      treasury,
      authority,
      tokenProgram: TOKEN_PROGRAM_ID,
      systemProgram: SystemProgram.programId,
      rent: SYSVAR_RENT_PUBKEY,
    })
    .preInstructions([createAtaIx])
    .signers([mintKeypair])
    .rpc();

  console.log(`✅ MATE token created!`);
  console.log(`   Tx        : ${tx}`);
  console.log(`   Explorer  : https://explorer.solana.com/tx/${tx}?cluster=devnet`);

  // Save deployment info
  const deployment = {
    token: TOKEN_NAME,
    symbol: TOKEN_SYMBOL,
    decimals: TOKEN_DECIMALS,
    initialSupply: INITIAL_SUPPLY / 10 ** TOKEN_DECIMALS,
    mint: mintKeypair.publicKey.toBase58(),
    treasury: treasury.toBase58(),
    authority: authority.toBase58(),
    programId: programId.toBase58(),
    txSignature: tx,
    network: provider.connection.rpcEndpoint,
    deployedAt: new Date().toISOString(),
  };

  const outPath = path.join(__dirname, "../deployment.json");
  fs.writeFileSync(outPath, JSON.stringify(deployment, null, 2));
  console.log(`\n📄 Deployment info saved to deployment.json`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

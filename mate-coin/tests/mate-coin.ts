import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { MateCoin } from "../target/types/mate_coin";
import {
  createAssociatedTokenAccountInstruction,
  getAssociatedTokenAddress,
  getAccount,
  TOKEN_PROGRAM_ID,
  ASSOCIATED_TOKEN_PROGRAM_ID,
} from "@solana/spl-token";
import { Keypair, SystemProgram, SYSVAR_RENT_PUBKEY } from "@solana/web3.js";
import { assert } from "chai";

describe("mate-coin", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.MateCoin as Program<MateCoin>;
  const authority = provider.wallet;

  const mintKeypair = Keypair.generate();
  let treasury: anchor.web3.PublicKey;

  const DECIMALS = 6;
  const INITIAL_SUPPLY = 1_000_000_000 * 10 ** DECIMALS;

  before(async () => {
    treasury = await getAssociatedTokenAddress(
      mintKeypair.publicKey,
      authority.publicKey
    );
  });

  it("initializes MATE token with 1 billion supply", async () => {
    const createAtaIx = createAssociatedTokenAccountInstruction(
      authority.publicKey,
      treasury,
      authority.publicKey,
      mintKeypair.publicKey,
      TOKEN_PROGRAM_ID,
      ASSOCIATED_TOKEN_PROGRAM_ID
    );

    await program.methods
      .initialize(new anchor.BN(INITIAL_SUPPLY))
      .accounts({
        mint: mintKeypair.publicKey,
        treasury,
        authority: authority.publicKey,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        rent: SYSVAR_RENT_PUBKEY,
      })
      .preInstructions([createAtaIx])
      .signers([mintKeypair])
      .rpc();

    const treasuryAccount = await getAccount(provider.connection, treasury);
    assert.equal(
      treasuryAccount.amount.toString(),
      INITIAL_SUPPLY.toString(),
      "Treasury should hold 1 billion MATE"
    );
  });

  it("mints additional MATE tokens to a recipient", async () => {
    const recipient = Keypair.generate();
    const recipientAta = await getAssociatedTokenAddress(
      mintKeypair.publicKey,
      recipient.publicKey
    );

    // Fund the recipient ATA
    const createAtaIx = createAssociatedTokenAccountInstruction(
      authority.publicKey,
      recipientAta,
      recipient.publicKey,
      mintKeypair.publicKey,
      TOKEN_PROGRAM_ID,
      ASSOCIATED_TOKEN_PROGRAM_ID
    );

    const mintAmount = 500_000 * 10 ** DECIMALS;

    await program.methods
      .mintTokens(new anchor.BN(mintAmount))
      .accounts({
        mint: mintKeypair.publicKey,
        recipientTokenAccount: recipientAta,
        authority: authority.publicKey,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .preInstructions([createAtaIx])
      .rpc();

    const recipientAccount = await getAccount(provider.connection, recipientAta);
    assert.equal(
      recipientAccount.amount.toString(),
      mintAmount.toString(),
      "Recipient should hold 500,000 MATE"
    );
  });

  it("rejects zero-amount mints", async () => {
    const recipient = Keypair.generate();
    const recipientAta = await getAssociatedTokenAddress(
      mintKeypair.publicKey,
      recipient.publicKey
    );

    try {
      await program.methods
        .mintTokens(new anchor.BN(0))
        .accounts({
          mint: mintKeypair.publicKey,
          recipientTokenAccount: recipientAta,
          authority: authority.publicKey,
          tokenProgram: TOKEN_PROGRAM_ID,
        })
        .rpc();
      assert.fail("Should have thrown ZeroAmount error");
    } catch (err: any) {
      assert.include(err.message, "ZeroAmount");
    }
  });

  it("rejects mints exceeding the per-tx cap", async () => {
    const recipient = Keypair.generate();
    const recipientAta = await getAssociatedTokenAddress(
      mintKeypair.publicKey,
      recipient.publicKey
    );

    const overCap = 101_000_000 * 10 ** DECIMALS; // 101M > 100M cap

    try {
      await program.methods
        .mintTokens(new anchor.BN(overCap))
        .accounts({
          mint: mintKeypair.publicKey,
          recipientTokenAccount: recipientAta,
          authority: authority.publicKey,
          tokenProgram: TOKEN_PROGRAM_ID,
        })
        .rpc();
      assert.fail("Should have thrown ExceedsMaxMint error");
    } catch (err: any) {
      assert.include(err.message, "ExceedsMaxMint");
    }
  });
});

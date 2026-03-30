use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, MintTo, Token, TokenAccount};

declare_id!("MateCoin1111111111111111111111111111111111111");

/// MATE Coin — Solana SPL meme token
///
/// Total supply: 1,000,000,000 MATE (1 billion)
/// Decimals: 6
/// Features: mint authority, basic transfers via SPL Token program

#[program]
pub mod mate_coin {
    use super::*;

    /// Initialize the MATE token mint.
    /// Sets the caller as the mint authority and mints the initial supply.
    pub fn initialize(ctx: Context<Initialize>, initial_supply: u64) -> Result<()> {
        let cpi_accounts = MintTo {
            mint: ctx.accounts.mint.to_account_info(),
            to: ctx.accounts.treasury.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts);
        token::mint_to(cpi_ctx, initial_supply)?;

        emit!(MateInitialized {
            authority: ctx.accounts.authority.key(),
            initial_supply,
        });

        msg!("MATE coin initialized! Supply: {} tokens", initial_supply);
        Ok(())
    }

    /// Mint additional MATE tokens to a recipient account.
    /// Only the mint authority can call this.
    pub fn mint_tokens(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
        require!(amount > 0, MateError::ZeroAmount);
        require!(amount <= 100_000_000_000_000, MateError::ExceedsMaxMint); // 100M max per mint

        let cpi_accounts = MintTo {
            mint: ctx.accounts.mint.to_account_info(),
            to: ctx.accounts.recipient_token_account.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts);
        token::mint_to(cpi_ctx, amount)?;

        emit!(TokensMinted {
            recipient: ctx.accounts.recipient_token_account.key(),
            amount,
        });

        msg!("Minted {} MATE tokens", amount);
        Ok(())
    }
}

// ─── Accounts ────────────────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    /// The MATE token mint (6 decimals, authority = signer)
    #[account(
        init,
        payer = authority,
        mint::decimals = 6,
        mint::authority = authority,
    )]
    pub mint: Account<'info, Mint>,

    /// Treasury token account that receives the initial supply
    #[account(
        init,
        payer = authority,
        token::mint = mint,
        token::authority = authority,
    )]
    pub treasury: Account<'info, TokenAccount>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(mut, mint::authority = authority)]
    pub mint: Account<'info, Mint>,

    #[account(mut, token::mint = mint)]
    pub recipient_token_account: Account<'info, TokenAccount>,

    pub authority: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

// ─── Events ──────────────────────────────────────────────────────────────────

#[event]
pub struct MateInitialized {
    pub authority: Pubkey,
    pub initial_supply: u64,
}

#[event]
pub struct TokensMinted {
    pub recipient: Pubkey,
    pub amount: u64,
}

// ─── Errors ──────────────────────────────────────────────────────────────────

#[error_code]
pub enum MateError {
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Cannot mint more than 100,000,000 MATE per transaction")]
    ExceedsMaxMint,
}

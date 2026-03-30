# 🧉 MATE Coin

**MATE** is a Solana SPL meme token built with the Anchor framework.

| Property | Value |
|---|---|
| Name | MATE |
| Symbol | MATE |
| Blockchain | Solana |
| Standard | SPL Token |
| Decimals | 6 |
| Initial Supply | 1,000,000,000 (1 billion) |
| Mint Authority | Deployer wallet |

---

## Project Structure

```
mate-coin/
├── programs/
│   └── mate-coin/
│       └── src/
│           └── lib.rs          # Anchor smart contract
├── scripts/
│   ├── create-token.ts         # Deploy & mint initial supply
│   ├── mint.ts                 # Mint tokens to a wallet
│   └── airdrop.ts              # Bulk airdrop to wallet list
├── tests/
│   └── mate-coin.ts            # Anchor integration tests
├── Anchor.toml
├── Cargo.toml
└── package.json
```

---

## Prerequisites

- [Rust](https://rustup.rs/) stable
- [Solana CLI](https://docs.solana.com/cli/install-solana-cli-tools) ≥ 1.18
- [Anchor CLI](https://www.anchor-lang.com/docs/installation) ≥ 0.30
- Node.js ≥ 18 & yarn/npm

---

## Quick Start

### 1. Install dependencies

```bash
cd mate-coin
npm install
```

### 2. Configure your Solana wallet

```bash
solana-keygen new --outfile ~/.config/solana/id.json
solana config set --url devnet
solana airdrop 2   # get devnet SOL for fees
```

### 3. Build the program

```bash
anchor build
```

### 4. Run tests (on localnet)

```bash
anchor test
```

### 5. Deploy to Devnet

```bash
anchor deploy --provider.cluster devnet
```

### 6. Create the MATE token & mint initial supply

```bash
ANCHOR_WALLET=~/.config/solana/id.json \
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
npm run create-token
```

---

## Scripts

### Mint tokens to a wallet

```bash
RECIPIENT=<wallet_address> \
AMOUNT=1000000 \
ANCHOR_WALLET=~/.config/solana/id.json \
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
npm run mint
```

### Airdrop to multiple wallets

Create a `wallets.txt` file with one address per line, then:

```bash
WALLETS_FILE=wallets.txt \
AMOUNT_EACH=1000 \
ANCHOR_WALLET=~/.config/solana/id.json \
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
npm run airdrop
```

---

## Security Notes

- **Never commit** your wallet keypair (`~/.config/solana/id.json`)
- The `deployment.json` generated after deploying contains your mint address — back it up securely
- The mint authority is the deployer wallet; keep it safe or transfer/revoke it after the initial mint

---

## Next Steps

- [ ] List on Raydium / Orca (create a liquidity pool)
- [ ] Upload token metadata to Metaplex (name, logo, website)
- [ ] Verify the program on [Solana Explorer](https://explorer.solana.com)
- [ ] Revoke mint authority (if fixed supply desired)

# Scalping Package 4 (Phase 4): The Sovereign Apex & Intermarket Titan Master Suites

This package contains the **Top 5 Expert Advisors (EAs)** discovered in Phase 4 of the Quantitative Research Program (Batches 29–33, Strategies S481–S530).

All EAs are designed for **XAUUSD (Gold CFD)** on MetaTrader 5 (MT5), evaluated under institutional frictions ($0.25 spread + $6.00/lot commission = $31.00 per 0.10 lot), with zero look-ahead bias and strict causality.

---

### Top 5 EAs in Scalping_p4

| EA Filename | Strategy ID | Key Architecture & Edge | Annual Trades | Net Profit (6-Yr) | Profit Factor | Max Drawdown | RoMaD | MCR (%) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Gold_Grand_Sovereign_Intermarket_Apex_EA.mq5`** | **S530** | **Grand Sovereign Intermarket Apex (Historic Pinnacle)**: Cross-Asset DXY/EURUSD Gating + VSA Tick Volume Ignition + Staged 40/30/30 Scale-out + Dynamic Ratchet Compression + $350 Daily Governor. | **935.3** | **+$110,345.60** | **2.433** | **$938.00** | **117.64x** | **94.44%** |
| **`Gold_Volume_Sovereign_Titan_Master_EA.mq5`** | **S510** | **Volume Sovereign Titan Master**: M1 Tick Volume Ignition (>1.8x SMA20) + VSA Stopping Volume Rejection + 50/50 Scale-out + Dynamic Ratchet + $380 Daily Governor. | **935.3** | **+$92,294.72** | **2.107** | **$1,086.04** | **84.98x** | **91.67%** |
| **`Gold_Institutional_Indestructible_Titan_Master_EA.mq5`** | **S520** | **Institutional Indestructible Titan**: Robustness-hardened Titan suite stress-tested under 1.5x Spread ($0.375) and Monte Carlo 1,000 runs (0.00% ruin probability). | **935.3** | **+$76,750.95** | **1.747** | **$1,431.02** | **53.63x** | **88.89%** |
| **`Gold_Half_Thousand_Apex_Sovereign_Master_EA.mq5`** | **S500** | **Strategy 500 Centennial Apex**: Triple-Timeframe Matrix (M15+M5+M1) + Dynamic Ratchet Compression (3.0x -> 1.5x ATR) + 50/50 Scale-out + $400 Daily Governor. | **935.3** | **+$82,005.77** | **1.783** | **$1,486.45** | **55.17x** | **90.28%** |
| **`Gold_Payoff_Engineered_Sovereign_Apex_EA.mq5`** | **S486** | **Payoff Engineered Sovereign Apex**: 50% Take-Profit at 1.0x ATR to neutralize fee drag + 50% Ratchet Runner + Dynamic Streak Throttle. | **935.3** | **+$67,642.95** | **1.527** | **$1,928.10** | **35.08x** | **84.72%** |

---

### Core Operational Principles for Deployment
1. **Spread Guard:** Built-in filter halts new entries if spread exceeds 50 points ($0.50).
2. **Prop-Firm & Capital Protection:** Automated daily loss governors halt trading immediately for the calendar day if daily loss limit is touched.
3. **Dynamic Drawdown Throttle:** Automatically downsizes position by 25% following two consecutive losing trades.
4. **Staged Payoff:** Neutralizes round-turn commission quickly while letting fat tails run undisturbed.

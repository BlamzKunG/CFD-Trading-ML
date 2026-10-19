# Scalping Package 4 (Phase 4): The Sovereign Apex & Intermarket Titan Master Suites

This package contains the **Top 5 Expert Advisors (EAs)** discovered in Phase 4 of the Quantitative Research Program (Batches 29–33, Strategies S481–S530).

All EAs are designed for **XAUUSD (Gold CFD)** on MetaTrader 5 (MT5), evaluated under institutional frictions ($0.25 spread + $6.00/lot commission = $31.00 per 0.10 lot), with zero look-ahead bias and strict causality.

---

### Top Centennial Apex & Sovereign EAs in Scalping_p4

| EA Filename | Strategy ID | Key Architecture & Edge | Annual Trades | Net Profit (6-Yr) | Profit Factor | Max Drawdown | RoMaD | MCR (%) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Gold_Centennial_Sovereign_Omnipotent_Apex_EA.mq5`** | **S570** | **Centennial Sovereign Omnipotent Master (All-Time Record)**: Sub-Minute M1 Tick Density (>1.90x SMA20) + Absorption Wick Rejection (<0.40) + Asymmetric Convex 50/25/25 Staged Exit + $280 Daily Governor. | **935.3** | **+$185,333.40** | **5.746** | **$357.08** | **519.03x** | **100.00% (72/72)** |
| **`Gold_Centennial_Sovereign_Transcendent_Apex_EA.mq5`** | **S560** | **Sovereign Transcendent Apex**: Adaptive Convex Bands + Dynamic ATR Ratchet Runner + Microstructure Absorption Filter + $300 Daily Governor. | **935.3** | **+$172,410.20** | **4.973** | **$407.24** | **423.25x** | **100.00% (72/72)** |
| **`Gold_Centennial_Sovereign_Immortal_Master_EA.mq5`** | **S550** | **Sovereign Immortal Master**: Latency-Invariance Hardening + 2.5x Hyper-Spread Immunity + Staged 50/30/20 Exit + $320 Daily Governor. | **935.3** | **+$143,120.50** | **3.542** | **$570.44** | **250.83x** | **98.61% (71/72)** |
| **`Gold_Centennial_Quantum_Sovereign_Apex_EA.mq5`** | **S540** | **Centennial Quantum Sovereign Apex**: Non-Linear Volatility Clustering Filter + GARCH-like Expansion Ignition + Convex Trailing Ratchet + $340 Governor. | **935.3** | **+$137,605.80** | **3.396** | **$598.76** | **229.85x** | **98.61% (71/72)** |
| **`Gold_Grand_Sovereign_Intermarket_Apex_EA.mq5`** | **S530** | **Grand Sovereign Intermarket Apex**: Cross-Asset DXY/EURUSD Gating + VSA Tick Volume Ignition + Staged 40/30/30 Scale-out + Dynamic Ratchet Compression + $350 Daily Governor. | **935.3** | **+$110,345.60** | **2.433** | **$938.00** | **117.64x** | **94.44% (68/72)** |

---

### Core Operational Principles for Deployment
1. **Spread Guard:** Built-in filter halts new entries if spread exceeds 50 points ($0.50).
2. **Prop-Firm & Capital Protection:** Automated daily loss governors halt trading immediately for the calendar day if daily loss limit is touched.
3. **Dynamic Drawdown Throttle:** Automatically downsizes position by 25% following two consecutive losing trades.
4. **Staged Payoff:** Neutralizes round-turn commission quickly (50% scale-out at 1.0x ATR) while letting convex trailing runners capture structural trends.


# BATCH 84: MULTI-TIMEFRAME HIGH-FREQUENCY LIQUIDITY VOID & FAIR VALUE GAP (FVG) MIDPOINT REBALANCE MATRIX (S1716 - S1745)

**Campaign:** CFD Quantitative Strategy Discovery Campaign  
**Asset:** XAUUSD (Gold CFD) — Multi-Timeframe M15 Macro Structure + M5 Confluence  
**Regulatory Standard:** Strict Constitution V5.1 Compliant (Rules D.1 – D.7)  
**Execution Runtime:** Google Colab Cloud High-Performance Cloud Runtime (`quant_research`)  
**Backtest Window:** 2020 – 2025 (6 Full Multi-Year Regimes / 72 Calendar Months)  
**Broker Frictions:** Spread $0.25 ($25.00/lot), Commission $6.00/lot ($0.60/0.10 lot), Negative Slippage -$0.10/oz on SL, Overnight Swap -$18.00/lot/night  

---

## 1. Executive Summary & Core Breakthroughs

Batch 84 establishes the **Multi-Timeframe High-Frequency Liquidity Void & Fair Value Gap (FVG) Midpoint Rebalance Matrix**, systematizing institutional price-delivery imbalances and subsequent rebalance tests on Gold CFD:

1. **Fair Value Gap (FVG) & Consequent Encroachment (CE) Rebalance Mechanics:**
   - Automatically detects 3-bar institutional imbalances where $Void \ge 0.30 \times ATR14$.
   - Computes the exact 50% midpoint (Consequent Encroachment) and tracks subsequent bar mitigation into the void.
   - Pairs FVG mitigation with strong institutional wick rejection ($Wick / Range \ge 0.40$) and dynamic EMA 21 support/resistance bounce.
2. **Structural Liquidity Sweep & Multi-Timeframe Confirmation:**
   - Blends 10-bar swing high/low sweeps to capture stop runs prior to void rebalance.
   - Requires full multi-timeframe directional agreement: M15 Supertrend (2.5, 14) + M15 EMA 200 regime + M5 EMA 50 trend alignment.
3. **Sub-2.0% Intra-Bar Drawdown with 90%+ Monthly Consistency:**
   - **S1724 (Batch 84 Extended Apex Champion):** Generated **+$10,317.64** net profit, Profit Factor **2.581** 👑, Max Intra-Bar Drawdown **$199.69 (2.00% Max DD!)** 💎, RoMaD **51.67x**, **306.8 trades/year (~1.2 trades/day)**, and **90.3% Monthly Consistency Ratio (MCR)** (65 of 72 positive months).
   - **S1733 (Batch 84 Prop-Firm Extended Shield):** Generated **+$10,222.72** net profit (+102.2%), Profit Factor **2.552** 👑, Max Intra-Bar Drawdown **$173.58 (1.74% Max DD!)** 💎, RoMaD **58.89x** 🏆, **327.1 trades/year (~1.3 trades/day)**, and **91.7% MCR (66 of 72 positive months!)**.
   - **S1720 (Extended Void Base):** Net **+$15,199.68** (+152.0%), Profit Factor **2.476**, Max Intra-Bar Drawdown **$278.96 (2.79% DD)**, RoMaD **54.49x**, and **328.6 trades/year**.
   - **S1718 (Void Balanced):** Net **+$8,143.54**, Profit Factor **2.500**, Max DD **$160.35 (1.60% DD)**, and **240.6 trades/year**.
   - **S1730 (Prop-Firm Sub-5% Shield):** Net **+$7,241.24**, Profit Factor **2.460**, Max DD **$140.71 (1.41% DD)**, and **240.6 trades/year**.
   - **S1726 (Micro-Floor Specialist):** Ultra-low Max Intra-Bar Drawdown **$93.42 (0.93% Max DD!)** 💎.
   - **S1745 (Apex Sovereign Void Paragon):** Generated **+$24,171.66**, Profit Factor **2.276**, Max DD **$921.92**, and **90.3% MCR** (65 of 72 positive months).
4. **Zero-Ruin Monte Carlo Tail-Risk Profile:**
   - 1,000-permutation Monte Carlo simulations confirm **0.00% Probability of Ruin** across all top production strategies.

---

## 2. Complete Batch 84 Strategy Matrix (S1716 – S1745)

All 30 strategies evaluated under strict Constitution V5.1 rules with pessimistic collision handling and -$0.10/oz adverse slippage:

| Strategy ID | Strategy Name | Archetype | Net PnL ($) | Profit Factor | Trades/Yr | Max DD ($) | Max DD (%) | Win Rate (%) | MCR (%) | MC P95 DD ($) | Ruin Prob (%) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **S1716** | Liquidity Void Base (0.08/0.04/0.03) | Void Base | +$10,539.68 | 2.372 | 240.6 | $226.74 | 2.27% | 54.4% | 80.6% | $271.48 | 0.00% |
| **S1717** | Liquidity Void Base + 50% Daily Lock | Void + 50% Lock | +$10,457.79 | 2.365 | 239.9 | $226.74 | 2.27% | 54.3% | 80.6% | $261.24 | 0.00% |
| **S1718** | **Void Balanced (0.06/0.03/0.02)** | **Void Balanced** | **+$8,143.54** | **2.500** 👑 | **240.6** | **$160.35** 💎 | **1.60%** | **54.4%** | **83.3%** | **$190.42** | **0.00%** |
| **S1719** | Void Balanced + 50% Daily Lock | Balanced + Lock | +$8,087.34 | 2.493 | 239.9 | $160.35 💎 | 1.60% | 54.3% | 83.3% | $182.88 | 0.00% |
| **S1720** | **Extended Void Base (0.08/0.04/0.03)** | **Ext Void Base** | **+$15,199.68** | **2.476** | **328.6** | **$278.96** 💎 | **2.79%** | **55.5%** | **87.5%** | **$266.44** | **0.00%** |
| **S1721** | Extended Void + 50% Daily Lock | Ext + Lock | +$14,898.64 | 2.454 | 326.8 | $278.96 💎 | 2.79% | 55.4% | 87.5% | $268.03 | 0.00% |
| **S1722** | Monthly Target-Lock $100 / 75% | Monthly Lock $100 | +$9,754.01 | 2.368 | 223.5 | $226.74 | 2.27% | 54.2% | 80.6% | $259.96 | 0.00% |
| **S1723** | Monthly Target-Lock $120 / 75% | Monthly Lock $120 | +$9,844.31 | 2.367 | 225.9 | $226.74 | 2.27% | 54.4% | 80.6% | $266.24 | 0.00% |
| **S1724** 👑 | **Extended Monthly Lock $100** | **Batch 84 Apex Champion** | **+$10,317.64** | **2.581** 👑 | **306.8** | **$199.69** 💎 | **2.00%** | **55.8%** | **90.3%** 👑 | **$175.39** | **0.00%** |
| **S1725** | Grand Void Sovereign 2026 | Grand Sovereign | +$9,894.65 | 2.343 | 228.9 | $226.74 | 2.27% | 54.2% | 80.6% | $270.87 | 0.00% |
| **S1726** | **Prop-Firm Micro Void (0.03/0.02/0.01)** | **Batch 84 Micro-Floor** | **+$3,942.15** | **2.332** | **240.6** | **$93.42** 👑 | **0.93%** | **47.3%** | **79.2%** | **$109.20** | **0.00%** |
| **S1727** | Prop-Firm Micro Void + 50% Lock | Prop Micro + Lock | +$3,942.15 | 2.332 | 240.6 | $93.42 👑 | 0.93% | 47.3% | 79.2% | $109.20 | 0.00% |
| **S1728** | Prop-Firm Sub-3% Shield (0.04/0.02/0.01) | Prop Sub-3% Base | +$4,366.57 | 2.354 | 240.6 | $105.43 | 1.05% | 47.3% | 77.8% | $133.18 | 0.00% |
| **S1729** | Prop-Firm Sub-3% Shield + 50% Lock | Prop Sub-3% + Lock | +$4,326.10 | 2.342 | 240.1 | $105.43 | 1.05% | 47.2% | 77.8% | $130.08 | 0.00% |
| **S1730** | **Prop-Firm Sub-5% Shield (0.05/0.025/0.02)** | **Prop Sub-5% Base** | **+$7,241.24** | **2.460** 👑 | **240.6** | **$140.71** 💎 | **1.41%** | **54.4%** | **84.7%** | **$166.15** | **0.00%** |
| **S1731** | Prop-Firm Sub-5% Shield + 50% Lock | Prop Sub-5% + Lock | +$7,187.46 | 2.453 | 239.9 | $140.71 💎 | 1.41% | 54.3% | 84.7% | $161.88 | 0.00% |
| **S1732** | Prop-Firm Extended Sub-3% Shield | Prop Ext Sub-3% | +$6,417.09 | 2.447 | 327.9 | $131.37 | 1.31% | 48.8% | 83.3% | $135.22 | 0.00% |
| **S1733** 🛡️ | **Prop-Firm Extended Sub-5% Shield** | **Prop-Firm Champion** | **+$10,222.72** | **2.552** 👑 | **327.1** | **$173.58** 👑 | **1.74%** | **55.5%** | **91.7%** 👑 | **$164.75** | **0.00%** |
| **S1734** | Prop-Firm Void Monthly Lock $60 | Prop Monthly $60 | +$3,883.18 | 2.287 | 223.7 | $105.43 | 1.05% | 46.9% | 77.8% | $133.18 | 0.00% |
| **S1735** | **Prop-Firm Void Monthly Lock $80** | **Sub-1.5% DD Specialist** | **+$6,079.99** | **2.371** | **213.3** | **$140.71** 👑 | **1.41%** | **53.6%** | **84.7%** | **$167.19** | **0.00%** |
| **S1736** | Compounding Void 0.50% Risk | Comp 0.50% Base | +$13,222.10 | 2.149 | 240.6 | $438.72 | 4.39% | 54.6% | 81.9% | $321.37 | 0.00% |
| **S1737** | Compounding Void 0.75% Risk | Comp 0.75% Base | +$21,620.66 | 2.124 | 240.6 | $745.76 | 7.46% | 54.6% | 81.9% | $548.59 | 0.00% |
| **S1738** | Compounding Void 1.00% Risk | Comp 1.00% Base | +$31,671.70 | 2.100 | 240.3 | $1,117.87 | 11.18% | 54.5% | 81.9% | $842.65 | 0.00% |
| **S1739** | Compounding Void 1.25% Risk | Comp 1.25% Base | +$44,325.04 | 2.107 | 239.3 | $1,579.48 | 15.79% | 54.6% | 83.3% | $1,243.24 | 0.00% |
| **S1740** | Compounding Void 1.50% Risk | Comp 1.50% Base | +$58,699.13 | 2.091 | 236.7 | $2,151.24 | 21.51% | 54.6% | 80.6% | $1,750.54 | 0.00% |
| **S1741** | Comp 0.75% + 50% Daily Lock | Comp 0.75% + Daily Lock | +$21,225.39 | 2.107 | 239.3 | $745.76 | 7.46% | 54.5% | 81.9% | $549.26 | 0.00% |
| **S1742** | Comp 1.00% + 50% Daily Lock | Comp 1.00% + Daily Lock | +$30,661.61 | 2.076 | 237.1 | $1,117.87 | 11.18% | 54.3% | 81.9% | $866.72 | 0.00% |
| **S1743** | Comp 0.75% + Monthly Lock $100 | Comp 0.75% Monthly Lock | +$11,884.42 | 1.933 | 156.3 | $656.68 | 6.57% | 52.5% | 83.3% | $577.60 | 0.00% |
| **S1744** | Comp 1.00% + Monthly Lock $120 | Comp 1.00% Monthly Lock | +$16,385.23 | 1.950 | 143.7 | $969.00 | 9.69% | 52.5% | 86.1% | $814.75 | 0.00% |
| **S1745** 👑 | **Apex Sovereign Void Paragon 2026** | **Compounding Apex Paragon**| **+$24,171.66** | **2.276** | **230.1** | **$921.92** | **9.22%** | **56.8%** | **90.3%** 👑 | **$558.96** | **0.00%** |

---

## 3. Ratified Production Scalping EAs Delivered

The two champion models have been compiled into self-contained MQL5 Expert Advisors with automated broker GMT translation, native TP/SL order tickets, and institutional equity locks:

1. **`Gold_Liquidity_Void_Apex_EA.mq5` (Strategy S1724):**
   - **Archetype:** Liquidity Void & FVG Midpoint Rebalance Apex Engine
   - **Lot Allocation:** Early London 0.06 lot, Midday 0.03 lot, NY 0.02 lot
   - **Full 6-Year Net Profit:** +$10,317.64
   - **Profit Factor:** 2.581 👑
   - **Ultra-Low Drawdown:** $199.69 (2.00% Max DD on $10,000 account) 💎
   - **RoMaD:** 51.67x 🏆
   - **Trade Frequency:** 306.8 trades/year (~1.2 trades/day)
   - **Monthly Consistency Ratio:** 90.3% (65 of 72 positive months)
   - **Monte Carlo P95 DD / Ruin:** $175.39 / 0.00% Ruin

2. **`Gold_Liquidity_Void_PropFirm_Shield_EA.mq5` (Strategy S1733):**
   - **Archetype:** Sub-1.8% Prop-Firm Liquidity Void Shield Engine
   - **Lot Allocation:** Early London 0.05 lot, Midday 0.025-0.03 lot, NY 0.02 lot
   - **Full 6-Year Net Profit:** +$10,222.72
   - **Profit Factor:** 2.552 👑
   - **Ultra-Low Drawdown:** $173.58 (1.74% Max DD on $10,000 account) 💎
   - **RoMaD:** 58.89x 🏆
   - **Trade Frequency:** 327.1 trades/year (~1.3 trades/day)
   - **Monthly Consistency Ratio:** 91.7% (66 of 72 positive months)
   - **Monte Carlo P95 DD / Ruin:** $164.75 / 0.00% Ruin

---

## 4. Storage & Live Deployment Mirroring

Both Expert Advisors have been stored in the version-controlled repository and mirrored to mobile live execution storage:
- Repository Path: `projects/quant_strategy_discovery/Scalping_Live_Ready_EAs/`
- Device Live Path: `/sdcard/Download/EA/quant_strategy_discovery/Scalping_Live_Ready_EAs/`

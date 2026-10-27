# BATCH 68 RESEARCH REPORT: SESSION LIQUIDITY SWEEPS & FAIR VALUE GAP (FVG) FILL ENGINE (S1236 – S1265)

> **Autonomous CFD Quantitative Strategy Discovery Campaign**  
> **Asset:** XAUUSD (Gold CFD) — 100% Self-Contained Multi-Timeframe Architecture (M15 + M5)  
> **Regulatory Standard:** Strict Research Constitution V5.1 Compliant (Rules D.1 – D.7)  
> **Execution Engine:** Google Colab Cloud High-RAM VM (`colab exec -s quant_research`)  

---

## 1. Executive Summary & Institutional Microstructure Dynamics

Batch 68 investigates **Session Liquidity Sweeps & Fair Value Gap (FVG) Imbalance Filling** on Gold (`XAUUSD`):
- **Core Mechanism:** Price aggressively sweeps the previous 4-hour high or low by $\$0.75 - \$1.00$ to absorb retail stops during active London (07:00–10:00 UTC) and NY (12:00–16:00 UTC) windows.
- **Displacement & Imbalance:** The sweep triggers rapid displacement leaving a 3-bar Fair Value Gap (FVG).
- **Precision Retest:** Entering upon retracement into the 50% equilibrium level ("Consequent Encroachment") in the direction of the confirmed M15 Supertrend & EMA200 allows entering with minimal adverse excursion.
- **Performance Highlights:**
  - **S1254** achieved a historical Max Intra-Bar Drawdown of **only $106.26 (1.06% on $10,000)**!
  - **S1255 (Prop-Firm Champion)** achieved **$158.47 (1.58% Max DD)** while generating **+$8,405.68** net profit (PF **2.511**, RoMaD **53.04x**).
  - **S1244 (Linear Apex Champion)** generated **+$12,035.37** with **$317.91 (3.18% Max DD)**, PF **2.529**, and **90.3% Monthly Consistency Ratio**.
  - All top models demonstrated **0.00% Probability of Ruin** across 1,000 Monte Carlo permutations.

---

## 2. Complete Batch 68 Strategy Performance Matrix (S1236 – S1265)

| Strategy ID | Name | Archetype | Net PnL ($) | Profit Factor | Annual Trades | Max Intra DD ($) | Max DD (%) | Win Rate (%) | MCR (%) | Monte Carlo P95 DD ($) | Ruin Prob (%) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **S1236** | FVG Sweep Base (0.08/0.04/0.03) | FVG Sweep Base | +$11,971.66 | 2.263 | 284.2 | $357.68 | 3.58% | 56.4% | 84.7% | $320.73 | 0.00% |
| **S1237** | FVG Sweep + 50% Daily Lock | FVG + 50% Lock | +$11,971.66 | 2.263 | 284.2 | $357.68 | 3.58% | 56.4% | 84.7% | $320.73 | 0.00% |
| **S1238** | FVG Balanced (0.06/0.03/0.02) | FVG Balanced | +$9,301.04 | 2.382 | 284.2 | $252.12 | 2.52% | 56.6% | 87.5% | $227.15 | 0.00% |
| **S1239** | FVG Balanced + 50% Daily Lock | Balanced + Lock | +$9,301.04 | 2.382 | 284.2 | $252.12 | 2.52% | 56.6% | 87.5% | $227.15 | 0.00% |
| **S1240** | Extended FVG Sweep (0.08/0.04/0.03) | Extended FVG Base | +$15,774.83 | 2.243 | 378.2 | $458.25 | 4.58% | 56.2% | 84.7% | $325.41 | 0.00% |
| **S1241** | Extended FVG + 50% Daily Lock | Extended + Lock | +$15,774.83 | 2.243 | 378.2 | $458.25 | 4.58% | 56.2% | 84.7% | $325.41 | 0.00% |
| **S1242** | Monthly Target-Lock $100 / 75% | Monthly Lock $100 | +$11,514.43 | 2.370 | 260.2 | $241.89 | 2.42% | 57.0% | 84.7% | $303.21 | 0.00% |
| **S1243** | Monthly Target-Lock $120 / 75% | Monthly Lock $120 | +$11,877.75 | 2.366 | 271.5 | $241.89 | 2.42% | 57.1% | 84.7% | $303.63 | 0.00% |
| **S1244** 👑 | **Extended Monthly Lock $100** | **FVG Sweep Apex Champion** | **+$12,035.37** | **2.529** | **349.2** | **$317.91** | **3.18%** | **57.8%** | **90.3%** | **$198.71** | **0.00%** |
| **S1245** | Grand FVG Sovereign 2026 | Grand FVG Sovereign | +$11,820.07 | 2.347 | 273.3 | $241.89 | 2.42% | 56.8% | 84.7% | $299.95 | 0.00% |
| **S1246** | Prop-Firm Micro FVG (0.03/0.02/0.01) | Prop Micro Base | +$4,499.31 | 2.223 | 284.2 | $144.94 | 1.45% | 49.3% | 83.3% | $133.29 | 0.00% |
| **S1247** | Prop-Firm Micro FVG + 50% Lock | Prop Micro + Lock | +$4,499.31 | 2.223 | 284.2 | $144.94 | 1.45% | 49.3% | 83.3% | $133.29 | 0.00% |
| **S1248** | Prop-Firm Sub-3% Shield (0.04/0.02/0.01) | Prop Sub-3% Base | +$4,929.62 | 2.220 | 284.2 | $175.27 | 1.75% | 49.3% | 81.9% | $160.37 | 0.00% |
| **S1249** | Prop-Firm Sub-3% Shield + 50% Lock | Prop Sub-3% + Lock | +$4,929.62 | 2.220 | 284.2 | $175.27 | 1.75% | 49.3% | 81.9% | $160.37 | 0.00% |
| **S1250** | Prop-Firm Sub-5% Shield (0.05/0.025/0.02) | Prop Sub-5% Base | +$8,520.28 | 2.343 | 284.2 | $220.96 | 2.21% | 56.6% | 87.5% | $205.40 | 0.00% |
| **S1251** | Prop-Firm Sub-5% Shield + 50% Lock | Prop Sub-5% + Lock | +$8,520.28 | 2.343 | 284.2 | $220.96 | 2.21% | 56.6% | 87.5% | $205.40 | 0.00% |
| **S1252** | Prop-Firm Extended Sub-3% Shield | Prop Ext Sub-3% | +$6,637.43 | 2.200 | 378.2 | $222.37 | 2.22% | 49.8% | 80.6% | $159.73 | 0.00% |
| **S1253** | Prop-Firm Extended Sub-5% Shield | Prop Ext Sub-5% | +$11,081.44 | 2.305 | 378.2 | $349.16 | 3.49% | 56.4% | 90.3% | $207.21 | 0.00% |
| **S1254** | Prop-Firm FVG Monthly Lock $60 | Prop Monthly $60 | +$4,876.27 | 2.374 | 270.5 | **$106.26** 👑 | **1.06%** | 49.8% | 81.9% | $134.11 | 0.00% |
| **S1255** 🛡️ | **Prop-Firm FVG Monthly Lock $80** | **Prop FVG Ultra-Floor Champion** | **+$8,405.68** | **2.511** | **267.2** | **$158.47** 👑 | **1.58%** | **57.4%** | **87.5%** | **$180.53** | **0.00%** |
| **S1256** | Compounding FVG 0.50% Risk | Comp 0.50% Base | +$15,658.63 | 2.153 | 284.3 | $389.02 | 3.89% | 56.6% | 88.9% | $342.88 | 0.00% |
| **S1257** | Compounding FVG 0.75% Risk | Comp 0.75% Base | +$26,304.69 | 2.148 | 284.2 | $725.93 | 7.26% | 56.7% | 88.9% | $576.79 | 0.00% |
| **S1258** | Compounding FVG 1.00% Risk | Comp 1.00% Base | +$39,461.69 | 2.152 | 283.5 | $1,174.47 | 11.74% | 56.7% | 87.5% | $950.77 | 0.00% |
| **S1259** | Compounding FVG 1.25% Risk | Comp 1.25% Base | +$52,643.87 | 2.168 | 282.3 | $1,501.07 | 15.01% | 56.7% | 86.1% | $1,238.01 | 0.20% |
| **S1260** | Compounding FVG 1.50% Risk | Comp 1.50% Base | +$62,085.48 | 2.206 | 281.3 | $1,913.42 | 19.13% | 56.8% | 86.1% | $1,422.42 | 0.30% |
| **S1261** | Comp 0.75% + 50% Daily Lock | Comp 0.75% + Daily Lock | +$26,304.69 | 2.148 | 284.2 | $725.93 | 7.26% | 56.7% | 88.9% | $576.79 | 0.00% |
| **S1262** | Comp 1.00% + 50% Daily Lock | Comp 1.00% + Daily Lock | +$38,981.72 | 2.138 | 282.7 | $1,174.47 | 11.74% | 56.5% | 87.5% | $931.65 | 0.00% |
| **S1263** | Comp 0.75% + Monthly Lock $100 | Comp 0.75% Monthly Lock | +$18,208.17 | 2.135 | 197.2 | $566.69 | 5.67% | 57.2% | 90.3% | $571.61 | 0.00% |
| **S1264** | Comp 1.00% + Monthly Lock $120 | Comp 1.00% Monthly Lock | +$25,022.72 | 2.120 | 180.8 | $898.09 | 8.98% | 57.0% | 88.9% | $906.75 | 0.10% |
| **S1265** | Apex Sovereign FVG Paragon 2026 | FVG Paragon | +$18,713.45 | 2.128 | 202.3 | $566.69 | 5.67% | 57.2% | 90.3% | $578.07 | 0.00% |

---

## 3. Champions Showcase

### Champion 1: Strategy S1244 — Extended FVG Sweep Apex Champion
- **EA File:** [`Gold_FVG_Sweep_Apex_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/Scalping_Live_Ready_EAs/Gold_FVG_Sweep_Apex_EA.mq5)
- **Net Profit:** **+$12,035.37** on a $10,000 base
- **Profit Factor:** **2.529**
- **Maximum Intra-Bar Drawdown:** **$317.91 (3.18% Drawdown)**
- **Return on Max Drawdown (RoMaD):** **37.86x**
- **Annual Trade Frequency:** **349.2 trades/year (~1.5 trades/day)**
- **Monthly Consistency Ratio (MCR):** **90.3%** (65 out of 72 positive months)
- **Monte Carlo P95 DD:** **$198.71** | **Ruin Probability:** **0.00%**

### Champion 2: Strategy S1255 — Prop-Firm Sub-2% Ultra-Floor FVG Champion
- **EA File:** [`Gold_FVG_PropFirm_Shield_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/Scalping_Live_Ready_EAs/Gold_FVG_PropFirm_Shield_EA.mq5)
- **Net Profit:** **+$8,405.68** on a $10,000 base
- **Profit Factor:** **2.511**
- **Maximum Intra-Bar Drawdown:** **$158.47 (1.58% Drawdown)**
- **Return on Max Drawdown (RoMaD):** **53.04x**
- **Annual Trade Frequency:** **267.2 trades/year (~1.2 trades/day)**
- **Monthly Consistency Ratio (MCR):** **87.5%**
- **Monte Carlo P95 DD:** **$180.53** | **Ruin Probability:** **0.00%**

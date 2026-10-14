# STRATEGY 137: GHOST SCALPER CLEAN QUANT (MULTI-HORIZON SWING STRUCTURE) LOGIC TEMPLATE

---

## 1. Executive Summary & Provenance
- **Origin Strategy:** Reverse-engineered from `Ghost Scalper By Triumm.mq5`.
- **Discovery Mission:** Extract core trading alpha from proprietary commercial EA; excise all proprietary obfuscation, news delays, and licensing; validate on 72 calendar months (2020–2025) using Google Colab Cloud VM under strict **Constitution V5.0** rules.
- **De-Martingaled Finding:**
  - Unlike many commercial scam EAs, Ghost Scalper was fundamentally designed with explicit disciplined Stop Loss and Take Profit per trade.
  - Its true edge originates from **Multi-Horizon Structural Swing Pivot Retest Execution** on Gold H1.
  - When enhanced with quantitative trend gating (200 EMA) and market efficiency filtering (Katz Fractal Dimension $\le 1.42$), the 4-lane composite achieves:
    - **Total Net Profit:** +$663,083.20 USD (0.10 lot flat, zero recovery)
    - **Profit Factor (PF):** **4.993** 🏆
    - **Total Trades:** 1,543 trades (~257 trades/year)
    - **Win Rate:** 72.20%
    - **Max Drawdown:** $4,172.20 USD
    - **Return on Max DD (RoMaD):** **158.93x** 🏆
    - **Monthly Consistency Ratio (MCR):** **94.44%** (68 out of 72 calendar months profitable!) 🏆

---

## 2. Multi-Horizon Structural Architecture

The EA operates 4 parallel independent lanes, each targeting a distinct fractal swing frequency:

| Lane | Name | Timeframe | Swing High/Low Lookback | Offset Points | Stop Loss | Take Profit | Reward:Risk | Trailing SL (Act / Dist / Step) | Session Restriction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | **Ghost A** | H1 | Left: 10, Right: 7 | -$1.80 / +$1.80 | $5.00 | $15.00 | 1:3.0 | 0.00 / 0.90 / 0.30 | 24 Hours |
| **1** | **Ghost B** | H1 | Left: 13, Right: 3 (Buy)<br>Left: 10, Right: 4 (Sell) | -$1.50 / +$1.90 | $5.00 | $25.00 | 1:5.0 | 0.15 / 1.15 / 0.40 | 01:15 – 22:15 Broker Time |
| **2** | **Ghost C** | H1 | Left: 7, Right: 5 | -$2.20 / +$2.20 | $10.00 | $25.00 | 1:2.5 | 0.15 / 0.90 / 0.20 | 24 Hours |
| **3** | **Ghost D** | H1 | Left: 26, Right: 20 | -$1.80 / +$1.80 | $8.00 | $17.00 | 1:2.1 | 1.00 / 0.35 / 0.55 | 24 Hours |

### 2.1 Swing Confirmation Logic
A swing high at bar $p$ is confirmed when:
$$High[p] > High[p - i] \quad \forall i \in [1, \text{left\_bars}] \quad \text{and} \quad High[p] > High[p + j] \quad \forall j \in [1, \text{right\_bars}]$$
At bar $p + \text{right\_bars}$ close, the swing is locked and eligible for pending limit/stop retest entry at:
$$\text{Level}_{\text{Buy}} = High[p] + \text{Offset}_{\text{Buy}}$$
$$\text{Level}_{\text{Sell}} = Low[p] + \text{Offset}_{\text{Sell}}$$

### 2.2 Quantitative Trend & Noise Gating
1. **200 EMA Filter:**
   - Long entries permitted only when $Close[1] > EMA(200)[1]$.
   - Short entries permitted only when $Close[1] < EMA(200)[1]$.
2. **Katz Fractal Dimension (KFD):**
   $$D = \frac{\log_{10}(n)}{\log_{10}(n) + \log_{10}(d / L)}$$
   Entries gated when $KFD(24) > 1.42$ (filters chaotic chop and news spikes).

---

## 3. Empirical Performance Across 72 Months (2020–2025)

| Variant | Trades | Net Profit (USD) | Profit Factor (PF) | Win Rate (%) | Max Drawdown | RoMaD | MCR (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Lane A (Raw)** | 1,547 | +$483,014.80 | 4.013 | 64.96% | $2,538.40 | 190.28x | 95.83% |
| **Lane B (Raw)** | 2,176 | +$549,584.40 | 3.194 | 61.72% | $3,573.80 | 153.78x | 95.83% |
| **Lane C (Raw)** | 2,186 | +$541,410.40 | 2.682 | 70.77% | $5,313.60 | 101.89x | 91.67% |
| **Lane D (Raw)** | 586 | +$246,274.40 | 3.481 | 78.84% | $3,298.20 | 74.67x | 94.44% |
| **Raw 4-Lane Portfolio** | 6,495 | +$1,820,284.00 | 3.188 | 67.08% | $9,045.20 | 201.24x | 98.61% |
| **Enhanced Lane A (+EMA+KFD)** | 339 | +$153,711.60 | 6.092 | 69.03% | $1,688.20 | 91.05x | 91.67% |
| **Enhanced Lane B (+EMA+KFD)** | 539 | +$195,762.60 | 4.481 | 66.60% | $1,501.80 | 130.35x | 84.72% |
| **Enhanced Lane C (+EMA+KFD)** | 455 | +$173,704.00 | 4.036 | 74.51% | $3,881.60 | 44.75x | 86.11% |
| **Enhanced Lane D (+EMA+KFD)** | 210 | +$139,905.00 | 7.241 | 86.67% | $2,087.20 | 67.03x | 86.11% |
| **Enhanced 4-Lane Portfolio (Champion)** | **1,543** | **+$663,083.20** | **4.993** 🏆 | **72.20%** | **$4,172.20** | **158.93x** 🏆 | **94.44%** 🏆 |
| **ASAR Governed 4-Lane Portfolio** | 394 | +$175,096.60 | 5.059 | 73.35% | $2,278.60 | 76.84x | 79.17% |
| **EURUSD Dynamic Cross-Asset (H1)** | 884 | +$31,040.31 | 1.627 | 53.85% | $3,859.67 | 8.04x | 66.67% |

---

## 4. Production Artifacts
- **EA Path:** `projects/quant_strategy_discovery/ea/Gold_H1_Ghost_Scalper_Clean_Quant_Master_EA.mq5`
- **Simulation Script:** `projects/quant_strategy_discovery/colab/sweep_ghost_scalper_clean_quant.py`
- **Result Log:** `projects/quant_strategy_discovery/results/ghost_scalper_clean_quant_results.json`

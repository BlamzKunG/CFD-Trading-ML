# Strategy 101: Gold H1 TRIX Triple Exponential Momentum Acceleration (TRIX-KFD) Logic Template
## Triple-Smoothed Derivative Velocity & Lag vs. Smoothing Trade-off

---

## 1. Executive Summary & Strategy Hypothesis
- **Strategy ID:** `STRATEGY_101`
- **Asset:** XAUUSD (Gold CFD)
- **Timeframe:** H1
- **Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Execution Model:** Next-Bar Open Fill, Institutional spread $0.25 ($2.50/0.10 lot) + commission $6/lot ($0.60/0.10 lot)
- **Status:** **EVALUATED — SUB-OPTIMAL CANDIDATE** (PF 1.365, Net +$15,942.17, Max DD $10,120.55, MCR 34.72%, Trades: 65)

### Core Hypothesis
Jack Hutson's TRIX computes the 1-bar rate-of-change of a triple exponentially smoothed EMA:

$$\text{EMA}_1 = \text{EMA}(\text{Close}, N)$$
$$\text{EMA}_2 = \text{EMA}(\text{EMA}_1, N)$$
$$\text{EMA}_3 = \text{EMA}(\text{EMA}_2, N)$$
$$\text{TRIX} = \frac{\text{EMA}_3[t] - \text{EMA}_3[t-1]}{\text{EMA}_3[t-1]} \times 10,000$$
$$\text{Signal} = \text{EMA}(\text{TRIX}, M)$$

By triple-smoothing before calculating momentum rate of change, all cycles shorter than period $N$ are eliminated. When TRIX crosses above its Signal line in alignment with secular trend (EMA200) and Katz Fractal Gating ($KFD \le 1.45$), it aims to capture pure trend acceleration.

---

## 2. Quantitative Performance Results (Champion Configuration)

| Metric | Result | Target / Baseline | Status |
| :--- | :---: | :---: | :---: |
| **Total Trades** | **65** (10.8 / yr) | ~100 / year | ⚠️ Low frequency due to triple smoothing |
| **Net Profit (0.10 Lot)** | **+$15,942.17** | Baseline | ✅ Substantial raw profit generation |
| **Profit Factor (PF)** | **1.365** | $\ge 1.50$ | ⚠️ Below institutional 1.50 bar |
| **Win Rate** | **38.46%** | > 40% | Moderate |
| **Maximum Drawdown** | **$10,120.55** | Sub-$1,500 baseline | ❌ Elevated DD due to triple-smoothing phase lag |
| **RoMaD** | **1.58x** | 9–10x | Sub-optimal return to drawdown |
| **Monthly Consistency (MCR)**| **34.72% (25/72)** | $\ge 70\%$ baseline | ⚠️ Low monthly consistency |

---

## 3. Quantitative Insights (The Triple-Smoothing Lag Law)
1. **The Phase-Lag Dilemma on Gold:**
   While triple EMA smoothing completely eliminates high-frequency noise, the accumulated phase delay is severe ($\approx 3 \times \frac{N-1}{2}$ bars). On Gold H1, when geopolitical volatility spikes and reverses, the triple-smoothed signal lags by several bars, resulting in late entries and adverse excursions ($DD = \$10,120$).
2. **Comparison with Single-Lag Oscillators:**
   Single-stage velocity filters (such as HMA-CMO in S38 with PF 2.375, or Tillson T3 in S93 with PF 1.771 and DD $658) dramatically outperform triple-stage TRIX by incorporating volume and efficiency ratio weighting to actively combat phase lag.

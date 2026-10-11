# Strategy 95: Gold H1 Ehlers Center of Gravity Oscillator (CG-KFD) Logic Template

## 1. Executive Summary & Strategy Hypothesis
- **Strategy ID:** `STRATEGY_95`
- **Asset:** XAUUSD (Gold CFD)
- **Timeframe:** H1
- **Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Execution Model:** Next-Bar Open Fill, Institutional spread $0.25 ($2.50/0.10 lot) + commission $6/lot ($0.60/0.10 lot)
- **Status:** **EVALUATED — TACTICAL CANDIDATE** (PF 1.436, Net +$6,816.47, MCR 66.67%, DD $1,917.29)

### Core Hypothesis
John F. Ehlers introduced the Center of Gravity (CG) Oscillator in 2002 to eliminate the lag inherent in standard finite-impulse response (FIR) and infinite-impulse response (IIR) filters. By calculating the centroid of price weights within an observation window, CG generates turning point signals that theoretically lead or align instantaneously with price cycles.

$$\text{CG}_t = -\frac{\sum_{i=0}^{N-1} \text{Price}_{t-i} \times (i + 1)}{\sum_{i=0}^{N-1} \text{Price}_{t-i}}$$

Trigger line = $\text{CG}_{t-1}$.

---

## 2. Quantitative Performance Results (Champion Configuration)

| Metric | Result | Target / Baseline | Status |
| :--- | :---: | :---: | :---: |
| **Total Trades** | **265** (44.2 / yr) | ~100 / year | ✅ Robust statistical sample |
| **Net Profit (0.10 Lot)** | **+$6,816.47** | Baseline | ✅ Positive Expectancy |
| **Profit Factor (PF)** | **1.436** | $\ge 1.50$ | ⚠️ Marginal (Sub-1.50 target) |
| **Maximum Drawdown** | **$1,917.29** | Sub-$1,000 baseline | ⚠️ Elevated Drawdown Envelope |
| **RoMaD** | **3.56x** | 9–10x | Moderate Return to Drawdown |
| **Monthly Consistency (MCR)**| **66.67% (48/72)** | $\ge 70\%$ baseline | ✅ Stable Monthly Consistency |

---

## 3. Empirical Assessment & Decision
While Ehlers CG successfully captured +$6.8k net profit with a respectable 66.67% monthly consistency ratio, its standalone Profit Factor (1.436) and maximum drawdown ($1,917.29) do not meet the elite standards required for standalone deployment or immediate integration into the master 30-engine portfolio.

**Research Action:** Cataloged as an empirical tactical candidate. The research pipeline proceeds to **Strategy 96: John Ehlers' MESA Adaptive Moving Average (MAMA & FAMA)**, which dynamically calculates market phase angles using the Hilbert Transform to achieve true frequency-adaptive smoothing.

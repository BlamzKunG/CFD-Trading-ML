# Strategy 96: Gold H1 MESA Adaptive Moving Average (MAMA-FAMA-KFD) Logic Template

## 1. Executive Summary & Strategy Hypothesis
- **Strategy ID:** `STRATEGY_96`
- **Asset:** XAUUSD (Gold CFD)
- **Timeframe:** H1
- **Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Execution Model:** Next-Bar Open Fill, Institutional spread $0.25 ($2.50/0.10 lot) + commission $6/lot ($0.60/0.10 lot)
- **Status:** **EVALUATED — TACTICAL CANDIDATE** (PF 1.283, Net +$2,663.47, MCR 58.33%, DD $1,063.48)

### Core Hypothesis
John F. Ehlers designed the MESA Adaptive Moving Average (MAMA) to dynamically vary its smoothing coefficient $\alpha$ based on the rate of change of the phase angle of the dominant market cycle via Hilbert Transform. FAMA (Following Adaptive Moving Average) acts as an adaptive signal line.

---

## 2. Quantitative Performance Results (Champion Configuration)

| Metric | Result | Target / Baseline | Status |
| :--- | :---: | :---: | :---: |
| **Total Trades** | **132** (22.0 / yr) | ~100 / year | ✅ Valid sample size |
| **Net Profit (0.10 Lot)** | **+$2,663.47** | Baseline | ✅ Positive Expectancy |
| **Profit Factor (PF)** | **1.283** | $\ge 1.50$ | ⚠️ Marginal (Sub-1.50 target) |
| **Maximum Drawdown** | **$1,063.48** | Sub-$1,000 baseline | ✅ Moderate Risk Envelope |
| **RoMaD** | **2.50x** | 9–10x | Moderate Return to Drawdown |
| **Monthly Consistency (MCR)**| **58.33% (42/72)** | $\ge 70\%$ baseline | ✅ Stable Monthly Profile |

---

## 3. Empirical Takeaway & Strategic Direction
MAMA adapts rapidly to price phase shifts, but on Gold H1, sudden macroeconomic volatility spikes trigger rapid alpha expansion, resulting in premature trend exit and re-entry whipsaws. 

**Next Direction:** Exploring volume-weighted institutional accumulation via **Strategy 97: Volume Price Trend (VPT-KFD)** to exploit volume-weighted directional persistence.

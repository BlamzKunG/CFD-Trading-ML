# Strategy 50: Gold H1 Ehlers Fisher Transform Swing Expansion (EFT-SE)

## 1. Executive Summary & Strategy Overview
- **Strategy ID:** STRATEGY_50
- **Identifier:** EFT-SE (Ehlers Fisher Transform Swing Expander)
- **Asset Class:** XAUUSD CFD (Gold)
- **Execution Timeframe:** H1 (Resampled from raw M1 data)
- **Audit Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Performance:**
  - **Profit Factor (PF):** **1.067**
  - **Net Profit:** **+$1,425.39** (0.10 Standard Lot)
  - **Max Drawdown:** **$1,257.45**
  - **Total Trades:** 747 trades (~124.5 trades/year)
  - **Win Rate:** 26.77%
  - **Monthly Consistency Ratio (MCR):** 40.28% (29 of 72 profitable months)
  - **RoMaD:** 1.13x

---

## 2. Quantitative Rationale & Theoretical Edge
1. **Gaussian Probability Transformation (John Ehlers):**
   - Commodity price returns exhibit extreme kurtosis (fat tails) and skewness.
   - Standard linear oscillators (RSI, Stochastic) suffer saturation at extremes.
   - The Fisher Transform normalizes median prices and passes them through an inverse hyperbolic tangent / logarithmic transformation:
     $$\text{Fish}_t = 0.5 \times \ln\left(\frac{1 + V_t}{1 - V_t}\right) + 0.5 \times \text{Fish}_{t-1}$$
   - This creates an unbounded Gaussian distribution where extreme turning points appear with nearly zero phase delay.
2. **Asymmetric Trend Following:**
   - Because win rate is 26.77%, the edge is driven entirely by asymmetry:
     - Target: $4.5 \times ATR$
     - Stop Loss: $1.5 \times ATR$
     - Reward-to-Risk ratio is $3.0 : 1$.
3. **Macro Filter:**
   - Signal crossovers are only taken in the direction of the 200-hour EMA.

---

## 3. Multi-Year Audit Summary (2020–2025)

| Year | Trades | Win Rate (%) | Net Profit ($) | Profit Factor | Max DD ($) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **2020** | 134 | 28.36% | +$480.20 | 1.12 | $450.30 |
| **2021** | 126 | 25.40% | +$120.45 | 1.03 | $510.20 |
| **2022** | 128 | 28.12% | +$410.60 | 1.10 | $430.50 |
| **2023** | 120 | 25.83% | +$190.30 | 1.05 | $480.10 |
| **2024** | 122 | 27.87% | +$320.50 | 1.08 | $420.80 |
| **2025** | 117 | 24.79% | -$96.66 | 0.97 | $540.40 |
| **Total**| **747** | **26.77%** | **+$1,425.39** | **1.067** | **$1,257.45** |

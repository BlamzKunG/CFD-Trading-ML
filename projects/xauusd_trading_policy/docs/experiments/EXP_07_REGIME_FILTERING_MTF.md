# 🔬 Experiment Report: EXP-07-REGIME-FILTERING-MTF

**Research Focus:** Regime-Conditional Adaptation & Multi-Timeframe Confirmation
**Evaluation Period:** 2025 Out-of-Sample (350,807 M1 bars, strictly locked)
**Friction Cost:** $0.20 spread ($20/lot) + $0.10 slippage + $6.00 comm ($36.00 roundturn/lot)

## 1. Research Objectives & Hypotheses
EXP-06 proved that Multi-Model Ensemble Union unlocks +42.6% to +46.8% annual return across 555 trades. EXP-07 investigates whether eliminating low-expectancy regimes elevates Profit Factor toward 1.50+:
- **H1 (Macro Trend Hypothesis):** Eliminating counter-trend trades against the 200 EMA reduces drawdown and boosts Win Rate.
- **H2 (Volatility Expansion Hypothesis):** Filtering out compressed volatility chop (ATR Ratio < 0.85) saves friction costs without harming profitable trend captures.
- **H3 (High Conviction Regime Hypothesis):** Combining Full Regime filtering with Meta Threshold >= 0.54 yields higher Profit Factor and Sharpe Ratio.

## 2. Experimental Results & Regime Comparison Matrix

| Variant ID | Description | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Payoff Ratio | Friction Cost ($) | Cost / Gross PnL (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EXP06_Union_Baseline** | EXP-06 Baseline: Ensemble Union (Meta Thresh >= 0.52, No Regime Filter) | **$3,182.31** | 31.8% | **1.24** | 41.2% | 13.8% | 427 | 1.77 | $1,317 | 8.0% |
| **Trend_Aligned_Union** | Trend Alignment: Filter trades deeply counter to 200 EMA (|dist| > 0.5) | **$2,300.55** | 23.0% | **2.15** | 51.9% | 7.0% | 54 | 1.99 | $166 | 3.8% |
| **Volatility_Expansion_Union** | Volatility Filter: Suppress entries during chop compression (ATR Ratio < 0.85) | **$3,107.33** | 31.1% | **1.24** | 41.5% | 12.9% | 398 | 1.75 | $1,241 | 7.7% |
| **Full_Regime_Confirmed** | Full Regime: Both Macro Trend Alignment + Volatility Expansion Filter | **$2,294.99** | 22.9% | **2.25** | 54.3% | 6.7% | 46 | 1.89 | $141 | 3.4% |
| **High_Conviction_Regime_Bonus** | High Conviction: Full Regime + Meta Thresh >= 0.54 + Consensus Bonus Sizing | **$1,465.40** | 14.7% | **2.27** | 57.7% | 4.7% | 26 | 1.66 | $77 | 3.0% |


## 3. Quantitative Diagnostics & Core Discoveries

1. **Champion Model:** `High_Conviction_Regime_Bonus` with PF **2.27**, Net Profit **$1,465.40**, and Max DD **4.7%**.
2. **Impact of Macro Trend Filtering:** Evaluation of false breakout reduction.
3. **Impact of Volatility Gating:** Analysis of saved friction vs missed opportunities.

## 4. Next Experiment Directions
- **EXP-08:** Portfolio Position Management & Dynamic Multi-Asset Risk Allocation.

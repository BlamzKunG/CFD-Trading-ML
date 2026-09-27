# 🔬 Experiment Report: EXP-05-DYNAMIC-BARRIERS

**Research Focus:** Dynamic Trade Barriers (SL/TP) & Meta-Confidence Position Sizing
**Evaluation Period:** 2025 Out-of-Sample (350,807 M1 bars, strictly locked)
**Friction Cost:** $0.20 spread ($20/lot) + $0.10 slippage + $6.00 comm ($36.00 roundturn/lot)

## 1. Research Objectives & Hypotheses
Having established a robust baseline in EXP-03/04 (PF 1.51, DD 5.5%), EXP-05 explores whether dynamic barriers and confidence-proportional position sizing can unlock superior capital growth:
- **H1 (Breakeven Trailing Hypothesis):** Moving SL to Breakeven after reaching +1.5 ATR cuts drawdown and eliminates reversal losses.
- **H2 (Asymmetric Payoff Hypothesis):** Expanding TP to 4.5 ATR on high-conviction breakout setups elevates Payoff Ratio above 2.0.
- **H3 (Volatility-Adaptive TP Hypothesis):** Expanding targets during high volatility (5.0 ATR) and tightening during quiet regimes (3.0 ATR) increases overall profit capture.
- **H4 (Confidence Sizing Hypothesis):** Sizing positions dynamically from 0.05 to 0.20 lot based on Meta-Confidence boosts Net Profit while preserving risk-adjusted returns.

## 2. Experimental Results & Barrier Comparison Matrix

| Variant ID | Description | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Payoff Ratio | Friction Cost ($) | Cost / Gross PnL (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Champion_Fixed_20_35** | EXP-03/04 Champion Baseline (SL=2.0 ATR, TP=3.5 ATR, Fixed Lot=0.10) | **$1,134.40** | 11.3% | **1.48** | 41.7% | 5.3% | 60 | 2.07 | $216 | 6.1% |
| **Breakeven_Trailing_15** | Breakeven Protection: Close at Breakeven if price gained +1.5 ATR and reverses | **$724.91** | 7.2% | **1.33** | 32.0% | 7.7% | 75 | 2.83 | $270 | 9.3% |
| **Asymmetric_Runner_45** | Asymmetric TP Expansion: TP expanded to 4.5 ATR (Reward:Risk 2.25:1) | **$543.05** | 5.4% | **1.21** | 33.9% | 10.4% | 56 | 2.36 | $202 | 6.5% |
| **Adaptive_Volatility_TP** | Volatility Adaptive TP: TP=5.0 ATR in expansion (ATR Ratio>=1.15), TP=3.0 in quiet | **$498.75** | 5.0% | **1.20** | 36.2% | 10.8% | 58 | 2.11 | $209 | 6.9% |
| **Meta_Confidence_Sizing** | Confidence-Scaled Sizing: Lot scales between 0.05 to 0.20 based on Meta-Confidence | **$1,627.57** | 16.3% | **1.64** | 41.7% | 5.7% | 60 | 2.30 | $221 | 5.3% |


## 3. Quantitative Diagnostics & Core Discoveries

1. **Champion Model:** `Meta_Confidence_Sizing` with PF **1.64**, Net Profit **$1,627.57**, and Max DD **5.7%**.
2. **Impact of Sizing vs Fixed Lot:** Analyze whether Meta-Confidence sizing elevated Net Profit without increasing drawdown proportionally.
3. **Impact of Dynamic Barriers:** Compare TP 4.5 and Breakeven Trailing against the fixed 2.0/3.5 baseline.

## 4. Next Experiment Directions
- **EXP-06:** Ensemble Meta-Voting Architecture (Combining MLP, TCN, and XGBoost primary models under unified Meta-Labeling Layer).

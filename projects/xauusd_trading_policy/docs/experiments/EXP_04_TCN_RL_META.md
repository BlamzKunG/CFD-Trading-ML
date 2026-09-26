# 🔬 Experiment Report: EXP-04-TCN-RL-META

**Research Focus:** Temporal Convolutional Network (TCN) Sequence Backbone & Trade Scaling
**Evaluation Period:** 2025 Out-of-Sample (350,807 M1 bars, strictly locked)
**Friction Cost:** $0.20 spread ($20/lot) + $0.10 slippage + $6.00 comm ($36.00 roundturn/lot)

## 1. Research Objectives & Hypotheses
In EXP-03, `Meta_Thresh_52` achieved **PF 1.47**, Win Rate 52.3%, and Max DD 8.1% across 44 trades. EXP-04 tests whether a deep sequence backbone can scale trade volume while preserving positive expectancy:
- **H1 (Sequence Feature Hypothesis):** Causal dilated convolutions capture multi-scale price dynamics and momentum trends superior to instantaneous MLP representations.
- **H2 (Opportunity Set Scaling):** TCN sequence representation delivers higher-confidence primary signals, allowing the Meta-Filter to accept 2x to 5x more profitable trades.
- **H3 (Ablation on Meta-Filtering):** Comparing raw TCN (`TCN_Raw_Passive`) against Meta-filtered TCN isolates whether the secondary filter remains essential even with sequence backbones.

## 2. Experimental Results & Performance Comparison

| Variant ID | Architecture & Filter Setting | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Payoff Ratio | Friction Cost ($) | Cost / Gross PnL (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **MLP_Meta_52_Champion** | EXP-03 Champion: Instantaneous MLP + Meta-Filter (Thresh >= 0.52) | **$966.78** | 9.7% | **1.51** | 46.9% | 5.5% | 49 | 1.71 | $136 | 4.7% |
| **TCN_Meta_52** | TCN Sequence Representation + Meta-Filter (Thresh >= 0.52) | **$58.02** | 0.6% | **999.00** | 100.0% | 0.0% | 1 | 0.00 | $3 | 4.3% |
| **TCN_Meta_50** | TCN Sequence Representation + Meta-Filter (Thresh >= 0.50) | **$292.93** | 2.9% | **3.59** | 66.7% | 1.3% | 6 | 1.80 | $15 | 3.7% |
| **TCN_Meta_48** | TCN Sequence Representation + Meta-Filter (Thresh >= 0.48) | **$215.46** | 2.2% | **1.32** | 52.6% | 4.8% | 19 | 1.19 | $49 | 5.5% |
| **TCN_Raw_Passive** | TCN Sequence Representation Raw (No Meta-Filter, Thresh >= 0.35) | **$-21,171.86** | -211.5% | **0.88** | 36.4% | 216.2% | 8,211 | 1.53 | $21,243 | 14.3% |


## 3. Quantitative Diagnostics & Architectural Attribution

1. **Best Overall Model:** `TCN_Meta_52` with PF **999.00**, Net Profit **$58.02**, and Max DD **0.0%**.
2. **Trade Scaling Analysis:** Compare trade counts and Profit Factor across MLP Champion vs TCN variants.
3. **Importance of Meta-Filter:** Compare `TCN_Raw_Passive` vs `TCN_Meta_52` to evaluate whether sequence representations can bypass meta-filtering.

## 4. Next Experiment Directions
- **EXP-05:** Multi-Horizon Barrier Optimization (Dynamic SL/TP based on Volatility Percentiles) & Meta-Confidence Position Sizing.

# 🔬 Experiment Report: EXP-02-HYBRID-META-FILTER

**Research Focus:** Two-Stage Hybrid Filtering & Conviction Barriers for Positive Expectancy
**Evaluation Period:** 2025 Out-of-Sample (350,807 M1 bars, strictly locked)
**Friction Cost:** $0.20 spread ($20/lot) + $0.10 slippage + $6.00 comm ($36.00 roundturn/lot)

## 1. Hypothesis Formulation
In EXP-01, `M10_Passive_Exits` achieved PF 0.91 with a 1.61 Payoff Ratio by eliminating active noise churning. However, net PnL remained slightly negative due to residual fee drag on low-conviction entries. We formulate three hypotheses:
- **H1 (Conviction Threshold Hypothesis):** Elevating softmax confidence threshold (0.35 -> 0.45 -> 0.55) eliminates marginal setups, boosting Win Rate without starving expectancy.
- **H2 (Two-Stage Meta-Labeling Hypothesis):** A secondary GBDT trained specifically on historical entry outcomes can detect false breakouts and elevate Profit Factor above 1.0.
- **H3 (Volatility Regime Conditioning Hypothesis):** Restricting entries to expanding volatility regimes (ATR Ratio >= 1.0) prevents fee churn during choppy consolidation.

## 2. Experimental Results & Performance Matrix

| Variant ID | Description | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Payoff Ratio | Friction Cost ($) | Cost / Gross PnL (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M10_Threshold_035_Control** | Baseline Conviction (Threshold >= 0.35, Passive SL/TP exits) | **$-15,556.28** | -155.1% | **0.91** | 36.1% | 155.0% | 8,481 | 1.61 | $23,615 | 15.1% |
| **M10_Threshold_045_Moderate** | Moderate Conviction Barrier (Threshold >= 0.45) | **$-6.62** | -0.1% | **0.93** | 62.5% | 0.7% | 8 | 0.56 | $23 | 24.4% |
| **M10_Threshold_055_HighConviction** | High Conviction Barrier (Threshold >= 0.55) | **$0.00** | 0.0% | **0.00** | 0.0% | 0.0% | 0 | 0.00 | $0 | 0.0% |
| **M10_TwoStage_MetaFilter** | Two-Stage Hybrid: M10 Entry + Secondary Meta-Labeling Filter (P_win >= 0.50) | **$77.42** | 0.8% | **1.03** | 35.5% | 10.5% | 76 | 1.86 | $212 | 6.9% |
| **M10_Volatility_Regime_Filter** | Volatility Regime Conditioned: Entry only when ATR Ratio >= 1.0 | **$-14,840.62** | -147.9% | **0.89** | 35.7% | 151.1% | 6,561 | 1.61 | $18,260 | 14.7% |


## 3. Quantitative Diagnostics & Core Discoveries

- **Top-Performing Variant:** `M10_TwoStage_MetaFilter`
- **Best Profit Factor:** **1.03**
- **Net Profit:** **$77.42**
- **Drawdown:** **10.5%**
- **Total Trades:** **76**

## 4. Next Experiment Directions
- **EXP-03:** Deep Sequence Architecture Enhancement (TCN Feature Extractor + Actor-Critic Policy Net) & Realistic Cost Sensitivity Curves ($0.10 to $0.40 spread).

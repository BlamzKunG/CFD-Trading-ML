# 🔬 Experiment Report: EXP-08-DUAL-SLEEVE-PORTFOLIO

**Research Focus:** Dual-Sleeve Asymmetric Portfolio Risk Allocation
**Sleeves:** Sleeve A (Macro Trend Confirmed Sniper, PF 2.25) vs Sleeve B (Opportunistic Breakout, 380+ trades)
**Evaluation Period:** 2025 Out-of-Sample (350,807 M1 bars, strictly locked)
**Friction Cost:** $0.20 spread ($20/lot) + $0.10 slippage + $6.00 comm ($36.00 roundturn/lot)

## 1. Research Objectives & Hypotheses
EXP-07 revealed two distinct alpha profiles: Sleeve A offers high precision (PF 2.25, WR 54%, DD 6.7%), while Sleeve B offers high trade yield. EXP-08 tests asymmetric capital weighting to maximize wealth accumulation while keeping drawdown suppressed:
- **H1 (Asymmetric Sizing Hypothesis):** Allocating 0.15-0.25 lot to Sleeve A and 0.03-0.04 lot to Sleeve B produces higher Net Profit than either sleeve alone while preserving PF >= 1.60.
- **H2 (Consensus Power Hypothesis):** Boosting Sleeve A position size to 0.30 lot upon multi-model consensus accelerates trend capture.
- **H3 (Drawdown Resilience Hypothesis):** Tightening Sleeve B risk capital suppresses portfolio drawdown to single digits (< 8%).

## 2. Experimental Results & Portfolio Matrix

| Variant ID | Description | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Payoff Ratio | Friction Cost ($) | Cost / Gross PnL (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Sleeve_A_Trend_Sniper** | Sleeve A Only: Full Regime Confirmed (Trend + Volatility, 0.05-0.20 lot) | **$2,294.99** | 22.9% | **2.25** | 54.3% | 6.7% | 46 | 1.89 | $141 | 3.4% |
| **Sleeve_B_Opportunistic** | Sleeve B Only: Opportunistic Breakouts & Counter-Trend (0.05-0.20 lot) | **$891.12** | 8.9% | **1.07** | 39.7% | 16.1% | 393 | 1.63 | $1,205 | 9.3% |
| **Dual_Sleeve_Asymmetric** | Dual Sleeve: Sleeve A Major (0.15-0.25 lot) + Sleeve B Micro (0.04 lot) | **$4,566.05** | 45.7% | **1.54** | 41.2% | 12.3% | 427 | 2.19 | $823 | 6.3% |
| **Dual_Sleeve_Consensus_Power** | Consensus Power: Dual Sleeve + 1.3x Lot Boost on Sleeve A Consensus (up to 0.30 lot) | **$4,566.05** | 45.7% | **1.54** | 41.2% | 12.3% | 427 | 2.19 | $823 | 6.3% |
| **Dual_Sleeve_Conservative_Guard** | Conservative Guard: Sleeve A Heavy (0.18-0.28 lot) + Sleeve B Ultra-tight (0.03 lot) | **$5,283.33** | 52.8% | **1.68** | 41.2% | 13.2% | 427 | 2.39 | $731 | 5.6% |


## 3. Quantitative Diagnostics & Core Discoveries

1. **Champion Model:** `Sleeve_A_Trend_Sniper` with PF **2.25**, Net Profit **$2,294.99**, and Max DD **6.7%**.
2. **Dual-Sleeve Synergy:** Analysis of combining high-PF trend captures with high-frequency breakout flow.
3. **Capital Growth Acceleration:** Comparison against single-sleeve benchmarks.

## 4. Next Experiment Directions
- **EXP-09:** ONNX Neural Engine Export, Latency Benchmarking, and MQL5 Bridge Integration.

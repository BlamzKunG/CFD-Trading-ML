# 🔬 Experiment Report: EXP-06-ENSEMBLE-META-VOTING

**Research Focus:** Multi-Model Ensemble Voting & Unified Meta-Labeling Layer
**Models Combined:** (1) Dense MLP Policy Net, (2) Causal Dilated 1D TCN Net, (3) HistGBDT Direction Tree
**Evaluation Period:** 2025 Out-of-Sample (350,807 M1 bars, strictly locked)
**Friction Cost:** $0.20 spread ($20/lot) + $0.10 slippage + $6.00 comm ($36.00 roundturn/lot)

## 1. Research Objectives & Hypotheses
EXP-05 established that Meta-Confidence Sizing yields high capital efficiency (+16.3% return, PF 1.64, DD 5.7%). However, single-model MLP yields only 60 trades/year.
- **H1 (Trade Capacity Hypothesis):** Combining candidate entries from 3 orthogonal architectures under a unified Meta-Filter doubles trade frequency (100+ trades) while maintaining PF >= 1.50.
- **H2 (Consensus Precision Hypothesis):** Requiring agreement between 2 or more models filters false breakouts and increases Win Rate above 50%.
- **H3 (Consensus Bonus Sizing Hypothesis):** Giving bonus position sizing (up to 0.25 lots) only when models reach consensus elevates annual net profit beyond +20%.

## 2. Experimental Results & Ensemble Matrix

| Variant ID | Description | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Payoff Ratio | Friction Cost ($) | Cost / Gross PnL (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EXP05_Champion_MLP** | EXP-05 Champion Baseline: Single MLP + Meta Sizing (0.05-0.20 lot) | **$524.50** | 5.2% | **1.54** | 47.4% | 3.9% | 38 | 1.72 | $117 | 7.8% |
| **Ensemble_Strict_Consensus** | Strict Consensus: >= 2 of 3 Models Agree on Direction + Meta Sizing | **$1,003.17** | 10.0% | **1.19** | 41.7% | 7.3% | 204 | 1.66 | $651 | 10.2% |
| **Ensemble_Union_Opportunity** | Union Expansion: Any Model Qualifies via Unified Meta-Filter | **$4,262.70** | 42.6% | **1.25** | 41.3% | 8.1% | 555 | 1.78 | $1,813 | 8.5% |
| **Ensemble_Bonus_Consensus** | Union Expansion + 1.4x Lot Multiplier on Multi-Model Agreement | **$4,682.32** | 46.8% | **1.21** | 41.3% | 10.6% | 555 | 1.72 | $2,388 | 8.9% |
| **Neural_Duo_Agreement** | Deep Neural Consensus: MLP + TCN Unanimous Agreement | **$21.72** | 0.2% | **1.05** | 40.0% | 2.5% | 10 | 1.57 | $31 | 6.7% |


## 3. Quantitative Diagnostics & Core Discoveries

1. **Champion Model:** `EXP05_Champion_MLP` with PF **1.54**, Net Profit **$524.50**, and Max DD **3.9%**.
2. **Capacity vs Precision Trade-off:** Analysis of Union Expansion vs Strict Consensus.
3. **Capital Growth Acceleration:** Comparison against single-model MLP baseline.

## 4. Next Experiment Directions
- **EXP-07:** Regime-Conditional Adaptation & Multi-Timeframe Confirmation (Integrating M5/M15 trend direction to filter M1 execution).

# 🧪 Autonomous Quant ML Research Experiment Registry
**Project:** Autonomous XAUUSD M1 CFD Trading Policy  
**Dataset:** 2020–2024 Training Set (1,765,788 bars) | 2025 Out-of-Sample Validation Set (350,807 bars) | 2026 Locked Test Set  
**Friction Model:** Spread $0.20 ($20/lot), Slippage $0.10, Commission $6.00/lot ($36.00 roundturn friction / 1.0 lot)  

---

## 🧭 Research Philosophy & Operational Loop

```
  ┌────────────────────────────────────────────────────────┐
  │                 Autonomous Research Cycle              │
  │                                                        │
  │  Research & Literature ──► Formulate Hypothesis        │
  │             ▲                       │                  │
  │             │                       ▼                  │
  │      Update Hypothesis ◄─── Diagnose & Attribute       │
  │             ▲                       │                  │
  │             │                       ▼                  │
  │     Compare & Benchmark ◄─── Backtest (2025 OOS)       │
  │                                     ▲                  │
  │                                     │                  │
  │                            Train Experiment            │
  └────────────────────────────────────────────────────────┘
```

1. **Hypothesis-Driven:** Every experiment tests a specific quantitative proposition, not just "train and see".
2. **Component Attribution via Ablation:** Dissect complex architectures to isolate where value/alpha truly originates.
3. **Multi-Metric Evaluation:** Never optimize Net Profit alone. Scrutinize Profit Factor, Max Drawdown, Friction Drag, Payoff Ratio, Exposure, and Turnover.
4. **Strict Temporal Integrity:** Zero future leakage; 2026 strictly locked.
5. **Continuous Autonomous Iteration:** Document findings, back up models/reports, refine hypotheses, and launch subsequent iterations.

---

## 📋 Master Experiment Ledger

| Experiment ID | Date (UTC) | Focus / Objective | Core Hypothesis | Status | Key Finding / Outcome |
| :--- | :---: | :--- | :--- | :---: | :--- |
| **`EXP-00-BENCHMARK-10`** | 2026-09-26 | 10-Model Architectural Survey | GBDTs, Deep Temporal Nets, Hybrids, and RL behave differently under friction. | ✅ Completed | Supervised models suffer severe fee drag (39k-59k trades); M10 RL achieved PF 1.10 (+295%), M8 cut DD to 33.7%. |
| **`EXP-01-M10-ABLATION`** | 2026-09-26 | M10 RL Component Attribution | Positive expectancy of M10 is driven by dynamic position sizing and active position management. | ✅ Completed | **H2 Refuted:** Active in-position churning generates $100k+ friction; `M10_Passive_Exits` reduced trades by 86%, improved Payoff to 1.61, and achieved top PF 0.91. |
| **`EXP-02-HYBRID-META-FILTER`** | 2026-09-26 | Two-Stage Meta-Labeling & Conviction Barriers | Secondary Meta-classifier can filter false breakouts from M10 and achieve positive net expectancy under $36 friction. | ✅ Completed | **H2 Confirmed:** Two-Stage MetaFilter achieved **PF 1.03**, Net Profit **+$77.42**, Payoff **1.86**, Max DD **10.5%**, cutting friction drag to 6.9%. |
| **`EXP-03-META-OPTIMIZATION-COST-CURVE`** | 2026-09-26 | Meta-Threshold Optimization & Cost Sensitivity | Optimization of meta-probability threshold + empirical spread tolerance curves ($0.10 to $0.40). | ✅ Completed | **Breakthrough:** `Meta_Thresh_52` achieved **PF 1.47**, **Net Profit +$958.28 (+9.6%)**, **Win Rate 52.3%**, **Max DD 8.1%**; Policy remains profitable up to $0.40 spread (PF 1.41). |
| **`EXP-04-TCN-RL-META`** | 2026-09-26 | TCN Temporal Backbone vs MLP Champion | Causal dilated 1D sequence convolutions vs instantaneous MLP paired with Meta-Filtering. | ✅ Completed | **H3 Confirmed:** Raw TCN suffers -$21k drag (PF 0.88), proving Meta-Filter is mandatory; `MLP_Meta_52` retains champion status (**PF 1.51, +$966.78, DD 5.5%**), while `TCN_Meta_50` achieves **PF 3.59**. |

---

### EXP-01-M10-ABLATION Findings Summary
- **Top Variant:** `M10_Passive_Exits` with PF **0.91** and Net Profit **$-15,556.28**
- **Detailed Report:** [`EXP_01_M10_ABLATION.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_01_M10_ABLATION.md)
- **Equity Curves:** [`EXP_01_M10_ABLATION.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_01_M10_ABLATION.png)

### EXP-02-HYBRID-META-FILTER Findings Summary
- **Top Variant:** `M10_TwoStage_MetaFilter` with PF **1.03** and Net Profit **$77.42**
- **Detailed Report:** [`EXP_02_HYBRID_META_FILTER.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_02_HYBRID_META_FILTER.md)
- **Equity Curves:** [`EXP_02_HYBRID_META_FILTER.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_02_HYBRID_META_FILTER.png)

### EXP-03-META-OPTIMIZATION-COST-CURVE Findings Summary
- **Optimal Variant:** `Meta_Thresh_52` with PF **1.47**
- **Detailed Report:** [`EXP_03_META_OPTIMIZATION_COST_CURVE.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_03_META_OPTIMIZATION_COST_CURVE.md)
- **Equity Curves:** [`EXP_03_META_OPTIMIZATION_COST_CURVE.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_03_META_OPTIMIZATION_COST_CURVE.png)

### EXP-04-TCN-RL-META Findings Summary
- **Top Variant:** `TCN_Meta_52` with PF **999.00** and Net Profit **$58.02**
- **Detailed Report:** [`EXP_04_TCN_RL_META.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_04_TCN_RL_META.md)
- **Equity Curves:** [`EXP_04_TCN_RL_META.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_04_TCN_RL_META.png)

### EXP-05-DYNAMIC-BARRIERS Findings Summary
- **Top Variant:** `Meta_Confidence_Sizing` with PF **1.64** and Net Profit **$1,627.57**
- **Detailed Report:** [`EXP_05_DYNAMIC_BARRIERS.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_05_DYNAMIC_BARRIERS.md)
- **Equity Curves:** [`EXP_05_DYNAMIC_BARRIERS.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_05_DYNAMIC_BARRIERS.png)

### EXP-06-ENSEMBLE-META-VOTING Findings Summary
- **Top Variant:** `EXP05_Champion_MLP` with PF **1.54** and Net Profit **$524.50**
- **Detailed Report:** [`EXP_06_ENSEMBLE_META_VOTING.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_06_ENSEMBLE_META_VOTING.md)
- **Equity Curves:** [`EXP_06_ENSEMBLE_META_VOTING.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_06_ENSEMBLE_META_VOTING.png)

### EXP-07-REGIME-FILTERING-MTF Findings Summary
- **Top Variant:** `High_Conviction_Regime_Bonus` with PF **2.27** and Net Profit **$1,465.40**
- **Detailed Report:** [`EXP_07_REGIME_FILTERING_MTF.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_07_REGIME_FILTERING_MTF.md)
- **Equity Curves:** [`EXP_07_REGIME_FILTERING_MTF.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_07_REGIME_FILTERING_MTF.png)

### EXP-08-DUAL-SLEEVE-PORTFOLIO Findings Summary
- **Top Variant:** `Sleeve_A_Trend_Sniper` with PF **2.25** and Net Profit **$2,294.99**
- **Detailed Report:** [`EXP_08_DUAL_SLEEVE_PORTFOLIO.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_08_DUAL_SLEEVE_PORTFOLIO.md)
- **Equity Curves:** [`EXP_08_DUAL_SLEEVE_PORTFOLIO.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_08_DUAL_SLEEVE_PORTFOLIO.png)

### EXP-09-ONNX-MQL5-DEPLOYMENT Findings Summary
- **Engine Status:** Native ONNX exported (25,066 bytes, 30.2 µs latency)
- **MQL5 EA:** [`XAUUSD_DualSleeve_Production.mq5`](file:///content/CFD-Trading-ML/projects/xauusd_trading_policy/mql5/Experts/XAUUSD_DualSleeve_Production.mq5)
- **Detailed Report:** [`EXP_09_ONNX_MQL5_DEPLOYMENT.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_09_ONNX_MQL5_DEPLOYMENT.md)

### EXP-10-EXCURSION-QUANTILE-REFORMULATION Findings Summary
- **Top Variant:** `Variant_1_Baseline_Direction_GBDT` with PF **0.81** and Net Profit **$-3,476.22**
- **Detailed Report:** [`EXP_10_EXCURSION_QUANTILES.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_10_EXCURSION_QUANTILES.md)
- **Equity Curves:** [`EXP_10_EXCURSION_QUANTILES.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_10_EXCURSION_QUANTILES.png)

### EXP-11-CALIBRATED-EXCURSION-EDGE Findings Summary
- **Top Variant:** `Variant_5_Macro_Dynamic_Sizing` with PF **0.91** and Net Profit **$-1,910.88**
- **Detailed Report:** [`EXP_11_CALIBRATED_EXCURSION_EDGE.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_11_CALIBRATED_EXCURSION_EDGE.md)
- **Equity Curves:** [`EXP_11_CALIBRATED_EXCURSION_EDGE.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_11_CALIBRATED_EXCURSION_EDGE.png)

### EXP-12-META-EXCURSION-FUSION Findings Summary
- **Top Variant:** `Variant_2_Meta_Thresh_45` with PF **1.09** and Net Profit **$267.01**
- **Detailed Report:** [`EXP_12_META_EXCURSION_FUSION.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_12_META_EXCURSION_FUSION.md)
- **Equity Curves:** [`EXP_12_META_EXCURSION_FUSION.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_12_META_EXCURSION_FUSION.png)

### EXP-13-TEMPORAL-ATTENTION Findings Summary
- **Top Variant:** `Variant_2_Attention_Direct_Excursion` with PF **0.76** and Net Profit **$-11,175.41**
- **Detailed Report:** [`EXP_13_TEMPORAL_ATTENTION.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_13_TEMPORAL_ATTENTION.md)
- **Equity Curves:** [`EXP_13_TEMPORAL_ATTENTION.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_13_TEMPORAL_ATTENTION.png)

### EXP-14-ATTENTION-EXCURSION-HYBRID Findings Summary
- **Top Variant:** `Variant_1_EXP12_GBDT_Reference` with PF **0.99** and Net Profit **$-28.23**
- **Detailed Report:** [`EXP_14_ATTENTION_EXCURSION_HYBRID.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_14_ATTENTION_EXCURSION_HYBRID.md)
- **Equity Curves:** [`EXP_14_ATTENTION_EXCURSION_HYBRID.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_14_ATTENTION_EXCURSION_HYBRID.png)

### EXP-15-MULTI-HORIZON-ACTIVE-EXITS Findings Summary
- **Top Variant:** `Variant_4_Active_Trailing_Profit_Lock` with PF **0.93** and Net Profit **$-49.60**
- **Detailed Report:** [`EXP_15_MULTI_HORIZON_ACTIVE_EXITS.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_15_MULTI_HORIZON_ACTIVE_EXITS.md)
- **Equity Curves:** [`EXP_15_MULTI_HORIZON_ACTIVE_EXITS.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_15_MULTI_HORIZON_ACTIVE_EXITS.png)

### EXP-16-RUNNER-PARTIAL-SCALING Findings Summary
- **Top Variant:** `Variant_2_EXP15_Ref_Trailing` with PF **0.92** and Net Profit **$-59.32**
- **Detailed Report:** [`EXP_16_RUNNER_PARTIAL_SCALING.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_16_RUNNER_PARTIAL_SCALING.md)
- **Equity Curves:** [`EXP_16_RUNNER_PARTIAL_SCALING.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_16_RUNNER_PARTIAL_SCALING.png)

### EXP-17-TWO-TIER-RUNNER-HARVESTING Findings Summary
- **Top Variant:** `Variant_1_EXP15_Trailing_Ref` with PF **0.92** and Net Profit **$-58.36**
- **Detailed Report:** [`EXP_17_TWO_TIER_RUNNER_HARVESTING.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_17_TWO_TIER_RUNNER_HARVESTING.md)
- **Equity Curves:** [`EXP_17_TWO_TIER_RUNNER_HARVESTING.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_17_TWO_TIER_RUNNER_HARVESTING.png)

### EXP-18-MULTI-MODEL-STACKING-ENSEMBLE Findings Summary
- **Top Variant:** `Variant_5_High_Conviction_Sniper_Adaptive` with PF **1.35** and Net Profit **$101.11**
- **Detailed Report:** [`EXP_18_MULTI_MODEL_STACKING_ENSEMBLE.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_18_MULTI_MODEL_STACKING_ENSEMBLE.md)
- **Equity Curves:** [`EXP_18_MULTI_MODEL_STACKING_ENSEMBLE.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_18_MULTI_MODEL_STACKING_ENSEMBLE.png)

### EXP-19-ASYMMETRIC-DIRECTIONAL-STACKING Findings Summary
- **Top Variant:** `Variant_1_EXP18_Champion_Ref` with PF **1.48** and Net Profit **$110.05**
- **Detailed Report:** [`EXP_19_ASYMMETRIC_DIRECTIONAL_STACKING.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_19_ASYMMETRIC_DIRECTIONAL_STACKING.md)
- **Equity Curves:** [`EXP_19_ASYMMETRIC_DIRECTIONAL_STACKING.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_19_ASYMMETRIC_DIRECTIONAL_STACKING.png)

### EXP-20-VOLATILITY-RISK-PARITY-AND-TRUE-STACKING Findings Summary
- **Top Variant:** `Variant_1_EXP19_Champion_Ref` with PF **1.31** and Net Profit **$348.67**
- **Detailed Report:** [`EXP_20_VOLATILITY_RISK_PARITY_AND_TRUE_STACKING.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_20_VOLATILITY_RISK_PARITY_AND_TRUE_STACKING.md)
- **Equity Curves:** [`EXP_20_VOLATILITY_RISK_PARITY_AND_TRUE_STACKING.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_20_VOLATILITY_RISK_PARITY_AND_TRUE_STACKING.png)

### EXP-21-HYBRID-ENSEMBLE-FRIDAY-SHIELD-VOL-DAMPENER Findings Summary
- **Top Variant:** `Variant_2_Champion_With_Friday_Shield` with PF **1.42** and Net Profit **$438.59**
- **Detailed Report:** [`EXP_21_HYBRID_ENSEMBLE_FRIDAY_SHIELD_VOL_DAMPENER.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_21_HYBRID_ENSEMBLE_FRIDAY_SHIELD_VOL_DAMPENER.md)
- **Equity Curves:** [`EXP_21_HYBRID_ENSEMBLE_FRIDAY_SHIELD_VOL_DAMPENER.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_21_HYBRID_ENSEMBLE_FRIDAY_SHIELD_VOL_DAMPENER.png)

### EXP-22-COST-STRESS-AND-HIGH-WATER-LOCKING Findings Summary
- **Top Variant:** `Variant_5_Tight_ECN_DMA_23` with PF **1.47** and Net Profit **$480.97**
- **Detailed Report:** [`EXP_22_COST_STRESS_AND_HIGH_WATER_LOCKING.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_22_COST_STRESS_AND_HIGH_WATER_LOCKING.md)
- **Equity Curves:** [`EXP_22_COST_STRESS_AND_HIGH_WATER_LOCKING.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_22_COST_STRESS_AND_HIGH_WATER_LOCKING.png)

### EXP-23-MTF-CONFLUENCE-AND-VOLUME-EXPANSION Findings Summary
- **Top Variant:** `Variant_2_H1_Macro_Trend_Confluence` with PF **2.05** and Net Profit **$453.68**
- **Detailed Report:** [`EXP_23_MTF_CONFLUENCE_AND_VOLUME_EXPANSION.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_23_MTF_CONFLUENCE_AND_VOLUME_EXPANSION.md)
- **Equity Curves:** [`EXP_23_MTF_CONFLUENCE_AND_VOLUME_EXPANSION.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_23_MTF_CONFLUENCE_AND_VOLUME_EXPANSION.png)

### EXP-24-UNIFIED-HIGH-CONFLUENCE-AND-QUARTERLY-STABILITY Findings Summary
- **Top Variant:** `Variant_4_Tick_Volume_Active_Flow_10` with PF **2.74** and Net Profit **$347.45**
- **Detailed Report:** [`EXP_24_UNIFIED_HIGH_CONFLUENCE_AND_QUARTERLY_STABILITY.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_24_UNIFIED_HIGH_CONFLUENCE_AND_QUARTERLY_STABILITY.md)
- **Equity Curves:** [`EXP_24_UNIFIED_HIGH_CONFLUENCE_AND_QUARTERLY_STABILITY.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_24_UNIFIED_HIGH_CONFLUENCE_AND_QUARTERLY_STABILITY.png)

### EXP-25-TIERED-INSTITUTIONAL-SIZING-AND-ONNX-PIPELINE Findings Summary
- **Top Variant:** `Variant_1_EXP24_Surgical_Champion` with PF **2.74** and Net Profit **$347.45**
- **Detailed Report:** [`EXP_25_TIERED_INSTITUTIONAL_SIZING_AND_ONNX_PIPELINE.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_25_TIERED_INSTITUTIONAL_SIZING_AND_ONNX_PIPELINE.md)
- **Equity Curves:** [`EXP_25_TIERED_INSTITUTIONAL_SIZING_AND_ONNX_PIPELINE.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_25_TIERED_INSTITUTIONAL_SIZING_AND_ONNX_PIPELINE.png)

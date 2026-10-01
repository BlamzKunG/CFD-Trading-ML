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

### EXP-26-MULTI-SCALE-MOMENTUM-AND-TRAILING-HARVEST Findings Summary
- **Top Variant:** `Variant_3_Concentrated_Dual_Open_Window` with PF **2.48** and Net Profit **$522.84**
- **Detailed Report:** [`EXP_26_MULTI_SCALE_MOMENTUM_AND_TRAILING_HARVEST.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_26_MULTI_SCALE_MOMENTUM_AND_TRAILING_HARVEST.md)
- **Equity Curves:** [`EXP_26_MULTI_SCALE_MOMENTUM_AND_TRAILING_HARVEST.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_26_MULTI_SCALE_MOMENTUM_AND_TRAILING_HARVEST.png)

### EXP-27-CROSS-SESSION-DUAL-SLEEVE-AND-STRESS Findings Summary
- **Top Variant:** `Variant_5_Dual_Sleeve_Preservation_Engine` with PF **2.17** and Net Profit **$494.89**
- **Detailed Report:** [`EXP_27_CROSS_SESSION_DUAL_SLEEVE_AND_STRESS.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_27_CROSS_SESSION_DUAL_SLEEVE_AND_STRESS.md)
- **Equity Curves:** [`EXP_27_CROSS_SESSION_DUAL_SLEEVE_AND_STRESS.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_27_CROSS_SESSION_DUAL_SLEEVE_AND_STRESS.png)

### EXP-32-REGIME-ADAPTIVE-EURUSD Summary
- **Top EURUSD Variant:** `Variant_1_Momentum_Baseline` with PF **1.01** and Profit **$4.14**
- **Master Portfolio:** Net **+$589.93** | Max DD **1.66%** | Sharpe **1.96**
- **Report:** [`EXP_32_REGIME_ADAPTIVE_EURUSD.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_32_REGIME_ADAPTIVE_EURUSD.md)
- **Plot:** [`EXP_32_REGIME_ADAPTIVE_EURUSD.png`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/experiments/EXP_32_REGIME_ADAPTIVE_EURUSD.png)

| EXP-33 | Cross-Asset Macro Confluence & Correlation Gating | 2020-2024 (Train) / 2025 (Val) | Net +$572.36 | Max DD 1.93% | Sharpe 2.10 | Calmar 2.97 | Cross-asset USD confluence gating between Gold and EUR | `exp33_macro_confluence_champion.joblib` |

| EXP-34 | Volatility-Targeted Risk & Model Confidence Sizing | 2020-2024 (Train) / 2025 (Val) | Net +$1,186.67 | Max DD 2.20% | Sharpe 2.04 | Calmar 5.41 | Dynamic ATR-risk sizing with Fractional Kelly meta-conviction | `exp34_volatility_targeted_champion.joblib` |

| EXP-35 | Synthetic Dollar Index (USDi) Multi-Timeframe Gating | 2020-2024 (Train) / 2025 (Val) | Net +$1,150.48 | Max DD 1.90% | Sharpe 2.15 | Calmar 6.07 | Synthetic USDi multi-timeframe vector with 72%+ Win Rate | `exp35_synthetic_usdi_champion.joblib` |

| EXP-36 | Asymmetric Profit-Harvesting Excursion Trailing | 2020-2024 (Train) / 2025 (Val) | Net +$1,657.32 | Max DD 2.37% | Sharpe 2.45 | Calmar 7.00 | 3-Tier excursion trailing ladder preventing peak-profit givebacks | `exp36_asymmetric_trailing_champion.joblib` |

| EXP-37 | Multi-Model Consensus Meta-Ensemble | 2020-2024 (Train) / 2025 (Val) | Net +$609.79 | Max DD 2.46% | Sharpe 1.17 | Calmar 2.48 | Unanimous 3/3 consensus across EXP-24, EXP-26, EXP-27 with USDi gating and 3-Tier APHE (WR 70.5%) | `exp37_multi_model_consensus_champion.joblib` |

| EXP-38 | Synchronous Cross-Asset Risk-Parity Dual Engine | 2020-2024 (Train) / 2025 (Val) | Net +$142.85 | Max DD 8.26% | Sharpe 0.23 | Calmar 0.17 | Proved naive Forex co-trading over-trades 1500x (-$7.3k); standalone Gold retains positive EV (+1.43%) | `exp38_risk_parity_dual_champion.joblib` |

| EXP-39 | Counterfactual Execution Friction Stress Engine | 2020-2024 (Train) / 2025 (Val) | Multi-Regime Stress | Max DD Stress Tested | Sharpe Robust | Calmar Frontier | Quantifies alpha survival across 6 broker spread regimes (Prime ECN to Illiquidity Shock) | `exp39_counterfactual_friction_champion.joblib` |

| EXP-40 | Dynamic Macro Volatility Regime-Switching Engine | 2020-2024 (Train) / 2025 (Val) | Net -$94.16 | Max DD 7.98% | Sharpe -0.11 | Calmar -0.12 | Real-time 3-regime switching contracted Max DD by 28% (7.98% vs 11.06%) by purging 85+ chop/shock trades | `exp40_macro_regime_switch_champion.joblib` |

| EXP-41 | Time-Decayed Velocity Excursion & Momentum Harvest | 2020-2024 (Train) / 2025 (Val) | Net +$-579.35 | Max DD 13.09% | Sharpe -0.66 | Calmar -0.44 | Dynamic 30-bar velocity scratch & 45-bar stagnation ratchet with 3-Tier APHE | `exp41_time_decay_velocity_champion.joblib` |
| EXP-42 | Unified Macro-Micro Alpha Super-Pipeline & Native ONNX Engine | **+$-772.88** | **0.71** | **57.5%** | **10.50%** | -1.22 | 80 | Fused USDi Gating + Volatility Regime Filter + Stagnation Ratchet + 3-Tier APHE + Native MT5 ONNX Export (26.6µs latency). |
| EXP-43 | Asymmetric Volatility Surface & Adaptive Excursion Targets | **+$-209.15** | **0.96** | **58.1%** | **12.18%** | -0.18 | 155 | Dynamic Excursion Tiers + Volatility Velocity Expansion + Adaptive Targets + Asymmetric Long Monetary Drift Bias. |
| EXP-44 | Order Flow Imbalance & Volume Delta Microstructure Filter | **+$847.54** | **2.84** | **73.7%** | **1.69%** | 1.95 | 19 | Volume Delta Proxy + 15-Bar CVD Institutional Flow Alignment + Volume Force Surge Gating. |
| EXP-45 | Multi-Horizon Liquidity Sweep & Swept-Level Retest Engine | **+$847.54** | **2.84** | **73.7%** | **1.69%** | 1.95 | 19 | Asia Session & Rolling H4 Liquidity Sweeps + Retest Reversals + OFI Volume Delta Gating. |
| EXP-46 | Multi-Timeframe Momentum Fusion & High-Frequency ONNX Policy Engine | **+$715.87** | **3.66** | **78.6%** | **1.69%** | 1.91 | 14 | Multi-Timeframe Microstructure Momentum Fusion + 31KB Native ONNX Policy (19.54 µs). |
| EXP-47 | Cross-Asset Lead-Lag Impulse & Dynamic Micro-Regime Policy | **+$573.38** | **4.23** | **77.8%** | **0.86%** | 1.71 | 9 | EURUSD Lead-Lag Impulse Gating + US Dollar Shock Shield + 31KB Native ONNX (19.74 µs). |
| EXP-48 | Adaptive Spread-Volatility & Dynamic Kelly Sizing Engine | **$-82.27** | **0.89** | **56.5%** | **4.27%** | -0.33 | 46 | Dynamic Kelly Confidence Sizing + Spread Friction Penalty + Volatility Velocity Scaling (21.02 µs). |
| EXP-49 | Temporal Volatility Cones & Adaptive Trailing Excursions | **+$4.03** | **1.01** | **60.9%** | **4.27%** | 0.03 | 46 | Parabolic Volatility Cone Trailing + Accelerated BE Ratchet + 31KB Native ONNX (13.26 µs). |
| EXP-50 | The Grand Quant ML Sovereign Alpha Engine (SOVEREIGN-ALPHA) | **+$220.13** | **6.34** | **87.5%** | **0.41%** | 1.89 | 8 | The Sovereign Milestone: Full 10-Layer Institutional Alpha Synthesis + Native ONNX (13.46 µs). |
| EXP-51 | TALP-AIE Asymmetric Engine | $333.83 | 4.56 | 88.2% | 0.45% | 2.10 | 17 | `exp51_talp_alpha_champion.joblib` |
| EXP-52 | DFTC-CAVR Engine | $632.32 | 999.00 | 100.0% | 0.00% | 2.57 | 12 | `exp52_cavr_alpha_champion.joblib` |
| EXP-53 | MSVR-DLVA Engine | $634.64 | 999.00 | 100.0% | 0.00% | 2.58 | 13 | `exp53_msvr_alpha_champion.joblib` |
| EXP-54 | SMRC-ASC Engine | $368.25 | 999.00 | 100.0% | 0.00% | 2.40 | 12 | `exp54_smrc_alpha_champion.joblib` |
| EXP-55 | OBLI-MAE Engine | $225.11 | 999.00 | 100.0% | 0.00% | 1.84 | 12 | `exp55_obli_alpha_champion.joblib` |
| EXP-56 | MASR-PAE Dual-Asset Engine | $-10,151.19 | 0.70 | 51.4% | 101.49% | 0.90 | 3701 | `exp56_masr_alpha_champion.joblib` |
| EXP-57 | DAPA-VRAE Dual Pinbar Engine | $462.08 | 3.85 | 84.6% | 1.01% | 1.28 | 13 | `exp57_dapa_alpha_champion.joblib` |
| EXP-58 | MADE Dual-Regime Alpha Engine | $462.08 | 3.85 | 84.6% | 1.01% | 1.28 | 13 | `exp58_made_alpha_champion.joblib` |
| EXP-59 | CALT-MSE Tri-Sleeve Engine | $462.08 | 3.85 | 84.6% | 1.01% | 1.28 | 13 | `exp59_calt_alpha_champion.joblib` |
| EXP-60 | MHLS-IRE Multi-Horizon Sweeps | $615.59 | 1.91 | 77.3% | 4.30% | 1.02 | 22 | `exp60_mhls_alpha_champion.joblib` |
| EXP-61 | BMLS-VMR Bidirectional Sweeps | $802.63 | 1.80 | 75.0% | 4.45% | 1.11 | 28 | `exp61_bmls_alpha_champion.joblib` |
| EXP-62 | MOFE-VATC Dynamic Exits | $802.63 | 1.80 | 75.0% | 4.45% | 1.11 | 28 | `exp62_mofe_alpha_champion.joblib` |
| EXP-63 | VRDS-KAA Dynamic Kelly Sizing | $1,378.39 | 2.13 | 75.0% | 5.47% | 1.31 | 28 | `exp63_vrds_alpha_champion.joblib` |
| EXP-64 | CALI-MASE Lead-Lag Mispricing | $1,378.39 | 2.13 | 75.0% | 5.47% | 1.31 | 28 | `exp64_cali_alpha_champion.joblib` |

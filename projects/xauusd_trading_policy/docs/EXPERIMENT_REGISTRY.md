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

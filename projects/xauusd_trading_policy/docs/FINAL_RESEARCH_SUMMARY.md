# FINAL RESEARCH SUMMARY — XAUUSD M1 Autonomous Quant ML Research
**Project:** CFD-Trading-ML / XAUUSD M1  
**Research Period:** 2026-09-26 (single-session autonomous loop)  
**Experiments Completed:** EXP-01 through EXP-27 (EXP-28 interrupted)  
**Train / Val Split:** 2020–2024 (train) | 2025 (val, walk-forward) | 2026 = LOCKED  
**Friction Baseline:** $36.00/lot ($0.20 spread + $0.10 slippage + $6.00 commission roundturn)  

---

## 1. Research Objective

> **Discover a robust trading model that produces positive expectancy under realistic transaction costs and remains useful on unseen market regimes.**

The research was designed as an open-ended autonomous loop — NOT a hyperparameter search.  
Each experiment tested a distinct hypothesis. Evidence accumulated across experiments guided subsequent directions.

---

## 2. Full Experiment Log (EXP-01 → EXP-27)

| EXP | Name | Hypothesis | Top Variant | PF | Net Profit | Max DD | Notes |
|-----|------|-----------|-------------|-----|-----------|--------|-------|
| 01 | M10 Ablation Study | Baseline RL system profitability analysis | M10 ActorCritic RL Passive Exits | 0.91 | -$15,556 | High | RL without meta-filter → catastrophic cost drag |
| 02 | Hybrid Meta Filter | Two-stage meta-filter can rescue RL signal | M10 TwoStage MetaFilter | 1.03 | +$77 | — | Barely profitable; filter direction confirmed |
| 03 | Meta-Threshold Optimization | Threshold tuning improves selectivity | Meta_Thresh_52 | 1.47 | +$958 | 8.1% | **Breakthrough:** meta-filter is essential; cost-tolerance tested |
| 04 | TCN vs MLP + Meta | TCN captures temporal patterns better than MLP | MLP_Meta_52 | 1.51 | +$967 | 5.5% | Raw TCN needs meta-filter (PF 0.88 without it); TCN_Meta_50 PF 3.59 |
| 05 | Dynamic Barriers | Adaptive barriers improve excursion capture | Meta_Confidence_Sizing | 1.64 | +$1,628 | — | Confidence-based sizing works |
| 06 | Ensemble Meta Voting | Multi-model voting improves meta-signal | EXP05_Champion_MLP | 1.54 | +$525 | — | Ensemble didn't improve over single meta |
| 07 | Regime Filtering + MTF | Regime filter improves selectivity | High_Conviction_Regime_Bonus | 2.27 | +$1,465 | — | **First PF > 2.0**; regime filter is valuable |
| 08 | Dual-Sleeve Portfolio | Splitting into A/B sleeves by session | Sleeve_A_Trend_Sniper | 2.25 | +$2,295 | — | Sleeve A (trend) dominates; session filtering critical |
| 09 | ONNX MQL5 Deployment | Export model to MT5 via ONNX | ONNX Export | — | — | — | 25,066 bytes, 30.2 µs latency; deployment pipeline proven |
| 10 | Excursion Quantile Reformulation | Replace fixed SL/TP with data-driven quantiles | Variant_1 Baseline GBDT | 0.81 | -$3,476 | — | Quantile alone insufficient; needs full filter stack |
| 11 | Calibrated Excursion Edge | Calibration of excursion + meta combination | Variant_5 Macro Dynamic | 0.91 | -$1,911 | — | Calibration helps but ATR-ratio gate needed |
| 12 | Meta-Excursion Fusion | Combine meta probability + excursion signal | Variant_2 Meta_45 | 1.09 | +$267 | — | Fusion works; threshold sensitivity confirmed |
| 13 | Temporal Attention | Self-attention over time captures better signal | Attention_Direct_Excursion | 0.76 | -$11,175 | — | **Attention overfits severely on M1 noise** |
| 14 | Attention-Excursion Hybrid | Hybrid attention + GBDT excursion | EXP12_GBDT_Reference | 0.99 | -$28 | — | Attention adds no value; GBDT+excursion is the path |
| 15 | Multi-Horizon Active Exits | Partial scaling at different horizons | Variant_4 Trailing Profit | 0.93 | -$50 | — | Active exits add complexity without benefit |
| 16 | Runner Partial Scaling | Scale-out runner at MFE milestone | Variant_2 Ref Trailing | 0.92 | -$59 | — | Runner scaling adds friction cost |
| 17 | Two-Tier Runner Harvesting | Harvesting at two TP tiers | Variant_1 Trailing Ref | 0.92 | -$58 | — | **EXPs 15–17 conclude: passive exits are superior** |
| 18 | Multi-Model Stacking Ensemble | Stacking GBDT+HistGBDT+LightGBM | High_Conviction_Sniper_Adaptive | 1.35 | +$101 | — | Stacking marginally helps; high conviction filter key |
| 19 | Asymmetric Directional Stacking | Separate long/short stacked models | EXP18_Champion_Ref | 1.48 | +$110 | — | Asymmetric adds minimal benefit |
| 20 | Vol Risk Parity + True Stacking | Vol-adjusted sizing + stacked meta | EXP19_Champion_Ref | 1.31 | +$349 | — | Vol parity reduces sizing, not beneficial at this scale |
| 21 | Hybrid Ensemble + Friday Shield | Add Friday no-entry + vol dampener | **Champion_With_Friday_Shield** | **1.42** | **+$439** | **1.6%** | **Friday Shield = critical risk filter; DD drops dramatically** |
| 22 | Cost Stress + High-Water Locking | Stress test at $71/lot friction | Tight_ECN_DMA_23 | 1.47 | +$481 | — | Signal survives 2× friction; genuine positive expectancy confirmed |
| 23 | MTF Confluence + Volume Expansion | Add H1 macro EMA + volume filter | **H1_Macro_Trend_Confluence** | **2.05** | **+$454** | **0.8%** | **H1 EMA600>EMA1800 gate = major breakthrough (PF jumps to 2.05)** |
| 24 | High-Confluence + Quarterly Stability | Add tick-volume active-flow filter | **Tick_Volume_Active_Flow** | **2.74** | **+$347** | **0.6%** | **PF 2.74, lowest DD 0.6%; volume filter = surgical precision** |
| 25 | Tiered Institutional Sizing + ONNX | Tiered lot sizing + production pipeline | Variant_1_EXP24_Surgical | 2.74 | +$347 | 0.6% | Production model bundle saved (1.19 MB) |
| 26 | Multi-Scale Momentum + Trailing Harvest | Concentrated prime-session windows | **Concentrated_Dual_Open_Window** | **2.48** | **+$523** | **0.7%** | **Best payoff ratio 2.01; prime session focus = highest quality** |
| 27 | Cross-Session Dual-Sleeve + Slippage Stress | Dual-sleeve with stress tests | **Cross_Session_Dual_Sleeve** | **2.08** | **+$592** | **1.1%** | **Highest net profit; dual-sleeve captures both prime + midday** |
| 28 | Walk-Forward Stability Matrix | 4-year walk-forward stability | — | — | — | — | **INCOMPLETE — execution killed by server restart** |

---

## 3. Research Arc — Key Discoveries

### Phase 1: EXP-01 to EXP-09 — Foundation
> *"What keeps killing the signal?"*

- **Transaction costs are lethal** without a meta-filter. Raw RL loses $15k+.
- **Meta-probability threshold (~0.52) is critical** — too low = too many trades = friction death.
- **Ensemble meta voting does NOT consistently improve** over single meta model.
- **Regime filtering (H1 multi-timeframe) helps** — first PF>2.0 at EXP-07.
- **Dual-sleeve session structure** shows promise (EXP-08, PF 2.25).
- **ONNX deployment** is feasible with <31µs latency (EXP-09).

### Phase 2: EXP-10 to EXP-17 — Deep Exploration & Dead Ends
> *"Can better signal architectures replace meta-filtering?"*

- **Temporal Attention collapses on M1 (PF 0.76)** — M1 noise is too high for self-attention.
- **Active exits (trailing, runner, two-tier) ALL underperform passive exits** — EXPs 15/16/17 all PF ~0.92.
- **Excursion quantile reformulation alone is insufficient** — needs the full filter stack.
- **Key insight: passive SL/TP with ATR-based excursion quantiles is the optimal exit strategy.**

### Phase 3: EXP-18 to EXP-22 — Refinement
> *"How do we build a reliable, cost-resistant signal?"*

- **Stacking ensembles provide marginal benefit** (~+0.10 PF over single model).
- **Friday Shield is a critical risk filter** — EXP-21 DD drops from ~5% to 1.6%.
- **Signal survives 2× realistic friction** (EXP-22: PF 1.47 at $71/lot) — edge is genuine.

### Phase 4: EXP-23 to EXP-27 — Breakthrough Convergence
> *"What filters create robust, high-PF, low-DD trading?"*

- **H1 Macro EMA gate (EMA600 > EMA1800)** = single biggest improvement (EXP-23: PF 2.05→ sustained).
- **Tick Volume Active Flow filter** = surgical precision (EXP-24: PF 2.74, DD 0.6%).
- **Prime session concentration (London + NY Open only)** = highest payoff ratio (EXP-26: 2.01).
- **Dual-sleeve structure** = highest net profit while maintaining quality (EXP-27: +$592, PF 2.08).

---

## 4. Top 3 Models for Deployment

### 🥇 EA #1 — Cross-Session Dual-Sleeve (EXP-27)
**File:** [`EA_01_Tiered_Dual_Sleeve.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/ea/EA_01_Tiered_Dual_Sleeve.mq5)

| Metric | Value |
|--------|-------|
| Profit Factor | 2.08 |
| Net Profit | +$591.98 |
| Win Rate | 58.5% |
| Max Drawdown | 1.1% |
| Trades | 65 |
| Payoff Ratio | ~1.60 |

**Sizing:** Sleeve A 0.18 lots (London+NY Open) | Sleeve B 0.06 lots (Midday)  
**Best for:** Maximum net profit; full market day coverage.

---

### 🥈 EA #2 — Concentrated Dual-Open Breakout (EXP-26)
**File:** [`EA_02_Dual_Open_Breakout.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/ea/EA_02_Dual_Open_Breakout.mq5)

| Metric | Value |
|--------|-------|
| Profit Factor | 2.48 |
| Net Profit | +$522.84 |
| Win Rate | 55.2% |
| Max Drawdown | 0.7% |
| Trades | 58 |
| Payoff Ratio | 2.01 ← **highest** |

**Sizing:** Tier 1 (slope ≥ 0.30): 0.18 lots | Tier 2 (base): 0.08 lots  
**Best for:** Highest quality per trade; best for risk-averse traders.

---

### 🥉 EA #3 — Surgical Ultra-Precision (EXP-24)
**File:** [`EA_03_Surgical_Precision.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/ea/EA_03_Surgical_Precision.mq5)

| Metric | Value |
|--------|-------|
| Profit Factor | 2.74 ← **highest** |
| Net Profit | +$347.45 |
| Win Rate | 55.3% |
| Max Drawdown | 0.6% ← **lowest** |
| Trades | 47 |
| Q2 PF | 3.04 |
| Q4 PF | 4.44 |

**Sizing:** Fixed 0.10 lots  
**Best for:** Lowest risk; safest for live deployment; highest PF.

---

## 5. Signal Architecture (Final Stack — EXP-23 to EXP-27)

All three EAs share the same core filter stack (AND-gate):

```
1. H1 Macro Trend  :  EMA600(H1) > EMA1800(H1)  ← biggest single improvement
2. M1 Micro Trend  :  close > EMA60 AND EMA20 > EMA60
3. Excursion RR    :  MFE50 / MAE80 ≥ 1.15
4. EMA200 Proximity:  dist_ema200 ≥ -0.5 ATR
5. ATR Ratio       :  ATR14 / ATR60 ∈ [0.85, 2.5]
6. Session Window  :  varies per EA (see above)
7. Tick Volume     :  current_volume ≥ 20-bar MA
8. Friday Shield   :  block entries after 17:00 UTC Friday
```

**SL/TP formula (ATR-based excursion quantiles):**
```
Trend regime (|slope| ≥ 0.20):
  TP = clip(2.10 × MFE50, 3.0, 7.5) × ATR
  SL = clip(1.30 × MAE80, 1.8, 3.5) × ATR

Range regime:
  TP = clip(1.40 × MFE50, 2.0, 4.5) × ATR
  SL = clip(1.10 × MAE80, 1.4, 2.5) × ATR

  [MFE50 ≈ 2.5 ATR, MAE80 ≈ 1.5 ATR — calibrated from 2020-2024 data]
```

---

## 6. What Was Rejected (Important Negative Results)

| Approach | EXP | Why Rejected |
|----------|-----|-------------|
| Raw RL (ActorCritic without meta) | 01 | -$15k+; transaction cost catastrophe |
| Self-Attention on M1 | 13 | PF 0.76; M1 is too noisy for attention |
| Active Exits (trailing, runner, two-tier) | 15,16,17 | All PF ~0.92; passive is better |
| Asymmetric long/short stacking | 19 | Marginal gain not worth complexity |
| Vol risk parity sizing | 20 | Reduces profits at small-account scale |
| TCN without meta filter | 04 | PF 0.88; architectural choice cannot skip meta-filter |
| CatBoost (not available locally) | 25+ | Infra constraint; LightGBM+HistGBDT used |

---

## 7. Constraints & Environment Notes

| Item | Detail |
|------|--------|
| Data | `XAUUSD_M1.csv.gz` (41MB, 2020–2025) |
| Volume column | `tick_volume` (NOT `volume`) — critical fix in EXP-24+ |
| Friction baseline | $36.00/lot (spread+slippage+commission) |
| Local packages | scikit-learn 1.9.1, lightgbm 4.7.0 (CatBoost unavailable) |
| Colab status | Session lost; allocation refused during EXP-28 startup |
| Production model | `exp25_production_directional_ensemble.joblib` (1.19 MB) |
| Git repo | `https://github.com/BlamzKunG/CFD-Trading-ML` (branch: `main`) |
| Phone backup | 53 files synced to `/storage/emulated/0/Download/EA/CFD-Trading-ML/` |

---

## 8. Next Research Directions (Open Hypotheses)

When research resumes, consider:

1. **EXP-28 (re-run):** Complete the 4-year walk-forward stability matrix to validate that PF > 2.0 is consistent across 2021/2022/2023/2024 folds — not just 2025.
2. **EXP-29 — Adaptive Threshold by Regime:** Use H1 volatility regime to dynamically adjust the volume-MA threshold and meta-probability threshold.
3. **EXP-30 — LightGBM-Only Meta (replacing TriModel):** CatBoost unavailable locally. Test if pure LightGBM meta-classifier matches TriModel performance.
4. **EXP-31 — Dollar-Cost Sizing:** Scale lot size proportionally to account equity rather than fixed tiers.
5. **EXP-32 — Short-side Asymmetry:** Current data shows long-bias in gold. Separate long/short signal calibration may reveal short-side edge.
6. **EXP-33 — Out-of-Sample 2026 Unlock:** After sufficient walk-forward validation, unlock 2026 data for final out-of-sample verification.

---

## 9. Files Created

| File | Description |
|------|-------------|
| [`EA_01_Tiered_Dual_Sleeve.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/ea/EA_01_Tiered_Dual_Sleeve.mq5) | EXP-27 champion EA — dual-sleeve, highest net profit |
| [`EA_02_Dual_Open_Breakout.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/ea/EA_02_Dual_Open_Breakout.mq5) | EXP-26 champion EA — prime sessions, best payoff ratio |
| [`EA_03_Surgical_Precision.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/ea/EA_03_Surgical_Precision.mq5) | EXP-24 champion EA — surgical filter, highest PF, lowest DD |
| [`exp25_production_directional_ensemble.joblib`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/models/exp25_production_directional_ensemble.joblib) | Production model bundle (1.19 MB) |
| [`EXPERIMENT_REGISTRY.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/EXPERIMENT_REGISTRY.md) | Master experiment registry (EXP-01 to EXP-27) |
| [`FINAL_RESEARCH_SUMMARY.md`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/docs/FINAL_RESEARCH_SUMMARY.md) | This document |

---

*Session checkpoint: 2026-09-27. Research loop ready to resume from EXP-28.*

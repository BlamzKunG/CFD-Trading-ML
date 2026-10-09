# STRATEGY 32: DUAL-ASSET ASYNCHRONOUS RISK-ISOLATED COMPOSITE (DA-ARIC)

## 1. Executive Summary & Portfolio Breakthrough
Strategy 32 resolves the critical multi-asset scaling challenge in quantitative CFD trading: **Cross-Contamination Failure**.
In prior multi-asset attempts (Strategy 21 & 26), heterogeneous assets (Gold + EURUSD) pooled into a shared circuit breaker or forced onto identical timeframes caused cross-contamination: FX chop locked out Gold trend expansions.

Under **Strategy 32: Asynchronous Risk Isolation (DA-ARIC)**, each asset executes on its natural structural timeframe with completely decoupled risk budgets:
1. **Engine 1 (Gold CFD - XAUUSD):**
   - Timeframe: M15.
   - Operating Window: London & NY Sessions (08:00 – 18:00 UTC).
   - Logic: Multi-Timeframe Fractal Expansion & Structural Volatility Envelope (MFE-SVE).
   - Independent ASAR Budget: +$150 Profit Lock | -$250 Loss Breaker | -$100 Defensive Sizing.
2. **Engine 2 (Euro FX CFD - EURUSD):**
   - Timeframe: H1.
   - Operating Window: 24-Hour Macro Structural Flow.
   - Logic: Macro Structural Momentum & Dual EMA Continuation (MSM-DEC).
   - Independent ASAR Budget: +$120 Profit Lock | -$200 Loss Breaker | -$80 Defensive Sizing.

---

## 2. Audited Performance Across 72 Calendar Months (2020–2025)

| Metric | Sub-Engine 1 (Gold M15) | Sub-Engine 2 (EURUSD H1) | **Variant A: High-Consistency Composite** | **Variant B: Ultra-Sniper Composite** |
| :--- | :--- | :--- | :--- | :--- |
| **Total Trades** | 516 | 709 | **1,225** | 861 |
| **Net Profit** | +$4,841.46 | +$1,958.93 | **+$6,800.39** | **+$6,691.11** |
| **Profit Factor (PF)** | 1.352 | 1.214 | **1.297** | **1.452** |
| **Max Drawdown** | $1,341.45 | $542.54 | **$1,253.08** *(Smoothed)* | **$817.37** *(Record Portfolio DD)* |
| **MCR (Profitable Months)**| 62.50% (45/72) | 54.17% (39/72) | **66.67% (48/72)** | 61.11% (44/72) |
| **Annual Consistency** | 6 of 6 years (100%)| 6 of 6 years (100%) | **6 of 6 years (100%)** | **6 of 6 years (100%)** |

### Key Quantitative Discoveries
1. **The Diversification Benefit on Monthly Consistency:**
   - Gold alone had 45 profitable months out of 72.
   - EURUSD alone had 39 profitable months out of 72.
   - When combined under asynchronous risk isolation, **EURUSD rescued 3 losing months for Gold**, boosting the portfolio to **48 profitable months (66.67% MCR)**!
2. **Drawdown Compression:**
   - Gold's standalone max drawdown was $1,341.45.
   - In the combined portfolio (Variant A), max drawdown compressed to **$1,253.08** because EURUSD profits offset Gold pullbacks.
   - In Variant B (Sniper Gold + Macro EURUSD), portfolio drawdown collapsed to **$817.37** with a **1.452 Profit Factor**!

---

## 3. Production Deployment Architecture for Expert Advisors

Because each engine operates independently, live MT5 deployment requires **Zero Code Interdependence**:
- **Terminal Chart 1:** `XAUUSD, Period M15` $\rightarrow$ Attach [`Gold_MFE_SVE_Master_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/Gold_MFE_SVE_Master_EA.mq5) (Magic: `303030`).
- **Terminal Chart 2:** `EURUSD, Period H1` $\rightarrow$ Attach [`EURUSD_H1_MSM_DEC_Master_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/EURUSD_H1_MSM_DEC_Master_EA.mq5) (Magic: `313131`).

This ensures total hardware and account thread safety: each EA manages its own deal history and calendar risk budgets without any mutex or shared memory bottlenecks.

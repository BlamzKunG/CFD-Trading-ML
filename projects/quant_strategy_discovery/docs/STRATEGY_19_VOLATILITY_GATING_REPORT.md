# Rule-Based CFD Quantitative Research Report: Strategy 19 (Dynamic Volatility Gating & Regime Sizing)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M1, 141,567 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ❌ **REJECTED (Lagging Volatility Percentile Gate Distorts Breakout Ignition, PF 0.941)**  

---

## 1. Executive Summary & Core Hypothesis

Strategy 19 explored the institutional concept of **Dynamic Volatility Percentile Gating**:
- Compute rolling 30-day min-max percentile rank of 14-period ATR ($P_{vol}$).
- When $P_{vol} < 25\%$ (dead low-volatility regime), disable breakout trend trading to protect against false breakouts during holiday/summer chop.
- When $P_{vol} > 75\%$ or $85\%$ (extreme runaway volatility), disable mean-reversion and expand trend Take Profit targets to 5.5R.
- Combined with Monthly Profit Locks ($+\$250$ to $+\$350$) and Loss Circuit Breakers ($-\$250$ to $-\$350$).

---

## 2. 72-Month Empirical Results & Parameter Sweep

Across 108 parameter combinations swept over 72 calendar months:

| Metric | Top Candidate ($LowCut=0.25, HighCut=0.75, Lock=\$250, Breaker=\$350, RR=5.5$) | Baseline Unconstrained |
| :--- | :---: | :---: |
| **Net Profit (0.10 Lot)** | **-$1,865.60** | **-$3,492.61** |
| **Profit Factor (PF)** | **0.941** | **0.896** |
| **Win Rate (%)** | 33.29% | 29.64% |
| **Max Drawdown ($)** | $3,992.52 | $5,413.44 |
| **Total Trades** | 790 | 840 |
| **Monthly Consistency (MCR)** | **46.48% (33 of 71 months)** | **43.66% (31 of 71 months)** |

---

## 3. Quantitative Autopsy: Why Rolling ATR Percentile Gating Failed

1. **The Causality Lag of Volatility Percentiles:**
   - Volatility does not precede price movement; it is a mathematical artifact *caused* by price movement.
   - When a major new trend ignites out of a prolonged consolidation, the 30-day rolling ATR percentile is initially extremely low ($P_{vol} \approx 10\% - 20\%$).
   - By enforcing $P_{vol} \ge 25\%$, the algorithm systematically blocked entries at the exact early ignition points of mega-trends.
   - It only allowed entries AFTER the trend had already expanded for days and ATR had risen into the 30th–50th percentile, causing trades to enter late into late-stage trends.
2. **Mean-Reversion Suppression in Ranging Markets:**
   - Conversely, cutting off mean-reversion during normal volatility spikes prevented the algorithm from harvesting rapid snapbacks after news climaxes.

---

## 4. Key Discovery for Next Generation Models
- **Volatility Compression (TTM Squeeze, Keltner/Bollinger Bands) $\gg$ Rolling ATR Percentiles.**
- Energy builds during *compression* (price coils inside narrowing bands), not by waiting for trailing ATR to rise.
- This finding directly establishes the mandate for **Strategy 20: Squeeze Compression with Hierarchical Weekly Risk Budgeting**.

# Rule-Based CFD Quantitative Research Report: Strategy 18 (Asymmetric Volatility Skew & Anchored VWAP Momentum Bands)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M1, 141,567 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ❌ **REJECTED (Intraday VWAP Band Exhaustion Trap, PF 0.959, MCR 56.94%)**  

---

## 1. Executive Summary & Core Concept

Strategy 18 investigates **Daily Anchored VWAP (AVWAP)** with running volume-weighted standard deviation bands ($\pm 1.2\sigma$ to $\pm 2.8\sigma$) anchored to 00:00 UTC.

### The Institutional Quantitative Hypothesis
- VWAP represents the volume-weighted institutional average benchmark price.
- In theory:
  1. Breaks outside $\pm 1.5\sigma$ during London/NY expansion hours (08:00–18:00 UTC) with macro trend alignment (EMA200) should indicate institutional aggressive volume driving price discovery.
  2. Stretches past $\pm 2.8\sigma$ in low-volume Asian hours (21:00–06:00 UTC) should represent price exhaustion ready to mean-revert to VWAP.

---

## 2. 72-Month Empirical Results & Sweep Audit

Across 162 parameter combinations tested on 72 consecutive months (2020–2025):

| Parameter / Metric | Top Candidate ($k_1=1.5, k_2=2.8, RR=3.0$, Lock=\$350) | Baseline Unconstrained ($k_1=1.5, k_2=2.8$) |
| :--- | :---: | :---: |
| **Net Profit (0.10 Lot)** | **-$3,386.75** | **-$7,610.66** |
| **Profit Factor (PF)** | **0.959** | **0.949** |
| **Win Rate (%)** | 33.20% | 30.52% |
| **Max Drawdown ($)** | $7,616.91 | $11,925.03 |
| **Total Trades** | 2,458 | 2,225 |
| **Monthly Consistency (MCR)** | **56.94% (41 of 72 months)** | **48.61% (35 of 72 months)** |

---

## 3. Quantitative Autopsy: Why Intraday VWAP Bands Fail on CFD Gold

1. **Intraday Extension Exhaustion (Late-Arrival Trap):**
   - By the time price pushes $1.5\sigma$ away from the 00:00 UTC daily VWAP anchor, the majority of the intraday momentum impulse has already occurred.
   - Entering long at $+1.5\sigma$ forces entry into an overextended market right before intraday mean-reversion pullbacks occur, resulting in heavy stop-outs.
2. **Session Anchor Reset Artifacts:**
   - Gold frequently moves in continuous multi-day waves. Resetting VWAP at 00:00 UTC artificially distorts the anchor relative to the multi-day macro trend, leading to contradictory signals compared to continuous indicators like Supertrend or TTM Squeeze.
3. **Asymmetric Fat Tails:**
   - Fading extreme bands ($\pm 2.8\sigma$) during late hours suffered massive catastrophic tail risk during geopolitically driven Asian market openings.

---

## 4. Architectural Verdict
- **Verdict:** **REJECTED** from the Champion Template Library.
- **Key Takeaway:** Daily VWAP standard deviation bands alone cannot serve as an entry trigger for Gold CFD momentum. Structural range compression (ARC, Strategy 11) and multi-day volatility filters (Strategy 17 & 19) are significantly superior.

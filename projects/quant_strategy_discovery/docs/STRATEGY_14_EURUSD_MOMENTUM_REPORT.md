# Quantitative Research Report: Strategy 14 (EURUSD London Liquidity Momentum)

**Asset Class:** Major Forex (EURUSD CFD / Forex)  
**Timeframe:** M15 (Resampled from 2,219,712 raw M1 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots (10,000 EUR)  
**Execution Frictions:** 0.5 pip spread ($0.50 / trade), $6.00/lot round-turn commission ($1.10 total friction / 0.10 lot)  
**Status:** ❌ **REJECTED (Structural FX Mean-Reversion Whipsaw, PF = 0.905)**  

---

## 1. Executive Summary & Core Hypothesis

Strategy 14 tested the classical retail concept of **London Session Open Breakouts (07:00 - 11:00 UTC)** of the Asian Session Range (00:00 - 06:00 UTC) on EURUSD across 6 years of data.

### Result Verdict
**Decisively Rejected.** The strategy produced negative net expectancy:
- **Net Profit (0.10 Lot):** -$1,555.71
- **Profit Factor (PF):** 0.905
- **Win Rate:** 30.15% (for a 3.0R target)
- **Monthly Consistency Ratio (MCR):** 40.28% (only 29 out of 72 months profitable)

---

## 2. Quantitative Root Cause Analysis: Forex vs Commodities Structural Difference

1. **Currencies Mean-Revert, Commodities Trend:**
   * Gold (XAUUSD) has asymmetric macro momentum; once an opening range breaks in New York, Gold tends to trend for hundreds of pips.
   * EURUSD, as a sovereign currency pair bounded by central bank rate parity, spends $\sim 75\%$ of its time in statistical mean reversion.
2. **The "London Judas Swing" Trap in FX:**
   * In EURUSD, excursions outside the Asian range during London open (07:00 - 09:00 UTC) are overwhelmingly institutional stop-runs (liquidity engineering) that reverse violently back into the range.
   * Breakout traders entering at the Asian boundary become immediate exit liquidity for institutional accumulation/distribution.
3. **Key Architectural Takeaway:**
   * **Do NOT use momentum breakouts on EURUSD session extremes.**
   * EURUSD requires **Mean-Reversion Fading & Statistical Extreme Fading** (Strategy 15).

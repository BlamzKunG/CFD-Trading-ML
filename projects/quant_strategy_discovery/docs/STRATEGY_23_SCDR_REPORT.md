# Rule-Based CFD Quantitative Research Report: Strategy 23 (Squeeze-Compressed Dual-Regime Ensemble)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M1, 141,567 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ❌ **REJECTED (Pre-London Squeeze Misalignment, PF 0.918)**  

---

## 1. Executive Summary & Core Concept

Strategy 23 attempted to upgrade Strategy 17's London/NY Trend Breakout by requiring that every breakout be preceded by a **Volatility Compression Squeeze (Bollinger Bands inside Keltner Channel)** within the active 08:00 - 18:00 UTC window.

### Quantitative Results

Across 48 parameter combinations tested over 72 calendar months:
- **Net Profit (0.10 Lot):** -$3,886.90
- **Profit Factor (PF):** 0.918
- **Win Rate (%):** 44.44%
- **Max Drawdown ($):** $8,282.32
- **Monthly Consistency Ratio (MCR):** 58.33% (42 of 72 months)

---

## 2. Quantitative Autopsy: Why Restricting Squeezes to Active Hours Failed

1. **The Pre-London Expansion Timing Mismatch:**
   - In Gold CFD microstructure, range compression squeezes typically form during the quiet late Asian session (02:00 - 06:00 UTC).
   - When the London session opens at 07:00–08:00 UTC, the initial volatility ignition expansion often fires right at 07:00 or 07:30 UTC.
   - Enforcing that the squeeze must fire strictly *within* 08:00 - 18:00 UTC meant that at 08:00 UTC, the squeeze had already fired. The state was no longer registered as a fresh squeeze trigger.
   - Consequently, the strategy filtered out the genuine high-momentum opening impulses and only entered secondary, late-session expansions that frequently reversed.

---

## 3. Key Takeaway & Architecture Direction
- Dual-regime session momentum relies on **Structural Session Timing** (such as London/NY opening momentum with trailing stops, as in Strategy 17) rather than rigid intra-session squeeze gating.
- This finding led directly to **Strategy 24: Adaptive Sizing Asymmetric Recovery (ASAR)**, focusing on position sizing dynamics and loss mitigation on proven setups.

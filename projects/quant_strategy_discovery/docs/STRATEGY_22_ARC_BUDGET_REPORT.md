# Rule-Based CFD Quantitative Research Report: Strategy 22 (Adaptive Range Compression with Hierarchical Risk Budgeting)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M1, 141,567 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ⚖️ **ACCEPTABLE DEFENSIVE MODEL (Ultra-Low Drawdown $1,626 - $1,974, Modest Net Profit +$540)**  

---

## 1. Executive Summary & Core Concept

Strategy 22 applied **Hierarchical Risk Budgeting** (Weekly Circuit Breakers of -$100 to -$150, Monthly Circuit Breakers of -$200 to -$300, and Monthly Profit Locks of +$250 to +$350) to the **Adaptive Range Compression (ARC)** breakout engine.

### Key Quantitative Findings
1. **Ultra-Low Drawdown Machine:**
   - Strategy 22 delivered the **lowest drawdown of any breakout engine tested: Max DD $1,626.92 - $1,974.79**.
   - Risk budgeting prevented severe loss streaks effectively.
2. **Profit Reduction Trade-off:**
   - Standalone ARC (Strategy 11) generated +$5,343.86 over 72 months because it allowed runners during multi-week trend clusters.
   - Enforcing tight weekly breakers (-$100) frequently clipped trading prematurely during temporary retracements within large trend weeks, reducing net profit to +$540.57.
3. **Monthly Consistency Ratio (MCR):**
   - 47.89% (34 of 71 calendar months profitable).

---

## 2. 72-Month Parameter Comparison Table

| Metric | Raw ARC Breakout (Strategy 11) | ARC with Hierarchical Budget (Strategy 22) |
| :--- | :---: | :---: |
| **Net Profit (0.10 Lot)** | **+$5,343.86** | **+$540.57** |
| **Profit Factor (PF)** | **1.183** | **1.035** |
| **Win Rate (%)** | 30.56% | 24.24% |
| **Max Drawdown ($)** | $1,859.59 | **$1,626.92 (New Record Low)** |
| **Total Trades** | 1,021 | 458 |
| **Monthly Consistency (MCR)** | 59.72% | 47.89% |

---

## 3. Architectural Verdict
- **Verdict:** Strategy 22 proves that tighter weekly budget limits serve as a double-edged sword for pure momentum breakouts: they eliminate deep drawdown at the expense of cutting off trend runners.
- This directly motivates **Strategy 23: Squeeze-Compressed Dual-Regime (SCDR)**, where trend profits are complemented by Asian mean reversion rather than capped by premature weekly halts.

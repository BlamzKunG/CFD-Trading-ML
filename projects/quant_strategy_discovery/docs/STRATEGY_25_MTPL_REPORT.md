# Rule-Based CFD Quantitative Research Report: Strategy 25 (Multi-Tier Trailing Profit Lock - MTPL)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M1, 141,567 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Base Lot Size:** 0.10 lots  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ❌ **REJECTED (The "Premature Break-Even Choke" Trap, PF Collapsed from 1.249 to 0.961)**  

---

## 1. Executive Summary & Core Hypothesis

Strategy 25 investigated whether moving the Stop Loss to **Break-Even (BE) at $+1.5R$** and locking $+1.2R$ profit at $+2.5R$ would protect winning months from late-stage reversals.

### The Catastrophic Collapse
In Strategy 24 (Fixed Stop with ASAR Dynamic Sizing):
- Net Profit: **+$4,890.18 to +$6,210.97**
- Profit Factor: **1.249**
- Max Drawdown: **$1,515.28**

In Strategy 25 (With $+1.5R$ Break-Even & Trailing):
- Net Profit: **-$888.26 to -$8,872.21**
- Profit Factor: **0.961 down to 0.754**
- Win Rate: 32.49%
- MCR: 44.44% down to 19.44%

---

## 2. Quantitative Autopsy: Why Break-Even Stops Destroy Trend Alpha

1. **The Intraday Retest Choke:**
   - Gold price discovery is characterized by violent impulse-pullback structures.
   - When an impulse reaches $+1.5R$, it almost always performs an intraday retest of the original breakout level (the entry price).
   - Moving the stop to Break-Even at $+1.5R$ causes the retest to stop out the position at $\approx \$0.00$.
   - Immediately after triggering the Break-Even stop, the macro trend resumes and explodes to $+4.0R$—but the algorithm is no longer in the trade.
2. **Asymmetric Payout Destruction:**
   - The algorithm still absorbs the full $-1.0R$ loss on bad trades.
   - But it chokes off the $+4.0R$ mega-winners, converting them into $+0.0R$ scratch trades.
   - This single mechanism completely eviscerates the positive expectancy of the system.

---

## 3. Institutional Policy Ruling
- **Never enforce premature Break-Even on Gold trend breakouts.**
- A high-expectancy trend breakout requires full breathing room ($2.5 \cdot \text{ATR}$ stop) to endure natural liquidity pullbacks before reaching full multi-R targets.
- **Strategy 24 (ASAR Dual-Regime)** remains our unchallenged champion for execution efficiency.

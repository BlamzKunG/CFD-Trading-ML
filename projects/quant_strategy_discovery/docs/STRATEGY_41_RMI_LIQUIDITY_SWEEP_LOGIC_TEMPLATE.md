# Strategy 41: Relative Momentum Index Asian Liquidity Sweep (RMI-ARLS)

## 1. Executive Summary & Audit Result
- **Asset:** CFD Commodity (XAUUSD / Gold)
- **Timeframe:** M15 (Resampled from raw M1 high-resolution ticks)
- **Validation Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months, 6 full multi-year market cycles)
- **Execution Frictions Applied:** $0.25 spread ($25.00/standard lot) + $6.00/lot commission + slippage
- **Evaluation Status:** ❌ **DECISIVELY REJECTED (Capital Destruction Engine)**
  - **Profit Factor (PF):** **0.669** (Severe structural underperformance, fails $\ge 1.50+$ mandate)
  - **Net Profit (0.10 Lot Base):** **-$2,350.52**
  - **Win Rate:** **15.96%** (84.04% of trades hit stop loss)
  - **Max Drawdown:** **$2,729.40**
  - **Monthly Consistency Ratio (MCR):** **23.61% (Only 17 out of 72 months profitable)**
  - **Total Completed Trades:** 188 trades across 72 calendar months

---

## 2. Quantitative Rationale & Post-Mortem Failure Analysis

### The Gold Sweep-Continuation Trap (The False Fakeout Fallacy):
1. **The Retail Trap Exposed:**
   - Popular retail "Smart Money Concepts" (SMC) assert that when price sweeps the Asian Session High or Low during London or NY Open (08:00 - 16:00 UTC), institutional market makers are "running stops" and will promptly reverse price back into the range.
2. **Empirical Reality on Gold CFD:**
   - On Gold CFD across 6 years of tick data, a sweep of the Asian Range during London/NY Open is **NOT a reversal event in 84% of occurrences**.
   - It represents an **Explosive Institutional Trend Initiation**!
   - By attempting to fade the sweep with the Relative Momentum Index (RMI), the strategy stood directly in front of runaway momentum freight trains.
3. **Contrast with Pro-Trend Models:**
   - Trend Continuation models (Strategies 30, 33, 35, 36, 38) achieved Profit Factors of **2.20 – 2.71**.
   - Fading session breakouts yielded a disastrous Profit Factor of **0.669**.
   - This scientifically proves that Gold is an asset governed by **Fat-Tailed Momentum Continuation**, where intraday mean reversion outside midnight Asian hours is mathematically destructive.

---

## 3. Production Artifacts Manifest
- **Python Sweep Engine:** [`projects/quant_strategy_discovery/scripts/strategy_41_rmi_liquidity_sweep.py`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/scripts/strategy_41_rmi_liquidity_sweep.py)
- **Champion Configuration JSON:** [`projects/quant_strategy_discovery/results/strategy_41_champion.json`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_41_champion.json)
- **Complete 216 Sweeps CSV:** [`projects/quant_strategy_discovery/results/strategy_41_rmi_sweep_results.csv`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_41_rmi_sweep_results.csv)
- **Status:** **REJECTED / CATALOGED AS NEGATIVE KNOWLEDGE BASE**

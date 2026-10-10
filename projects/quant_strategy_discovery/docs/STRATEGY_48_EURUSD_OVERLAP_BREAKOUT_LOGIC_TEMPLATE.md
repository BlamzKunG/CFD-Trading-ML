# Strategy 48: EURUSD London/NY Overlap Range Expansion (FX-LOV) — REJECTION AUDIT

## 1. Executive Summary & Strategy Verdict
- **Strategy ID:** STRATEGY_48
- **Identifier:** FX-LOV (London/NY Overlap Volatility Breakout)
- **Asset Class:** EURUSD CFD (Forex)
- **Execution Timeframe:** M15 (Resampled from raw M1 data)
- **Audit Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Status:** ❌ **DECISIVELY REJECTED**
- **Performance:**
  - **Profit Factor (PF):** **0.844** ❌ *(Target: $\ge 1.50$)*
  - **Net Profit:** **-$1,459.43** (0.10 Lot sizing)
  - **Max Drawdown:** **$1,899.94**
  - **Total Trades:** 1,134 trades
  - **Win Rate:** 34.13%
  - **Monthly Consistency Ratio (MCR):** 30.56% (22 of 72 profitable months)
  - **RoMaD:** -0.77x

---

## 2. Quantitative Rationale & Rejection Diagnosis
1. **The Core Inefficiency: Gold vs. Forex Microstructure Divergence:**
   - In **Strategy 42 (Gold M15 Asian Breakout)**, trading in the direction of the range expansion yielded **PF 1.817** and **+$6,065.16 net profit** because Gold possesses heavy fat tails and strong momentum persistence during liquidity runs.
   - In contrast, on **EURUSD M15**, session range breaks during the London/NY Overlap (12:00–16:00 UTC) fail 66% of the time. Market makers sweep pre-market highs/lows for liquidity and rapidly revert back toward equilibrium/VWAP.
2. **Transaction Friction Suffocation:**
   - EURUSD average M15 ATR is only 10–15 pips.
   - Broker friction (0.6 pip spread + 0.6 pip commission = 1.2 pips roundturn) consumes ~8–12% of the entire bar's excursion.
   - When combined with frequent false breakout whipsaws, capital depletion is guaranteed.
3. **Negative Knowledge Principle (Constitution V5.0 Section 7):**
   - **Empirical Law:** *Never trade intraday directional breakouts on EURUSD M15.*
   - Forex requires either **macro multi-day trend following on H1/H4 (like Strategy 31 DEC)** or **disciplined mean-reversion at session extremes (fading sweeps)**.

---

## 3. Parametric Sweep Summary Across 144 Configurations

| Buffer ATR | Take Profit | Stop Loss | Profit Lock | Total Trades | Win Rate (%) | Net Profit ($) | Profit Factor | Max DD ($) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0.3 | 3.0R | 1.5R | $200 | 1,134 | 34.13% | -$1,459.43 | 0.844 | $1,899.94 |
| 0.3 | 3.0R | 1.5R | $150 | 1,130 | 33.98% | -$1,541.47 | 0.835 | $1,930.28 |
| 0.2 | 3.0R | 1.5R | $200 | 1,167 | 34.02% | -$1,582.21 | 0.834 | $2,005.70 |
| 0.2 | 2.0R | 1.5R | $100 | 1,161 | 41.95% | -$1,481.69 | 0.829 | $1,985.46 |
| 0.3 | 3.0R | 1.2R | $150 | 1,130 | 29.73% | -$1,446.86 | 0.827 | $1,835.96 |
| 0.4 | 3.5R | 1.5R | $100 | 920 | 28.59% | -$1,920.40 | 0.792 | $2,140.10 |

*Every single configuration produced a negative Profit Factor ($0.75 - 0.84$). Strategy 48 is archived in the negative knowledge registry to permanently prevent redundant research.*

# STRATEGY 01: DONCHIAN / TURTLE BREAKOUT MASS PARAMETER SWEEP REPORT

**Author:** Quantitative Trading Policy Discovery Engine  
**Target Asset:** XAUUSD (Gold CFD)  
**Timeframe:** M15 (Derived from 2.11M ticks / M1 bars)  
**Backtest Period:** 2020-01-02 to 2025-12-30 (5 Full Years)  
**Execution Frictions:** Spread = $0.25 ($2.50 / 0.1 lot), Commission = $6.00 / standard lot, Realistic slippage on gaps  
**Combinations Evaluated:** 1,728 parameter sets  
**Evaluation Compute Time:** 4.71 seconds (367.2 parameter sets / second via Numba machine-code JIT)

---

## 1. Strategy Overview & Theoretical Thesis

The **Donchian Breakout System** (popularized by Richard Dennis and William Eckhardt's Turtle Traders in the 1980s) is one of the most famous trend-following systems in financial history.

### Trading Logic:
- **Long Entry:** Market makes a new $N$-bar high (`Close[t] > Highest_High[t-1, N]`). Enter on Open of next bar (`Open[t+1]`).
- **Short Entry:** Market makes a new $N$-bar low (`Close[t] < Lowest_Low[t-1, N]`). Enter on Open of next bar (`Open[t+1]`).
- **Trend Filter (Optional):** EMA 100 or EMA 200 filter (Longs only above EMA, Shorts only below EMA).
- **Exit Logic:**
  1. **Donchian Exit Channel:** Exit longs on breakdown of shorter $M$-bar low (`Lowest_Low[t-1, M]`), exit shorts on breakout of $M$-bar high (`Highest_High[t-1, M]`).
  2. **Take Profit (Optional):** Fixed ATR multiple ($3.0\times$ or $5.0\times$ ATR).
- **Risk Preservation:** Volatility-adjusted Stop Loss ($1.5\times, 2.0\times, 2.5\times, 3.0\times$ ATR(14)).
- **Session Filter:** All-day (24h) vs Prime Liquidity Hours (London + New York, 07:00 - 20:00 UTC).

---

## 2. Mass Parameter Sweep Grid (1,728 Combinations)

| Parameter | Tested Grid Values | Description |
| :--- | :--- | :--- |
| **`entry_lookback`** | `[15, 20, 30, 45, 60, 90]` bars | 3.75 hrs to 22.5 hrs lookback channel |
| **`exit_lookback`** | `[5, 10, 15, 20]` bars | 1.25 hrs to 5.0 hrs trailing exit channel |
| **`sl_atr_mult`** | `[1.5, 2.0, 2.5, 3.0]` | Volatility Stop Loss buffer |
| **`tp_atr_mult`** | `[0.0 (Trailing), 3.0, 5.0]` | Take Profit multiple |
| **`ema_filter`** | `[0 (None), 100, 200]` | Higher-timeframe trend alignment |
| **`session_mode`** | `[24h, London_NY (07-20 UTC)]` | Session liquidity window |

---

## 3. Global Quantitative Findings & Parameter Distribution

```
Total Parameter Sets Evaluated: 1,728
Profitable Combinations (PF > 1.0): 0 (0.00%)
Combinations with PF >= 1.10: 0 (0.00%)
Maximum Profit Factor Achieved: 0.9816
Average Profit Factor: 0.8541
Maximum Net PnL: -$1,662.32 (0.10 lot)
Minimum Net PnL (Worst Set): -$55,618.62 (0.10 lot)
Average Holding Period: 16.8 bars (4.2 hours)
```

### Empirical Discovery: Why Naive Donchian Breakout Fails on Gold (XAUUSD)
1. **Aggressive Mean Reversion & Liquidity Sweeps:** Unlike commodities in the 1980s that exhibited persistent unidirectional trends, intraday Gold CFD (XAUUSD) is heavily dominated by algorithmic institutional liquidity sweeps ("Judas swings"). When price reaches a 20- or 60-bar high, institutional sellers often use the breakout liquidity to dump supply, causing immediate reversal and trapping retail breakout traders.
2. **Spread & Slippage Decay:** With 1,700 to 2,500 trades over 5 years, paying $3.10 friction per trade creates over $6,000+ in pure transaction drag per 0.10 lot. A strategy must have substantial edge to overcome this friction.
3. **Session Filtering Impact:** Confining trading to London and New York sessions significantly reduced losses (Max Net PnL improved from -$3,078 to -$1,662), confirming that Asian session breakout attempts on Gold are almost purely noise.

---

## 4. Top Champion Parameter Set (Best of 1,728 Sets)

```json
{
  "entry_lookback": 90,
  "exit_lookback": 20,
  "sl_atr_mult": 3.0,
  "tp_atr_mult": 3.0,
  "ema_filter": 200,
  "session_mode": "London_NY",
  "total_trades": 2095,
  "net_profit": -1662.32,
  "profit_factor": 0.9816,
  "win_rate": 45.63,
  "max_drawdown": 5587.33,
  "sharpe": -0.1534
}
```

### Yearly Consistency Breakdown for Champion:
- **2020:** 335 trades | Net: -$597.07 | PF: 0.96 | Win Rate: 46.0% | Max DD: $1,980.42
- **2021:** 338 trades | Net: -$1,855.78 | PF: 0.84 | Win Rate: 42.6% | Max DD: $2,817.75
- **2022:** 362 trades | Net: -$193.98 | PF: 0.99 | Win Rate: 45.0% | Max DD: $1,298.19
- **2023:** 357 trades | Net: +$560.96 | PF: 1.05 | Win Rate: 47.3% | Max DD: $1,660.35
- **2024:** 354 trades | Net: +$172.72 | PF: 1.01 | Win Rate: 46.9% | Max DD: $1,845.00
- **2025:** 338 trades | Net: -$67.83 | PF: 1.00 | Win Rate: 45.0% | Max DD: $2,926.48

*Note: In strong multi-month trending regimes (2023 and 2024 Gold bull runs), Donchian achieved positive net profit ($PF \approx 1.01 - 1.05$). However, during consolidating or choppy years (2021), it suffered substantial decay.*

---

## 5. Strategic Verdict & Architecture Recommendation

> [!WARNING]
> **VERDICT: REJECT NAIVE DONCHIAN BREAKOUT AS STANDALONE EA STRATEGY.**  
> Out of 1,728 parameter combinations, 0% achieved a viable commercial Profit Factor ($PF \ge 1.30$).  
> Naive breakout triggers without structural confirmation (such as Volatility Squeeze / Keltner compression or Liquidity Sweeps) are unviable on XAUUSD.

### Actionable Takeaway for Next Strategies:
- Moving immediately to **Strategy 02: Opening Range Breakout (ORB / London Breakout)**, which confines breakout triggers strictly to session open energy bursts rather than arbitrary rolling rolling channels.

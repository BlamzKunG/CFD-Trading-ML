# STRATEGY 07: BOLLINGER BANDS EXTREME REVERSION (ASIAN SCALPER) REPORT

**Author:** Quantitative Trading Policy Discovery Engine  
**Target Asset:** XAUUSD (Gold CFD)  
**Timeframe:** M15 (Resampled from 2.11M ticks / M1 bars, 141,567 bars)  
**Backtest Period:** 2020-01-02 to 2025-12-30 (5 Full Years)  
**Execution Frictions:** Spread = $0.25 ($2.50 / 0.1 lot), Commission = $6.00 / standard lot, Realistic slippage on gaps  
**Combinations Evaluated:** 144 parameter sets  
**Evaluation Compute Time:** 78.1 seconds

---

## 1. Strategy Overview & Theoretical Thesis

While retail trend-followers frequently buy breakouts during the Asian session, market makers know that overnight liquidity in Gold is predominantly mean-reverting.

### Core Mathematical Mechanics:
- **Statistical Extremes (Bollinger Bands):**
  - $Basis = SMA_{20}(Close)$
  - $Upper_{BB} = SMA_{20} + Multiplier \times \sigma_{20}$
  - $Lower_{BB} = SMA_{20} - Multiplier \times \sigma_{20}$ where $Multiplier \in [2.0, 2.3, 2.6, 3.0]$.
- **Rejection Confirmation:**
  - Long: Bar Low pierces below $Lower_{BB}$, but candle closes back bullish inside ($Close > Open$ and $Close > Lower_{BB}$). Execution at `Open[t+1]`.
  - Short: Bar High pierces above $Upper_{BB}$, but candle closes back bearish inside ($Close < Open$ and $Close < Upper_{BB}$). Execution at `Open[t+1]`.
- **Session Windowing:**
  - Quiet Asian Session (21:00 to 06:00 UTC) vs 24h.

---

## 2. Mass Parameter Sweep Grid (144 Combinations)

| Parameter | Tested Grid Values | Description |
| :--- | :--- | :--- |
| **`bb_multiplier`** | `[2.0x, 2.3x, 2.6x, 3.0x]` StdDev | Extreme excursion envelope width |
| **`session_mode`** | `[24h, Quiet_Asian (21:00 - 06:00 UTC)]` | Session liquidity window |
| **`exit_mode`** | `[Midline_Touch (20 SMA), Fixed_Risk_Reward]` | Reversion target method |
| **`sl_atr_mult`** | `[1.5x, 2.0x, 2.5x]` | Volatility Stop Loss buffer |
| **`tp_rr_mult`** | `[1.5R, 2.0R, 3.0R]` | Asymmetric Risk:Reward target |

---

## 3. Global Quantitative Findings & Parameter Distribution

```
Total Parameter Sets Evaluated: 144
Profitable Combinations (PF > 1.0): 36 (25.0%)
All Profitable Combinations Confined To: Quiet_Asian Session (100% of 24h sets failed)
Maximum Profit Factor Achieved: 1.1042
Maximum Net PnL: +$2,372.54 (on 0.10 lot)
Average Holding Period: 18.6 bars (4.7 hours)
```

### Critical Empirical Insight:
- **24-Hour Mean Reversion is Suicidal on Gold:** In the London and New York sessions, standard deviation extremes are trend inception signals rather than mean reversion signals. Trying to fade a 2.0-3.0 StdDev move during NY open results in catastrophic trend steamrolling.
- **Asian Session Containment:** Confining reversion to 21:00 - 06:00 UTC with an extreme $3.0\sigma$ threshold produced a profitable edge ($PF = 1.10$, Win Rate 35.2%).

---

## 4. Top Champion Parameter Set (Best of 144 Sets)

```json
{
  "bb_multiplier": 3.0,
  "session_mode": "Quiet_Asian",
  "exit_mode": "2.0R_Fixed",
  "sl_atr_mult": 2.0,
  "tp_rr_mult": 2.0,
  "total_trades": 506,
  "net_profit": 1618.60,
  "profit_factor": 1.10,
  "win_rate": 35.18,
  "max_drawdown": 2025.88,
  "romad": 0.80,
  "sharpe": 0.35
}
```

---

## 5. Comparative Strategic Leaderboard (Strategies 1 - 7)

| Rank | Strategy Name | 5-Yr Net PnL | Profit Factor | Status |
| :---: | :--- | :---: | :---: | :---: |
| 🥇 | **Strategy 03: Supertrend Volatility Trailing** | **+$29,509.61** | **1.41 (Peak 1.52)** | **TIER 1 CHAMPION** |
| 🥈 | **Strategy 06: Zero-Lag MACD Trend Inflection** | **+$21,802.69** | **1.17 (Peak 1.24)** | **TIER 1 SWING ENGINE** |
| 🥉 | **Strategy 04: TTM Squeeze Volatility Expansion** | **+$13,095.97** | **1.20 (Peak 1.58)** | **TIER 1 EXPANSION** |
| 4 | **Strategy 05: Triple Screen MTF Pullback** | **+$8,888.78** | **1.11 (Peak 1.13)** | **VIABLE COMPONENT** |
| 5 | **Strategy 02: NY Opening Range Breakout (ORB)** | **+$8,245.93** | **1.13 (Peak 1.59)** | **VIABLE COMPONENT** |
| 6 | **Strategy 07: Bollinger Extreme Reversion (Asian)** | **+$1,618.60** | **1.10** | **SESSION-SPECIFIC SCALPER** |
| 7 | **Strategy 01: Donchian / Turtle Breakout** | **-$1,662.32** | **0.98** | **REJECTED** |

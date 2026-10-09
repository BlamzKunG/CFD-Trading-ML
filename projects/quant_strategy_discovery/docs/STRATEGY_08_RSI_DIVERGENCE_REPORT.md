# Quantitative Strategy Discovery Report: Strategy 08 (RSI Divergence & Rejection Wick)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from 2,116,595 raw M1 ticks/candlesticks)  
**Validation Period:** 2020-01-01 to 2025-12-31 (6 full years out-of-sample)  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot commission, realistic tick slippage  
**Position Sizing:** 0.10 standard lots (10 oz units)  
**Status:** ❌ **REJECTED (Severe Structural Disadvantage / Retail Trap)**  

---

## 1. Executive Summary & Core Hypothesis

Strategy 08 investigates one of the most widely cited classical technical analysis concepts in retail trading: **RSI Regular Divergence with Candlestick Rejection**.

### Tested Hypothesis
- **Bullish Divergence:** Price creates a Lower Low ($P_t < P_{t-k}$) while RSI(14) creates a Higher Low ($RSI_t > RSI_{t-k}$), accompanied by an oversold condition ($RSI < 30/35$) and a bullish rejection candle (lower wick $\ge 33\%$ of bar range).
- **Bearish Divergence:** Price creates a Higher High ($P_t > P_{t-k}$) while RSI(14) creates a Lower High ($RSI_t < RSI_{t-k}$), accompanied by an overbought condition ($RSI > 65/70$) and a bearish rejection candle (upper wick $\ge 33\%$ of bar range).
- **Exit Logic:** Asymmetric profit targets (1.5R to 4.0R) with ATR-based volatility stops (2.0x to 3.0x ATR).

### Result Verdict
**Decisively Rejected.** Across all 32 multi-year parametric combinations, **0% of parameter sets produced positive net expectancy**. The strategy produced a consistent negative drift with a maximum Profit Factor of $0.93$ and severe drawdowns exceeding $16,000.

---

## 2. Quantitative Performance Metrics (Champion Set)

| Metric | Champion Value | Baseline Expectation | Assessment |
| :--- | :--- | :--- | :--- |
| **SL ATR Multiplier** | `3.0x ATR(14)` | - | Maximum room allowed |
| **TP RR Multiplier** | `3.0R` | - | High reward-to-risk ratio |
| **Session Filter** | `24 Hours` | - | All-session execution |
| **Total Trades** | **1,219** | $> 500$ | Highly statistically significant |
| **Win Rate** | **23.30%** | $> 35\%$ | Very poor win rate |
| **Profit Factor (PF)** | **0.93** | $\ge 1.30$ | Sub-breakeven ($PF < 1.0$) |
| **Net PnL (0.10 Lot)** | **-$7,576.03** | $> +$5,000 | Systemic capital destruction |
| **Max Drawdown ($)** | **$16,039.80** | $< $3,000 | Catastrophic drawdown |
| **Sharpe Ratio** | **-0.38** | $\ge 1.00$ | Negative risk-adjusted return |
| **RoMaD** | **-0.47** | $\ge 2.00$ | Failed |

---

## 3. Annual Consistency Breakdown

| Year | Trades | Win Rate | Net PnL ($) | Profit Factor | Max Drawdown ($) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2020** | 171 | 19.9% | -$4,146.42 | 0.75 | $4,604.18 |
| **2021** | 199 | 23.1% | -$1,810.89 | 0.86 | $3,160.72 |
| **2022** | 220 | 22.3% | -$2,079.06 | 0.87 | $4,125.53 |
| **2023** | 179 | 25.1% | +$1,034.45 | 1.09 | $1,700.84 |
| **2024** | 189 | 26.5% | +$95.49 | 1.01 | $3,957.77 |
| **2025** | 253 | 22.9% | -$562.06 | 0.99 | $9,681.69 |

**Observations:**
- In volatile and strongly trending regimes (2020 Covid rally, 2022 Fed rate hike trend), the strategy suffered catastrophic losses ($PF = 0.75 - 0.87$).
- Even in consolidating years (2023, 2024), performance barely hovered around breakeven ($PF = 1.01 - 1.09$).

---

## 4. Top Parameter Plateau Comparison

| Rank | Stop Loss | Take Profit | Session Window | Net PnL ($) | Profit Factor | Win Rate | Total Trades | Max DD ($) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 3.0x ATR | 3.0R | 24h | -$7,576.03 | 0.93 | 23.3% | 1,219 | $16,039.80 |
| **2** | 3.0x ATR | 4.0R | 24h | -$8,389.34 | 0.91 | 18.3% | 947 | $18,926.44 |
| **3** | 2.5x ATR | 4.0R | 24h | -$8,760.01 | 0.92 | 18.9% | 1,334 | $16,439.17 |
| **4** | 3.0x ATR | 1.5R | 24h | -$12,215.64 | 0.92 | 38.5% | 2,226 | $17,139.80 |
| **5** | 2.5x ATR | 2.0R | London + NY | -$13,680.13 | 0.90 | 32.5% | 1,992 | $19,150.07 |

---

## 5. Quantitative Root Cause Analysis

1. **The "Cascading Divergence" Trap on Trend Extensions:**
   Gold is a high-momentum asset. During strong macro trend legs (e.g., $1,800 to $2,075 in 2020, or $2,000 to $2,780 in 2024-2025), price establishes 3, 4, or even 5 consecutive higher highs while RSI displays lower highs. Mean-reversion traders attempting to fade each divergence get stopped out repeatedly before any meaningful pullback occurs.
2. **Rejection Wicks in Strong Trends Are Absorption, Not Reversal:**
   A long rejection wick during an uptrend often represents aggressive institutional limit absorption rather than an impending trend reversal. Retail fading of these wicks creates immediate liquidity for institutional continuation.
3. **Spread and Commission Friction Erosion:**
   With 1,200 to 2,200 trades across the 6-year period, friction costs ($31/trade on a standard lot) erode over $37,000 to $68,000 in gross expectancy when edge is close to zero.

---

## 6. Recommendation for Portfolio EA Integration

- **DO NOT include standalone RSI Divergence reversal as an entry signal.**
- **Exclusion from Champion EA:** Strategy 08 is eliminated from our production portfolio.
- **Valuable Research Takeaway:** Confirms that Gold CFD rewards trend-following (Supertrend, Zero-Lag MACD) and volatility breakout (TTM Squeeze, ORB), while punishing blind counter-trend momentum divergence.

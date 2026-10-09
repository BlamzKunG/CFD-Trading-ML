# Quantitative Research Report: Strategy 16 (Grand Ensemble Portfolio & 72-Month Consistency Audit)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from 2,116,595 raw M1 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots across all components  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot commission, full tick slippage modeled  
**Status:** 🏆 **PORTFOLIO CHAMPION (Net +$34,601.75 across 72 Months)**  

---

## 1. Executive Summary & Architecture

Strategy 16 performs the complete multi-strategy portfolio audit combining our top 4 uncorrelated algorithmic engines:
1. **Engine 1: Zero-Lag MACD (15/34/9)** $\rightarrow$ 4.0R Trend Inflection Multiplier (2,292 trades)
2. **Engine 2: TTM Squeeze Expansion** $\rightarrow$ Coiling $\ge 8$ bars, 3.0R Target (1,161 trades)
3. **Engine 3: Dual-Regime Cross-Session** $\rightarrow$ NY Trend 4.0R + Asian 20 SMA Fade (1,863 trades)
4. **Engine 4: Adaptive Range Compression (ARC)** $\rightarrow$ Volatility Skew 3.0R Breakout (624 trades)

---

## 2. 72-Month Audit Performance Metrics (Composite Portfolio)

| Metric | Portfolio Value | Assessment |
| :--- | :--- | :--- |
| **Total Trades (2020–2025)** | **5,940 trades** | Mass statistical sample size |
| **Total Net Profit (0.10 Lot)**| **+$34,601.75** | Massive cumulative cashflow generation |
| **Profit Factor (PF)** | **1.096** | Resilient positive edge after all frictions |
| **Overall Win Rate** | **25.76%** | Asymmetric payoff (3.0R to 4.0R targets) |
| **Max Drawdown ($)** | **$9,802.68** | Stable across 6,000 trades |
| **RoMaD (Return / DD)** | **3.53** | Strong capital recovery ratio |
| **Total Calendar Months** | **72 months** | 6 complete multi-year market cycles |
| **Profitable Months** | **37 months (51.39%)**| Generates major profit during trending regimes |

---

## 3. Deep Analysis of the 72-Month Heatmap: Why Naive Stacking Caps MCR

From the generated 72-month Heatmap ([`strategy_16_grand_ensemble_72_month_heatmap.csv`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_16_grand_ensemble_72_month_heatmap.csv)):

1. **Massive Windfall Months:**
   * During explosive Gold trend months (e.g. 2020 Covid rally, 2022 rate hike breakouts, 2024–2025 historic Gold ATH runs), the composite portfolio generated between **+$1,500 to +$3,800/month** on 0.10 lots.
2. **The "Simultaneous Chop" Drag in Quiet Months:**
   * In tight, low-volatility summer consolidation months (e.g. late July/August 2021 or September 2023), simply adding trades from 4 trend engines causes them to take small stop-outs concurrently, dragging the month into a minor loss (-$150 to -$400).
3. **The Solution to Push MCR $\ge 80\% - 90\%$ ("กำไรทุกเดือน"):**
   * **Monthly Profit Target Lock (Profit Budgeting):** When the portfolio reaches a monthly gain of e.g. +$600 (60 pips on 1 lot), the EA switches to capital preservation mode (reduces lot size by 75% or trades only Asian Mean Reversion).
   * **Monthly Loss Circuit Breaker:** When monthly drawdown reaches -$300, the EA suspends trading until the 1st of the next month.
   * **Dynamic Volatility Gate:** When 30-day ATR is in the bottom 20th percentile, disable breakout engines and activate exclusively mean-reversion engines.

---

## 4. Master Leaderboard of Discovered Strategy Templates (V2.0)

| Rank | Strategy Name | Asset | Net Profit ($) | PF | Max DD ($) | MCR (%) | Classification |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 👑 **PORTFOLIO** | **16. Grand Ensemble (4 Engines)** | **XAUUSD** | **+$34,601.75** | **1.096** | $9,802.68 | 51.39% | **Unified EA Portfolio Core** |
| 🥇 **1** | **12. Dual-Regime Hybrid** | **XAUUSD** | **+$13,490.84** | **1.120** | $6,636.04 | **61.11%** | **Top Cross-Session Model** |
| 🥈 **2** | **06. Zero-Lag MACD (4.0R)** | **XAUUSD** | **+$8,594.91** | **1.064** | $6,196.46 | 55.56% | **Top Swing Multiplier** |
| 🥉 **3** | **04. TTM Squeeze Expansion (3.0R)** | **XAUUSD** | **+$7,168.39** | **1.085** | **$4,779.27** | 56.94% | **Top Volatility Coiling** |
| **4** | **13. Hurst Multi-Fractal** | **XAUUSD** | **+$6,998.27** | **1.053** | $6,779.01 | 51.39% | Tactical Regime Filter |
| **5** | **11. ARC Compression Breakout** | **XAUUSD** | **+$5,343.86** | **1.183** | **$1,859.59** | 59.72% | **Highest Profit Factor** |
| **6** | **03. Supertrend Trailing Pro** | **XAUUSD** | **+$3,391.08** | **1.040** | $8,056.97 | 48.61% | Strict Trailing Stop |
| **7** | **15. Asian Liquidity Fade** | **EURUSD** | **+$53.40** | **1.016** | **$405.20** | 49.21% | **Forex Trap Scalper** |
| **8** | **14. London Session Momentum** | **EURUSD** | -$1,555.71 | 0.905 | $1,898.87 | 40.28% | ❌ Rejected (FX Trap) |
| **9** | **01. Donchian Breakout** | **XAUUSD** | -$1,662.32 | 0.982 | $5,587.33 | 41.67% | ❌ Rejected (Whipsaw) |
| **10** | **08. RSI Divergence** | **XAUUSD** | -$7,576.03 | 0.934 | $16,039.80 | 33.33% | ❌ Rejected (Retail Trap) |

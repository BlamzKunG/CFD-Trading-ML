# Rule-Based CFD Strategy Logic Template: Strategy 13 (Hurst Exponent & Fractal Regime Switching)

**Asset Class:** CFD Commodity (XAUUSD / Gold) & Multi-Asset  
**Timeframe:** M15 (Resampled from M1)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots (10 oz units)  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ⚠️ **MARGINAL PASS (Net +$7.0k, PF = 1.053, MCR = 51.39%)**  

---

## 1. Executive Summary & Core Hypothesis

Strategy 13 applies the **Fractal Market Hypothesis (FMH)** and **Rescaled Range (R/S) Analysis** to dynamically classify financial markets into three distinct stochastic regimes:
1. **Persistent Trending Regime ($H \ge 0.55$):** Time series exhibits long memory and positive autocorrelation.
2. **Anti-Persistent Mean-Reverting Regime ($H \le 0.42$):** Time series exhibits negative autocorrelation and mean reversion.
3. **Brownian Noise / Random Walk ($0.42 < H < 0.55$):** Pure noise with independent increments $\rightarrow$ Stay 100% FLAT.

---

## 2. Deterministic Strategy Logic Specification (พิมพ์เขียวตรรกะที่แน่นอน)

### A. State & Indicator Inputs
1. `ATR(14)` on M15 Close.
2. `Rolling_Hurst(100)`: 100-bar sliding window R/S estimate on log prices.
3. `H_Trend_Threshold`: $0.55$.
4. `H_Reversion_Threshold`: $0.42$.
5. `SMA(20)` and `StdDev(20)` for Mean Reversion envelope.

### B. Regime 1: Persistent Trend Execution ($H \ge 0.55$)
At the close of candle $i$:
1. **Bullish Trigger:** $\text{Close}[i] > \max(\text{High}[i-10 \dots i-1])$
   - Enter BUY at $\text{Open}[i+1]$
   - Stop Loss: $\text{Entry} - (2.5 \times \text{ATR}_{14}[i])$
   - Take Profit: $\text{Entry} + (4.0 \times \text{SL\_Distance})$ ($4.0R$)
2. **Bearish Trigger:** $\text{Close}[i] < \min(\text{Low}[i-10 \dots i-1])$
   - Enter SELL at $\text{Open}[i+1]$
   - Stop Loss: $\text{Entry} + (2.5 \times \text{ATR}_{14}[i])$
   - Take Profit: $\text{Entry} - (4.0 \times \text{SL\_Distance})$ ($4.0R$)

### C. Regime 2: Anti-Persistent Reversion Execution ($H \le 0.42$)
At the close of candle $i$:
1. **Bullish Fade:** $\text{Low}[i] < \text{Lower\_BB}[i] \text{ and } \text{Close}[i] > \text{Lower\_BB}[i]$
   - Enter BUY at $\text{Open}[i+1]$, SL: $2.5 \times \text{ATR}$, TP: $\text{SMA}_{20}$ midline.
2. **Bearish Fade:** $\text{High}[i] > \text{Upper\_BB}[i] \text{ and } \text{Close}[i] < \text{Upper\_BB}[i]$
   - Enter SELL at $\text{Open}[i+1]$, SL: $2.5 \times \text{ATR}$, TP: $\text{SMA}_{20}$ midline.

### D. Regime 3: Noise Exclusion ($0.42 < H < 0.55$)
- **Do not open any new trades.** Protects capital from random-walk churn.

---

## 3. 72-Month Audit Performance Metrics (Champion Set)

| Metric | Champion Value | Assessment |
| :--- | :--- | :--- |
| **Total Trades (2020–2025)** | **1,818 trades** | Active sample |
| **Net Profit (0.10 Lot)** | **+$6,998.27** | Net of frictions |
| **Profit Factor (PF)** | **1.053** | Marginally above breakeven |
| **Win Rate** | **21.51%** | Offset by 4.0R trend targets |
| **Max Drawdown ($)** | **$6,779.01** | Elevated drawdown |
| **Monthly Consistency (MCR)**| **51.39% (37 / 72 months)** | Insufficient for standalone core |

---

## 4. Quantitative Takeaway
While the Hurst Exponent is theoretically sound, the high computational overhead of calculating rolling Hurst in real-time and its tendency to lag rapid market inflection points makes it inferior to **Zero-Lag MACD** and **TTM Squeeze** for CFD intraday execution.

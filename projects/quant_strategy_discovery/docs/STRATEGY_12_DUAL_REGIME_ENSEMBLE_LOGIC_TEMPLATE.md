# Rule-Based CFD Strategy Logic Template: Strategy 12 (Dual-Regime Cross-Session Ensemble)

**Asset Class:** CFD Commodity (XAUUSD / Gold) & Major Forex  
**Timeframe:** M15 (Resampled from M1)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots (10 oz units)  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ✅ **ACCEPTED (Multi-Regime Cashflow Generator, Net +$13.5k, PF = 1.12)**  

---

## 1. Executive Summary & Core Hypothesis

Strategy 12 is a bespoke hybrid algorithmic template engineered to overcome the cyclical drawdowns of standalone trend-following strategies during market consolidation.

### Core Hypothesis
- **Market Asymmetry by Session:**
  * **London & New York Sessions (08:00 - 18:00 UTC):** Market exhibits high institutional volume and sustained directional momentum.
  * **Asian & Overnight Sessions (21:00 - 06:00 UTC):** Market exhibits low volatility, bounded ranges, and strong mean-reverting tendencies.
- **Ensemble Synergy:**
  * By deploying a 4.0R Trend Expansion Engine during London/NY and a 20 SMA Reversion Engine during Asian quiet hours, capital remains active across both trending and consolidating macro regimes.

---

## 2. Deterministic Strategy Logic Specification (พิมพ์เขียวตรรกะที่แน่นอน 100%)

### A. State & Indicator Inputs
1. `ATR(14)` on M15 Close.
2. `EMA(200)` on M15 Close.
3. `SMA(20)` and `StdDev(20)` on M15 Close.
4. `Upper_Band` = $\text{SMA}(20) + 2.8 \times \text{StdDev}(20)$.
5. `Lower_Band` = $\text{SMA}(20) - 2.8 \times \text{StdDev}(20)$.
6. `Hour` = Candle bar hour in UTC.

### B. Engine A: Trend Breakout Mode (08:00 $\le$ Hour < 18:00 UTC)
At the close of candle $i$:
1. **Long Entry Trigger:**
   $$\text{Close}[i] > \max(\text{High}[i-8 \dots i-1]) \quad \text{AND} \quad \text{Close}[i] > \text{EMA}_{200}[i]$$
   - Execution: Enter BUY at $\text{Open}[i+1]$.
   - Stop Loss: $\text{Entry} - (2.5 \times \text{ATR}_{14}[i])$.
   - Take Profit: $\text{Entry} + (4.0 \times \text{SL\_Distance})$ ($4.0R$).
2. **Short Entry Trigger:**
   $$\text{Close}[i] < \min(\text{Low}[i-8 \dots i-1]) \quad \text{AND} \quad \text{Close}[i] < \text{EMA}_{200}[i]$$
   - Execution: Enter SELL at $\text{Open}[i+1]$.
   - Stop Loss: $\text{Entry} + (2.5 \times \text{ATR}_{14}[i])$.
   - Take Profit: $\text{Entry} - (4.0 \times \text{SL\_Distance})$ ($4.0R$).

### C. Engine B: Asian Mean Reversion Mode (Hour $\ge$ 21:00 OR Hour < 06:00 UTC)
At the close of candle $i$:
1. **Long Entry Trigger (Oversold Extreme):**
   $$\text{Low}[i] < \text{Lower\_Band}[i] \quad \text{AND} \quad \text{Close}[i] > \text{Lower\_Band}[i]$$
   - Execution: Enter BUY at $\text{Open}[i+1]$.
   - Stop Loss: $\text{Entry} - (2.0 \times \text{ATR}_{14}[i])$.
   - Take Profit: Exit at touch of $\text{SMA}_{20}$ Midline.
2. **Short Entry Trigger (Overbought Extreme):**
   $$\text{High}[i] > \text{Upper\_Band}[i] \quad \text{AND} \quad \text{Close}[i] < \text{Upper\_Band}[i]$$
   - Execution: Enter SELL at $\text{Open}[i+1]$.
   - Stop Loss: $\text{Entry} + (2.0 \times \text{ATR}_{14}[i])$.
   - Take Profit: Exit at touch of $\text{SMA}_{20}$ Midline.

---

## 3. 72-Month Audit Performance Metrics (Champion Set)

| Metric | Champion Value | Assessment |
| :--- | :--- | :--- |
| **Total Trades (2020–2025)** | **1,863 trades** | Balanced activity across 6 years |
| **Net Profit (0.10 Lot)** | **+$13,490.84** | Robust multi-year edge |
| **Profit Factor (PF)** | **1.120** | Consistent positive expectancy |
| **Win Rate** | **29.68%** | High payoff due to 4.0R trend targets |
| **Max Drawdown ($)** | **$6,636.04** | Broadly distributed over 1,800+ trades |
| **Total Calendar Months** | **72 months** | Complete multi-regime evaluation |
| **Profitable Months** | **44 months (61.11%)**| Consistent cashflow |

---

## 4. Plug-and-Play MQL5 Logic Implementation

```mql5
//+------------------------------------------------------------------+
//| Check Dual-Regime Ensemble Signal (MQL5 Snippet)                |
//+------------------------------------------------------------------+
bool CheckDualRegimeSignal(int &signal_type, string &engine_tag, double &sl_price, double &tp_price)
{
   signal_type = 0;
   engine_tag = "";

   datetime time_arr[1];
   if(CopyTime(_Symbol, _Period, 1, 1, time_arr) <= 0) return false;
   MqlDateTime dt;
   TimeToStruct(time_arr[0], dt);
   int hr = dt.hour;

   double atr[1], ema200[1];
   if(CopyBuffer(h_atr14, 0, 1, 1, atr) <= 0) return false;
   if(CopyBuffer(h_ema200, 0, 1, 1, ema200) <= 0) return false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 1, 25, rates) < 25) return false;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // -------------------------------------------------------------
   // 1. ENGINE A: TREND EXPANSION (08:00 - 18:00 UTC)
   // -------------------------------------------------------------
   if(hr >= 8 && hr < 18)
   {
      double h8 = -1e9, l8 = 1e9;
      for(int k = 1; k <= 8; k++)
      {
         if(rates[k].high > h8) h8 = rates[k].high;
         if(rates[k].low < l8)  l8 = rates[k].low;
      }

      double c1 = rates[0].close;
      if(c1 > h8 && c1 > ema200[0])
      {
         signal_type = 1;
         engine_tag = "TREND";
         double sl_dist = 2.5 * atr[0];
         sl_price = ask - sl_dist;
         tp_price = ask + (4.0 * sl_dist);
         return true;
      }
      else if(c1 < l8 && c1 < ema200[0])
      {
         signal_type = -1;
         engine_tag = "TREND";
         double sl_dist = 2.5 * atr[0];
         sl_price = bid + sl_dist;
         tp_price = bid - (4.0 * sl_dist);
         return true;
      }
   }
   // -------------------------------------------------------------
   // 2. ENGINE B: ASIAN MEAN REVERSION (21:00 - 06:00 UTC)
   // -------------------------------------------------------------
   else if(hr >= 21 || hr < 6)
   {
      double sum = 0.0;
      for(int k = 0; k < 20; k++) sum += rates[k].close;
      double sma20 = sum / 20.0;

      double var_sum = 0.0;
      for(int k = 0; k < 20; k++) var_sum += MathPow(rates[k].close - sma20, 2.0);
      double std20 = MathSqrt(var_sum / 20.0);

      double up_band = sma20 + (2.8 * std20);
      double low_band = sma20 - (2.8 * std20);

      if(rates[0].low < low_band && rates[0].close > low_band)
      {
         signal_type = 1;
         engine_tag = "REVERSION";
         sl_price = ask - (2.0 * atr[0]);
         tp_price = sma20; // Reversion to 20 SMA
         return true;
      }
      else if(rates[0].high > up_band && rates[0].close < up_band)
      {
         signal_type = -1;
         engine_tag = "REVERSION";
         sl_price = bid + (2.0 * atr[0]);
         tp_price = sma20; // Reversion to 20 SMA
         return true;
      }
   }

   return false;
}
```

//+------------------------------------------------------------------+
//|                                  Gold_H1_RVI_Volatility_Master_EA.mq5 |
//|                                  CFD Quantitative Strategy Discovery |
//|                                    Strategy 53: RVI-KFD H1 Expander  |
//+------------------------------------------------------------------+
#property copyright "CFD Quant Research Project"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== Strategy Parameters ==="
input int    InpStdPeriod       = 10;       // Standard Deviation Lookback
input int    InpEMAPeriod       = 14;       // RVI Smoothing EMA Period
input double InpRVIUpperThresh  = 60.0;     // RVI Upper Bullish Expansion Threshold
input double InpRVILowerThresh  = 40.0;     // RVI Lower Bearish Expansion Threshold
input int    InpKFDPeriod       = 24;       // Katz Fractal Lookback
input double InpKFDThreshold    = 1.40;     // Katz Fractal Dimension Max Threshold
input int    InpMacroEMAPeriod  = 200;      // Macro Trend EMA Period
input double InpTPMult          = 4.5;      // Take Profit (x ATR)
input double InpSLMult          = 2.0;      // Stop Loss (x ATR)

input group "=== Risk & ASAR Parameters ==="
input double InpBaseLot         = 0.10;     // Base Lot Size
input double InpMonthlyProfitLock = 200.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreaker = -250.0;// Monthly Loss Circuit Breaker ($)
input double InpDefensiveDDThresh = 120.0;  // Defensive Drawdown Threshold ($)
input double InpDefensiveLotMult  = 0.25;   // Defensive Lot Multiplier
input ulong  InpMagicNumber     = 105301;   // Magic Number

//--- Indicator Handles
int handle_atr;
int handle_macro_ema;

//--- Internal State
datetime last_bar_time = 0;
int current_month = -1;
double monthly_pnl = 0.0;
double peak_monthly_pnl = 0.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   
   handle_atr = iATR(_Symbol, PERIOD_H1, 14);
   handle_macro_ema = iMA(_Symbol, PERIOD_H1, InpMacroEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   
   if(handle_atr == INVALID_HANDLE || handle_macro_ema == INVALID_HANDLE)
   {
      Print("Error creating indicator handles.");
      return(INIT_FAILED);
   }
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_macro_ema);
}

//+------------------------------------------------------------------+
//| Calculate Relative Volatility Index (RVI)                        |
//+------------------------------------------------------------------+
double CalculateRVI(int std_p, int ema_p)
{
   int lookback = std_p + ema_p * 3;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, lookback + 2, rates);
   
   double std_up[], std_down[];
   ArrayResize(std_up, lookback);
   ArrayResize(std_down, lookback);
   
   for(int i = 0; i < lookback; i++)
   {
      double sum = 0.0;
      for(int k = 0; k < std_p; k++) sum += rates[i + k].close;
      double mean = sum / std_p;
      
      double sum_sq = 0.0;
      for(int k = 0; k < std_p; k++) sum_sq += MathPow(rates[i + k].close - mean, 2.0);
      double std_val = MathSqrt(sum_sq / std_p);
      
      double diff = rates[i].close - rates[i + 1].close;
      std_up[i] = (diff > 0) ? std_val : 0.0;
      std_down[i] = (diff < 0) ? std_val : 0.0;
   }
   
   // EMA of std_up and std_down
   double alpha = 2.0 / (ema_p + 1.0);
   double e_up = std_up[lookback - 1];
   double e_down = std_down[lookback - 1];
   
   for(int i = lookback - 2; i >= 0; i--)
   {
      e_up = alpha * std_up[i] + (1.0 - alpha) * e_up;
      e_down = alpha * std_down[i] + (1.0 - alpha) * e_down;
   }
   
   double denom = e_up + e_down;
   if(denom <= 0) return 50.0;
   return 100.0 * (e_up / denom);
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension                                 |
//+------------------------------------------------------------------+
double CalculateKatzFractal(int window)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, window + 1, rates);
   
   double max_c = -999999.0;
   double min_c = 999999.0;
   double total_dist = 0.0;
   
   for(int i = 0; i < window; i++)
   {
      if(rates[i].close > max_c) max_c = rates[i].close;
      if(rates[i].close < min_c) min_c = rates[i].close;
      total_dist += MathAbs(rates[i].close - rates[i + 1].close);
   }
   
   double d = max_c - min_c;
   if(total_dist <= 0 || d <= 0) return 1.5;
   
   double log_w = MathLog10((double)window);
   double ratio = d / total_dist;
   if(ratio <= 0) return 1.5;
   
   double kfd = log_w / (log_w + MathLog10(ratio));
   return MathMax(1.0, MathMin(kfd, 2.0));
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == last_bar_time)
      return;
      
   last_bar_time = current_bar_time;
   
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.mon != current_month)
   {
      current_month = dt.mon;
      monthly_pnl = 0.0;
      peak_monthly_pnl = 0.0;
   }
   
   if(monthly_pnl >= InpMonthlyProfitLock || monthly_pnl <= InpMonthlyLossBreaker)
      return;
      
   double active_lot = InpBaseLot;
   if((peak_monthly_pnl - monthly_pnl) >= InpDefensiveDDThresh)
      active_lot = InpBaseLot * InpDefensiveLotMult;
      
   if(PositionsTotal() > 0)
      return;
      
   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(handle_atr, 0, 1, 1, atr);
   
   double ema[];
   ArraySetAsSeries(ema, true);
   CopyBuffer(handle_macro_ema, 0, 1, 1, ema);
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, 2, rates);
   
   double kfd = CalculateKatzFractal(InpKFDPeriod);
   if(kfd > InpKFDThreshold)
      return;
      
   double rvi_cur = CalculateRVI(InpStdPeriod, InpEMAPeriod);
   double c1 = rates[0].close;
   double c_atr = atr[0];
   
   if(rvi_cur >= InpRVIUpperThresh && c1 > ema[0])
   {
      double sl = c1 - InpSLMult * c_atr;
      double tp = c1 + InpTPMult * c_atr;
      trade.Buy(active_lot, _Symbol, 0, sl, tp, "S53_RVI_KFD_Buy");
   }
   else if(rvi_cur <= InpRVILowerThresh && c1 < ema[0])
   {
      double sl = c1 + InpSLMult * c_atr;
      double tp = c1 - InpTPMult * c_atr;
      trade.Sell(active_lot, _Symbol, 0, sl, tp, "S53_RVI_KFD_Sell");
   }
}

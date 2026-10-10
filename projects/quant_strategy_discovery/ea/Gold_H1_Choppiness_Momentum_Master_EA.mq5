//+------------------------------------------------------------------+
//|                           Gold_H1_Choppiness_Momentum_Master_EA.mq5 |
//|                                  CFD Quantitative Strategy Discovery |
//|                                    Strategy 46: CHOP-CMO H1 Expander |
//+------------------------------------------------------------------+
#property copyright "CFD Quant Research Project"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== Strategy Parameters ==="
input int    InpChopPeriod      = 14;       // Choppiness Index Period
input double InpChopThreshold   = 45.0;     // Max Choppiness Threshold (<= 45.0 = Trending)
input int    InpCMOPeriod       = 14;       // Chande Momentum Period
input double InpCMOThreshold    = 20.0;     // CMO Threshold (>= 20.0 or <= -20.0)
input int    InpChannelPeriod   = 20;       // Donchian Breakout Period
input int    InpEMAPeriod       = 200;      // Macro Trend EMA Period
input double InpTPMult          = 3.5;      // Take Profit (x ATR)
input double InpSLMult          = 2.0;      // Stop Loss (x ATR)

input group "=== Risk & ASAR Parameters ==="
input double InpBaseLot         = 0.10;     // Base Lot Size
input double InpMonthlyProfitLock = 300.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreaker = -250.0;// Monthly Loss Circuit Breaker ($)
input double InpDefensiveDDThresh = 120.0;  // Defensive Drawdown Threshold ($)
input double InpDefensiveLotMult  = 0.25;   // Defensive Lot Multiplier
input ulong  InpMagicNumber     = 104601;   // Magic Number

//--- Indicator Handles
int handle_atr;
int handle_ema;

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
   
   handle_atr = iATR(_Symbol, PERIOD_H1, InpChopPeriod);
   handle_ema = iMA(_Symbol, PERIOD_H1, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   
   if(handle_atr == INVALID_HANDLE || handle_ema == INVALID_HANDLE)
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
   IndicatorRelease(handle_ema);
}

//+------------------------------------------------------------------+
//| Calculate Choppiness Index                                       |
//+------------------------------------------------------------------+
double CalculateChoppinessIndex(int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, period + 1, rates);
   
   double sum_tr = 0.0;
   double max_high = -999999.0;
   double min_low = 999999.0;
   
   for(int i = 0; i < period; i++)
   {
      double hl = rates[i].high - rates[i].low;
      double hc = MathAbs(rates[i].high - rates[i + 1].close);
      double lc = MathAbs(rates[i].low - rates[i + 1].close);
      double tr = MathMax(hl, MathMax(hc, lc));
      sum_tr += tr;
      
      if(rates[i].high > max_high) max_high = rates[i].high;
      if(rates[i].low < min_low) min_low = rates[i].low;
   }
   
   double rng = max_high - min_low;
   if(rng <= 0) return 50.0;
   
   double ratio = sum_tr / rng;
   if(ratio <= 0) return 50.0;
   
   double ci = 100.0 * (MathLog10(ratio) / MathLog10(period));
   return ci;
}

//+------------------------------------------------------------------+
//| Calculate Chande Momentum Oscillator                             |
//+------------------------------------------------------------------+
double CalculateCMO(int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, period + 1, rates);
   
   double sum_up = 0.0;
   double sum_down = 0.0;
   
   for(int i = 0; i < period; i++)
   {
      double diff = rates[i].close - rates[i + 1].close;
      if(diff > 0) sum_up += diff;
      else if(diff < 0) sum_down += MathAbs(diff);
   }
   
   double total = sum_up + sum_down;
   if(total <= 0) return 0.0;
   
   return 100.0 * (sum_up - sum_down) / total;
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
   CopyBuffer(handle_ema, 0, 1, 1, ema);
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, InpChannelPeriod + 2, rates);
   
   double ci = CalculateChoppinessIndex(InpChopPeriod);
   double cmo = CalculateCMO(InpCMOPeriod);
   
   if(ci > InpChopThreshold)
      return; // Market is choppy
      
   double high20 = -999999.0;
   double low20 = 999999.0;
   for(int i = 1; i <= InpChannelPeriod; i++)
   {
      if(rates[i].close > high20) high20 = rates[i].close;
      if(rates[i].close < low20) low20 = rates[i].close;
   }
   
   double c1 = rates[0].close;
   double c_atr = atr[0];
   
   if(c1 > ema[0] && cmo >= InpCMOThreshold && c1 >= high20)
   {
      double sl = c1 - InpSLMult * c_atr;
      double tp = c1 + InpTPMult * c_atr;
      trade.Buy(active_lot, _Symbol, 0, sl, tp, "S46_CHOP_CMO_Buy");
   }
   else if(c1 < ema[0] && cmo <= -InpCMOThreshold && c1 <= low20)
   {
      double sl = c1 + InpSLMult * c_atr;
      double tp = c1 - InpTPMult * c_atr;
      trade.Sell(active_lot, _Symbol, 0, sl, tp, "S46_CHOP_CMO_Sell");
   }
}

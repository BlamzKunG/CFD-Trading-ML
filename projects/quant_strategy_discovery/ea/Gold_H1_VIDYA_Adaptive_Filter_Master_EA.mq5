//+------------------------------------------------------------------+
//|                      Gold_H1_VIDYA_Adaptive_Filter_Master_EA.mq5|
//|               CFD Quantitative Strategy Discovery - Strategy 130 |
//|        Variable Index Dynamic Average (VIDYA) Master EA for Gold |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Parameters ==="
input int    InpCMOPeriod         = 9;      // Chande Momentum Oscillator Lookback Period
input int    InpEMAPeriod         = 14;     // Base Exponential Smoothing Lookback Period
input double InpCMOThreshold      = 15.0;   // CMO Momentum Acceleration Threshold
input int    InpATRPeriod         = 14;     // ATR Lookback Window
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input int    InpKFDPeriod         = 24;     // Katz Fractal Lookback Window
input double InpKFDThreshold      = 1.42;   // Maximum Katz Fractal Dimension

input group "=== Risk & Target Multipliers ==="
input double InpTakeProfitMult    = 4.5;    // Take Profit (ATR Multiplier - 2.25:1 R:R)
input double InpStopLossMult      = 2.0;    // Stop Loss (ATR Multiplier)
input double InpLotSize           = 0.10;   // Institutional Lot Size
input ulong  InpMagicNumber       = 130001; // EA Magic Number

input group "=== ASAR Calendar Risk Governance ==="
input double InpMonthlyProfitLock = 200.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreak  = 250.0;  // Monthly Loss Breaker ($)

// Global variables
CTrade   trade;
int      handle_atr;
int      handle_ema200;
datetime last_bar_time;
int      current_month;
double   monthly_pnl;
bool     month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);

   handle_atr = iATR(_Symbol, PERIOD_H1, InpATRPeriod);
   handle_ema200 = iMA(_Symbol, PERIOD_H1, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE)
   {
      Print("[-] Error initializing indicators.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   current_month = -1;
   monthly_pnl = 0.0;
   month_locked = false;

   Print("[+] Gold H1 VIDYA Adaptive Filter Master EA initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_ema200);
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension (KFD)                           |
//+------------------------------------------------------------------+
double CalculateKFD(int shift)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, shift, InpKFDPeriod + 1, closes) <= InpKFDPeriod)
      return 1.5;

   double length = 0.0;
   double max_dist = 0.0;
   double p0 = closes[InpKFDPeriod];

   for(int i = InpKFDPeriod - 1; i >= 0; i--)
   {
      length += MathAbs(closes[i] - closes[i + 1]);
      double dist = MathAbs(closes[i] - p0);
      if(dist > max_dist) max_dist = dist;
   }

   if(length <= 0.0 || max_dist <= 0.0) return 1.5;
   double k = MathLog10((double)InpKFDPeriod) / (MathLog10((double)InpKFDPeriod) + MathLog10(max_dist / length));
   return MathMax(1.0, MathMin(2.0, k));
}

//+------------------------------------------------------------------+
//| Calculate VIDYA and CMO at a specific shift                      |
//+------------------------------------------------------------------+
bool CalculateVIDYA_State(int shift, double &vidya_out, double &cmo_out)
{
   int lookback = InpEMAPeriod * 5 + InpCMOPeriod;
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, shift, lookback, closes) < lookback)
      return false;

   // Compute CMO series for the window
   double cmo_series[];
   ArrayResize(cmo_series, lookback - InpCMOPeriod);
   
   for(int k = 0; k < lookback - InpCMOPeriod; k++)
   {
      double sumUp = 0.0, sumDown = 0.0;
      for(int c = 0; c < InpCMOPeriod; c++)
      {
         double diff = closes[k + c] - closes[k + c + 1];
         if(diff > 0) sumUp += diff;
         else         sumDown += MathAbs(diff);
      }
      double total = sumUp + sumDown;
      cmo_series[k] = (total > 1e-6) ? (100.0 * (sumUp - sumDown) / total) : 0.0;
   }

   cmo_out = cmo_series[0];

   // Vectorized dynamic EMA recursion
   double alpha = 2.0 / ((double)InpEMAPeriod + 1.0);
   int warm_len = ArraySize(cmo_series);
   double v = closes[warm_len - 1];

   for(int i = warm_len - 1; i >= 0; i--)
   {
      double k = (MathAbs(cmo_series[i]) / 100.0) * alpha;
      v = (k * closes[i]) + ((1.0 - k) * v);
   }

   vidya_out = v;
   return true;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == last_bar_time) return;

   MqlDateTime dt;
   TimeToStruct(current_bar_time, dt);
   int bar_month = dt.year * 100 + dt.mon;

   // Check calendar month budget reset
   if(bar_month != current_month)
   {
      current_month = bar_month;
      monthly_pnl = 0.0;
      month_locked = false;
      PrintFormat("[*] S130: Month reset to %d. Risk governance unlocked.", current_month);
   }

   if(month_locked) return;

   // Position Check
   bool has_position = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         has_position = true;
         break;
      }
   }

   if(has_position) return;

   // Indicators on confirmed bars
   double atr[];
   double ema200[];
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(ema200, true);

   if(CopyBuffer(handle_atr, 0, 1, 1, atr) <= 0 ||
      CopyBuffer(handle_ema200, 0, 1, 1, ema200) <= 0)
      return;

   double close_1 = iClose(_Symbol, PERIOD_H1, 1);
   double close_2 = iClose(_Symbol, PERIOD_H1, 2);
   double kfd_1   = CalculateKFD(1);

   double vidya_1, vidya_2, cmo_1, cmo_2;
   if(!CalculateVIDYA_State(1, vidya_1, cmo_1) || !CalculateVIDYA_State(2, vidya_2, cmo_2))
      return;

   bool cross_up = (close_1 > vidya_1) && (close_2 <= vidya_2);
   bool cross_dn = (close_1 < vidya_1) && (close_2 >= vidya_2);

   bool trend_bull = (close_1 > ema200[0]);
   bool trend_bear = (close_1 < ema200[0]);
   bool kfd_ok     = (kfd_1 <= InpKFDThreshold);

   double atr_val = atr[0];
   double sl_dist = InpStopLossMult * atr_val;
   double tp_dist = InpTakeProfitMult * atr_val;

   if(cross_up && (cmo_1 > InpCMOThreshold) && trend_bull && kfd_ok)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = ask - sl_dist;
      double tp  = ask + tp_dist;

      trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "S130 VIDYA Long");
      last_bar_time = current_bar_time;
   }
   else if(cross_dn && (cmo_1 < -InpCMOThreshold) && trend_bear && kfd_ok)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = bid + sl_dist;
      double tp  = bid - tp_dist;

      trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "S130 VIDYA Short");
      last_bar_time = current_bar_time;
   }
}
//+------------------------------------------------------------------+

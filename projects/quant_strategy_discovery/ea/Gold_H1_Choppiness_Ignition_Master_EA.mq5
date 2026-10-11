//+------------------------------------------------------------------+
//|                         Gold_H1_Choppiness_Ignition_Master_EA.mq5|
//|               CFD Quantitative Strategy Discovery - Strategy 113 |
//|        Choppiness Index Compression to Explosion Ignition Master |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Parameters ==="
input int    InpChopPeriod        = 20;     // Choppiness Lookback Period
input double InpChopThreshold     = 38.2;   // Compression Ignition Threshold
input int    InpATRPeriod         = 14;     // ATR Lookback Window
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input int    InpKFDPeriod         = 24;     // Katz Fractal Lookback
input double InpKFDThreshold      = 1.42;   // Maximum Katz Fractal Dimension

input group "=== Risk & Target Multipliers ==="
input double InpTakeProfitMult    = 5.5;    // Take Profit (ATR Multiplier - 3.67:1 R:R)
input double InpStopLossMult      = 1.5;    // Stop Loss (ATR Multiplier)
input double InpLotSize           = 0.10;   // Institutional Lot Size
input ulong  InpMagicNumber       = 113001; // EA Magic Number

input group "=== ASAR Calendar Risk Governance ==="
input double InpMonthlyProfitLock = 250.0;  // Monthly Profit Lock ($)
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

   Print("[+] Gold H1 Choppiness Ignition Master EA initialized successfully.");
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
//| Calculate Katz Fractal Dimension                                 |
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
   double k = MathLog10(InpKFDPeriod) / (MathLog10(InpKFDPeriod) + MathLog10(max_dist / length));
   return MathMax(1.0, MathMin(2.0, k));
}

//+------------------------------------------------------------------+
//| Calculate Choppiness Index                                       |
//+------------------------------------------------------------------+
double CalculateChop(int shift)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, shift, InpChopPeriod, rates) < InpChopPeriod)
      return 50.0;

   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(handle_atr, 0, shift, InpChopPeriod, atr_buf) < InpChopPeriod)
      return 50.0;

   double max_high = rates[0].high;
   double min_low  = rates[0].low;
   double sum_atr  = 0.0;

   for(int i = 0; i < InpChopPeriod; i++)
   {
      if(rates[i].high > max_high) max_high = rates[i].high;
      if(rates[i].low < min_low)   min_low = rates[i].low;
      sum_atr += atr_buf[i];
   }

   double range = max_high - min_low;
   if(range <= 0.0) return 50.0;

   double chop = 100.0 * MathLog10(sum_atr / range) / MathLog10(InpChopPeriod);
   return chop;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == last_bar_time) return;

   MqlDateTime dt;
   TimeCurrent(dt);
   int bar_month = dt.year * 100 + dt.mon;

   if(bar_month != current_month)
   {
      current_month = bar_month;
      monthly_pnl = 0.0;
      month_locked = false;
   }

   last_bar_time = current_bar_time;

   // Check active position
   bool in_pos = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         in_pos = true;
         break;
      }
   }

   if(in_pos || month_locked) return;

   // Indicators on confirmed bars
   double atr_buf[];
   double ema200_buf[];
   ArraySetAsSeries(atr_buf, true);
   ArraySetAsSeries(ema200_buf, true);

   if(CopyBuffer(handle_atr, 0, 1, 1, atr_buf) <= 0) return;
   if(CopyBuffer(handle_ema200, 0, 1, 1, ema200_buf) <= 0) return;

   double atr = atr_buf[0];
   double ema200 = ema200_buf[0];
   double close1 = iClose(_Symbol, PERIOD_H1, 1);

   double chop1 = CalculateChop(1);
   double chop2 = CalculateChop(2);
   double kfd = CalculateKFD(1);

   bool kfd_ok = (kfd <= InpKFDThreshold);
   bool trend_bull = (close1 > ema200);
   bool trend_bear = (close1 < ema200);

   // Ignition: CHOP crosses below threshold
   bool ignition = (chop1 < InpChopThreshold) && (chop2 >= InpChopThreshold);
   bool bull_sig = ignition && trend_bull && kfd_ok;
   bool bear_sig = ignition && trend_bear && kfd_ok;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(bull_sig)
   {
      double sl = ask - (InpStopLossMult * atr);
      double tp = ask + (InpTakeProfitMult * atr);
      trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "Strategy 113 Chop Ignition Long");
   }
   else if(bear_sig)
   {
      double sl = bid + (InpStopLossMult * atr);
      double tp = bid - (InpTakeProfitMult * atr);
      trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "Strategy 113 Chop Ignition Short");
   }
}
//+------------------------------------------------------------------+

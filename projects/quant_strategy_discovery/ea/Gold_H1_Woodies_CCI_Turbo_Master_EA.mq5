//+------------------------------------------------------------------+
//|                             Gold_H1_Woodies_CCI_Turbo_Master_EA.mq5|
//|               CFD Quantitative Strategy Discovery - Strategy 102 |
//|       Woodies CCI Turbo Dual-Oscillator Acceleration System      |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Parameters ==="
input int    InpStandardCCIPeriod = 20;     // Standard CCI Period
input int    InpTurboCCIPeriod    = 6;      // Turbo Fast CCI Period
input int    InpATRPeriod         = 14;     // ATR Lookback Window
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input int    InpKFDPeriod         = 24;     // Katz Fractal Lookback
input double InpKFDThreshold      = 1.38;   // Maximum Katz Fractal Dimension

input group "=== Risk & Target Multipliers ==="
input double InpTakeProfitMult    = 4.5;    // Take Profit (ATR Multiplier)
input double InpStopLossMult      = 2.5;    // Stop Loss (ATR Multiplier)
input double InpLotSize           = 0.10;   // Institutional Lot Size
input ulong  InpMagicNumber       = 102001; // EA Magic Number

input group "=== ASAR Calendar Risk Governance ==="
input double InpMonthlyProfitLock = 200.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreak  = 250.0;  // Monthly Loss Breaker ($)

// Global handles & variables
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

   Print("[+] Gold H1 Woodies CCI Turbo Master EA initialized successfully.");
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
//| Calculate Custom Woodies CCI Value                               |
//+------------------------------------------------------------------+
double CalculateCCI(int period, int shift)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, shift, period, rates) < period)
      return 0.0;

   double sum_tp = 0.0;
   double tp[];
   ArrayResize(tp, period);

   for(int i = 0; i < period; i++)
   {
      tp[i] = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      sum_tp += tp[i];
   }
   double mean_tp = sum_tp / period;

   double sum_dev = 0.0;
   for(int i = 0; i < period; i++)
      sum_dev += MathAbs(tp[i] - mean_tp);
   double mean_dev = sum_dev / period;

   if(mean_dev <= 0.0) return 0.0;
   return (tp[0] - mean_tp) / (0.015 * mean_dev);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == last_bar_time) return; // Execute once per bar close

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

   // Get indicator buffers on confirmed bar 1
   double atr_buf[];
   double ema200_buf[];
   ArraySetAsSeries(atr_buf, true);
   ArraySetAsSeries(ema200_buf, true);

   if(CopyBuffer(handle_atr, 0, 1, 1, atr_buf) <= 0) return;
   if(CopyBuffer(handle_ema200, 0, 1, 1, ema200_buf) <= 0) return;

   double atr = atr_buf[0];
   double ema200 = ema200_buf[0];
   double close1 = iClose(_Symbol, PERIOD_H1, 1);

   double cci_std = CalculateCCI(InpStandardCCIPeriod, 1);
   double cci_turbo = CalculateCCI(InpTurboCCIPeriod, 1);
   double kfd = CalculateKFD(1);

   bool kfd_ok = (kfd <= InpKFDThreshold);
   bool trend_bull = (close1 > ema200);
   bool trend_bear = (close1 < ema200);

   // Woodies Turbo Cross signals
   bool bull_sig = (cci_turbo > cci_std) && (cci_std > 0) && trend_bull && kfd_ok;
   bool bear_sig = (cci_turbo < cci_std) && (cci_std < 0) && trend_bear && kfd_ok;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(bull_sig)
   {
      double sl = ask - (InpStopLossMult * atr);
      double tp = ask + (InpTakeProfitMult * atr);
      trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "Strategy 102 Woodies Turbo Long");
   }
   else if(bear_sig)
   {
      double sl = bid + (InpStopLossMult * atr);
      double tp = bid - (InpTakeProfitMult * atr);
      trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "Strategy 102 Woodies Turbo Short");
   }
}
//+------------------------------------------------------------------+

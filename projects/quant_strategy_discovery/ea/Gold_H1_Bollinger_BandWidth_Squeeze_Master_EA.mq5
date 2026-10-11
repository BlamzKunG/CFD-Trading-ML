//+------------------------------------------------------------------+
//|                 Gold_H1_Bollinger_BandWidth_Squeeze_Master_EA.mq5|
//|               CFD Quantitative Strategy Discovery - Strategy 118 |
//|        Bollinger %B BandWidth Expansion Squeeze Ignition System  |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Parameters ==="
input int    InpBBPeriod          = 14;     // Bollinger Bands Lookback Period
input double InpBBMaskDev         = 1.8;    // Bollinger Standard Deviation Multiplier
input double InpPctBUpperCutoff   = 0.80;   // %B Upper Ignition Threshold
input double InpPctBLowerCutoff   = 0.20;   // %B Lower Ignition Threshold
input int    InpATRPeriod         = 14;     // ATR Lookback Window
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input int    InpKFDPeriod         = 24;     // Katz Fractal Lookback
input double InpKFDThreshold      = 1.38;   // Maximum Katz Fractal Dimension

input group "=== Risk & Target Multipliers ==="
input double InpTakeProfitMult    = 3.5;    // Take Profit (ATR Multiplier)
input double InpStopLossMult      = 2.5;    // Stop Loss (ATR Multiplier)
input double InpLotSize           = 0.10;   // Institutional Lot Size
input ulong  InpMagicNumber       = 118001; // EA Magic Number

input group "=== ASAR Calendar Risk Governance ==="
input double InpMonthlyProfitLock = 200.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreak  = 250.0;  // Monthly Loss Breaker ($)

// Global handles & variables
CTrade   trade;
int      handle_atr;
int      handle_ema200;
int      handle_bb;
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
   handle_bb = iBands(_Symbol, PERIOD_H1, InpBBPeriod, 0, InpBBMaskDev, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE || handle_bb == INVALID_HANDLE)
   {
      Print("[-] Error initializing indicators.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   current_month = -1;
   monthly_pnl = 0.0;
   month_locked = false;

   Print("[+] Gold H1 Bollinger BandWidth Squeeze Master EA initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_ema200);
   IndicatorRelease(handle_bb);
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
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == last_bar_time) return; // Execute once per confirmed bar close

   MqlDateTime dt;
   TimeToStruct(current_bar_time, dt);
   int bar_month = dt.year * 100 + dt.mon;

   // Check calendar month budget reset
   if(bar_month != current_month)
   {
      current_month = bar_month;
      monthly_pnl = 0.0;
      month_locked = false;
      PrintFormat("[*] S118: Month reset to %d. Risk governance unlocked.", current_month);
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

   // Indicators on confirmed bars 1 and 2
   double atr[];
   double ema200[];
   double bb_mid[], bb_up[], bb_lo[];
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(ema200, true);
   ArraySetAsSeries(bb_mid, true);
   ArraySetAsSeries(bb_up, true);
   ArraySetAsSeries(bb_lo, true);

   if(CopyBuffer(handle_atr, 0, 1, 1, atr) <= 0 ||
      CopyBuffer(handle_ema200, 0, 1, 1, ema200) <= 0 ||
      CopyBuffer(handle_bb, 0, 1, 2, bb_mid) <= 1 ||
      CopyBuffer(handle_bb, 1, 1, 2, bb_up) <= 1 ||
      CopyBuffer(handle_bb, 2, 1, 2, bb_lo) <= 1)
      return;

   double close_1 = iClose(_Symbol, PERIOD_H1, 1);
   double close_2 = iClose(_Symbol, PERIOD_H1, 2);
   double kfd_1 = CalculateKFD(1);

   // BandWidth and %B on bars 1 and 2
   double bw_1 = (bb_up[0] - bb_lo[0]) / (bb_mid[0] + 1e-9);
   double bw_2 = (bb_up[1] - bb_lo[1]) / (bb_mid[1] + 1e-9);
   bool bw_expanding = (bw_1 > bw_2);

   double pct_b_1 = (close_1 - bb_lo[0]) / (bb_up[0] - bb_lo[0] + 1e-9);
   double pct_b_2 = (close_2 - bb_lo[1]) / (bb_up[1] - bb_lo[1] + 1e-9);

   bool bull_cross = (pct_b_1 > InpPctBUpperCutoff) && (pct_b_2 <= InpPctBUpperCutoff);
   bool bear_cross = (pct_b_1 < InpPctBLowerCutoff) && (pct_b_2 >= InpPctBLowerCutoff);

   bool trend_bull = (close_1 > ema200[0]);
   bool trend_bear = (close_1 < ema200[0]);
   bool kfd_ok = (kfd_1 <= InpKFDThreshold);

   double atr_val = atr[0];
   double sl_dist = InpStopLossMult * atr_val;
   double tp_dist = InpTakeProfitMult * atr_val;

   if(bull_cross && bw_expanding && trend_bull && kfd_ok)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - sl_dist;
      double tp = ask + tp_dist;

      trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "S118 %B Squeeze Long");
      last_bar_time = current_bar_time;
      PrintFormat("[+] S118 Buy executed @ %f | SL: %f | TP: %f | ATR: %f | BW: %f", ask, sl, tp, atr_val, bw_1);
   }
   else if(bear_cross && bw_expanding && trend_bear && kfd_ok)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + sl_dist;
      double tp = bid - tp_dist;

      trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "S118 %B Squeeze Short");
      last_bar_time = current_bar_time;
      PrintFormat("[-] S118 Sell executed @ %f | SL: %f | TP: %f | ATR: %f | BW: %f", bid, sl, tp, atr_val, bw_1);
   }
}

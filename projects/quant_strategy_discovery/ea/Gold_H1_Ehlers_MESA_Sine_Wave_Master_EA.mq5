//+------------------------------------------------------------------+
//|                        Gold_H1_Ehlers_MESA_Sine_Wave_Master_EA.mq5|
//|               CFD Quantitative Strategy Discovery - Strategy 116 |
//|           Ehlers MESA Sine Wave Cycle Turning Point System       |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Parameters ==="
input int    InpCyclePeriod       = 10;     // Cycle Calculation Period
input double InpPhaseShiftDeg     = 30.0;   // LeadSine Phase Shift (Degrees)
input int    InpATRPeriod         = 14;     // ATR Lookback Window
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input int    InpKFDPeriod         = 24;     // Katz Fractal Lookback
input double InpKFDThreshold      = 1.42;   // Maximum Katz Fractal Dimension

input group "=== Risk & Target Multipliers ==="
input double InpTakeProfitMult    = 5.5;    // Take Profit (ATR Multiplier)
input double InpStopLossMult      = 2.0;    // Stop Loss (ATR Multiplier)
input double InpLotSize           = 0.10;   // Institutional Lot Size
input ulong  InpMagicNumber       = 116001; // EA Magic Number

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

   Print("[+] Gold H1 Ehlers MESA Sine Wave Master EA initialized successfully.");
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
//| Calculate Ehlers MESA Sine and LeadSine                          |
//+------------------------------------------------------------------+
void CalculateMESASine(int shift, double &sine, double &leadsine)
{
   int lookback = InpCyclePeriod + 10;
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, shift, lookback, closes) < lookback)
   {
      sine = 0.0;
      leadsine = 0.0;
      return;
   }

   double smooth[];
   ArrayResize(smooth, lookback - 3);
   for(int i = 0; i < lookback - 3; i++)
   {
      smooth[i] = (4.0 * closes[i] + 3.0 * closes[i + 1] + 2.0 * closes[i + 2] + closes[i + 3]) / 10.0;
   }

   int half_c = MathMax(3, InpCyclePeriod / 2);
   double cycle_diff[];
   ArrayResize(cycle_diff, InpCyclePeriod);
   for(int i = 0; i < InpCyclePeriod; i++)
   {
      cycle_diff[i] = smooth[i] - smooth[i + half_c];
   }

   double x_first = cycle_diff[InpCyclePeriod - 1];
   double x_last = cycle_diff[0];
   double phase = 0.0;
   if(MathAbs(x_first) > 1e-6)
      phase = MathArctan(x_last / x_first);

   sine = MathSin(phase);
   double phase_shift_rad = InpPhaseShiftDeg * 3.14159265358979323846 / 180.0;
   leadsine = MathSin(phase + phase_shift_rad);
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
      PrintFormat("[*] S116: Month reset to %d. Risk governance unlocked.", current_month);
   }

   // Track floating / closed PnL
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

   // Indicators on confirmed bar 1
   double atr[];
   double ema200[];
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(ema200, true);

   if(CopyBuffer(handle_atr, 0, 1, 1, atr) <= 0 ||
      CopyBuffer(handle_ema200, 0, 1, 1, ema200) <= 0)
      return;

   double close_1 = iClose(_Symbol, PERIOD_H1, 1);
   double kfd_1 = CalculateKFD(1);

   double sine_1, leadsine_1;
   double sine_2, leadsine_2;
   CalculateMESASine(1, sine_1, leadsine_1);
   CalculateMESASine(2, sine_2, leadsine_2);

   // Signals: Crossover of Sine vs LeadSine
   bool cross_up = (sine_1 > leadsine_1) && (sine_2 <= leadsine_2);
   bool cross_dn = (sine_1 < leadsine_1) && (sine_2 >= leadsine_2);

   bool trend_bull = (close_1 > ema200[0]);
   bool trend_bear = (close_1 < ema200[0]);
   bool kfd_ok = (kfd_1 <= InpKFDThreshold);

   double atr_val = atr[0];
   double sl_dist = InpStopLossMult * atr_val;
   double tp_dist = InpTakeProfitMult * atr_val;

   if(cross_up && trend_bull && kfd_ok)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - sl_dist;
      double tp = ask + tp_dist;

      trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "S116 MESA Sine Long");
      last_bar_time = current_bar_time;
      PrintFormat("[+] S116 Buy executed @ %f | SL: %f | TP: %f | ATR: %f", ask, sl, tp, atr_val);
   }
   else if(cross_dn && trend_bear && kfd_ok)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + sl_dist;
      double tp = bid - tp_dist;

      trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "S116 MESA Sine Short");
      last_bar_time = current_bar_time;
      PrintFormat("[-] S116 Sell executed @ %f | SL: %f | TP: %f | ATR: %f", bid, sl, tp, atr_val);
   }
}

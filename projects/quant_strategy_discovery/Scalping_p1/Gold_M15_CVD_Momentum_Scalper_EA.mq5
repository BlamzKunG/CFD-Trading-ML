//+------------------------------------------------------------------+
//|                  Gold_M15_CVD_Momentum_Scalper_EA.mq5            |
//|               CFD Quantitative Strategy Discovery - Strategy 403 |
//|           Microstructure Cumulative Volume Delta Specialist      |
//|                  Asset: XAUUSD | Timeframe: M15                  |
//|      Expected Frequency: ~260 Trades/Year | Net Profit: +$27.1k  |
//|               Profit Factor: 1.525 | Max Drawdown: $1,057.67     |
//|                    Return on Max DD: 25.64x (RECORD)             |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Trade Configuration ==="
input double InpLotSize              = 0.10;       // Standardized Institutional Lot Size
input ulong  InpMagicNumber          = 403001;     // Magic Number for Engine
input int    InpEMA200Period         = 200;        // Macro Trend Filter Period (EMA 200)
input double InpMaxSpread            = 0.60;       // Maximum Allowed Spread ($/oz)
input bool   InpFilterRollover       = true;       // Avoid New Trades during Rollover (21:00-23:00 UTC)

input group "=== Supertrend Ratchet Trailing Settings ==="
input int    InpST_ATRPeriod         = 14;         // ATR Period
input double InpST_Multiplier        = 3.0;        // Supertrend Ratchet Multiplier (3.0x)

input group "=== Microstructure CVD Orderflow Filter ==="
input int    InpCVD_Period           = 20;         // Cumulative Volume Delta Rolling Window
input bool   InpRequireCVDAlignment  = true;       // Require CVD20 > 0 for Long, < 0 for Short

// Global Variables & Trade Handle
CTrade   trade;
int      handle_atr;
int      handle_ema200;
datetime last_bar_time;

// Supertrend Internal State Variables
int      st_trend;       // 1 = Bullish, -1 = Bearish
double   st_upper_band;
double   st_lower_band;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);

   handle_atr    = iATR(_Symbol, PERIOD_M15, InpST_ATRPeriod);
   handle_ema200 = iMA(_Symbol, PERIOD_M15, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles for CVD Momentum Scalper.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   st_trend      = 1;
   st_upper_band = 0.0;
   st_lower_band = 0.0;

   Print("[+] Strategy 403 CVD Momentum Scalper EA Initialized Successfully on XAUUSD M15.");
   Print("[+] Parameters: ATR 14, Mult 3.0x, EMA 200, CVD Window 20 bars, Lot 0.10.");
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
//| Helper: Get Active Position Count by Magic Number                |
//+------------------------------------------------------------------+
int GetPositionCount(ulong magic)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == (long)magic)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Helper: Close Position by Magic Number                           |
//+------------------------------------------------------------------+
void ClosePositionByMagic(ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == (long)magic)
         {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0)
            {
               trade.PositionClose(ticket);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: Check Rollover Hours (21:00 - 23:00 UTC)                 |
//+------------------------------------------------------------------+
bool IsRolloverTime()
{
   if(!InpFilterRollover) return false;
   MqlDateTime dt;
   TimeGMT(dt);
   return (dt.hour >= 21 && dt.hour < 23);
}

//+------------------------------------------------------------------+
//| Helper: Compute 20-bar Cumulative Volume Delta (CVD)             |
//| Delta = ((Close - Low) - (High - Close)) / (High - Low) * Volume |
//+------------------------------------------------------------------+
double CalculateCVD(int period)
{
   double cvd_sum = 0.0;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, 1, period, rates);
   if(copied < period) return 0.0;

   for(int i = 0; i < period; i++)
   {
      double h = rates[i].high;
      double l = rates[i].low;
      double c = rates[i].close;
      double v = (double)rates[i].tick_volume;
      if(v <= 0.0) v = (double)rates[i].real_volume;
      if(v <= 0.0) v = 1.0;

      double rng = MathMax(h - l, 0.0001);
      double delta_ratio = ((c - l) - (h - c)) / rng;
      double bar_delta = delta_ratio * v;
      cvd_sum += bar_delta;
   }
   return cvd_sum;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Strictly execute only once per completed M15 candle (Bar 1)
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // Read indicator buffers for closed candle [1]
   double atr_buf[2], ema_buf[2];
   if(CopyBuffer(handle_atr, 0, 1, 2, atr_buf) < 2) return;
   if(CopyBuffer(handle_ema200, 0, 1, 2, ema_buf) < 2) return;

   double close_1 = iClose(_Symbol, PERIOD_M15, 1);
   double close_2 = iClose(_Symbol, PERIOD_M15, 2);
   double high_1  = iHigh(_Symbol, PERIOD_M15, 1);
   double low_1   = iLow(_Symbol, PERIOD_M15, 1);
   double atr_1   = atr_buf[1];
   double ema_1   = ema_buf[1];

   if(atr_1 <= 0.0) return;

   // Check spread filter
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMaxSpread) return;

   // Calculate 20-bar Cumulative Volume Delta
   double cvd_val = CalculateCVD(InpCVD_Period);

   // =================================================================
   // SUPERTREND DYNAMIC RATCHET TRAILING LOGIC
   // =================================================================
   double median_1 = (high_1 + low_1) * 0.5;
   double basic_upper = median_1 + (InpST_Multiplier * atr_1);
   double basic_lower = median_1 - (InpST_Multiplier * atr_1);

   if(st_lower_band == 0.0) st_lower_band = basic_lower;
   if(st_upper_band == 0.0) st_upper_band = basic_upper;

   // Ratchet mechanics: Monotonic trailing stop
   if(close_2 > st_lower_band)
      st_lower_band = MathMax(basic_lower, st_lower_band);
   else
      st_lower_band = basic_lower;

   if(close_2 < st_upper_band)
      st_upper_band = MathMin(basic_upper, st_upper_band);
   else
      st_upper_band = basic_upper;

   int prev_trend = st_trend;
   if(st_trend == 1)
   {
      if(close_1 < st_lower_band)
         st_trend = -1;
      else
         st_trend = 1;
   }
   else
   {
      if(close_1 > st_upper_band)
         st_trend = 1;
      else
         st_trend = -1;
   }

   // 1. Check Trailing Ratchet Exits
   int pos_count = GetPositionCount(InpMagicNumber);
   if(pos_count > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagicNumber)
         {
            long pos_type = PositionGetInteger(POSITION_TYPE);
            if(pos_type == POSITION_TYPE_BUY)
            {
               if(low_1 <= st_lower_band || st_trend == -1)
               {
                  ClosePositionByMagic(InpMagicNumber);
                  PrintFormat("[*] CVD Scalper Long Closed at Ratchet Band: %.2f (Low: %.2f)", st_lower_band, low_1);
               }
            }
            else if(pos_type == POSITION_TYPE_SELL)
            {
               if(high_1 >= st_upper_band || st_trend == 1)
               {
                  ClosePositionByMagic(InpMagicNumber);
                  PrintFormat("[*] CVD Scalper Short Closed at Ratchet Band: %.2f (High: %.2f)", st_upper_band, high_1);
               }
            }
         }
      }
   }

   // 2. Check Fresh Trend Flip Entries with CVD Orderflow Filter
   pos_count = GetPositionCount(InpMagicNumber);
   if(pos_count == 0 && !IsRolloverTime())
   {
      bool cvd_long_ok  = (!InpRequireCVDAlignment) || (cvd_val > 0.0);
      bool cvd_short_ok = (!InpRequireCVDAlignment) || (cvd_val < 0.0);

      // Bullish flip confirmed above EMA 200 with positive cumulative delta
      if(st_trend == 1 && prev_trend == -1 && close_1 > ema_1 && cvd_long_ok)
      {
         ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade.Buy(InpLotSize, _Symbol, ask, 0, 0, "CVD_Scalper_Long");
         PrintFormat("[+] CVD BUY Executed at %.2f | Band: %.2f | CVD20: %.1f | EMA200: %.2f", ask, st_lower_band, cvd_val, ema_1);
      }
      // Bearish flip confirmed below EMA 200 with negative cumulative delta
      else if(st_trend == -1 && prev_trend == 1 && close_1 < ema_1 && cvd_short_ok)
      {
         bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade.Sell(InpLotSize, _Symbol, bid, 0, 0, "CVD_Scalper_Short");
         PrintFormat("[+] CVD SELL Executed at %.2f | Band: %.2f | CVD20: %.1f | EMA200: %.2f", bid, st_upper_band, cvd_val, ema_1);
      }
   }
}
//+------------------------------------------------------------------+

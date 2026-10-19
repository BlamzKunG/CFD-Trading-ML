//+------------------------------------------------------------------+
//|                  Gold_M15_Solo_Supertrend_Scalper_EA.mq5         |
//|               CFD Quantitative Strategy Discovery - Strategy 291 |
//|                     Solo Trend Core Champion                     |
//|                  Asset: XAUUSD | Timeframe: M15                  |
//|      Expected Frequency: ~342 Trades/Year | Net Profit: +$30.6k  |
//|               Profit Factor: 1.440 | Max Drawdown: $1,680.04     |
//|                      Return on Max DD: 18.21x                    |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Trade Configuration ==="
input double InpLotSize              = 0.10;       // Standardized Institutional Lot Size
input ulong  InpMagicNumber          = 291001;     // Magic Number for Engine
input int    InpEMA200Period         = 200;        // Macro Trend Filter Period (EMA 200)
input double InpMaxSpread            = 0.60;       // Maximum Allowed Spread ($/oz)
input bool   InpFilterRollover       = true;       // Avoid New Trades during Rollover (21:00-23:00 UTC)

input group "=== Supertrend Ratchet Trailing Settings ==="
input int    InpST_ATRPeriod         = 14;         // ATR Period
input double InpST_Multiplier        = 3.0;        // Supertrend Ratchet Multiplier (Optimal: 3.0x)

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
      Print("[-] Error: Failed to initialize indicator handles for Solo Supertrend Scalper.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   st_trend      = 1;
   st_upper_band = 0.0;
   st_lower_band = 0.0;

   Print("[+] Strategy 291 Solo Supertrend Scalper EA Initialized Successfully on XAUUSD M15.");
   Print("[+] Parameters: ATR 14, Multiplier 3.0x, EMA 200 Trend Filter, Lot 0.10.");
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
   if(current_spread > InpMaxSpread)
   {
      PrintFormat("[!] Spread (%.2f) exceeds limit (%.2f). Skipping trade signals.", current_spread, InpMaxSpread);
      return;
   }

   // =================================================================
   // SUPERTREND DYNAMIC RATCHET TRAILING LOGIC
   // =================================================================
   double median_1 = (high_1 + low_1) * 0.5;
   double basic_upper = median_1 + (InpST_Multiplier * atr_1);
   double basic_lower = median_1 - (InpST_Multiplier * atr_1);

   if(st_lower_band == 0.0) st_lower_band = basic_lower;
   if(st_upper_band == 0.0) st_upper_band = basic_upper;

   // Ratchet mechanics: Monotonic trailing stop movement
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

   // 1. Check Trailing Ratchet Exits for Open Position
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
                  PrintFormat("[*] Supertrend Long Closed at Ratchet Band: %.2f (Low: %.2f)", st_lower_band, low_1);
               }
            }
            else if(pos_type == POSITION_TYPE_SELL)
            {
               if(high_1 >= st_upper_band || st_trend == 1)
               {
                  ClosePositionByMagic(InpMagicNumber);
                  PrintFormat("[*] Supertrend Short Closed at Ratchet Band: %.2f (High: %.2f)", st_upper_band, high_1);
               }
            }
         }
      }
   }

   // 2. Check Fresh Trend Flip Entries
   pos_count = GetPositionCount(InpMagicNumber);
   if(pos_count == 0 && !IsRolloverTime())
   {
      // Bullish flip confirmed above EMA 200
      if(st_trend == 1 && prev_trend == -1 && close_1 > ema_1)
      {
         ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade.Buy(InpLotSize, _Symbol, ask, 0, 0, "ST_Solo_Long");
         PrintFormat("[+] Solo Supertrend BUY Executed at %.2f | Band: %.2f | EMA200: %.2f", ask, st_lower_band, ema_1);
      }
      // Bearish flip confirmed below EMA 200
      else if(st_trend == -1 && prev_trend == 1 && close_1 < ema_1)
      {
         bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade.Sell(InpLotSize, _Symbol, bid, 0, 0, "ST_Solo_Short");
         PrintFormat("[+] Solo Supertrend SELL Executed at %.2f | Band: %.2f | EMA200: %.2f", bid, st_upper_band, ema_1);
      }
   }
}
//+------------------------------------------------------------------+

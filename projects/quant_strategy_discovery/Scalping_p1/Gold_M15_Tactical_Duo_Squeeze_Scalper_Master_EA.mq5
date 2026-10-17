//+------------------------------------------------------------------+
//|            Gold_M15_Tactical_Duo_Squeeze_Scalper_Master_EA.mq5   |
//|               CFD Quantitative Strategy Discovery - Strategy 296 |
//|        Tactical Duo B: Supertrend Trailing + TTM Squeeze Breakout|
//|                  Asset: XAUUSD | Timeframe: M15                  |
//|      Expected Frequency: ~536+ Trades/Year | Net Profit: +$37.5k |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Trade Configuration ==="
input double InpLotSize              = 0.10;       // Standardized Institutional Lot Size
input ulong  InpMagicSupertrend      = 296001;     // Magic Number: Supertrend Engine
input ulong  InpMagicTTMSqueeze      = 296002;     // Magic Number: TTM Squeeze Engine
input int    InpEMA200Period         = 200;        // Macro Trend Filter Period

input group "=== Sub-Engine 1: Supertrend Trailing Ratchet ==="
input bool   InpEnableSupertrend     = true;       // Enable Supertrend Engine
input int    InpST_ATRPeriod         = 14;         // ATR Period
input double InpST_Multiplier        = 3.0;        // Supertrend Ratchet Multiplier

input group "=== Sub-Engine 2: TTM Squeeze Volatility Breakout ==="
input bool   InpEnableTTMSqueeze     = true;       // Enable TTM Squeeze Engine
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // Bollinger Bands StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel ATR Multiplier
input int    InpMinSqueezeBars       = 8;          // Minimum Consecutive Squeeze Bars Required
input double InpSqueeze_SL_Mult      = 3.0;        // Stop Loss Distance (x ATR)
input double InpSqueeze_TP_Mult      = 3.0;        // Take Profit Distance (x ATR)

// Global Trade Handles & Variables
CTrade   trade_st;
CTrade   trade_ttm;
int      handle_atr;
int      handle_ema200;
int      handle_bb;
datetime last_bar_time;

// Supertrend Internal State Variables
int      st_trend;       // 1 = Bullish, -1 = Bearish
double   st_upper_band;
double   st_lower_band;

// TTM Squeeze State Variables
int      consecutive_squeeze_count = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_st.SetExpertMagicNumber(InpMagicSupertrend);
   trade_st.SetMarginMode();
   trade_st.SetTypeFillingBySymbol(_Symbol);

   trade_ttm.SetExpertMagicNumber(InpMagicTTMSqueeze);
   trade_ttm.SetMarginMode();
   trade_ttm.SetTypeFillingBySymbol(_Symbol);

   handle_atr    = iATR(_Symbol, PERIOD_M15, InpST_ATRPeriod);
   handle_ema200 = iMA(_Symbol, PERIOD_M15, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_bb     = iBands(_Symbol, PERIOD_M15, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE || handle_bb == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   st_trend      = 1;
   st_upper_band = 0.0;
   st_lower_band = 0.0;
   consecutive_squeeze_count = 0;

   Print("[+] Strategy 296 Tactical Duo Scalper EA Initialized Successfully on XAUUSD M15.");
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
               if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                  trade_st.PositionClose(ticket);
               else if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
                  trade_st.PositionClose(ticket);
            }
         }
      }
   }
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
   double atr_buf[2], ema_buf[2], bb_base[2], bb_upper[2], bb_lower[2];
   if(CopyBuffer(handle_atr, 0, 1, 2, atr_buf) < 2) return;
   if(CopyBuffer(handle_ema200, 0, 1, 2, ema_buf) < 2) return;
   if(CopyBuffer(handle_bb, 0, 1, 2, bb_base) < 2) return;
   if(CopyBuffer(handle_bb, 1, 1, 2, bb_upper) < 2) return;
   if(CopyBuffer(handle_bb, 2, 1, 2, bb_lower) < 2) return;

   double close_1 = iClose(_Symbol, PERIOD_M15, 1);
   double close_2 = iClose(_Symbol, PERIOD_M15, 2);
   double high_1  = iHigh(_Symbol, PERIOD_M15, 1);
   double low_1   = iLow(_Symbol, PERIOD_M15, 1);
   double atr_1   = atr_buf[1];
   double ema_1   = ema_buf[1];

   if(atr_1 <= 0.0) return;

   // =================================================================
   // SUB-ENGINE 1: SUPERTREND DYNAMIC RATCHET TRAILING
   // =================================================================
   if(InpEnableSupertrend)
   {
      double median_1 = (high_1 + low_1) * 0.5;
      double basic_upper = median_1 + (InpST_Multiplier * atr_1);
      double basic_lower = median_1 - (InpST_Multiplier * atr_1);

      if(st_lower_band == 0.0) st_lower_band = basic_lower;
      if(st_upper_band == 0.0) st_upper_band = basic_upper;

      // Ratchet mechanics
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

      // Check Exits for Supertrend Position
      int pos_st = GetPositionCount(InpMagicSupertrend);
      if(pos_st > 0)
      {
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagicSupertrend)
            {
               long pos_type = PositionGetInteger(POSITION_TYPE);
               if(pos_type == POSITION_TYPE_BUY)
               {
                  if(low_1 <= st_lower_band || st_trend == -1)
                     ClosePositionByMagic(InpMagicSupertrend);
               }
               else if(pos_type == POSITION_TYPE_SELL)
               {
                  if(high_1 >= st_upper_band || st_trend == 1)
                     ClosePositionByMagic(InpMagicSupertrend);
               }
            }
         }
      }

      // Check Entries for Supertrend on Fresh Trend Flip
      pos_st = GetPositionCount(InpMagicSupertrend);
      if(pos_st == 0)
      {
         if(st_trend == 1 && prev_trend == -1 && close_1 > ema_1)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade_st.Buy(InpLotSize, _Symbol, ask, 0, 0, "ST_Ratchet_Long");
         }
         else if(st_trend == -1 && prev_trend == 1 && close_1 < ema_1)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade_st.Sell(InpLotSize, _Symbol, bid, 0, 0, "ST_Ratchet_Short");
         }
      }
   }

   // =================================================================
   // SUB-ENGINE 2: TTM SQUEEZE VOLATILITY BREAKOUT
   // =================================================================
   if(InpEnableTTMSqueeze)
   {
      double kc_upper = bb_base[1] + (InpKC_Multiplier * atr_1);
      double kc_lower = bb_base[1] - (InpKC_Multiplier * atr_1);

      // Check if BB is inside KC (Squeeze is ACTIVE)
      bool is_squeezing = (bb_upper[1] <= kc_upper && bb_lower[1] >= kc_lower);
      bool squeeze_fired = false;

      if(is_squeezing)
      {
         consecutive_squeeze_count++;
      }
      else
      {
         // If was squeezing for >= InpMinSqueezeBars and now broke out
         if(consecutive_squeeze_count >= InpMinSqueezeBars)
         {
            squeeze_fired = true;
         }
         consecutive_squeeze_count = 0;
      }

      int pos_ttm = GetPositionCount(InpMagicTTMSqueeze);
      if(pos_ttm == 0 && squeeze_fired)
      {
         if(close_1 > bb_base[1] && close_1 > ema_1)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl_dist = InpSqueeze_SL_Mult * atr_1;
            double sl = ask - sl_dist;
            double tp = ask + (InpSqueeze_TP_Mult * sl_dist);
            trade_ttm.Buy(InpLotSize, _Symbol, ask, sl, tp, "TTM_Squeeze_Long");
         }
         else if(close_1 < bb_base[1] && close_1 < ema_1)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl_dist = InpSqueeze_SL_Mult * atr_1;
            double sl = bid + sl_dist;
            double tp = bid - (InpSqueeze_TP_Mult * sl_dist);
            trade_ttm.Sell(InpLotSize, _Symbol, bid, sl, tp, "TTM_Squeeze_Short");
         }
      }
   }
}
//+------------------------------------------------------------------+

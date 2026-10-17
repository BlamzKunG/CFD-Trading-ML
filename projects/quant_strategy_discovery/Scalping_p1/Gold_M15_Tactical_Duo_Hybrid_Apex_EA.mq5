//+------------------------------------------------------------------+
//|               Gold_M15_Tactical_Duo_Hybrid_Apex_EA.mq5           |
//|               CFD Quantitative Strategy Discovery - Strategy 389 |
//|           Tactical Scalper Duo B: Hybrid Market + Limit Apex     |
//|                  Asset: XAUUSD | Timeframe: M15                  |
//|      Expected Frequency: ~505 Trades/Year | Net Profit: +$38.2k  |
//|               Profit Factor: 1.279 | Max Drawdown: $4,148.83     |
//|               Return on Max DD: 9.22x (ALL-TIME RECORD)          |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Trade Configuration ==="
input double InpBaseLot              = 0.10;       // Standardized Base Lot Size
input ulong  InpMagicSupertrend      = 389001;     // Magic Number: Supertrend Market Engine
input ulong  InpMagicTTMLimit        = 389002;     // Magic Number: TTM Squeeze Limit Engine
input int    InpEMA200Period         = 200;        // Macro Trend Filter Period
input double InpMaxSpread            = 0.60;       // Maximum Allowed Spread ($/oz)
input bool   InpFilterRollover       = true;       // Avoid New Trades during Rollover (21:00-23:00 UTC)

input group "=== Dynamic Microstructure Volume Sizing ==="
input bool   InpEnableDynamicVol     = true;       // Enable Dynamic Volume Scaling (S409: 0.8x - 1.3x)
input int    InpVolEMAPeriod         = 20;         // Relative Volume EMA Period

input group "=== Sub-Engine 1: Supertrend Market Trailing ==="
input bool   InpEnableSupertrend     = true;       // Enable Supertrend Engine
input int    InpST_ATRPeriod         = 14;         // ATR Period
input double InpST_Multiplier        = 3.0;        // Supertrend Ratchet Multiplier (3.0x)

input group "=== Sub-Engine 2: TTM Squeeze Limit Pullback ==="
input bool   InpEnableTTMLimit       = true;       // Enable TTM Squeeze Limit Engine
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // Bollinger Bands StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel ATR Multiplier
input int    InpMinSqueezeBars       = 8;          // Minimum Consecutive Squeeze Bars Required
input double InpLimitPullbackATR     = 0.20;       // Limit Order Pullback Discount (x ATR)
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

   trade_ttm.SetExpertMagicNumber(InpMagicTTMLimit);
   trade_ttm.SetMarginMode();
   trade_ttm.SetTypeFillingBySymbol(_Symbol);

   handle_atr    = iATR(_Symbol, PERIOD_M15, InpST_ATRPeriod);
   handle_ema200 = iMA(_Symbol, PERIOD_M15, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_bb     = iBands(_Symbol, PERIOD_M15, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE || handle_bb == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles for Hybrid Apex EA.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   st_trend      = 1;
   st_upper_band = 0.0;
   st_lower_band = 0.0;
   consecutive_squeeze_count = 0;

   Print("[+] Strategy 389 Tactical Duo Hybrid Apex EA Initialized Successfully on XAUUSD M15.");
   Print("[+] Mechanics: Supertrend Market Breakout + TTM Squeeze Limit Pullback (-0.2x ATR).");
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
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)magic)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Helper: Cancel Pending Orders by Magic Number                    |
//+------------------------------------------------------------------+
void CancelPendingOrdersByMagic(ulong magic)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(OrderGetTicket(i) > 0)
      {
         if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == (long)magic)
         {
            trade_ttm.OrderDelete(OrderGetTicket(i));
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: Close Position by Magic Number                           |
//+------------------------------------------------------------------+
void ClosePositionByMagic(ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)magic)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0)
         {
            trade_st.PositionClose(ticket);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: Dynamic Lot Sizing based on Relative Volume (S409)       |
//+------------------------------------------------------------------+
double CalculateDynamicLot()
{
   if(!InpEnableDynamicVol) return InpBaseLot;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, 1, InpVolEMAPeriod + 5, rates);
   if(copied < InpVolEMAPeriod) return InpBaseLot;

   double vol_sum = 0.0;
   for(int i = 0; i < InpVolEMAPeriod; i++)
   {
      double v = (double)rates[i].tick_volume;
      if(v <= 0.0) v = (double)rates[i].real_volume;
      vol_sum += MathMax(v, 1.0);
   }
   double avg_vol = vol_sum / (double)InpVolEMAPeriod;
   double cur_vol = (double)rates[0].tick_volume;
   if(cur_vol <= 0.0) cur_vol = (double)rates[0].real_volume;

   double rel_vol = cur_vol / MathMax(avg_vol, 1.0);
   double scale = 1.0;

   // Scale between 0.8x and 1.3x
   if(rel_vol < 0.8) scale = 0.8;
   else if(rel_vol > 1.3) scale = 1.3;
   else scale = rel_vol;

   double raw_lot = InpBaseLot * scale;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   raw_lot = MathFloor(raw_lot / step) * step;
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   return MathMax(min_lot, MathMin(max_lot, raw_lot));
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

   // 1. Cancel unfulfilled pending limit orders from previous bar (15-min TTL)
   CancelPendingOrdersByMagic(InpMagicTTMLimit);

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

   // Spread check
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMaxSpread) return;

   double trade_lot = CalculateDynamicLot();

   // =================================================================
   // SUB-ENGINE 1: SUPERTREND MARKET TRAILING RATCHET
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

      // Check Market Entries for Supertrend on Fresh Trend Flip
      pos_st = GetPositionCount(InpMagicSupertrend);
      if(pos_st == 0 && !IsRolloverTime())
      {
         if(st_trend == 1 && prev_trend == -1 && close_1 > ema_1)
         {
            ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade_st.Buy(trade_lot, _Symbol, ask, 0, 0, "ST_Hybrid_Long");
            PrintFormat("[+] Hybrid Duo BUY (Market) at %.2f | Lot: %.2f | Band: %.2f", ask, trade_lot, st_lower_band);
         }
         else if(st_trend == -1 && prev_trend == 1 && close_1 < ema_1)
         {
            bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade_st.Sell(trade_lot, _Symbol, bid, 0, 0, "ST_Hybrid_Short");
            PrintFormat("[+] Hybrid Duo SELL (Market) at %.2f | Lot: %.2f | Band: %.2f", bid, trade_lot, st_upper_band);
         }
      }
   }

   // =================================================================
   // SUB-ENGINE 2: TTM SQUEEZE LIMIT PULLBACK BREAKOUT (-0.2x ATR)
   // =================================================================
   if(InpEnableTTMLimit)
   {
      double kc_upper = bb_base[1] + (InpKC_Multiplier * atr_1);
      double kc_lower = bb_base[1] - (InpKC_Multiplier * atr_1);

      bool is_squeezing = (bb_upper[1] <= kc_upper && bb_lower[1] >= kc_lower);
      bool squeeze_fired = false;

      if(is_squeezing)
      {
         consecutive_squeeze_count++;
      }
      else
      {
         if(consecutive_squeeze_count >= InpMinSqueezeBars)
         {
            squeeze_fired = true;
         }
         consecutive_squeeze_count = 0;
      }

      int pos_ttm = GetPositionCount(InpMagicTTMLimit);
      if(pos_ttm == 0 && squeeze_fired && !IsRolloverTime())
      {
         datetime order_expiry = TimeCurrent() + (PeriodSeconds(PERIOD_M15) * 2);

         if(close_1 > bb_base[1] && close_1 > ema_1)
         {
            ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            // Place Limit Order at discount: Open/Ask - 0.20 ATR
            double limit_price = NormalizeDouble(ask - (InpLimitPullbackATR * atr_1), _Digits);
            double sl_dist = InpSqueeze_SL_Mult * atr_1;
            double sl = NormalizeDouble(limit_price - sl_dist, _Digits);
            double tp = NormalizeDouble(limit_price + (InpSqueeze_TP_Mult * sl_dist), _Digits);

            trade_ttm.BuyLimit(trade_lot, limit_price, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, order_expiry, "TTM_Limit_Long");
            PrintFormat("[+] TTM Limit Buy Placed at %.2f (-0.2 ATR discount) | SL: %.2f | TP: %.2f", limit_price, sl, tp);
         }
         else if(close_1 < bb_base[1] && close_1 < ema_1)
         {
            bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            // Place Limit Order at discount: Bid + 0.20 ATR
            double limit_price = NormalizeDouble(bid + (InpLimitPullbackATR * atr_1), _Digits);
            double sl_dist = InpSqueeze_SL_Mult * atr_1;
            double sl = NormalizeDouble(limit_price + sl_dist, _Digits);
            double tp = NormalizeDouble(limit_price - (InpSqueeze_TP_Mult * sl_dist), _Digits);

            trade_ttm.SellLimit(trade_lot, limit_price, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, order_expiry, "TTM_Limit_Short");
            PrintFormat("[+] TTM Limit Sell Placed at %.2f (+0.2 ATR discount) | SL: %.2f | TP: %.2f", limit_price, sl, tp);
         }
      }
   }
}
//+------------------------------------------------------------------+

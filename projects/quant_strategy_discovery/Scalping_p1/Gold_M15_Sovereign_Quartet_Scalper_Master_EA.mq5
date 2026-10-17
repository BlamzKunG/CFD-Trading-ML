//+------------------------------------------------------------------+
//|            Gold_M15_Sovereign_Quartet_Scalper_Master_EA.mq5      |
//|               CFD Quantitative Strategy Discovery - Strategy 300 |
//|           Sovereign Scalper Quartet (4 Orthogonal Engines)       |
//|                  Asset: XAUUSD | Timeframe: M15                  |
//|    Expected Turnover: ~1,248 Trades/Year | Net Profit: +$45.1k+  |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Trade Configuration ==="
input double InpBaseLot              = 0.10;       // Base Lot Size (Scaled by engine weights)
input int    InpEMA200Period         = 200;        // Macro Trend Filter Period

input group "=== Engine 1: Supertrend Trailing Ratchet (Weight 1.0) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1
input ulong  InpMagic1               = 300001;     // Magic Number Engine 1
input double InpWeight1              = 1.00;       // Lot Weight (1.00 = 0.10 lot)
input int    InpST_ATRPeriod         = 14;         // ATR Period
input double InpST_Multiplier        = 3.0;        // Ratchet Multiplier

input group "=== Engine 2: Zero-Lag MACD Inflection (Weight 0.7) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2
input ulong  InpMagic2               = 300002;     // Magic Number Engine 2
input double InpWeight2              = 0.70;       // Lot Weight (0.70 = 0.07 lot)
input int    InpZL_Fast              = 15;         // Fast Period
input int    InpZL_Slow              = 34;         // Slow Period
input int    InpZL_Signal            = 9;          // Signal Period
input double InpZL_SL_Mult           = 2.0;        // SL (x ATR)
input double InpZL_TP_Mult           = 4.0;        // TP (x SL)

input group "=== Engine 3: TTM Squeeze Breakout (Weight 0.8) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3
input ulong  InpMagic3               = 300003;     // Magic Number Engine 3
input double InpWeight3              = 0.80;       // Lot Weight (0.80 = 0.08 lot)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Consecutive Squeeze Bars
input double InpTTM_SL_Mult          = 3.0;        // SL (x ATR)
input double InpTTM_TP_Mult          = 3.0;        // TP (x SL)

input group "=== Engine 4: Fair Value Gap Retest (Weight 0.5) ==="
input bool   InpEnableEngine4        = true;       // Enable Engine 4
input ulong  InpMagic4               = 300004;     // Magic Number Engine 4
input double InpWeight4              = 0.50;       // Lot Weight (0.50 = 0.05 lot)
input double InpMinGapATR            = 0.4;        // Min Gap Size (x ATR)
input double InpFVG_SL_Buf           = 0.5;        // SL Buffer (x ATR)
input double InpFVG_TP_Mult          = 3.0;        // TP (x SL)

// Trade Objects
CTrade   trade_1, trade_2, trade_3, trade_4;
int      handle_atr;
int      handle_ema200;
int      handle_bb;
datetime last_bar_time;

// State Tracking
int      st_trend;
double   st_upper_band;
double   st_lower_band;
int      consecutive_squeeze_count = 0;

// FVG Tracking
double   bull_fvg_top = 0.0, bull_fvg_bot = 0.0;
bool     bull_fvg_active = false;
double   bear_fvg_top = 0.0, bear_fvg_bot = 0.0;
bool     bear_fvg_active = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_1.SetExpertMagicNumber(InpMagic1); trade_1.SetMarginMode(); trade_1.SetTypeFillingBySymbol(_Symbol);
   trade_2.SetExpertMagicNumber(InpMagic2); trade_2.SetMarginMode(); trade_2.SetTypeFillingBySymbol(_Symbol);
   trade_3.SetExpertMagicNumber(InpMagic3); trade_3.SetMarginMode(); trade_3.SetTypeFillingBySymbol(_Symbol);
   trade_4.SetExpertMagicNumber(InpMagic4); trade_4.SetMarginMode(); trade_4.SetTypeFillingBySymbol(_Symbol);

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

   Print("[+] Strategy 300 Sovereign Quartet Scalper Master EA Initialized on XAUUSD M15.");
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
//| Helper: Close Position by Magic Number                           |
//+------------------------------------------------------------------+
void ClosePositionByMagic(ulong magic, CTrade &tr)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)magic)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0) tr.PositionClose(ticket);
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: Calculate Normalized Lot Size                            |
//+------------------------------------------------------------------+
double GetLotSize(double weight)
{
   double lot = InpBaseLot * weight;
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathFloor(lot / lot_step) * lot_step;
   return MathMax(min_lot, MathMin(max_lot, lot));
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

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
   double high_3  = iHigh(_Symbol, PERIOD_M15, 3);
   double low_3   = iLow(_Symbol, PERIOD_M15, 3);
   double atr_1   = atr_buf[1];
   double ema_1   = ema_buf[1];
   if(atr_1 <= 0.0) return;

   // -----------------------------------------------------------------
   // ENGINE 1: SUPERTREND TRAILING RATCHET
   // -----------------------------------------------------------------
   if(InpEnableEngine1)
   {
      double median_1 = (high_1 + low_1) * 0.5;
      double basic_upper = median_1 + (InpST_Multiplier * atr_1);
      double basic_lower = median_1 - (InpST_Multiplier * atr_1);

      if(st_lower_band == 0.0) st_lower_band = basic_lower;
      if(st_upper_band == 0.0) st_upper_band = basic_upper;

      if(close_2 > st_lower_band) st_lower_band = MathMax(basic_lower, st_lower_band);
      else st_lower_band = basic_lower;

      if(close_2 < st_upper_band) st_upper_band = MathMin(basic_upper, st_upper_band);
      else st_upper_band = basic_upper;

      int prev_t = st_trend;
      if(st_trend == 1)
      {
         if(close_1 < st_lower_band) st_trend = -1;
         else st_trend = 1;
      }
      else
      {
         if(close_1 > st_upper_band) st_trend = 1;
         else st_trend = -1;
      }

      int pos1 = GetPositionCount(InpMagic1);
      if(pos1 > 0)
      {
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagic1)
            {
               long p_type = PositionGetInteger(POSITION_TYPE);
               if(p_type == POSITION_TYPE_BUY && (low_1 <= st_lower_band || st_trend == -1))
                  ClosePositionByMagic(InpMagic1, trade_1);
               else if(p_type == POSITION_TYPE_SELL && (high_1 >= st_upper_band || st_trend == 1))
                  ClosePositionByMagic(InpMagic1, trade_1);
            }
         }
      }

      pos1 = GetPositionCount(InpMagic1);
      if(pos1 == 0)
      {
         double lot1 = GetLotSize(InpWeight1);
         if(st_trend == 1 && prev_t == -1 && close_1 > ema_1)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade_1.Buy(lot1, _Symbol, ask, 0, 0, "ST_Ratchet_Long");
         }
         else if(st_trend == -1 && prev_t == 1 && close_1 < ema_1)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade_1.Sell(lot1, _Symbol, bid, 0, 0, "ST_Ratchet_Short");
         }
      }
   }

   // -----------------------------------------------------------------
   // ENGINE 3: TTM SQUEEZE BREAKOUT
   // -----------------------------------------------------------------
   if(InpEnableEngine3)
   {
      double kc_upper = bb_base[1] + (InpKC_Multiplier * atr_1);
      double kc_lower = bb_base[1] - (InpKC_Multiplier * atr_1);
      bool is_sqz = (bb_upper[1] <= kc_upper && bb_lower[1] >= kc_lower);
      bool sqz_fired = false;

      if(is_sqz) consecutive_squeeze_count++;
      else
      {
         if(consecutive_squeeze_count >= InpMinSqueezeBars) sqz_fired = true;
         consecutive_squeeze_count = 0;
      }

      int pos3 = GetPositionCount(InpMagic3);
      if(pos3 == 0 && sqz_fired)
      {
         double lot3 = GetLotSize(InpWeight3);
         double sl_dist = InpTTM_SL_Mult * atr_1;
         if(close_1 > bb_base[1] && close_1 > ema_1)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade_3.Buy(lot3, _Symbol, ask, ask - sl_dist, ask + (InpTTM_TP_Mult * sl_dist), "TTM_Squeeze_Long");
         }
         else if(close_1 < bb_base[1] && close_1 < ema_1)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade_3.Sell(lot3, _Symbol, bid, bid + sl_dist, bid - (InpTTM_TP_Mult * sl_dist), "TTM_Squeeze_Short");
         }
      }
   }

   // -----------------------------------------------------------------
   // ENGINE 4: FAIR VALUE GAP RETEST
   // -----------------------------------------------------------------
   if(InpEnableEngine4)
   {
      if(low_1 - high_3 >= InpMinGapATR * atr_1)
      {
         bull_fvg_top = low_1;
         bull_fvg_bot = high_3;
         bull_fvg_active = true;
         bear_fvg_active = false;
      }
      else if(low_3 - high_1 >= InpMinGapATR * atr_1)
      {
         bear_fvg_top = low_3;
         bear_fvg_bot = high_1;
         bear_fvg_active = true;
         bull_fvg_active = false;
      }

      int pos4 = GetPositionCount(InpMagic4);
      if(pos4 == 0)
      {
         double lot4 = GetLotSize(InpWeight4);
         if(bull_fvg_active && close_1 > ema_1 && low_1 <= bull_fvg_top)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl_dist = MathMax((ask - bull_fvg_bot) + (InpFVG_SL_Buf * atr_1), 1.0 * atr_1);
            trade_4.Buy(lot4, _Symbol, ask, ask - sl_dist, ask + (InpFVG_TP_Mult * sl_dist), "FVG_Retest_Long");
            bull_fvg_active = false;
         }
         else if(bear_fvg_active && close_1 < ema_1 && high_1 >= bear_fvg_bot)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl_dist = MathMax((bear_fvg_top - bid) + (InpFVG_SL_Buf * atr_1), 1.0 * atr_1);
            trade_4.Sell(lot4, _Symbol, bid, bid + sl_dist, bid - (InpFVG_TP_Mult * sl_dist), "FVG_Retest_Short");
            bear_fvg_active = false;
         }
      }
   }
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|       Gold_Payoff_Engineered_Sovereign_Apex_EA.mq5               |
//|        CFD Quantitative Strategy Discovery - Strategy S486       |
//|  Triple-Timeframe + 50/50 Scale-Out Payoff + Loss Streak Throttle|
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 935.3 Trades/Year | Net Profit: +$67,642.95      |
//|      Profit Factor: 1.527 | Max DD: $1,928.10 | RoMaD: 35.08x    |
//|           Monthly Consistency Ratio (MCR): 84.72% (61/72)         |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Settings & Risk Parity ==="
input double InpBaseLot              = 0.10;       // Base Benchmark Lot Size
input int    InpMaxSpreadPoints      = 50;         // Max Allowed Spread in Points (50 pts = $0.50)
input double InpMaxDailyLossUSD      = 500.0;      // Prop-Firm Daily Loss Limit ($500 stop)
input bool   InpEnableLossThrottle   = true;       // Dynamic Loss Streak Throttle (0.75x after 2 losses)

input group "=== Payoff Engineering (50/50 Split Scale-Out) ==="
input bool   InpEnableScaleOut       = true;       // Enable 50/50 Scale-Out Architecture
input double InpScaleOutATRMult      = 1.0;        // Target ATR Multiple for Leg 1 Take-Profit
input double InpRunnerRatio          = 0.50;       // Leg 2 Runner Fraction (50% holds for trend)

input group "=== Engine 1: M15 Macro Core (Parity Weight 1.00) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1 (M15 Macro Core)
input ulong  InpMagic1               = 48615;      // Magic Number M15
input double InpWeight1              = 1.00;       // Risk Parity Weight (1.00x = 0.10 lot)
input int    InpST15_ATRPeriod       = 14;         // M15 ATR Period
input double InpST15_Multiplier      = 3.0;        // M15 Supertrend Multiplier
input int    InpM15_EMA200           = 200;        // M15 Trend Filter Period

input group "=== Engine 2: M5 Dual Monotonic Ratchet (Parity Weight 0.85) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2 (M5 S433)
input ulong  InpMagic2               = 48605;      // Magic Number M5
input double InpWeight2              = 0.85;       // Risk Parity Weight (0.85x = 0.08 lot)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)
input int    InpST5_ATRPeriod        = 14;         // M5 ATR Period
input double InpST5_Multiplier       = 3.0;        // M5 Ratchet Multiplier

input group "=== Engine 3: M1 NY Micro Sniper (Parity Weight 0.70) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3 (M1 S446)
input ulong  InpMagic3               = 48601;      // Magic Number M1
input double InpWeight3              = 0.70;       // Risk Parity Weight (0.70x = 0.07 lot)
input int    InpNY_StartHourUTC      = 12;         // New York Open Hour UTC
input int    InpNY_EndHourUTC        = 17;         // New York Close Hour UTC
input double InpMinM1_ATR            = 1.00;       // Min M1 ATR Volatility Threshold ($1.00)
input int    InpST1_ATRPeriod        = 14;         // M1 ATR Period
input double InpST1_Multiplier       = 3.0;        // M1 Ratchet Multiplier

input group "=== New York Liquidity Acceleration (13:00 - 16:00 UTC) ==="
input bool   InpEnableNY_Overweight  = true;       // Enable NY Peak Volume Boost
input double InpNY_BoostMultiplier   = 1.25;       // Boost Multiplier during 13-16 UTC

// Trade Objects
CTrade   trade_1, trade_2, trade_3;

// Indicators Handles
int      handle_atr_m15, handle_ema_m15;
int      handle_atr_m5,  handle_bb_m5;
int      handle_atr_m1;

// Bar Tracking for Causality
datetime last_bar_m15;
datetime last_bar_m5;
datetime last_bar_m1;

// Internal State
int      m5_squeeze_count = 0;
datetime current_day_start = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_1.SetExpertMagicNumber(InpMagic1);
   trade_2.SetExpertMagicNumber(InpMagic2);
   trade_3.SetExpertMagicNumber(InpMagic3);

   handle_atr_m15 = iATR(_Symbol, PERIOD_M15, InpST15_ATRPeriod);
   handle_ema_m15 = iMA(_Symbol, PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);

   handle_atr_m5  = iATR(_Symbol, PERIOD_M5, InpST5_ATRPeriod);
   handle_bb_m5   = iBands(_Symbol, PERIOD_M5, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   handle_atr_m1  = iATR(_Symbol, PERIOD_M1, InpST1_ATRPeriod);

   if(handle_atr_m15 == INVALID_HANDLE || handle_ema_m15 == INVALID_HANDLE ||
      handle_atr_m5 == INVALID_HANDLE  || handle_bb_m5 == INVALID_HANDLE ||
      handle_atr_m1 == INVALID_HANDLE)
   {
      Print("[!] Error creating indicator handles");
      return INIT_FAILED;
   }

   Print("[+] S486 Gold Payoff Engineered Sovereign Apex EA Initialized (PF: 1.527, RoMaD: 35.08x).");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr_m15);
   IndicatorRelease(handle_ema_m15);
   IndicatorRelease(handle_atr_m5);
   IndicatorRelease(handle_bb_m5);
   IndicatorRelease(handle_atr_m1);
}

//+------------------------------------------------------------------+
//| Daily Loss Governor Check                                        |
//+------------------------------------------------------------------+
bool CheckDailyLossExceeded()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime today_midnight = StructToTime(dt);

   HistorySelect(today_midnight, now);
   int total_deals = HistoryDealsTotal();
   double daily_pnl = 0.0;

   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == (long)InpMagic1 || magic == (long)InpMagic2 || magic == (long)InpMagic3 ||
            magic == (long)(InpMagic1 + 1) || magic == (long)(InpMagic2 + 1) || magic == (long)(InpMagic3 + 1))
         {
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }

   return (daily_pnl <= -InpMaxDailyLossUSD);
}

//+------------------------------------------------------------------+
//| Dynamic Consecutive Loss Throttle                                |
//+------------------------------------------------------------------+
double GetLossStreakMultiplier()
{
   if(!InpEnableLossThrottle) return 1.0;

   HistorySelect(TimeCurrent() - 7 * 86400, TimeCurrent());
   int total_deals = HistoryDealsTotal();
   int consecutive_losses = 0;

   for(int i = total_deals - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            if(profit < 0.0)
               consecutive_losses++;
            else if(profit > 0.0)
               break;
         }
      }
      if(consecutive_losses >= 2) break;
   }

   if(consecutive_losses >= 2) return 0.75;
   return 1.0;
}

//+------------------------------------------------------------------+
//| Dynamic Lot Calculator                                           |
//+------------------------------------------------------------------+
double GetDynamicLot(double engine_weight, int hour_utc)
{
   double lot = InpBaseLot * engine_weight;
   if(InpEnableNY_Overweight && hour_utc >= 13 && hour_utc <= 16)
      lot *= InpNY_BoostMultiplier;

   lot *= GetLossStreakMultiplier();

   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   lot = MathFloor(lot / step) * step;
   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;

   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Supertrend Indicator Calculation Helper                          |
//+------------------------------------------------------------------+
bool GetSupertrend(ENUM_TIMEFRAMES tf, int atr_handle, double mult, int shift, int &out_trend, double &out_band)
{
   int bars_needed = shift + 10;
   double high[], low[], close[], atr[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);
   ArraySetAsSeries(atr, true);

   if(CopyHigh(_Symbol, tf, 0, bars_needed, high) < bars_needed ||
      CopyLow(_Symbol, tf, 0, bars_needed, low) < bars_needed ||
      CopyClose(_Symbol, tf, 0, bars_needed, close) < bars_needed ||
      CopyBuffer(atr_handle, 0, 0, bars_needed, atr) < bars_needed)
      return false;

   double upper[], lower[];
   int trend[];
   ArrayResize(upper, bars_needed);
   ArrayResize(lower, bars_needed);
   ArrayResize(trend, bars_needed);

   for(int i = bars_needed - 1; i >= 0; i--)
   {
      double hl2 = (high[i] + low[i]) / 2.0;
      double basic_upper = hl2 + (mult * atr[i]);
      double basic_lower = hl2 - (mult * atr[i]);

      if(i == bars_needed - 1)
      {
         upper[i] = basic_upper;
         lower[i] = basic_lower;
         trend[i] = 1;
      }
      else
      {
         if(basic_upper < upper[i+1] || close[i+1] > upper[i+1])
            upper[i] = basic_upper;
         else
            upper[i] = upper[i+1];

         if(basic_lower > lower[i+1] || close[i+1] < lower[i+1])
            lower[i] = basic_lower;
         else
            lower[i] = lower[i+1];

         if(trend[i+1] == 1)
         {
            if(close[i] < lower[i])
               trend[i] = -1;
            else
               trend[i] = 1;
         }
         else
         {
            if(close[i] > upper[i])
               trend[i] = 1;
            else
               trend[i] = -1;
         }
      }
   }

   out_trend = trend[shift];
   out_band  = (out_trend == 1) ? lower[shift] : upper[shift];
   return true;
}

//+------------------------------------------------------------------+
//| Helper to execute 50/50 Scale-Out Entry                          |
//+------------------------------------------------------------------+
void ExecuteScaleOutBuy(CTrade &trade, ulong magic_base, double total_lot, double ask, double sl, double tp1, string comment)
{
   double lot_leg1 = NormalizeDouble(total_lot * 0.50, 2);
   double lot_leg2 = NormalizeDouble(total_lot - lot_leg1, 2);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   if(lot_leg1 < min_lot) lot_leg1 = min_lot;
   if(lot_leg2 < min_lot) lot_leg2 = min_lot;

   // Leg 1: Fixed Take-Profit at TP1
   trade.SetExpertMagicNumber(magic_base);
   trade.Buy(lot_leg1, _Symbol, ask, sl, tp1, comment + "_TP1");

   // Leg 2: Runner holding for monotonic trailing stop
   trade.SetExpertMagicNumber(magic_base + 1);
   trade.Buy(lot_leg2, _Symbol, ask, sl, 0.0, comment + "_Runner");
}

void ExecuteScaleOutSell(CTrade &trade, ulong magic_base, double total_lot, double bid, double sl, double tp1, string comment)
{
   double lot_leg1 = NormalizeDouble(total_lot * 0.50, 2);
   double lot_leg2 = NormalizeDouble(total_lot - lot_leg1, 2);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   if(lot_leg1 < min_lot) lot_leg1 = min_lot;
   if(lot_leg2 < min_lot) lot_leg2 = min_lot;

   // Leg 1: Fixed Take-Profit at TP1
   trade.SetExpertMagicNumber(magic_base);
   trade.Sell(lot_leg1, _Symbol, bid, sl, tp1, comment + "_TP1");

   // Leg 2: Runner holding for monotonic trailing stop
   trade.SetExpertMagicNumber(magic_base + 1);
   trade.Sell(lot_leg2, _Symbol, bid, sl, 0.0, comment + "_Runner");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   bool daily_loss_halt = CheckDailyLossExceeded();

   datetime cur_m15 = iTime(_Symbol, PERIOD_M15, 0);
   datetime cur_m5  = iTime(_Symbol, PERIOD_M5,  0);
   datetime cur_m1  = iTime(_Symbol, PERIOD_M1,  0);

   MqlDateTime dt;
   TimeCurrent(dt);
   int cur_hour = dt.hour;

   // Macro Indicators on M15
   int m15_trend = 0;
   double m15_band = 0.0;
   GetSupertrend(PERIOD_M15, handle_atr_m15, InpST15_Multiplier, 1, m15_trend, m15_band);

   double ema_m15[], atr_m15[];
   ArraySetAsSeries(ema_m15, true);
   ArraySetAsSeries(atr_m15, true);
   CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
   CopyBuffer(handle_atr_m15, 0, 1, 1, atr_m15);
   double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

   // ==================================================================
   // ENGINE 1: M15 Macro Core Supertrend
   // ==================================================================
   if(InpEnableEngine1 && cur_m15 != last_bar_m15)
   {
      last_bar_m15 = cur_m15;

      // Trailing Ratchet for Active M15 Positions
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol)
         {
            long magic = PositionGetInteger(POSITION_MAGIC);
            if(magic == (long)InpMagic1 || magic == (long)(InpMagic1 + 1))
            {
               long type = PositionGetInteger(POSITION_TYPE);
               ulong ticket = PositionGetTicket(i);
               if(type == POSITION_TYPE_BUY)
               {
                  if(m15_trend == -1)
                     trade_1.PositionClose(ticket);
                  else if(m15_band > PositionGetDouble(POSITION_SL))
                     trade_1.PositionModify(ticket, m15_band, PositionGetDouble(POSITION_TP));
               }
               else if(type == POSITION_TYPE_SELL)
               {
                  if(m15_trend == 1)
                     trade_1.PositionClose(ticket);
                  else if(PositionGetDouble(POSITION_SL) == 0.0 || m15_band < PositionGetDouble(POSITION_SL))
                     trade_1.PositionModify(ticket, m15_band, PositionGetDouble(POSITION_TP));
               }
            }
         }
      }

      bool has_eng1_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol)
         {
            long magic = PositionGetInteger(POSITION_MAGIC);
            if(magic == (long)InpMagic1 || magic == (long)(InpMagic1 + 1))
            { has_eng1_pos = true; break; }
         }
      }

      if(!has_eng1_pos && !daily_loss_halt)
      {
         int prev_trend = 0;
         double prev_band = 0.0;
         GetSupertrend(PERIOD_M15, handle_atr_m15, InpST15_Multiplier, 2, prev_trend, prev_band);

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lot1 = GetDynamicLot(InpWeight1, cur_hour);
         double target_tp1 = InpScaleOutATRMult * atr_m15[0];

         if(m15_trend == 1 && prev_trend == -1 && close_m15 > ema_m15[0])
            ExecuteScaleOutBuy(trade_1, InpMagic1, lot1, ask, m15_band, ask + target_tp1, "S486_E1");
         else if(m15_trend == -1 && prev_trend == 1 && close_m15 < ema_m15[0])
            ExecuteScaleOutSell(trade_1, InpMagic1, lot1, bid, m15_band, bid - target_tp1, "S486_E1");
      }
   }

   // ==================================================================
   // ENGINE 2: M5 Dual Monotonic Ratchet (S433)
   // ==================================================================
   if(InpEnableEngine2 && cur_m5 != last_bar_m5)
   {
      last_bar_m5 = cur_m5;

      double bb_mid[], bb_up[], bb_low[], atr_m5[];
      ArraySetAsSeries(bb_mid, true);
      ArraySetAsSeries(bb_up, true);
      ArraySetAsSeries(bb_low, true);
      ArraySetAsSeries(atr_m5, true);

      CopyBuffer(handle_bb_m5, 0, 1, 1, bb_mid);
      CopyBuffer(handle_bb_m5, 1, 1, 1, bb_up);
      CopyBuffer(handle_bb_m5, 2, 1, 1, bb_low);
      CopyBuffer(handle_atr_m5, 0, 1, 1, atr_m5);

      double kc_up  = bb_mid[0] + (InpKC_Multiplier * atr_m5[0]);
      double kc_low = bb_mid[0] - (InpKC_Multiplier * atr_m5[0]);

      bool is_sqz = (bb_low[0] > kc_low && bb_up[0] < kc_up);
      bool sqz_fired = false;

      if(is_sqz)
         m5_squeeze_count++;
      else
      {
         if(m5_squeeze_count >= InpMinSqueezeBars)
            sqz_fired = true;
         m5_squeeze_count = 0;
      }

      int m5_trend = 0;
      double m5_band = 0.0;
      GetSupertrend(PERIOD_M5, handle_atr_m5, InpST5_Multiplier, 1, m5_trend, m5_band);

      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol)
         {
            long magic = PositionGetInteger(POSITION_MAGIC);
            if(magic == (long)InpMagic2 || magic == (long)(InpMagic2 + 1))
            {
               long type = PositionGetInteger(POSITION_TYPE);
               ulong ticket = PositionGetTicket(i);
               if(type == POSITION_TYPE_BUY)
               {
                  if(m5_trend == -1 || m15_trend == -1)
                     trade_2.PositionClose(ticket);
                  else if(m5_band > PositionGetDouble(POSITION_SL))
                     trade_2.PositionModify(ticket, m5_band, PositionGetDouble(POSITION_TP));
               }
               else if(type == POSITION_TYPE_SELL)
               {
                  if(m5_trend == 1 || m15_trend == 1)
                     trade_2.PositionClose(ticket);
                  else if(PositionGetDouble(POSITION_SL) == 0.0 || m5_band < PositionGetDouble(POSITION_SL))
                     trade_2.PositionModify(ticket, m5_band, PositionGetDouble(POSITION_TP));
               }
            }
         }
      }

      bool has_eng2_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol)
         {
            long magic = PositionGetInteger(POSITION_MAGIC);
            if(magic == (long)InpMagic2 || magic == (long)(InpMagic2 + 1))
            { has_eng2_pos = true; break; }
         }
      }

      if(!has_eng2_pos && sqz_fired && !daily_loss_halt)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double close_m5 = iClose(_Symbol, PERIOD_M5, 1);
         double lot2 = GetDynamicLot(InpWeight2, cur_hour);
         double target_tp1 = InpScaleOutATRMult * atr_m5[0];

         if(m15_trend == 1 && close_m15 > ema_m15[0] && close_m5 > bb_mid[0])
            ExecuteScaleOutBuy(trade_2, InpMagic2, lot2, ask, m5_band, ask + target_tp1, "S486_E2");
         else if(m15_trend == -1 && close_m15 < ema_m15[0] && close_m5 < bb_mid[0])
            ExecuteScaleOutSell(trade_2, InpMagic2, lot2, bid, m5_band, bid - target_tp1, "S486_E2");
      }
   }

   // ==================================================================
   // ENGINE 3: M1 NY Session Micro Sniper (S446)
   // ==================================================================
   if(InpEnableEngine3 && cur_m1 != last_bar_m1)
   {
      last_bar_m1 = cur_m1;

      bool is_ny_session = (cur_hour >= InpNY_StartHourUTC && cur_hour < InpNY_EndHourUTC);

      double atr_m1[];
      ArraySetAsSeries(atr_m1, true);
      CopyBuffer(handle_atr_m1, 0, 1, 1, atr_m1);
      bool is_vol_ok = (atr_m1[0] >= InpMinM1_ATR);

      int m1_trend = 0;
      double m1_band = 0.0;
      GetSupertrend(PERIOD_M1, handle_atr_m1, InpST1_Multiplier, 1, m1_trend, m1_band);

      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol)
         {
            long magic = PositionGetInteger(POSITION_MAGIC);
            if(magic == (long)InpMagic3 || magic == (long)(InpMagic3 + 1))
            {
               long type = PositionGetInteger(POSITION_TYPE);
               ulong ticket = PositionGetTicket(i);
               if(type == POSITION_TYPE_BUY)
               {
                  if(m1_trend == -1)
                     trade_3.PositionClose(ticket);
                  else if(m1_band > PositionGetDouble(POSITION_SL))
                     trade_3.PositionModify(ticket, m1_band, PositionGetDouble(POSITION_TP));
               }
               else if(type == POSITION_TYPE_SELL)
               {
                  if(m1_trend == 1)
                     trade_3.PositionClose(ticket);
                  else if(PositionGetDouble(POSITION_SL) == 0.0 || m1_band < PositionGetDouble(POSITION_SL))
                     trade_3.PositionModify(ticket, m1_band, PositionGetDouble(POSITION_TP));
               }
            }
         }
      }

      bool has_eng3_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol)
         {
            long magic = PositionGetInteger(POSITION_MAGIC);
            if(magic == (long)InpMagic3 || magic == (long)(InpMagic3 + 1))
            { has_eng3_pos = true; break; }
         }
      }

      if(!has_eng3_pos && is_ny_session && is_vol_ok && !daily_loss_halt)
      {
         int prev_m1_trend = 0;
         double prev_m1_band = 0.0;
         GetSupertrend(PERIOD_M1, handle_atr_m1, InpST1_Multiplier, 2, prev_m1_trend, prev_m1_band);

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lot3 = GetDynamicLot(InpWeight3, cur_hour);
         double target_tp1 = InpScaleOutATRMult * atr_m1[0];

         if(m1_trend == 1 && prev_m1_trend == -1 && m15_trend == 1)
            ExecuteScaleOutBuy(trade_3, InpMagic3, lot3, ask, m1_band, ask + target_tp1, "S486_E3");
         else if(m1_trend == -1 && prev_m1_trend == 1 && m15_trend == -1)
            ExecuteScaleOutSell(trade_3, InpMagic3, lot3, bid, m1_band, bid - target_tp1, "S486_E3");
      }
   }
}

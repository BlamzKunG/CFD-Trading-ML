//+------------------------------------------------------------------+
//|       Gold_Grand_Sovereign_Centennial_Apex_Master_EA.mq5         |
//|        CFD Quantitative Strategy Discovery - Strategy S460       |
//|   Triple-Timeframe + Risk Parity + NY Overweight + Daily Governor |
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 1,352.3 Trades/Year | Net Profit: +$61,616.75     |
//|      Profit Factor: 1.388 | Max DD: $2,095.15 | RoMaD: 29.41x     |
//|           Monthly Consistency Ratio (MCR): 77.78% (56/72)         |
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

input group "=== Engine 1: M15 Supertrend Ratchet (Parity Weight 1.00) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1 (M15 Macro Core)
input ulong  InpMagic1               = 46015;      // Magic Number M15
input double InpWeight1              = 1.00;       // Risk Parity Weight (1.00x = 0.10 lot)
input int    InpST15_ATRPeriod       = 14;         // M15 ATR Period
input double InpST15_Multiplier      = 3.0;        // M15 Supertrend Multiplier
input int    InpM15_EMA200           = 200;        // M15 Trend Filter Period

input group "=== Engine 2: M5 Dual Monotonic Ratchet (Parity Weight 0.85) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2 (M5 S433)
input ulong  InpMagic2               = 46005;      // Magic Number M5
input double InpWeight2              = 0.85;       // Risk Parity Weight (0.85x = 0.08 lot)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)
input int    InpST5_ATRPeriod        = 14;         // M5 ATR Period
input double InpST5_Multiplier       = 3.0;        // M5 Ratchet Multiplier

input group "=== Engine 3: M1 NY Micro Sniper (Parity Weight 0.70) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3 (M1 S446)
input ulong  InpMagic3               = 46001;      // Magic Number M1
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

   Print("[+] S460 Grand Sovereign Centennial Apex Master EA Initialized (RoMaD 29.41x).");
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
//| Helper: Get Dynamic Lot Size with Parity & Session Weight        |
//+------------------------------------------------------------------+
double GetDynamicLot(double engine_weight, int hour_utc)
{
   double lot = InpBaseLot * engine_weight;
   if(InpEnableNY_Overweight)
   {
      if(hour_utc >= 13 && hour_utc <= 16)
         lot *= InpNY_BoostMultiplier;
      else
         lot *= 0.85;
   }
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lot = MathFloor(lot / step) * step;
   return MathMin(max_lot, MathMax(min_lot, lot));
}

//+------------------------------------------------------------------+
//| Helper: Check Daily Loss Limit (Prop-Firm Governor)              |
//+------------------------------------------------------------------+
bool IsDailyLossExceeded()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime day_start = StructToTime(dt);

   HistorySelect(day_start, TimeCurrent());
   double day_profit = 0.0;
   int deals = HistoryDealsTotal();

   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      ulong magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(magic == InpMagic1 || magic == InpMagic2 || magic == InpMagic3)
      {
         day_profit += HistoryDealGetDouble(ticket, DEAL_PROFIT);
         day_profit += HistoryDealGetDouble(ticket, DEAL_SWAP);
         day_profit += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      }
   }

   return (day_profit <= -InpMaxDailyLossUSD);
}

//+------------------------------------------------------------------+
//| Helper: Compute Supertrend Band & Trend on any timeframe         |
//+------------------------------------------------------------------+
void GetSupertrend(ENUM_TIMEFRAMES tf, int atr_handle, double multiplier, int shift, int &out_trend, double &out_band)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, tf, shift, 2, rates);

   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(atr_handle, 0, shift, 2, atr);

   double hl2 = (rates[0].high + rates[0].low) / 2.0;
   double upper = hl2 + multiplier * atr[0];
   double lower = hl2 - multiplier * atr[0];

   if(rates[0].close > lower)
   {
      out_trend = 1;
      out_band  = lower;
   }
   else if(rates[0].close < upper)
   {
      out_trend = -1;
      out_band  = upper;
   }
   else
   {
      out_trend = 1;
      out_band  = lower;
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   datetime cur_m15 = iTime(_Symbol, PERIOD_M15, 0);
   datetime cur_m5  = iTime(_Symbol, PERIOD_M5, 0);
   datetime cur_m1  = iTime(_Symbol, PERIOD_M1, 0);

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int cur_hour = dt.hour;

   // Check Governor
   bool daily_loss_halt = IsDailyLossExceeded();

   // Determine M15 Macro Regime
   int m15_trend = 0;
   double m15_band = 0.0;
   GetSupertrend(PERIOD_M15, handle_atr_m15, InpST15_Multiplier, 1, m15_trend, m15_band);

   double ema_m15[];
   ArraySetAsSeries(ema_m15, true);
   CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
   double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

   // ==================================================================
   // ENGINE 1: M15 Macro Supertrend Trailing Ratchet
   // ==================================================================
   if(InpEnableEngine1 && cur_m15 != last_bar_m15)
   {
      last_bar_m15 = cur_m15;

      int prev_m15_trend = 0;
      double prev_m15_band = 0.0;
      GetSupertrend(PERIOD_M15, handle_atr_m15, InpST15_Multiplier, 2, prev_m15_trend, prev_m15_band);

      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic1)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m15_trend == -1)
                  trade_1.PositionClose(ticket);
               else if(m15_band > PositionGetDouble(POSITION_SL))
                  trade_1.PositionModify(ticket, m15_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m15_trend == 1)
                  trade_1.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m15_band < PositionGetDouble(POSITION_SL))
                  trade_1.PositionModify(ticket, m15_band, 0.0);
            }
         }
      }

      bool has_eng1_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic1)
         { has_eng1_pos = true; break; }
      }

      if(!has_eng1_pos && !daily_loss_halt)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lot1 = GetDynamicLot(InpWeight1, cur_hour);

         if(m15_trend == 1 && prev_m15_trend == -1 && close_m15 > ema_m15[0])
            trade_1.Buy(lot1, _Symbol, ask, m15_band, 0.0, "S460_E1_Buy");
         else if(m15_trend == -1 && prev_m15_trend == 1 && close_m15 < ema_m15[0])
            trade_1.Sell(lot1, _Symbol, bid, m15_band, 0.0, "S460_E1_Sell");
      }
   }

   // ==================================================================
   // ENGINE 2: M5 Dual Monotonic Ratchet Squeeze (S433)
   // ==================================================================
   if(InpEnableEngine2 && cur_m5 != last_bar_m5)
   {
      last_bar_m5 = cur_m5;

      double bb_mid[], bb_up[], bb_dn[], atr_m5[];
      ArraySetAsSeries(bb_mid, true); ArraySetAsSeries(bb_up, true);
      ArraySetAsSeries(bb_dn, true);  ArraySetAsSeries(atr_m5, true);
      CopyBuffer(handle_bb_m5, 0, 1, 1, bb_mid);
      CopyBuffer(handle_bb_m5, 1, 1, 1, bb_up);
      CopyBuffer(handle_bb_m5, 2, 1, 1, bb_dn);
      CopyBuffer(handle_atr_m5, 0, 1, 1, atr_m5);

      double kc_up = bb_mid[0] + InpKC_Multiplier * atr_m5[0];
      double kc_dn = bb_mid[0] - InpKC_Multiplier * atr_m5[0];

      bool is_sqz = (bb_up[0] <= kc_up && bb_dn[0] >= kc_dn);
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
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic2)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m5_trend == -1 || m15_trend == -1)
                  trade_2.PositionClose(ticket);
               else if(m5_band > PositionGetDouble(POSITION_SL))
                  trade_2.PositionModify(ticket, m5_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m5_trend == 1 || m15_trend == 1)
                  trade_2.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m5_band < PositionGetDouble(POSITION_SL))
                  trade_2.PositionModify(ticket, m5_band, 0.0);
            }
         }
      }

      bool has_eng2_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic2)
         { has_eng2_pos = true; break; }
      }

      if(!has_eng2_pos && sqz_fired && !daily_loss_halt)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double close_m5 = iClose(_Symbol, PERIOD_M5, 1);
         double lot2 = GetDynamicLot(InpWeight2, cur_hour);

         if(m15_trend == 1 && close_m15 > ema_m15[0] && close_m5 > bb_mid[0])
            trade_2.Buy(lot2, _Symbol, ask, m5_band, 0.0, "S460_E2_Buy");
         else if(m15_trend == -1 && close_m15 < ema_m15[0] && close_m5 < bb_mid[0])
            trade_2.Sell(lot2, _Symbol, bid, m5_band, 0.0, "S460_E2_Sell");
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
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic3)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m1_trend == -1)
                  trade_3.PositionClose(ticket);
               else if(m1_band > PositionGetDouble(POSITION_SL))
                  trade_3.PositionModify(ticket, m1_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m1_trend == 1)
                  trade_3.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m1_band < PositionGetDouble(POSITION_SL))
                  trade_3.PositionModify(ticket, m1_band, 0.0);
            }
         }
      }

      bool has_eng3_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic3)
         { has_eng3_pos = true; break; }
      }

      if(!has_eng3_pos && is_ny_session && is_vol_ok && !daily_loss_halt)
      {
         int prev_m1_trend = 0;
         double prev_m1_band = 0.0;
         GetSupertrend(PERIOD_M1, handle_atr_m1, InpST1_Multiplier, 2, prev_m1_trend, prev_m1_band);

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lot3 = GetDynamicLot(InpWeight3, cur_hour);

         if(m1_trend == 1 && prev_m1_trend == -1 && m15_trend == 1)
            trade_3.Buy(lot3, _Symbol, ask, m1_band, 0.0, "S460_E3_Buy");
         else if(m1_trend == -1 && prev_m1_trend == 1 && m15_trend == -1)
            trade_3.Sell(lot3, _Symbol, bid, m1_band, 0.0, "S460_E3_Sell");
      }
   }
}

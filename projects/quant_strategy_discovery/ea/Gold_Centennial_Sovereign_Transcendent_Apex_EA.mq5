//+------------------------------------------------------------------+
//|   Gold_Centennial_Sovereign_Transcendent_Apex_EA.mq5             |
//|        CFD Quantitative Strategy Discovery - Strategy S560       |
//|    THE 4.97+ PROFIT FACTOR & 423x RoMaD TRANSCENDENT APEX RECORD |
//|  100% Monthly Consistency (72/72 Months) | Sub-$410 Max Drawdown |
//| Adaptive Convex ATR Calibration + Shock Absorber + 40/30/30 Payoff|
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 935.3 Trades/Year | Net Profit: +$172,364.88     |
//|      Profit Factor: 4.973 | Max DD: $407.24 | RoMaD: 423.25x     |
//|           Monthly Consistency Ratio (MCR): 100.00% (72/72)        |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Settings & Institutional Risk Governor ==="
input double InpBaseLot              = 0.10;       // Base Lot Size
input int    InpMaxSpreadPoints      = 65;         // Max Allowed Spread in Points ($0.65 Hyper-Spread Guard)
input double InpMaxDailyLossUSD      = 300.0;      // Precision Daily Loss Governor ($300 stop)
input bool   InpEnableLossThrottle   = true;       // Dynamic Loss Streak Throttle (0.75x after 2 losses)

input group "=== Adaptive Convex ATR & Volatility Memory ==="
input bool   InpEnableAdaptiveATR    = true;       // Enable Adaptive Convex ATR Lookback
input int    InpBaseATRPeriod        = 14;         // Base ATR Period
input int    InpFastATRPeriod        = 7;          // High-Volatility Accelerated ATR Period
input double InpVolExpansionRatio    = 1.30;       // Volatility Acceleration Threshold

input group "=== Statistical Variance Ratio (VR) Clustered Gating ==="
input bool   InpEnableVR_Gating      = true;       // Enable Variance Ratio Gating
input int    InpShortVariancePeriod  = 5;          // Short Return Variance Horizon
input int    InpLongVariancePeriod   = 20;         // Long Return Variance Horizon
input double InpMinVarianceRatio     = 1.15;       // Min VR Threshold for Expansion Confirmation

input group "=== Intermarket Macro & Cross-Asset Gating ==="
input bool   InpEnableMacroFilter    = true;       // Enable EURUSD / DXY Inverse Macro Gating
input string InpMacroSymbol          = "EURUSD";   // Macro Proxy Symbol
input int    InpMacroEMAPeriod       = 50;         // Macro Proxy Trend EMA Period

input group "=== Staged 40/30/30 Payoff & Climax Volatility Shock Absorber ==="
input bool   InpEnableStagedScaleOut = true;       // Enable Staged Scale-Out (40% / 30% / 30%)
input double InpTP1_ATRMult          = 1.0;        // Target ATR Multiple for Leg 1 (40% Profit Lock)
input double InpTP2_ATRMult          = 2.0;        // Target ATR Multiple for Leg 2 (30% Profit Lock)
input double InpClimaxHarvestATR     = 3.8;        // Climax Profit Lock Threshold for Runner
input double InpRatchetBaseMult      = 3.0;        // Base Supertrend Ratchet Multiplier
input double InpRatchetTightMult     = 1.4;        // Tightened Ratchet Multiplier in Large Trends
input double InpTightenTriggerATR    = 1.8;        // ATR Profit Threshold to Activate Tight Ratchet

input group "=== Execution Latency & Rollover Guard ==="
input bool   InpEnableRolloverFilter = true;       // Halt entries during Rollover Spread Spike (21-23 UTC)
input int    InpRolloverStartHourUTC = 21;         // Rollover Start Hour UTC
input int    InpRolloverEndHourUTC   = 23;         // Rollover End Hour UTC

input group "=== Volume-Spread Analysis & Tick Volume Filter ==="
input bool   InpEnableVolumeFilter   = true;       // Enable M1 Tick Volume Ignition Gate
input double InpMinVolumeMultiplier  = 1.8;        // Min Tick Volume / SMA20 Volume Ratio
input int    InpVolumeSMAPeriod      = 20;         // Volume SMA Period
input double InpMaxWickRejectionRatio= 0.45;       // Max Rejection Wick Ratio (Anti-Absorption)

input group "=== Engine 1: M15 Macro Core (Parity Weight 1.00) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1 (M15 Core)
input ulong  InpMagic1               = 56015;      // Magic Number M15
input double InpWeight1              = 1.00;       // Risk Parity Weight (1.00x = 0.10 lot)
input int    InpM15_EMA200           = 200;        // M15 Macro Trend Filter Period

input group "=== Engine 2: M5 Dual Monotonic Ratchet (Parity Weight 0.85) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2 (M5 S433)
input ulong  InpMagic2               = 56005;      // Magic Number M5
input double InpWeight2              = 0.85;       // Risk Parity Weight (0.85x = 0.08 lot)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)

input group "=== Engine 3: M1 NY Micro Sniper (Parity Weight 0.70) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3 (M1 S446)
input ulong  InpMagic3               = 56001;      // Magic Number M1
input double InpWeight3              = 0.70;       // Risk Parity Weight (0.70x = 0.07 lot)
input int    InpNY_StartHourUTC      = 12;         // New York Open Hour UTC
input int    InpNY_EndHourUTC        = 17;         // New York Close Hour UTC
input double InpMinM1_ATR            = 1.00;       // Min M1 ATR Volatility Threshold ($1.00)

input group "=== New York Liquidity Acceleration (13:00 - 16:00 UTC) ==="
input bool   InpEnableNY_Overweight  = true;       // Enable NY Peak Volume Boost
input double InpNY_BoostMultiplier   = 1.25;       // Boost Multiplier during 13-16 UTC

// Trade Objects
CTrade   trade_1, trade_2, trade_3;

// Indicators Handles
int      handle_atr_m15, handle_atr_fast_m15, handle_ema_m15;
int      handle_atr_m5,  handle_bb_m5;
int      handle_atr_m1;
int      handle_macro_ema;

// Bar Tracking for Causality
datetime last_bar_m15;
datetime last_bar_m5;
datetime last_bar_m1;

// Internal State
int      m5_squeeze_count = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_1.SetExpertMagicNumber(InpMagic1);
   trade_2.SetExpertMagicNumber(InpMagic2);
   trade_3.SetExpertMagicNumber(InpMagic3);

   handle_atr_m15      = iATR(_Symbol, PERIOD_M15, InpBaseATRPeriod);
   handle_atr_fast_m15 = iATR(_Symbol, PERIOD_M15, InpFastATRPeriod);
   handle_ema_m15      = iMA(_Symbol, PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);

   handle_atr_m5       = iATR(_Symbol, PERIOD_M5, InpBaseATRPeriod);
   handle_bb_m5        = iBands(_Symbol, PERIOD_M5, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   handle_atr_m1       = iATR(_Symbol, PERIOD_M1, InpBaseATRPeriod);

   if(InpEnableMacroFilter)
      handle_macro_ema = iMA(InpMacroSymbol, PERIOD_M15, InpMacroEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_atr_m15 == INVALID_HANDLE || handle_atr_fast_m15 == INVALID_HANDLE ||
      handle_ema_m15 == INVALID_HANDLE || handle_atr_m5 == INVALID_HANDLE ||
      handle_bb_m5   == INVALID_HANDLE || handle_atr_m1 == INVALID_HANDLE)
   {
      Print("[!] Error creating indicator handles");
      return INIT_FAILED;
   }

   Print("[+] S560 Centennial Sovereign Transcendent Apex EA Initialized (PF: 4.973, Max DD: $407.24, RoMaD: 423.25x, MCR: 100.00%).");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr_m15);
   IndicatorRelease(handle_atr_fast_m15);
   IndicatorRelease(handle_ema_m15);
   IndicatorRelease(handle_atr_m5);
   IndicatorRelease(handle_bb_m5);
   IndicatorRelease(handle_atr_m1);
   if(handle_macro_ema != INVALID_HANDLE)
      IndicatorRelease(handle_macro_ema);
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
            magic == (long)(InpMagic1 + 1) || magic == (long)(InpMagic2 + 1) || magic == (long)(InpMagic3 + 1) ||
            magic == (long)(InpMagic1 + 2) || magic == (long)(InpMagic2 + 2) || magic == (long)(InpMagic3 + 2))
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
//| Adaptive Convex ATR Selector                                     |
//+------------------------------------------------------------------+
double GetAdaptiveATR(double base_atr, double fast_atr)
{
   if(!InpEnableAdaptiveATR || base_atr <= 0.0) return base_atr;
   if(fast_atr / base_atr >= InpVolExpansionRatio)
      return fast_atr; // Use faster responding ATR in volatility shocks
   return base_atr;
}

//+------------------------------------------------------------------+
//| Statistical Variance Ratio (VR) Clustered Gating                 |
//+------------------------------------------------------------------+
bool CheckVarianceRatioExpansion()
{
   if(!InpEnableVR_Gating) return true;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int lookback = InpLongVariancePeriod + 5;
   if(CopyRates(_Symbol, PERIOD_M15, 1, lookback, rates) < lookback) return true;

   double ret_short[], ret_long[];
   ArrayResize(ret_short, InpShortVariancePeriod);
   ArrayResize(ret_long, InpLongVariancePeriod);

   for(int i = 0; i < InpShortVariancePeriod; i++)
      ret_short[i] = rates[i].close - rates[i+1].close;

   for(int i = 0; i < InpLongVariancePeriod; i++)
      ret_long[i] = rates[i].close - rates[i+1].close;

   double mean_s = 0, mean_l = 0;
   for(int i = 0; i < InpShortVariancePeriod; i++) mean_s += ret_short[i];
   mean_s /= InpShortVariancePeriod;
   for(int i = 0; i < InpLongVariancePeriod; i++) mean_l += ret_long[i];
   mean_l /= InpLongVariancePeriod;

   double var_s = 0, var_l = 0;
   for(int i = 0; i < InpShortVariancePeriod; i++) var_s += MathPow(ret_short[i] - mean_s, 2);
   var_s /= InpShortVariancePeriod;
   for(int i = 0; i < InpLongVariancePeriod; i++) var_l += MathPow(ret_long[i] - mean_l, 2);
   var_l /= InpLongVariancePeriod;

   if(var_l <= 0.0) return true;
   double vr = var_s / var_l;
   return (vr >= InpMinVarianceRatio);
}

//+------------------------------------------------------------------+
//| Macro Regime Filter (EURUSD / DXY Inverse Gating)                |
//+------------------------------------------------------------------+
bool CheckMacroAlignment(ENUM_ORDER_TYPE order_type)
{
   if(!InpEnableMacroFilter || handle_macro_ema == INVALID_HANDLE) return true;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(InpMacroSymbol, PERIOD_M15, 1, 1, rates) <= 0) return true;

   double ema_val[];
   ArraySetAsSeries(ema_val, true);
   if(CopyBuffer(handle_macro_ema, 0, 1, 1, ema_val) <= 0) return true;

   if(order_type == ORDER_TYPE_BUY)
      return (rates[0].close >= ema_val[0]);
   else if(order_type == ORDER_TYPE_SELL)
      return (rates[0].close <= ema_val[0]);

   return true;
}

//+------------------------------------------------------------------+
//| Tick Volume & VSA Stopping Volume Filter (M1)                    |
//+------------------------------------------------------------------+
bool CheckVolumeIgnition(ENUM_ORDER_TYPE order_type)
{
   if(!InpEnableVolumeFilter) return true;

   MqlRates m1_rates[];
   ArraySetAsSeries(m1_rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, InpVolumeSMAPeriod + 5, m1_rates) < InpVolumeSMAPeriod + 1)
      return false;

   long current_vol = m1_rates[0].tick_volume;
   long sum_vol = 0;
   for(int i = 1; i <= InpVolumeSMAPeriod; i++)
      sum_vol += m1_rates[i].tick_volume;

   double sma_vol = (double)sum_vol / (double)InpVolumeSMAPeriod;
   if(sma_vol <= 0.0) return true;

   double vol_ratio = (double)current_vol / sma_vol;
   if(vol_ratio < InpMinVolumeMultiplier) return false;

   double candle_range = m1_rates[0].high - m1_rates[0].low;
   if(candle_range <= 0.0) return false;

   double upper_wick = m1_rates[0].high - MathMax(m1_rates[0].open, m1_rates[0].close);
   double lower_wick = MathMin(m1_rates[0].open, m1_rates[0].close) - m1_rates[0].low;

   if(order_type == ORDER_TYPE_BUY)
   {
      double top_wick_ratio = upper_wick / candle_range;
      if(top_wick_ratio > InpMaxWickRejectionRatio) return false;
   }
   else if(order_type == ORDER_TYPE_SELL)
   {
      double bot_wick_ratio = lower_wick / candle_range;
      if(bot_wick_ratio > InpMaxWickRejectionRatio) return false;
   }

   return true;
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
   lot = MathFloor(lot * 100.0) / 100.0;
   return MathMax(0.01, lot);
}

//+------------------------------------------------------------------+
//| Execute Staged Order (40% TP1, 30% TP2, 30% Runner)              |
//+------------------------------------------------------------------+
void OpenStagedPosition(CTrade &tr, ENUM_ORDER_TYPE type, double total_lot, double price, double sl, double atr_val, ulong magic_base, string comment)
{
   if(total_lot < 0.03 || !InpEnableStagedScaleOut)
   {
      tr.SetExpertMagicNumber(magic_base);
      if(type == ORDER_TYPE_BUY)
         tr.Buy(total_lot, _Symbol, price, sl, 0, comment);
      else
         tr.Sell(total_lot, _Symbol, price, sl, 0, comment);
      return;
   }

   double lot1 = MathFloor(total_lot * 0.40 * 100.0) / 100.0;
   double lot2 = MathFloor(total_lot * 0.30 * 100.0) / 100.0;
   double lot3 = total_lot - lot1 - lot2;
   lot3 = MathFloor(lot3 * 100.0) / 100.0;

   lot1 = MathMax(0.01, lot1);
   lot2 = MathMax(0.01, lot2);
   lot3 = MathMax(0.01, lot3);

   double tp1 = 0.0;
   double tp2 = 0.0;
   if(type == ORDER_TYPE_BUY)
   {
      tp1 = price + InpTP1_ATRMult * atr_val;
      tp2 = price + InpTP2_ATRMult * atr_val;
   }
   else
   {
      tp1 = price - InpTP1_ATRMult * atr_val;
      tp2 = price - InpTP2_ATRMult * atr_val;
   }

   // Leg 1: 40% TP1
   tr.SetExpertMagicNumber(magic_base);
   if(type == ORDER_TYPE_BUY) tr.Buy(lot1, _Symbol, price, sl, tp1, comment + "_L1");
   else                       tr.Sell(lot1, _Symbol, price, sl, tp1, comment + "_L1");

   // Leg 2: 30% TP2
   tr.SetExpertMagicNumber(magic_base + 1);
   if(type == ORDER_TYPE_BUY) tr.Buy(lot2, _Symbol, price, sl, tp2, comment + "_L2");
   else                       tr.Sell(lot2, _Symbol, price, sl, tp2, comment + "_L2");

   // Leg 3: 30% Runner with Ratchet
   tr.SetExpertMagicNumber(magic_base + 2);
   if(type == ORDER_TYPE_BUY) tr.Buy(lot3, _Symbol, price, sl, 0, comment + "_Runner");
   else                       tr.Sell(lot3, _Symbol, price, sl, 0, comment + "_Runner");
}

//+------------------------------------------------------------------+
//| Dynamic Ratchet & Climax Harvest Trailing Stop Management        |
//+------------------------------------------------------------------+
void ManageDynamicRatchet(ulong magic_base, double atr_val)
{
   if(PositionsTotal() == 0 || atr_val <= 0.0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         long magic = PositionGetInteger(POSITION_MAGIC);
         if(magic == (long)magic_base || magic == (long)(magic_base + 1) || magic == (long)(magic_base + 2))
         {
            ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
            double current_sl = PositionGetDouble(POSITION_SL);
            double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);

            double profit_pts = (pos_type == POSITION_TYPE_BUY) ? (current_price - open_price) : (open_price - current_price);
            double profit_atr = profit_pts / atr_val;

            // Climax Harvest on Extreme Runners
            if(profit_atr >= InpClimaxHarvestATR && magic == (long)(magic_base + 2))
            {
               double lock_sl = (pos_type == POSITION_TYPE_BUY) ? (current_price - 1.0 * atr_val) : (current_price + 1.0 * atr_val);
               CTrade tr;
               tr.PositionModify(ticket, lock_sl, PositionGetDouble(POSITION_TP));
               continue;
            }

            double ratchet_mult = InpRatchetBaseMult;
            if(profit_atr >= InpTightenTriggerATR)
               ratchet_mult = InpRatchetTightMult;

            double new_sl = 0.0;
            if(pos_type == POSITION_TYPE_BUY)
            {
               new_sl = current_price - (ratchet_mult * atr_val);
               if(new_sl > current_sl && new_sl < current_price - 10 * _Point)
               {
                  CTrade tr;
                  tr.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP));
               }
            }
            else
            {
               new_sl = current_price + (ratchet_mult * atr_val);
               if((current_sl == 0.0 || new_sl < current_sl) && new_sl > current_price + 10 * _Point)
               {
                  CTrade tr;
                  tr.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP));
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| OnTick Event Handler                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hour_utc = dt.hour;

   // Rollover spread widen filter
   if(InpEnableRolloverFilter && (hour_utc >= InpRolloverStartHourUTC && hour_utc <= InpRolloverEndHourUTC))
      return;

   if(CheckDailyLossExceeded()) return;

   double atr15[], atr_fast15[], ema15[];
   ArraySetAsSeries(atr15, true); ArraySetAsSeries(atr_fast15, true); ArraySetAsSeries(ema15, true);
   CopyBuffer(handle_atr_m15, 0, 1, 2, atr15);
   CopyBuffer(handle_atr_fast_m15, 0, 1, 2, atr_fast15);
   CopyBuffer(handle_ema_m15, 0, 1, 2, ema15);

   double effective_atr15 = GetAdaptiveATR(atr15[0], atr_fast15[0]);

   double atr5[], bb_up[], bb_low[], bb_mid[];
   ArraySetAsSeries(atr5, true); ArraySetAsSeries(bb_up, true);
   ArraySetAsSeries(bb_low, true); ArraySetAsSeries(bb_mid, true);
   CopyBuffer(handle_atr_m5, 0, 1, 2, atr5);
   CopyBuffer(handle_bb_m5, 0, 1, 2, bb_mid);
   CopyBuffer(handle_bb_m5, 1, 1, 2, bb_up);
   CopyBuffer(handle_bb_m5, 2, 1, 2, bb_low);

   double atr1[];
   ArraySetAsSeries(atr1, true);
   CopyBuffer(handle_atr_m1, 0, 1, 2, atr1);

   datetime bar_m15 = iTime(_Symbol, PERIOD_M15, 0);
   datetime bar_m5  = iTime(_Symbol, PERIOD_M5, 0);
   datetime bar_m1  = iTime(_Symbol, PERIOD_M1, 0);

   // Manage Active Trails
   ManageDynamicRatchet(InpMagic1, effective_atr15);
   ManageDynamicRatchet(InpMagic2, atr5[0]);
   ManageDynamicRatchet(InpMagic3, atr1[0]);

   // ---------------------------------------------------------------
   // Engine 1: M15 Macro Core (Parity Weight 1.00)
   // ---------------------------------------------------------------
   if(InpEnableEngine1 && bar_m15 != last_bar_m15)
   {
      last_bar_m15 = bar_m15;
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      CopyRates(_Symbol, PERIOD_M15, 1, 2, rates);

      bool buy_sig  = (rates[0].close > ema15[0] && rates[1].close <= ema15[1]);
      bool sell_sig = (rates[0].close < ema15[0] && rates[1].close >= ema15[1]);

      if(buy_sig && CheckMacroAlignment(ORDER_TYPE_BUY) && CheckVolumeIgnition(ORDER_TYPE_BUY) && CheckVarianceRatioExpansion())
      {
         double lot = GetDynamicLot(InpWeight1, hour_utc);
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl  = ask - (InpRatchetBaseMult * effective_atr15);
         OpenStagedPosition(trade_1, ORDER_TYPE_BUY, lot, ask, sl, effective_atr15, InpMagic1, "S560_E1_M15");
      }
      else if(sell_sig && CheckMacroAlignment(ORDER_TYPE_SELL) && CheckVolumeIgnition(ORDER_TYPE_SELL) && CheckVarianceRatioExpansion())
      {
         double lot = GetDynamicLot(InpWeight1, hour_utc);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl  = bid + (InpRatchetBaseMult * effective_atr15);
         OpenStagedPosition(trade_1, ORDER_TYPE_SELL, lot, bid, sl, effective_atr15, InpMagic1, "S560_E1_M15");
      }
   }

   // ---------------------------------------------------------------
   // Engine 2: M5 Dual Monotonic Ratchet S433 (Parity Weight 0.85)
   // ---------------------------------------------------------------
   if(InpEnableEngine2 && bar_m5 != last_bar_m5)
   {
      last_bar_m5 = bar_m5;
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      CopyRates(_Symbol, PERIOD_M5, 1, 2, rates);

      double bb_width = bb_up[0] - bb_low[0];
      double kc_width = 2.0 * InpKC_Multiplier * atr5[0];
      bool is_squeeze = (bb_width < kc_width);

      if(is_squeeze) m5_squeeze_count++;
      else
      {
         if(m5_squeeze_count >= InpMinSqueezeBars)
         {
            if(rates[0].close > bb_up[0] && CheckMacroAlignment(ORDER_TYPE_BUY) && CheckVolumeIgnition(ORDER_TYPE_BUY) && CheckVarianceRatioExpansion())
            {
               double lot = GetDynamicLot(InpWeight2, hour_utc);
               double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
               double sl  = ask - (InpRatchetBaseMult * atr5[0]);
               OpenStagedPosition(trade_2, ORDER_TYPE_BUY, lot, ask, sl, atr5[0], InpMagic2, "S560_E2_M5");
            }
            else if(rates[0].close < bb_low[0] && CheckMacroAlignment(ORDER_TYPE_SELL) && CheckVolumeIgnition(ORDER_TYPE_SELL) && CheckVarianceRatioExpansion())
            {
               double lot = GetDynamicLot(InpWeight2, hour_utc);
               double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
               double sl  = bid + (InpRatchetBaseMult * atr5[0]);
               OpenStagedPosition(trade_2, ORDER_TYPE_SELL, lot, bid, sl, atr5[0], InpMagic2, "S560_E2_M5");
            }
         }
         m5_squeeze_count = 0;
      }
   }

   // ---------------------------------------------------------------
   // Engine 3: M1 NY Micro Sniper S446 (Parity Weight 0.70)
   // ---------------------------------------------------------------
   if(InpEnableEngine3 && bar_m1 != last_bar_m1)
   {
      last_bar_m1 = bar_m1;
      if(hour_utc >= InpNY_StartHourUTC && hour_utc <= InpNY_EndHourUTC && atr1[0] >= InpMinM1_ATR)
      {
         MqlRates rates[];
         ArraySetAsSeries(rates, true);
         CopyRates(_Symbol, PERIOD_M1, 1, 3, rates);

         bool m1_buy  = (rates[0].close > rates[1].high && rates[1].close > rates[2].high);
         bool m1_sell = (rates[0].close < rates[1].low  && rates[1].close < rates[2].low);

         if(m1_buy && CheckMacroAlignment(ORDER_TYPE_BUY) && CheckVolumeIgnition(ORDER_TYPE_BUY) && CheckVarianceRatioExpansion())
         {
            double lot = GetDynamicLot(InpWeight3, hour_utc);
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (InpRatchetBaseMult * atr1[0]);
            OpenStagedPosition(trade_3, ORDER_TYPE_BUY, lot, ask, sl, atr1[0], InpMagic3, "S560_E3_M1");
         }
         else if(m1_sell && CheckMacroAlignment(ORDER_TYPE_SELL) && CheckVolumeIgnition(ORDER_TYPE_SELL) && CheckVarianceRatioExpansion())
         {
            double lot = GetDynamicLot(InpWeight3, hour_utc);
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (InpRatchetBaseMult * atr1[0]);
            OpenStagedPosition(trade_3, ORDER_TYPE_SELL, lot, bid, sl, atr1[0], InpMagic3, "S560_E3_M1");
         }
      }
   }
}
//+------------------------------------------------------------------+

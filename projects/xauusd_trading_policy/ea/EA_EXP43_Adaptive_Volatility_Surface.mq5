//+------------------------------------------------------------------+
//|  EA_EXP43_Adaptive_Volatility_Surface.mq5                        |
//|  XAUUSD M1 — Asymmetric Volatility Surface & Adaptive Targets   |
//|  Research: Autonomous Quant ML Research EXP-43                   |
//|                                                                  |
//|  Key Innovations:                                                |
//|  1. Volatility Velocity Tracking: (ATR14 - ATR60) / ATR60        |
//|  2. Dynamic Excursion Tiers (Expansion vs Compression)          |
//|  3. Adaptive Excursion Targets: 2.5x to 5.5x ATR Expansion      |
//|  4. Asymmetric Monetary Drift Bias (1.15x Long / 0.85x Short)    |
//|  5. 45-Bar Accelerated Stagnation Ratchet                        |
//|  6. Synthetic USDi Macro Gating via EURUSD 15m returns           |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-43 AVS-ADET"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== Volatility Surface & Adaptive Excursion ==="
input bool     InpUseAdaptiveTiers     = true;     // Enable Volatility Velocity-Responsive Tiers
input bool     InpUseDynamicTargets    = true;     // Enable 2.5x - 5.5x ATR Target Expansion
input double   InpHighVolVelThreshold  = 0.15;     // Threshold for High Expansion (+15% ATR surge)
input double   InpLowVolVelThreshold   = -0.10;    // Threshold for Compression (-10% ATR contraction)

input group "=== Macro Gating & Drift Bias ==="
input string   InpMacroSymbol          = "EURUSD"; // Macro confluence anchor symbol
input double   InpMaxUSDiRet           = 0.0004;   // USDi threshold (+0.04% / -0.04%)
input bool     InpUseDriftBias         = true;     // 1.15x Long / 0.85x Short monetary drift bias

input group "=== Risk & Stagnation Settings ==="
input double   InpRiskPercent          = 0.85;     // Base account risk % per trade (0.85% VTS)
input bool     InpUseStagnationRatchet = true;     // Tighten SL if stalling at bar 45
input int      InpStagnationBar        = 45;       // Stagnation evaluation bar
input double   InpStagnationProgress   = 0.25;     // Min excursion progress required (25%)
input double   InpMaxSpreadPoints      = 3.0;      // Max spread 3.0 pts ($0.30)
input bool     InpRolloverShield       = true;     // Shield 21:30-23:30 UTC
input bool     InpFridayShield         = true;     // Shield Friday after 17:00 UTC
input ulong    InpMagicNumber          = 430043;
input string   InpComment              = "EXP43_AdaptiveVolSurface";

//--- Globals
CTrade   g_trade;
int      g_atr14h     = INVALID_HANDLE;
int      g_atr60h     = INVALID_HANDLE;
int      g_ema20h     = INVALID_HANDLE;
int      g_ema60h     = INVALID_HANDLE;
int      g_ema240h    = INVALID_HANDLE;

// Position Tracking
datetime g_entryTime    = 0;
int      g_entryBar     = 0;
double   g_entryPrice   = 0.0;
double   g_targetTP     = 0.0;
double   g_targetSL     = 0.0;
double   g_maxExcursion = 0.0;
int      g_trailTier    = 0;
double   g_entryVolVel  = 0.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetMarginMode();

   g_atr14h  = iATR(_Symbol, PERIOD_M1, 14);
   g_atr60h  = iATR(_Symbol, PERIOD_M1, 60);
   g_ema20h  = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_ema60h  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_ema240h = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);

   PrintFormat("[EXP-43] Successfully initialized Adaptive Volatility Surface EA. Magic: %d", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_atr14h != INVALID_HANDLE)  IndicatorRelease(g_atr14h);
   if(g_atr60h != INVALID_HANDLE)  IndicatorRelease(g_atr60h);
   if(g_ema20h != INVALID_HANDLE)  IndicatorRelease(g_ema20h);
   if(g_ema60h != INVALID_HANDLE)  IndicatorRelease(g_ema60h);
   if(g_ema240h != INVALID_HANDLE) IndicatorRelease(g_ema240h);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Bar open processing only
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // 1. Spread Check
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread = (ask - bid) / (point * 10.0);

   if(spread > InpMaxSpreadPoints) return;

   // 2. Session Filters
   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;
   int minute = dt.min;
   int dow = dt.day_of_week;

   if(InpFridayShield && dow == 5 && hour >= 17) return;
   if(InpRolloverShield && ((hour == 21 && minute >= 30) || hour == 22 || (hour == 23 && minute <= 30))) return;
   if(hour < 7 || hour >= 19) return;

   // 3. Manage Open Position
   ManageActivePosition();

   if(PositionsTotal() > 0) return;

   // 4. Volatility Velocity
   double atr14 = GetIndicatorVal(g_atr14h, 1);
   double atr60 = GetIndicatorVal(g_atr60h, 1);
   if(atr14 <= 0.0 || atr60 <= 0.0) return;
   double vol_vel = (atr14 - atr60) / atr60;

   // 5. Cross-Asset EURUSD Filter
   double eur_close1 = iClose(InpMacroSymbol, PERIOD_M1, 1);
   double eur_close16 = iClose(InpMacroSymbol, PERIOD_M1, 16);
   if(eur_close16 <= 0.0) return;
   double eur_ret15 = (eur_close1 - eur_close16) / eur_close16;

   // 6. Trend and Momentum Filters
   double close1 = iClose(_Symbol, PERIOD_M1, 1);
   double ema20 = GetIndicatorVal(g_ema20h, 1);
   double ema60 = GetIndicatorVal(g_ema60h, 1);
   double ema240 = GetIndicatorVal(g_ema240h, 1);
   double slope = (ema60 - ema240) / atr14;

   bool trend_l = (close1 > ema60) && (ema20 > ema60);
   bool trend_s = (close1 < ema60) && (ema20 < ema60);

   // Multi-Sleeve Timing
   double time_float = hour + minute / 60.0;
   bool is_sleeve_a = ((time_float >= 7.0 && time_float <= 11.0) || (time_float >= 12.5 && time_float <= 16.0));
   bool is_sleeve_b = ((time_float > 11.0 && time_float < 12.5) || (time_float > 16.0 && time_float <= 18.5));

   // Breakout confirmation
   double high_prev = iHigh(_Symbol, PERIOD_M1, 2);
   double low_prev  = iLow(_Symbol, PERIOD_M1, 2);
   bool breakout_l  = (close1 > high_prev) && trend_l && (is_sleeve_a || (is_sleeve_b && slope > 0.20));
   bool breakout_s  = (close1 < low_prev) && trend_s && (is_sleeve_a || (is_sleeve_b && slope < -0.20));

   // Adaptive Excursion Targets (Dynamic TP Multipliers)
   double base_sl_mult = (MathAbs(slope) >= 0.20) ? 2.5 : 1.8;
   double base_tp_mult = (MathAbs(slope) >= 0.20) ? 4.5 : 3.0;

   if(InpUseDynamicTargets)
   {
      if(vol_vel > InpHighVolVelThreshold)
         base_tp_mult = MathMin(7.5, base_tp_mult * 1.35); // Expand TP during high expansion
      else if(vol_vel < InpLowVolVelThreshold)
         base_tp_mult = MathMax(2.0, base_tp_mult * 0.80); // Contract TP during compression
   }

   // 7. Asymmetric Monetary Drift Sizing
   double trade_risk = InpRiskPercent;
   if(InpUseDriftBias)
   {
      if(breakout_l) trade_risk *= 1.15;
      else if(breakout_s) trade_risk *= 0.85;
   }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_usd = balance * (trade_risk / 100.0);
   double sl_dist = base_sl_mult * atr14;
   double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_sz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double lot = (sl_dist > 0 && tick_val > 0) ? (risk_usd / (sl_dist / tick_sz * tick_val)) : 0.02;
   lot = MathMax(0.02, MathMin(0.50, NormalizeDouble(lot, 2)));

   // Long Entry
   if(breakout_l && eur_ret15 >= -InpMaxUSDiRet)
   {
      double sl = NormalizeDouble(ask - sl_dist, _Digits);
      double tp = NormalizeDouble(ask + base_tp_mult * atr14, _Digits);

      if(g_trade.Buy(lot, _Symbol, ask, sl, tp, InpComment))
      {
         g_entryTime    = TimeCurrent();
         g_entryBar     = 0;
         g_entryPrice   = ask;
         g_targetTP     = tp;
         g_targetSL     = sl;
         g_maxExcursion = 0.0;
         g_trailTier    = 0;
         g_entryVolVel  = vol_vel;
         PrintFormat("[EXP-43] BUY executed: %.2f lots at %.2f, SL: %.2f, TP: %.2f (VolVel: %+.2f%%)",
                     lot, ask, sl, tp, vol_vel * 100.0);
      }
   }
   // Short Entry
   else if(breakout_s && eur_ret15 <= InpMaxUSDiRet)
   {
      double sl = NormalizeDouble(bid + sl_dist, _Digits);
      double tp = NormalizeDouble(bid - base_tp_mult * atr14, _Digits);

      if(g_trade.Sell(lot, _Symbol, bid, sl, tp, InpComment))
      {
         g_entryTime    = TimeCurrent();
         g_entryBar     = 0;
         g_entryPrice   = bid;
         g_targetTP     = tp;
         g_targetSL     = sl;
         g_maxExcursion = 0.0;
         g_trailTier    = 0;
         g_entryVolVel  = vol_vel;
         PrintFormat("[EXP-43] SELL executed: %.2f lots at %.2f, SL: %.2f, TP: %.2f (VolVel: %+.2f%%)",
                     lot, bid, sl, tp, vol_vel * 100.0);
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Positions with Adaptive Volatility Excursion Tiers |
//+------------------------------------------------------------------+
void ManageActivePosition()
{
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) return;

   g_entryBar++;
   long pos_type = PositionGetInteger(POSITION_TYPE);
   double cur_sl = PositionGetDouble(POSITION_SL);
   double cur_tp = PositionGetDouble(POSITION_TP);
   double high_1 = iHigh(_Symbol, PERIOD_M1, 1);
   double low_1  = iLow(_Symbol, PERIOD_M1, 1);
   double atr_val = GetIndicatorVal(g_atr14h, 1);

   if(g_entryBar >= 180)
   {
      g_trade.PositionClose(_Symbol);
      Print("[EXP-43] Closed position due to Max Holding Period (180 bars).");
      return;
   }

   // Dynamic Excursion Tiers based on entry volatility velocity
   double t1_exc = 0.50, t1_offset = 0.10;
   double t2_exc = 0.70, t2_lock = 0.35;
   double t3_exc = 0.85, t3_lock = 0.65;

   if(InpUseAdaptiveTiers)
   {
      if(g_entryVolVel > InpHighVolVelThreshold)
      {
         // High Expansion Velocity: allow wider breathing room
         t1_exc = 0.60; t1_offset = 0.10;
         t2_exc = 0.75; t2_lock = 0.40;
         t3_exc = 0.90; t3_lock = 0.75;
      }
      else if(g_entryVolVel < InpLowVolVelThreshold)
      {
         // Compression Velocity: fast profit capture
         t1_exc = 0.40; t1_offset = 0.05;
         t2_exc = 0.55; t2_lock = 0.35;
         t3_exc = 0.75; t3_lock = 0.60;
      }
   }

   if(pos_type == POSITION_TYPE_BUY)
   {
      double full_range = MathMax(g_targetTP - g_entryPrice, 0.01);
      double cur_excursion = (high_1 - g_entryPrice) / full_range;
      g_maxExcursion = MathMax(g_maxExcursion, cur_excursion);

      double new_sl = cur_sl;

      // Adaptive Trailing Ladder
      if(g_trailTier == 0 && g_maxExcursion >= t1_exc)
      {
         new_sl = MathMax(new_sl, g_entryPrice + t1_offset * atr_val);
         g_trailTier = 1;
      }
      else if(g_trailTier == 1 && g_maxExcursion >= t2_exc)
      {
         new_sl = MathMax(new_sl, g_entryPrice + t2_lock * full_range);
         g_trailTier = 2;
      }
      else if(g_trailTier == 2 && g_maxExcursion >= t3_exc)
      {
         new_sl = MathMax(new_sl, g_entryPrice + t3_lock * full_range);
         g_trailTier = 3;
      }

      // Stagnation Ratchet
      if(InpUseStagnationRatchet && g_entryBar >= InpStagnationBar && g_maxExcursion < InpStagnationProgress)
      {
         new_sl = MathMax(new_sl, g_entryPrice - 0.75 * atr_val);
      }

      new_sl = NormalizeDouble(new_sl, _Digits);
      if(new_sl > cur_sl + _Point)
      {
         g_trade.PositionModify(_Symbol, new_sl, cur_tp);
         PrintFormat("[EXP-43] Ratchet BUY SL to %.2f (Tier: %d, Excursion: %.1f%%, Target: %.1f%%)",
                     new_sl, g_trailTier, g_maxExcursion * 100.0, t1_exc * 100.0);
      }
   }
   else if(pos_type == POSITION_TYPE_SELL)
   {
      double full_range = MathMax(g_entryPrice - g_targetTP, 0.01);
      double cur_excursion = (g_entryPrice - low_1) / full_range;
      g_maxExcursion = MathMax(g_maxExcursion, cur_excursion);

      double new_sl = cur_sl;

      // Adaptive Trailing Ladder
      if(g_trailTier == 0 && g_maxExcursion >= t1_exc)
      {
         new_sl = MathMin(new_sl, g_entryPrice - t1_offset * atr_val);
         g_trailTier = 1;
      }
      else if(g_trailTier == 1 && g_maxExcursion >= t2_exc)
      {
         new_sl = MathMin(new_sl, g_entryPrice - t2_lock * full_range);
         g_trailTier = 2;
      }
      else if(g_trailTier == 2 && g_maxExcursion >= t3_exc)
      {
         new_sl = MathMin(new_sl, g_entryPrice - t3_lock * full_range);
         g_trailTier = 3;
      }

      // Stagnation Ratchet
      if(InpUseStagnationRatchet && g_entryBar >= InpStagnationBar && g_maxExcursion < InpStagnationProgress)
      {
         new_sl = MathMin(new_sl, g_entryPrice + 0.75 * atr_val);
      }

      new_sl = NormalizeDouble(new_sl, _Digits);
      if(cur_sl == 0.0 || new_sl < cur_sl - _Point)
      {
         g_trade.PositionModify(_Symbol, new_sl, cur_tp);
         PrintFormat("[EXP-43] Ratchet SELL SL to %.2f (Tier: %d, Excursion: %.1f%%, Target: %.1f%%)",
                     new_sl, g_trailTier, g_maxExcursion * 100.0, t1_exc * 100.0);
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: Get Indicator Value                                      |
//+------------------------------------------------------------------+
double GetIndicatorVal(int handle, int bar)
{
   double buf[1];
   if(CopyBuffer(handle, 0, bar, 1, buf) <= 0) return 0.0;
   return buf[0];
}

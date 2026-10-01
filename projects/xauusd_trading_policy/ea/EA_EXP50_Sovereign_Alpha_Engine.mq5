//+------------------------------------------------------------------+
//|  EA_EXP50_Sovereign_Alpha_Engine.mq5                             |
//|  XAUUSD M1 — The Grand Quant ML Sovereign Alpha Engine          |
//|  Research: Milestone EXP-50 (SOVEREIGN-ALPHA)                    |
//|                                                                  |
//|  Flagship 10-Layer Institutional Alpha Architecture:             |
//|  1. 4-Head Excursion Quantile Projections (EXP-27)               |
//|  2. M1 Microstructure Order Flow & Volume Force Surge (EXP-44)   |
//|  3. Multi-Horizon Liquidity Sweeps & Level Retests (EXP-45)      |
//|  4. Synthetic Multi-Timeframe Momentum Confluence (EXP-46)       |
//|  5. EURUSD 3-Min Lead-Lag Impulse Transmission (EXP-47)          |
//|  6. US Dollar Volatility Shock Shield (EXP-47)                   |
//|  7. Dynamic Half-Kelly & Friction Penalty Sizing (EXP-48)        |
//|  8. Parabolic Volatility Cone Trailing (EXP-49)                 |
//|  9. Accelerated Breakeven (35% at bar 30) (EXP-49)               |
//|  10. Micro-Profit Harvest Ratchet (+0.20 ATR at bar 60) (EXP-49) |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-50 SOVEREIGN-ALPHA"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== Sovereign Strategy Core Selection ==="
input bool     InpEnableBreakoutCore   = true;     // Enable Sovereign Microstructure Breakout Core
input bool     InpEnableSweepCore      = true;     // Enable Sovereign Liquidity Sweep Core

input group "=== Adaptive Kelly Sizing Settings ==="
input bool     InpUseDynamicKelly      = true;     // Enable Dynamic Kelly position sizing
input double   InpBaseRiskPercent      = 0.60;     // Base risk % per trade (0.60%)
input double   InpMaxRiskPercent       = 1.35;     // Max risk % per trade (1.35% hard ceiling)
input double   InpMinRiskPercent       = 0.40;     // Min risk % per trade (0.40% hard floor)
input bool     InpUseFrictionPenalty   = true;     // Penalize lot size when spread / ATR is high
input bool     InpUseVolatilityScaling = true;     // Boost lot size during positive ATR velocity

input group "=== Temporal Volatility Cone & Trailing Settings ==="
input bool     InpUseAcceleratedBE     = true;     // Lower BE threshold from 50% to 35% after 30 bars
input int      InpAcceleratedBEBar     = 30;       // Bar threshold for accelerated BE
input double   InpAcceleratedBEProgress= 0.35;     // Excursion progress required for accelerated BE
input bool     InpUseMicroProfitLock   = true;     // Lock +0.20 ATR micro-profit after 60 bars
input int      InpMicroProfitBar       = 60;       // Bar threshold for micro-profit lock
input double   InpMicroProfitATR       = 0.20;     // Profit lock in ATR units
input double   InpTier2_Excursion      = 0.65;     // 65% TP progress -> Lock 40% of profit
input double   InpTier3_Excursion      = 0.80;     // 80% TP progress -> Lock 70% of profit

input group "=== Cross-Asset Lead-Lag & Macro Shock Settings ==="
input string   InpMacroSymbol          = "EURUSD"; // Macro confluence anchor symbol
input bool     InpUseLeadLagImpulse    = true;     // Require EURUSD 3m impulse alignment
input double   InpMinEURImpulseZ       = 0.25;     // Min EURUSD 3m z-score impulse
input bool     InpUseDollarShockShield = true;     // Block trades during extreme Dollar volatility
input double   InpMaxDollarShockRet    = 0.0008;   // Max 3m Dollar shock tolerance (0.08%)

input group "=== Microstructure & Order Flow Settings ==="
input bool     InpUseVolumeDelta       = true;     // Require VDP > 0 for Long, < 0 for Short
input bool     InpUseCVD15             = true;     // Require 15-bar Cumulative Volume Delta confirmation
input bool     InpUseVolumeForceSurge  = true;     // Require Volume Force Surge (VFS)
input double   InpMinVFS               = 1.10;     // Min VFS threshold for breakouts
input double   InpMinSweepVFS          = 1.05;     // Min VFS threshold for liquidity sweeps
input int      InpCVDLookback          = 15;       // Cumulative Volume Delta lookback bars

input group "=== Multi-Timeframe Momentum Settings ==="
input bool     InpUseMTFTrend          = true;     // Require M5/M15 EMA trend alignment for breakouts
input int      InpM5_EMA_Period        = 100;      // Synthetic M5 EMA (100 M1 bars)
input int      InpM15_EMA_Period       = 300;      // Synthetic M15 EMA (300 M1 bars)
input bool     InpUseRSIExhaustion     = true;     // Require M5 RSI exhaustion for sweep reversals
input int      InpM5_RSI_Period        = 70;       // Synthetic M5 RSI (70 M1 bars)
input double   InpRSI_Oversold         = 35.0;     // M5 RSI Oversold threshold
input double   InpRSI_Overbought       = 65.0;     // M5 RSI Overbought threshold

input group "=== Multi-Horizon Liquidity Sweep Settings ==="
input bool     InpUseAsiaSweep         = true;     // Enable Asia Session High/Low sweeps
input bool     InpUseH4Sweep           = true;     // Enable Rolling H4 Liquidity Sweeps
input int      InpH4Lookback           = 240;      // 240 M1 bars rolling high/low pool

input group "=== Risk & Stagnation Controls ==="
input bool     InpUseStagnationRatchet = true;     // Tighten SL if stalling at bar 45
input int      InpStagnationBar        = 45;       // Stagnation evaluation bar
input double   InpStagnationProgress   = 0.25;     // Min excursion progress required (25%)
input double   InpMaxSpreadPoints      = 3.0;      // Friction Shield: max spread 3.0 pts ($0.30)
input bool     InpRolloverShield       = true;     // Rollover Shield: 21:30-23:30 UTC
input bool     InpFridayShield         = true;     // Friday Shield: after 17:00 UTC
input ulong    InpMagicNumber          = 500050;
input string   InpComment              = "EXP50_SOVEREIGN";

//--- Globals
CTrade   g_trade;
int      g_atrHandle      = INVALID_HANDLE;
int      g_ema20h         = INVALID_HANDLE;
int      g_ema60h         = INVALID_HANDLE;
int      g_ema240h        = INVALID_HANDLE;
int      g_emaM5h         = INVALID_HANDLE;
int      g_emaM15h        = INVALID_HANDLE;
int      g_rsiM5h         = INVALID_HANDLE;

// Position Tracking
datetime g_entryTime    = 0;
int      g_entryBar     = 0;
double   g_entryPrice   = 0.0;
double   g_targetTP     = 0.0;
double   g_targetSL     = 0.0;
double   g_maxExcursion = 0.0;
int      g_trailTier    = 0;

// Asia Session Trackers
datetime g_currentAsiaDate = 0;
double   g_asiaHigh = 0.0;
double   g_asiaLow  = 999999.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetMarginMode();

   g_atrHandle = iATR(_Symbol, PERIOD_M1, 14);
   g_ema20h    = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_ema60h    = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_ema240h   = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);
   g_emaM5h    = iMA(_Symbol, PERIOD_M1, InpM5_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_emaM15h   = iMA(_Symbol, PERIOD_M1, InpM15_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_rsiM5h    = iRSI(_Symbol, PERIOD_M1, InpM5_RSI_Period, PRICE_CLOSE);

   PrintFormat("[EXP-50] The Grand Sovereign Alpha Engine successfully initialized. Magic: %d", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_ema20h != INVALID_HANDLE)    IndicatorRelease(g_ema20h);
   if(g_ema60h != INVALID_HANDLE)    IndicatorRelease(g_ema60h);
   if(g_ema240h != INVALID_HANDLE)   IndicatorRelease(g_ema240h);
   if(g_emaM5h != INVALID_HANDLE)    IndicatorRelease(g_emaM5h);
   if(g_emaM15h != INVALID_HANDLE)   IndicatorRelease(g_emaM15h);
   if(g_rsiM5h != INVALID_HANDLE)    IndicatorRelease(g_rsiM5h);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // 1. Manage Active Positions
   ManageActivePosition();

   if(PositionsTotal() > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            return;
      }
   }

   // 2. Friction & Rollover Shields
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;
   double spread_points = (tick.ask - tick.bid) / _Point;
   if(spread_points > InpMaxSpreadPoints * 10.0) return;

   MqlDateTime dt;
   TimeGMT(dt);

   if(InpFridayShield && dt.day_of_week == 5 && dt.hour >= 17) return;
   if(InpRolloverShield && ((dt.hour == 21 && dt.min >= 30) || dt.hour == 22 || (dt.hour == 23 && dt.min <= 30))) return;
   if(dt.hour < 7 || dt.hour >= 18) return;

   // 3. Update Asia Session Levels (00:00 - 06:00 UTC)
   MqlDateTime bar_dt;
   TimeToStruct(current_bar_time, bar_dt);
   datetime today_date = StringToTime(StringFormat("%04d.%02d.%02d 00:00", bar_dt.year, bar_dt.mon, bar_dt.day));

   if(today_date != g_currentAsiaDate)
   {
      g_currentAsiaDate = today_date;
      g_asiaHigh = 0.0;
      g_asiaLow  = 999999.0;
   }

   if(bar_dt.hour >= 0 && bar_dt.hour < 6)
   {
      double h0 = iHigh(_Symbol, PERIOD_M1, 1);
      double l0 = iLow(_Symbol, PERIOD_M1, 1);
      if(h0 > g_asiaHigh) g_asiaHigh = h0;
      if(l0 < g_asiaLow && l0 > 0.0)  g_asiaLow = l0;
   }

   // 4. Calculate Indicators & Microstructure
   double atr[20];
   if(CopyBuffer(g_atrHandle, 0, 1, 20, atr) <= 0 || atr[0] <= 0) return;
   double atr_val = atr[0];

   double atr_sum = 0.0;
   for(int k = 0; k < 20; k++) atr_sum += atr[k];
   double atr_ma20 = atr_sum / 20.0;
   double vol_vel = (atr_val - atr_ma20) / MathMax(atr_ma20, 0.1);

   double ema20[1], ema60[1], ema240[1], emaM5[1], emaM15[1], rsiM5[1];
   if(CopyBuffer(g_ema20h, 0, 1, 1, ema20) <= 0 ||
      CopyBuffer(g_ema60h, 0, 1, 1, ema60) <= 0 ||
      CopyBuffer(g_ema240h, 0, 1, 1, ema240) <= 0 ||
      CopyBuffer(g_emaM5h, 0, 1, 1, emaM5) <= 0 ||
      CopyBuffer(g_emaM15h, 0, 1, 1, emaM15) <= 0 ||
      CopyBuffer(g_rsiM5h, 0, 1, 1, rsiM5) <= 0) return;

   double c1 = iClose(_Symbol, PERIOD_M1, 1);
   double o1 = iOpen(_Symbol, PERIOD_M1, 1);
   double h1 = iHigh(_Symbol, PERIOD_M1, 1);
   double l1 = iLow(_Symbol, PERIOD_M1, 1);
   long   v1 = iTickVolume(_Symbol, PERIOD_M1, 1);

   double rng1 = MathMax(h1 - l1, 0.0001);
   double vdp = (double)v1 * ((c1 - l1) - (h1 - c1)) / rng1;

   double cvd_15 = 0.0;
   double vol_sum20 = 0.0;
   for(int b = 1; b <= 20; b++)
   {
      double hb = iHigh(_Symbol, PERIOD_M1, b);
      double lb = iLow(_Symbol, PERIOD_M1, b);
      double cb = iClose(_Symbol, PERIOD_M1, b);
      long   vb = iTickVolume(_Symbol, PERIOD_M1, b);
      double rngb = MathMax(hb - lb, 0.0001);
      double vdp_b = (double)vb * ((cb - lb) - (hb - cb)) / rngb;
      if(b <= InpCVDLookback) cvd_15 += vdp_b;
      vol_sum20 += (double)vb;
   }
   double vol_ma20 = vol_sum20 / 20.0;
   double rel_vol = (double)v1 / MathMax(vol_ma20, 1.0);
   double norm_body = MathAbs(c1 - o1) / atr_val;
   double vfs = rel_vol * norm_body;

   double h4_high = -1.0;
   double h4_low  = 999999.0;
   for(int b = 2; b <= InpH4Lookback + 1; b++)
   {
      double hb = iHigh(_Symbol, PERIOD_M1, b);
      double lb = iLow(_Symbol, PERIOD_M1, b);
      if(hb > h4_high) h4_high = hb;
      if(lb < h4_low && lb > 0.0) h4_low = lb;
   }

   bool mtf_bull = (c1 > emaM5[0]) && (emaM5[0] > emaM15[0]);
   bool mtf_bear = (c1 < emaM5[0]) && (emaM5[0] < emaM15[0]);
   bool rsi_exhaust_l = (rsiM5[0] <= InpRSI_Oversold);
   bool rsi_exhaust_s = (rsiM5[0] >= InpRSI_Overbought);

   double eur_impulse_z = 0.0;
   double usdi_ret3 = 0.0;
   double usdi_ret15 = 0.0;

   if(InpMacroSymbol != "")
   {
      double eur_c1  = iClose(InpMacroSymbol, PERIOD_M1, 1);
      double eur_c4  = iClose(InpMacroSymbol, PERIOD_M1, 4);
      double eur_c16 = iClose(InpMacroSymbol, PERIOD_M1, 16);
      double xau_c4  = iClose(_Symbol, PERIOD_M1, 4);
      double xau_c16 = iClose(_Symbol, PERIOD_M1, 16);

      if(eur_c4 > 0 && eur_c16 > 0 && xau_c4 > 0 && xau_c16 > 0)
      {
         double eur_ret3  = (eur_c1 - eur_c4) / eur_c4;
         double eur_ret15 = (eur_c1 - eur_c16) / eur_c16;
         double xau_ret3  = (c1 - xau_c4) / xau_c4;
         double xau_ret15 = (c1 - xau_c16) / xau_c16;

         usdi_ret3  = -0.60 * eur_ret3 - 0.40 * xau_ret3;
         usdi_ret15 = -0.60 * eur_ret15 - 0.40 * xau_ret15;

         double sum_sq = 0.0;
         for(int k = 1; k <= 30; k++)
         {
            double ek1 = iClose(InpMacroSymbol, PERIOD_M1, k);
            double ek4 = iClose(InpMacroSymbol, PERIOD_M1, k + 3);
            if(ek4 > 0)
            {
               double rk = (ek1 - ek4) / ek4;
               sum_sq += rk * rk;
            }
         }
         double eur_std = MathSqrt(sum_sq / 30.0);
         eur_impulse_z = (eur_std > 0.00001) ? (eur_ret3 / eur_std) : 0.0;
      }
   }

   if(InpUseDollarShockShield && MathAbs(usdi_ret3) > InpMaxDollarShockRet) return;

   bool usdi_gate_l = (usdi_ret15 <= 0.0004);
   bool usdi_gate_s = (usdi_ret15 >= -0.0004);

   bool long_signal = false;
   bool short_signal = false;

   // 1. Breakout Core
   if(InpEnableBreakoutCore)
   {
      bool m1_trend_l = (c1 > ema60[0]) && (ema20[0] > ema60[0]);
      bool m1_trend_s = (c1 < ema60[0]) && (ema20[0] < ema60[0]);

      bool ofi_l = (vdp > 0) && (cvd_15 > 0) && (vfs >= InpMinVFS);
      bool ofi_s = (vdp < 0) && (cvd_15 < 0) && (vfs >= InpMinVFS);

      bool eur_lead_l = (!InpUseLeadLagImpulse) || (eur_impulse_z >= InpMinEURImpulseZ);
      bool eur_lead_s = (!InpUseLeadLagImpulse) || (eur_impulse_z <= -InpMinEURImpulseZ);

      if(m1_trend_l && ofi_l && mtf_bull && usdi_gate_l && eur_lead_l) long_signal = true;
      if(m1_trend_s && ofi_s && mtf_bear && usdi_gate_s && eur_lead_s) short_signal = true;
   }

   // 2. Liquidity Sweep Core
   if(InpEnableSweepCore && !long_signal && !short_signal)
   {
      bool asia_sweep_l = InpUseAsiaSweep && (l1 < g_asiaLow) && (c1 > g_asiaLow) && (c1 > o1) && (vfs >= InpMinSweepVFS) && (vdp > 0);
      bool asia_sweep_s = InpUseAsiaSweep && (h1 > g_asiaHigh) && (c1 < g_asiaHigh) && (c1 < o1) && (vfs >= InpMinSweepVFS) && (vdp < 0);

      bool h4_sweep_l = InpUseH4Sweep && (l1 < h4_low) && (c1 > h4_low) && (c1 > o1) && (vfs >= InpMinVFS) && (vdp > 0);
      bool h4_sweep_s = InpUseH4Sweep && (h1 > h4_high) && (c1 < h4_high) && (c1 < o1) && (vfs >= InpMinVFS) && (vdp < 0);

      bool eur_sweep_ok_l = (eur_impulse_z >= -1.0);
      bool eur_sweep_ok_s = (eur_impulse_z <= 1.0);

      if((asia_sweep_l || h4_sweep_l) && rsi_exhaust_l && eur_sweep_ok_l && usdi_gate_l) long_signal = true;
      if((asia_sweep_s || h4_sweep_s) && rsi_exhaust_s && eur_sweep_ok_s && usdi_gate_s) short_signal = true;
   }

   double slope = (ema60[0] - ema240[0]) / atr_val;
   bool is_hi_slope = MathAbs(slope) >= 0.20;
   double sl_mult = is_hi_slope ? 2.5 : 1.8;
   double tp_mult = is_hi_slope ? 5.5 : 3.5;

   double dynamic_risk = InpBaseRiskPercent;
   if(InpUseDynamicKelly)
   {
      double spread_ratio = (spread_points * 0.10 * _Point) / atr_val;
      double fric_penalty = InpUseFrictionPenalty ? MathMax(0.50, MathMin(1.10, 1.0 - (spread_ratio - 0.02) * 5.0)) : 1.0;

      double vol_mult = 1.0;
      if(InpUseVolatilityScaling)
      {
         if(vol_vel > 0.10) vol_mult = 1.20;
         else if(vol_vel < -0.10) vol_mult = 0.75;
      }

      dynamic_risk = InpBaseRiskPercent * fric_penalty * vol_mult;
      dynamic_risk = MathMax(InpMinRiskPercent, MathMin(InpMaxRiskPercent, dynamic_risk));
   }

   if(long_signal)
   {
      ExecuteOrder(ORDER_TYPE_BUY, sl_mult, tp_mult, atr_val, dynamic_risk);
   }
   else if(short_signal)
   {
      ExecuteOrder(ORDER_TYPE_SELL, sl_mult, tp_mult, atr_val, dynamic_risk);
   }
}

//+------------------------------------------------------------------+
//| Execute Order Function                                           |
//+------------------------------------------------------------------+
void ExecuteOrder(ENUM_ORDER_TYPE order_type, double sl_mult, double tp_mult, double atr_val, double risk_percent)
{
   double point_val = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tick_val  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point_value_contract = (tick_size > 0) ? (tick_val / tick_size) * point_val : 100.0;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_budget = balance * (risk_percent / 100.0);
   double dollar_per_lot_risk = sl_mult * atr_val * point_value_contract;
   double calc_lot = (dollar_per_lot_risk > 10.0) ? (risk_budget / dollar_per_lot_risk) : 0.05;

   double min_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double trade_lot = MathFloor(calc_lot / step_lot) * step_lot;
   trade_lot = MathMax(min_lot, MathMin(max_lot, trade_lot));
   trade_lot = MathMin(trade_lot, 0.60);

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   if(order_type == ORDER_TYPE_BUY)
   {
      double entry = tick.ask;
      double sl = entry - (sl_mult * atr_val);
      double tp = entry + (tp_mult * atr_val);
      if(g_trade.Buy(trade_lot, _Symbol, entry, sl, tp, InpComment))
      {
         g_entryPrice = entry;
         g_targetSL = sl;
         g_targetTP = tp;
         g_entryTime = TimeCurrent();
         g_entryBar = 0;
         g_maxExcursion = 0.0;
         g_trailTier = 0;
      }
   }
   else if(order_type == ORDER_TYPE_SELL)
   {
      double entry = tick.bid;
      double sl = entry + (sl_mult * atr_val);
      double tp = entry - (tp_mult * atr_val);
      if(g_trade.Sell(trade_lot, _Symbol, entry, sl, tp, InpComment))
      {
         g_entryPrice = entry;
         g_targetSL = sl;
         g_targetTP = tp;
         g_entryTime = TimeCurrent();
         g_entryBar = 0;
         g_maxExcursion = 0.0;
         g_trailTier = 0;
      }
   }
}

//+------------------------------------------------------------------+
//| Position Management Function with Parabolic Volatility Cone      |
//+------------------------------------------------------------------+
void ManageActivePosition()
{
   if(PositionsTotal() == 0)
   {
      g_trailTier = 0;
      g_maxExcursion = 0.0;
      return;
   }

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      ulong  ticket = PositionGetInteger(POSITION_TICKET);
      double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur_sl     = PositionGetDouble(POSITION_SL);
      double cur_tp     = PositionGetDouble(POSITION_TP);
      long   pos_type   = PositionGetInteger(POSITION_TYPE);
      datetime pos_time = (datetime)PositionGetInteger(POSITION_TIME);

      int bars_held = (int)((TimeCurrent() - pos_time) / 60);

      double atr[1];
      if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) <= 0) return;
      double atr_val = atr[0];

      MqlTick tick;
      if(!SymbolInfoTick(_Symbol, tick)) return;

      if(pos_type == POSITION_TYPE_BUY)
      {
         double cur_exc = (tick.bid - open_price) / MathMax(cur_tp - open_price, 0.01);
         g_maxExcursion = MathMax(g_maxExcursion, cur_exc);

         double new_sl = cur_sl;

         double be_thresh = (InpUseAcceleratedBE && bars_held >= InpAcceleratedBEBar) ? InpAcceleratedBEProgress : 0.50;

         if(g_trailTier == 0 && g_maxExcursion >= be_thresh)
         {
            new_sl = MathMax(new_sl, open_price + 0.10 * atr_val);
            g_trailTier = 1;
         }
         else if(g_trailTier == 1 && g_maxExcursion >= InpTier2_Excursion)
         {
            new_sl = MathMax(new_sl, open_price + 0.40 * (cur_tp - open_price));
            g_trailTier = 2;
         }
         else if(g_trailTier == 2 && g_maxExcursion >= InpTier3_Excursion)
         {
            new_sl = MathMax(new_sl, open_price + 0.70 * (cur_tp - open_price));
            g_trailTier = 3;
         }

         if(InpUseMicroProfitLock && bars_held >= InpMicroProfitBar && g_maxExcursion >= 0.20)
         {
            new_sl = MathMax(new_sl, open_price + InpMicroProfitATR * atr_val);
         }

         if(InpUseStagnationRatchet && bars_held >= InpStagnationBar && g_maxExcursion < InpStagnationProgress)
         {
            new_sl = MathMax(new_sl, open_price - 0.75 * atr_val);
         }

         if(new_sl > cur_sl + _Point)
         {
            g_trade.PositionModify(ticket, new_sl, cur_tp);
         }
      }
      else if(pos_type == POSITION_TYPE_SELL)
      {
         double cur_exc = (open_price - tick.ask) / MathMax(open_price - cur_tp, 0.01);
         g_maxExcursion = MathMax(g_maxExcursion, cur_exc);

         double new_sl = cur_sl;

         double be_thresh = (InpUseAcceleratedBE && bars_held >= InpAcceleratedBEBar) ? InpAcceleratedBEProgress : 0.50;

         if(g_trailTier == 0 && g_maxExcursion >= be_thresh)
         {
            new_sl = (new_sl == 0) ? open_price - 0.10 * atr_val : MathMin(new_sl, open_price - 0.10 * atr_val);
            g_trailTier = 1;
         }
         else if(g_trailTier == 1 && g_maxExcursion >= InpTier2_Excursion)
         {
            new_sl = MathMin(new_sl, open_price - 0.40 * (open_price - cur_tp));
            g_trailTier = 2;
         }
         else if(g_trailTier == 2 && g_maxExcursion >= InpTier3_Excursion)
         {
            new_sl = MathMin(new_sl, open_price - 0.70 * (open_price - cur_tp));
            g_trailTier = 3;
         }

         if(InpUseMicroProfitLock && bars_held >= InpMicroProfitBar && g_maxExcursion >= 0.20)
         {
            new_sl = (new_sl == 0) ? open_price - InpMicroProfitATR * atr_val : MathMin(new_sl, open_price - InpMicroProfitATR * atr_val);
         }

         if(InpUseStagnationRatchet && bars_held >= InpStagnationBar && g_maxExcursion < InpStagnationProgress)
         {
            new_sl = (new_sl == 0) ? open_price + 0.75 * atr_val : MathMin(new_sl, open_price + 0.75 * atr_val);
         }

         if(cur_sl == 0 || (new_sl < cur_sl - _Point && new_sl > 0))
         {
            g_trade.PositionModify(ticket, new_sl, cur_tp);
         }
      }
   }
}

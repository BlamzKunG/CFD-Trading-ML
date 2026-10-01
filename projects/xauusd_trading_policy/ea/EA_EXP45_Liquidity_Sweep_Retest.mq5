//+------------------------------------------------------------------+
//|  EA_EXP45_Liquidity_Sweep_Retest.mq5                             |
//|  XAUUSD M1 — Multi-Horizon Liquidity Sweep & Swept-Level Retest  |
//|  Research: Autonomous Quant ML Research EXP-45                   |
//|                                                                  |
//|  Key Innovations:                                                |
//|  1. Asia Session Liquidity Pool (00:00-06:00 UTC High/Low)       |
//|  2. Rolling H4 Liquidity Pool (240-bar High/Low)                 |
//|  3. Microstructure Sweep Reclaim Detection with VFS >= 1.05      |
//|  4. Dual-Engine Portfolio: OFI Breakouts + Liquidity Sweeps      |
//|  5. Synthetic USDi Macro Gating (EURUSD 15m return inverse)       |
//|  6. 3-Tier Asymmetric Profit-Harvesting Excursion Trailing (APHE)|
//|  7. 45-Bar Accelerated Stagnation Ratchet                        |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-45 MLS-SLRE"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== Liquidity Sweep Settings ==="
input bool     InpEnableAsiaSweeps     = true;     // Enable Asia Session High/Low Sweeps
input bool     InpEnableH4Sweeps       = true;     // Enable Rolling H4 High/Low Sweeps
input bool     InpEnableOFIBreakouts   = true;     // Enable EXP-44 Order Flow Breakouts
input double   InpMinVFS               = 1.05;     // Min Volume Force Surge on Sweep Reclaim

input group "=== Macro Gating Settings ==="
input string   InpMacroSymbol          = "EURUSD"; // Macro confluence anchor symbol
input double   InpMaxUSDiRet           = 0.0004;   // Max USDi return tolerance (+0.04% / -0.04%)

input group "=== Asymmetric Profit-Harvesting (APHE) ==="
input bool     InpUseAPHE              = true;     // Enable 3-Tier Excursion Trailing
input double   InpTier1_Excursion      = 0.50;     // 50% TP progress -> Lock Breakeven (+0.1 ATR)
input double   InpTier2_Excursion      = 0.70;     // 70% TP progress -> Lock 35% of profit
input double   InpTier3_Excursion      = 0.85;     // 85% TP progress -> Lock 65% of profit

input group "=== Risk & Stagnation Controls ==="
input double   InpRiskPercent          = 0.85;     // Account risk % per trade (0.85% VTS)
input bool     InpUseStagnationRatchet = true;     // Tighten SL if stalling at bar 45
input int      InpStagnationBar        = 45;       // Stagnation evaluation bar
input double   InpStagnationProgress   = 0.25;     // Min excursion progress required (25%)
input double   InpMaxSpreadPoints      = 3.0;      // Friction Shield: max spread 3.0 pts ($0.30)
input bool     InpRolloverShield       = true;     // Rollover Shield: 21:30-23:30 UTC
input bool     InpFridayShield         = true;     // Friday Shield: after 17:00 UTC
input ulong    InpMagicNumber          = 450045;
input string   InpComment              = "EXP45_LiquiditySweep";

//--- Globals
CTrade   g_trade;
int      g_atrHandle  = INVALID_HANDLE;
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

// Asia Levels Cache
datetime g_currentAsiaDate = 0;
double   g_asiaHigh = 0.0;
double   g_asiaLow  = 0.0;

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

   PrintFormat("[EXP-45] Successfully initialized Liquidity Sweep & Retest EA. Magic: %d", InpMagicNumber);
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
}

//+------------------------------------------------------------------+
//| Update Asia Session High/Low (00:00 - 06:00 UTC)                 |
//+------------------------------------------------------------------+
void UpdateAsiaLevels()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime today_midnight = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(today_midnight != g_currentAsiaDate)
   {
      g_currentAsiaDate = today_midnight;
      g_asiaHigh = 0.0;
      g_asiaLow  = 999999.0;
   }

   // Accumulate during 00:00 to 06:00 UTC
   if(dt.hour >= 0 && dt.hour < 6)
   {
      double h = iHigh(_Symbol, PERIOD_M1, 1);
      double l = iLow(_Symbol, PERIOD_M1, 1);
      if(h > g_asiaHigh) g_asiaHigh = h;
      if(l < g_asiaLow && l > 0.0)  g_asiaLow  = l;
   }
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

   UpdateAsiaLevels();

   // 1. Friction & Spread Shield
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread = (ask - bid) / (point * 10.0);

   if(spread > InpMaxSpreadPoints) return;

   // 2. Timing and Session Filters
   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;
   int minute = dt.min;
   int dow = dt.day_of_week;

   if(InpFridayShield && dow == 5 && hour >= 17) return;
   if(InpRolloverShield && ((hour == 21 && minute >= 30) || hour == 22 || (hour == 23 && minute <= 30))) return;
   if(hour < 7 || hour >= 19) return;

   // 3. Manage Open Positions
   ManageActivePosition();

   if(PositionsTotal() > 0) return;

   // 4. Cross-Asset EURUSD Filter
   double eur_close1 = iClose(InpMacroSymbol, PERIOD_M1, 1);
   double eur_close16 = iClose(InpMacroSymbol, PERIOD_M1, 16);
   if(eur_close16 <= 0.0) return;
   double eur_ret15 = (eur_close1 - eur_close16) / eur_close16;

   // 5. Technical Context & Rates
   double atr_val = GetIndicatorVal(g_atrHandle, 1);
   if(atr_val <= 0.0) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 245, rates) < 245) return;

   double c1 = rates[0].close;
   double o1 = rates[0].open;
   double h1 = rates[0].high;
   double l1 = rates[0].low;

   // Rolling H4 High/Low (240 bars)
   double h4_high = rates[1].high;
   double h4_low  = rates[1].low;
   for(int i = 2; i <= 240; i++)
   {
      if(rates[i].high > h4_high) h4_high = rates[i].high;
      if(rates[i].low < h4_low && rates[i].low > 0.0) h4_low = rates[i].low;
   }

   // Microstructure Volume Features
   double rng1 = MathMax(h1 - l1, point);
   double vdp1 = (double)rates[0].tick_volume * ((c1 - l1) - (h1 - c1)) / rng1;

   double total_vol20 = 0.0;
   for(int i = 0; i < 20; i++) total_vol20 += (double)rates[i].tick_volume;
   double vol_ma20 = total_vol20 / 20.0;
   double rel_vol = (double)rates[0].tick_volume / MathMax(vol_ma20, 1.0);
   double norm_body = MathAbs(c1 - o1) / atr_val;
   double vfs = rel_vol * norm_body;

   // 6. Signal Triggers
   bool sig_buy = false;
   bool sig_sell = false;
   string sig_reason = "";

   // A. Asia Session Liquidity Sweep Reversals
   if(InpEnableAsiaSweeps && g_asiaHigh > 0.0 && g_asiaLow < 900000.0)
   {
      if(l1 < g_asiaLow && c1 > g_asiaLow && c1 > o1 && vfs >= InpMinVFS && vdp1 > 0)
      {
         sig_buy = true;
         sig_reason = "Asia_Sweep_Reclaim";
      }
      else if(h1 > g_asiaHigh && c1 < g_asiaHigh && c1 < o1 && vfs >= InpMinVFS && vdp1 < 0)
      {
         sig_sell = true;
         sig_reason = "Asia_Sweep_Reclaim";
      }
   }

   // B. Rolling H4 Liquidity Sweep Reversals
   if(InpEnableH4Sweeps && !sig_buy && !sig_sell)
   {
      if(l1 < h4_low && c1 > h4_low && c1 > o1 && vfs >= InpMinVFS && vdp1 > 0)
      {
         sig_buy = true;
         sig_reason = "H4_Sweep_Reclaim";
      }
      else if(h1 > h4_high && c1 < h4_high && c1 < o1 && vfs >= InpMinVFS && vdp1 < 0)
      {
         sig_sell = true;
         sig_reason = "H4_Sweep_Reclaim";
      }
   }

   // C. EXP-44 OFI Breakouts
   if(InpEnableOFIBreakouts && !sig_buy && !sig_sell)
   {
      double ema20  = GetIndicatorVal(g_ema20h, 1);
      double ema60  = GetIndicatorVal(g_ema60h, 1);
      double ema240 = GetIndicatorVal(g_ema240h, 1);
      double slope  = (ema60 - ema240) / atr_val;

      bool trend_l = (c1 > ema60) && (ema20 > ema60);
      bool trend_s = (c1 < ema60) && (ema20 < ema60);

      double time_float = hour + minute / 60.0;
      bool is_sleeve_a = ((time_float >= 7.0 && time_float <= 11.0) || (time_float >= 12.5 && time_float <= 16.0));
      bool is_sleeve_b = ((time_float > 11.0 && time_float < 12.5) || (time_float > 16.0 && time_float <= 18.5));

      bool breakout_l = (c1 > rates[1].high) && trend_l && (is_sleeve_a || (is_sleeve_b && slope > 0.20));
      bool breakout_s = (c1 < rates[1].low) && trend_s && (is_sleeve_a || (is_sleeve_b && slope < -0.20));

      double cvd15 = 0.0;
      for(int i = 0; i < 15; i++)
      {
         double r_i = MathMax(rates[i].high - rates[i].low, point);
         cvd15 += (double)rates[i].tick_volume * ((rates[i].close - rates[i].low) - (rates[i].high - rates[i].close)) / r_i;
      }

      if(breakout_l && vdp1 > 0 && cvd15 > 0 && vfs >= 1.10)
      {
         sig_buy = true;
         sig_reason = "OFI_Breakout";
      }
      else if(breakout_s && vdp1 < 0 && cvd15 < 0 && vfs >= 1.10)
      {
         sig_sell = true;
         sig_reason = "OFI_Breakout";
      }
   }

   // 7. Sizing & Order Execution
   double sl_mult = 2.0;
   double tp_mult = 3.5;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_usd = balance * (InpRiskPercent / 100.0);
   double sl_dist = sl_mult * atr_val;
   double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_sz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double lot = (sl_dist > 0 && tick_val > 0) ? (risk_usd / (sl_dist / tick_sz * tick_val)) : 0.02;
   lot = MathMax(0.02, MathMin(0.50, NormalizeDouble(lot, 2)));

   // BUY Signal
   if(sig_buy && eur_ret15 >= -InpMaxUSDiRet)
   {
      double sl = NormalizeDouble(ask - sl_dist, _Digits);
      double tp = NormalizeDouble(ask + tp_mult * atr_val, _Digits);

      if(g_trade.Buy(lot, _Symbol, ask, sl, tp, InpComment))
      {
         g_entryTime    = TimeCurrent();
         g_entryBar     = 0;
         g_entryPrice   = ask;
         g_targetTP     = tp;
         g_targetSL     = sl;
         g_maxExcursion = 0.0;
         g_trailTier    = 0;
         PrintFormat("[EXP-45] BUY executed (%s): %.2f lots at %.2f, SL: %.2f, TP: %.2f (VFS: %.2f)",
                     sig_reason, lot, ask, sl, tp, vfs);
      }
   }
   // SELL Signal
   else if(sig_sell && eur_ret15 <= InpMaxUSDiRet)
   {
      double sl = NormalizeDouble(bid + sl_dist, _Digits);
      double tp = NormalizeDouble(bid - tp_mult * atr_val, _Digits);

      if(g_trade.Sell(lot, _Symbol, bid, sl, tp, InpComment))
      {
         g_entryTime    = TimeCurrent();
         g_entryBar     = 0;
         g_entryPrice   = bid;
         g_targetTP     = tp;
         g_targetSL     = sl;
         g_maxExcursion = 0.0;
         g_trailTier    = 0;
         PrintFormat("[EXP-45] SELL executed (%s): %.2f lots at %.2f, SL: %.2f, TP: %.2f (VFS: %.2f)",
                     sig_reason, lot, bid, sl, tp, vfs);
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Positions with 3-Tier APHE & Stagnation Ratchet    |
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
   double atr_val = GetIndicatorVal(g_atrHandle, 1);

   if(g_entryBar >= 180)
   {
      g_trade.PositionClose(_Symbol);
      Print("[EXP-45] Closed position due to Max Holding Period (180 bars).");
      return;
   }

   if(pos_type == POSITION_TYPE_BUY)
   {
      double full_range = MathMax(g_targetTP - g_entryPrice, 0.01);
      double cur_excursion = (high_1 - g_entryPrice) / full_range;
      g_maxExcursion = MathMax(g_maxExcursion, cur_excursion);

      double new_sl = cur_sl;

      // 3-Tier APHE Ladder
      if(InpUseAPHE)
      {
         if(g_trailTier == 0 && g_maxExcursion >= InpTier1_Excursion)
         {
            new_sl = MathMax(new_sl, g_entryPrice + 0.10 * atr_val);
            g_trailTier = 1;
         }
         else if(g_trailTier == 1 && g_maxExcursion >= InpTier2_Excursion)
         {
            new_sl = MathMax(new_sl, g_entryPrice + 0.35 * full_range);
            g_trailTier = 2;
         }
         else if(g_trailTier == 2 && g_maxExcursion >= InpTier3_Excursion)
         {
            new_sl = MathMax(new_sl, g_entryPrice + 0.65 * full_range);
            g_trailTier = 3;
         }
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
         PrintFormat("[EXP-45] Ratchet BUY SL to %.2f (Tier: %d, Excursion: %.1f%%)", new_sl, g_trailTier, g_maxExcursion * 100.0);
      }
   }
   else if(pos_type == POSITION_TYPE_SELL)
   {
      double full_range = MathMax(g_entryPrice - g_targetTP, 0.01);
      double cur_excursion = (g_entryPrice - low_1) / full_range;
      g_maxExcursion = MathMax(g_maxExcursion, cur_excursion);

      double new_sl = cur_sl;

      // 3-Tier APHE Ladder
      if(InpUseAPHE)
      {
         if(g_trailTier == 0 && g_maxExcursion >= InpTier1_Excursion)
         {
            new_sl = MathMin(new_sl, g_entryPrice - 0.10 * atr_val);
            g_trailTier = 1;
         }
         else if(g_trailTier == 1 && g_maxExcursion >= InpTier2_Excursion)
         {
            new_sl = MathMin(new_sl, g_entryPrice - 0.35 * full_range);
            g_trailTier = 2;
         }
         else if(g_trailTier == 2 && g_maxExcursion >= InpTier3_Excursion)
         {
            new_sl = MathMin(new_sl, g_entryPrice - 0.65 * full_range);
            g_trailTier = 3;
         }
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
         PrintFormat("[EXP-45] Ratchet SELL SL to %.2f (Tier: %d, Excursion: %.1f%%)", new_sl, g_trailTier, g_maxExcursion * 100.0);
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

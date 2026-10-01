//+------------------------------------------------------------------+
//|                        EA_EXP60_Multi_Horizon_Liquidity_Sweeps.mq5 |
//|                                  Copyright 2026, Quant ML Research Bot   |
//|                                      https://github.com/BlamzKunG/       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant ML Research Engine"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "EXP-60: Multi-Horizon Liquidity Sweeps & Imbalance Retest Engine (MHLS-IRE)"
#property description "Multi-Horizon Structural Absorption: 1-Bar Pinbar, 2/3-Bar Composite Hammers, M5 Sweep Traps, FVG Retests"
#property description "Real-Chart Execution with 2-Stage Asymmetric ATR Trailing Ladder"

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Institutional Risk Management ==="
input ulong    InpMagicNumber         = 600001;       // Magic Number
input double   InpRiskPercent         = 1.0;          // Base Risk per Trade (%)
input double   InpGoldSLMultiplier    = 1.8;          // Gold SL ATR Multiplier
input double   InpGoldTPMultiplier    = 3.8;          // Gold TP ATR Multiplier
input double   InpGoldBETriggerATR    = 1.5;          // Gold Breakeven Trigger (x ATR)
input double   InpGoldLockTriggerATR  = 2.8;          // Gold Profit Lock Trigger (x ATR)
input double   InpGoldBEBufferATR     = 0.10;         // Gold BE Buffer (x ATR)
input double   InpGoldLockBufferATR   = 1.20;         // Gold Profit Lock Buffer (x ATR)

input group "=== Cross-Asset Information Transmission ==="
input string   InpEurSymbol           = "EURUSD";     // EURUSD Leading Symbol
input double   InpEurImpulseThreshold = 0.15;         // EURUSD Z-Score Lead Threshold

input group "=== Multi-Horizon Structural Sleeves ==="
input bool     InpEnableSleeveA       = true;         // Enable Sleeve A (Sovereign 1-Bar Pinbar Fortress)
input bool     InpEnableSleeveB       = true;         // Enable Sleeve B (Multi-Bar Composite Hammers)
input bool     InpEnableSleeveC       = true;         // Enable Sleeve C (M5 Liquidity Sweep Trap)
input bool     InpEnableSleeveD       = true;         // Enable Sleeve D (FVG Imbalance Retest Absorption)
input int      InpAtrPeriod           = 14;           // ATR Period

//--- Global Objects & Handles
CTrade         m_trade;
int            h_atr_xau;
int            h_ema20_xau;
int            h_ema60_xau;
int            h_ema_m5_xau;
int            h_ema_m15_xau;
int            h_atr_eur;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   h_atr_xau    = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   h_ema20_xau  = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60_xau  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m5_xau = iMA(_Symbol, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m15_xau= iMA(_Symbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   h_atr_eur    = iATR(InpEurSymbol, PERIOD_M1, InpAtrPeriod);

   Print("✅ EA_EXP60_Multi_Horizon_Liquidity_Sweeps successfully initialized.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr_xau);
   IndicatorRelease(h_ema20_xau);
   IndicatorRelease(h_ema60_xau);
   IndicatorRelease(h_ema_m5_xau);
   IndicatorRelease(h_ema_m15_xau);
   IndicatorRelease(h_atr_eur);
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double GetATR(int handle, int shift=1)
{
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) > 0) return buf[0];
   return 0.0;
}

double GetMA(int handle, int shift=1)
{
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) > 0) return buf[0];
   return 0.0;
}

double CalculateLotSize(string sym, double sl_distance)
{
   if(sl_distance <= 0) return 0.01;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (InpRiskPercent / 100.0);
   double tick_size = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);

   if(tick_size == 0 || tick_value == 0 || point == 0) return 0.01;

   double points = sl_distance / point;
   double risk_per_lot = (points * (tick_value / tick_size * point));
   if(risk_per_lot <= 0) return 0.01;

   double lot = risk_amount / risk_per_lot;
   double min_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double step_lot= SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   lot = MathFloor(lot / step_lot) * step_lot;
   return MathMax(min_lot, MathMin(max_lot, lot));
}

//+------------------------------------------------------------------+
//| Manage Trailing Ladder                                           |
//+------------------------------------------------------------------+
void ManageTrailingLadder(string sym, ulong magic, double atr)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != sym) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;

      double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      double current_sl = PositionGetDouble(POSITION_SL);
      double current_tp = PositionGetDouble(POSITION_TP);
      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

      double current_price = (type == POSITION_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
      double profit_dist = (type == POSITION_TYPE_BUY) ? (current_price - open_price) : (open_price - current_price);

      if(type == POSITION_TYPE_BUY)
      {
         // Stage 1: Breakeven
         if(profit_dist >= InpGoldBETriggerATR * atr && current_sl < open_price)
         {
            double new_sl = open_price + InpGoldBEBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
         // Stage 2: Profit Lock Ladder
         if(profit_dist >= InpGoldLockTriggerATR * atr && current_sl < (open_price + InpGoldLockBufferATR * atr))
         {
            double new_sl = open_price + InpGoldLockBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         // Stage 1: Breakeven
         if(profit_dist >= InpGoldBETriggerATR * atr && (current_sl > open_price || current_sl == 0))
         {
            double new_sl = open_price - InpGoldBEBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
         // Stage 2: Profit Lock Ladder
         if(profit_dist >= InpGoldLockTriggerATR * atr && current_sl > (open_price - InpGoldLockBufferATR * atr))
         {
            double new_sl = open_price - InpGoldLockBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| OnTick Handler                                                   |
//+------------------------------------------------------------------+
void OnTick()
{
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);

   double atr_xau = GetATR(h_atr_xau, 1);
   if(atr_xau <= 0) return;

   // Manage active positions trailing ladder every tick
   ManageTrailingLadder(_Symbol, InpMagicNumber, atr_xau);

   // New Bar Evaluation for Entry Triggers
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // Avoid Friday rollover risk
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   // Ensure single position
   if(PositionsTotal() > 0)
   {
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            return;
      }
   }

   // Session filter: European and US liquid hours
   double time_float = dt.hour + dt.min / 60.0;
   bool is_trade_session = (time_float >= 7.0 && time_float < 19.0);
   if(!is_trade_session) return;

   // Read Market State Data
   MqlRates rates_xau[65];
   if(CopyRates(_Symbol, PERIOD_M1, 1, 65, rates_xau) < 65) return;

   MqlRates rates_eur[10];
   if(CopyRates(InpEurSymbol, PERIOD_M1, 1, 10, rates_eur) < 10) return;

   double c_xau = rates_xau[0].close;
   double o_xau = rates_xau[0].open;
   double h_xau = rates_xau[0].high;
   double l_xau = rates_xau[0].low;
   long vol_xau = rates_xau[0].tick_volume;

   double ema20 = GetMA(h_ema20_xau, 1);
   double ema60 = GetMA(h_ema60_xau, 1);
   double ema_m5 = GetMA(h_ema_m5_xau, 1);
   double ema_m15 = GetMA(h_ema_m15_xau, 1);

   bool mtf_bull = (c_xau > ema60) && (ema20 > ema60) && (c_xau > ema_m5) && (ema_m5 > ema_m15);
   if(!mtf_bull) return;

   // Candle Geometry
   double rng_xau = MathMax(h_xau - l_xau, 0.01);
   double upper_wick = h_xau - MathMax(c_xau, o_xau);
   double lower_wick = MathMin(c_xau, o_xau) - l_xau;

   // EURUSD Velocity Lead
   double eur_ret3 = (rates_eur[0].close - rates_eur[2].open) / MathMax(rates_eur[2].open, 0.0001);
   bool eur_lead_bull = (eur_ret3 >= InpEurImpulseThreshold * 0.0001);

   bool trigger_long = false;
   string sleeve_used = "";

   // --- Sleeve A: Sovereign 1-Bar Pinbar Fortress Baseline
   if(InpEnableSleeveA && !trigger_long)
   {
      bool pinbar_1b = (lower_wick >= 0.38 * rng_xau) && (upper_wick <= 0.28 * rng_xau) && (c_xau >= o_xau);
      if(pinbar_1b && eur_lead_bull)
      {
         trigger_long = true;
         sleeve_used = "Sleeve_A_Pinbar_1B";
      }
   }

   // --- Sleeve B: Multi-Bar Composite Absorption Pinbars (2-Bar & 3-Bar Hammers)
   if(InpEnableSleeveB && !trigger_long)
   {
      // 2-Bar Composite: rates_xau[0] (t) + rates_xau[1] (t-1)
      double comp2_low = MathMin(rates_xau[0].low, rates_xau[1].low);
      double comp2_high = MathMax(rates_xau[0].high, rates_xau[1].high);
      double comp2_open = rates_xau[1].open;
      double comp2_close = rates_xau[0].close;
      double comp2_rng = MathMax(comp2_high - comp2_low, 0.01);
      double comp2_lwick = MathMin(comp2_close, comp2_open) - comp2_low;
      double comp2_uwick = comp2_high - MathMax(comp2_close, comp2_open);
      bool comp2_hammer = (comp2_lwick >= 0.38 * comp2_rng) && (comp2_uwick <= 0.30 * comp2_rng) && (comp2_close >= comp2_open);

      // 3-Bar Composite: rates_xau[0] (t) + rates_xau[1] (t-1) + rates_xau[2] (t-2)
      double comp3_low = MathMin(rates_xau[0].low, MathMin(rates_xau[1].low, rates_xau[2].low));
      double comp3_high = MathMax(rates_xau[0].high, MathMax(rates_xau[1].high, rates_xau[2].high));
      double comp3_open = rates_xau[2].open;
      double comp3_close = rates_xau[0].close;
      double comp3_rng = MathMax(comp3_high - comp3_low, 0.01);
      double comp3_lwick = MathMin(comp3_close, comp3_open) - comp3_low;
      double comp3_uwick = comp3_high - MathMax(comp3_close, comp3_open);
      bool comp3_hammer = (comp3_lwick >= 0.40 * comp3_rng) && (comp3_uwick <= 0.30 * comp3_rng) && (comp3_close >= comp3_open);

      if((comp2_hammer || comp3_hammer) && eur_lead_bull)
      {
         trigger_long = true;
         sleeve_used = "Sleeve_B_Composite_Hammers";
      }
   }

   // --- Sleeve C: Multi-Timeframe M5 Liquidity Sweep Trap (MLST)
   if(InpEnableSleeveC && !trigger_long)
   {
      double swing_low_60 = rates_xau[1].low;
      for(int k = 2; k <= 60; k++)
      {
         if(rates_xau[k].low < swing_low_60) swing_low_60 = rates_xau[k].low;
      }
      bool sweep_trap = (l_xau < swing_low_60) && (c_xau > swing_low_60 + 0.10 * atr_xau);
      if(sweep_trap)
      {
         trigger_long = true;
         sleeve_used = "Sleeve_C_Sweep_Trap";
      }
   }

   // --- Sleeve D: Fair Value Gap (FVG) Imbalance Retest Absorption
   if(InpEnableSleeveD && !trigger_long)
   {
      // Check for FVG formation in bars 3 to 10
      for(int k = 3; k <= 10; k++)
      {
         if(rates_xau[k].low > rates_xau[k+2].high && (rates_xau[k].close - rates_xau[k].open) >= 0.70 * atr_xau)
         {
            double fvg_top = rates_xau[k].low;
            double fvg_bot = rates_xau[k+2].high;
            if(l_xau <= fvg_top && c_xau >= fvg_bot && lower_wick >= 0.25 * rng_xau && c_xau >= o_xau)
            {
               trigger_long = true;
               sleeve_used = "Sleeve_D_FVG_Retest";
               break;
            }
         }
      }
   }

   // Execute Order on Real-Chart Levels
   if(trigger_long)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl_dist = InpGoldSLMultiplier * atr_xau;
      double sl = ask - sl_dist;
      double tp = ask + (InpGoldTPMultiplier * atr_xau);
      double lot = CalculateLotSize(_Symbol, sl_dist);

      if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "EXP60_" + sleeve_used))
      {
         PrintFormat("🎯 [EXP-60 ENTRY] Sleeve: %s | Ask: %.2f | SL: %.2f | TP: %.2f | Lot: %.2f | ATR: %.2f",
                     sleeve_used, ask, sl, tp, lot, atr_xau);
      }
   }
}
//+------------------------------------------------------------------+

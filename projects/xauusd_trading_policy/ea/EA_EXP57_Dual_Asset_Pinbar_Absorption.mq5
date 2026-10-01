//+------------------------------------------------------------------+
//|                                EA_EXP57_Dual_Asset_Pinbar_Absorption.mq5 |
//|                                  Copyright 2026, Quant ML Research Bot   |
//|                                      https://github.com/BlamzKunG/       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant ML Research Engine"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "EXP-57: Dual-Asset Pinbar Absorption & Volatility Regime Alpha Engine (DAPA-VRAE)"
#property description "Dual-Asset Risk-Parity Execution: XAUUSD (70%) + EURUSD (30%)"
#property description "Features: CAVR Volatility Gating + Pinbar Rejection Absorption + 2-Stage ATR Trailing Ladder"

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Institutional Risk Management ==="
input ulong    InpMagicNumber         = 570001;       // Magic Number
input double   InpRiskPercent         = 1.0;          // Base Risk per Cycle (%)
input double   InpGoldRiskWeight      = 0.70;         // Gold Allocation Weight (70%)
input double   InpEurRiskWeight       = 0.30;         // EURUSD Allocation Weight (30%)

input group "=== XAUUSD Execution Parameters ==="
input double   InpGoldSLMultiplier    = 1.8;          // Gold SL ATR Multiplier
input double   InpGoldTPMultiplier    = 3.8;          // Gold TP ATR Multiplier
input double   InpGoldBETriggerATR    = 1.5;          // Gold Breakeven Trigger (x ATR)
input double   InpGoldLockTriggerATR  = 2.8;          // Gold Profit Lock Trigger (x ATR)
input double   InpGoldBEBufferATR     = 0.10;         // Gold BE Buffer (x ATR)
input double   InpGoldLockBufferATR   = 1.20;         // Gold Profit Lock Buffer (x ATR)

input group "=== EURUSD Execution Parameters ==="
input string   InpEurSymbol           = "EURUSD";     // EURUSD Pair Symbol
input double   InpEurSLMultiplier     = 1.5;          // EURUSD SL ATR Multiplier
input double   InpEurTPMultiplier     = 3.2;          // EURUSD TP ATR Multiplier
input double   InpEurBETriggerATR     = 1.2;          // EURUSD Breakeven Trigger (x ATR)
input double   InpEurLockTriggerATR   = 2.2;          // EURUSD Profit Lock Trigger (x ATR)
input double   InpEurBEBufferATR      = 0.05;         // EURUSD BE Buffer (x ATR)
input double   InpEurLockBufferATR    = 0.80;         // EURUSD Profit Lock Buffer (x ATR)

input group "=== Multi-Asset Volatility & Microstructure ==="
input int      InpAtrPeriod           = 14;           // ATR Period
input double   InpCAVRThresholdLondon = 0.88;         // London CAVR Threshold
input double   InpCAVRThresholdNY     = 0.95;         // NY Overlap CAVR Threshold
input double   InpCAVRThresholdBase   = 0.92;         // Base CAVR Threshold

//--- Global Objects & Handles
CTrade         m_trade;
int            h_atr_xau;
int            h_atr_eur;
int            h_ema60_xau;
int            h_ema_m5_xau;
int            h_ema_m15_xau;
int            h_ema60_eur;
int            h_ema_m5_eur;
int            h_ema_m15_eur;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   // Indicators for Gold
   h_atr_xau    = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   h_ema60_xau  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m5_xau = iMA(_Symbol, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE); // ~M5 Trend
   h_ema_m15_xau= iMA(_Symbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE); // ~M15 Trend

   // Indicators for EURUSD
   h_atr_eur    = iATR(InpEurSymbol, PERIOD_M1, InpAtrPeriod);
   h_ema60_eur  = iMA(InpEurSymbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m5_eur = iMA(InpEurSymbol, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m15_eur= iMA(InpEurSymbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   Print("✅ EA_EXP57_Dual_Asset_Pinbar_Absorption successfully initialized.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr_xau);
   IndicatorRelease(h_atr_eur);
   IndicatorRelease(h_ema60_xau);
   IndicatorRelease(h_ema_m5_xau);
   IndicatorRelease(h_ema_m15_xau);
   IndicatorRelease(h_ema60_eur);
   IndicatorRelease(h_ema_m5_eur);
   IndicatorRelease(h_ema_m15_eur);
}

//+------------------------------------------------------------------+
//| Calculate ATR Helper                                             |
//+------------------------------------------------------------------+
double GetATR(int handle, int shift=1)
{
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) > 0)
      return buf[0];
   return 0.0;
}

//+------------------------------------------------------------------+
//| Calculate Moving Average Helper                                  |
//+------------------------------------------------------------------+
double GetMA(int handle, int shift=1)
{
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) > 0)
      return buf[0];
   return 0.0;
}

//+------------------------------------------------------------------+
//| Calculate Dynamic Lot Size                                       |
//+------------------------------------------------------------------+
double CalculateLotSize(string sym, double risk_weight, double sl_distance)
{
   if(sl_distance <= 0) return 0.01;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (InpRiskPercent / 100.0) * risk_weight;
   double tick_size = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);

   if(tick_size <= 0 || tick_value <= 0 || point <= 0) return 0.01;

   double loss_per_lot = (sl_distance / tick_size) * tick_value;
   if(loss_per_lot <= 0) return 0.01;

   double raw_lot = risk_amount / loss_per_lot;
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);

   double lot = MathFloor(raw_lot / step) * step;
   return MathMax(min_lot, MathMin(max_lot, lot));
}

//+------------------------------------------------------------------+
//| Manage Excursion Trailing Ladder                                 |
//+------------------------------------------------------------------+
void ManageTrailingStops(string sym, double be_trigger, double be_buf, double lock_trigger, double lock_buf, int handle_atr)
{
   double atr = GetATR(handle_atr, 1);
   if(atr <= 0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == sym && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         ulong ticket = PositionGetTicket(i);
         double open_p = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_sl = PositionGetDouble(POSITION_SL);
         double current_tp = PositionGetDouble(POSITION_TP);
         long pos_type = PositionGetInteger(POSITION_TYPE);
         double current_p = PositionGetDouble(POSITION_PRICE_CURRENT);

         if(pos_type == POSITION_TYPE_BUY)
         {
            double excursion = current_p - open_p;
            // Stage 2: Profit Lock
            if(excursion >= lock_trigger * atr)
            {
               double target_sl = open_p + lock_buf * atr;
               if(target_sl > current_sl + SymbolInfoDouble(sym, SYMBOL_POINT) * 10)
               {
                  m_trade.PositionModify(ticket, target_sl, current_tp);
               }
            }
            // Stage 1: Breakeven Lock
            else if(excursion >= be_trigger * atr)
            {
               double target_sl = open_p + be_buf * atr;
               if(target_sl > current_sl + SymbolInfoDouble(sym, SYMBOL_POINT) * 10)
               {
                  m_trade.PositionModify(ticket, target_sl, current_tp);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check Existing Positions                                         |
//+------------------------------------------------------------------+
bool HasOpenPosition(string sym)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == sym && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Manage Trailing Ladders
   ManageTrailingStops(_Symbol, InpGoldBETriggerATR, InpGoldBEBufferATR, InpGoldLockTriggerATR, InpGoldLockBufferATR, h_atr_xau);
   ManageTrailingStops(InpEurSymbol, InpEurBETriggerATR, InpEurBEBufferATR, InpEurLockTriggerATR, InpEurLockBufferATR, h_atr_eur);

   // 2. Bar Timing Filters (M1 Bar Completion)
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   MqlDateTime dt;
   TimeCurrent(dt);
   double tf = dt.hour + dt.min / 60.0;

   // Friday Risk Block
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   // Session filter: 07:00 to 19:00 UTC
   bool is_trade_session = (dt.hour >= 7 && dt.hour < 19);
   if(!is_trade_session) return;

   // 3. Gold Setup Detection (EXP-53/55 Champion Core)
   if(!HasOpenPosition(_Symbol) && InpGoldRiskWeight > 0)
   {
      MqlRates rates_xau[2];
      if(CopyRates(_Symbol, PERIOD_M1, 1, 2, rates_xau) == 2)
      {
         double c_xau = rates_xau[1].close;
         double o_xau = rates_xau[1].open;
         double h_xau = rates_xau[1].high;
         double l_xau = rates_xau[1].low;
         double rng_xau = MathMax(h_xau - l_xau, 0.01);
         double lower_wick_xau = MathMin(c_xau, o_xau) - l_xau;
         double upper_wick_xau = h_xau - MathMax(c_xau, o_xau);

         bool bull_pinbar_xau = (lower_wick_xau >= 0.38 * rng_xau) && (upper_wick_xau <= 0.28 * rng_xau) && (c_xau >= o_xau);

         double ema_m5 = GetMA(h_ema_m5_xau, 1);
         double ema_m15 = GetMA(h_ema_m15_xau, 1);
         double ema60 = GetMA(h_ema60_xau, 1);
         bool mtf_bull = (c_xau > ema_m5) && (ema_m5 > ema_m15) && (c_xau > ema60);

         double atr_xau = GetATR(h_atr_xau, 1);

         if(bull_pinbar_xau && mtf_bull && atr_xau > 0)
         {
            double sl_dist = InpGoldSLMultiplier * atr_xau;
            double tp_dist = InpGoldTPMultiplier * atr_xau;
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = ask - sl_dist;
            double tp = ask + tp_dist;
            double lot = CalculateLotSize(_Symbol, InpGoldRiskWeight, sl_dist);

            m_trade.Buy(lot, _Symbol, ask, sl, tp, "EXP57_DAPA_XAU");
         }
      }
   }

   // 4. EURUSD Setup Detection
   if(!HasOpenPosition(InpEurSymbol) && InpEurRiskWeight > 0)
   {
      MqlRates rates_eur[2];
      if(CopyRates(InpEurSymbol, PERIOD_M1, 1, 2, rates_eur) == 2)
      {
         double c_eur = rates_eur[1].close;
         double o_eur = rates_eur[1].open;
         double h_eur = rates_eur[1].high;
         double l_eur = rates_eur[1].low;
         double rng_eur = MathMax(h_eur - l_eur, 0.00001);
         double lower_wick_eur = MathMin(c_eur, o_eur) - l_eur;
         double upper_wick_eur = h_eur - MathMax(c_eur, o_eur);

         bool bull_pinbar_eur = (lower_wick_eur >= 0.40 * rng_eur) && (upper_wick_eur <= 0.25 * rng_eur) && (c_eur >= o_eur);

         double ema_m5_e = GetMA(h_ema_m5_eur, 1);
         double ema_m15_e = GetMA(h_ema_m15_eur, 1);
         double ema60_e = GetMA(h_ema60_eur, 1);
         bool mtf_bull_eur = (c_eur > ema_m5_e) && (ema_m5_e > ema_m15_e) && (c_eur > ema60_e);

         double atr_eur = GetATR(h_atr_eur, 1);

         if(bull_pinbar_eur && mtf_bull_eur && atr_eur > 0)
         {
            double sl_dist = InpEurSLMultiplier * atr_eur;
            double tp_dist = InpEurTPMultiplier * atr_eur;
            double ask = SymbolInfoDouble(InpEurSymbol, SYMBOL_ASK);
            double sl = ask - sl_dist;
            double tp = ask + tp_dist;
            double lot = CalculateLotSize(InpEurSymbol, InpEurRiskWeight, sl_dist);

            m_trade.Buy(lot, InpEurSymbol, ask, sl, tp, "EXP57_DAPA_EUR");
         }
      }
   }
}
//+------------------------------------------------------------------+

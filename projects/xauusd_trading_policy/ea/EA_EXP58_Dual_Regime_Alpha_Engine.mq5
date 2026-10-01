//+------------------------------------------------------------------+
//|                                  EA_EXP58_Dual_Regime_Alpha_Engine.mq5 |
//|                                  Copyright 2026, Quant ML Research Bot   |
//|                                      https://github.com/BlamzKunG/       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant ML Research Engine"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "EXP-58: Multi-Asset Dual-Regime Alpha Engine (MADE-GTAMR)"
#property description "Gold Trend Pinbar Absorption (70%) + EURUSD Asian Sweep Mean-Reversion (30%)"
#property description "Real-Chart Execution with Scale-Invariant Multi-Regime Gating"

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Institutional Risk Management ==="
input ulong    InpMagicNumber         = 580001;       // Magic Number
input double   InpRiskPercent         = 1.0;          // Base Risk per Cycle (%)
input double   InpGoldRiskWeight      = 0.70;         // Gold Allocation Weight (70%)
input double   InpEurRiskWeight       = 0.30;         // EURUSD Allocation Weight (30%)

input group "=== Gold Trend Absorption Parameters ==="
input double   InpGoldSLMultiplier    = 1.8;          // Gold SL ATR Multiplier
input double   InpGoldTPMultiplier    = 3.8;          // Gold TP ATR Multiplier
input double   InpGoldBETriggerATR    = 1.5;          // Gold Breakeven Trigger (x ATR)
input double   InpGoldLockTriggerATR  = 2.8;          // Gold Profit Lock Trigger (x ATR)
input double   InpGoldBEBufferATR     = 0.10;         // Gold BE Buffer (x ATR)
input double   InpGoldLockBufferATR   = 1.20;         // Gold Profit Lock Buffer (x ATR)

input group "=== EURUSD Asian Box Mean-Reversion ==="
input string   InpEurSymbol           = "EURUSD";     // EURUSD Pair Symbol
input double   InpEurSLMultiplier     = 1.2;          // EURUSD SL ATR Multiplier
input double   InpEurTPMultiplier     = 1.8;          // EURUSD TP ATR Multiplier
input double   InpEurBETriggerATR     = 1.0;          // EURUSD Breakeven Trigger (x ATR)
input double   InpEurBEBufferATR      = 0.05;         // EURUSD BE Buffer (x ATR)
input double   InpEurZScoreThreshold  = 1.80;         // Z-Score Mean-Reversion Threshold

input group "=== General Parameters ==="
input int      InpAtrPeriod           = 14;           // ATR Period

//--- Global Objects & Handles
CTrade         m_trade;
int            h_atr_xau;
int            h_atr_eur;
int            h_ema60_xau;
int            h_ema_m5_xau;
int            h_ema_m15_xau;
int            h_ema60_eur;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   h_atr_xau    = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   h_ema60_xau  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m5_xau = iMA(_Symbol, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m15_xau= iMA(_Symbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   h_atr_eur    = iATR(InpEurSymbol, PERIOD_M1, InpAtrPeriod);
   h_ema60_eur  = iMA(InpEurSymbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);

   Print("✅ EA_EXP58_Dual_Regime_Alpha_Engine successfully initialized.");
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

bool HasOpenPosition(string sym)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == sym && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return true;
   }
   return false;
}

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
            if(lock_trigger > 0 && excursion >= lock_trigger * atr)
            {
               double target_sl = open_p + lock_buf * atr;
               if(target_sl > current_sl + SymbolInfoDouble(sym, SYMBOL_POINT) * 10)
                  m_trade.PositionModify(ticket, target_sl, current_tp);
            }
            else if(excursion >= be_trigger * atr)
            {
               double target_sl = open_p + be_buf * atr;
               if(target_sl > current_sl + SymbolInfoDouble(sym, SYMBOL_POINT) * 10)
                  m_trade.PositionModify(ticket, target_sl, current_tp);
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            double excursion = open_p - current_p;
            if(lock_trigger > 0 && excursion >= lock_trigger * atr)
            {
               double target_sl = open_p - lock_buf * atr;
               if(target_sl < current_sl - SymbolInfoDouble(sym, SYMBOL_POINT) * 10 || current_sl == 0)
                  m_trade.PositionModify(ticket, target_sl, current_tp);
            }
            else if(excursion >= be_trigger * atr)
            {
               double target_sl = open_p - be_buf * atr;
               if(target_sl < current_sl - SymbolInfoDouble(sym, SYMBOL_POINT) * 10 || current_sl == 0)
                  m_trade.PositionModify(ticket, target_sl, current_tp);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Asian Session Range (00:00 - 06:00 UTC)                |
//+------------------------------------------------------------------+
bool GetAsianRange(string sym, double &asia_high, double &asia_low)
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime today_start = StringToTime(StringFormat("%04d.%02d.%02d 00:00:00", dt.year, dt.mon, dt.day));
   datetime asia_end    = StringToTime(StringFormat("%04d.%02d.%02d 06:00:00", dt.year, dt.mon, dt.day));

   MqlRates rates[];
   int copied = CopyRates(sym, PERIOD_M1, today_start, asia_end, rates);
   if(copied < 60) return false;

   asia_high = -1e9;
   asia_low  = 1e9;
   for(int i = 0; i < copied; i++)
   {
      if(rates[i].high > asia_high) asia_high = rates[i].high;
      if(rates[i].low < asia_low)   asia_low  = rates[i].low;
   }
   return (asia_high > asia_low);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Manage Trailing Ladders
   ManageTrailingStops(_Symbol, InpGoldBETriggerATR, InpGoldBEBufferATR, InpGoldLockTriggerATR, InpGoldLockBufferATR, h_atr_xau);
   ManageTrailingStops(InpEurSymbol, InpEurBETriggerATR, InpEurBEBufferATR, 0.0, 0.0, h_atr_eur);

   // 2. Bar Timing (M1 completion)
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   MqlDateTime dt;
   TimeCurrent(dt);
   double tf = dt.hour + dt.min / 60.0;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   // 3. Gold Setup (Sovereign Trend Absorption)
   if(!HasOpenPosition(_Symbol) && InpGoldRiskWeight > 0 && dt.hour >= 7 && dt.hour < 19)
   {
      MqlRates rates_xau[2];
      if(CopyRates(_Symbol, PERIOD_M1, 1, 2, rates_xau) == 2)
      {
         double c_xau = rates_xau[1].close;
         double o_xau = rates_xau[1].open;
         double h_xau = rates_xau[1].high;
         double l_xau = rates_xau[1].low;
         double rng_xau = MathMax(h_xau - l_xau, 0.01);
         double lower_wick = MathMin(c_xau, o_xau) - l_xau;
         double upper_wick = h_xau - MathMax(c_xau, o_xau);

         bool bull_pinbar = (lower_wick >= 0.38 * rng_xau) && (upper_wick <= 0.28 * rng_xau) && (c_xau >= o_xau);
         double ema_m5 = GetMA(h_ema_m5_xau, 1);
         double ema_m15 = GetMA(h_ema_m15_xau, 1);
         double ema60 = GetMA(h_ema60_xau, 1);
         bool mtf_bull = (c_xau > ema_m5) && (ema_m5 > ema_m15) && (c_xau > ema60);
         double atr_xau = GetATR(h_atr_xau, 1);

         if(bull_pinbar && mtf_bull && atr_xau > 0)
         {
            double sl_dist = InpGoldSLMultiplier * atr_xau;
            double tp_dist = InpGoldTPMultiplier * atr_xau;
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = ask - sl_dist;
            double tp = ask + tp_dist;
            double lot = CalculateLotSize(_Symbol, InpGoldRiskWeight, sl_dist);

            m_trade.Buy(lot, _Symbol, ask, sl, tp, "EXP58_MADE_XAU");
         }
      }
   }

   // 4. EURUSD Setup (Asian Sweep Mean-Reversion: 07:00 - 14:00 UTC)
   if(!HasOpenPosition(InpEurSymbol) && InpEurRiskWeight > 0 && tf >= 7.0 && tf <= 14.0)
   {
      double asia_h, asia_l;
      if(GetAsianRange(InpEurSymbol, asia_h, asia_l))
      {
         MqlRates rates_eur[2];
         if(CopyRates(InpEurSymbol, PERIOD_M1, 1, 2, rates_eur) == 2)
         {
            double c_eur = rates_eur[1].close;
            double o_eur = rates_eur[1].open;
            double h_eur = rates_eur[1].high;
            double l_eur = rates_eur[1].low;
            double rng_eur = MathMax(h_eur - l_eur, 0.00001);
            double lower_wick = MathMin(c_eur, o_eur) - l_eur;
            double upper_wick = h_eur - MathMax(c_eur, o_eur);
            double atr_eur = GetATR(h_atr_eur, 1);

            // Long Mean-Reversion: Sweep below Asian Low
            if(l_eur <= asia_l - 0.20 * atr_eur && c_eur >= asia_l - 0.50 * atr_eur && lower_wick >= 0.35 * rng_eur && c_eur >= o_eur && atr_eur > 0)
            {
               double sl_dist = InpEurSLMultiplier * atr_eur;
               double tp_dist = InpEurTPMultiplier * atr_eur;
               double ask = SymbolInfoDouble(InpEurSymbol, SYMBOL_ASK);
               double sl = ask - sl_dist;
               double tp = ask + tp_dist;
               double lot = CalculateLotSize(InpEurSymbol, InpEurRiskWeight, sl_dist);

               m_trade.Buy(lot, InpEurSymbol, ask, sl, tp, "EXP58_MADE_EUR_BUY");
            }
            // Short Mean-Reversion: Sweep above Asian High
            else if(h_eur >= asia_h + 0.20 * atr_eur && c_eur <= asia_h + 0.50 * atr_eur && upper_wick >= 0.35 * rng_eur && c_eur <= o_eur && atr_eur > 0)
            {
               double sl_dist = InpEurSLMultiplier * atr_eur;
               double tp_dist = InpEurTPMultiplier * atr_eur;
               double bid = SymbolInfoDouble(InpEurSymbol, SYMBOL_BID);
               double sl = bid + sl_dist;
               double tp = bid - tp_dist;
               double lot = CalculateLotSize(InpEurSymbol, InpEurRiskWeight, sl_dist);

               m_trade.Sell(lot, InpEurSymbol, bid, sl, tp, "EXP58_MADE_EUR_SELL");
            }
         }
      }
   }
}
//+------------------------------------------------------------------+

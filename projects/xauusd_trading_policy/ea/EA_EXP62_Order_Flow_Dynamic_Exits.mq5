//+------------------------------------------------------------------+
//|                      EA_EXP62_Order_Flow_Dynamic_Exits.mq5       |
//|                                  Copyright 2026, Quant ML Research Bot   |
//|                                      https://github.com/BlamzKunG/       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant ML Research Engine"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "EXP-62: Dynamic Microstructure Order Flow Exits & Volatility Trailing Cones (MOFE-VATC)"
#property description "Order Flow In-Position Management: Early Liquidation on Counter-Absorption + 3-Tier Trailing Cones"
#property description "Real-Chart Execution with Exact 1:1 Research Logic Parity"

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Institutional Risk Management ==="
input ulong    InpMagicNumber         = 620001;       // Magic Number
input double   InpRiskPercent         = 1.5;          // Risk per Trade (%)
input double   InpGoldSLMultiplier    = 1.8;          // Gold SL ATR Multiplier
input double   InpGoldTPMultiplier    = 5.0;          // Gold Initial TP Multiplier (Runner Ceiling)
input double   InpGoldBETriggerATR    = 1.0;          // Tier 1 Fast BE Trigger (x ATR)
input double   InpGoldBEBufferATR     = 0.15;         // Tier 1 BE Buffer (x ATR)
input double   InpGoldLockTriggerATR  = 2.0;          // Tier 2 Lock Trigger (x ATR)
input double   InpGoldLockBufferATR   = 1.00;         // Tier 2 Lock Buffer (x ATR)
input double   InpGoldRunnerTriggerATR= 3.0;          // Tier 3 Runner Trigger (x ATR)
input double   InpGoldRunnerBufferATR = 2.00;         // Tier 3 Runner Buffer (x ATR)

input group "=== Microstructure Order Flow Exits (MOFE) ==="
input bool     InpEnableMofeExits     = true;         // Enable Order Flow Exhaustion Exits
input double   InpMofeProfitThreshold = 1.2;          // Min Profit before MOFE Activation (x ATR)

input group "=== Cross-Asset Information Transmission ==="
input string   InpEurSymbol           = "EURUSD";     // EURUSD Leading Symbol
input double   InpEurImpulseThreshold = 0.15;         // EURUSD Z-Score Lead Threshold
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

   Print("✅ EA_EXP62_Order_Flow_Dynamic_Exits successfully initialized.");
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
//| Manage 3-Tier Trailing Cones                                     |
//+------------------------------------------------------------------+
void Manage3TierTrailingCones(string sym, ulong magic, double atr)
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
         // Tier 1: Fast BE
         if(profit_dist >= InpGoldBETriggerATR * atr && current_sl < open_price)
         {
            double new_sl = open_price + InpGoldBEBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
         // Tier 2: Conservative Lock
         if(profit_dist >= InpGoldLockTriggerATR * atr && current_sl < (open_price + InpGoldLockBufferATR * atr))
         {
            double new_sl = open_price + InpGoldLockBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
         // Tier 3: Runner Trail
         if(profit_dist >= InpGoldRunnerTriggerATR * atr && current_sl < (open_price + InpGoldRunnerBufferATR * atr))
         {
            double new_sl = open_price + InpGoldRunnerBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         // Tier 1: Fast BE
         if(profit_dist >= InpGoldBETriggerATR * atr && (current_sl > open_price || current_sl == 0))
         {
            double new_sl = open_price - InpGoldBEBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
         // Tier 2: Conservative Lock
         if(profit_dist >= InpGoldLockTriggerATR * atr && current_sl > (open_price - InpGoldLockBufferATR * atr))
         {
            double new_sl = open_price - InpGoldLockBufferATR * atr;
            m_trade.PositionModify(ticket, new_sl, current_tp);
         }
         // Tier 3: Runner Trail
         if(profit_dist >= InpGoldRunnerTriggerATR * atr && current_sl > (open_price - InpGoldRunnerBufferATR * atr))
         {
            double new_sl = open_price - InpGoldRunnerBufferATR * atr;
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

   // Manage 3-Tier trailing cones every tick
   Manage3TierTrailingCones(_Symbol, InpMagicNumber, atr_xau);

   // New Bar Evaluation
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // Avoid Friday rollover risk
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   // Read Market State Data
   MqlRates rates_xau[65];
   if(CopyRates(_Symbol, PERIOD_M1, 1, 65, rates_xau) < 65) return;

   MqlRates rates_eur[10];
   if(CopyRates(InpEurSymbol, PERIOD_M1, 1, 10, rates_eur) < 10) return;

   double c_xau = rates_xau[0].close;
   double o_xau = rates_xau[0].open;
   double h_xau = rates_xau[0].high;
   double l_xau = rates_xau[0].low;

   double rng_xau = MathMax(h_xau - l_xau, 0.01);
   double upper_wick = h_xau - MathMax(c_xau, o_xau);
   double lower_wick = MathMin(c_xau, o_xau) - l_xau;

   // --- CHECK MOFE EXITS ON ACTIVE POSITIONS ---
   if(InpEnableMofeExits && PositionsTotal() > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket <= 0) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

         double open_p = PositionGetDouble(POSITION_PRICE_OPEN);
         ENUM_POSITION_TYPE ptype = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

         if(ptype == POSITION_TYPE_BUY)
         {
            double profit_atr = (c_xau - open_p) / atr_xau;
            // Counter-rejection: Aggressive shooting star
            bool counter_star = (upper_wick >= 0.35 * rng_xau) && (c_xau <= o_xau);
            if(profit_atr >= InpMofeProfitThreshold && counter_star)
            {
               m_trade.PositionClose(ticket);
               PrintFormat("⚡ [MOFE EXIT BUY] Ticket: %d | Closed at: %.2f | Profit ATR: %.2f", ticket, c_xau, profit_atr);
               return;
            }
         }
         else if(ptype == POSITION_TYPE_SELL)
         {
            double profit_atr = (open_p - c_xau) / atr_xau;
            // Counter-rejection: Aggressive hammer
            bool counter_hammer = (lower_wick >= 0.35 * rng_xau) && (c_xau >= o_xau);
            if(profit_atr >= InpMofeProfitThreshold && counter_hammer)
            {
               m_trade.PositionClose(ticket);
               PrintFormat("⚡ [MOFE EXIT SELL] Ticket: %d | Closed at: %.2f | Profit ATR: %.2f", ticket, c_xau, profit_atr);
               return;
            }
         }
      }
   }

   // Ensure single position for new entries
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

   double ema20 = GetMA(h_ema20_xau, 1);
   double ema60 = GetMA(h_ema60_xau, 1);
   double ema_m5 = GetMA(h_ema_m5_xau, 1);
   double ema_m15 = GetMA(h_ema_m15_xau, 1);

   bool mtf_bull = (c_xau > ema60) && (ema20 > ema60) && (c_xau > ema_m5) && (ema_m5 > ema_m15);
   bool mtf_bear = (c_xau < ema60) && (ema20 < ema60) && (c_xau < ema_m5) && (ema_m5 < ema_m15);

   double eur_ret3 = (rates_eur[0].close - rates_eur[2].open) / MathMax(rates_eur[2].open, 0.0001);
   bool eur_lead_bull = (eur_ret3 >= InpEurImpulseThreshold * 0.0001);
   bool eur_lead_bear = (eur_ret3 <= -InpEurImpulseThreshold * 0.0001);

   bool trigger_long = false;
   bool trigger_short = false;
   string sleeve_used = "";

   // --- LONG SIGNALS
   if(mtf_bull)
   {
      bool pinbar_1b = (lower_wick >= 0.38 * rng_xau) && (upper_wick <= 0.28 * rng_xau) && (c_xau >= o_xau);
      if(pinbar_1b && eur_lead_bull)
      {
         trigger_long = true;
         sleeve_used = "Long_Pinbar_1B";
      }

      if(!trigger_long)
      {
         double comp2_low = MathMin(rates_xau[0].low, rates_xau[1].low);
         double comp2_high = MathMax(rates_xau[0].high, rates_xau[1].high);
         double comp2_rng = MathMax(comp2_high - comp2_low, 0.01);
         double comp2_lwick = MathMin(c_xau, rates_xau[1].open) - comp2_low;
         double comp2_uwick = comp2_high - MathMax(c_xau, rates_xau[1].open);
         bool comp2_hammer = (comp2_lwick >= 0.38 * comp2_rng) && (comp2_uwick <= 0.30 * comp2_rng) && (c_xau >= rates_xau[1].open);

         if(comp2_hammer && eur_lead_bull)
         {
            trigger_long = true;
            sleeve_used = "Long_Composite_Hammer";
         }
      }
   }

   // --- SHORT SIGNALS
   if(mtf_bear && !trigger_long)
   {
      bool star_1b = (upper_wick >= 0.38 * rng_xau) && (lower_wick <= 0.28 * rng_xau) && (c_xau <= o_xau);
      if(star_1b && eur_lead_bear)
      {
         trigger_short = true;
         sleeve_used = "Short_Shooting_Star_1B";
      }

      if(!trigger_short)
      {
         double comp2_low = MathMin(rates_xau[0].low, rates_xau[1].low);
         double comp2_high = MathMax(rates_xau[0].high, rates_xau[1].high);
         double comp2_rng = MathMax(comp2_high - comp2_low, 0.01);
         double comp2_lwick = MathMin(c_xau, rates_xau[1].open) - comp2_low;
         double comp2_uwick = comp2_high - MathMax(c_xau, rates_xau[1].open);
         bool comp2_star = (comp2_uwick >= 0.38 * comp2_rng) && (comp2_lwick <= 0.30 * comp2_rng) && (c_xau <= rates_xau[1].open);

         if(comp2_star && eur_lead_bear)
         {
            trigger_short = true;
            sleeve_used = "Short_Composite_Star";
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

      if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "EXP62_" + sleeve_used))
      {
         PrintFormat("🎯 [EXP-62 BUY] Sleeve: %s | Ask: %.2f | SL: %.2f | TP: %.2f | Lot: %.2f",
                     sleeve_used, ask, sl, tp, lot);
      }
   }
   else if(trigger_short)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl_dist = InpGoldSLMultiplier * atr_xau;
      double sl = bid + sl_dist;
      double tp = bid - (InpGoldTPMultiplier * atr_xau);
      double lot = CalculateLotSize(_Symbol, sl_dist);

      if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "EXP62_" + sleeve_used))
      {
         PrintFormat("🎯 [EXP-62 SELL] Sleeve: %s | Bid: %.2f | SL: %.2f | TP: %.2f | Lot: %.2f",
                     sleeve_used, bid, sl, tp, lot);
      }
   }
}
//+------------------------------------------------------------------+

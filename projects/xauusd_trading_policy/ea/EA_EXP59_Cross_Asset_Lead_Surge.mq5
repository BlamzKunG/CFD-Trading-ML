//+------------------------------------------------------------------+
//|                                EA_EXP59_Cross_Asset_Lead_Surge.mq5 |
//|                                  Copyright 2026, Quant ML Research Bot   |
//|                                      https://github.com/BlamzKunG/       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant ML Research Engine"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "EXP-59: Cross-Asset Lead Transmission & Microstructure Surge Engine (CALT-MSE)"
#property description "Tri-Sleeve Alpha Architecture: Sovereign Fortress + Cross-Asset Momentum + Volatility Compression"
#property description "Real-Chart Execution with 2-Stage Asymmetric ATR Trailing Ladder"

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Institutional Risk Management ==="
input ulong    InpMagicNumber         = 590001;       // Magic Number
input double   InpRiskPercent         = 1.0;          // Base Risk per Trade (%)
input double   InpGoldSLMultiplier    = 1.8;          // Gold SL ATR Multiplier
input double   InpGoldTPMultiplier    = 3.8;          // Gold TP ATR Multiplier
input double   InpGoldBETriggerATR    = 1.5;          // Gold Breakeven Trigger (x ATR)
input double   InpGoldLockTriggerATR  = 2.8;          // Gold Profit Lock Trigger (x ATR)
input double   InpGoldBEBufferATR     = 0.10;         // Gold BE Buffer (x ATR)
input double   InpGoldLockBufferATR   = 1.20;         // Gold Profit Lock Buffer (x ATR)

input group "=== Cross-Asset Information Transmission ==="
input string   InpEurSymbol           = "EURUSD";     // EURUSD Leading Symbol
input double   InpEurImpulseThreshold = 1.40;         // EURUSD Z-Score Velocity Threshold

input group "=== Multi-Sleeve Configuration ==="
input bool     InpEnableSleeveA       = true;         // Enable Sleeve A (Sovereign Pinbar Fortress)
input bool     InpEnableSleeveB       = true;         // Enable Sleeve B (Cross-Asset Momentum Surge)
input bool     InpEnableSleeveC       = true;         // Enable Sleeve C (Volatility Compression Breakout)
input int      InpAtrPeriod           = 14;           // ATR Period

//--- Global Objects & Handles
CTrade         m_trade;
int            h_atr_xau;
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
   h_ema60_xau  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m5_xau = iMA(_Symbol, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_m15_xau= iMA(_Symbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   h_atr_eur    = iATR(InpEurSymbol, PERIOD_M1, InpAtrPeriod);

   Print("✅ EA_EXP59_Cross_Asset_Lead_Surge successfully initialized.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr_xau);
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
            if(excursion >= lock_trigger * atr)
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
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate EURUSD Lead Impulse (3-bar Return Z-Score)             |
//+------------------------------------------------------------------+
double GetEurImpulseZ()
{
   MqlRates rates[35];
   if(CopyRates(InpEurSymbol, PERIOD_M1, 1, 35, rates) < 35) return 0.0;

   double c_now = rates[34].close;
   double c_3   = rates[31].close;
   double ret3  = (c_3 > 0) ? (c_now - c_3) / c_3 : 0.0;

   // Compute 30-bar rolling standard deviation of 3-bar returns
   double sum = 0.0;
   double sum_sq = 0.0;
   int n = 0;
   for(int i = 3; i < 34; i++)
   {
      double r = (rates[i-3].close > 0) ? (rates[i].close - rates[i-3].close) / rates[i-3].close : 0.0;
      sum += r;
      sum_sq += r * r;
      n++;
   }
   if(n < 10) return 0.0;
   double mean = sum / n;
   double variance = (sum_sq / n) - (mean * mean);
   double std_dev = MathSqrt(MathMax(variance, 1e-12));

   return (ret3 - mean) / std_dev;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Manage Trailing Ladders
   ManageTrailingStops(_Symbol, InpGoldBETriggerATR, InpGoldBEBufferATR, InpGoldLockTriggerATR, InpGoldLockBufferATR, h_atr_xau);

   // 2. Bar Timing (M1 completion)
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   MqlDateTime dt;
   TimeCurrent(dt);
   double tf = dt.hour + dt.min / 60.0;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   // Session filter: 07:00 to 19:00 UTC
   if(dt.hour < 7 || dt.hour >= 19) return;

   if(HasOpenPosition(_Symbol)) return;

   MqlRates rates_xau[25];
   if(CopyRates(_Symbol, PERIOD_M1, 1, 25, rates_xau) < 25) return;

   double c_xau = rates_xau[24].close;
   double o_xau = rates_xau[24].open;
   double h_xau = rates_xau[24].high;
   double l_xau = rates_xau[24].low;
   double rng_xau = MathMax(h_xau - l_xau, 0.01);
   double lower_wick = MathMin(c_xau, o_xau) - l_xau;
   double upper_wick = h_xau - MathMax(c_xau, o_xau);

   double ema_m5 = GetMA(h_ema_m5_xau, 1);
   double ema_m15 = GetMA(h_ema_m15_xau, 1);
   double ema60 = GetMA(h_ema60_xau, 1);
   bool mtf_bull = (c_xau > ema_m5) && (ema_m5 > ema_m15) && (c_xau > ema60);
   double atr_xau = GetATR(h_atr_xau, 1);
   if(atr_xau <= 0) return;

   double vol_xau = (double)rates_xau[24].tick_volume;
   double vol_sum = 0.0;
   for(int i = 5; i < 25; i++) vol_sum += (double)rates_xau[i].tick_volume;
   double vol_ma20 = vol_sum / 20.0;
   double rel_vol = vol_xau / MathMax(vol_ma20, 1.0);
   double norm_body = MathAbs(c_xau - o_xau) / atr_xau;
   double vfs = rel_vol * norm_body;

   double vdp = vol_xau * ((c_xau - l_xau) - (h_xau - c_xau)) / rng_xau;

   bool signal_long = false;
   string signal_sleeve = "";

   // Sleeve A: Sovereign Pinbar Fortress
   if(InpEnableSleeveA && !signal_long)
   {
      bool bull_pinbar = (lower_wick >= 0.38 * rng_xau) && (upper_wick <= 0.28 * rng_xau) && (c_xau >= o_xau);
      if(bull_pinbar && mtf_bull && vfs >= 1.10)
      {
         signal_long = true;
         signal_sleeve = "SleeveA_Pinbar";
      }
   }

   // Sleeve B: Cross-Asset Momentum Surge (EURUSD Lead)
   if(InpEnableSleeveB && !signal_long)
   {
      double eur_z = GetEurImpulseZ();
      if(mtf_bull && (c_xau > ema60) && (eur_z >= InpEurImpulseThreshold) && (vfs >= 1.10) && (vdp > 0))
      {
         signal_long = true;
         signal_sleeve = "SleeveB_EurSurge";
      }
   }

   // Sleeve C: Volatility Compression Breakout
   if(InpEnableSleeveC && !signal_long)
   {
      double atr_sum = 0.0;
      for(int i = 1; i <= 20; i++) atr_sum += GetATR(h_atr_xau, i);
      double atr_ma20 = atr_sum / 20.0;
      bool vol_compressed = (atr_xau <= 0.85 * atr_ma20);
      bool vol_expansion  = (rng_xau >= 1.20 * atr_xau) && (vfs >= 1.15) && (vdp > 0);

      if(mtf_bull && (c_xau > ema60) && vol_compressed && vol_expansion)
      {
         signal_long = true;
         signal_sleeve = "SleeveC_VolBreakout";
      }
   }

   // Execution
   if(signal_long)
   {
      double sl_dist = InpGoldSLMultiplier * atr_xau;
      double tp_dist = InpGoldTPMultiplier * atr_xau;
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - sl_dist;
      double tp = ask + tp_dist;
      double lot = CalculateLotSize(_Symbol, sl_dist);

      m_trade.Buy(lot, _Symbol, ask, sl, tp, "EXP59_" + signal_sleeve);
   }
}
//+------------------------------------------------------------------+

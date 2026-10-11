//+------------------------------------------------------------------+
//|                   Gold_H1_Ulcer_Index_Master_EA.mq5              |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 93: Gold H1 Peter Martin's Ulcer Index                |
//|   Downside Volatility Compression & Exhaustion (UI-VCD-KFD)      |
//|     Magic: 930001 | Timeframe: H1 | Symbol: XAUUSD               |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Peter Martin Ulcer Index Master EA (Magic 930001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_UI_TRIGGER
{
   UI_SMOOTH_THRUST,         // Smooth Velocity Impulse: UI compresses below threshold
   UI_EXHAUSTION_TURN,       // Retracement Exhaustion: UI spikes high and hooks downward
   UI_COMPRESSION_BREAKOUT   // Volatility Expansion: UI breaks out from extreme low
};

enum ENUM_TREND_FILTER
{
   TREND_EMA200,    // Macro Structural Trend: Price > EMA200
   TREND_EMA50,     // Intermediate Structural Trend: Price > EMA50
   TREND_NONE       // No Macro Filter
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 930001;               // EA Magic Number
input double                InpLotSize             = 0.10;                 // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;                 // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;                // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;                // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;                // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;                 // Defensive Lot Multiplier (0.25x)

input group "=== Peter Martin Ulcer Index Configuration ==="
input int                   InpUiPeriod            = 20;                   // UI Lookback Period (Default: 20)
input ENUM_UI_TRIGGER       InpTriggerMode         = UI_SMOOTH_THRUST;     // Entry Trigger Mechanism
input double                InpTriggerThreshold    = 0.50;                 // UI Compression Threshold (0.50%)
input double                InpTpMult              = 5.0;                  // Take Profit ATR Multiplier (5.0R)
input double                InpSlMult              = 2.5;                  // Stop Loss ATR Multiplier (2.5R)

input group "=== Structural Trend & Anti-Chaos Filters ==="
input int                   InpAtrPeriod           = 14;                   // ATR Volatility Period
input ENUM_TREND_FILTER     InpTrendFilter         = TREND_EMA200;         // Structural Trend Gate
input int                   InpTrendEmaPeriod      = 200;                  // Trend EMA Period (50 or 200)
input bool                  InpUseKfdFilter        = true;                 // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.40;                 // Maximum Fractal Dimension (<= 1.40)
input int                   InpKfdPeriod           = 24;                   // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hTrendEMA;
datetime       m_last_bar_time;
int            m_current_month;
double         m_monthly_realized_pnl;
bool           m_is_month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();

   m_hATR = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   if(m_hATR == INVALID_HANDLE)
   {
      Print("[!] Error initializing ATR handle.");
      return(INIT_FAILED);
   }

   if(InpTrendFilter != TREND_NONE)
   {
      int ema_p = (InpTrendFilter == TREND_EMA200) ? 200 : InpTrendEmaPeriod;
      m_hTrendEMA = iMA(_Symbol, PERIOD_H1, ema_p, 0, MODE_EMA, PRICE_CLOSE);
      if(m_hTrendEMA == INVALID_HANDLE)
      {
         Print("[!] Error initializing Trend EMA handle.");
         return(INIT_FAILED);
      }
   }
   else
   {
      m_hTrendEMA = INVALID_HANDLE;
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   PrintFormat("[+] Strategy 93 Initialized: UI(%d), Trigger=%s, Thresh=%.2f, TP=%.1fR, SL=%.1fR, Magic=%d",
               InpUiPeriod, EnumToString(InpTriggerMode), InpTriggerThreshold, InpTpMult, InpSlMult, InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hTrendEMA != INVALID_HANDLE) IndicatorRelease(m_hTrendEMA);
}

//+------------------------------------------------------------------+
//| Katz Fractal Dimension Calculation                               |
//+------------------------------------------------------------------+
double CalculateKFD(int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, period + 1, rates);
   if(copied < period) return 1.5;

   double c_first = rates[period - 1].close;
   double c_last  = rates[0].close;
   double euclid_d = MathAbs(c_last - c_first);

   double total_len = 0.0;
   for(int i = 0; i < period - 1; i++)
   {
      total_len += MathAbs(rates[i].close - rates[i + 1].close);
   }

   if(total_len <= 1e-6 || euclid_d <= 1e-6) return 1.5;

   double val = MathLog10((double)period) / (MathLog10((double)period) + MathLog10(euclid_d / total_len));
   if(val < 1.0) val = 1.0;
   if(val > 2.0) val = 2.0;
   return val;
}

//+------------------------------------------------------------------+
//| Peter Martin's Ulcer Index Calculation                           |
//| Computes ui_long and ui_short at specified shift bar             |
//+------------------------------------------------------------------+
bool CalculateUlcerIndex(int period, int shift, double &ui_long, double &ui_short)
{
   int req_bars = period * 2 + 5;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, shift, req_bars, rates);
   if(copied < period + 1) return false;

   // For each bar j from 0 to period-1:
   // R_long[j] = 100.0 * (Close[j] - MaxHigh[j..j+period-1]) / MaxHigh
   // R_short[j] = 100.0 * (Close[j] - MinLow[j..j+period-1]) / MinLow
   double sum_sq_long = 0.0;
   double sum_sq_short = 0.0;

   for(int j = 0; j < period; j++)
   {
      double max_h = rates[j].high;
      double min_l = rates[j].low;
      for(int k = 1; k < period; k++)
      {
         if(rates[j + k].high > max_h) max_h = rates[j + k].high;
         if(rates[j + k].low < min_l) min_l = rates[j + k].low;
      }

      double r_l = 100.0 * (rates[j].close - max_h) / (max_h + 1e-6);
      double r_s = 100.0 * (rates[j].close - min_l) / (min_l + 1e-6);

      sum_sq_long  += (r_l * r_l);
      sum_sq_short += (r_s * r_s);
   }

   ui_long  = MathSqrt(sum_sq_long / (double)period);
   ui_short = MathSqrt(sum_sq_short / (double)period);
   return true;
}

//+------------------------------------------------------------------+
//| ASAR Monthly PnL Auditor                                         |
//+------------------------------------------------------------------+
void UpdateMonthlyPnL()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int month_key = dt.year * 100 + dt.mon;

   if(month_key != m_current_month)
   {
      m_current_month = month_key;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked = false;
      PrintFormat("[*] S93: New Calendar Month %d. ASAR Risk Engine Reset.", month_key);
   }

   datetime start_of_month = D'2020.01.01';
   MqlDateTime m_start = dt;
   m_start.day = 1;
   m_start.hour = 0;
   m_start.min = 0;
   m_start.sec = 0;
   start_of_month = StructToTime(m_start);

   if(!HistorySelect(start_of_month, TimeCurrent())) return;

   double net_pnl = 0.0;
   int total_deals = HistoryDealsTotal();
   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            net_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            net_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            net_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }

   m_monthly_realized_pnl = net_pnl;

   if(InpMonthlyProfitLock > 0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      if(!m_is_month_locked)
      {
         m_is_month_locked = true;
         PrintFormat("[LOCK] S93 Monthly Profit Lock Active: Net PnL = $%.2f >= $%.2f",
                     m_monthly_realized_pnl, InpMonthlyProfitLock);
      }
   }

   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
      {
         m_is_month_locked = true;
         PrintFormat("[BREAKER] S93 Circuit Breaker Tripped: Net PnL = $%.2f <= -$%.2f",
                     m_monthly_realized_pnl, InpHardLossBreaker);
      }
   }
}

//+------------------------------------------------------------------+
//| Check Position Status                                            |
//+------------------------------------------------------------------+
bool HasOpenPosition(int &pos_type, ulong &pos_ticket)
{
   pos_type = 0;
   pos_ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            pos_ticket = ticket;
            pos_type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
            return true;
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check bar time for Bar-Close confirmation
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == m_last_bar_time) return; // Only execute on new H1 bar open

   UpdateMonthlyPnL();

   int pos_type = 0;
   ulong pos_ticket = 0;
   bool in_position = HasOpenPosition(pos_type, pos_ticket);

   // Bar index 1 is confirmed closed bar
   m_last_bar_time = current_bar_time;

   if(in_position || m_is_month_locked) return;

   // Check Spread
   double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   if(spread > InpMaxSpread) return;

   // Copy ATR
   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0) return;
   double c_atr = atr_buf[0];
   if(c_atr < 0.5) return;

   // Macro Structural Trend
   bool trend_up = true;
   bool trend_dn = true;
   if(InpTrendFilter != TREND_NONE)
   {
      double ema_buf[];
      ArraySetAsSeries(ema_buf, true);
      if(CopyBuffer(m_hTrendEMA, 0, 1, 1, ema_buf) <= 0) return;
      double close1 = iClose(_Symbol, PERIOD_H1, 1);
      trend_up = (close1 > ema_buf[0]);
      trend_dn = (close1 < ema_buf[0]);
   }

   // Katz Fractal Dimension Gate
   if(InpUseKfdFilter)
   {
      double kfd = CalculateKFD(InpKfdPeriod);
      if(kfd > InpKfdThreshold) return; // Anti-chaos filter triggered
   }

   // Calculate Ulcer Index for Bar 1 and Bar 2
   double uil_1 = 0.0, uis_1 = 0.0;
   double uil_2 = 0.0, uis_2 = 0.0;
   if(!CalculateUlcerIndex(InpUiPeriod, 1, uil_1, uis_1)) return;
   if(!CalculateUlcerIndex(InpUiPeriod, 2, uil_2, uis_2)) return;

   bool buy_signal = false;
   bool sell_signal = false;

   if(InpTriggerMode == UI_SMOOTH_THRUST)
   {
      // Compression threshold crossed downwards -> smooth trend velocity
      if(uil_2 >= InpTriggerThreshold && uil_1 < InpTriggerThreshold && trend_up)
         buy_signal = true;
      else if(uis_2 >= InpTriggerThreshold && uis_1 < InpTriggerThreshold && trend_dn)
         sell_signal = true;
   }
   else if(InpTriggerMode == UI_EXHAUSTION_TURN)
   {
      // Elevated retracement hooks down -> correction exhausted back into trend
      if(uil_2 >= InpTriggerThreshold * 1.5 && uil_1 < uil_2 && trend_up)
         buy_signal = true;
      else if(uis_2 >= InpTriggerThreshold * 1.5 && uis_1 < uis_2 && trend_dn)
         sell_signal = true;
   }
   else if(InpTriggerMode == UI_COMPRESSION_BREAKOUT)
   {
      // Compression expands outward
      if(uil_2 < InpTriggerThreshold && uil_1 >= InpTriggerThreshold && trend_up)
         buy_signal = true;
      else if(uis_2 < InpTriggerThreshold && uis_1 >= InpTriggerThreshold && trend_dn)
         sell_signal = true;
   }

   // Defensive Sizing
   double lots = InpLotSize;
   if(InpDefensiveThresh > 0 && m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      lots = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(lots < 0.01) lots = 0.01;
   }

   // Execute Entry
   if(buy_signal)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - (InpSlMult * c_atr), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * c_atr), _Digits);
      m_trade.Buy(lots, _Symbol, ask, sl, tp, "S93 UI BUY");
      PrintFormat("[ENTRY] S93 BUY: %.2f lots @ %.2f | SL: %.2f | TP: %.2f | UI_L: %.2f (prev %.2f)",
                  lots, ask, sl, tp, uil_1, uil_2);
   }
   else if(sell_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + (InpSlMult * c_atr), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * c_atr), _Digits);
      m_trade.Sell(lots, _Symbol, bid, sl, tp, "S93 UI SELL");
      PrintFormat("[ENTRY] S93 SELL: %.2f lots @ %.2f | SL: %.2f | TP: %.2f | UI_S: %.2f (prev %.2f)",
                  lots, bid, sl, tp, uis_1, uis_2);
   }
}
//+------------------------------------------------------------------+

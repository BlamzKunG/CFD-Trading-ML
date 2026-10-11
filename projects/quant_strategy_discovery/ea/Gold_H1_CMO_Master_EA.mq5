//+------------------------------------------------------------------+
//|                   Gold_H1_CMO_Master_EA.mq5                      |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 91: Gold H1 Tushar Chande's Momentum Oscillator       |
//|   Pure Unsmoothed Price Change Momentum Thrust (CMO-MPE-KFD)     |
//|     Magic: 910001 | Timeframe: H1 | Symbol: XAUUSD               |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Tushar Chande Momentum Oscillator Master EA (Magic 910001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_CMO_TRIGGER
{
   CMO_THRUST_EXPANSION,    // Thrust Breakout: CMO crosses above +thresh / below -thresh
   CMO_ZERO_CROSS,          // Centerline Cross: CMO crosses 0.0 in trend direction
   CMO_EXTREME_REVERSION,   // Mean Reversion: CMO dips below -thresh and crosses back up
   CMO_SIGNAL_CROSS         // Signal Cross: CMO crosses its EMA signal line
};

enum ENUM_TREND_FILTER
{
   TREND_EMA50,     // Fast Structural Trend: Price > EMA50
   TREND_EMA200,    // Macro Structural Trend: Price > EMA200
   TREND_NONE       // No Macro Filter
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 910001;               // EA Magic Number
input double                InpLotSize             = 0.10;                 // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;                 // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;                // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;                // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;                // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;                 // Defensive Lot Multiplier (0.25x)

input group "=== Tushar Chande Momentum Oscillator Configuration ==="
input int                   InpCmoPeriod           = 20;                   // CMO Lookback Period (Default: 20)
input ENUM_CMO_TRIGGER      InpTriggerMode         = CMO_THRUST_EXPANSION; // Entry Trigger Mechanism
input double                InpTriggerThreshold    = 40.0;                 // CMO Threshold (+40 / -40)
input int                   InpSignalPeriod        = 9;                    // Signal EMA Period
input double                InpTpMult              = 6.0;                  // Take Profit ATR Multiplier (6.0R)
input double                InpSlMult              = 2.0;                  // Stop Loss ATR Multiplier (2.0R)

input group "=== Structural Trend & Anti-Chaos Filters ==="
input int                   InpAtrPeriod           = 14;                   // ATR Volatility Period
input ENUM_TREND_FILTER     InpTrendFilter         = TREND_EMA50;          // Structural Trend Gate
input int                   InpTrendEmaPeriod      = 50;                   // Trend EMA Period (50 or 200)
input bool                  InpUseKfdFilter        = false;                // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.35;                 // Maximum Fractal Dimension (<= 1.35)
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

   Print("[+] Gold H1 CMO Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hTrendEMA != INVALID_HANDLE) IndicatorRelease(m_hTrendEMA);
   Print("[-] Gold H1 CMO Master EA Deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Katz Fractal Dimension calculation                               |
//+------------------------------------------------------------------+
double CalculateKFD(int shift, int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, shift, period + 1, rates);
   if(copied < period + 1) return(1.5);

   double first_close = rates[period].close;
   double last_close  = rates[0].close;
   double euclid_d    = MathAbs(last_close - first_close);

   double total_len = 0.0;
   for(int i = 0; i < period; i++)
   {
      total_len += MathAbs(rates[i].close - rates[i + 1].close);
   }

   if(total_len > 1e-6 && euclid_d > 1e-6)
   {
      double d = MathLog10(period) / (MathLog10(period) + MathLog10(euclid_d / total_len));
      if(d < 1.0) d = 1.0;
      if(d > 2.0) d = 2.0;
      return(d);
   }
   return(1.5);
}

//+------------------------------------------------------------------+
//| Chande Momentum Oscillator (CMO) Calculation                     |
//| shift = 1 evaluates Bar 1 Close; shift = 2 evaluates Bar 2 Close |
//+------------------------------------------------------------------+
double CalculateCMO(int shift, int period)
{
   int needed = period + 2;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, shift, needed, rates);
   if(copied < period + 1) return(0.0);

   double sum_pos = 0.0;
   double sum_neg = 0.0;

   for(int i = 0; i < period; i++)
   {
      double diff = rates[i].close - rates[i + 1].close;
      if(diff > 0.0) sum_pos += diff;
      else if(diff < 0.0) sum_neg += MathAbs(diff);
   }

   double tot = sum_pos + sum_neg;
   if(tot <= 1e-6) return(0.0);

   return(100.0 * (sum_pos - sum_neg) / tot);
}

//+------------------------------------------------------------------+
//| Monthly PnL tracking & ASAR Risk Management                      |
//+------------------------------------------------------------------+
void UpdateMonthlyState(datetime current_time)
{
   MqlDateTime dt;
   TimeToStruct(current_time, dt);
   int bar_month = dt.year * 100 + dt.mon;

   if(bar_month != m_current_month)
   {
      m_current_month        = bar_month;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      Print("[*] Strategy 91: New calendar month initialized: ", m_current_month);
   }

   // Recalculate monthly realized PnL
   datetime start_of_month;
   MqlDateTime m_dt = dt;
   m_dt.day = 1; m_dt.hour = 0; m_dt.min = 0; m_dt.sec = 0;
   start_of_month = StructToTime(m_dt);

   HistorySelect(start_of_month, current_time);
   double pnl = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber)
         {
            pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   m_monthly_realized_pnl = pnl;

   if(InpMonthlyProfitLock > 0.0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      if(!m_is_month_locked)
      {
         Print("[LOCK] Monthly profit lock triggered! Realized: $", m_monthly_realized_pnl, " >= $", InpMonthlyProfitLock);
         m_is_month_locked = true;
      }
   }

   if(InpHardLossBreaker > 0.0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
      {
         Print("[CIRCUIT BREAKER] Hard loss breaker triggered! Realized: $", m_monthly_realized_pnl, " <= -$", InpHardLossBreaker);
         m_is_month_locked = true;
      }
   }
}

//+------------------------------------------------------------------+
//| Get dynamic lot size with defensive de-leveraging                |
//+------------------------------------------------------------------+
double GetExecutionLotSize()
{
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      double def_lot = InpLotSize * InpDefensiveMult;
      return(MathMax(def_lot, 0.01));
   }
   return(InpLotSize);
}

//+------------------------------------------------------------------+
//| Check if position currently open for this magic number           |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            return(true);
      }
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Bar Close confirmation: execute only once per new bar open
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == m_last_bar_time) return;
   m_last_bar_time = current_bar_time;

   // Update Monthly PnL & risk gates
   UpdateMonthlyState(current_bar_time);
   if(m_is_month_locked) return;

   // Spread Check
   double current_spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(current_spread > InpMaxSpread)
   {
      Print("[!] Spread too wide: $", current_spread, " > $", InpMaxSpread);
      return;
   }

   // Skip if position open
   if(HasOpenPosition()) return;

   // Read ATR(14) on completed bar (shift 1)
   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0) return;
   double c_atr = atr_buf[0];
   if(c_atr < 0.5) return; // Stagnant volatility gate

   // Read Katz Fractal Dimension on completed bar (shift 1)
   if(InpUseKfdFilter)
   {
      double kfd = CalculateKFD(1, InpKfdPeriod);
      if(kfd > InpKfdThreshold) return; // Anti-Chaos Filter triggered
   }

   // Read Structural Trend Filter on completed bar (shift 1)
   bool trend_up = true;
   bool trend_dn = true;
   if(InpTrendFilter != TREND_NONE && m_hTrendEMA != INVALID_HANDLE)
   {
      double ema_buf[];
      ArraySetAsSeries(ema_buf, true);
      if(CopyBuffer(m_hTrendEMA, 0, 1, 1, ema_buf) <= 0) return;
      double trend_ema = ema_buf[0];
      double bar1_close = iClose(_Symbol, PERIOD_H1, 1);
      trend_up = (bar1_close > trend_ema);
      trend_dn = (bar1_close < trend_ema);
   }

   // Calculate CMO on closed bars: shift 1, 2
   double cmo_1 = CalculateCMO(1, InpCmoPeriod);
   double cmo_2 = CalculateCMO(2, InpCmoPeriod);

   bool long_signal  = false;
   bool short_signal = false;

   switch(InpTriggerMode)
   {
      case CMO_THRUST_EXPANSION:
         // Breakout thrust: CMO crosses above +thresh / below -thresh
         if(cmo_2 < InpTriggerThreshold && cmo_1 >= InpTriggerThreshold && trend_up)
            long_signal = true;
         else if(cmo_2 > -InpTriggerThreshold && cmo_1 <= -InpTriggerThreshold && trend_dn)
            short_signal = true;
         break;

      case CMO_ZERO_CROSS:
         // Centerline cross
         if(cmo_2 <= 0.0 && cmo_1 > 0.0 && trend_up)
            long_signal = true;
         else if(cmo_2 >= 0.0 && cmo_1 < 0.0 && trend_dn)
            short_signal = true;
         break;

      case CMO_EXTREME_REVERSION:
         // Extreme bounce
         if(cmo_2 <= -InpTriggerThreshold && cmo_1 > -InpTriggerThreshold && trend_up)
            long_signal = true;
         else if(cmo_2 >= InpTriggerThreshold && cmo_1 < InpTriggerThreshold && trend_dn)
            short_signal = true;
         break;

      case CMO_SIGNAL_CROSS:
         // Signal cross placeholder
         break;
   }

   // Execution
   double trade_lot = GetExecutionLotSize();

   if(long_signal)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = ask - (InpSlMult * c_atr);
      double tp  = ask + (InpTpMult * c_atr);

      sl = NormalizeDouble(sl, _Digits);
      tp = NormalizeDouble(tp, _Digits);

      if(m_trade.Buy(trade_lot, _Symbol, ask, sl, tp, "CMO_H1_BUY"))
      {
         Print("[+] CMO BUY Executed: Price=", ask, " SL=", sl, " TP=", tp, " Lot=", trade_lot, " CMO1=", cmo_1);
      }
      else
      {
         Print("[!] BUY Execution Error: ", m_trade.ResultRetcode(), " Desc: ", m_trade.ResultRetcodeDescription());
      }
   }
   else if(short_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = bid + (InpSlMult * c_atr);
      double tp  = bid - (InpTpMult * c_atr);

      sl = NormalizeDouble(sl, _Digits);
      tp = NormalizeDouble(tp, _Digits);

      if(m_trade.Sell(trade_lot, _Symbol, bid, sl, tp, "CMO_H1_SELL"))
      {
         Print("[+] CMO SELL Executed: Price=", bid, " SL=", sl, " TP=", tp, " Lot=", trade_lot, " CMO1=", cmo_1);
      }
      else
      {
         Print("[!] SELL Execution Error: ", m_trade.ResultRetcode(), " Desc: ", m_trade.ResultRetcodeDescription());
      }
   }
}
//+------------------------------------------------------------------+

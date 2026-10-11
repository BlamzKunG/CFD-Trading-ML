//+------------------------------------------------------------------+
//|                   Gold_H1_BOP_Master_EA.mq5                      |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 89: Gold H1 Igor Livshin Balance of Power             |
//|   Internal Bar Auction Dominance & Thrust (BOP-IBV-KFD)          |
//|     Magic: 890001 | Timeframe: H1 | Symbol: XAUUSD               |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Igor Livshin Balance of Power Master EA (Magic 890001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM DEFINITIONS ---
enum ENUM_BOP_SMOOTH
{
   BOP_SMOOTH_SMA,  // Simple Moving Average
   BOP_SMOOTH_EMA   // Exponential Moving Average
};

enum ENUM_BOP_TRIGGER
{
   BOP_THRUST_EXPANSION,    // Thrust Breakout: BOP crosses above/below threshold
   BOP_ZERO_CROSS,          // Centerline Cross: BOP crosses 0.0 in trend direction
   BOP_EXTREME_INFLECTION,  // Mean Reversion: BOP reaches extreme and inflects
   BOP_CONTINUATION_TURN    // Continuation: BOP turns in trend direction on active side
};

enum ENUM_TREND_FILTER
{
   TREND_EMA50,     // Fast Structural Trend: Price > EMA50
   TREND_EMA200,    // Macro Structural Trend: Price > EMA200
   TREND_NONE       // No Macro Filter
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 890001;               // EA Magic Number
input double                InpLotSize             = 0.10;                 // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;                 // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 250.0;                // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;                // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;                // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;                 // Defensive Lot Multiplier (0.25x)

input group "=== Igor Livshin Balance of Power Configuration ==="
input int                   InpBopPeriod           = 10;                   // BOP Smoothing Period (Default: 10)
input ENUM_BOP_SMOOTH       InpSmoothType          = BOP_SMOOTH_SMA;       // Smoothing Method (SMA / EMA)
input ENUM_BOP_TRIGGER      InpTriggerMode         = BOP_THRUST_EXPANSION; // Entry Trigger Mechanism
input double                InpTriggerThreshold    = 0.25;                 // BOP Threshold (e.g. 0.25 for thrust)
input double                InpTpMult              = 5.0;                  // Take Profit ATR Multiplier (5.0R)
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

   Print("[+] Gold H1 BOP Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hTrendEMA != INVALID_HANDLE) IndicatorRelease(m_hTrendEMA);
   Print("[-] Gold H1 BOP Master EA Deinitialized. Reason: ", reason);
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
//| Raw Bar BOP calculation: (Close - Open) / (High - Low)           |
//+------------------------------------------------------------------+
double GetRawBOP(const MqlRates &rate)
{
   double hl = rate.high - rate.low;
   if(hl <= 1e-4) return(0.0);
   double raw = (rate.close - rate.open) / hl;
   if(raw > 1.0) raw = 1.0;
   if(raw < -1.0) raw = -1.0;
   return(raw);
}

//+------------------------------------------------------------------+
//| Smoothed BOP calculation over window                             |
//| shift = 1 evaluates Bar 1 Close; shift = 2 evaluates Bar 2 Close |
//+------------------------------------------------------------------+
double CalculateSmoothedBOP(int shift, int period, ENUM_BOP_SMOOTH smooth_type)
{
   int needed = period + 50; // Extra buffer for EMA convergence
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, shift, needed, rates);
   if(copied < period) return(0.0);

   if(smooth_type == BOP_SMOOTH_SMA)
   {
      double sum = 0.0;
      for(int i = 0; i < period; i++)
      {
         sum += GetRawBOP(rates[i]);
      }
      return(sum / (double)period);
   }
   else // EMA
   {
      double alpha = 2.0 / (period + 1.0);
      int start_idx = copied - 1;
      double ema = GetRawBOP(rates[start_idx]);
      for(int i = start_idx - 1; i >= 0; i--)
      {
         ema = (GetRawBOP(rates[i]) * alpha) + (ema * (1.0 - alpha));
      }
      return(ema);
   }
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
      Print("[*] Strategy 89: New calendar month initialized: ", m_current_month);
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

   // Calculate BOP on closed bars: shift 1, 2, 3
   double bop_1 = CalculateSmoothedBOP(1, InpBopPeriod, InpSmoothType);
   double bop_2 = CalculateSmoothedBOP(2, InpBopPeriod, InpSmoothType);
   double bop_3 = CalculateSmoothedBOP(3, InpBopPeriod, InpSmoothType);

   bool long_signal  = false;
   bool short_signal = false;

   switch(InpTriggerMode)
   {
      case BOP_THRUST_EXPANSION:
         // Breakout thrust: BOP expands across threshold
         if(bop_2 < InpTriggerThreshold && bop_1 >= InpTriggerThreshold && trend_up)
            long_signal = true;
         else if(bop_2 > -InpTriggerThreshold && bop_1 <= -InpTriggerThreshold && trend_dn)
            short_signal = true;
         break;

      case BOP_ZERO_CROSS:
         // Centerline cross
         if(bop_2 <= 0.0 && bop_1 > 0.0 && trend_up)
            long_signal = true;
         else if(bop_2 >= 0.0 && bop_1 < 0.0 && trend_dn)
            short_signal = true;
         break;

      case BOP_EXTREME_INFLECTION:
         // Extreme bounce
         if(bop_2 <= -InpTriggerThreshold && bop_1 > bop_2 && trend_up)
            long_signal = true;
         else if(bop_2 >= InpTriggerThreshold && bop_1 < bop_2 && trend_dn)
            short_signal = true;
         break;

      case BOP_CONTINUATION_TURN:
         // Inflection on active side
         if(bop_2 > 0.0 && bop_1 > bop_2 && bop_2 <= bop_3 && trend_up)
            long_signal = true;
         else if(bop_2 < 0.0 && bop_1 < bop_2 && bop_2 >= bop_3 && trend_dn)
            short_signal = true;
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

      if(m_trade.Buy(trade_lot, _Symbol, ask, sl, tp, "BOP_H1_BUY"))
      {
         Print("[+] BOP BUY Executed: Price=", ask, " SL=", sl, " TP=", tp, " Lot=", trade_lot, " BOP1=", bop_1);
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

      if(m_trade.Sell(trade_lot, _Symbol, bid, sl, tp, "BOP_H1_SELL"))
      {
         Print("[+] BOP SELL Executed: Price=", bid, " SL=", sl, " TP=", tp, " Lot=", trade_lot, " BOP1=", bop_1);
      }
      else
      {
         Print("[!] SELL Execution Error: ", m_trade.ResultRetcode(), " Desc: ", m_trade.ResultRetcodeDescription());
      }
   }
}
//+------------------------------------------------------------------+

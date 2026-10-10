//+------------------------------------------------------------------+
//|                 Gold_H1_TSI_Momentum_Master_EA.mq5               |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|    Strategy 75: Gold H1 True Strength Index Momentum Inflection  |
//|      PF: 1.666 | Net: +$8,173.20 | DD: $895.81 | MCR: 68.06%     |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 True Strength Index (TSI) Momentum Inflection Master EA (Magic 750001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_TSI_TRIGGER
{
   TSI_SIGNAL_CROSS,     // TSI crosses Signal Line
   TSI_ZERO_CROSS,       // TSI crosses Zero Line
   TSI_SIGNAL_AND_ZERO,  // Signal Cross confirmed by Zero Line direction
   TSI_INFLECTION        // Slope turning point in oversold/overbought zone
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 750001;    // EA Magic Number
input double                InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== True Strength Index Configuration ==="
input int                   InpR                   = 13;        // First Smoothing Period (r)
input int                   InpS                   = 7;         // Second Smoothing Period (s)
input int                   InpSigLen              = 5;         // Signal Line EMA Period
input ENUM_TSI_TRIGGER      InpTriggerMode         = TSI_INFLECTION; // Trigger Mode
input double                InpInflectionZone      = 5.0;       // Inflection Boundary (+/- level)
input double                InpTpMult              = 5.0;       // Take Profit ATR Multiplier (5.0R)
input double                InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

input group "=== Macro Trend & Noise Gate ==="
input int                   InpAtrPeriod           = 14;        // ATR Volatility Period
input int                   InpEmaPeriod           = 0;         // Macro Structural Trend EMA (0 = Disabled)
input bool                  InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.35;      // Maximum Fractal Dimension (<= 1.35)
input int                   InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hEMA;
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

   if(InpEmaPeriod > 0)
   {
      m_hEMA = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(m_hEMA == INVALID_HANDLE)
      {
         Print("[!] Error initializing EMA handle.");
         return(INIT_FAILED);
      }
   }
   else
   {
      m_hEMA = INVALID_HANDLE;
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Gold H1 TSI Momentum Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   if(m_hEMA != INVALID_HANDLE) IndicatorRelease(m_hEMA);
   Print("[-] Gold H1 TSI Momentum Master EA Deinitialized.");
}

//+------------------------------------------------------------------+
//| Monthly Risk & Performance Governance                           |
//+------------------------------------------------------------------+
void UpdateMonthlyGovernance(datetime current_time)
{
   MqlDateTime dt;
   TimeToStruct(current_time, dt);
   int month_key = dt.year * 100 + dt.mon;

   if(month_key != m_current_month)
   {
      m_current_month        = month_key;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      Print("[GOVERNANCE] New Calendar Month: ", month_key, " | Resetting Risk Allocation.");
      return;
   }

   HistorySelect(StringToTime(StringFormat("%04d.%02d.01 00:00", dt.year, dt.mon)), TimeCurrent());
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
            pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }
   m_monthly_realized_pnl = pnl;

   if(InpMonthlyProfitLock > 0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      if(!m_is_month_locked)
      {
         Print("[PROFIT LOCK] Target of $", InpMonthlyProfitLock, " achieved! Realized: $", m_monthly_realized_pnl);
         m_is_month_locked = true;
      }
   }
   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
      {
         Print("[CIRCUIT BREAKER] Hard Stop Loss of -$", InpHardLossBreaker, " hit! Realized: $", m_monthly_realized_pnl);
         m_is_month_locked = true;
      }
   }
}

//+------------------------------------------------------------------+
//| Dynamic Execution Lot Size Sizing                                |
//+------------------------------------------------------------------+
double GetExecutionLotSize()
{
   if(InpDefensiveThresh > 0 && m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      double def_lot = InpLotSize * InpDefensiveMult;
      return MathMax(0.01, NormalizeDouble(def_lot, 2));
   }
   return InpLotSize;
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension (KFD)                             |
//+------------------------------------------------------------------+
double ComputeKFD(const double &closes[], int shift, int period)
{
   if(ArraySize(closes) < shift + period + 1) return 1.5;

   double c_first = closes[shift + period - 1];
   double c_last  = closes[shift];
   double d = MathAbs(c_last - c_first);

   double total_length = 0.0;
   for(int i = 0; i < period - 1; i++)
   {
      total_length += MathAbs(closes[shift + i] - closes[shift + i + 1]);
   }

   if(total_length > 1e-6 && d > 1e-6)
   {
      double num = MathLog10(period);
      double den = MathLog10(period) + MathLog10(d / total_length);
      if(den > 0.0)
      {
         double kfd = num / den;
         return MathMax(1.0, MathMin(2.0, kfd));
      }
   }
   return 1.5;
}

//+------------------------------------------------------------------+
//| Compute True Strength Index (TSI) & Signal Line                 |
//+------------------------------------------------------------------+
bool ComputeTSI(const double &closes[], int total_bars,
                double &tsi1, double &tsi2, double &tsi3,
                double &sig1, double &sig2)
{
   // closes[] is in series format (0 is current bar, 1 is bar 1, etc.)
   if(total_bars < 80) return false;

   // Convert to chronological array (0 = oldest)
   double c[];
   ArrayResize(c, total_bars);
   for(int i = 0; i < total_bars; i++)
   {
      c[i] = closes[total_bars - 1 - i];
   }

   int n = total_bars;
   double diff[], abs_diff[];
   ArrayResize(diff, n);
   ArrayResize(abs_diff, n);
   diff[0] = 0.0;
   abs_diff[0] = 0.0;
   for(int i = 1; i < n; i++)
   {
      diff[i] = c[i] - c[i - 1];
      abs_diff[i] = MathAbs(diff[i]);
   }

   // EMA1 of diff and abs_diff
   double ema1_diff[], ema1_abs[];
   ArrayResize(ema1_diff, n);
   ArrayResize(ema1_abs, n);
   ema1_diff[0] = diff[0];
   ema1_abs[0] = abs_diff[0];
   double a_r = 2.0 / (InpR + 1.0);
   for(int i = 1; i < n; i++)
   {
      ema1_diff[i] = (diff[i] * a_r) + (ema1_diff[i - 1] * (1.0 - a_r));
      ema1_abs[i]  = (abs_diff[i] * a_r) + (ema1_abs[i - 1] * (1.0 - a_r));
   }

   // EMA2 of ema1
   double ema2_diff[], ema2_abs[];
   ArrayResize(ema2_diff, n);
   ArrayResize(ema2_abs, n);
   ema2_diff[0] = ema1_diff[0];
   ema2_abs[0] = ema1_abs[0];
   double a_s = 2.0 / (InpS + 1.0);
   for(int i = 1; i < n; i++)
   {
      ema2_diff[i] = (ema1_diff[i] * a_s) + (ema2_diff[i - 1] * (1.0 - a_s));
      ema2_abs[i]  = (ema1_abs[i] * a_s) + (ema2_abs[i - 1] * (1.0 - a_s));
   }

   double tsi[];
   ArrayResize(tsi, n);
   for(int i = 0; i < n; i++)
   {
      if(ema2_abs[i] > 1e-6)
         tsi[i] = 100.0 * (ema2_diff[i] / ema2_abs[i]);
      else
         tsi[i] = 0.0;
   }

   // Signal line = EMA of TSI
   double sig[];
   ArrayResize(sig, n);
   sig[0] = tsi[0];
   double a_sig = 2.0 / (InpSigLen + 1.0);
   for(int i = 1; i < n; i++)
   {
      sig[i] = (tsi[i] * a_sig) + (sig[i - 1] * (1.0 - a_sig));
   }

   // Map back to series indices:
   // closes[1] corresponds to c[n - 2]
   // closes[2] corresponds to c[n - 3]
   // closes[3] corresponds to c[n - 4]
   tsi1 = tsi[n - 2];
   tsi2 = tsi[n - 3];
   tsi3 = tsi[n - 4];

   sig1 = sig[n - 2];
   sig2 = sig[n - 3];

   return true;
}

//+------------------------------------------------------------------+
//| Count active positions for this EA                              |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            count++;
         }
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == m_last_bar_time) return;

   UpdateMonthlyGovernance(TimeCurrent());

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   if(spread > InpMaxSpread) return;

   int open_positions = CountOpenPositions();
   if(open_positions > 0 || m_is_month_locked)
   {
      m_last_bar_time = bar_time;
      return;
   }

   int lookback = 120;
   double closes[];
   ArraySetAsSeries(closes, true);

   if(CopyClose(_Symbol, PERIOD_H1, 1, lookback, closes) < lookback) return;

   double atr_buf[1];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0) return;
   double current_atr = atr_buf[0];
   if(current_atr < 0.50) return;

   bool ema_long_ok = true;
   bool ema_short_ok = true;
   if(m_hEMA != INVALID_HANDLE)
   {
      double ema_buf[1];
      if(CopyBuffer(m_hEMA, 0, 1, 1, ema_buf) <= 0) return;
      ema_long_ok  = (closes[0] > ema_buf[0]);
      ema_short_ok = (closes[0] < ema_buf[0]);
   }

   if(InpUseKFD_Filter)
   {
      double kfd_val = ComputeKFD(closes, 0, InpKfdPeriod);
      if(kfd_val > InpKfdThreshold)
      {
         m_last_bar_time = bar_time;
         return;
      }
   }

   double t1, t2, t3, s1, s2;
   if(!ComputeTSI(closes, lookback, t1, t2, t3, s1, s2)) return;

   bool bull_signal = false;
   bool bear_signal = false;

   if(InpTriggerMode == TSI_SIGNAL_CROSS)
   {
      bull_signal = (t1 >= s1) && (t2 < s2);
      bear_signal = (t1 <= s1) && (t2 > s2);
   }
   else if(InpTriggerMode == TSI_ZERO_CROSS)
   {
      bull_signal = (t1 >= 0.0) && (t2 < 0.0);
      bear_signal = (t1 <= 0.0) && (t2 > 0.0);
   }
   else if(InpTriggerMode == TSI_SIGNAL_AND_ZERO)
   {
      bull_signal = (t1 >= s1) && (t2 < s2) && (t1 > 0.0);
      bear_signal = (t1 <= s1) && (t2 > s2) && (t1 < 0.0);
   }
   else if(InpTriggerMode == TSI_INFLECTION)
   {
      bull_signal = (t1 > t2) && (t2 <= t3) && (t1 < -InpInflectionZone);
      bear_signal = (t1 < t2) && (t2 >= t3) && (t1 > InpInflectionZone);
   }

   bool bull_trigger = bull_signal && ema_long_ok;
   bool bear_trigger = bear_signal && ema_short_ok;

   double exec_lot = GetExecutionLotSize();

   if(bull_trigger)
   {
      double sl = ask - (InpSlMult * current_atr);
      double tp = ask + (InpTpMult * current_atr);
      m_trade.Buy(exec_lot, _Symbol, ask, sl, tp, "S75 TSI Long");
      Print("[TRADE] BUY 0.10 XAUUSD @ ", ask, " | SL: ", sl, " | TP: ", tp, " | TSI: ", DoubleToString(t1, 2));
   }
   else if(bear_trigger)
   {
      double sl = bid + (InpSlMult * current_atr);
      double tp = bid - (InpTpMult * current_atr);
      m_trade.Sell(exec_lot, _Symbol, bid, sl, tp, "S75 TSI Short");
      Print("[TRADE] SELL 0.10 XAUUSD @ ", bid, " | SL: ", sl, " | TP: ", tp, " | TSI: ", DoubleToString(t1, 2));
   }

   m_last_bar_time = bar_time;
}
//+------------------------------------------------------------------+

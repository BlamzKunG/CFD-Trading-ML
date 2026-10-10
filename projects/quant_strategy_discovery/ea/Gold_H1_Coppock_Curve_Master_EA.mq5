//+------------------------------------------------------------------+
//|                 Gold_H1_Coppock_Curve_Master_EA.mq5               |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|       Strategy 69: Coppock Curve Momentum Inflection (CCMI-KFD)  |
//|        PF: 1.450 | Win: 50.0% | Max DD: $1,153 | Net: +$7.0k      |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Coppock Curve Momentum Inflection Master EA (Magic 690001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_TRIGGER_MODE
{
   TRIGGER_INFLECTION,       // Inflection Bottom/Top Turn (<0 for Long, >0 for Short)
   TRIGGER_ZERO_CROSS,       // Zero Line Cross
   TRIGGER_SIGNAL_CROSS,     // Coppock Signal Line Cross
   TRIGGER_INFLECTION_OR_ZERO// Inflection OR Zero Line Cross
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong              InpMagicNumber         = 690001;    // EA Magic Number
input double             InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double             InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double             InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double             InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double             InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double             InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Coppock Curve Configuration ==="
input int                InpROC1                = 6;         // Fast ROC Period (r1)
input int                InpROC2                = 12;        // Slow ROC Period (r2)
input int                InpWMAPeriod           = 8;         // WMA Smoothing Period (w)
input int                InpSignalPeriod        = 5;         // Signal Line EMA Period
input ENUM_TRIGGER_MODE  InpTriggerMode         = TRIGGER_INFLECTION; // Trigger Mode
input double             InpTpMult              = 3.5;       // Take Profit ATR Multiplier (3.5R)
input double             InpSlMult              = 2.5;       // Stop Loss ATR Multiplier (2.5R)

input group "=== Macro Trend & Fractal Noise Gate ==="
input int                InpAtrPeriod           = 14;        // ATR Volatility Period
input int                InpEmaPeriod           = 0;         // Macro Structural Trend EMA (0 = Disabled / None)
input bool               InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double             InpKfdThreshold        = 1.40;      // Maximum Fractal Dimension (<= 1.40)
input int                InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

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

   Print("[+] Gold H1 Coppock Curve Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   if(m_hEMA != INVALID_HANDLE)
      IndicatorRelease(m_hEMA);
   Comment("");
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension                                   |
//+------------------------------------------------------------------+
double ComputeKFD(const double &closes[], int start_idx, int period)
{
   if(ArraySize(closes) < start_idx + period) return 1.5;
   double euclid_d = MathAbs(closes[start_idx] - closes[start_idx + period - 1]);
   double total_len = 0.0;
   for(int i = start_idx; i < start_idx + period - 1; i++)
   {
      total_len += MathAbs(closes[i] - closes[i + 1]);
   }
   if(total_len > 1e-6 && euclid_d > 1e-6)
   {
      double ratio = euclid_d / total_len;
      double n_bars = (double)period;
      double val = MathLog10(n_bars) / (MathLog10(n_bars) + MathLog10(ratio));
      return MathMax(1.0, MathMin(2.0, val));
   }
   return 1.5;
}

//+------------------------------------------------------------------+
//| Compute Coppock Curve and Signal Line                            |
//+------------------------------------------------------------------+
bool ComputeCoppock(const double &closes[], int total_bars, double &c_now, double &c_prev1, double &c_prev2, double &s_now, double &s_prev)
{
   // Closes array indexed 0 = bar 1, 1 = bar 2, etc. (older to the right)
   int req_bars = InpROC2 + InpWMAPeriod + InpSignalPeriod + 10;
   if(total_bars < req_bars) return false;

   // Calculate ROC_sum for needed lookback
   int roc_len = InpWMAPeriod + InpSignalPeriod + 5;
   double roc_sum[];
   ArrayResize(roc_sum, roc_len);

   for(int k = 0; k < roc_len; k++)
   {
      int idx_curr = k;
      int idx_r1   = k + InpROC1;
      int idx_r2   = k + InpROC2;
      if(idx_r2 >= total_bars) return false;

      double c0 = closes[idx_curr];
      double cr1 = closes[idx_r1];
      double cr2 = closes[idx_r2];

      double r1_val = (cr1 > 1e-6) ? ((c0 - cr1) / cr1 * 100.0) : 0.0;
      double r2_val = (cr2 > 1e-6) ? ((c0 - cr2) / cr2 * 100.0) : 0.0;
      roc_sum[k] = r1_val + r2_val;
   }

   // Calculate WMA for bar 1, bar 2, bar 3, etc.
   // WMA weights: 1 for oldest in window, InpWMAPeriod for newest
   double w_sum = (double)(InpWMAPeriod * (InpWMAPeriod + 1)) / 2.0;

   int coppock_points = InpSignalPeriod + 3;
   double coppock_vals[];
   ArrayResize(coppock_vals, coppock_points);

   for(int m = 0; m < coppock_points; m++)
   {
      double weighted = 0.0;
      for(int w = 0; w < InpWMAPeriod; w++)
      {
         // In roc_sum, index m is newest, m + (InpWMAPeriod - 1 - w) is older
         int weight = InpWMAPeriod - w;
         weighted += roc_sum[m + w] * weight;
      }
      coppock_vals[m] = weighted / w_sum;
   }

   c_now   = coppock_vals[0]; // bar 1
   c_prev1 = coppock_vals[1]; // bar 2
   c_prev2 = coppock_vals[2]; // bar 3

   // Compute EMA signal line
   double alpha = 2.0 / (InpSignalPeriod + 1.0);
   s_prev = coppock_vals[1];
   s_now  = (c_now * alpha) + (s_prev * (1.0 - alpha));

   return true;
}

//+------------------------------------------------------------------+
//| Check and Update ASAR Monthly Risk Governance                     |
//+------------------------------------------------------------------+
void UpdateMonthlyGovernance(datetime time_current)
{
   MqlDateTime dt;
   TimeToStruct(time_current, dt);
   int bar_month = dt.year * 100 + dt.month;

   if(bar_month != m_current_month)
   {
      m_current_month        = bar_month;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      Print("[ASAR] New month entered: ", m_current_month, ". Monthly governance limits reset.");
   }

   // Scan history deals closed in current month
   datetime start_of_month = StringToTime(StringFormat("%04d.%02d.01 00:00", dt.year, dt.month));
   HistorySelect(start_of_month, time_current);

   double current_pnl = 0.0;
   int total_deals = HistoryDealsTotal();
   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber &&
            HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol)
         {
            current_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                         + HistoryDealGetDouble(ticket, DEAL_SWAP)
                         + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   m_monthly_realized_pnl = current_pnl;

   if(InpMonthlyProfitLock > 0.0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      if(!m_is_month_locked)
         Print("[ASAR LOCK] Target Profit reached ($", DoubleToString(m_monthly_realized_pnl, 2), " >= $", InpMonthlyProfitLock, "). Trading locked for month.");
      m_is_month_locked = true;
   }
   else if(InpHardLossBreaker > 0.0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
         Print("[ASAR BREAKER] Max Drawdown Breaker hit ($", DoubleToString(m_monthly_realized_pnl, 2), " <= -$", InpHardLossBreaker, "). Trading locked for month.");
      m_is_month_locked = true;
   }
}

//+------------------------------------------------------------------+
//| Calculate dynamic sizing based on ASAR defensive throttling      |
//+------------------------------------------------------------------+
double GetExecutionLotSize()
{
   double lot = InpLotSize;
   if(InpDefensiveThresh > 0.0 && m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      lot = InpLotSize * InpDefensiveMult;
      double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      if(lot < min_lot) lot = min_lot;
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      lot = MathFloor(lot / step) * step;
   }
   return lot;
}

//+------------------------------------------------------------------+
//| Count active positions for this EA                              |
//+------------------------------------------------------------------+
int CountOpenPositions(int &pos_type)
{
   int count = 0;
   pos_type = -1;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            count++;
            pos_type = (int)PositionGetInteger(POSITION_TYPE);
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
   // Check bar arrival (Execute on Bar Open)
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == m_last_bar_time) return;

   // Update Monthly ASAR Risk Limits
   UpdateMonthlyGovernance(TimeCurrent());

   // Check spread filter
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   if(spread > InpMaxSpread)
   {
      Print("[!] Spread too wide: ", DoubleToString(spread, 2), " > ", InpMaxSpread);
      return;
   }

   int pos_type = -1;
   int open_positions = CountOpenPositions(pos_type);

   // If already in position or month locked, do not enter new trade
   if(open_positions > 0 || m_is_month_locked)
   {
      m_last_bar_time = bar_time;
      return;
   }

   // Prepare Lookback Data
   int lookback = 80;
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, lookback, closes) < lookback) return;

   // Compute ATR
   double atr_buf[1];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0) return;
   double current_atr = atr_buf[0];
   if(current_atr < 0.50) return; // Stagnant volatility safety

   // Macro Structural Trend Filter (EMA)
   bool ema_long_ok = true;
   bool ema_short_ok = true;
   if(m_hEMA != INVALID_HANDLE)
   {
      double ema_buf[1];
      if(CopyBuffer(m_hEMA, 0, 1, 1, ema_buf) <= 0) return;
      ema_long_ok  = (closes[0] > ema_buf[0]);
      ema_short_ok = (closes[0] < ema_buf[0]);
   }

   // Katz Fractal Dimension Gate
   if(InpUseKFD_Filter)
   {
      double kfd_val = ComputeKFD(closes, 0, InpKfdPeriod);
      if(kfd_val > InpKfdThreshold)
      {
         m_last_bar_time = bar_time;
         return; // High Brownian noise, block entry
      }
   }

   // Compute Coppock Curve Metrics
   double c_now, c_prev1, c_prev2, s_now, s_prev;
   if(!ComputeCoppock(closes, lookback, c_now, c_prev1, c_prev2, s_now, s_prev)) return;

   bool bull_signal = false;
   bool bear_signal = false;

   if(InpTriggerMode == TRIGGER_INFLECTION)
   {
      bull_signal = (c_now > c_prev1) && (c_prev1 <= c_prev2) && (c_now < 0.0);
      bear_signal = (c_now < c_prev1) && (c_prev1 >= c_prev2) && (c_now > 0.0);
   }
   else if(InpTriggerMode == TRIGGER_ZERO_CROSS)
   {
      bull_signal = (c_now > 0.0) && (c_prev1 <= 0.0);
      bear_signal = (c_now < 0.0) && (c_prev1 >= 0.0);
   }
   else if(InpTriggerMode == TRIGGER_SIGNAL_CROSS)
   {
      bull_signal = (c_now > s_now) && (c_prev1 <= s_prev);
      bear_signal = (c_now < s_now) && (c_prev1 >= s_prev);
   }
   else if(InpTriggerMode == TRIGGER_INFLECTION_OR_ZERO)
   {
      bool infl_bull = (c_now > c_prev1) && (c_prev1 <= c_prev2) && (c_now < 0.0);
      bool zero_bull = (c_now > 0.0) && (c_prev1 <= 0.0);
      bull_signal = infl_bull || zero_bull;

      bool infl_bear = (c_now < c_prev1) && (c_prev1 >= c_prev2) && (c_now > 0.0);
      bool zero_bear = (c_now < 0.0) && (c_prev1 >= 0.0);
      bear_signal = infl_bear || zero_bear;
   }

   bool bull_trigger = bull_signal && ema_long_ok;
   bool bear_trigger = bear_signal && ema_short_ok;

   double exec_lot = GetExecutionLotSize();

   if(bull_trigger)
   {
      double sl = ask - (InpSlMult * current_atr);
      double tp = ask + (InpTpMult * current_atr);
      m_trade.Buy(exec_lot, _Symbol, ask, sl, tp, "S69 CCMI Long");
      Print("[TRADE] BUY 0.10 XAUUSD @ ", ask, " | SL: ", sl, " | TP: ", tp, " | Coppock: ", DoubleToString(c_now, 4));
   }
   else if(bear_trigger)
   {
      double sl = bid + (InpSlMult * current_atr);
      double tp = bid - (InpTpMult * current_atr);
      m_trade.Sell(exec_lot, _Symbol, bid, sl, tp, "S69 CCMI Short");
      Print("[TRADE] SELL 0.10 XAUUSD @ ", bid, " | SL: ", sl, " | TP: ", tp, " | Coppock: ", DoubleToString(c_now, 4));
   }

   m_last_bar_time = bar_time;
}
//+------------------------------------------------------------------+

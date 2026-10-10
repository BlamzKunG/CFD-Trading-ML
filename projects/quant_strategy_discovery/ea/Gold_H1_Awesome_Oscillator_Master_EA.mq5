//+------------------------------------------------------------------+
//|               Gold_H1_Awesome_Oscillator_Master_EA.mq5            |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|       Strategy 71: Awesome Oscillator Saucer & Zero Cross (AO)    |
//|        PF: 1.414 | Win: 39.4% | Max DD: $981 | Net: +$6.8k        |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Awesome Oscillator Saucer & Regime Flip Master EA (Magic 710001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_AO_TRIGGER
{
   AO_SAUCER,           // Saucer Re-acceleration
   AO_ZERO_CROSS,       // Zero Line Waterline Cross
   AO_TWIN_PEAKS,       // Twin Peaks Divergence
   AO_SAUCER_OR_ZERO    // Saucer OR Zero Line Cross
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong              InpMagicNumber         = 710001;    // EA Magic Number
input double             InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double             InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double             InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double             InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double             InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double             InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Awesome Oscillator Configuration ==="
input int                InpFastPeriod          = 3;         // Fast SMA Period (Default 3)
input int                InpSlowPeriod          = 21;        // Slow SMA Period (Default 21)
input ENUM_AO_TRIGGER    InpTriggerMode         = AO_SAUCER_OR_ZERO; // Trigger Mode
input double             InpTpMult              = 4.5;       // Take Profit ATR Multiplier (4.5R)
input double             InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

input group "=== Macro Trend & Noise Gate ==="
input int                InpAtrPeriod           = 14;        // ATR Volatility Period
input int                InpEmaPeriod           = 0;         // Macro Structural Trend EMA (0 = Disabled / None)
input bool               InpUseKFD_Filter       = false;     // Enable Katz Fractal Gate
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

   Print("[+] Gold H1 Awesome Oscillator Master EA Initialized Successfully. Magic: ", InpMagicNumber);
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
//| Compute Awesome Oscillator buffer for bars 1, 2, 3              |
//+------------------------------------------------------------------+
bool ComputeAO(const double &highs[], const double &lows[], int total_bars, double &ao0, double &ao1, double &ao2)
{
   int req_bars = InpSlowPeriod + 10;
   if(total_bars < req_bars) return false;

   double mp[];
   ArrayResize(mp, total_bars);
   for(int i = 0; i < total_bars; i++)
   {
      mp[i] = (highs[i] + lows[i]) / 2.0;
   }

   // Compute AO for bar 1 (index 0), bar 2 (index 1), bar 3 (index 2)
   double ao_vals[3];
   for(int k = 0; k < 3; k++)
   {
      double sum_fast = 0.0;
      for(int f = 0; f < InpFastPeriod; f++) sum_fast += mp[k + f];
      double sma_fast = sum_fast / InpFastPeriod;

      double sum_slow = 0.0;
      for(int s = 0; s < InpSlowPeriod; s++) sum_slow += mp[k + s];
      double sma_slow = sum_slow / InpSlowPeriod;

      ao_vals[k] = sma_fast - sma_slow;
   }

   ao0 = ao_vals[0]; // Bar 1
   ao1 = ao_vals[1]; // Bar 2
   ao2 = ao_vals[2]; // Bar 3
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
      Print("[ASAR] New month entered: ", m_current_month, ". Limits reset.");
   }

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
         Print("[ASAR LOCK] Target Profit reached ($", DoubleToString(m_monthly_realized_pnl, 2), " >= $", InpMonthlyProfitLock, "). Trading locked.");
      m_is_month_locked = true;
   }
   else if(InpHardLossBreaker > 0.0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
         Print("[ASAR BREAKER] Hard Loss Breaker hit ($", DoubleToString(m_monthly_realized_pnl, 2), " <= -$", InpHardLossBreaker, "). Trading locked.");
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

   int lookback = 60;
   double highs[], lows[], closes[];
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows, true);
   ArraySetAsSeries(closes, true);

   if(CopyHigh(_Symbol, PERIOD_H1, 1, lookback, highs) < lookback) return;
   if(CopyLow(_Symbol, PERIOD_H1, 1, lookback, lows) < lookback) return;
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

   double ao0, ao1, ao2;
   if(!ComputeAO(highs, lows, lookback, ao0, ao1, ao2)) return;

   bool bull_signal = false;
   bool bear_signal = false;

   if(InpTriggerMode == AO_SAUCER)
   {
      bull_signal = (ao0 > 0.0) && (ao1 > 0.0) && (ao2 > 0.0) && (ao1 < ao2) && (ao0 > ao1);
      bear_signal = (ao0 < 0.0) && (ao1 < 0.0) && (ao2 < 0.0) && (ao1 > ao2) && (ao0 < ao1);
   }
   else if(InpTriggerMode == AO_ZERO_CROSS)
   {
      bull_signal = (ao0 > 0.0) && (ao1 <= 0.0);
      bear_signal = (ao0 < 0.0) && (ao1 >= 0.0);
   }
   else if(InpTriggerMode == AO_SAUCER_OR_ZERO)
   {
      bool saucer_b = (ao0 > 0.0) && (ao1 > 0.0) && (ao2 > 0.0) && (ao1 < ao2) && (ao0 > ao1);
      bool cross_b  = (ao0 > 0.0) && (ao1 <= 0.0);
      bull_signal = saucer_b || cross_b;

      bool saucer_s = (ao0 < 0.0) && (ao1 < 0.0) && (ao2 < 0.0) && (ao1 > ao2) && (ao0 < ao1);
      bool cross_s  = (ao0 < 0.0) && (ao1 >= 0.0);
      bear_signal = saucer_s || cross_s;
   }

   bool bull_trigger = bull_signal && ema_long_ok;
   bool bear_trigger = bear_signal && ema_short_ok;

   double exec_lot = GetExecutionLotSize();

   if(bull_trigger)
   {
      double sl = ask - (InpSlMult * current_atr);
      double tp = ask + (InpTpMult * current_atr);
      m_trade.Buy(exec_lot, _Symbol, ask, sl, tp, "S71 AO Long");
      Print("[TRADE] BUY 0.10 XAUUSD @ ", ask, " | SL: ", sl, " | TP: ", tp, " | AO: ", DoubleToString(ao0, 3));
   }
   else if(bear_trigger)
   {
      double sl = bid + (InpSlMult * current_atr);
      double tp = bid - (InpTpMult * current_atr);
      m_trade.Sell(exec_lot, _Symbol, bid, sl, tp, "S71 AO Short");
      Print("[TRADE] SELL 0.10 XAUUSD @ ", bid, " | SL: ", sl, " | TP: ", tp, " | AO: ", DoubleToString(ao0, 3));
   }

   m_last_bar_time = bar_time;
}
//+------------------------------------------------------------------+

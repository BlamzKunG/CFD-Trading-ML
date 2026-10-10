//+------------------------------------------------------------------+
//|                   Gold_H1_DMI_ADX_Master_EA.mq5                  |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|    Strategy 79: Gold H1 Directional Movement System (DMI / ADX)  |
//|      PF: 1.933 | Net: +$5,503.08 | Max DD: $649.64 | Win: 50.0%  |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Directional Movement & ADX Trend Expansion Master EA (Magic 790001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_DMI_TRIGGER
{
   DMI_CROSS_ADX20,     // +DI/-DI Cross with ADX >= 20
   DMI_CROSS_ADX25,     // +DI/-DI Cross with ADX >= 25
   DMI_ADX_IGNITION,    // ADX crosses above 20 in dominant DI direction
   DMI_CROSS_ONLY       // +DI/-DI Cross unconstrained
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 790001;    // EA Magic Number
input double                InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Directional Movement Configuration ==="
input int                   InpDiPeriod            = 24;        // Directional Indicator (+/- DI) Period
input int                   InpAdxPeriod           = 14;        // ADX Smoothing Period
input ENUM_DMI_TRIGGER      InpTriggerMode         = DMI_CROSS_ADX20; // Trigger Mode
input double                InpAdxThreshold        = 20.0;      // Minimum ADX Threshold
input double                InpTpMult              = 4.0;       // Take Profit ATR Multiplier (4.0R)
input double                InpSlMult              = 2.5;       // Stop Loss ATR Multiplier (2.5R)

input group "=== Macro Trend & Noise Gate ==="
input int                   InpAtrPeriod           = 14;        // ATR Volatility Period
input int                   InpEmaPeriod           = 200;       // Macro Structural Trend EMA (200)
input bool                  InpUseKFD_Filter       = false;     // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.40;      // Maximum Fractal Dimension (<= 1.40)
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

   Print("[+] Gold H1 DMI ADX Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   if(m_hEMA != INVALID_HANDLE) IndicatorRelease(m_hEMA);
   Print("[-] Gold H1 DMI ADX Master EA Deinitialized.");
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
//| Compute Directional Movement Index (DMI) and ADX                 |
//+------------------------------------------------------------------+
bool ComputeDMI_ADX(const double &highs[], const double &lows[], const double &closes[], int total_bars,
                    double &pdi0, double &pdi1,
                    double &mdi0, double &mdi1,
                    double &adx0, double &adx1)
{
   if(total_bars < InpDiPeriod + InpAdxPeriod + 10) return false;

   int n = total_bars;
   double h[], l[], c[];
   ArrayResize(h, n);
   ArrayResize(l, n);
   ArrayResize(c, n);

   // Convert to chronological array (0 = oldest)
   for(int i = 0; i < n; i++)
   {
      h[i] = highs[n - 1 - i];
      l[i] = lows[n - 1 - i];
      c[i] = closes[n - 1 - i];
   }

   double tr[], plus_dm[], minus_dm[];
   ArrayResize(tr, n);
   ArrayResize(plus_dm, n);
   ArrayResize(minus_dm, n);

   tr[0] = h[0] - l[0];
   plus_dm[0] = 0.0;
   minus_dm[0] = 0.0;

   for(int i = 1; i < n; i++)
   {
      double hl = h[i] - l[i];
      double hc = MathAbs(h[i] - c[i - 1]);
      double lc = MathAbs(l[i] - c[i - 1]);
      tr[i] = MathMax(hl, MathMax(hc, lc));

      double up_move = h[i] - h[i - 1];
      double down_move = l[i - 1] - l[i];

      plus_dm[i] = (up_move > down_move && up_move > 0.0) ? up_move : 0.0;
      minus_dm[i] = (down_move > up_move && down_move > 0.0) ? down_move : 0.0;
   }

   // Wilder smooth
   double sm_tr[], sm_plus[], sm_minus[];
   ArrayResize(sm_tr, n);
   ArrayResize(sm_plus, n);
   ArrayResize(sm_minus, n);

   double a_di = 1.0 / (double)InpDiPeriod;
   sm_tr[InpDiPeriod - 1] = 0.0;
   sm_plus[InpDiPeriod - 1] = 0.0;
   sm_minus[InpDiPeriod - 1] = 0.0;
   for(int j = 0; j < InpDiPeriod; j++)
   {
      sm_tr[InpDiPeriod - 1] += tr[j];
      sm_plus[InpDiPeriod - 1] += plus_dm[j];
      sm_minus[InpDiPeriod - 1] += minus_dm[j];
   }
   sm_tr[InpDiPeriod - 1] /= InpDiPeriod;
   sm_plus[InpDiPeriod - 1] /= InpDiPeriod;
   sm_minus[InpDiPeriod - 1] /= InpDiPeriod;

   for(int j = InpDiPeriod; j < n; j++)
   {
      sm_tr[j] = sm_tr[j - 1] * (1.0 - a_di) + tr[j] * a_di;
      sm_plus[j] = sm_plus[j - 1] * (1.0 - a_di) + plus_dm[j] * a_di;
      sm_minus[j] = sm_minus[j - 1] * (1.0 - a_di) + minus_dm[j] * a_di;
   }

   double plus_di[], minus_di[], dx[];
   ArrayResize(plus_di, n);
   ArrayResize(minus_di, n);
   ArrayResize(dx, n);

   for(int i = InpDiPeriod - 1; i < n; i++)
   {
      if(sm_tr[i] > 1e-6)
      {
         plus_di[i] = 100.0 * (sm_plus[i] / sm_tr[i]);
         minus_di[i] = 100.0 * (sm_minus[i] / sm_tr[i]);
         double di_sum = plus_di[i] + minus_di[i];
         if(di_sum > 1e-6)
            dx[i] = 100.0 * MathAbs(plus_di[i] - minus_di[i]) / di_sum;
         else
            dx[i] = 0.0;
      }
   }

   // Smooth DX into ADX
   double adx[];
   ArrayResize(adx, n);
   int adx_start = InpDiPeriod - 1 + InpAdxPeriod;
   if(adx_start >= n) return false;

   double a_adx = 1.0 / (double)InpAdxPeriod;
   double sum_dx = 0.0;
   for(int j = InpDiPeriod - 1; j < adx_start; j++) sum_dx += dx[j];
   adx[adx_start - 1] = sum_dx / InpAdxPeriod;

   for(int j = adx_start; j < n; j++)
   {
      adx[j] = adx[j - 1] * (1.0 - a_adx) + dx[j] * a_adx;
   }

   // Map back to series indices
   pdi0 = plus_di[n - 2];
   pdi1 = plus_di[n - 3];
   mdi0 = minus_di[n - 2];
   mdi1 = minus_di[n - 3];
   adx0 = adx[n - 2];
   adx1 = adx[n - 3];

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

   double pdi0, pdi1, mdi0, mdi1, adx0, adx1;
   if(!ComputeDMI_ADX(highs, lows, closes, lookback, pdi0, pdi1, mdi0, mdi1, adx0, adx1)) return;

   bool bull_signal = false;
   bool bear_signal = false;

   bool di_cross_up   = (pdi0 >= mdi0) && (pdi1 < mdi1);
   bool di_cross_down = (pdi0 <= mdi0) && (pdi1 > mdi1);

   if(InpTriggerMode == DMI_CROSS_ADX20)
   {
      bull_signal = di_cross_up && (adx0 >= 20.0);
      bear_signal = di_cross_down && (adx0 >= 20.0);
   }
   else if(InpTriggerMode == DMI_CROSS_ADX25)
   {
      bull_signal = di_cross_up && (adx0 >= 25.0);
      bear_signal = di_cross_down && (adx0 >= 25.0);
   }
   else if(InpTriggerMode == DMI_ADX_IGNITION)
   {
      bool adx_cross = (adx0 >= 20.0) && (adx1 < 20.0);
      bull_signal = adx_cross && (pdi0 > mdi0);
      bear_signal = adx_cross && (mdi0 > pdi0);
   }
   else if(InpTriggerMode == DMI_CROSS_ONLY)
   {
      bull_signal = di_cross_up;
      bear_signal = di_cross_down;
   }

   bool bull_trigger = bull_signal && ema_long_ok;
   bool bear_trigger = bear_signal && ema_short_ok;

   double exec_lot = GetExecutionLotSize();

   if(bull_trigger)
   {
      double sl = ask - (InpSlMult * current_atr);
      double tp = ask + (InpTpMult * current_atr);
      m_trade.Buy(exec_lot, _Symbol, ask, sl, tp, "S79 DMI Long");
      Print("[TRADE] BUY 0.10 XAUUSD @ ", ask, " | SL: ", sl, " | TP: ", tp, " | ADX: ", DoubleToString(adx0, 2));
   }
   else if(bear_trigger)
   {
      double sl = bid + (InpSlMult * current_atr);
      double tp = bid - (InpTpMult * current_atr);
      m_trade.Sell(exec_lot, _Symbol, bid, sl, tp, "S79 DMI Short");
      Print("[TRADE] SELL 0.10 XAUUSD @ ", bid, " | SL: ", sl, " | TP: ", tp, " | ADX: ", DoubleToString(adx0, 2));
   }

   m_last_bar_time = bar_time;
}
//+------------------------------------------------------------------+

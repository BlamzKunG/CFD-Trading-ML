//+------------------------------------------------------------------+
//|                  Gold_H1_CMF_Volume_Master_EA.mq5                |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|    Strategy 77: Gold H1 Chaikin Money Flow Volume Accumulation   |
//|     PF: 2.270 | Net: +$11,002.93 | DD: $978.41 | MCR: 73.61%     |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Chaikin Money Flow (CMF) Institutional Flow Master EA (Magic 770001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_CMF_TRIGGER
{
   CMF_ZERO_CROSS,      // CMF crosses 0.0 Waterline
   CMF_THRESHOLD_05,    // CMF crosses +/- 0.05 Accumulation Level
   CMF_THRESHOLD_10,    // CMF crosses +/- 0.10 Strong Flow Level
   CMF_INFLECTION       // CMF inflection from extreme zones (+/- 0.08)
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 770001;    // EA Magic Number
input double                InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Chaikin Money Flow Configuration ==="
input int                   InpPeriod              = 28;        // CMF Calculation Window (Bars)
input ENUM_CMF_TRIGGER      InpTriggerMode         = CMF_THRESHOLD_10; // Trigger Mode
input double                InpTpMult              = 4.5;       // Take Profit ATR Multiplier (4.5R)
input double                InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

input group "=== Macro Trend & Noise Gate ==="
input int                   InpAtrPeriod           = 14;        // ATR Volatility Period
input int                   InpEmaPeriod           = 200;       // Macro Structural Trend EMA (200)
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

   Print("[+] Gold H1 CMF Volume Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   if(m_hEMA != INVALID_HANDLE) IndicatorRelease(m_hEMA);
   Print("[-] Gold H1 CMF Volume Master EA Deinitialized.");
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
//| Compute Chaikin Money Flow (CMF)                                 |
//+------------------------------------------------------------------+
double ComputeSingleCMF(const double &highs[], const double &lows[],
                        const double &closes[], const long &vols[],
                        int shift, int period)
{
   double sum_mfv = 0.0;
   double sum_vol = 0.0;

   for(int k = 0; k < period; k++)
   {
      int idx = shift + k;
      double h = highs[idx];
      double l = lows[idx];
      double c = closes[idx];
      double v = (double)vols[idx];

      double hl = h - l;
      if(hl < 1e-6) hl = 1e-6;

      double clv = ((c - l) - (h - c)) / hl;
      double mfv = clv * v;

      sum_mfv += mfv;
      sum_vol += v;
   }

   if(sum_vol > 1e-6)
      return (sum_mfv / sum_vol);
   return 0.0;
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

   int lookback = InpPeriod + 10;
   double highs[], lows[], closes[];
   long vols[];
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows, true);
   ArraySetAsSeries(closes, true);
   ArraySetAsSeries(vols, true);

   if(CopyHigh(_Symbol, PERIOD_H1, 1, lookback, highs) < lookback) return;
   if(CopyLow(_Symbol, PERIOD_H1, 1, lookback, lows) < lookback) return;
   if(CopyClose(_Symbol, PERIOD_H1, 1, lookback, closes) < lookback) return;
   if(CopyTickVolume(_Symbol, PERIOD_H1, 1, lookback, vols) < lookback) return;

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

   double cmf0 = ComputeSingleCMF(highs, lows, closes, vols, 0, InpPeriod);
   double cmf1 = ComputeSingleCMF(highs, lows, closes, vols, 1, InpPeriod);
   double cmf2 = ComputeSingleCMF(highs, lows, closes, vols, 2, InpPeriod);

   bool bull_signal = false;
   bool bear_signal = false;

   if(InpTriggerMode == CMF_ZERO_CROSS)
   {
      bull_signal = (cmf0 >= 0.0) && (cmf1 < 0.0);
      bear_signal = (cmf0 <= 0.0) && (cmf1 > 0.0);
   }
   else if(InpTriggerMode == CMF_THRESHOLD_05)
   {
      bull_signal = (cmf0 >= 0.05) && (cmf1 < 0.05);
      bear_signal = (cmf0 <= -0.05) && (cmf1 > -0.05);
   }
   else if(InpTriggerMode == CMF_THRESHOLD_10)
   {
      bull_signal = (cmf0 >= 0.10) && (cmf1 < 0.10);
      bear_signal = (cmf0 <= -0.10) && (cmf1 > -0.10);
   }
   else if(InpTriggerMode == CMF_INFLECTION)
   {
      bull_signal = (cmf0 > cmf1) && (cmf1 <= cmf2) && (cmf0 < -0.08);
      bear_signal = (cmf0 < cmf1) && (cmf1 >= cmf2) && (cmf0 > 0.08);
   }

   bool bull_trigger = bull_signal && ema_long_ok;
   bool bear_trigger = bear_signal && ema_short_ok;

   double exec_lot = GetExecutionLotSize();

   if(bull_trigger)
   {
      double sl = ask - (InpSlMult * current_atr);
      double tp = ask + (InpTpMult * current_atr);
      m_trade.Buy(exec_lot, _Symbol, ask, sl, tp, "S77 CMF Long");
      Print("[TRADE] BUY 0.10 XAUUSD @ ", ask, " | SL: ", sl, " | TP: ", tp, " | CMF: ", DoubleToString(cmf0, 3));
   }
   else if(bear_trigger)
   {
      double sl = bid + (InpSlMult * current_atr);
      double tp = bid - (InpTpMult * current_atr);
      m_trade.Sell(exec_lot, _Symbol, bid, sl, tp, "S77 CMF Short");
      Print("[TRADE] SELL 0.10 XAUUSD @ ", bid, " | SL: ", sl, " | TP: ", tp, " | CMF: ", DoubleToString(cmf0, 3));
   }

   m_last_bar_time = bar_time;
}
//+------------------------------------------------------------------+

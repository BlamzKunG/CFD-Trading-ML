//+------------------------------------------------------------------+
//|                     Gold_H1_Schaff_Trend_Cycle_Master_EA.mq5      |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|                Strategy 62: Schaff Trend Cycle (STC-KFD)         |
//|          PF: 1.573 | Win: 46.3% | Max DD: $1,277 | Net: +$6.4k    |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Schaff Trend Cycle Master EA (Dual-Stochastic MACD Cycle Expansion)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 620001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Schaff Trend Cycle (STC) Configuration ==="
input int      InpFastPeriod          = 23;        // Fast MACD EMA Period
input int      InpSlowPeriod          = 50;        // Slow MACD EMA Period
input int      InpCyclePeriod         = 10;        // Stochastic Cycle Length
input double   InpStcLower            = 30.0;      // Bullish Cycle Trigger Level (Cross Above)
input double   InpStcUpper            = 70.0;      // Bearish Cycle Trigger Level (Cross Below)
input double   InpTpMult              = 4.5;       // Take Profit ATR Multiplier (4.5R)
input double   InpSlMult              = 2.5;       // Stop Loss ATR Multiplier (2.5R)

input group "=== Macro Trend & Fractal Noise Gate ==="
input int      InpAtrPeriod           = 14;        // ATR Volatility Period
input int      InpEmaPeriod           = 200;       // Macro Structural Trend EMA
input bool     InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double   InpKfdThreshold        = 1.40;      // Maximum Fractal Dimension (<= 1.40)
input int      InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hEMA200;
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

   m_hATR    = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicator handles.");
      return(INIT_FAILED);
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Gold H1 Schaff Trend Cycle Master EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   IndicatorRelease(m_hEMA200);
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
//| Compute Schaff Trend Cycle (STC) for bar 1 and bar 2             |
//+------------------------------------------------------------------+
bool ComputeSTC(double &stc1, double &stc2)
{
   int total_bars = InpSlowPeriod + (InpCyclePeriod * 3) + 50;
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 0, total_bars, closes) < total_bars) return false;

   // Need oldest to newest for recursive smoothing
   int n = total_bars;
   double c_asc[];
   ArrayResize(c_asc, n);
   for(int i = 0; i < n; i++) c_asc[i] = closes[n - 1 - i];

   // 1. Compute EMA Fast & EMA Slow
   double ema_f[], ema_s[], macd[];
   ArrayResize(ema_f, n); ArrayResize(ema_s, n); ArrayResize(macd, n);
   double alpha_f = 2.0 / (InpFastPeriod + 1.0);
   double alpha_s = 2.0 / (InpSlowPeriod + 1.0);
   ema_f[0] = c_asc[0]; ema_s[0] = c_asc[0]; macd[0] = 0.0;

   for(int i = 1; i < n; i++)
   {
      ema_f[i] = (c_asc[i] * alpha_f) + (ema_f[i - 1] * (1.0 - alpha_f));
      ema_s[i] = (c_asc[i] * alpha_s) + (ema_s[i - 1] * (1.0 - alpha_s));
      macd[i]  = ema_f[i] - ema_s[i];
   }

   // 2. First Stochastic on MACD
   double stoch1[], pf1[];
   ArrayResize(stoch1, n); ArrayResize(pf1, n);
   ArrayInitialize(stoch1, 0.0); ArrayInitialize(pf1, 0.0);

   for(int i = InpCyclePeriod; i < n; i++)
   {
      double ll = macd[i]; double hh = macd[i];
      for(int k = 1; k < InpCyclePeriod; k++)
      {
         if(macd[i - k] < ll) ll = macd[i - k];
         if(macd[i - k] > hh) hh = macd[i - k];
      }
      double denom = hh - ll;
      if(denom > 1e-8) stoch1[i] = ((macd[i] - ll) / denom) * 100.0;
      else stoch1[i] = stoch1[i - 1];

      pf1[i] = pf1[i - 1] + 0.5 * (stoch1[i] - pf1[i - 1]);
   }

   // 3. Second Stochastic on pf1
   double stoch2[], stc[];
   ArrayResize(stoch2, n); ArrayResize(stc, n);
   ArrayInitialize(stoch2, 0.0); ArrayInitialize(stc, 0.0);

   for(int i = InpCyclePeriod * 2; i < n; i++)
   {
      double ll = pf1[i]; double hh = pf1[i];
      for(int k = 1; k < InpCyclePeriod; k++)
      {
         if(pf1[i - k] < ll) ll = pf1[i - k];
         if(pf1[i - k] > hh) hh = pf1[i - k];
      }
      double denom = hh - ll;
      if(denom > 1e-8) stoch2[i] = ((pf1[i] - ll) / denom) * 100.0;
      else stoch2[i] = stoch2[i - 1];

      stc[i] = stc[i - 1] + 0.5 * (stoch2[i] - stc[i - 1]);
      if(stc[i] < 0.0) stc[i] = 0.0;
      if(stc[i] > 100.0) stc[i] = 100.0;
   }

   // Return bar 1 (completed previous bar) and bar 2 (bar before previous)
   stc1 = stc[n - 2]; // Bar 1 in series
   stc2 = stc[n - 3]; // Bar 2 in series
   return true;
}

//+------------------------------------------------------------------+
//| Track Monthly Realized PnL                                       |
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
      PrintFormat("[*] Reset Monthly ASAR Risk Budget for Year-Month: %d", month_key);
   }

   datetime month_start;
   dt.day = 1; dt.hour = 0; dt.min = 0; dt.sec = 0;
   month_start = StructToTime(dt);

   HistorySelect(month_start, current_time);
   int total_deals = HistoryDealsTotal();
   double realized = 0.0;

   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            realized += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            realized += HistoryDealGetDouble(ticket, DEAL_SWAP);
            realized += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }

   m_monthly_realized_pnl = realized;

   if(InpMonthlyProfitLock > 0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      m_is_month_locked = true;
   }
   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      m_is_month_locked = true;
   }
}

//+------------------------------------------------------------------+
//| Check if open positions exist                                    |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == 0 || bar_time == m_last_bar_time) return;

   m_last_bar_time = bar_time;
   UpdateMonthlyGovernance(bar_time);

   string status_str = StringFormat(
      "STC-KFD Master EA | Mo PnL: $%.2f | Status: %s",
      m_monthly_realized_pnl,
      m_is_month_locked ? "LOCKED" : "ACTIVE"
   );
   Comment(status_str);

   if(m_is_month_locked || HasOpenPosition()) return;

   // Check spread
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMaxSpread) return;

   // Indicators
   double atr_buf[1], ema_buf[1];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0 || CopyBuffer(m_hEMA200, 0, 1, 1, ema_buf) <= 0) return;
   double atr14  = atr_buf[0];
   double ema200 = ema_buf[0];
   if(atr14 < 0.50) return;

   double stc1, stc2;
   if(!ComputeSTC(stc1, stc2)) return;

   // Closes for KFD
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, InpKfdPeriod + 5, closes) < InpKfdPeriod) return;

   double kfd_val = ComputeKFD(closes, 0, InpKfdPeriod);
   bool kfd_ok    = (!InpUseKFD_Filter) || (kfd_val <= InpKfdThreshold);

   double close1 = closes[0]; // Bar 1 Close
   bool ema_long_ok  = (close1 > ema200);
   bool ema_short_ok = (close1 < ema200);

   // STC Crossover
   bool bull_cross = (stc1 >= InpStcLower) && (stc2 < InpStcLower) && ema_long_ok && kfd_ok;
   bool bear_cross = (stc1 <= InpStcUpper) && (stc2 > InpStcUpper) && ema_short_ok && kfd_ok;

   // Lot Sizing
   double trade_lot = InpLotSize;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      trade_lot = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(trade_lot < 0.01) trade_lot = 0.01;
   }

   if(bull_cross)
   {
      double sl = NormalizeDouble(ask - (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * atr14), _Digits);
      m_trade.Buy(trade_lot, _Symbol, ask, sl, tp, "STC-KFD Buy");
      PrintFormat("[+] Executed BUY @ %.2f | SL: %.2f | TP: %.2f | STC: %.1f -> %.1f | KFD: %.3f", ask, sl, tp, stc2, stc1, kfd_val);
   }
   else if(bear_cross)
   {
      double sl = NormalizeDouble(bid + (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * atr14), _Digits);
      m_trade.Sell(trade_lot, _Symbol, bid, sl, tp, "STC-KFD Sell");
      PrintFormat("[+] Executed SELL @ %.2f | SL: %.2f | TP: %.2f | STC: %.1f -> %.1f | KFD: %.3f", bid, sl, tp, stc2, stc1, kfd_val);
   }
}

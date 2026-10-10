//+------------------------------------------------------------------+
//|                 Gold_H1_Chande_Kroll_Stop_Master_EA.mq5           |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|              Strategy 65: Chande Kroll Stop (CKS-KFD)            |
//|          PF: 1.337 | Win: 41.2% | Max DD: $866 | Net: +$4.1k     |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Chande Kroll Stop Master EA (Double-Smoothed Volatility Breakout)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 650001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Chande Kroll Stop Configuration ==="
input int      InpP_Period            = 14;        // Primary Lookback Period (P)
input double   InpCksMult             = 2.5;       // ATR Volatility Multiplier
input int      InpQ_Period            = 20;        // Secondary Smoothing Period (Q)
input double   InpTpMult              = 5.0;       // Take Profit ATR Multiplier (5.0R)
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

   Print("[+] Gold H1 Chande Kroll Stop Master EA Initialized Successfully.");
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
//| Compute Chande Kroll Stop for bar 1 and bar 2                    |
//+------------------------------------------------------------------+
bool ComputeCKS(double &stopLong1, double &stopShort1, double &stopLong2, double &stopShort2)
{
   int total_bars = InpP_Period + InpQ_Period + 20;
   double highs[], lows[], atr[];
   ArraySetAsSeries(highs, true); ArraySetAsSeries(lows, true); ArraySetAsSeries(atr, true);

   if(CopyHigh(_Symbol, PERIOD_H1, 0, total_bars, highs) < total_bars ||
      CopyLow(_Symbol, PERIOD_H1, 0, total_bars, lows) < total_bars ||
      CopyBuffer(m_hATR, 0, 0, total_bars, atr) < total_bars) return false;

   int n = total_bars;
   double hs1[], ls1[];
   ArrayResize(hs1, n); ArrayResize(ls1, n);

   // Stage 1
   for(int i = 0; i <= n - InpP_Period; i++)
   {
      double hh = highs[i];
      double ll = lows[i];
      for(int k = 1; k < InpP_Period; k++)
      {
         if(highs[i + k] > hh) hh = highs[i + k];
         if(lows[i + k] < ll) ll = lows[i + k];
      }
      hs1[i] = hh - (atr[i] * InpCksMult);
      ls1[i] = ll + (atr[i] * InpCksMult);
   }

   // Stage 2
   double sl1 = hs1[1]; double ss1 = ls1[1];
   for(int k = 2; k < 1 + InpQ_Period; k++)
   {
      if(hs1[k] > sl1) sl1 = hs1[k];
      if(ls1[k] < ss1) ss1 = ls1[k];
   }

   double sl2 = hs1[2]; double ss2 = ls1[2];
   for(int k = 3; k < 2 + InpQ_Period; k++)
   {
      if(hs1[k] > sl2) sl2 = hs1[k];
      if(ls1[k] < ss2) ss2 = ls1[k];
   }

   stopLong1  = sl1; stopShort1 = ss1;
   stopLong2  = sl2; stopShort2 = ss2;
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
      m_is_month_locked = true;
   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
      m_is_month_locked = true;
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
      "CKS-KFD Master EA | Mo PnL: $%.2f | Status: %s",
      m_monthly_realized_pnl,
      m_is_month_locked ? "LOCKED" : "ACTIVE"
   );
   Comment(status_str);

   if(m_is_month_locked || HasOpenPosition()) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMaxSpread) return;

   double atr_buf[1], ema_buf[1];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0 || CopyBuffer(m_hEMA200, 0, 1, 1, ema_buf) <= 0) return;
   double atr14  = atr_buf[0];
   double ema200 = ema_buf[0];
   if(atr14 < 0.50) return;

   double sl1, ss1, sl2, ss2;
   if(!ComputeCKS(sl1, ss1, sl2, ss2)) return;

   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, InpKfdPeriod + 5, closes) < InpKfdPeriod) return;

   double kfd_val = ComputeKFD(closes, 0, InpKfdPeriod);
   bool kfd_ok    = (!InpUseKFD_Filter) || (kfd_val <= InpKfdThreshold);

   double close1 = closes[0]; // Bar 1 Close
   double close2 = closes[1]; // Bar 2 Close
   bool ema_long_ok  = (close1 > ema200);
   bool ema_short_ok = (close1 < ema200);

   // Breakout Signals
   bool bull_break = (close1 > sl1) && (close2 <= sl2) && ema_long_ok && kfd_ok;
   bool bear_break = (close1 < ss1) && (close2 >= ss2) && ema_short_ok && kfd_ok;

   double trade_lot = InpLotSize;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      trade_lot = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(trade_lot < 0.01) trade_lot = 0.01;
   }

   if(bull_break)
   {
      double sl = NormalizeDouble(ask - (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * atr14), _Digits);
      m_trade.Buy(trade_lot, _Symbol, ask, sl, tp, "CKS-KFD Buy");
      PrintFormat("[+] Executed BUY @ %.2f | SL: %.2f | TP: %.2f | StopLong: %.2f | KFD: %.3f", ask, sl, tp, sl1, kfd_val);
   }
   else if(bear_break)
   {
      double sl = NormalizeDouble(bid + (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * atr14), _Digits);
      m_trade.Sell(trade_lot, _Symbol, bid, sl, tp, "CKS-KFD Sell");
      PrintFormat("[+] Executed SELL @ %.2f | SL: %.2f | TP: %.2f | StopShort: %.2f | KFD: %.3f", bid, sl, tp, ss1, kfd_val);
   }
}

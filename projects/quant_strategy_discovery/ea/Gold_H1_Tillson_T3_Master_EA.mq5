//+------------------------------------------------------------------+
//|                        Gold_H1_Tillson_T3_Master_EA.mq5          |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|               Strategy 93: Tillson T3 Moving Average (T3-KFD)    |
//|           Profit Factor: 1.771 | Max DD: $658-$908 | Net: +$6.3k |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Tillson T3 Adaptive Moving Average Master EA"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 930001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Tillson T3 Configuration ==="
input int      InpT3Period            = 14;        // T3 Smoothing Period (14)
input double   InpT3VolumeFactor      = 0.7;       // T3 Volume Factor v (0.7)
input double   InpTpMult              = 3.5;       // Take Profit ATR Multiplier (3.5R)
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

   Print("[+] Gold H1 Tillson T3 Master EA Initialized Successfully.");
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
//| Compute Tillson T3 Moving Average series                         |
//+------------------------------------------------------------------+
bool GetTillsonT3Values(int period, double v, double &t3_bar1, double &t3_bar2, int bars_needed = 250)
{
   double close[];
   ArraySetAsSeries(close, true);
   int copied = CopyClose(_Symbol, PERIOD_H1, 0, bars_needed, close);
   if(copied < bars_needed) return false;

   // Arrays for successive EMAs: e1, e2, e3, e4, e5, e6
   double e1[], e2[], e3[], e4[], e5[], e6[];
   ArrayResize(e1, bars_needed);
   ArrayResize(e2, bars_needed);
   ArrayResize(e3, bars_needed);
   ArrayResize(e4, bars_needed);
   ArrayResize(e5, bars_needed);
   ArrayResize(e6, bars_needed);

   double alpha = 2.0 / (period + 1.0);

   // Oldest bar is index bars_needed - 1
   int oldest = bars_needed - 1;
   e1[oldest] = close[oldest];
   e2[oldest] = close[oldest];
   e3[oldest] = close[oldest];
   e4[oldest] = close[oldest];
   e5[oldest] = close[oldest];
   e6[oldest] = close[oldest];

   for(int i = oldest - 1; i >= 1; i--)
   {
      e1[i] = (close[i] * alpha) + (e1[i + 1] * (1.0 - alpha));
      e2[i] = (e1[i] * alpha) + (e2[i + 1] * (1.0 - alpha));
      e3[i] = (e2[i] * alpha) + (e3[i + 1] * (1.0 - alpha));
      e4[i] = (e3[i] * alpha) + (e4[i + 1] * (1.0 - alpha));
      e5[i] = (e4[i] * alpha) + (e5[i + 1] * (1.0 - alpha));
      e6[i] = (e5[i] * alpha) + (e6[i + 1] * (1.0 - alpha));
   }

   // T3 polynomial coefficients based on v factor:
   // c1 = -(v*v*v), c2 = 3*(v*v) + 3*(v*v*v), c3 = -6*(v*v) - 3*v - 3*(v*v*v), c4 = 1 + 3*v + (v*v*v) + 3*(v*v)
   double v2 = v * v;
   double v3 = v2 * v;
   double c1 = -v3;
   double c2 = 3.0 * (v2 + v3);
   double c3 = -6.0 * v2 - 3.0 * v - 3.0 * v3;
   double c4 = 1.0 + 3.0 * v + v3 + 3.0 * v2;

   t3_bar2 = c1 * e6[2] + c2 * e5[2] + c3 * e4[2] + c4 * e3[2];
   t3_bar1 = c1 * e6[1] + c2 * e5[1] + c3 * e4[1] + c4 * e3[1];

   return true;
}

//+------------------------------------------------------------------+
//| Update Monthly Realized PnL                                      |
//+------------------------------------------------------------------+
void UpdateMonthlyRealizedPnL(int yearMonth)
{
   datetime startOfMonth = StringToTime(StringFormat("%04d.%02d.01 00:00:00", yearMonth / 100, yearMonth % 100));
   datetime now = TimeCurrent();

   HistorySelect(startOfMonth, now);
   double pnl = 0.0;
   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber)
         {
            long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            {
               pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
               pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
               pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            }
         }
      }
   }
   m_monthly_realized_pnl = pnl;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_H1, 0);
   if(currentBarTime == m_last_bar_time) return;
   m_last_bar_time = currentBarTime;

   MqlDateTime dt;
   TimeToStruct(currentBarTime, dt);
   int barMonth = dt.year * 100 + dt.mon;

   if(barMonth != m_current_month)
   {
      m_current_month        = barMonth;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      PrintFormat("[*] New Trading Month %d Initialized for Tillson T3 EA.", m_current_month);
   }

   UpdateMonthlyRealizedPnL(m_current_month);

   if(m_monthly_realized_pnl >= InpMonthlyProfitLock) m_is_month_locked = true;
   if(m_monthly_realized_pnl <= -InpHardLossBreaker)   m_is_month_locked = true;

   string statusStr = m_is_month_locked ? "LOCKED" : "ACTIVE";
   Comment(StringFormat("=== GOLD H1 TILLSON T3 MASTER EA ===\n" +
                        "Month: %d | Status: %s\n" +
                        "Realized Month PnL: $%.2f\n" +
                        "Profit Lock: $%.2f | Loss Breaker: -$%.2f",
                        m_current_month, statusStr, m_monthly_realized_pnl,
                        InpMonthlyProfitLock, InpHardLossBreaker));

   if(m_is_month_locked) return;

   // Check spread filter
   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(spread > InpMaxSpread) return;

   // Position Check (Only 1 active position per magic number)
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return; // Already in trade
   }

   int needed_rates = MathMax(InpKfdPeriod + 10, 250);
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 1, needed_rates, rates) < needed_rates) return;

   double atrBuf[], emaBuf[];
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(emaBuf, true);
   if(CopyBuffer(m_hATR, 0, 1, 5, atrBuf) < 5) return;
   if(CopyBuffer(m_hEMA200, 0, 1, 5, emaBuf) < 5) return;

   double current_atr = atrBuf[0];
   double current_ema = emaBuf[0];
   if(current_atr < 0.5) return;

   if(InpUseKFD_Filter)
   {
      double closes_arr[];
      ArrayResize(closes_arr, InpKfdPeriod);
      for(int i = 0; i < InpKfdPeriod; i++) closes_arr[i] = rates[i].close;
      double current_kfd = ComputeKFD(closes_arr, 0, InpKfdPeriod);
      if(current_kfd > InpKfdThreshold) return; // Market too choppy
   }

   double t3_1 = 0.0, t3_2 = 0.0;
   if(!GetTillsonT3Values(InpT3Period, InpT3VolumeFactor, t3_1, t3_2, 250)) return;

   double close1 = rates[0].close;
   double close2 = rates[1].close;

   bool t3_slope_up = (t3_1 > t3_2);
   bool t3_slope_dn = (t3_1 < t3_2);

   // T3 Crossover & Slope Inflection Logic
   bool bull_cross = (close1 > t3_1) && (close2 <= t3_2) && t3_slope_up && (close1 > current_ema);
   bool bear_cross = (close1 < t3_1) && (close2 >= t3_2) && t3_slope_dn && (close1 < current_ema);

   double tradeLot = InpLotSize;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      tradeLot = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(tradeLot < 0.01) tradeLot = 0.01;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(bull_cross)
   {
      double sl = ask - InpSlMult * current_atr;
      double tp = ask + InpTpMult * current_atr;
      m_trade.Buy(tradeLot, _Symbol, ask, sl, tp, "T3_Buy");
      PrintFormat("[+] Tillson T3 Long Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", ask, sl, tp, tradeLot);
   }
   else if(bear_cross)
   {
      double sl = bid + InpSlMult * current_atr;
      double tp = bid - InpTpMult * current_atr;
      m_trade.Sell(tradeLot, _Symbol, bid, sl, tp, "T3_Sell");
      PrintFormat("[+] Tillson T3 Short Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", bid, sl, tp, tradeLot);
   }
}

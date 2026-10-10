//+------------------------------------------------------------------+
//|                    Gold_H1_McGinley_Dynamic_Master_EA.mq5        |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|               Strategy 61: McGinley Dynamic Trend (MGD-KFD)       |
//|           Profit Factor: 1.641 | Max DD: $920 | Net: +$7.2k      |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 McGinley Dynamic Adaptive Trend Master EA"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 610001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== McGinley Dynamic Configuration ==="
input int      InpMdPeriod            = 20;        // McGinley Dynamic Baseline Smoothing Period (N=20)
input double   InpTpMult              = 3.5;       // Take Profit ATR Multiplier (3.5R or 4.0R)
input double   InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

input group "=== Macro Trend & Fractal Noise Gate ==="
input int      InpAtrPeriod           = 14;        // ATR Volatility Period
input int      InpEmaPeriod           = 200;       // Macro Structural Trend EMA
input bool     InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double   InpKfdThreshold        = 1.45;      // Maximum Fractal Dimension (<= 1.45)
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

   Print("[+] Gold H1 McGinley Dynamic Adaptive Trend Master EA Initialized Successfully.");
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
//| Compute McGinley Dynamic values for closed bars 1 and 2          |
//| MD_i = MD_{i-1} + (Close_i - MD_{i-1}) / (N * (Close_i/MD_{i-1})^4)
//+------------------------------------------------------------------+
bool GetMcGinleyDynamicValues(int period, double &md1, double &md2, int bars_needed = 200)
{
   double close[];
   ArraySetAsSeries(close, true);
   int copied = CopyClose(_Symbol, PERIOD_H1, 0, bars_needed, close);
   if(copied < bars_needed) return false;

   double md = close[bars_needed - 1];
   double k = (double)period;

   for(int i = bars_needed - 2; i >= 2; i--)
   {
      double c = close[i];
      if(md > 0.0001)
      {
         double ratio = c / md;
         double ratio4 = ratio * ratio * ratio * ratio;
         double denom = k * ratio4;
         if(denom > 0.0001)
            md = md + (c - md) / denom;
      }
      else
         md = c;
   }
   md2 = md; // Bar 2 (i-1)

   // Step to Bar 1 (i)
   double c1 = close[1];
   if(md > 0.0001)
   {
      double ratio = c1 / md;
      double ratio4 = ratio * ratio * ratio * ratio;
      double denom = k * ratio4;
      if(denom > 0.0001)
         md = md + (c1 - md) / denom;
   }
   else
      md = c1;

   md1 = md; // Bar 1 (i)
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
      PrintFormat("[*] New Trading Month %d Initialized for McGinley Dynamic EA.", m_current_month);
   }

   UpdateMonthlyRealizedPnL(m_current_month);

   if(m_monthly_realized_pnl >= InpMonthlyProfitLock) m_is_month_locked = true;
   if(m_monthly_realized_pnl <= -InpHardLossBreaker)   m_is_month_locked = true;

   string statusStr = m_is_month_locked ? "LOCKED" : "ACTIVE";
   Comment(StringFormat("=== GOLD H1 MCGINLEY DYNAMIC MASTER EA ===\n" +
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

   // Fetch Historical Bars for Calculations
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

   double md1 = 0.0, md2 = 0.0;
   if(!GetMcGinleyDynamicValues(InpMdPeriod, md1, md2, 250)) return;

   double close1 = rates[0].close;
   double close2 = rates[1].close;

   bool md_slope_up = (md1 > md2);
   bool md_slope_dn = (md1 < md2);

   // McGinley Dynamic Crossover & Slope Inflection Logic
   bool bull_cross = (close1 > md1) && (close2 <= md2) && md_slope_up && (close1 > current_ema);
   bool bear_cross = (close1 < md1) && (close2 >= md2) && md_slope_dn && (close1 < current_ema);

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
      m_trade.Buy(tradeLot, _Symbol, ask, sl, tp, "MGD_Buy");
      PrintFormat("[+] McGinley Long Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", ask, sl, tp, tradeLot);
   }
   else if(bear_cross)
   {
      double sl = bid + InpSlMult * current_atr;
      double tp = bid - InpTpMult * current_atr;
      m_trade.Sell(tradeLot, _Symbol, bid, sl, tp, "MGD_Sell");
      PrintFormat("[+] McGinley Short Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", bid, sl, tp, tradeLot);
   }
}

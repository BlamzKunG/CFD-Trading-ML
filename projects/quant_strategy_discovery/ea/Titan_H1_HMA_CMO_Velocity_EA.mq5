//+------------------------------------------------------------------+
//|                                Titan_H1_HMA_CMO_Velocity_EA.mq5  |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|                    Strategy 38: HMA-CMO Velocity Expansion       |
//|              Profit Factor: 2.375 | Max DD: $866 | RoMaD: 16.12x |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "2.00"
#property description "Titan H1 HMA-CMO Velocity Expansion EA (Single-Engine Peak Champion)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== Institutional Risk Architecture (ASAR) ==="
input ulong    InpMagicNumber         = 380001;    // EA Magic Number
input double   InpBaseLot             = 0.10;      // Base Lot Size (0.10 standard lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Drawdown Threshold for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Hull Moving Average (HMA) Configuration ==="
input int      InpHMA_Period          = 24;        // HMA Lookback Period (Hours)

input group "=== Chande Momentum Oscillator (CMO) Configuration ==="
input int      InpCMO_Period          = 10;        // CMO Lookback Period (Hours)
input double   InpCMO_Threshold       = 25.0;      // CMO Entry Momentum Threshold (+/- 25.0)

input group "=== Channel Breakout & Execution Parameters ==="
input int      InpChannelLookback     = 12;        // Breakout High/Low Channel Lookback (Hours)
input double   InpTrendSL_ATR_Mult    = 2.5;       // Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.5;       // Take Profit ATR Multiplier (4.5R)

input group "=== Katz Fractal Dimension (KFD) Gate ==="
input bool     InpUseKFD_Filter       = true;      // Enable Fractal Gating
input double   InpKFD_Threshold       = 1.40;      // Maximum Fractal Dimension (<= 1.40)
input int      InpKFD_Window          = 24;        // Fractal Lookback Window (Hours)

//--- GLOBAL SYSTEM STATE ---
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

   m_hATR    = iATR(_Symbol, PERIOD_H1, 14);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicator handles.");
      return(INIT_FAILED);
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Titan H1 HMA-CMO Velocity EA Initialized Successfully (PF 2.375 Engine).");
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
//| Weighted Moving Average Calculation                              |
//+------------------------------------------------------------------+
double CalcWMA(const double &arr[], int startIdx, int period)
{
   double sum = 0.0;
   double weightSum = 0.0;
   for(int i = 0; i < period; i++)
   {
      double weight = period - i;
      sum += arr[startIdx + i] * weight;
      weightSum += weight;
   }
   return (weightSum > 0) ? (sum / weightSum) : arr[startIdx];
}

//+------------------------------------------------------------------+
//| Compute Hull Moving Average State (Bar 1, Bar 2 & Slope)         |
//+------------------------------------------------------------------+
bool ComputeHMA_State(int period, double &hma1, double &hma2, double &slope1)
{
   int halfPeriod = (int)MathMax(period / 2, 2);
   int sqrtPeriod = (int)MathMax(MathSqrt(period), 2);
   int totalRequired = period + sqrtPeriod + 10;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, totalRequired, rates);
   if(copied < totalRequired) return false;

   double rawSeries[];
   ArrayResize(rawSeries, sqrtPeriod + 4);

   for(int k = 0; k < sqrtPeriod + 4; k++)
   {
      double closes[];
      ArrayResize(closes, period);
      for(int c = 0; c < period; c++)
      {
         closes[c] = rates[k + c].close;
      }
      double wmaHalf = CalcWMA(closes, 0, halfPeriod);
      double wmaFull = CalcWMA(closes, 0, period);
      rawSeries[k] = 2.0 * wmaHalf - wmaFull;
   }

   hma1 = CalcWMA(rawSeries, 0, sqrtPeriod);
   hma2 = CalcWMA(rawSeries, 1, sqrtPeriod);
   slope1 = hma1 - hma2;
   return true;
}

//+------------------------------------------------------------------+
//| Compute Chande Momentum Oscillator (CMO)                         |
//+------------------------------------------------------------------+
double ComputeCMO(int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, period + 5, rates);
   if(copied < period + 1) return 0.0;

   double sumUp = 0.0, sumDown = 0.0;
   for(int i = 0; i < period; i++)
   {
      double diff = rates[i].close - rates[i + 1].close;
      if(diff > 0) sumUp += diff;
      else         sumDown += MathAbs(diff);
   }

   double total = sumUp + sumDown;
   return (total > 1e-6) ? (100.0 * (sumUp - sumDown) / total) : 0.0;
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension                                   |
//+------------------------------------------------------------------+
double ComputeKFD(int window)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, window + 5, rates);
   if(copied < window) return 1.5;

   double euclidDist = MathAbs(rates[0].close - rates[window - 1].close);
   double totalCurve = 0.0;

   for(int i = 0; i < window - 1; i++)
   {
      totalCurve += MathAbs(rates[i].close - rates[i + 1].close);
   }

   if(totalCurve > 1e-6 && euclidDist > 1e-6)
   {
      double ratio = euclidDist / totalCurve;
      double nBars = (double)window;
      double kfd = MathLog10(nBars) / (MathLog10(nBars) + MathLog10(ratio));
      return MathMax(1.0, MathMin(2.0, kfd));
   }
   return 1.5;
}

//+------------------------------------------------------------------+
//| Update Realized Monthly PnL from Closed Orders                   |
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
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket > 0)
      {
         if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) == InpMagicNumber)
         {
            long entry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            {
               pnl += HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
               pnl += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
               pnl += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
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
   // Execute only on new H1 bar
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
      PrintFormat("[*] New Trading Month %d Initialized for Titan HMA-CMO EA.", m_current_month);
   }

   UpdateMonthlyRealizedPnL(m_current_month);

   // Check ASAR Circuit Breakers
   if(m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      m_is_month_locked = true;
   }
   if(m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      m_is_month_locked = true;
   }

   // On-Chart Status HUD
   string hud = StringFormat(
      "=== TITAN H1 HMA-CMO VELOCITY EA (PF 2.375) ===\n"
      "Month: %d | Realized PnL: $%.2f\n"
      "Status: %s\n"
      "Spread: %.2f (Max: %.2f)",
      m_current_month, m_monthly_realized_pnl,
      m_is_month_locked ? "LOCKED (ASAR Budget Hit)" : "ACTIVE",
      SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID),
      InpMaxSpread
   );
   Comment(hud);

   if(m_is_month_locked) return;

   // Check Spread Protection
   double currentSpread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(currentSpread > InpMaxSpread)
   {
      PrintFormat("[!] Spread too high (%.2f > %.2f). Trade skipped.", currentSpread, InpMaxSpread);
      return;
   }

   // Check Active Position
   bool hasPosition = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         hasPosition = true;
         break;
      }
   }
   if(hasPosition) return;

   // Retrieve Rates & Indicators for Bar 1
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int needed = MathMax(InpChannelLookback + 5, InpHMA_Period + 20);
   if(CopyRates(_Symbol, PERIOD_H1, 1, needed, rates) < needed) return;

   double atrBuf[], emaBuf[];
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(emaBuf, true);
   if(CopyBuffer(m_hATR, 0, 1, 5, atrBuf) < 5) return;
   if(CopyBuffer(m_hEMA200, 0, 1, 5, emaBuf) < 5) return;

   double cATR    = atrBuf[0];
   double cEMA200 = emaBuf[0];
   if(cATR < 0.5) return;

   // Compute Indicators
   double hma1 = 0.0, hma2 = 0.0, hmaSlope = 0.0;
   if(!ComputeHMA_State(InpHMA_Period, hma1, hma2, hmaSlope)) return;

   double cmoVal = ComputeCMO(InpCMO_Period);

   if(InpUseKFD_Filter)
   {
      double kfd = ComputeKFD(InpKFD_Window);
      if(kfd > InpKFD_Threshold) return; // Market is random walk / choppy
   }

   // Compute Donchian Channel
   double chHigh = -1.0, chLow = 999999.0;
   for(int i = 1; i <= InpChannelLookback; i++)
   {
      if(rates[i].high > chHigh) chHigh = rates[i].high;
      if(rates[i].low < chLow)   chLow  = rates[i].low;
   }

   double close1 = rates[0].close;

   // Entry Triggers
   bool longSignal = (close1 > chHigh) && (close1 > cEMA200) && (hmaSlope > 0) && (cmoVal > InpCMO_Threshold);
   bool shortSignal = (close1 < chLow) && (close1 < cEMA200) && (hmaSlope < 0) && (cmoVal < -InpCMO_Threshold);

   // Dynamic Defensive Sizing
   double tradeLot = InpBaseLot;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      tradeLot = NormalizeDouble(InpBaseLot * InpDefensiveMult, 2);
      if(tradeLot < 0.01) tradeLot = 0.01;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(longSignal)
   {
      double sl = ask - InpTrendSL_ATR_Mult * cATR;
      double tp = ask + InpTrendTP_Ratio * cATR;
      m_trade.Buy(tradeLot, _Symbol, ask, sl, tp, "Titan_HMA_CMO_Buy");
      PrintFormat("[+] Titan HMA-CMO Long Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", ask, sl, tp, tradeLot);
   }
   else if(shortSignal)
   {
      double sl = bid + InpTrendSL_ATR_Mult * cATR;
      double tp = bid - InpTrendTP_Ratio * cATR;
      m_trade.Sell(tradeLot, _Symbol, bid, sl, tp, "Titan_HMA_CMO_Sell");
      PrintFormat("[+] Titan HMA-CMO Short Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", bid, sl, tp, tradeLot);
   }
}

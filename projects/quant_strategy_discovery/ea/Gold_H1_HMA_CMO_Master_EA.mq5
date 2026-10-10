//+------------------------------------------------------------------+
//|                                     Gold_H1_HMA_CMO_Master_EA.mq5|
//|                                  Copyright 2026, Quant CFD Lab   |
//|            Strategy 38: HMA-CMO Velocity Expansion Master EA     |
//|                             Target Profit Factor >= 1.50+ (PF 2.37)|
//+------------------------------------------------------------------+
#property copyright "Quant CFD Lab"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 HMA-CMO Velocity Expansion Master EA (PF 2.375, DD $866)"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input double   InpBaseLot             = 0.10;     // Base Lot Size (0.10 = 10.0 oz Gold)
input double   InpMonthlyProfitLock   = 200.0;    // Monthly Profit Target Lock (USD)
input double   InpHardLossBreaker     = 250.0;    // Hard Monthly Loss Circuit Breaker (USD)
input double   InpDefensiveThresh     = 120.0;    // Monthly Loss Threshold for Defensive Sizing (USD)
input double   InpDefensiveMult       = 0.25;     // Defensive Lot Multiplier (0.25 = 0.025 lot)
input ulong    InpMagicNumber         = 383838;   // EA Magic Number

input group "=== Hull Moving Average Parameters ==="
input int      InpHMA_Period          = 24;       // HMA Lookback Period (24 hours)

input group "=== Chande Momentum Oscillator Parameters ==="
input int      InpCMO_Period          = 10;       // CMO Lookback Period (10 hours)
input double   InpCMO_Threshold       = 25.0;     // CMO Entry Threshold (+/- 25.0)

input group "=== Channel Breakout & Execution ==="
input int      InpChannelLookback     = 12;       // Channel Lookback (12 hours)
input double   InpTrendSL_ATR_Mult    = 2.5;      // Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.5;      // Take Profit R:R Ratio (4.5R)

input group "=== Katz Fractal Horizon Gate ==="
input bool     InpUseKFD_Filter       = true;     // Enable Fractal Gate
input double   InpKFD_Threshold       = 1.40;     // Maximum Fractal Dimension (<= 1.40)
input int      InpKFD_Window          = 24;       // Lookback Bars for KFD (24 hours)

//--- INDICATOR HANDLES & STATE ---
int hATR, hEMA200;
datetime lastBarTime = 0;
int currentMonth = -1;
double monthlyRealizedPnL = 0.0;
bool isMonthLocked = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();

   hATR    = iATR(_Symbol, PERIOD_H1, 14);
   hEMA200 = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(hATR == INVALID_HANDLE || hEMA200 == INVALID_HANDLE) {
      Print("[-] Error initializing indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] Gold H1 HMA-CMO Master EA Initialized Successfully (PF 2.375 Engine).");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   IndicatorRelease(hATR);
   IndicatorRelease(hEMA200);
}

//+------------------------------------------------------------------+
//| Compute WMA Helper                                               |
//+------------------------------------------------------------------+
double CalcWMA(const double &arr[], int startIdx, int period) {
   double sum = 0.0;
   double weightSum = 0.0;
   for(int i = 0; i < period; i++) {
      double weight = period - i;
      sum += arr[startIdx + i] * weight;
      weightSum += weight;
   }
   return (weightSum > 0) ? (sum / weightSum) : arr[startIdx];
}

//+------------------------------------------------------------------+
//| Compute HMA for Bar 1 and Bar 2                                  |
//+------------------------------------------------------------------+
bool ComputeHMA_State(int period, double &hma1, double &hma2, double &slope1) {
   int halfPeriod = (int)MathMax(period / 2, 2);
   int sqrtPeriod = (int)MathMax(MathSqrt(period), 2);
   int totalRequired = period + sqrtPeriod + 10;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, totalRequired, rates);
   if(copied < totalRequired) return false;

   double closes[];
   ArrayResize(closes, copied);
   for(int i = 0; i < copied; i++) closes[i] = rates[i].close;

   double diffSeries[];
   int diffCount = copied - period;
   ArrayResize(diffSeries, diffCount);

   for(int i = 0; i < diffCount; i++) {
      double wmaHalf = CalcWMA(closes, i, halfPeriod);
      double wmaFull = CalcWMA(closes, i, period);
      diffSeries[i] = 2.0 * wmaHalf - wmaFull;
   }

   hma1 = CalcWMA(diffSeries, 0, sqrtPeriod);
   hma2 = CalcWMA(diffSeries, 1, sqrtPeriod);
   slope1 = hma1 - hma2;
   return true;
}

//+------------------------------------------------------------------+
//| Compute Chande Momentum Oscillator (CMO)                         |
//+------------------------------------------------------------------+
double ComputeCMO(int period) {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, period + 2, rates);
   if(copied < period + 2) return 0.0;

   double sumUp = 0.0;
   double sumDown = 0.0;

   for(int i = 0; i < period; i++) {
      double diff = rates[i].close - rates[i + 1].close;
      if(diff > 0) sumUp += diff;
      else if(diff < 0) sumDown += MathAbs(diff);
   }

   double total = sumUp + sumDown;
   return (total > 0.00001) ? (100.0 * (sumUp - sumDown) / total) : 0.0;
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension                                   |
//+------------------------------------------------------------------+
double ComputeKFD(int window, double atrVal) {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, window + 1, rates);
   if(copied < window + 1) return 1.5;

   double L = 0.0;
   double minP = rates[0].close;
   double maxP = rates[0].close;

   for(int i = 0; i < window; i++) {
      L += MathAbs(rates[i].close - rates[i + 1].close);
      if(rates[i].close < minP) minP = rates[i].close;
      if(rates[i].close > maxP) maxP = rates[i].close;
   }

   double d = maxP - minP;
   if(d <= 0.0001) d = 0.0001;
   double c_atr = (atrVal > 0.1) ? atrVal : 0.1;

   double L_norm = MathMax(L / c_atr, 1.01);
   double d_norm = MathMax(d / c_atr, 1.01);

   double kfd = MathLog10(L_norm) / MathLog10(d_norm);
   if(kfd < 1.0) kfd = 1.0;
   if(kfd > 2.0) kfd = 2.0;
   return kfd;
}

//+------------------------------------------------------------------+
//| Update Calendar Month PnL & ASAR Circuit Breakers                |
//+------------------------------------------------------------------+
void UpdateMonthlyRiskState() {
   MqlDateTime dt;
   TimeCurrent(dt);
   int mKey = dt.year * 100 + dt.mon;

   if(mKey != currentMonth) {
      currentMonth = mKey;
      monthlyRealizedPnL = 0.0;
      isMonthLocked = false;
      PrintFormat("[CALENDAR] Reset ASAR Risk Budget for Month: %d", currentMonth);
   }

   datetime startOfMonth = StringToTime(StringFormat("%04d.%02d.01 00:00", dt.year, dt.mon));
   HistorySelect(startOfMonth, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   double cumPnL = 0.0;

   for(int i = 0; i < totalDeals; i++) {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket > 0) {
         long magic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
         if(magic == InpMagicNumber) {
            cumPnL += HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
            cumPnL += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
            cumPnL += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
         }
      }
   }
   monthlyRealizedPnL = cumPnL;

   if(InpMonthlyProfitLock > 0 && monthlyRealizedPnL >= InpMonthlyProfitLock) {
      if(!isMonthLocked) {
         PrintFormat("[ASAR LOCK] Target +$%.2f reached. Locking Month %d.", monthlyRealizedPnL, currentMonth);
         isMonthLocked = true;
      }
   }
   else if(InpHardLossBreaker > 0 && monthlyRealizedPnL <= -InpHardLossBreaker) {
      if(!isMonthLocked) {
         PrintFormat("[ASAR BREAKER] Loss -$%.2f reached. Halting Month %d.", monthlyRealizedPnL, currentMonth);
         isMonthLocked = true;
      }
   }
}

//+------------------------------------------------------------------+
//| Dynamic Position Sizing (ASAR Defensive Scaler)                  |
//+------------------------------------------------------------------+
double GetActiveLotSize() {
   if(InpDefensiveThresh > 0 && monthlyRealizedPnL <= -InpDefensiveThresh) {
      double defLot = InpBaseLot * InpDefensiveMult;
      return MathMax(0.01, NormalizeDouble(defLot, 2));
   }
   return InpBaseLot;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
   datetime currentBar = iTime(_Symbol, PERIOD_H1, 0);
   if(currentBar == lastBarTime) return;
   lastBarTime = currentBar;

   UpdateMonthlyRiskState();
   if(isMonthLocked) return;

   // Check open positions
   bool hasPosition = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol) {
         ulong posMagic = PositionGetInteger(POSITION_MAGIC);
         if(posMagic == InpMagicNumber) {
            hasPosition = true;
            break;
         }
      }
   }
   if(hasPosition) return;

   // Read indicators on Bar 1
   double atr[1], ema200[1];
   if(CopyBuffer(hATR, 0, 1, 1, atr) <= 0) return;
   if(CopyBuffer(hEMA200, 0, 1, 1, ema200) <= 0) return;

   double c_atr = atr[0];
   if(c_atr <= 0.0) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int reqBars = MathMax(InpChannelLookback + 2, InpKFD_Window + 2);
   if(CopyRates(_Symbol, PERIOD_H1, 1, reqBars, rates) < reqBars) return;

   double close1 = rates[0].close;

   // 1. Fractal Horizon Gate
   if(InpUseKFD_Filter) {
      double kfd = ComputeKFD(InpKFD_Window, c_atr);
      if(kfd > InpKFD_Threshold) return;
   }

   // 2. Compute HMA and CMO
   double hma1, hma2, hmaSlope;
   if(!ComputeHMA_State(InpHMA_Period, hma1, hma2, hmaSlope)) return;

   double cmo1 = ComputeCMO(InpCMO_Period);

   // 3. Macro & Directional Vectors
   bool longTrend  = (close1 > ema200[0]) && (close1 > hma1) && (hmaSlope > 0) && (cmo1 >= InpCMO_Threshold);
   bool shortTrend = (close1 < ema200[0]) && (close1 < hma1) && (hmaSlope < 0) && (cmo1 <= -InpCMO_Threshold);

   // 4. Channel High/Low Extremes
   double highestHigh = -1.0;
   double lowestLow = 9999999.0;
   for(int i = 1; i <= InpChannelLookback; i++) {
      if(rates[i].high > highestHigh) highestHigh = rates[i].high;
      if(rates[i].low < lowestLow) lowestLow = rates[i].low;
   }

   bool longSignal  = longTrend && (close1 > highestHigh);
   bool shortSignal = shortTrend && (close1 < lowestLow);

   double lotSize = GetActiveLotSize();
   double slDist = InpTrendSL_ATR_Mult * c_atr;
   double tpDist = slDist * InpTrendTP_Ratio;

   if(longSignal) {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      trade.Buy(lotSize, _Symbol, ask, sl, tp, "S38-HMA-LONG");
   }
   else if(shortSignal) {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      trade.Sell(lotSize, _Symbol, bid, sl, tp, "S38-HMA-SHORT");
   }
}
//+------------------------------------------------------------------+

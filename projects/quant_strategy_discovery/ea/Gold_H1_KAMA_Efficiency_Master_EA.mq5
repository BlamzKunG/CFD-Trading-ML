//+------------------------------------------------------------------+
//|                                Gold_H1_KAMA_Efficiency_Master_EA.mq5|
//|                                  Copyright 2026, Quant CFD Lab   |
//|               Strategy 36: KAMA Dynamic Efficiency Ratio Master EA|
//|                             Target Profit Factor >= 1.50+ (PF 2.71)|
//+------------------------------------------------------------------+
#property copyright "Quant CFD Lab"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 KAMA Dynamic Efficiency Master EA (PF 2.71 Record Engine)"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input double   InpBaseLot             = 0.10;     // Base Lot Size (0.10 = 10.0 oz Gold)
input double   InpMonthlyProfitLock   = 250.0;    // Monthly Profit Target Lock (USD)
input double   InpHardLossBreaker     = 250.0;    // Hard Monthly Loss Circuit Breaker (USD)
input double   InpDefensiveThresh     = 120.0;    // Monthly Loss Threshold for Defensive Sizing (USD)
input double   InpDefensiveMult       = 0.25;     // Defensive Lot Multiplier (0.25 = 0.025 lot)
input ulong    InpMagicNumber         = 363636;   // EA Magic Number

input group "=== KAMA Adaptive Parameters ==="
input int      InpKAMA_Period         = 10;       // KAMA Lookback Period (10 hours)
input int      InpFastSpan            = 2;        // Fast EMA equivalent
input int      InpSlowSpan            = 30;       // Slow EMA equivalent
input double   InpER_Threshold        = 0.45;     // Minimum Efficiency Ratio (ER >= 0.45)

input group "=== Risk / Reward & Execution ==="
input double   InpTrendSL_ATR_Mult    = 2.0;      // Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.5;      // Take Profit R:R Ratio (4.5R)

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

   Print("[+] Gold H1 KAMA Efficiency Master EA Initialized (PF 2.71 Record Engine).");
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
//| Compute KAMA, ER, and Slope for Bar 1 and Bar 2                  |
//+------------------------------------------------------------------+
bool ComputeKAMA_State(int period, double &kama1, double &er1, double &slope1, double &kama2, double &slope2) {
   int totalRequired = period + 50; // Warmup window for accurate KAMA
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, totalRequired, rates);
   if(copied < totalRequired) return false;

   double fastSC = 2.0 / (InpFastSpan + 1.0);
   double slowSC = 2.0 / (InpSlowSpan + 1.0);

   // Calculate running KAMA from oldest to newest
   double kamaVals[];
   double erVals[];
   ArrayResize(kamaVals, copied);
   ArrayResize(erVals, copied);

   // Oldest bar index in rates (copied - 1)
   int oldestIdx = copied - 1;
   kamaVals[oldestIdx] = rates[oldestIdx].close;
   erVals[oldestIdx] = 0.0;

   for(int i = oldestIdx - 1; i >= 0; i--) {
      if(oldestIdx - i < period) {
         kamaVals[i] = rates[i].close;
         erVals[i] = 0.0;
         continue;
      }

      double change = MathAbs(rates[i].close - rates[i + period].close);
      double volatility = 0.0;
      for(int j = 0; j < period; j++) {
         volatility += MathAbs(rates[i + j].close - rates[i + j + 1].close);
      }

      double c_er = (volatility > 0.00001) ? (change / volatility) : 0.0;
      if(c_er > 1.0) c_er = 1.0;
      erVals[i] = c_er;

      double sc = MathPow(c_er * (fastSC - slowSC) + slowSC, 2.0);
      kamaVals[i] = kamaVals[i + 1] + sc * (rates[i].close - kamaVals[i + 1]);
   }

   kama1 = kamaVals[0];
   er1   = erVals[0];
   kama2 = kamaVals[1];

   slope1 = kama1 - kama2;
   slope2 = kama2 - kamaVals[2];

   return true;
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

   // Indicators on Bar 1
   double atr[1], ema200[1];
   if(CopyBuffer(hATR, 0, 1, 1, atr) <= 0) return;
   if(CopyBuffer(hEMA200, 0, 1, 1, ema200) <= 0) return;

   double c_atr = atr[0];
   if(c_atr <= 0.0) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 1, 5, rates) < 5) return;

   double close1 = rates[0].close;
   double close2 = rates[1].close;

   double kama1, er1, slope1, kama2, slope2;
   if(!ComputeKAMA_State(InpKAMA_Period, kama1, er1, slope1, kama2, slope2)) return;

   // Filter 1: Efficiency Ratio Threshold
   if(er1 < InpER_Threshold) return;

   // Filter 2: Macro EMA200 Alignment
   bool longMacro  = (close1 > ema200[0]);
   bool shortMacro = (close1 < ema200[0]);

   // Filter 3: KAMA Regime Alignment & Fresh Inflection Cross
   bool longTrend  = longMacro && (close1 > kama1) && (slope1 > 0);
   bool shortTrend = shortMacro && (close1 < kama1) && (slope1 < 0);

   bool longSignal  = longTrend && (close2 <= kama2 || slope2 <= 0);
   bool shortSignal = shortTrend && (close2 >= kama2 || slope2 >= 0);

   double lotSize = GetActiveLotSize();
   double slDist = InpTrendSL_ATR_Mult * c_atr;
   double tpDist = slDist * InpTrendTP_Ratio;

   if(longSignal) {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      trade.Buy(lotSize, _Symbol, ask, sl, tp, "S36-KAMA-LONG");
   }
   else if(shortSignal) {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      trade.Sell(lotSize, _Symbol, bid, sl, tp, "S36-KAMA-SHORT");
   }
}
//+------------------------------------------------------------------+

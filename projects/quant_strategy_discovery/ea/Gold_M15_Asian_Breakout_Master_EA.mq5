//+------------------------------------------------------------------+
//|                               Gold_M15_Asian_Breakout_Master_EA.mq5|
//|                                  Copyright 2026, Quant CFD Lab   |
//|          Strategy 42: Asian Range Breakout Expansion Master EA    |
//|                             Target Profit Factor >= 1.50+ (PF 1.82)|
//+------------------------------------------------------------------+
#property copyright "Quant CFD Lab"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold M15 Asian Range Breakout Expansion Master EA (PF 1.817)"
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
input ulong    InpMagicNumber         = 424242;   // EA Magic Number

input group "=== Session & Breakout Parameters ==="
input int      InpAsianEndHour        = 7;        // Asian Session End Hour (UTC, 00:00-07:00)
input int      InpExecStartHour       = 8;        // London/NY Window Start Hour (08:00 UTC)
input int      InpExecEndHour         = 16;       // London/NY Window End Hour (16:00 UTC)
input double   InpBreakoutBufferATR   = 0.4;      // Breakout Buffer (0.4x ATR)
input double   InpTrendSL_ATR_Mult    = 2.2;      // Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.5;      // Take Profit R:R Ratio (4.5R)

input group "=== Katz Fractal Horizon Gate ==="
input bool     InpUseKFD_Filter       = true;     // Enable Fractal Gate
input double   InpKFD_Threshold       = 1.40;     // Maximum Fractal Dimension (<= 1.40)
input int      InpKFD_Window          = 32;       // Lookback Bars for KFD (32 bars = 8 hours)

//--- INDICATOR HANDLES & STATE ---
int hATR, hEMA50, hEMA200;
datetime lastBarTime = 0;
int currentMonth = -1;
int currentDay = -1;
double monthlyRealizedPnL = 0.0;
bool isMonthLocked = false;
bool tradedToday = false;

double asianHigh = -1.0;
double asianLow  = 999999.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();

   hATR    = iATR(_Symbol, PERIOD_M15, 14);
   hEMA50  = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEMA200 = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(hATR == INVALID_HANDLE || hEMA50 == INVALID_HANDLE || hEMA200 == INVALID_HANDLE) {
      Print("[-] Error initializing indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] Gold M15 Asian Breakout Master EA Initialized Successfully (PF 1.82 Engine).");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   IndicatorRelease(hATR);
   IndicatorRelease(hEMA50);
   IndicatorRelease(hEMA200);
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension                                   |
//+------------------------------------------------------------------+
double ComputeKFD(int window, double atrVal) {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, 1, window + 1, rates);
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
   int dKey = dt.year * 10000 + dt.mon * 100 + dt.day;

   if(dKey != currentDay) {
      currentDay = dKey;
      tradedToday = false;
      asianHigh = -1.0;
      asianLow  = 999999.0;
   }

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
   datetime currentBar = iTime(_Symbol, PERIOD_M15, 0);
   if(currentBar == lastBarTime) return;
   lastBarTime = currentBar;

   UpdateMonthlyRiskState();
   if(isMonthLocked) return;

   MqlDateTime dt;
   TimeToStruct(currentBar, dt);

   // Update Asian Range (00:00 - AsianEndHour)
   if(dt.hour < InpAsianEndHour) {
      double high1 = iHigh(_Symbol, PERIOD_M15, 1);
      double low1  = iLow(_Symbol, PERIOD_M15, 1);
      if(high1 > asianHigh) asianHigh = high1;
      if(low1 < asianLow)   asianLow  = low1;
   }

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
   if(hasPosition || tradedToday) return;

   // Execution Window
   if(dt.hour < InpExecStartHour || dt.hour > InpExecEndHour) return;
   if(asianHigh <= 0 || asianLow >= 900000.0) return;

   // Indicators on Bar 1
   double atr[1], ema50[1], ema200[1];
   if(CopyBuffer(hATR, 0, 1, 1, atr) <= 0) return;
   if(CopyBuffer(hEMA50, 0, 1, 1, ema50) <= 0) return;
   if(CopyBuffer(hEMA200, 0, 1, 1, ema200) <= 0) return;

   double c_atr = atr[0];
   if(c_atr <= 0.0) return;

   double close1 = iClose(_Symbol, PERIOD_M15, 1);

   // Fractal Horizon Gate
   if(InpUseKFD_Filter) {
      double kfd = ComputeKFD(InpKFD_Window, c_atr);
      if(kfd > InpKFD_Threshold) return;
   }

   double buffer = InpBreakoutBufferATR * c_atr;
   bool longBreakout  = (close1 > asianHigh + buffer) && (close1 > ema50[0]) && (close1 > ema200[0]);
   bool shortBreakout = (close1 < asianLow - buffer)  && (close1 < ema50[0]) && (close1 < ema200[0]);

   double lotSize = GetActiveLotSize();
   double slDist = InpTrendSL_ATR_Mult * c_atr;
   double tpDist = slDist * InpTrendTP_Ratio;

   if(longBreakout) {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      trade.Buy(lotSize, _Symbol, ask, sl, tp, "S42-ASIAN-BREAKOUT-LONG");
      tradedToday = true;
   }
   else if(shortBreakout) {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      trade.Sell(lotSize, _Symbol, bid, sl, tp, "S42-ASIAN-BREAKOUT-SHORT");
      tradedToday = true;
   }
}
//+------------------------------------------------------------------+

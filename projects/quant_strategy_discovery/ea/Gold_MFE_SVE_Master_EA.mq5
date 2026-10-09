//+------------------------------------------------------------------+
//|                                       Gold_MFE_SVE_Master_EA.mq5 |
//|                                  Copyright 2026, Quant CFD Lab   |
//|                    Strategy 30: Multi-Timeframe Fractal Expansion |
//+------------------------------------------------------------------+
#property copyright "Quant CFD Lab"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold MFE-SVE Master Expert Advisor (M15 XAUUSD)"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input double   InpBaseLot             = 0.10;     // Base Lot Size (0.10 = 10.0 oz)
input double   InpMonthlyProfitLock   = 150.0;    // Monthly Profit Target Lock (USD)
input double   InpHardLossBreaker     = 250.0;    // Hard Monthly Loss Circuit Breaker (USD)
input double   InpDefensiveThresh     = 100.0;    // Monthly Drawdown for Defensive Downsizing (USD)
input double   InpDefensiveMult       = 0.30;     // Defensive Lot Multiplier (0.30 = 0.03 lot)
input ulong    InpMagicNumber         = 303030;   // EA Magic Number

input group "=== Multi-Timeframe Structural Trend & Breakout ==="
input int      InpTrendStartHour      = 8;        // Start Hour (UTC)
input int      InpTrendEndHour        = 18;       // End Hour (UTC)
input int      InpDonchianLookback    = 8;        // Market Structure Lookback (bars)
input bool     InpUseEMA50Filter      = true;     // Require Close > EMA50 Alignment
input double   InpTrendSL_ATR_Mult    = 2.5;      // Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.0;      // Take Profit R:R Ratio (4.0R)

input group "=== Optional Fractal Sniper Mode (Record DD < $700) ==="
input bool     InpUseKFD_Filter       = false;    // Enable Katz Fractal Dimension Gate
input double   InpKFD_Threshold       = 1.40;     // Maximum Fractal Dimension (<= 1.40)
input bool     InpUseVR_Filter        = false;    // Enable Volatility Ratio Gate
input double   InpVR_Threshold        = 1.15;     // Maximum Volatility Ratio (<= 1.15)

//--- INDICATOR HANDLES & STATE ---
int hATR14, hATR7, hATR28, hEMA50, hEMA200;
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

   hATR14  = iATR(_Symbol, PERIOD_M15, 14);
   hATR7   = iATR(_Symbol, PERIOD_M15, 7);
   hATR28  = iATR(_Symbol, PERIOD_M15, 28);
   hEMA50  = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEMA200 = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(hATR14 == INVALID_HANDLE || hATR7 == INVALID_HANDLE || hATR28 == INVALID_HANDLE ||
      hEMA50 == INVALID_HANDLE || hEMA200 == INVALID_HANDLE) {
      Print("[-] Error initializing indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] Gold MFE-SVE Master EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   IndicatorRelease(hATR14);
   IndicatorRelease(hATR7);
   IndicatorRelease(hATR28);
   IndicatorRelease(hEMA50);
   IndicatorRelease(hEMA200);
}

//+------------------------------------------------------------------+
//| Calculate Monthly Realized PnL from Trade History                |
//+------------------------------------------------------------------+
double GetMonthlyPnL(int year, int month) {
   MqlDateTime dtStart;
   dtStart.year = year;
   dtStart.mon = month;
   dtStart.day = 1;
   dtStart.hour = 0;
   dtStart.min = 0;
   dtStart.sec = 0;
   datetime tStart = StructToTime(dtStart);

   HistorySelect(tStart, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   double pnl = 0.0;

   for(int i = 0; i < totalDeals; i++) {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0) {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber) {
            pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }
   return pnl;
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension (32-bar lookback)               |
//+------------------------------------------------------------------+
double ComputeKFD(const MqlRates &rates[], double currentATR) {
   int window = 32;
   if(ArraySize(rates) < window + 1 || currentATR <= 0.001) return 1.5;

   double L = 0.0;
   double d = 0.0;
   double p0 = rates[1].close;

   for(int k = 1; k <= window; k++) {
      L += MathAbs(rates[k].close - rates[k + 1].close);
      double dist = MathAbs(rates[k].close - p0);
      if(dist > d) d = dist;
   }

   if(d <= 0.0001) d = 0.0001;
   double L_norm = MathMax(L / currentATR, 1.01);
   double d_norm = MathMax(d / currentATR, 1.01);

   double kfd = MathLog10(L_norm) / MathLog10(d_norm);
   if(kfd < 1.0) kfd = 1.0;
   if(kfd > 2.0) kfd = 2.0;
   return kfd;
}

//+------------------------------------------------------------------+
//| Check if open position exists for this EA                        |
//+------------------------------------------------------------------+
bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetTicket(i) > 0) {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) {
            return true;
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
   datetime currentBarTime = iTime(_Symbol, PERIOD_M15, 0);
   if(currentBarTime == lastBarTime) return; // New bar confirmation only
   lastBarTime = currentBarTime;

   // 1. Monthly Risk Management & ASAR Updates
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.mon != currentMonth) {
      currentMonth = dt.mon;
      monthlyRealizedPnL = 0.0;
      isMonthLocked = false;
      PrintFormat("[CALENDAR] Resetting month cycle for %04d-%02d.", dt.year, dt.mon);
   }

   monthlyRealizedPnL = GetMonthlyPnL(dt.year, dt.mon);

   if(monthlyRealizedPnL >= InpMonthlyProfitLock) {
      if(!isMonthLocked) {
         PrintFormat("[ASAR PROFIT LOCK] Monthly profit target reached ($%.2f >= $%.2f). Locking trading.",
                     monthlyRealizedPnL, InpMonthlyProfitLock);
         isMonthLocked = true;
      }
      return;
   }

   if(monthlyRealizedPnL <= -InpHardLossBreaker) {
      if(!isMonthLocked) {
         PrintFormat("[ASAR CIRCUIT BREAKER] Hard monthly loss limit breached ($%.2f <= -$%.2f). Halting.",
                     monthlyRealizedPnL, InpHardLossBreaker);
         isMonthLocked = true;
      }
      return;
   }

   // 2. Determine Dynamic Position Size
   double tradeLot = InpBaseLot;
   if(monthlyRealizedPnL <= -InpDefensiveThresh) {
      tradeLot = InpBaseLot * InpDefensiveMult;
      double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      tradeLot = MathFloor(tradeLot / lotStep) * lotStep;
      if(tradeLot < minLot) tradeLot = minLot;
   }

   if(HasOpenPosition()) return;

   // 3. Trading Session Check
   int currentHour = dt.hour;
   if(currentHour < InpTrendStartHour || currentHour >= InpTrendEndHour) return;

   // 4. Indicator Buffers
   double atrVal[1], atr7Val[1], atr28Val[1], ema50Val[1], ema200Val[1];
   if(CopyBuffer(hATR14, 0, 1, 1, atrVal) <= 0 ||
      CopyBuffer(hATR7, 0, 1, 1, atr7Val) <= 0 ||
      CopyBuffer(hATR28, 0, 1, 1, atr28Val) <= 0 ||
      CopyBuffer(hEMA50, 0, 1, 1, ema50Val) <= 0 ||
      CopyBuffer(hEMA200, 0, 1, 1, ema200Val) <= 0) return;

   double cATR = atrVal[0];
   double cEMA50 = ema50Val[0];
   double cEMA200 = ema200Val[0];
   double vrRatio = atr7Val[0] / MathMax(atr28Val[0], 0.0001);

   // 5. Rates Buffer for Market Structure & KFD
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M15, 0, 40, rates) < 40) return;

   // Optional Fractal Sniper Filters
   if(InpUseVR_Filter && vrRatio > InpVR_Threshold) return;

   if(InpUseKFD_Filter) {
      double cKFD = ComputeKFD(rates, cATR);
      if(cKFD > InpKFD_Threshold) return;
   }

   // 6. Market Structure Breakout Level
   double highLookback = 0.0;
   double lowLookback = 9999999.0;
   for(int k = 1; k <= InpDonchianLookback; k++) {
      if(rates[k].high > highLookback) highLookback = rates[k].high;
      if(rates[k].low < lowLookback) lowLookback = rates[k].low;
   }

   double confirmedClose = rates[1].close;

   // 7. Order Execution Logic
   bool longCondition = (confirmedClose > highLookback) && (confirmedClose > cEMA200) &&
                        (!InpUseEMA50Filter || confirmedClose > cEMA50);
   bool shortCondition = (confirmedClose < lowLookback) && (confirmedClose < cEMA200) &&
                         (!InpUseEMA50Filter || confirmedClose < cEMA50);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(longCondition) {
      double slDist = InpTrendSL_ATR_Mult * cATR;
      double slPrice = NormalizeDouble(ask - slDist, _Digits);
      double tpPrice = NormalizeDouble(ask + (slDist * InpTrendTP_Ratio), _Digits);

      trade.Buy(tradeLot, _Symbol, ask, slPrice, tpPrice, "MFE_SVE_Long");
      PrintFormat("[ENTRY BUY] Lot: %.2f | Ask: %.2f | SL: %.2f | TP: %.2f | MonthPnL: $%.2f",
                  tradeLot, ask, slPrice, tpPrice, monthlyRealizedPnL);
   }
   else if(shortCondition) {
      double slDist = InpTrendSL_ATR_Mult * cATR;
      double slPrice = NormalizeDouble(bid + slDist, _Digits);
      double tpPrice = NormalizeDouble(bid - (slDist * InpTrendTP_Ratio), _Digits);

      trade.Sell(tradeLot, _Symbol, bid, slPrice, tpPrice, "MFE_SVE_Short");
      PrintFormat("[ENTRY SELL] Lot: %.2f | Bid: %.2f | SL: %.2f | TP: %.2f | MonthPnL: $%.2f",
                  tradeLot, bid, slPrice, tpPrice, monthlyRealizedPnL);
   }
}
//+------------------------------------------------------------------+

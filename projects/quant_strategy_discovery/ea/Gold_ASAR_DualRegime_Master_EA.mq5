//+------------------------------------------------------------------+
//|                                  Gold_ASAR_DualRegime_Master_EA.mq5|
//|                                  Copyright 2026, Quant CFD Lab  |
//|                         Strategy 27: ASAR Precision Champion EA  |
//+------------------------------------------------------------------+
#property copyright "Quant CFD Lab"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold ASAR Dual-Regime Master Expert Advisor (M15 XAUUSD)"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- INPUT PARAMETERS ---
input group "=== Institutional Risk Architecture (ASAR) ==="
input double   InpBaseLot             = 0.10;     // Base Lot Size
input double   InpMonthlyProfitLock   = 150.0;    // Monthly Profit Target Lock (USD)
input double   InpHardLossBreaker     = 250.0;    // Hard Monthly Loss Circuit Breaker (USD)
input double   InpDefensiveThresh     = 120.0;    // Monthly Loss Threshold for Defensive Sizing (USD)
input double   InpDefensiveMult       = 0.30;     // Defensive Lot Multiplier (0.30 = 0.03 lot)
input ulong    InpMagicNumber         = 272727;   // EA Magic Number

input group "=== Engine 1: London / NY Trend Parameters ==="
input int      InpTrendStartHour      = 8;        // Trend Start Hour (UTC)
input int      InpTrendEndHour        = 18;       // Trend End Hour (UTC)
input double   InpTrendSL_ATR_Mult    = 2.5;      // Trend Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.0;      // Trend Risk:Reward Ratio (4.0R)
input int      InpDonchianLookback    = 8;        // Lookback Bars for Breakout

input group "=== Engine 2: Asian Reversion Parameters ==="
input double   InpRevStdMult          = 2.8;      // Bollinger Bands Std Deviation
input double   InpRevSL_ATR_Mult      = 2.0;      // Reversion Stop Loss ATR Multiplier

//--- INDICATOR HANDLES & STATE ---
int hATR, hEMA, hBB;
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

   hATR = iATR(_Symbol, PERIOD_M15, 14);
   hEMA = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   hBB  = iBands(_Symbol, PERIOD_M15, 20, 0, InpRevStdMult, PRICE_CLOSE);

   if(hATR == INVALID_HANDLE || hEMA == INVALID_HANDLE || hBB == INVALID_HANDLE) {
      Print("[-] Error initializing indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] Gold ASAR Dual-Regime Master EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   IndicatorRelease(hATR);
   IndicatorRelease(hEMA);
   IndicatorRelease(hBB);
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
//| Count Open Positions for this EA                                 |
//+------------------------------------------------------------------+
int CountOpenPositions() {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol) {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) {
            count++;
         }
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
   // Bar confirmation filter: Execute ONLY at the open of a new M15 bar
   datetime barTime = iTime(_Symbol, PERIOD_M15, 0);
   if(barTime == lastBarTime) return;
   lastBarTime = barTime;

   MqlDateTime dt;
   TimeToStruct(barTime, dt);

   // Check Calendar Month Budget Reset
   if(dt.mon != currentMonth) {
      currentMonth = dt.mon;
      monthlyRealizedPnL = 0.0;
      isMonthLocked = false;
      PrintFormat("[*] New Calendar Month Started (%d-%02d). Budget Reset.", dt.year, dt.mon);
   }

   // Update Monthly Realized PnL
   monthlyRealizedPnL = GetMonthlyPnL(dt.year, dt.mon);

   // Evaluate Monthly Circuit Breakers
   if(monthlyRealizedPnL >= InpMonthlyProfitLock) {
      if(!isMonthLocked) {
         PrintFormat("[+] MONTH LOCKED IN PROFIT! Monthly PnL = +$%.2f >= Lock ($%.2f). Halting new orders.",
                     monthlyRealizedPnL, InpMonthlyProfitLock);
      }
      isMonthLocked = true;
      return;
   }
   else if(monthlyRealizedPnL <= -InpHardLossBreaker) {
      if(!isMonthLocked) {
         PrintFormat("[-] HARD LOSS BREAKER TRIGGERED! Monthly PnL = -$%.2f <= -$%.2f. Halting new orders.",
                     MathAbs(monthlyRealizedPnL), InpHardLossBreaker);
      }
      isMonthLocked = true;
      return;
   }

   // If month is locked, exit immediately
   if(isMonthLocked) return;

   // Calculate Active Position Sizing (ASAR Dynamic Downsizing)
   double activeLot = InpBaseLot;
   if(monthlyRealizedPnL <= -InpDefensiveThresh) {
      activeLot = NormalizeDouble(InpBaseLot * InpDefensiveMult, 2);
      if(activeLot < 0.01) activeLot = 0.01;
   }

   // Manage Exits for Asian Reversion Positions (Target = SMA20)
   double bbMid[1];
   CopyBuffer(hBB, 0, 1, 1, bbMid);
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) {
         string comment = PositionGetString(POSITION_COMMENT);
         if(StringFind(comment, "REV") >= 0) {
            long posType = PositionGetInteger(POSITION_TYPE);
            double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            if(posType == POSITION_TYPE_BUY && currentBid >= bbMid[0]) {
               trade.PositionClose(PositionGetTicket(i));
            } else if(posType == POSITION_TYPE_SELL && currentAsk <= bbMid[0]) {
               trade.PositionClose(PositionGetTicket(i));
            }
         }
      }
   }

   // Check if we already have an open position
   if(CountOpenPositions() > 0) return;

   // Indicator Buffers (Bar 1 = closed bar)
   double atr[1], ema[1], bbUp[1], bbLow[1];
   CopyBuffer(hATR, 0, 1, 1, atr);
   CopyBuffer(hEMA, 0, 1, 1, ema);
   CopyBuffer(hBB, 1, 1, 1, bbUp);
   CopyBuffer(hBB, 2, 1, 1, bbLow);

   double close1 = iClose(_Symbol, PERIOD_M15, 1);
   double high1  = iHigh(_Symbol, PERIOD_M15, 1);
   double low1   = iLow(_Symbol, PERIOD_M15, 1);

   // --- ENGINE 1: London / NY Trend Momentum (08:00 - 18:00 UTC) ---
   if(dt.hour >= InpTrendStartHour && dt.hour < InpTrendEndHour) {
      double highestHigh = -1.0;
      double lowestLow = 999999.0;
      for(int k = 2; k <= InpDonchianLookback + 1; k++) {
         highestHigh = MathMax(highestHigh, iHigh(_Symbol, PERIOD_M15, k));
         lowestLow   = MathMin(lowestLow, iLow(_Symbol, PERIOD_M15, k));
      }

      // Bullish Trend Breakout
      if(close1 > highestHigh && close1 > ema[0]) {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double slDist = InpTrendSL_ATR_Mult * atr[0];
         double sl = ask - slDist;
         double tp = ask + (slDist * InpTrendTP_Ratio);
         trade.Buy(activeLot, _Symbol, ask, sl, tp, "ASAR_TREND_BUY");
         return;
      }
      // Bearish Trend Breakout
      else if(close1 < lowestLow && close1 < ema[0]) {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double slDist = InpTrendSL_ATR_Mult * atr[0];
         double sl = bid + slDist;
         double tp = bid - (slDist * InpTrendTP_Ratio);
         trade.Sell(activeLot, _Symbol, bid, sl, tp, "ASAR_TREND_SELL");
         return;
      }
   }

   // --- ENGINE 2: Asian Session Mean Reversion (21:00 - 06:00 UTC) ---
   else if(dt.hour >= 21 || dt.hour < 6) {
      // Long Reversion: Bar pierced below lower band and closed back above
      if(low1 < bbLow[0] && close1 > bbLow[0]) {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = ask - (InpRevSL_ATR_Mult * atr[0]);
         trade.Buy(activeLot, _Symbol, ask, sl, 0.0, "ASAR_REV_BUY");
         return;
      }
      // Short Reversion: Bar pierced above upper band and closed back below
      else if(high1 > bbUp[0] && close1 < bbUp[0]) {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = bid + (InpRevSL_ATR_Mult * atr[0]);
         trade.Sell(activeLot, _Symbol, bid, sl, 0.0, "ASAR_REV_SELL");
         return;
      }
   }
}
//+------------------------------------------------------------------+

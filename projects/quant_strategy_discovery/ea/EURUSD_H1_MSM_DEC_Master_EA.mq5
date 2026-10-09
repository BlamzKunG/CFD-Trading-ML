//+------------------------------------------------------------------+
//|                                  EURUSD_H1_MSM_DEC_Master_EA.mq5 |
//|                                  Copyright 2026, Quant CFD Lab   |
//|                 Strategy 31: EURUSD H1 Macro Structural Momentum  |
//+------------------------------------------------------------------+
#property copyright "Quant CFD Lab"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "EURUSD H1 Macro Structural Momentum Master EA"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input double   InpBaseLot             = 0.10;     // Base Lot Size (0.10 = 10,000 EUR)
input double   InpMonthlyProfitLock   = 120.0;    // Monthly Profit Target Lock (USD)
input double   InpHardLossBreaker     = 200.0;    // Hard Monthly Loss Circuit Breaker (USD)
input double   InpDefensiveThresh     = 80.0;     // Monthly Loss Threshold for Defensive Sizing (USD)
input double   InpDefensiveMult       = 0.30;     // Defensive Lot Multiplier (0.30 = 0.03 lot)
input ulong    InpMagicNumber         = 313131;   // EA Magic Number

input group "=== Macro Trend & Channel Breakout Parameters ==="
input int      InpChannelLookback     = 12;       // Lookback Bars for Channel (12 hours)
input double   InpTrendSL_ATR_Mult    = 1.8;      // Stop Loss ATR Multiplier
input double   InpTrendTP_Ratio       = 4.0;      // Take Profit R:R Ratio (4.0R)

//--- INDICATOR HANDLES & STATE ---
int hATR, hEMA50, hEMA200;
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
   hEMA50  = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEMA200 = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(hATR == INVALID_HANDLE || hEMA50 == INVALID_HANDLE || hEMA200 == INVALID_HANDLE) {
      Print("[-] Error initializing indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EURUSD H1 MSM-DEC Master EA Initialized Successfully.");
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
   datetime currentBarTime = iTime(_Symbol, PERIOD_H1, 0);
   if(currentBarTime == lastBarTime) return; // New bar confirmation only
   lastBarTime = currentBarTime;

   // 1. Monthly Risk Management & ASAR Updates
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.mon != currentMonth) {
      currentMonth = dt.mon;
      monthlyRealizedPnL = 0.0;
      isMonthLocked = false;
      PrintFormat("[CALENDAR] Resetting monthly cycle for %04d-%02d.", dt.year, dt.mon);
   }

   monthlyRealizedPnL = GetMonthlyPnL(dt.year, dt.mon);

   if(monthlyRealizedPnL >= InpMonthlyProfitLock) {
      if(!isMonthLocked) {
         PrintFormat("[ASAR PROFIT LOCK] Monthly profit target reached ($%.2f >= $%.2f). Pausing EA.",
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

   // 3. Indicator Buffers
   double atrVal[1], ema50Val[1], ema200Val[1];
   if(CopyBuffer(hATR, 0, 1, 1, atrVal) <= 0 ||
      CopyBuffer(hEMA50, 0, 1, 1, ema50Val) <= 0 ||
      CopyBuffer(hEMA200, 0, 1, 1, ema200Val) <= 0) return;

   double cATR = atrVal[0];
   double cEMA50 = ema50Val[0];
   double cEMA200 = ema200Val[0];

   // 4. Rates Buffer for Channel Lookback
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 0, InpChannelLookback + 5, rates) < InpChannelLookback + 5) return;

   double highLookback = 0.0;
   double lowLookback = 9999999.0;
   for(int k = 1; k <= InpChannelLookback; k++) {
      if(rates[k].high > highLookback) highLookback = rates[k].high;
      if(rates[k].low < lowLookback) lowLookback = rates[k].low;
   }

   double confirmedClose = rates[1].close;

   // 5. Entry Rules
   bool longCondition = (confirmedClose > highLookback) && (confirmedClose > cEMA200) && (confirmedClose > cEMA50);
   bool shortCondition = (confirmedClose < lowLookback) && (confirmedClose < cEMA200) && (confirmedClose < cEMA50);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(longCondition) {
      double slDist = InpTrendSL_ATR_Mult * cATR;
      double slPrice = NormalizeDouble(ask - slDist, _Digits);
      double tpPrice = NormalizeDouble(ask + (slDist * InpTrendTP_Ratio), _Digits);

      trade.Buy(tradeLot, _Symbol, ask, slPrice, tpPrice, "EUR_MSM_Long");
      PrintFormat("[ENTRY BUY] Lot: %.2f | Ask: %.5f | SL: %.5f | TP: %.5f | MonthPnL: $%.2f",
                  tradeLot, ask, slPrice, tpPrice, monthlyRealizedPnL);
   }
   else if(shortCondition) {
      double slDist = InpTrendSL_ATR_Mult * cATR;
      double slPrice = NormalizeDouble(bid + slDist, _Digits);
      double tpPrice = NormalizeDouble(bid - (slDist * InpTrendTP_Ratio), _Digits);

      trade.Sell(tradeLot, _Symbol, bid, slPrice, tpPrice, "EUR_MSM_Short");
      PrintFormat("[ENTRY SELL] Lot: %.2f | Bid: %.5f | SL: %.5f | TP: %.5f | MonthPnL: $%.2f",
                  tradeLot, bid, slPrice, tpPrice, monthlyRealizedPnL);
   }
}
//+------------------------------------------------------------------+

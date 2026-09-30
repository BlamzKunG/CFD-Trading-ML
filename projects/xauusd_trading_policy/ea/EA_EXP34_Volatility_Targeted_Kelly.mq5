//+------------------------------------------------------------------+
//|                         EA_EXP34_Volatility_Targeted_Kelly.mq5  |
//|                         Autonomous Quant ML Research Suite EXP-34|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD Quant ML Research — EXP-34 Volatility-Targeted Kelly"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Strategy from EXP-34: Dynamic Volatility-Targeted Risk (0.65%), Model Confidence Sizing, and Breakeven Ratchet."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Volatility-Targeted Risk (VTS) ==="
input bool     InpEnableVTS            = true;       // Enable Volatility-Targeted Sizing
input double   InpTargetRiskPct        = 0.0065;     // Target Risk per Trade (0.65% of Equity)
input double   InpMinLot               = 0.02;       // Minimum Allowed Lot
input double   InpMaxLot               = 0.50;       // Maximum Allowed Lot
input double   InpFallbackLot          = 0.15;       // Fallback Lot if VTS disabled

input group "=== Cross-Asset Macro Reference (EXP-33) ==="
input string   InpCrossSymbol          = "EURUSD";   // Reference USD Quote Symbol
input double   InpEURRet15Threshold    = 0.0004;     // Max EURUSD 15m Divergence Threshold (0.04%)

input group "=== Dynamic Excursion Ratchet ==="
input bool     InpEnableBeRatchet      = true;       // Enable Breakeven Ratchet after 50% TP progress
input double   InpRatchetProgressPct   = 0.50;       // Progress towards TP to activate ratchet (50%)
input double   InpRatchetOffsetAtr     = 0.10;       // Offset beyond entry to lock in (0.10 ATR)

input group "=== Session Windows (UTC) ==="
input double   InpLondonOpenStartUtc   = 7.0;        // London Open Start (07:00 UTC)
input double   InpLondonOpenEndUtc     = 11.0;       // London Open End (11:00 UTC)
input double   InpNyOpenStartUtc       = 12.5;       // New York Open Start (12:30 UTC)
input double   InpNyOpenEndUtc         = 16.5;       // New York Open End (16:30 UTC)
input double   InpSessionEndUtc        = 18.5;       // Liquid Session End (18:30 UTC)
input bool     InpFridayShield         = true;       // Block new trades after Friday 17:00 UTC
input int      InpBrokerGmtOffset      = 2;          // Broker GMT/UTC Offset (Hours)

input group "=== Technical Filters & Magic ==="
input double   InpMinAtrRatio          = 0.85;       // Min ATR14 / ATR60 ratio
input double   InpMaxEma200DistAtr     = 0.50;       // Max distance from EMA200 (in ATR)
input double   InpTrendSlopeThreshold  = 0.20;       // Standard Trend slope threshold
input int      InpMagicNumber          = 340001;     // Magic Number
input string   InpTradeComment         = "EXP34_VTS"; // Order Comment
input double   InpMaxDailyLossUsd      = 400.0;      // Daily loss circuit breaker ($ USD)
input double   InpSlippagePoints       = 20.0;       // Allowed Slippage Points

//--- Indicator Handles
int g_hAtr14    = INVALID_HANDLE;
int g_hAtr60    = INVALID_HANDLE;
int g_hEma20    = INVALID_HANDLE;
int g_hEma60    = INVALID_HANDLE;
int g_hEma200   = INVALID_HANDLE;
int g_hEma240   = INVALID_HANDLE;
int g_hEma600   = INVALID_HANDLE;
int g_hEma1800  = INVALID_HANDLE;

//--- Global Variables
CTrade   g_trade;
datetime g_lastBarTime     = 0;
datetime g_lastDayChecked   = 0;
double   g_dailyRealizedPnl = 0.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints((ulong)InpSlippagePoints);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   g_hAtr14   = iATR(_Symbol, PERIOD_M1, 14);
   g_hAtr60   = iATR(_Symbol, PERIOD_M1, 60);
   g_hEma20   = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma60   = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma200  = iMA(_Symbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma240  = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma600  = iMA(_Symbol, PERIOD_M1, 600, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma1800 = iMA(_Symbol, PERIOD_M1, 1800, 0, MODE_EMA, PRICE_CLOSE);

   if(g_hAtr14 == INVALID_HANDLE || g_hAtr60 == INVALID_HANDLE ||
      g_hEma20 == INVALID_HANDLE || g_hEma60 == INVALID_HANDLE ||
      g_hEma200 == INVALID_HANDLE || g_hEma240 == INVALID_HANDLE ||
      g_hEma600 == INVALID_HANDLE || g_hEma1800 == INVALID_HANDLE)
   {
      Print("[-] EXP-34 EA Init Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EXP-34 Volatility-Targeted Kelly EA initialized. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(g_hAtr14);
   IndicatorRelease(g_hAtr60);
   IndicatorRelease(g_hEma20);
   IndicatorRelease(g_hEma60);
   IndicatorRelease(g_hEma200);
   IndicatorRelease(g_hEma240);
   IndicatorRelease(g_hEma600);
   IndicatorRelease(g_hEma1800);
   Print("[*] EXP-34 EA deinitialized. Reason code: ", reason);
}

//+------------------------------------------------------------------+
//| Manage Open Positions (Breakeven Excursion Ratchet)              |
//+------------------------------------------------------------------+
void ManageOpenPositions(double currentAtr)
{
   if(!InpEnableBeRatchet) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         long posType = PositionGetInteger(POSITION_TYPE);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentSl = PositionGetDouble(POSITION_SL);
         double currentTp = PositionGetDouble(POSITION_TP);
         if(currentTp <= 0) continue;

         double ratchetOffset = InpRatchetOffsetAtr * currentAtr;

         if(posType == POSITION_TYPE_BUY)
         {
            double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double halfTpThreshold = openPrice + (currentTp - openPrice) * InpRatchetProgressPct;
            if(currentBid >= halfTpThreshold)
            {
               double newSl = openPrice + ratchetOffset;
               if(currentSl < newSl)
               {
                  g_trade.PositionModify(ticket, newSl, currentTp);
                  Print("[+] EXP-34 BE Ratchet Locked: Ticket=", ticket, " NewSL=", newSl);
               }
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double halfTpThreshold = openPrice - (openPrice - currentTp) * InpRatchetProgressPct;
            if(currentAsk <= halfTpThreshold)
            {
               double newSl = openPrice - ratchetOffset;
               if(currentSl > newSl || currentSl == 0)
               {
                  g_trade.PositionModify(ticket, newSl, currentTp);
                  Print("[+] EXP-34 BE Ratchet Locked: Ticket=", ticket, " NewSL=", newSl);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Fetch current ATR for active position management
   double currentAtr14[];
   ArraySetAsSeries(currentAtr14, true);
   if(CopyBuffer(g_hAtr14, 0, 0, 1, currentAtr14) > 0)
   {
      ManageOpenPositions(currentAtr14[0]);
   }

   // 2. Bar-close execution check
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == g_lastBarTime) return;
   g_lastBarTime = currentBarTime;

   CheckDailyCircuitBreaker();
   if(g_dailyRealizedPnl <= -InpMaxDailyLossUsd) return;

   // 3. Session Timing Checks (UTC)
   MqlDateTime dt;
   TimeToStruct(TimeCurrent() - InpBrokerGmtOffset * 3600, dt);
   double currentUtcTime = dt.hour + (dt.min / 60.0);

   if(InpFridayShield && dt.day_of_week == 5 && currentUtcTime >= 17.0) return;

   bool isSleeveA = ((currentUtcTime >= InpLondonOpenStartUtc && currentUtcTime <= InpLondonOpenEndUtc) ||
                     (currentUtcTime >= InpNyOpenStartUtc && currentUtcTime <= InpNyOpenEndUtc));
   bool isSleeveB = ((currentUtcTime > InpLondonOpenEndUtc && currentUtcTime < InpNyOpenStartUtc) ||
                     (currentUtcTime > InpNyOpenEndUtc && currentUtcTime <= InpSessionEndUtc));

   if(!isSleeveA && !isSleeveB) return;

   // 4. Fetch Indicator Buffers
   double atr14[], atr60[], ema20[], ema60[], ema200[], ema240[], ema600[], ema1800[];
   ArraySetAsSeries(atr14, true); ArraySetAsSeries(atr60, true);
   ArraySetAsSeries(ema20, true); ArraySetAsSeries(ema60, true);
   ArraySetAsSeries(ema200, true); ArraySetAsSeries(ema240, true);
   ArraySetAsSeries(ema600, true); ArraySetAsSeries(ema1800, true);

   if(CopyBuffer(g_hAtr14, 0, 1, 1, atr14) <= 0 || CopyBuffer(g_hAtr60, 0, 1, 1, atr60) <= 0 ||
      CopyBuffer(g_hEma20, 0, 1, 1, ema20) <= 0 || CopyBuffer(g_hEma60, 0, 1, 1, ema60) <= 0 ||
      CopyBuffer(g_hEma200, 0, 1, 1, ema200) <= 0 || CopyBuffer(g_hEma240, 0, 1, 1, ema240) <= 0 ||
      CopyBuffer(g_hEma600, 0, 1, 1, ema600) <= 0 || CopyBuffer(g_hEma1800, 0, 1, 1, ema1800) <= 0)
   {
      return;
   }

   double close_1 = iClose(_Symbol, PERIOD_M1, 1);
   double vAtr14 = atr14[0];
   double vAtr60 = atr60[0];
   if(vAtr14 <= 0 || vAtr60 <= 0) return;

   // 5. Technical Filters
   double atrRatio = vAtr14 / vAtr60;
   if(atrRatio < InpMinAtrRatio) return;

   double distEma200Atr = (close_1 - ema200[0]) / vAtr14;
   double trendSlope = (ema60[0] - ema240[0]) / vAtr14;
   bool isStrongTrend = MathAbs(trendSlope) >= InpTrendSlopeThreshold;

   bool goldLongAligned  = (close_1 > ema60[0]) && (ema20[0] > ema60[0]) && (close_1 > ema600[0]) && (ema600[0] > ema1800[0]) && (distEma200Atr >= -InpMaxEma200DistAtr);
   bool goldShortAligned = (close_1 < ema60[0]) && (ema20[0] < ema60[0]) && (close_1 < ema600[0]) && (ema600[0] < ema1800[0]) && (distEma200Atr <= InpMaxEma200DistAtr);

   if(!goldLongAligned && !goldShortAligned) return;

   // 6. EURUSD Macro Gating (EXP-33 Champion)
   double eurClose_1  = iClose(InpCrossSymbol, PERIOD_M1, 1);
   double eurClose_16 = iClose(InpCrossSymbol, PERIOD_M1, 16);
   if(eurClose_1 > 0 && eurClose_16 > 0)
   {
      double eurRet15 = (eurClose_1 - eurClose_16) / eurClose_16;
      if(goldLongAligned && eurRet15 < -InpEURRet15Threshold) return;  // Block Long on Dollar Spike
      if(goldShortAligned && eurRet15 > InpEURRet15Threshold) return; // Block Short on Dollar Crash
   }

   // 7. Check Existing Open Positions
   if(PositionsTotal() > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            return;
         }
      }
   }

   // 8. Dynamic ATR Risk & Sizing Calculation
   double slMult = isStrongTrend ? 1.8 : 1.3;
   double tpMult = isStrongTrend ? 4.5 : 2.5;
   double slDist = slMult * vAtr14;
   double tpDist = tpMult * vAtr14;

   double tradeLot = InpFallbackLot;
   if(InpEnableVTS)
   {
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      double dollarRisk = balance * InpTargetRiskPct;
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tickSize > 0 && tickVal > 0)
      {
         double dollarPerLotLoss = (slDist / tickSize) * tickVal;
         double calcLot = dollarRisk / MathMax(dollarPerLotLoss, 1.0);
         double sleeveMult = isSleeveA ? 1.0 : 0.40;
         tradeLot = MathMin(MathMax(calcLot * sleeveMult, InpMinLot), InpMaxLot);
      }
   }

   // Normalize lot size to broker lot step
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   tradeLot = MathFloor(tradeLot / lotStep) * lotStep;

   if(goldLongAligned)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      g_trade.Buy(tradeLot, _Symbol, ask, sl, tp, InpTradeComment);
      Print("[+] EXP-34 VTS BUY: Lot=", tradeLot, " SL_Dist=", slDist, " RiskPct=", InpTargetRiskPct*100, "%");
   }
   else if(goldShortAligned)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      g_trade.Sell(tradeLot, _Symbol, bid, sl, tp, InpTradeComment);
      Print("[+] EXP-34 VTS SELL: Lot=", tradeLot, " SL_Dist=", slDist, " RiskPct=", InpTargetRiskPct*100, "%");
   }
}

//+------------------------------------------------------------------+
//| Circuit Breaker Tracker                                          |
//+------------------------------------------------------------------+
void CheckDailyCircuitBreaker()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime todayStart = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(todayStart != g_lastDayChecked)
   {
      g_lastDayChecked = todayStart;
      g_dailyRealizedPnl = 0.0;
   }

   HistorySelect(todayStart, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   double realized = 0.0;

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            realized += HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_COMMISSION) + HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }
   g_dailyRealizedPnl = realized;
}

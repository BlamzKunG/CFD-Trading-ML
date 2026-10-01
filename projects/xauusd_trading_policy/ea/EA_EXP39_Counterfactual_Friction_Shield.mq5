//+------------------------------------------------------------------+
//|            EA_EXP39_Counterfactual_Friction_Shield.mq5           |
//|                         Autonomous Quant ML Research Suite EXP-39|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD Quant ML Research — EXP-39 Friction Shield"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Strategy from EXP-39: Friction-Shielded Execution Engine with dynamic broker spread filtration, rollover immunity (21:30-23:30 UTC), USDi macro gating, and 3-Tier APHE trailing."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Broker Execution & Spread Shield ==="
input double   InpMaxAllowedSpreadPoints = 35.0;     // Max Permissible Spread in Points ($0.35/oz)
input bool     InpEnableRolloverShield   = true;     // Block trades during daily rollover (21:30-23:30 UTC)
input double   InpRolloverStartUtc       = 21.5;     // Rollover Shield Start (21:30 UTC)
input double   InpRolloverEndUtc         = 23.5;     // Rollover Shield End (23:30 UTC)
input double   InpMaxExecutionSlippage   = 20.0;     // Allowed Slippage Points

input group "=== 3-Tier Asymmetric Excursion Ladder (APHE) ==="
input bool     InpEnableTrailingLadder = true;       // Enable 3-Tier Asymmetric Trailing Ladder
input double   InpTier1ProgressPct     = 0.50;       // Tier 1 Progress to Activate BE (50% of TP)
input double   InpTier1OffsetAtr       = 0.10;       // Tier 1 Lock-In Offset (0.10 ATR above entry)
input double   InpTier2ProgressPct     = 0.70;       // Tier 2 Progress to Lock 35% Profit (70% of TP)
input double   InpTier2LockPct         = 0.35;       // Tier 2 Profit Lock Fraction (35% of TP)
input double   InpTier3ProgressPct     = 0.85;       // Tier 3 Progress to Lock 65% Profit (85% of TP)
input double   InpTier3LockPct         = 0.65;       // Tier 3 Profit Lock Fraction (65% of TP)

input group "=== Cross-Asset Macro Gating (EXP-35) ==="
input string   InpCrossSymbol          = "EURUSD";   // Reference USD Quote Symbol
input double   InpUSDiRet15Threshold   = 0.0004;     // Max USDi 15m Divergence Threshold (0.04%)
input double   InpEurRet15Threshold    = 0.0004;     // Max EURUSD 15m Divergence Threshold (0.04%)

input group "=== Volatility-Targeted Risk (VTS) ==="
input bool     InpEnableVTS            = true;       // Enable Volatility-Targeted Sizing
input double   InpTargetRiskPct        = 0.0085;     // Target Risk per Trade (0.85% of Equity)
input double   InpMinLot               = 0.02;       // Minimum Allowed Lot
input double   InpMaxLot               = 0.50;       // Maximum Allowed Lot
input double   InpFallbackLot          = 0.18;       // Fallback Lot if VTS disabled

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
input int      InpMagicNumber          = 390001;     // Magic Number
input string   InpTradeComment         = "EXP39_FSHIELD"; // Order Comment
input double   InpMaxDailyLossUsd      = 450.0;      // Daily loss circuit breaker ($ USD)

//--- Indicator Handles
int g_hAtr14    = INVALID_HANDLE;
int g_hAtr60    = INVALID_HANDLE;
int g_hEma20    = INVALID_HANDLE;
int g_hEma60    = INVALID_HANDLE;
int g_hEma200   = INVALID_HANDLE;
int g_hEma240   = INVALID_HANDLE;

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
   g_trade.SetDeviationInPoints((ulong)InpMaxExecutionSlippage);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   g_hAtr14   = iATR(_Symbol, PERIOD_M1, 14);
   g_hAtr60   = iATR(_Symbol, PERIOD_M1, 60);
   g_hEma20   = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma60   = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma200  = iMA(_Symbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma240  = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);

   if(g_hAtr14 == INVALID_HANDLE || g_hAtr60 == INVALID_HANDLE ||
      g_hEma20 == INVALID_HANDLE || g_hEma60 == INVALID_HANDLE ||
      g_hEma200 == INVALID_HANDLE || g_hEma240 == INVALID_HANDLE)
   {
      Print("[-] EXP-39 EA Init Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EXP-39 Friction Shield EA initialized. Magic: ", InpMagicNumber);
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
   Print("[*] EXP-39 EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Check Spread & Rollover Shield                                   |
//+------------------------------------------------------------------+
bool IsExecutionFrictionAcceptable(double utcHour)
{
   if(InpEnableRolloverShield)
   {
      if(utcHour >= InpRolloverStartUtc && utcHour <= InpRolloverEndUtc)
      {
         PrintFormat("[FRICTION SHIELD] Rollover window active (%.2f UTC). Trading blocked to protect from spread blowout.", utcHour);
         return false;
      }
   }

   double currentSpread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(currentSpread > InpMaxAllowedSpreadPoints)
   {
      PrintFormat("[FRICTION SHIELD] Current spread %.1f pts exceeds limit %.1f pts ($%.2f/oz). Order aborted.",
                  currentSpread, InpMaxAllowedSpreadPoints, InpMaxAllowedSpreadPoints * 0.01);
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Daily Realized PnL Tracker & Circuit Breaker                     |
//+------------------------------------------------------------------+
bool IsDailyCircuitBreakerTriggered()
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
   double realizedToday = 0.0;

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            realizedToday += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            realizedToday += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            realizedToday += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }
   g_dailyRealizedPnl = realizedToday;

   if(g_dailyRealizedPnl <= -InpMaxDailyLossUsd)
   {
      PrintFormat("[CIRCUIT BREAKER] EXP-39 daily loss -$%.2f exceeded limit -$%.2f. Trading halted today.",
                  MathAbs(g_dailyRealizedPnl), InpMaxDailyLossUsd);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| 3-Tier Asymmetric Excursion Trailing Ladder                      |
//+------------------------------------------------------------------+
void ManageAsymmetricTrailingLadder(double atr)
{
   if(!InpEnableTrailingLadder || atr <= 0.0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         long posType = PositionGetInteger(POSITION_TYPE);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentSl = PositionGetDouble(POSITION_SL);
         double currentTp = PositionGetDouble(POSITION_TP);
         double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);

         if(currentTp <= 0.0) continue;

         if(posType == POSITION_TYPE_BUY)
         {
            double tpDist = currentTp - openPrice;
            if(tpDist <= 0.0) continue;
            double excursionProgress = (currentPrice - openPrice) / tpDist;

            if(excursionProgress >= InpTier3ProgressPct)
            {
               double targetSl = openPrice + (tpDist * InpTier3LockPct);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier2ProgressPct)
            {
               double targetSl = openPrice + (tpDist * InpTier2LockPct);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier1ProgressPct)
            {
               double targetSl = openPrice + (InpTier1OffsetAtr * atr);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
               }
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            double tpDist = openPrice - currentTp;
            if(tpDist <= 0.0) continue;
            double excursionProgress = (openPrice - currentPrice) / tpDist;

            if(excursionProgress >= InpTier3ProgressPct)
            {
               double targetSl = openPrice - (tpDist * InpTier3LockPct);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier2ProgressPct)
            {
               double targetSl = openPrice - (tpDist * InpTier2LockPct);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier1ProgressPct)
            {
               double targetSl = openPrice - (InpTier1OffsetAtr * atr);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check Cross-Asset USDi Macro Gating                              |
//+------------------------------------------------------------------+
bool CheckUSDMacroGating(bool isLongTrade)
{
   MqlRates eurRates[];
   ArraySetAsSeries(eurRates, true);
   int copiedEur = CopyRates(InpCrossSymbol, PERIOD_M15, 0, 2, eurRates);
   if(copiedEur < 2) return true;

   double eurOpen = eurRates[1].open;
   double eurClose = eurRates[1].close;
   if(eurOpen <= 0.0) return true;
   double eurRet15 = (eurClose - eurOpen) / eurOpen;

   MqlRates xauRates[];
   ArraySetAsSeries(xauRates, true);
   int copiedXau = CopyRates(_Symbol, PERIOD_M15, 0, 2, xauRates);
   if(copiedXau < 2) return true;

   double xauOpen = xauRates[1].open;
   double xauClose = xauRates[1].close;
   if(xauOpen <= 0.0) return true;
   double xauRet15 = (xauClose - xauOpen) / xauOpen;

   double usdiRet15 = -0.60 * eurRet15 - 0.40 * xauRet15;

   if(isLongTrade)
   {
      if(usdiRet15 > InpUSDiRet15Threshold || eurRet15 < -InpEurRet15Threshold) return false;
   }
   else
   {
      if(usdiRet15 < -InpUSDiRet15Threshold || eurRet15 > InpEurRet15Threshold) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Calculate Lot Size using Volatility-Targeted Risk (VTS)          |
//+------------------------------------------------------------------+
double CalculateVolatilityTargetedLot(double slDistancePrice)
{
   if(!InpEnableVTS || slDistancePrice <= 0.0) return InpFallbackLot;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dollarRiskBudget = equity * InpTargetRiskPct;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return InpFallbackLot;

   double pointValue = tickValue / tickSize;
   double dollarRiskPerLot = slDistancePrice * pointValue;
   if(dollarRiskPerLot <= 0.0) return InpFallbackLot;

   double lot = dollarRiskBudget / dollarRiskPerLot;
   lot = NormalizeDouble(lot, 2);
   lot = MathMax(InpMinLot, MathMin(InpMaxLot, lot));

   return lot;
}

//+------------------------------------------------------------------+
//| Main OnTick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Fetch current ATR for trailing
   double atr14Val[];
   ArraySetAsSeries(atr14Val, true);
   if(CopyBuffer(g_hAtr14, 0, 0, 2, atr14Val) >= 2)
   {
      ManageAsymmetricTrailingLadder(atr14Val[1]);
   }

   // 2. Bar Close Check
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == g_lastBarTime) return;
   g_lastBarTime = currentBarTime;

   // 3. Circuit breaker check
   if(IsDailyCircuitBreakerTriggered()) return;

   // 4. Existing Position Check (Single position policy)
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetTicket(i) > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol)
         return;
   }

   // 5. Time and Session Calculation
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 2, rates) < 2) return;

   MqlDateTime dt;
   TimeToStruct(rates[0].time, dt);
   double utcHour = dt.hour - InpBrokerGmtOffset + (dt.min / 60.0);
   if(utcHour < 0.0) utcHour += 24.0;
   if(utcHour >= 24.0) utcHour -= 24.0;

   // 6. Friction & Rollover Shield Check
   if(!IsExecutionFrictionAcceptable(utcHour)) return;

   if(InpFridayShield && dt.day_of_week == 5 && utcHour >= 17.0) return;
   if(utcHour < InpLondonOpenStartUtc || utcHour > InpSessionEndUtc) return;

   // 7. Read Indicator Buffers
   double atr60Val[], ema20Val[], ema60Val[], ema200Val[], ema240Val[];
   ArraySetAsSeries(atr60Val, true);
   ArraySetAsSeries(ema20Val, true);
   ArraySetAsSeries(ema60Val, true);
   ArraySetAsSeries(ema200Val, true);
   ArraySetAsSeries(ema240Val, true);

   if(CopyBuffer(g_hAtr60, 0, 1, 1, atr60Val) < 1 ||
      CopyBuffer(g_hEma20, 0, 1, 1, ema20Val) < 1 ||
      CopyBuffer(g_hEma60, 0, 1, 1, ema60Val) < 1 ||
      CopyBuffer(g_hEma200, 0, 1, 1, ema200Val) < 1 ||
      CopyBuffer(g_hEma240, 0, 1, 1, ema240Val) < 1)
      return;

   double close1 = rates[0].close;
   double atr14  = atr14Val[1];
   double atr60  = atr60Val[0];
   double ema20  = ema20Val[0];
   double ema60  = ema60Val[0];
   double ema200 = ema200Val[0];
   double ema240 = ema240Val[0];

   // Base filters
   if(atr14 < InpMinAtrRatio * atr60) return;
   double distEma200Atr = MathAbs(close1 - ema200) / MathMax(atr14, 0.10);
   if(distEma200Atr > InpMaxEma200DistAtr) return;

   double slope = (ema60 - ema240) / MathMax(atr14, 0.10);
   bool trendLong  = (close1 > ema60) && (ema20 > ema60);
   bool trendShort = (close1 < ema60) && (ema20 < ema60);

   bool isDualOpen = ((utcHour >= InpLondonOpenStartUtc && utcHour <= InpLondonOpenEndUtc) ||
                      (utcHour >= InpNyOpenStartUtc && utcHour <= InpNyOpenEndUtc));
   bool isSleeveB  = ((utcHour > InpLondonOpenEndUtc && utcHour < InpNyOpenStartUtc) ||
                      (utcHour > InpNyOpenEndUtc && utcHour <= InpSessionEndUtc));

   if(!isDualOpen && !isSleeveB) return;

   // USDi Macro Gating
   if(trendLong && !CheckUSDMacroGating(true)) return;
   if(trendShort && !CheckUSDMacroGating(false)) return;

   bool isHiSlope = MathAbs(slope) >= InpTrendSlopeThreshold;
   double slMult = isHiSlope ? 2.50 : 1.80;
   double tpMult = isHiSlope ? 4.50 : 3.00;

   double slDist = slMult * atr14;
   double tpDist = tpMult * atr14;

   if(trendLong)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      double lot = CalculateVolatilityTargetedLot(slDist);

      g_trade.Buy(lot, _Symbol, ask, NormalizeDouble(sl, _Digits), NormalizeDouble(tp, _Digits), InpTradeComment);
   }
   else if(trendShort)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      double lot = CalculateVolatilityTargetedLot(slDist);

      g_trade.Sell(lot, _Symbol, bid, NormalizeDouble(sl, _Digits), NormalizeDouble(tp, _Digits), InpTradeComment);
   }
}
//+------------------------------------------------------------------+

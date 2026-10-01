//+------------------------------------------------------------------+
//|                      EA_EXP37_Multi_Model_Consensus.mq5          |
//|                         Autonomous Quant ML Research Suite EXP-37|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD Quant ML Research — EXP-37 Multi-Model Consensus"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Strategy from EXP-37: Multi-Model Consensus Meta-Ensemble (EXP-24 + EXP-26 + EXP-27 with Graduated Risk Sizing, USDi Gating, and 3-Tier APHE)."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Multi-Model Consensus & Graduated Sizing ==="
input int      InpMinVotesRequired     = 2;          // Minimum Model Votes Required to Enter (2 or 3)
input double   InpUnanimousRiskPct     = 0.0095;     // Risk per Trade for Unanimous 3/3 Votes (0.95%)
input double   InpMajorityRiskPct      = 0.0060;     // Risk per Trade for Majority 2/3 Votes (0.60%)
input double   InpMinLot               = 0.02;       // Minimum Allowed Lot
input double   InpMaxLot               = 0.50;       // Maximum Allowed Lot
input double   InpFallbackLot          = 0.18;       // Fallback Lot if VTS disabled
input bool     InpEnableGraduatedSizing = true;      // Enable Consensus Graduated Sizing

input group "=== 3-Tier Asymmetric Excursion Ladder (APHE) ==="
input bool     InpEnableTrailingLadder = true;       // Enable 3-Tier Asymmetric Trailing Ladder
input double   InpTier1ProgressPct     = 0.50;       // Tier 1 Progress to Activate BE (50% of TP)
input double   InpTier1OffsetAtr       = 0.10;       // Tier 1 Lock-In Offset (0.10 ATR above entry)
input double   InpTier2ProgressPct     = 0.70;       // Tier 2 Progress to Lock 35% Profit (70% of TP)
input double   InpTier2LockPct         = 0.35;       // Tier 2 Profit Lock Fraction (35% of TP)
input double   InpTier3ProgressPct     = 0.85;       // Tier 3 Progress to Lock 65% Profit (85% of TP)
input double   InpTier3LockPct         = 0.65;       // Tier 3 Profit Lock Fraction (65% of TP)

input group "=== Cross-Asset Macro USDi Gating ==="
input string   InpCrossSymbol          = "EURUSD";   // Reference USD Quote Symbol
input double   InpUSDiRet15Threshold   = 0.0004;     // Max USDi 15m Divergence Threshold (0.04%)
input double   InpEurRet15Threshold    = 0.0004;     // Max EURUSD 15m Divergence Threshold (0.04%)

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
input int      InpMagicNumber          = 370001;     // Magic Number
input string   InpTradeComment         = "EXP37_MMC"; // Order Comment
input double   InpMaxDailyLossUsd      = 450.0;      // Daily loss circuit breaker ($ USD)
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
      Print("[-] EXP-37 EA Init Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EXP-37 Multi-Model Consensus EA initialized. Magic: ", InpMagicNumber);
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
   Print("[*] EXP-37 EA deinitialized. Reason: ", reason);
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
      PrintFormat("[CIRCUIT BREAKER] EXP-37 daily loss -$%.2f exceeded limit -$%.2f. Trading halted today.",
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

            // Tier 3: 85% TP progress -> Lock 65% TP
            if(excursionProgress >= InpTier3ProgressPct)
            {
               double targetSl = openPrice + (tpDist * InpTier3LockPct);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  PrintFormat("[EXP-37 APHE BUY Tier 3] Locked 65%% Profit @ %.2f (Progress: %.1f%%)", targetSl, excursionProgress * 100);
                  continue;
               }
            }

            // Tier 2: 70% TP progress -> Lock 35% TP
            if(excursionProgress >= InpTier2ProgressPct)
            {
               double targetSl = openPrice + (tpDist * InpTier2LockPct);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  PrintFormat("[EXP-37 APHE BUY Tier 2] Locked 35%% Profit @ %.2f (Progress: %.1f%%)", targetSl, excursionProgress * 100);
                  continue;
               }
            }

            // Tier 1: 50% TP progress -> Lock Breakeven (+0.10 ATR)
            if(excursionProgress >= InpTier1ProgressPct)
            {
               double targetSl = openPrice + (InpTier1OffsetAtr * atr);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  PrintFormat("[EXP-37 APHE BUY Tier 1] Locked Breakeven @ %.2f (Progress: %.1f%%)", targetSl, excursionProgress * 100);
               }
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            double tpDist = openPrice - currentTp;
            if(tpDist <= 0.0) continue;

            double excursionProgress = (openPrice - currentPrice) / tpDist;

            // Tier 3: 85% TP progress -> Lock 65% TP
            if(excursionProgress >= InpTier3ProgressPct)
            {
               double targetSl = openPrice - (tpDist * InpTier3LockPct);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  PrintFormat("[EXP-37 APHE SELL Tier 3] Locked 65%% Profit @ %.2f (Progress: %.1f%%)", targetSl, excursionProgress * 100);
                  continue;
               }
            }

            // Tier 2: 70% TP progress -> Lock 35% TP
            if(excursionProgress >= InpTier2ProgressPct)
            {
               double targetSl = openPrice - (tpDist * InpTier2LockPct);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  PrintFormat("[EXP-37 APHE SELL Tier 2] Locked 35%% Profit @ %.2f (Progress: %.1f%%)", targetSl, excursionProgress * 100);
                  continue;
               }
            }

            // Tier 1: 50% TP progress -> Lock Breakeven (-0.10 ATR)
            if(excursionProgress >= InpTier1ProgressPct)
            {
               double targetSl = openPrice - (InpTier1OffsetAtr * atr);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_trade.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  PrintFormat("[EXP-37 APHE SELL Tier 1] Locked Breakeven @ %.2f (Progress: %.1f%%)", targetSl, excursionProgress * 100);
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

   // USDi 15m return: -0.60 * eurRet15 - 0.40 * xauRet15
   double usdiRet15 = -0.60 * eurRet15 - 0.40 * xauRet15;

   if(isLongTrade)
   {
      if(usdiRet15 > InpUSDiRet15Threshold || eurRet15 < -InpEurRet15Threshold)
      {
         PrintFormat("[USDi Gating] Blocked BUY! USDi 15m Ret: %.4f%% > Limit %.4f%% | EURRet: %.4f%%",
                     usdiRet15 * 100, InpUSDiRet15Threshold * 100, eurRet15 * 100);
         return false;
      }
   }
   else
   {
      if(usdiRet15 < -InpUSDiRet15Threshold || eurRet15 > InpEurRet15Threshold)
      {
         PrintFormat("[USDi Gating] Blocked SELL! USDi 15m Ret: %.4f%% < Limit -%.4f%% | EURRet: %.4f%%",
                     usdiRet15 * 100, InpUSDiRet15Threshold * 100, eurRet15 * 100);
         return false;
      }
   }

   return true;
}

//+------------------------------------------------------------------+
//| Calculate Consensus-Graduated Lot Size                           |
//+------------------------------------------------------------------+
double CalculateConsensusLotSize(double slDistancePrice, int voteCount)
{
   if(!InpEnableGraduatedSizing || slDistancePrice <= 0.0) return InpFallbackLot;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskPct = (voteCount == 3) ? InpUnanimousRiskPct : InpMajorityRiskPct;
   double dollarRiskBudget = equity * riskPct;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return InpFallbackLot;

   double pointValue = tickValue / tickSize;
   double dollarRiskPerLot = slDistancePrice * pointValue;
   if(dollarRiskPerLot <= 0.0) return InpFallbackLot;

   double lot = dollarRiskBudget / dollarRiskPerLot;
   lot = NormalizeDouble(lot, 2);
   lot = MathMax(InpMinLot, MathMin(InpMaxLot, lot));

   PrintFormat("[EXP-37 Sizing] Votes: %d/3 -> Risk %.2f%% ($%.2f) -> Lot: %.2f (SL Dist: %.2f)",
               voteCount, riskPct * 100, dollarRiskBudget, lot, slDistancePrice);
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

   // 5. Read Indicator Buffers
   double atr60Val[], ema20Val[], ema60Val[], ema200Val[], ema240Val[], ema600Val[], ema1800Val[];
   ArraySetAsSeries(atr60Val, true);
   ArraySetAsSeries(ema20Val, true);
   ArraySetAsSeries(ema60Val, true);
   ArraySetAsSeries(ema200Val, true);
   ArraySetAsSeries(ema240Val, true);
   ArraySetAsSeries(ema600Val, true);
   ArraySetAsSeries(ema1800Val, true);

   if(CopyBuffer(g_hAtr60, 0, 1, 1, atr60Val) < 1 ||
      CopyBuffer(g_hEma20, 0, 1, 1, ema20Val) < 1 ||
      CopyBuffer(g_hEma60, 0, 1, 1, ema60Val) < 1 ||
      CopyBuffer(g_hEma200, 0, 1, 1, ema200Val) < 1 ||
      CopyBuffer(g_hEma240, 0, 1, 1, ema240Val) < 1 ||
      CopyBuffer(g_hEma600, 0, 1, 1, ema600Val) < 1 ||
      CopyBuffer(g_hEma1800, 0, 1, 1, ema1800Val) < 1)
      return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 25, rates) < 25) return;

   double close1 = rates[0].close;
   double atr14  = atr14Val[1];
   double atr60  = atr60Val[0];
   double ema20  = ema20Val[0];
   double ema60  = ema60Val[0];
   double ema200 = ema200Val[0];
   double ema240 = ema240Val[0];
   double ema600 = ema600Val[0];
   double ema1800 = ema1800Val[0];

   // 6. Time and Session Calculation
   MqlDateTime dt;
   TimeToStruct(rates[0].time, dt);
   double utcHour = dt.hour - InpBrokerGmtOffset + (dt.min / 60.0);
   if(utcHour < 0.0) utcHour += 24.0;
   if(utcHour >= 24.0) utcHour -= 24.0;

   if(InpFridayShield && dt.day_of_week == 5 && utcHour >= 17.0) return;
   if(utcHour < InpLondonOpenStartUtc || utcHour > InpSessionEndUtc) return;

   // 7. Base Quantitative Filters
   if(atr14 < 0.85 * atr60) return;
   double distEma200Atr = MathAbs(close1 - ema200) / MathMax(atr14, 0.10);
   if(distEma200Atr > InpMaxEma200DistAtr) return;

   double slope = (ema60 - ema240) / MathMax(atr14, 0.10);
   bool trendLong  = (close1 > ema60) && (ema20 > ema60);
   bool trendShort = (close1 < ema60) && (ema20 < ema60);

   // Volume filter
   double volSum = 0;
   for(int v = 0; v < 20; v++) volSum += (double)rates[v].tick_volume;
   double volMa = volSum / 20.0;
   bool isVolActive = ((double)rates[0].tick_volume >= volMa);

   // Session flags
   bool isDualOpen = ((utcHour >= InpLondonOpenStartUtc && utcHour <= InpLondonOpenEndUtc) ||
                      (utcHour >= InpNyOpenStartUtc && utcHour <= InpNyOpenEndUtc));
   bool isPeakWindow = (utcHour >= 8.0 && utcHour < 16.0);
   bool isSleeveA = isDualOpen;
   bool isSleeveB = ((utcHour > InpLondonOpenEndUtc && utcHour < InpNyOpenStartUtc) ||
                     (utcHour > InpNyOpenEndUtc && utcHour <= InpSessionEndUtc));

   // H1 Macro Trend
   bool h1Bullish = (close1 > ema600 && ema600 > ema1800);
   bool h1Bearish = (close1 < ema600 && ema600 < ema1800);

   // 8. Individual Sub-Model Triggers
   // Model 1: EXP-24 Surgical Precision
   bool exp24_long  = trendLong  && isPeakWindow && isVolActive && h1Bullish;
   bool exp24_short = trendShort && isPeakWindow && isVolActive && h1Bearish;

   // Model 2: EXP-26 Concentrated Dual-Open
   bool exp26_long  = trendLong  && isDualOpen;
   bool exp26_short = trendShort && isDualOpen;

   // Model 3: EXP-27 Cross-Session Dual-Sleeve
   bool exp27_long  = trendLong  && (isSleeveA || isSleeveB);
   bool exp27_short = trendShort && (isSleeveA || isSleeveB);

   int votesLong = (exp24_long ? 1 : 0) + (exp26_long ? 1 : 0) + (exp27_long ? 1 : 0);
   int votesShort = (exp24_short ? 1 : 0) + (exp26_short ? 1 : 0) + (exp27_short ? 1 : 0);

   // 9. Consensus Decision Matrix
   bool openLong = (votesLong >= InpMinVotesRequired) && (votesLong > votesShort);
   bool openShort = (votesShort >= InpMinVotesRequired) && (votesShort > votesLong);

   if(!openLong && !openShort) return;

   // 10. Check Cross-Asset USDi Gating
   if(openLong && !CheckUSDMacroGating(true)) return;
   if(openShort && !CheckUSDMacroGating(false)) return;

   // 11. Multipliers and Sizing
   bool isHiSlope = MathAbs(slope) >= InpTrendSlopeThreshold;
   double slMult = isHiSlope ? 2.50 : 1.80;
   double tpMult = isHiSlope ? 4.50 : 3.00;

   double slDist = slMult * atr14;
   double tpDist = tpMult * atr14;

   if(openLong)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      double lot = CalculateConsensusLotSize(slDist, votesLong);

      g_trade.Buy(lot, _Symbol, ask, NormalizeDouble(sl, _Digits), NormalizeDouble(tp, _Digits),
                  StringFormat("%s_V%d", InpTradeComment, votesLong));
   }
   else if(openShort)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      double lot = CalculateConsensusLotSize(slDist, votesShort);

      g_trade.Sell(lot, _Symbol, bid, NormalizeDouble(sl, _Digits), NormalizeDouble(tp, _Digits),
                   StringFormat("%s_V%d", InpTradeComment, votesShort));
   }
}
//+------------------------------------------------------------------+

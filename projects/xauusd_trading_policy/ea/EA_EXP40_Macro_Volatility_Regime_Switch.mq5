//+------------------------------------------------------------------+
//|          EA_EXP40_Macro_Volatility_Regime_Switch.mq5             |
//|                         Autonomous Quant ML Research Suite EXP-40|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD Quant ML Research — EXP-40 DMV-RSE"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Strategy from EXP-40: Real-Time Dynamic Macro Volatility Regime-Switching Engine (DMV-RSE) deploying specialized parameters across Expansion, Consolidation, and Shock regimes."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Macro Volatility Regime Classification ==="
input double   InpExpansionAtrRatio    = 1.00;       // Minimum ATR14/ATR60 for Expansion Regime
input double   InpExpansionSlope       = 0.20;       // Minimum EMA Trend Slope for Expansion
input double   InpShockUsdiDivergence  = 0.0006;     // Max Permissible USDi 15m Divergence (0.06%)

input group "=== Regime Sizing & Risk Allocation ==="
input double   InpExpansionRiskPct     = 0.0090;     // Expansion Risk per Trade (0.90% Equity)
input double   InpConsolidationRiskPct = 0.0055;     // Consolidation Risk per Trade (0.55% Equity)
input double   InpMinLot               = 0.02;       // Minimum Allowed Lot
input double   InpMaxLot               = 0.50;       // Maximum Allowed Lot
input double   InpFallbackLot          = 0.18;       // Fallback Lot

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
input double   InpUSDiRet15Threshold   = 0.0004;     // Max USDi 15m Normal Gating (0.04%)
input double   InpEurRet15Threshold    = 0.0004;     // Max EURUSD 15m Divergence Threshold (0.04%)

input group "=== Session Windows (UTC) ==="
input double   InpLondonOpenStartUtc   = 7.0;        // London Open Start (07:00 UTC)
input double   InpSessionEndUtc        = 18.5;       // Liquid Session End (18:30 UTC)
input bool     InpFridayShield         = true;       // Block new trades after Friday 17:00 UTC
input int      InpBrokerGmtOffset      = 2;          // Broker GMT/UTC Offset (Hours)

input group "=== Execution & Safety ==="
input int      InpMagicNumber          = 400001;     // Magic Number
input string   InpTradeComment         = "EXP40_DMVRSE"; // Order Comment
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
      Print("[-] EXP-40 EA Init Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EXP-40 Dynamic Regime-Switching EA initialized. Magic: ", InpMagicNumber);
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
   Print("[*] EXP-40 EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Circuit Breaker Tracker                                          |
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
      PrintFormat("[CIRCUIT BREAKER] EXP-40 daily loss -$%.2f exceeded limit -$%.2f. Trading halted today.",
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
//| Check Cross-Asset USDi Macro & Shock Gating                      |
//+------------------------------------------------------------------+
bool CheckMacroRegime(bool isLongTrade, bool &isShockOut)
{
   isShockOut = false;
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

   if(MathAbs(usdiRet15) > InpShockUsdiDivergence)
   {
      isShockOut = true;
      return false; // Macro Shock Freeze
   }

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
//| Main OnTick Handler                                              |
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

   // 3. Circuit breaker
   if(IsDailyCircuitBreakerTriggered()) return;

   // 4. Existing Position Check
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

   MqlDateTime dt;
   TimeToStruct(rates[0].time, dt);
   double utcHour = dt.hour - InpBrokerGmtOffset + (dt.min / 60.0);
   if(utcHour < 0.0) utcHour += 24.0;
   if(utcHour >= 24.0) utcHour -= 24.0;

   if(InpFridayShield && dt.day_of_week == 5 && utcHour >= 17.0) return;
   if(utcHour < InpLondonOpenStartUtc || utcHour > InpSessionEndUtc) return;

   double atrRatio = atr14 / MathMax(atr60, 0.05);
   double slope = (ema60 - ema240) / MathMax(atr14, 0.10);
   bool isExpansion = (atrRatio >= InpExpansionAtrRatio) && (MathAbs(slope) >= InpExpansionSlope);

   bool trendLong  = (close1 > ema60) && (ema20 > ema60);
   bool trendShort = (close1 < ema60) && (ema20 < ema60);

   bool isShock = false;
   bool macroOkLong = CheckMacroRegime(true, isShock);
   bool macroOkShort = CheckMacroRegime(false, isShock);
   if(isShock) return; // Shock freeze

   bool isDualOpen = (((utcHour >= 7.0) && (utcHour <= 11.0)) || ((utcHour >= 12.5) && (utcHour <= 16.5)));
   bool isPeak = (utcHour >= 8.0 && utcHour < 16.0);

   // Volume filter
   double volSum = 0;
   for(int v = 0; v < 20; v++) volSum += (double)rates[v].tick_volume;
   bool isVolActive = ((double)rates[0].tick_volume >= (volSum / 20.0));

   bool h1Bull = (close1 > ema600 && ema600 > ema1800);
   bool h1Bear = (close1 < ema600 && ema600 < ema1800);

   bool openLong = false;
   bool openShort = false;
   double riskPct = 0.0;
   double slMult = 1.80;
   double tpMult = 3.00;

   if(isExpansion)
   {
      // Regime 1: Expansion (Dual Sleeve)
      if(trendLong && isDualOpen && macroOkLong) { openLong = true; }
      if(trendShort && isDualOpen && macroOkShort) { openShort = true; }
      riskPct = InpExpansionRiskPct;
      slMult = 2.50;
      tpMult = 4.50;
   }
   else
   {
      // Regime 2: Consolidation (Surgical Precision)
      if(trendLong && isPeak && isVolActive && h1Bull && macroOkLong) { openLong = true; }
      if(trendShort && isPeak && isVolActive && h1Bear && macroOkShort) { openShort = true; }
      riskPct = InpConsolidationRiskPct;
      slMult = 1.80;
      tpMult = 3.00;
   }

   if(!openLong && !openShort) return;

   double slDist = slMult * atr14;
   double tpDist = tpMult * atr14;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dollarRisk = equity * riskPct;
   double lot = MathMax(InpMinLot, MathMin(InpMaxLot, NormalizeDouble(dollarRisk / (slDist * 100.0), 2)));

   if(openLong)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      g_trade.Buy(lot, _Symbol, ask, NormalizeDouble(ask - slDist, _Digits),
                  NormalizeDouble(ask + tpDist, _Digits),
                  StringFormat("%s_%s", InpTradeComment, isExpansion ? "EXP" : "CON"));
   }
   else if(openShort)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      g_trade.Sell(lot, _Symbol, bid, NormalizeDouble(bid + slDist, _Digits),
                   NormalizeDouble(bid - tpDist, _Digits),
                   StringFormat("%s_%s", InpTradeComment, isExpansion ? "EXP" : "CON"));
   }
}
//+------------------------------------------------------------------+

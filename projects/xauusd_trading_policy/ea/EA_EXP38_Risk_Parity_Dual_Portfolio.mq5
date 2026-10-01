//+------------------------------------------------------------------+
//|                 EA_EXP38_Risk_Parity_Dual_Portfolio.mq5          |
//|                         Autonomous Quant ML Research Suite EXP-38|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD + EURUSD Quant ML Research — EXP-38 Risk Parity"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Dual-Asset Strategy: Synchronous Cross-Asset Risk-Parity Portfolio (CARP-DEP) co-trading Gold and EURUSD with dynamic inverse-volatility sizing, Drawdown Shield, and 3-Tier APHE trailing."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Cross-Asset Allocation & Risk Parity ==="
input string   InpGoldSymbol           = "XAUUSD";   // Primary Asset (Gold)
input string   InpForexSymbol          = "EURUSD";   // Secondary Asset (Forex)
input double   InpTargetGoldRiskPct    = 0.0075;     // Base Risk per Gold Trade (0.75% Equity)
input double   InpTargetForexRiskPct   = 0.0045;     // Base Risk per Forex Trade (0.45% Equity)
input bool     InpEnableVolParity      = true;       // Enable Inverse-Volatility Risk Parity
input bool     InpEnableDrawdownShield = true;       // Enable Portfolio Drawdown Shield
input double   InpShieldTriggerDdPct   = 2.0;        // DD Shield Activation Level (2.0% Drawdown)
input double   InpShieldThrottleFactor = 0.65;       // Risk Sizing Multiplier under Shield (65% sizing)

input group "=== Gold 3-Tier APHE Trailing ==="
input bool     InpEnableGoldLadder     = true;       // Enable 3-Tier Trailing Ladder for Gold
input double   InpTier1ProgressPct     = 0.50;       // Tier 1 Progress to Activate BE (50% of TP)
input double   InpTier1OffsetAtr       = 0.10;       // Tier 1 Lock-In Offset (0.10 ATR above entry)
input double   InpTier2ProgressPct     = 0.70;       // Tier 2 Progress to Lock 35% Profit (70% of TP)
input double   InpTier2LockPct         = 0.35;       // Tier 2 Profit Lock Fraction (35% of TP)
input double   InpTier3ProgressPct     = 0.85;       // Tier 3 Progress to Lock 65% Profit (85% of TP)
input double   InpTier3LockPct         = 0.65;       // Tier 3 Profit Lock Fraction (65% of TP)

input group "=== Cross-Asset Macro USDi Gating ==="
input double   InpUSDiRet15Threshold   = 0.0004;     // Max USDi 15m Divergence Threshold (0.04%)
input double   InpEurRet15Threshold    = 0.0004;     // Max EURUSD 15m Divergence Threshold (0.04%)

input group "=== Session Windows (UTC) ==="
input double   InpLondonOpenStartUtc   = 7.0;        // London Open Start (07:00 UTC)
input double   InpSessionEndUtc        = 18.5;       // Liquid Session End (18:30 UTC)
input bool     InpFridayShield         = true;       // Block new trades after Friday 17:00 UTC
input int      InpBrokerGmtOffset      = 2;          // Broker GMT/UTC Offset (Hours)

input group "=== Execution & Safety ==="
input int      InpGoldMagicNumber      = 380001;     // Magic Number for Gold Orders
input int      InpForexMagicNumber     = 380002;     // Magic Number for Forex Orders
input double   InpMaxDailyLossUsd      = 500.0;      // Daily loss circuit breaker ($ USD)
input double   InpSlippagePoints       = 20.0;       // Allowed Slippage Points

//--- Indicator Handles
int g_hAtrGold14  = INVALID_HANDLE;
int g_hAtrGold60  = INVALID_HANDLE;
int g_hEmaGold20  = INVALID_HANDLE;
int g_hEmaGold60  = INVALID_HANDLE;
int g_hEmaGold200 = INVALID_HANDLE;
int g_hEmaGold240 = INVALID_HANDLE;

int g_hAtrEur14   = INVALID_HANDLE;
int g_hEmaEur20   = INVALID_HANDLE;
int g_hEmaEur60   = INVALID_HANDLE;
int g_hEmaEur200  = INVALID_HANDLE;

//--- Global Variables
CTrade   g_tradeGold;
CTrade   g_tradeForex;
datetime g_lastGoldBarTime   = 0;
datetime g_lastForexBarTime  = 0;
datetime g_lastDayChecked    = 0;
double   g_dailyRealizedPnl  = 0.0;
double   g_portfolioPeakEq   = 0.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_tradeGold.SetExpertMagicNumber(InpGoldMagicNumber);
   g_tradeGold.SetDeviationInPoints((ulong)InpSlippagePoints);
   g_tradeGold.SetTypeFilling(ORDER_FILLING_IOC);

   g_tradeForex.SetExpertMagicNumber(InpForexMagicNumber);
   g_tradeForex.SetDeviationInPoints((ulong)InpSlippagePoints);
   g_tradeForex.SetTypeFilling(ORDER_FILLING_IOC);

   // Gold Indicators
   g_hAtrGold14  = iATR(InpGoldSymbol, PERIOD_M1, 14);
   g_hAtrGold60  = iATR(InpGoldSymbol, PERIOD_M1, 60);
   g_hEmaGold20  = iMA(InpGoldSymbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaGold60  = iMA(InpGoldSymbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaGold200 = iMA(InpGoldSymbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaGold240 = iMA(InpGoldSymbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);

   // Forex Indicators
   g_hAtrEur14   = iATR(InpForexSymbol, PERIOD_M1, 14);
   g_hEmaEur20   = iMA(InpForexSymbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaEur60   = iMA(InpForexSymbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaEur200  = iMA(InpForexSymbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);

   g_portfolioPeakEq = AccountInfoDouble(ACCOUNT_EQUITY);

   Print("[+] EXP-38 Cross-Asset Risk-Parity Dual-Engine EA initialized.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(g_hAtrGold14);
   IndicatorRelease(g_hAtrGold60);
   IndicatorRelease(g_hEmaGold20);
   IndicatorRelease(g_hEmaGold60);
   IndicatorRelease(g_hEmaGold200);
   IndicatorRelease(g_hEmaGold240);
   IndicatorRelease(g_hAtrEur14);
   IndicatorRelease(g_hEmaEur20);
   IndicatorRelease(g_hEmaEur60);
   IndicatorRelease(g_hEmaEur200);
   Print("[*] EXP-38 EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Circuit Breaker & High-Water Mark Drawdown Shield                |
//+------------------------------------------------------------------+
bool CheckPortfolioRiskShield(double &riskModOut)
{
   riskModOut = 1.0;
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity > g_portfolioPeakEq) g_portfolioPeakEq = currentEquity;

   double portfolioDd = (g_portfolioPeakEq - currentEquity) / MathMax(g_portfolioPeakEq, 1.0);
   if(InpEnableDrawdownShield && (portfolioDd * 100.0) >= InpShieldTriggerDdPct)
   {
      riskModOut = InpShieldThrottleFactor;
   }

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
         if(magic == InpGoldMagicNumber || magic == InpForexMagicNumber)
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
      PrintFormat("[CIRCUIT BREAKER] EXP-38 daily loss -$%.2f exceeded limit -$%.2f. Trading halted today.",
                  MathAbs(g_dailyRealizedPnl), InpMaxDailyLossUsd);
      return false; // Halted
   }

   return true; // OK to trade
}

//+------------------------------------------------------------------+
//| Gold 3-Tier Asymmetric Excursion Trailing Ladder                 |
//+------------------------------------------------------------------+
void ManageGoldTrailingLadder(double atr)
{
   if(!InpEnableGoldLadder || atr <= 0.0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpGoldMagicNumber && PositionGetString(POSITION_SYMBOL) == InpGoldSymbol)
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
                  g_tradeGold.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier2ProgressPct)
            {
               double targetSl = openPrice + (tpDist * InpTier2LockPct);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_tradeGold.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier1ProgressPct)
            {
               double targetSl = openPrice + (InpTier1OffsetAtr * atr);
               if(targetSl > currentSl + _Point * 10)
               {
                  g_tradeGold.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
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
                  g_tradeGold.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier2ProgressPct)
            {
               double targetSl = openPrice - (tpDist * InpTier2LockPct);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_tradeGold.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
                  continue;
               }
            }
            if(excursionProgress >= InpTier1ProgressPct)
            {
               double targetSl = openPrice - (InpTier1OffsetAtr * atr);
               if(currentSl == 0.0 || targetSl < currentSl - _Point * 10)
               {
                  g_tradeGold.PositionModify(ticket, NormalizeDouble(targetSl, _Digits), currentTp);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Cross-Asset USDi Macro Gating                                    |
//+------------------------------------------------------------------+
bool CheckUSDiMacroGating(bool isLongGold)
{
   MqlRates eurRates[];
   ArraySetAsSeries(eurRates, true);
   if(CopyRates(InpForexSymbol, PERIOD_M15, 0, 2, eurRates) < 2) return true;

   double eurOpen = eurRates[1].open;
   double eurClose = eurRates[1].close;
   if(eurOpen <= 0.0) return true;
   double eurRet15 = (eurClose - eurOpen) / eurOpen;

   MqlRates xauRates[];
   ArraySetAsSeries(xauRates, true);
   if(CopyRates(InpGoldSymbol, PERIOD_M15, 0, 2, xauRates) < 2) return true;

   double xauOpen = xauRates[1].open;
   double xauClose = xauRates[1].close;
   if(xauOpen <= 0.0) return true;
   double xauRet15 = (xauClose - xauOpen) / xauOpen;

   double usdiRet15 = -0.60 * eurRet15 - 0.40 * xauRet15;

   if(isLongGold)
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
   double riskMod = 1.0;
   if(!CheckPortfolioRiskShield(riskMod)) return;

   // 1. Manage Gold Trailing Ladder on every tick
   double atrGoldVal[];
   ArraySetAsSeries(atrGoldVal, true);
   if(CopyBuffer(g_hAtrGold14, 0, 0, 2, atrGoldVal) >= 2)
   {
      ManageGoldTrailingLadder(atrGoldVal[1]);
   }

   // 2. Bar close check on M1
   datetime barTime = iTime(InpGoldSymbol, PERIOD_M1, 0);
   if(barTime == g_lastGoldBarTime) return;
   g_lastGoldBarTime = barTime;

   // Session & Friday Shield
   MqlDateTime dt;
   TimeCurrent(dt);
   double utcHour = dt.hour - InpBrokerGmtOffset + (dt.min / 60.0);
   if(utcHour < 0.0) utcHour += 24.0;
   if(utcHour >= 24.0) utcHour -= 24.0;

   if(InpFridayShield && dt.day_of_week == 5 && utcHour >= 17.0) return;
   if(utcHour < InpLondonOpenStartUtc || utcHour > InpSessionEndUtc) return;

   // Check Active Positions
   bool hasGoldPos = false;
   bool hasForexPos = false;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetTicket(i) > 0)
      {
         long magic = PositionGetInteger(POSITION_MAGIC);
         if(magic == InpGoldMagicNumber) hasGoldPos = true;
         if(magic == InpForexMagicNumber) hasForexPos = true;
      }
   }

   // 3. Evaluate Gold Strategy (EXP-36/37 Engine)
   if(!hasGoldPos)
   {
      double atr60Val[], ema20Val[], ema60Val[], ema200Val[], ema240Val[];
      ArraySetAsSeries(atr60Val, true);
      ArraySetAsSeries(ema20Val, true);
      ArraySetAsSeries(ema60Val, true);
      ArraySetAsSeries(ema200Val, true);
      ArraySetAsSeries(ema240Val, true);

      if(CopyBuffer(g_hAtrGold60, 0, 1, 1, atr60Val) >= 1 &&
         CopyBuffer(g_hEmaGold20, 0, 1, 1, ema20Val) >= 1 &&
         CopyBuffer(g_hEmaGold60, 0, 1, 1, ema60Val) >= 1 &&
         CopyBuffer(g_hEmaGold200, 0, 1, 1, ema200Val) >= 1 &&
         CopyBuffer(g_hEmaGold240, 0, 1, 1, ema240Val) >= 1)
      {
         MqlRates rates[];
         ArraySetAsSeries(rates, true);
         if(CopyRates(InpGoldSymbol, PERIOD_M1, 1, 2, rates) >= 2)
         {
            double close1 = rates[0].close;
            double atr14  = atrGoldVal[1];
            double atr60  = atr60Val[0];
            double ema20  = ema20Val[0];
            double ema60  = ema60Val[0];
            double ema200 = ema200Val[0];
            double ema240 = ema240Val[0];

            if(atr14 >= 0.85 * atr60 && MathAbs(close1 - ema200) / MathMax(atr14, 0.1) <= 0.50)
            {
               double slope = (ema60 - ema240) / MathMax(atr14, 0.1);
               bool trendLong  = (close1 > ema60) && (ema20 > ema60);
               bool trendShort = (close1 < ema60) && (ema20 < ema60);

               bool isDualOpen = (((utcHour >= 7.0) && (utcHour <= 11.0)) || ((utcHour >= 12.5) && (utcHour <= 16.5)));

               if(isDualOpen)
               {
                  if(trendLong && CheckUSDiMacroGating(true))
                  {
                     double ask = SymbolInfoDouble(InpGoldSymbol, SYMBOL_ASK);
                     double slDist = (MathAbs(slope) >= 0.20 ? 2.50 : 1.80) * atr14;
                     double tpDist = (MathAbs(slope) >= 0.20 ? 4.50 : 3.00) * atr14;
                     double equity = AccountInfoDouble(ACCOUNT_EQUITY);
                     double dollarRisk = equity * InpTargetGoldRiskPct * riskMod;
                     double lot = MathMax(0.02, MathMin(0.50, NormalizeDouble(dollarRisk / (slDist * 100.0), 2)));

                     g_tradeGold.Buy(lot, InpGoldSymbol, ask, NormalizeDouble(ask - slDist, _Digits),
                                     NormalizeDouble(ask + tpDist, _Digits), "EXP38_GOLD");
                  }
                  else if(trendShort && CheckUSDiMacroGating(false))
                  {
                     double bid = SymbolInfoDouble(InpGoldSymbol, SYMBOL_BID);
                     double slDist = (MathAbs(slope) >= 0.20 ? 2.50 : 1.80) * atr14;
                     double tpDist = (MathAbs(slope) >= 0.20 ? 4.50 : 3.00) * atr14;
                     double equity = AccountInfoDouble(ACCOUNT_EQUITY);
                     double dollarRisk = equity * InpTargetGoldRiskPct * riskMod;
                     double lot = MathMax(0.02, MathMin(0.50, NormalizeDouble(dollarRisk / (slDist * 100.0), 2)));

                     g_tradeGold.Sell(lot, InpGoldSymbol, bid, NormalizeDouble(bid + slDist, _Digits),
                                      NormalizeDouble(bid - tpDist, _Digits), "EXP38_GOLD");
                  }
               }
            }
         }
      }
   }

   // 4. Evaluate EURUSD Strategy (EXP-32 Momentum Breakout)
   if(!hasForexPos)
   {
      double atrEurVal[], ema20EurVal[], ema60EurVal[], ema200EurVal[];
      ArraySetAsSeries(atrEurVal, true);
      ArraySetAsSeries(ema20EurVal, true);
      ArraySetAsSeries(ema60EurVal, true);
      ArraySetAsSeries(ema200EurVal, true);

      if(CopyBuffer(g_hAtrEur14, 0, 1, 1, atrEurVal) >= 1 &&
         CopyBuffer(g_hEmaEur20, 0, 1, 1, ema20EurVal) >= 1 &&
         CopyBuffer(g_hEmaEur60, 0, 1, 1, ema60EurVal) >= 1 &&
         CopyBuffer(g_hEmaEur200, 0, 1, 1, ema200EurVal) >= 1)
      {
         MqlRates eurRates[];
         ArraySetAsSeries(eurRates, true);
         if(CopyRates(InpForexSymbol, PERIOD_M1, 1, 16, eurRates) >= 16)
         {
            double cEur = eurRates[0].close;
            double atrEur = atrEurVal[0];
            double ema20E = ema20EurVal[0];
            double ema60E = ema60EurVal[0];
            double ema200E = ema200EurVal[0];

            double eurRet15 = (cEur - eurRates[15].open) / eurRates[15].open;
            bool trendEurLong = (cEur > ema60E) && (ema20E > ema60E);
            bool trendEurShort = (cEur < ema60E) && (ema20E < ema60E);
            double dist200 = MathAbs(cEur - ema200E) / MathMax(atrEur, 0.00005);

            if(dist200 <= 0.60 && utcHour >= 7.0 && utcHour <= 16.0)
            {
               double equity = AccountInfoDouble(ACCOUNT_EQUITY);
               double dollarRiskE = equity * InpTargetForexRiskPct * riskMod;
               double slPips = (1.80 * atrEur) / 0.0001;
               double lotE = MathMax(0.02, MathMin(0.60, NormalizeDouble(dollarRiskE / (slPips * 10.0), 2)));

               if(trendEurLong && eurRet15 >= 0.0002)
               {
                  double askE = SymbolInfoDouble(InpForexSymbol, SYMBOL_ASK);
                  g_tradeForex.Buy(lotE, InpForexSymbol, askE, NormalizeDouble(askE - 1.80 * atrEur, 5),
                                   NormalizeDouble(askE + 3.20 * atrEur, 5), "EXP38_EUR");
               }
               else if(trendEurShort && eurRet15 <= -0.0002)
               {
                  double bidE = SymbolInfoDouble(InpForexSymbol, SYMBOL_BID);
                  g_tradeForex.Sell(lotE, InpForexSymbol, bidE, NormalizeDouble(bidE + 1.80 * atrEur, 5),
                                    NormalizeDouble(bidE - 3.20 * atrEur, 5), "EXP38_EUR");
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+

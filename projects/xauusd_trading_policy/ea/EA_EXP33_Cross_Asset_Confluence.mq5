//+------------------------------------------------------------------+
//|                               EA_EXP33_Cross_Asset_Confluence.mq5|
//|                         Autonomous Quant ML Research Suite EXP-33|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD & EURUSD Quant ML Research — EXP-33 Macro Confluence"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Strategy from EXP-33: Cross-Asset Macro Confluence & Correlation Gating between XAUUSD & EURUSD."
#property strict

#include <Trade\Trade.mqh>

enum ENUM_CONFLUENCE_MODE
{
   CONFLUENCE_DYNAMIC_SIZING = 0, // Dynamic Lot Sizing (Boost 0.22 / De-risk 0.08)
   CONFLUENCE_HARD_GATE      = 1, // Hard Gating (Block Trades On USD Divergence)
   CONFLUENCE_DISABLED       = 2  // Standalone Gold (EXP-27 Baseline)
};

//--- Input Parameters
input group "=== Cross-Asset Macro Reference Settings ==="
input string                 InpCrossSymbol          = "EURUSD";   // Reference USD Quote Symbol
input ENUM_CONFLUENCE_MODE   InpConfluenceMode       = CONFLUENCE_DYNAMIC_SIZING; // Cross-Asset Mode
input double                 InpEURRet15Threshold    = 0.0004;     // Max EURUSD 15m Divergence Threshold (0.04%)
input int                    InpEURMAPeriod          = 60;         // EURUSD Macro Trend EMA Period

input group "=== Capital Allocation & Sizing ==="
input double                 InpBaseLotSleeveA       = 0.18;       // Base Lot for Sleeve A (Peak 07-11 & 12:30-16:30 UTC)
input double                 InpBaseLotSleeveB       = 0.06;       // Base Lot for Sleeve B (Cross-Session Transition)
input double                 InpConfluentBoostLot    = 0.22;       // Boosted Lot on Perfect Cross-Asset Confluence
input double                 InpDivergentRiskLot     = 0.08;       // Reduced Lot on Cross-Asset Divergence
input int                    InpMagicNumber          = 330001;     // Magic Number
input string                 InpTradeComment         = "EXP33_Macro"; // Order Comment
input int                    InpBrokerGmtOffset      = 2;          // Broker GMT/UTC Offset (Hours)

input group "=== Session Windows (UTC) ==="
input double                 InpLondonOpenStartUtc   = 7.0;        // London Open Start (07:00 UTC)
input double                 InpLondonOpenEndUtc     = 11.0;       // London Open End (11:00 UTC)
input double                 InpNyOpenStartUtc       = 12.5;       // New York Open Start (12:30 UTC)
input double                 InpNyOpenEndUtc         = 16.5;       // New York Open End (16:30 UTC)
input double                 InpSessionEndUtc        = 18.5;       // Liquid Session End (18:30 UTC)
input bool                   InpFridayShield         = true;       // Block new trades after Friday 17:00 UTC

input group "=== Gold Technical Filters ==="
input double                 InpMinAtrRatio          = 0.85;       // Min ATR14 / ATR60 ratio
input double                 InpMaxEma200DistAtr     = 0.50;       // Max distance from EMA200 (in ATR)
input double                 InpTrendSlopeThreshold  = 0.20;       // Standard Trend slope threshold

input group "=== Risk Management ==="
input double                 InpMaxDailyLossUsd      = 350.0;      // Daily loss circuit breaker ($ USD)
input double                 InpSlippagePoints       = 20.0;       // Allowed Slippage Points

//--- Indicator Handles (XAUUSD)
int g_hAtr14    = INVALID_HANDLE;
int g_hAtr60    = INVALID_HANDLE;
int g_hEma20    = INVALID_HANDLE;
int g_hEma60    = INVALID_HANDLE;
int g_hEma200   = INVALID_HANDLE;
int g_hEma240   = INVALID_HANDLE;
int g_hEma600   = INVALID_HANDLE;
int g_hEma1800  = INVALID_HANDLE;

//--- Indicator Handles (Cross-Asset EURUSD)
int g_hEurEma60 = INVALID_HANDLE;

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

   // Initialize Primary Symbol Indicators
   g_hAtr14   = iATR(_Symbol, PERIOD_M1, 14);
   g_hAtr60   = iATR(_Symbol, PERIOD_M1, 60);
   g_hEma20   = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma60   = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma200  = iMA(_Symbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma240  = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma600  = iMA(_Symbol, PERIOD_M1, 600, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma1800 = iMA(_Symbol, PERIOD_M1, 1800, 0, MODE_EMA, PRICE_CLOSE);

   // Initialize Reference Cross-Asset Symbol Indicator
   g_hEurEma60 = iMA(InpCrossSymbol, PERIOD_M1, InpEURMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(g_hAtr14 == INVALID_HANDLE || g_hAtr60 == INVALID_HANDLE ||
      g_hEma20 == INVALID_HANDLE || g_hEma60 == INVALID_HANDLE ||
      g_hEma200 == INVALID_HANDLE || g_hEma240 == INVALID_HANDLE ||
      g_hEma600 == INVALID_HANDLE || g_hEma1800 == INVALID_HANDLE ||
      g_hEurEma60 == INVALID_HANDLE)
   {
      Print("[-] EXP-33 EA Init Error: Failed to create indicator handles. Ensure ", InpCrossSymbol, " is in Market Watch!");
      return(INIT_FAILED);
   }

   Print("[+] EXP-33 Cross-Asset Macro Confluence EA initialized. Symbol: ", _Symbol, " Cross: ", InpCrossSymbol);
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
   IndicatorRelease(g_hEurEma60);
   Print("[*] EXP-33 EA deinitialized. Reason code: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == g_lastBarTime) return;
   g_lastBarTime = currentBarTime;

   CheckDailyCircuitBreaker();
   if(g_dailyRealizedPnl <= -InpMaxDailyLossUsd)
   {
      Print("[!] EXP-33 Circuit Breaker Active. Daily loss: $", g_dailyRealizedPnl);
      return;
   }

   // 1. Session Timing Checks (UTC)
   MqlDateTime dt;
   TimeToStruct(TimeCurrent() - InpBrokerGmtOffset * 3600, dt);
   double currentUtcTime = dt.hour + (dt.min / 60.0);

   if(InpFridayShield && dt.day_of_week == 5 && currentUtcTime >= 17.0) return;

   bool isSleeveA = ((currentUtcTime >= InpLondonOpenStartUtc && currentUtcTime <= InpLondonOpenEndUtc) ||
                     (currentUtcTime >= InpNyOpenStartUtc && currentUtcTime <= InpNyOpenEndUtc));
   bool isSleeveB = ((currentUtcTime > InpLondonOpenEndUtc && currentUtcTime < InpNyOpenStartUtc) ||
                     (currentUtcTime > InpNyOpenEndUtc && currentUtcTime <= InpSessionEndUtc));

   if(!isSleeveA && !isSleeveB) return;

   // 2. Fetch Indicator Buffers
   double atr14[], atr60[], ema20[], ema60[], ema200[], ema240[], ema600[], ema1800[], eurEma60[];
   ArraySetAsSeries(atr14, true); ArraySetAsSeries(atr60, true);
   ArraySetAsSeries(ema20, true); ArraySetAsSeries(ema60, true);
   ArraySetAsSeries(ema200, true); ArraySetAsSeries(ema240, true);
   ArraySetAsSeries(ema600, true); ArraySetAsSeries(ema1800, true);
   ArraySetAsSeries(eurEma60, true);

   if(CopyBuffer(g_hAtr14, 0, 1, 1, atr14) <= 0 || CopyBuffer(g_hAtr60, 0, 1, 1, atr60) <= 0 ||
      CopyBuffer(g_hEma20, 0, 1, 1, ema20) <= 0 || CopyBuffer(g_hEma60, 0, 1, 1, ema60) <= 0 ||
      CopyBuffer(g_hEma200, 0, 1, 1, ema200) <= 0 || CopyBuffer(g_hEma240, 0, 1, 1, ema240) <= 0 ||
      CopyBuffer(g_hEma600, 0, 1, 1, ema600) <= 0 || CopyBuffer(g_hEma1800, 0, 1, 1, ema1800) <= 0 ||
      CopyBuffer(g_hEurEma60, 0, 1, 1, eurEma60) <= 0)
   {
      return;
   }

   double close_1 = iClose(_Symbol, PERIOD_M1, 1);
   double vAtr14 = atr14[0];
   double vAtr60 = atr60[0];
   if(vAtr14 <= 0 || vAtr60 <= 0) return;

   // 3. Technical Filters
   double atrRatio = vAtr14 / vAtr60;
   if(atrRatio < InpMinAtrRatio) return;

   double distEma200Atr = (close_1 - ema200[0]) / vAtr14;
   double trendSlope = (ema60[0] - ema240[0]) / vAtr14;
   bool isStrongTrend = MathAbs(trendSlope) >= InpTrendSlopeThreshold;

   bool goldLongAligned  = (close_1 > ema60[0]) && (ema20[0] > ema60[0]) && (close_1 > ema600[0]) && (ema600[0] > ema1800[0]) && (distEma200Atr >= -InpMaxEma200DistAtr);
   bool goldShortAligned = (close_1 < ema60[0]) && (ema20[0] < ema60[0]) && (close_1 < ema600[0]) && (ema600[0] < ema1800[0]) && (distEma200Atr <= InpMaxEma200DistAtr);

   if(!goldLongAligned && !goldShortAligned) return;

   // 4. Fetch Cross-Asset Reference Data (EURUSD)
   double eurClose_1  = iClose(InpCrossSymbol, PERIOD_M1, 1);
   double eurClose_16 = iClose(InpCrossSymbol, PERIOD_M1, 16);
   if(eurClose_1 <= 0 || eurClose_16 <= 0) return;

   double eurRet15 = (eurClose_1 - eurClose_16) / eurClose_16;
   bool eurAboveEma60 = (eurClose_1 > eurEma60[0]);

   // Confluence flags: EUR rising means USD weakness (Bullish for Gold Long)
   bool isConfluentLong  = eurAboveEma60 && (eurRet15 > 0.0);
   bool isConfluentShort = (!eurAboveEma60) && (eurRet15 < 0.0);

   bool isDivergentLong  = (!eurAboveEma60) || (eurRet15 < -InpEURRet15Threshold);
   bool isDivergentShort = eurAboveEma60 || (eurRet15 > InpEURRet15Threshold);

   // 5. Evaluate Confluence Gating & Position Sizing
   double tradeLot = isSleeveA ? InpBaseLotSleeveA : InpBaseLotSleeveB;

   if(InpConfluenceMode == CONFLUENCE_HARD_GATE)
   {
      if(goldLongAligned && isDivergentLong) return;   // Block Gold Long if EURUSD is plunging
      if(goldShortAligned && isDivergentShort) return; // Block Gold Short if EURUSD is surging
   }
   else if(InpConfluenceMode == CONFLUENCE_DYNAMIC_SIZING)
   {
      if(goldLongAligned)
      {
         if(isConfluentLong) tradeLot = InpConfluentBoostLot;
         else if(isDivergentLong) tradeLot = InpDivergentRiskLot;
      }
      else if(goldShortAligned)
      {
         if(isConfluentShort) tradeLot = InpConfluentBoostLot;
         else if(isDivergentShort) tradeLot = InpDivergentRiskLot;
      }
   }

   // 6. Check Existing Positions
   if(PositionsTotal() > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            return; // 1 concurrent trade policy
         }
      }
   }

   // 7. Dynamic ATR Brackets
   double slDist = (isStrongTrend ? 2.5 : 1.8) * vAtr14;
   double tpDist = (isStrongTrend ? 4.5 : 3.0) * vAtr14;

   if(goldLongAligned)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - slDist;
      double tp = ask + tpDist;
      g_trade.Buy(tradeLot, _Symbol, ask, sl, tp, InpTradeComment);
      Print("[+] EXP-33 BUY Executed: Lot=", tradeLot, " Confluent=", isConfluentLong, " EURRet15=", eurRet15);
   }
   else if(goldShortAligned)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + slDist;
      double tp = bid - tpDist;
      g_trade.Sell(tradeLot, _Symbol, bid, sl, tp, InpTradeComment);
      Print("[+] EXP-33 SELL Executed: Lot=", tradeLot, " Confluent=", isConfluentShort, " EURRet15=", eurRet15);
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

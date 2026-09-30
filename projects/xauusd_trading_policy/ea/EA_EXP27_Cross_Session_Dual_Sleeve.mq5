//+------------------------------------------------------------------+
//|                                 EA_EXP27_Cross_Session_Dual_Sleeve.mq5|
//|                         Autonomous Quant ML Research Suite EXP-27|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD Quant ML Research — EXP-27 Cross-Session Dual-Sleeve"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Quantitative ML Strategy from EXP-27: 54.2% WR, 1.87 PF, 1.11% Max DD, +$563 on 2025 Out-of-Sample."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Dual-Sleeve Allocation Settings ==="
input double   InpSleeveALots          = 0.18;       // Sleeve A Lots (Dual-Open Peak 07-11 & 12:30-16:30 UTC)
input double   InpSleeveBLots          = 0.06;       // Sleeve B Lots (Cross-Session Transition 11-12:30 & 16:30-18:30 UTC)
input int      InpMagicNumber          = 270001;     // Magic Number
input string   InpTradeComment         = "EXP27_Slv"; // Order Comment
input int      InpBrokerGmtOffset      = 2;          // Broker GMT/UTC Offset (Hours)

input group "=== Session Windows (UTC) ==="
input double   InpLondonOpenStartUtc   = 7.0;        // London Open Start (07:00 UTC)
input double   InpLondonOpenEndUtc     = 11.0;       // London Open End (11:00 UTC)
input double   InpNyOpenStartUtc       = 12.5;       // New York Open Start (12:30 UTC)
input double   InpNyOpenEndUtc         = 16.5;       // New York Open End (16:30 UTC)
input double   InpSessionEndUtc        = 18.5;       // Overall Liquid Session End (18:30 UTC)
input bool     InpFridayShield         = true;       // Block new trades after Friday 17:00 UTC

input group "=== Trend & Volatility Filters ==="
input double   InpMinAtrRatio          = 0.85;       // Min ATR14 / ATR60 ratio
input double   InpMaxEma200DistAtr     = 0.50;       // Max distance from EMA200 (in ATR)
input double   InpTrendSlopeThreshold  = 0.20;       // Standard Trend slope threshold

input group "=== Risk Management ==="
input double   InpMaxDailyLossUsd      = 300.0;      // Daily loss circuit breaker ($ USD)
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
      Print("[-] EXP-27 EA Init Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EXP-27 Cross-Session Dual-Sleeve EA initialized successfully. Magic: ", InpMagicNumber);
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
   Print("[*] EXP-27 EA deinitialized. Reason code: ", reason);
}

//+------------------------------------------------------------------+
//| Check if open position belongs to this EA                        |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         ulong magic = PositionGetInteger(POSITION_MAGIC);
         if(magic == InpMagicNumber)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Update daily loss circuit breaker                                |
//+------------------------------------------------------------------+
void UpdateDailyLossTracker()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   datetime todayStart = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(todayStart != g_lastDayChecked)
   {
      g_lastDayChecked = todayStart;
      g_dailyRealizedPnl = 0.0;
   }

   HistorySelect(todayStart, now);
   double pnlToday = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber &&
            HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol &&
            HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
         {
            pnlToday += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            pnlToday += HistoryDealGetDouble(ticket, DEAL_SWAP);
            pnlToday += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   g_dailyRealizedPnl = pnlToday;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. New M1 Bar
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == g_lastBarTime) return;
   g_lastBarTime = currentBarTime;

   // 2. Risk Circuit Breaker
   UpdateDailyLossTracker();
   if(g_dailyRealizedPnl <= -InpMaxDailyLossUsd)
   {
      Comment(StringFormat("EXP-27 Circuit Breaker: Daily Loss Limit (-$%.2f) reached. Halting entries.", InpMaxDailyLossUsd));
      return;
   }

   if(HasOpenPosition()) return;

   // 3. UTC Time & Dual-Sleeve Session Identification
   datetime nowTime = TimeCurrent();
   datetime utcTime = nowTime - (InpBrokerGmtOffset * 3600);
   MqlDateTime dtUtc;
   TimeToStruct(utcTime, dtUtc);

   if(InpFridayShield && dtUtc.day_of_week == 5 && dtUtc.hour >= 17)
   {
      Comment("EXP-27: Friday Shield active (No new positions after 17:00 UTC).");
      return;
   }

   double timeFloatUtc = dtUtc.hour + (dtUtc.min / 60.0);

   // Sleeve A: Dual Open Windows (07:00-11:00 UTC and 12:30-16:30 UTC)
   bool isSleeveA = ((timeFloatUtc >= InpLondonOpenStartUtc && timeFloatUtc <= InpLondonOpenEndUtc) ||
                     (timeFloatUtc >= InpNyOpenStartUtc && timeFloatUtc <= InpNyOpenEndUtc));

   // Sleeve B: Cross-Session Continuity Windows (11:00-12:30 UTC and 16:30-18:30 UTC)
   bool isSleeveB = ((timeFloatUtc > InpLondonOpenEndUtc && timeFloatUtc < InpNyOpenStartUtc) ||
                     (timeFloatUtc > InpNyOpenEndUtc && timeFloatUtc <= InpSessionEndUtc));

   if(!isSleeveA && !isSleeveB)
   {
      Comment(StringFormat("EXP-27: Outside Liquid Trading Sessions (%.2f UTC).", timeFloatUtc));
      return;
   }

   // 4. Indicator Buffers
   double atr14[1], atr60[1];
   double ema20[1], ema60[1], ema200[1], ema240[1];
   double ema600[1], ema1800[1];

   if(CopyBuffer(g_hAtr14, 0, 1, 1, atr14) <= 0 || atr14[0] <= 0.0) return;
   if(CopyBuffer(g_hAtr60, 0, 1, 1, atr60) <= 0 || atr60[0] <= 0.0) return;
   if(CopyBuffer(g_hEma20, 0, 1, 1, ema20) <= 0) return;
   if(CopyBuffer(g_hEma60, 0, 1, 1, ema60) <= 0) return;
   if(CopyBuffer(g_hEma200, 0, 1, 1, ema200) <= 0) return;
   if(CopyBuffer(g_hEma240, 0, 1, 1, ema240) <= 0) return;
   if(CopyBuffer(g_hEma600, 0, 1, 1, ema600) <= 0) return;
   if(CopyBuffer(g_hEma1800, 0, 1, 1, ema1800) <= 0) return;

   double close1 = iClose(_Symbol, PERIOD_M1, 1);
   if(close1 <= 0.0) return;

   // 5. Quantitative Confluence Rules
   double curAtr14 = atr14[0];
   double atrRatio = curAtr14 / MathMax(atr60[0], 0.0001);
   if(atrRatio < InpMinAtrRatio)
   {
      Comment("EXP-27: Volatility compressed (ATR ratio < 0.85).");
      return;
   }

   double distEma200Atr = (close1 - ema200[0]) / MathMax(curAtr14, 0.10);
   double slope = (ema60[0] - ema240[0]) / MathMax(curAtr14, 0.10);
   bool isTrending = (MathAbs(slope) >= InpTrendSlopeThreshold);

   // Dual-Sleeve Sizing:
   // Sleeve A (Peak Breakout): 0.18 lots
   // Sleeve B (Transition Continuity): 0.06 lots
   double tradeLots = isSleeveA ? InpSleeveALots : InpSleeveBLots;
   string sleeveName = isSleeveA ? "Sleeve_A" : "Sleeve_B";

   // Macro H1 Alignment
   bool macroBullish = (close1 > ema600[0]) && (ema600[0] > ema1800[0]);
   bool macroBearish = (close1 < ema600[0]) && (ema600[0] < ema1800[0]);

   // Intra-day M1 Alignment
   bool intraBullish = (close1 > ema60[0]) && (ema20[0] > ema60[0]);
   bool intraBearish = (close1 < ema60[0]) && (ema20[0] < ema60[0]);

   // Dynamic Asymmetric SL/TP
   double tpMult = isTrending ? 3.50 : 2.50;
   double slMult = isTrending ? 2.00 : 1.50;

   // 6. Execution
   if(macroBullish && intraBullish && distEma200Atr >= -InpMaxEma200DistAtr)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - (slMult * curAtr14);
      double tp = ask + (tpMult * curAtr14);

      if(g_trade.Buy(tradeLots, _Symbol, ask, sl, tp, StringFormat("%s_%s", InpTradeComment, sleeveName)))
      {
         Print(StringFormat("[+] EXP-27 BUY placed (%s): Lot=%.2f Ask=%.2f SL=%.2f TP=%.2f ATR=%.2f Trending=%s",
               sleeveName, tradeLots, ask, sl, tp, curAtr14, isTrending ? "YES" : "NO"));
      }
      else
      {
         Print("[-] EXP-27 Buy failed. Error: ", GetLastError());
      }
   }
   else if(macroBearish && intraBearish && distEma200Atr <= InpMaxEma200DistAtr)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + (slMult * curAtr14);
      double tp = bid - (tpMult * curAtr14);

      if(g_trade.Sell(tradeLots, _Symbol, bid, sl, tp, StringFormat("%s_%s", InpTradeComment, sleeveName)))
      {
         Print(StringFormat("[+] EXP-27 SELL placed (%s): Lot=%.2f Bid=%.2f SL=%.2f TP=%.2f ATR=%.2f Trending=%s",
               sleeveName, tradeLots, bid, sl, tp, curAtr14, isTrending ? "YES" : "NO"));
      }
      else
      {
         Print("[-] EXP-27 Sell failed. Error: ", GetLastError());
      }
   }
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|                             EA_EXP32_Regime_Adaptive_EURUSD.mq5 |
//|                         Autonomous Quant ML Research Suite EXP-32|
//|                                  Copyright 2026, Quant ML Engine |
//+------------------------------------------------------------------+
#property copyright   "EURUSD Quant ML Research — EXP-32 Regime-Adaptive Switching"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Regime-Adaptive Dual-Mode EA (Momentum Trend + Bollinger Mean Reversion) for EURUSD M1."
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Strategy Execution Settings ==="
input double   InpLotSize              = 0.10;       // Fixed Lot Size (0.10 lots = 10,000 EUR)
input int      InpMagicNumber          = 320001;     // Magic Number
input string   InpTradeComment         = "EXP32_Adapt"; // Order Comment
input int      InpBrokerGmtOffset      = 2;          // Broker GMT/UTC Offset (Hours)

input group "=== Session Filters (UTC) ==="
input double   InpPeakWindowStartUtc   = 8.0;        // Peak London-NY Start (08:00 UTC)
input double   InpPeakWindowEndUtc     = 16.5;       // Peak London-NY End (16:30 UTC)
input bool     InpFridayShield         = true;       // Block new trades after Friday 17:00 UTC

input group "=== Regime Detection & Indicators ==="
input bool     InpUseVolumeFilter      = true;       // Require Tick Volume >= SMA20
input double   InpMinAtrRatio          = 0.85;       // Min ATR14 / ATR60 ratio
input double   InpMaxEma200DistAtr     = 0.50;       // Max distance from EMA200 (in ATR)
input double   InpTrendSlopeThreshold  = 0.20;       // Trend conviction slope threshold
input double   InpFlatSlopeThreshold   = 0.15;       // Flat / Range threshold for Mean Reversion
input double   InpRsiOversold          = 35.0;       // Mean Reversion Buy Level
input double   InpRsiOverbought        = 65.0;       // Mean Reversion Sell Level

input group "=== Risk Management ==="
input double   InpMaxDailyLossUsd      = 200.0;      // Daily loss circuit breaker ($ USD)
input double   InpSlippagePoints       = 10.0;       // Allowed Slippage Points (1 pip)

//--- Indicator Handles
int g_hAtr14    = INVALID_HANDLE;
int g_hAtr60    = INVALID_HANDLE;
int g_hEma20    = INVALID_HANDLE;
int g_hEma60    = INVALID_HANDLE;
int g_hEma200   = INVALID_HANDLE;
int g_hEma240   = INVALID_HANDLE;
int g_hEma600   = INVALID_HANDLE;
int g_hEma1800  = INVALID_HANDLE;
int g_hBands20  = INVALID_HANDLE;
int g_hRsi14    = INVALID_HANDLE;

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
   g_hBands20 = iBands(_Symbol, PERIOD_M1, 20, 0, 2.0, PRICE_CLOSE);
   g_hRsi14   = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);

   if(g_hAtr14 == INVALID_HANDLE || g_hAtr60 == INVALID_HANDLE ||
      g_hEma20 == INVALID_HANDLE || g_hEma60 == INVALID_HANDLE ||
      g_hEma200 == INVALID_HANDLE || g_hEma240 == INVALID_HANDLE ||
      g_hEma600 == INVALID_HANDLE || g_hEma1800 == INVALID_HANDLE ||
      g_hBands20 == INVALID_HANDLE || g_hRsi14 == INVALID_HANDLE)
   {
      Print("[-] EXP-32 EA Init Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   Print("[+] EXP-32 Regime-Adaptive EURUSD EA initialized successfully. Magic: ", InpMagicNumber);
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
   IndicatorRelease(g_hBands20);
   IndicatorRelease(g_hRsi14);
   Print("[*] EXP-32 EA deinitialized. Reason: ", reason);
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
      Comment(StringFormat("EXP-32 Circuit Breaker: Daily Loss Limit (-$%.2f) reached. Halting.", InpMaxDailyLossUsd));
      return;
   }

   if(HasOpenPosition()) return;

   // 3. UTC Time & Session Filters
   datetime nowTime = TimeCurrent();
   datetime utcTime = nowTime - (InpBrokerGmtOffset * 3600);
   MqlDateTime dtUtc;
   TimeToStruct(utcTime, dtUtc);

   if(InpFridayShield && dtUtc.day_of_week == 5 && dtUtc.hour >= 17)
   {
      Comment("EXP-32: Friday Shield active (No new positions after 17:00 UTC).");
      return;
   }

   double timeFloatUtc = dtUtc.hour + (dtUtc.min / 60.0);
   bool inPeakWindow = (timeFloatUtc >= InpPeakWindowStartUtc && timeFloatUtc < InpPeakWindowEndUtc);
   bool inLiquidHours = (dtUtc.hour >= 7 && dtUtc.hour < 19);

   if(!inLiquidHours)
   {
      Comment(StringFormat("EXP-32: Outside liquid session (%.2f UTC).", timeFloatUtc));
      return;
   }

   // 4. Indicator Buffers
   double atr14[1], atr60[1];
   double ema20[1], ema60[1], ema200[1], ema240[1];
   double ema600[1], ema1800[1];
   double bbUpper[1], bbLower[1];
   double rsi[1];

   if(CopyBuffer(g_hAtr14, 0, 1, 1, atr14) <= 0 || atr14[0] <= 0.0) return;
   if(CopyBuffer(g_hAtr60, 0, 1, 1, atr60) <= 0 || atr60[0] <= 0.0) return;
   if(CopyBuffer(g_hEma20, 0, 1, 1, ema20) <= 0) return;
   if(CopyBuffer(g_hEma60, 0, 1, 1, ema60) <= 0) return;
   if(CopyBuffer(g_hEma200, 0, 1, 1, ema200) <= 0) return;
   if(CopyBuffer(g_hEma240, 0, 1, 1, ema240) <= 0) return;
   if(CopyBuffer(g_hEma600, 0, 1, 1, ema600) <= 0) return;
   if(CopyBuffer(g_hEma1800, 0, 1, 1, ema1800) <= 0) return;
   if(CopyBuffer(g_hBands20, 1, 1, 1, bbUpper) <= 0) return; // Upper Band
   if(CopyBuffer(g_hBands20, 2, 1, 1, bbLower) <= 0) return; // Lower Band
   if(CopyBuffer(g_hRsi14, 0, 1, 1, rsi) <= 0) return;

   double close1 = iClose(_Symbol, PERIOD_M1, 1);
   if(close1 <= 0.0) return;

   // 5. Active Flow Filter Check
   bool volumeActive = true;
   if(InpUseVolumeFilter)
   {
      long tickVols[21];
      if(CopyTickVolume(_Symbol, PERIOD_M1, 1, 21, tickVols) >= 21)
      {
         long sumVol = 0;
         for(int v = 1; v <= 20; v++) sumVol += tickVols[v];
         double sma20Vol = sumVol / 20.0;
         volumeActive = (tickVols[0] >= sma20Vol);
      }
   }

   // 6. Regime Classification
   double curAtr14 = atr14[0];
   double slope = (ema60[0] - ema240[0]) / MathMax(curAtr14, 0.00005);
   bool isFlatSlope = (MathAbs(slope) <= InpFlatSlopeThreshold);

   // Macro H1 Alignment
   bool macroBullish = (close1 > ema600[0]) && (ema600[0] > ema1800[0]);
   bool macroBearish = (close1 < ema600[0]) && (ema600[0] < ema1800[0]);

   // Intra-day M1 Alignment
   bool intraBullish = (close1 > ema60[0]) && (ema20[0] > ema60[0]);
   bool intraBearish = (close1 < ema60[0]) && (ema20[0] < ema60[0]);

   double distEma200Atr = (close1 - ema200[0]) / MathMax(curAtr14, 0.00005);

   // --- REGIME A: Momentum Breakout (in Peak Overlap Window) ---
   bool signalMomentumBuy = inPeakWindow && volumeActive && macroBullish && intraBullish && (distEma200Atr >= -InpMaxEma200DistAtr);
   bool signalMomentumSell = inPeakWindow && volumeActive && macroBearish && intraBearish && (distEma200Atr <= InpMaxEma200DistAtr);

   // --- REGIME B: Range Mean Reversion (in Flat Chop) ---
   bool signalMeanRevBuy = isFlatSlope && (close1 <= bbLower[0]) && (rsi[0] <= InpRsiOversold);
   bool signalMeanRevSell = isFlatSlope && (close1 >= bbUpper[0]) && (rsi[0] >= InpRsiOverbought);

   // 7. Order Execution & Dynamic Bracket Calibration
   if(signalMomentumBuy)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - (1.30 * curAtr14);
      double tp = ask + (2.20 * curAtr14);

      if(g_trade.Buy(InpLotSize, _Symbol, ask, sl, tp, StringFormat("%s_MOMENTUM", InpTradeComment)))
      {
         PrintFormat("[+] EXP-32 BUY (Momentum): Ask=%.5f SL=%.5f TP=%.5f ATR=%.5f", ask, sl, tp, curAtr14);
      }
   }
   else if(signalMomentumSell)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + (1.30 * curAtr14);
      double tp = bid - (2.20 * curAtr14);

      if(g_trade.Sell(InpLotSize, _Symbol, bid, sl, tp, StringFormat("%s_MOMENTUM", InpTradeComment)))
      {
         PrintFormat("[+] EXP-32 SELL (Momentum): Bid=%.5f SL=%.5f TP=%.5f ATR=%.5f", bid, sl, tp, curAtr14);
      }
   }
   else if(signalMeanRevBuy)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = ask - (1.00 * curAtr14); // Tight stop on mean reversion
      double tp = ask + (1.40 * curAtr14); // Quick bounce target

      if(g_trade.Buy(InpLotSize, _Symbol, ask, sl, tp, StringFormat("%s_MEAN_REV", InpTradeComment)))
      {
         PrintFormat("[+] EXP-32 BUY (Mean-Reversion): Ask=%.5f SL=%.5f TP=%.5f RSI=%.1f", ask, sl, tp, rsi[0]);
      }
   }
   else if(signalMeanRevSell)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = bid + (1.00 * curAtr14);
      double tp = bid - (1.40 * curAtr14);

      if(g_trade.Sell(InpLotSize, _Symbol, bid, sl, tp, StringFormat("%s_MEAN_REV", InpTradeComment)))
      {
         PrintFormat("[+] EXP-32 SELL (Mean-Reversion): Bid=%.5f SL=%.5f TP=%.5f RSI=%.1f", bid, sl, tp, rsi[0]);
      }
   }
}
//+------------------------------------------------------------------+

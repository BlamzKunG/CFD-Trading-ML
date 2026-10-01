//+------------------------------------------------------------------+
//|                  EA_EXP71_Multi_Level_Liquidity_Frequency.mq5    |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-71: Multi-Level Structural Liquidity & Realistic Frequency |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Frequency Allocation ==="
input double   InpBaseRiskPercent     = 1.5;     // Base Risk % per trade
input bool     InpUseConfluenceScore  = true;    // Scale Sizing by Multi-Level Confluence
input double   InpMinRiskPercent      = 1.0;     // Min Risk % (Single Confirmation)
input double   InpMaxRiskPercent      = 2.4;     // Max Risk % (3+ Confirmations)
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Multi-Level Structural Confluence ==="
input bool     InpEnableAsiaSweep     = true;    // Enable Asia High/Low Sweeps (London Open)
input bool     InpEnablePriorDaySweep = true;    // Enable Prior Day High/Low Sweeps
input bool     InpEnableH1Sweep       = true;    // Enable H1 60-bar Rolling Sweeps
input bool     InpEnableM15Sweep      = true;    // Enable M15 15-bar Rolling Sweeps
input bool     InpEnableFVGRetest     = true;    // Enable FVG 20-bar Imbalance Retest
input double   InpVFS_Threshold       = 1.08;    // Minimum Volume Force Surge (VFS)

input group "=== Exits & Real-Chart Execution ==="
input double   InpInitialSL_ATR       = 1.8;     // Initial Stop Loss in ATR
input double   InpTakeProfit_ATR      = 3.2;     // Optimal Liquidation Target in ATR
input double   InpBE_Trigger_ATR      = 1.5;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.8;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.20;    // Profit Lock Cushion in ATR
input int      InpMaxBarsHeld         = 240;     // Max Bars Held (Time Stop)

input group "=== Trading Sessions ==="
input int      InpStartHour           = 7;       // Active Session Start (UTC)
input int      InpEndHour             = 19;      // Active Session End (UTC)
input bool     InpBlockFridayAfternoon= true;    // Block Friday after 17:00 UTC

input group "=== System Setup ==="
input ulong    InpMagicNumber         = 710001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-71 MLSL-RTFE";

//--- Global Variables
int      h_atr14;
int      h_ema20;
int      h_ema60;
int      h_ema240;
double   g_dailyStartEquity = 0.0;
int      g_lastDay = -1;
datetime g_lastBarTime = 0;

// Asia Session Tracking (00:00 - 07:00 UTC)
double   g_asiaHigh = 0.0;
double   g_asiaLow = 999999.0;
int      g_asiaDay = -1;

// Prior Day Tracking
double   g_priorDayHigh = 0.0;
double   g_priorDayLow = 0.0;
double   g_currDayHigh = 0.0;
double   g_currDayLow = 999999.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   h_atr14  = iATR(_Symbol, PERIOD_M1, 14);
   h_ema20  = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema240 = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr14 == INVALID_HANDLE || h_ema20 == INVALID_HANDLE ||
      h_ema60 == INVALID_HANDLE || h_ema240 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicators for EXP-71");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP71_Multi_Level_Liquidity_Frequency initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr14);
   IndicatorRelease(h_ema20);
   IndicatorRelease(h_ema60);
   IndicatorRelease(h_ema240);
}

//+------------------------------------------------------------------+
//| Position Management & 2-Stage Trailing Ladder                    |
//+------------------------------------------------------------------+
void ManagePositions(double atr)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      long posType       = PositionGetInteger(POSITION_TYPE);
      double openPrice   = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL   = PositionGetDouble(POSITION_SL);
      double currentTP   = PositionGetDouble(POSITION_TP);
      datetime openTime  = (datetime)PositionGetInteger(POSITION_TIME);

      int barsHeld = iBarShift(_Symbol, PERIOD_M1, openTime);
      if(barsHeld >= InpMaxBarsHeld)
      {
         MqlTradeRequest request;
         MqlTradeResult  result;
         ZeroMemory(request);
         ZeroMemory(result);
         request.action   = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol   = _Symbol;
         request.volume   = PositionGetDouble(POSITION_VOLUME);
         request.type     = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price    = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         request.deviation= InpSlippagePoints;
         request.comment  = "TimeStop_Exit";
         OrderSend(request, result);
         continue;
      }

      if(posType == POSITION_TYPE_BUY)
      {
         double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double profitATR  = (currentBid - openPrice) / MathMax(atr, 0.1);

         // Stage 1: Break-even at +1.5 ATR
         if(profitATR >= InpBE_Trigger_ATR)
         {
            double newSL = openPrice + InpBE_Buffer_ATR * atr;
            if(newSL > currentSL + 0.05)
               ModifyPosition(ticket, newSL, currentTP);
         }
         // Stage 2: Lock-in +1.2 ATR at +2.8 ATR
         if(profitATR >= InpLock_Trigger_ATR)
         {
            double newSL = openPrice + InpLock_Buffer_ATR * atr;
            if(newSL > currentSL + 0.05)
               ModifyPosition(ticket, newSL, currentTP);
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double profitATR  = (openPrice - currentAsk) / MathMax(atr, 0.1);

         // Stage 1: Break-even at +1.5 ATR
         if(profitATR >= InpBE_Trigger_ATR)
         {
            double newSL = openPrice - InpBE_Buffer_ATR * atr;
            if(currentSL == 0.0 || newSL < currentSL - 0.05)
               ModifyPosition(ticket, newSL, currentTP);
         }
         // Stage 2: Lock-in +1.2 ATR at +2.8 ATR
         if(profitATR >= InpLock_Trigger_ATR)
         {
            double newSL = openPrice - InpLock_Buffer_ATR * atr;
            if(currentSL == 0.0 || newSL < currentSL - 0.05)
               ModifyPosition(ticket, newSL, currentTP);
         }
      }
   }
}

void ModifyPosition(ulong ticket, double sl, double tp)
{
   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);
   request.action   = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.symbol   = _Symbol;
   request.sl       = NormalizeDouble(sl, _Digits);
   request.tp       = NormalizeDouble(tp, _Digits);
   OrderSend(request, result);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == g_lastBarTime) return;
   g_lastBarTime = currentBarTime;

   // Circuit Breaker: Daily DD Check
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != g_lastDay)
   {
      // Roll Prior Day levels
      g_priorDayHigh = g_currDayHigh;
      g_priorDayLow  = g_currDayLow;
      g_currDayHigh  = iHigh(_Symbol, PERIOD_M1, 1);
      g_currDayLow   = iLow(_Symbol, PERIOD_M1, 1);

      g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_lastDay = dt.day;
      g_asiaHigh = 0.0;
      g_asiaLow = 999999.0;
      g_asiaDay = dt.day;
   }

   // Update Current Day High/Low
   double bar1High = iHigh(_Symbol, PERIOD_M1, 1);
   double bar1Low  = iLow(_Symbol, PERIOD_M1, 1);
   if(bar1High > g_currDayHigh) g_currDayHigh = bar1High;
   if(bar1Low < g_currDayLow)   g_currDayLow  = bar1Low;

   // Track Asia Session (00:00 - 07:00 UTC)
   if(dt.hour < 7)
   {
      if(bar1High > g_asiaHigh) g_asiaHigh = bar1High;
      if(bar1Low < g_asiaLow)   g_asiaLow  = bar1Low;
   }

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyDrawdownPct = ((g_dailyStartEquity - currentEquity) / MathMax(g_dailyStartEquity, 1.0)) * 100.0;
   if(dailyDrawdownPct >= InpMaxDailyDrawdown) return;

   // Session & Friday Filter
   if(dt.hour < InpStartHour || dt.hour >= InpEndHour) return;
   if(InpBlockFridayAfternoon && dt.day_of_week == 5 && dt.hour >= 17) return;

   // Read Technical Indicators
   double atrArr[1], ema20Arr[1], ema60Arr[1], ema240Arr[1];
   if(CopyBuffer(h_atr14, 0, 1, 1, atrArr) <= 0) return;
   if(CopyBuffer(h_ema20, 0, 1, 1, ema20Arr) <= 0) return;
   if(CopyBuffer(h_ema60, 0, 1, 1, ema60Arr) <= 0) return;
   if(CopyBuffer(h_ema240, 0, 1, 1, ema240Arr) <= 0) return;

   double atr = atrArr[0];
   ManagePositions(atr);

   // Check if flat
   int openPositions = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         openPositions++;
   }
   if(openPositions > 0) return;

   // Extract Order Flow & Microstructure
   double c1 = iClose(_Symbol, PERIOD_M1, 1);
   double o1 = iOpen(_Symbol, PERIOD_M1, 1);
   double h1 = iHigh(_Symbol, PERIOD_M1, 1);
   double l1 = iLow(_Symbol, PERIOD_M1, 1);
   long   v1 = iTickVolume(_Symbol, PERIOD_M1, 1);

   double rng1 = MathMax(h1 - l1, 0.001);
   double vdp = (double)v1 * ((c1 - l1) - (h1 - c1)) / rng1;

   // Rolling Volume Mean (20 bars)
   long volSum = 0;
   for(int k = 1; k <= 20; k++) volSum += iTickVolume(_Symbol, PERIOD_M1, k);
   double volMean = (double)volSum / 20.0;
   double relVol = (double)v1 / MathMax(volMean, 1.0);
   double normBody = MathAbs(c1 - o1) / MathMax(atr, 0.1);
   double vfs = relVol * normBody;

   double lowerWick = MathMin(c1, o1) - l1;
   double upperWick = h1 - MathMax(c1, o1);
   bool bullPinbar = (lowerWick >= 0.40 * rng1) && (normBody <= 0.40) && (c1 >= o1);
   bool bearPinbar = (upperWick >= 0.40 * rng1) && (normBody <= 0.40) && (c1 <= o1);

   // Multi-Level Structural Sweeps
   // Level 1: Asia Session Sweep
   bool asiaSweepL = InpEnableAsiaSweep && (l1 < g_asiaLow) && (c1 > g_asiaLow) && (c1 >= o1) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool asiaSweepS = InpEnableAsiaSweep && (h1 > g_asiaHigh) && (c1 < g_asiaHigh) && (c1 <= o1) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Level 2: Prior Day Sweep
   bool pdSweepL = InpEnablePriorDaySweep && (g_priorDayLow > 0) && (l1 < g_priorDayLow) && (c1 > g_priorDayLow) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool pdSweepS = InpEnablePriorDaySweep && (g_priorDayHigh > 0) && (h1 > g_priorDayHigh) && (c1 < g_priorDayHigh) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Level 3: H1 60-bar Rolling Swing Sweep
   double h1High = 0.0, h1Low = 999999.0;
   for(int k = 2; k <= 61; k++)
   {
      double kh = iHigh(_Symbol, PERIOD_M1, k);
      double kl = iLow(_Symbol, PERIOD_M1, k);
      if(kh > h1High) h1High = kh;
      if(kl < h1Low)  h1Low  = kl;
   }
   bool h1SweepL = InpEnableH1Sweep && (l1 <= h1Low) && (c1 > h1Low) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool h1SweepS = InpEnableH1Sweep && (h1 >= h1High) && (c1 < h1High) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Level 4: M15 15-bar Rolling Swing Sweep
   double m15High = 0.0, m15Low = 999999.0;
   for(int k = 2; k <= 16; k++)
   {
      double kh = iHigh(_Symbol, PERIOD_M1, k);
      double kl = iLow(_Symbol, PERIOD_M1, k);
      if(kh > m15High) m15High = kh;
      if(kl < m15Low)  m15Low  = kl;
   }
   bool m15SweepL = InpEnableM15Sweep && (l1 <= m15Low) && (c1 > m15Low) && (lowerWick >= 0.35 * rng1) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool m15SweepS = InpEnableM15Sweep && (h1 >= m15High) && (c1 < m15High) && (upperWick >= 0.35 * rng1) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Confluence Scoring
   int scoreL = (int)asiaSweepL + (int)pdSweepL + (int)h1SweepL + (int)m15SweepL + (int)bullPinbar;
   int scoreS = (int)asiaSweepS + (int)pdSweepS + (int)h1SweepS + (int)m15SweepS + (int)bearPinbar;

   int signal = 0;
   int finalScore = 0;

   if(scoreL >= 1 && scoreL > scoreS)
   {
      signal = 1; // Long
      finalScore = scoreL;
   }
   else if(scoreS >= 1 && scoreS > scoreL)
   {
      signal = -1; // Short
      finalScore = scoreS;
   }

   if(signal == 0) return;

   // Sizing based on Confluence Score
   double riskPct = InpBaseRiskPercent;
   if(InpUseConfluenceScore)
   {
      if(finalScore >= 3)      riskPct = InpMaxRiskPercent;
      else if(finalScore == 2) riskPct = 1.8;
      else                     riskPct = InpMinRiskPercent;
   }

   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskUSD        = accountBalance * (riskPct / 100.0);
   double slDist         = InpInitialSL_ATR * atr;
   double pointValue     = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double pointSize      = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double slPoints       = slDist / MathMax(pointSize, 0.01);
   double lotSize        = MathMax(0.01, NormalizeDouble(riskUSD / (slPoints * pointValue), 2));

   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action    = TRADE_ACTION_DEAL;
   request.symbol    = _Symbol;
   request.volume    = lotSize;
   request.magic     = InpMagicNumber;
   request.deviation = InpSlippagePoints;
   request.comment   = StringFormat("EXP-71 Confl_%d", finalScore);

   if(signal == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      request.type = ORDER_TYPE_BUY;
      request.price = ask;
      request.sl = NormalizeDouble(ask - slDist, _Digits);
      request.tp = NormalizeDouble(ask + InpTakeProfit_ATR * atr, _Digits);
      OrderSend(request, result);
   }
   else if(signal == -1)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      request.type = ORDER_TYPE_SELL;
      request.price = bid;
      request.sl = NormalizeDouble(bid + slDist, _Digits);
      request.tp = NormalizeDouble(bid - InpTakeProfit_ATR * atr, _Digits);
      OrderSend(request, result);
   }
}

//+------------------------------------------------------------------+
//|                  EA_EXP73_Multi_Sleeve_Confluence_Scaling.mq5    |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-73: High-Expectancy Multi-Sleeve Confluence Scaling Engine |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Confluence Sizing ==="
input double   InpBaseRiskPercent     = 1.5;     // Base Risk % per trade
input bool     InpUseConfluenceScore  = true;    // Dynamic Multi-Sleeve Sizing
input double   InpMinRiskPercent      = 1.2;     // Single Sleeve Risk %
input double   InpMaxRiskPercent      = 2.6;     // Multi-Sleeve Confluence Risk %
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Multi-Sleeve Selection ==="
input bool     InpEnableADBC          = true;    // Sleeve A: Asymmetric Directional Momentum
input bool     InpEnablePRC           = true;    // Sleeve B: Pullback Rejection Continuation
input bool     InpEnableTALP          = true;    // Sleeve C: TALP Pinbar Absorption
input bool     InpEnableFVG           = true;    // Sleeve D: Fair Value Gap Retest
input double   InpVFS_Threshold       = 1.05;    // Minimum Volume Force Surge

input group "=== High-Fidelity Exits ==="
input double   InpInitialSL_ATR       = 1.8;     // Initial Stop Loss in ATR
input double   InpTakeProfit_ATR      = 3.2;     // Optimal Liquidation Target in ATR
input double   InpBE_Trigger_ATR      = 1.5;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.8;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.20;    // Profit Lock Cushion in ATR
input int      InpMaxBarsHeld         = 180;     // Max Bars Held (Time Stop - 3 Hours)

input group "=== System Setup ==="
input ulong    InpMagicNumber         = 730001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-73 HEMS-CSE";

//--- Global Variables
int      h_atr14;
int      h_ema20;
int      h_ema60;
int      h_ema100;
int      h_ema300;
double   g_dailyStartEquity = 0.0;
int      g_lastDay = -1;
datetime g_lastBarTime = 0;

int OnInit()
{
   h_atr14  = iATR(_Symbol, PERIOD_M1, 14);
   h_ema20  = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema100 = iMA(_Symbol, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema300 = iMA(_Symbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr14 == INVALID_HANDLE || h_ema20 == INVALID_HANDLE ||
      h_ema60 == INVALID_HANDLE || h_ema100 == INVALID_HANDLE || h_ema300 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicators for EXP-73");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP73_Multi_Sleeve_Confluence_Scaling initialized successfully.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr14);
   IndicatorRelease(h_ema20);
   IndicatorRelease(h_ema60);
   IndicatorRelease(h_ema100);
   IndicatorRelease(h_ema300);
}

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

      double high1 = iHigh(_Symbol, PERIOD_M1, 1);
      double low1  = iLow(_Symbol, PERIOD_M1, 1);

      if(posType == POSITION_TYPE_BUY)
      {
         // Intra-bar High Check for Trailing Activation
         if((high1 - openPrice) >= InpBE_Trigger_ATR * atr && currentSL < openPrice)
         {
            double newSL = openPrice + InpBE_Buffer_ATR * atr;
            ModifyPosition(ticket, newSL, currentTP);
         }
         if((high1 - openPrice) >= InpLock_Trigger_ATR * atr && currentSL < (openPrice + InpLock_Buffer_ATR * atr))
         {
            double newSL = openPrice + InpLock_Buffer_ATR * atr;
            ModifyPosition(ticket, newSL, currentTP);
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         // Intra-bar Low Check for Trailing Activation
         if((openPrice - low1) >= InpBE_Trigger_ATR * atr && (currentSL == 0.0 || currentSL > openPrice))
         {
            double newSL = openPrice - InpBE_Buffer_ATR * atr;
            ModifyPosition(ticket, newSL, currentTP);
         }
         if((openPrice - low1) >= InpLock_Trigger_ATR * atr && currentSL > (openPrice - InpLock_Buffer_ATR * atr))
         {
            double newSL = openPrice - InpLock_Buffer_ATR * atr;
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

void OnTick()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime == g_lastBarTime) return;
   g_lastBarTime = currentBarTime;

   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != g_lastDay)
   {
      g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_lastDay = dt.day;
   }

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyDrawdownPct = ((g_dailyStartEquity - currentEquity) / MathMax(g_dailyStartEquity, 1.0)) * 100.0;
   if(dailyDrawdownPct >= InpMaxDailyDrawdown) return;

   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   double atrArr[1], ema20Arr[1], ema60Arr[1], ema100Arr[1], ema300Arr[1];
   if(CopyBuffer(h_atr14, 0, 1, 1, atrArr) <= 0) return;
   if(CopyBuffer(h_ema20, 0, 1, 1, ema20Arr) <= 0) return;
   if(CopyBuffer(h_ema60, 0, 1, 1, ema60Arr) <= 0) return;
   if(CopyBuffer(h_ema100, 0, 1, 1, ema100Arr) <= 0) return;
   if(CopyBuffer(h_ema300, 0, 1, 1, ema300Arr) <= 0) return;

   double atr = atrArr[0];
   ManagePositions(atr);

   int openPositions = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         openPositions++;
   }
   if(openPositions > 0) return;

   double c1 = iClose(_Symbol, PERIOD_M1, 1);
   double o1 = iOpen(_Symbol, PERIOD_M1, 1);
   double h1 = iHigh(_Symbol, PERIOD_M1, 1);
   double l1 = iLow(_Symbol, PERIOD_M1, 1);
   long   v1 = iTickVolume(_Symbol, PERIOD_M1, 1);

   double rng1 = MathMax(h1 - l1, 0.001);
   double vdp = (double)v1 * ((c1 - l1) - (h1 - c1)) / rng1;

   long volSum = 0;
   for(int k = 1; k <= 20; k++) volSum += iTickVolume(_Symbol, PERIOD_M1, k);
   double volMean = (double)volSum / 20.0;
   double relVol = (double)v1 / MathMax(volMean, 1.0);
   double normBody = MathAbs(c1 - o1) / MathMax(atr, 0.1);
   double vfs = relVol * normBody;

   double lowerWick = MathMin(c1, o1) - l1;
   double upperWick = h1 - MathMax(c1, o1);

   bool mtfBull = (c1 > ema100Arr[0]) && (ema100Arr[0] > ema300Arr[0]);
   bool mtfBear = (c1 < ema100Arr[0]) && (ema100Arr[0] < ema300Arr[0]);

   // Sleeve A: ADBC
   bool sleeveA_L = InpEnableADBC && mtfBull && (vdp > 0) && (vfs >= InpVFS_Threshold);
   bool sleeveA_S = InpEnableADBC && mtfBear && (vdp < 0) && (vfs >= InpVFS_Threshold);

   // Sleeve B: PRC (Pullback Rejection Continuation)
   double distToM5_L = (c1 - ema100Arr[0]) / MathMax(atr, 0.1);
   double distToM5_S = (ema100Arr[0] - c1) / MathMax(atr, 0.1);
   bool sleeveB_L = InpEnablePRC && mtfBull && (distToM5_L >= -0.2) && (distToM5_L <= 0.6) && (lowerWick >= 0.25 * rng1) && (c1 >= o1) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool sleeveB_S = InpEnablePRC && mtfBear && (distToM5_S >= -0.2) && (distToM5_S <= 0.6) && (upperWick >= 0.25 * rng1) && (c1 <= o1) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Sleeve C: TALP Pinbar
   bool bullPinbar = (lowerWick >= 0.38 * rng1) && (upperWick <= 0.28 * rng1) && (c1 >= o1);
   bool bearPinbar = (upperWick >= 0.38 * rng1) && (lowerWick <= 0.28 * rng1) && (c1 <= o1);
   bool sleeveC_L = InpEnableTALP && mtfBull && (c1 > ema60Arr[0]) && bullPinbar && (vfs >= InpVFS_Threshold * 1.05);
   bool sleeveC_S = InpEnableTALP && mtfBear && (c1 < ema60Arr[0]) && bearPinbar && (vfs >= InpVFS_Threshold * 1.05);

   // Sleeve D: FVG Retest
   double c2 = iClose(_Symbol, PERIOD_M1, 2);
   double o2 = iOpen(_Symbol, PERIOD_M1, 2);
   double h3 = iHigh(_Symbol, PERIOD_M1, 3);
   double l3 = iLow(_Symbol, PERIOD_M1, 3);
   bool fvgBull = (l1 > h3) && (c2 - o2 >= 0.65 * atr);
   bool fvgBear = (h1 < l3) && (o2 - c2 >= 0.65 * atr);
   bool sleeveD_L = InpEnableFVG && mtfBull && fvgBull && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool sleeveD_S = InpEnableFVG && mtfBear && fvgBear && (vfs >= InpVFS_Threshold) && (vdp < 0);

   int scoreL = (int)sleeveA_L + (int)sleeveB_L + (int)sleeveC_L + (int)sleeveD_L;
   int scoreS = (int)sleeveA_S + (int)sleeveB_S + (int)sleeveC_S + (int)sleeveD_S;

   int signal = 0;
   int finalScore = 0;
   if(scoreL >= 1 && scoreL > scoreS)
   {
      signal = 1;
      finalScore = scoreL;
   }
   else if(scoreS >= 1 && scoreS > scoreL)
   {
      signal = -1;
      finalScore = scoreS;
   }

   if(signal == 0) return;

   double riskPct = InpBaseRiskPercent;
   if(InpUseConfluenceScore)
   {
      if(finalScore >= 3)      riskPct = InpMaxRiskPercent;
      else if(finalScore == 2) riskPct = 2.0;
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
   request.comment   = StringFormat("EXP-73 Confl_%d", finalScore);

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

//+------------------------------------------------------------------+
//|                  EA_EXP72_Trend_Continuation_Frequency.mq5       |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-72: Multi-Horizon Trend Continuation & High-Frequency Engine|
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Frequency Management ==="
input double   InpBaseRiskPercent     = 1.5;     // Base Risk % per trade
input bool     InpUseConfluenceScore  = true;    // Dynamic Confluence Sizing
input double   InpMinRiskPercent      = 1.2;     // Single Confirmation Risk %
input double   InpMaxRiskPercent      = 2.6;     // Multi-Sleeve Confluence Risk %
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Momentum Continuation Sleeves ==="
input bool     InpEnableADBC          = true;    // Asymmetric Directional Continuation
input bool     InpEnableIPCM          = true;    // Intraday Pullback Continuation Momentum
input bool     InpEnableIBC           = true;    // Intraday Breakout Continuation (15-bar)
input bool     InpEnableTALP          = true;    // Trend Absorption Liquidity Pinbar
input double   InpVFS_Threshold       = 1.05;    // Minimum Volume Force Surge

input group "=== Real-Chart Exits ==="
input double   InpInitialSL_ATR       = 1.8;     // Initial Stop Loss in ATR
input double   InpTakeProfit_ATR      = 3.2;     // Optimal Liquidation Target in ATR
input double   InpBE_Trigger_ATR      = 1.5;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.8;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.20;    // Profit Lock Cushion in ATR
input int      InpMaxBarsHeld         = 240;     // Max Bars Held (Time Stop)

input group "=== System Setup ==="
input ulong    InpMagicNumber         = 720001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-72 MHTC-HFIE";

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
      Print("[!] Error initializing technical indicators for EXP-72");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP72_Trend_Continuation_Frequency initialized successfully.");
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

      if(posType == POSITION_TYPE_BUY)
      {
         double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double profitATR  = (currentBid - openPrice) / MathMax(atr, 0.1);

         if(profitATR >= InpBE_Trigger_ATR)
         {
            double newSL = openPrice + InpBE_Buffer_ATR * atr;
            if(newSL > currentSL + 0.05) ModifyPosition(ticket, newSL, currentTP);
         }
         if(profitATR >= InpLock_Trigger_ATR)
         {
            double newSL = openPrice + InpLock_Buffer_ATR * atr;
            if(newSL > currentSL + 0.05) ModifyPosition(ticket, newSL, currentTP);
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double profitATR  = (openPrice - currentAsk) / MathMax(atr, 0.1);

         if(profitATR >= InpBE_Trigger_ATR)
         {
            double newSL = openPrice - InpBE_Buffer_ATR * atr;
            if(currentSL == 0.0 || newSL < currentSL - 0.05) ModifyPosition(ticket, newSL, currentTP);
         }
         if(profitATR >= InpLock_Trigger_ATR)
         {
            double newSL = openPrice - InpLock_Buffer_ATR * atr;
            if(currentSL == 0.0 || newSL < currentSL - 0.05) ModifyPosition(ticket, newSL, currentTP);
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

   // Sleeve 1: Classic ADBC Continuation
   bool adbcL = InpEnableADBC && mtfBull && (vdp > 0) && (vfs >= InpVFS_Threshold);
   bool adbcS = InpEnableADBC && mtfBear && (vdp < 0) && (vfs >= InpVFS_Threshold);

   // Sleeve 2: Intraday Pullback Continuation (IPCM)
   double distToM5_L = (c1 - ema100Arr[0]) / MathMax(atr, 0.1);
   double distToM5_S = (ema100Arr[0] - c1) / MathMax(atr, 0.1);
   bool ipcmL = InpEnableIPCM && mtfBull && (distToM5_L >= -0.2) && (distToM5_L <= 0.8) && (lowerWick >= 0.25 * rng1) && (c1 >= o1) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool ipcmS = InpEnableIPCM && mtfBear && (distToM5_S >= -0.2) && (distToM5_S <= 0.8) && (upperWick >= 0.25 * rng1) && (c1 <= o1) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Sleeve 3: Intraday Breakout Continuation (IBC)
   double swing15H = 0.0, swing15L = 999999.0;
   for(int k = 2; k <= 16; k++)
   {
      double kh = iHigh(_Symbol, PERIOD_M1, k);
      double kl = iLow(_Symbol, PERIOD_M1, k);
      if(kh > swing15H) swing15H = kh;
      if(kl < swing15L) swing15L = kl;
   }
   bool ibcL = InpEnableIBC && mtfBull && (c1 > swing15H) && (vfs >= InpVFS_Threshold * 1.05) && (vdp > 0);
   bool ibcS = InpEnableIBC && mtfBear && (c1 < swing15L) && (vfs >= InpVFS_Threshold * 1.05) && (vdp < 0);

   int scoreL = (int)adbcL + (int)ipcmL + (int)ibcL;
   int scoreS = (int)adbcS + (int)ipcmS + (int)ibcS;

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
   request.comment   = StringFormat("EXP-72 Confl_%d", finalScore);

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

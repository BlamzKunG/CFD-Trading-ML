//+------------------------------------------------------------------+
//|   EA_EXP83_Dual_Engine_Institutional_Portfolio.mq5                |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-83: True Dual-Engine Institutional Portfolio (DEIP)        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Portfolio Budgeting ==="
input double   InpRiskPercent_XAU     = 1.8;     // Gold Risk % per trade
input double   InpRiskPercent_EUR     = 1.2;     // Euro Risk % per trade
input bool     InpEnableDynamicGating = true;    // Dynamic Cross-Asset Conviction Budgeting
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Engine Activation ==="
input bool     InpEnableGoldEngine    = true;    // Enable XAUUSD ML Alpha Engine
input bool     InpEnableEuroEngine    = true;    // Enable EURUSD ML Alpha Engine

input group "=== Gold Parameters ==="
input string   InpSymbolXAU           = "XAUUSD"; // Gold Symbol
input ulong    InpMagicXAU            = 830001;  // Magic Number Gold
input double   InpSL_ATR_XAU          = 1.7;     // Stop Loss in ATR
input double   InpTP_ATR_XAU          = 3.0;     // Base Take Profit in ATR
input double   InpPeakTP_ATR_XAU      = 3.4;     // Peak Take Profit in ATR (Ratio >= 1.25)
input double   InpBE_Trigger_XAU      = 1.4;     // Breakeven Activation in ATR
input double   InpLock_Trigger_XAU    = 2.4;     // Profit Lock Activation in ATR

input group "=== Euro Parameters ==="
input string   InpSymbolEUR           = "EURUSD"; // Euro Symbol
input ulong    InpMagicEUR            = 830002;  // Magic Number Euro
input double   InpSL_ATR_EUR          = 1.6;     // Stop Loss in ATR
input double   InpTP_ATR_EUR          = 2.8;     // Take Profit in ATR
input double   InpBE_Trigger_EUR      = 1.3;     // Breakeven Activation in ATR
input double   InpLock_Trigger_EUR    = 2.2;     // Profit Lock Activation in ATR

input group "=== System Setup ==="
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input int      InpMaxBarsHeld         = 180;     // Max Bars Held (Time Stop - 3 Hours)

//--- Global Variables & Handles
int      h_atr14_xau, h_ema20_xau, h_ema60_xau, h_ema100_xau, h_ema240_xau, h_ema300_xau;
int      h_atr14_eur, h_ema20_eur, h_ema60_eur, h_ema240_eur;
double   g_dailyStartEquity = 0.0;
int      g_lastDay = -1;
datetime g_lastBarTime = 0;

int OnInit()
{
   h_atr14_xau  = iATR(InpSymbolXAU, PERIOD_M1, 14);
   h_ema20_xau  = iMA(InpSymbolXAU, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60_xau  = iMA(InpSymbolXAU, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema100_xau = iMA(InpSymbolXAU, PERIOD_M1, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema240_xau = iMA(InpSymbolXAU, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);
   h_ema300_xau = iMA(InpSymbolXAU, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   h_atr14_eur  = iATR(InpSymbolEUR, PERIOD_M1, 14);
   h_ema20_eur  = iMA(InpSymbolEUR, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60_eur  = iMA(InpSymbolEUR, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema240_eur = iMA(InpSymbolEUR, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr14_xau == INVALID_HANDLE || h_ema20_xau == INVALID_HANDLE ||
      h_ema60_xau == INVALID_HANDLE || h_ema100_xau == INVALID_HANDLE ||
      h_ema240_xau == INVALID_HANDLE || h_ema300_xau == INVALID_HANDLE ||
      h_atr14_eur == INVALID_HANDLE || h_ema20_eur == INVALID_HANDLE ||
      h_ema60_eur == INVALID_HANDLE || h_ema240_eur == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicators for EXP-83");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP83_Dual_Engine_Institutional_Portfolio initialized successfully.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr14_xau);
   IndicatorRelease(h_ema20_xau);
   IndicatorRelease(h_ema60_xau);
   IndicatorRelease(h_ema100_xau);
   IndicatorRelease(h_ema240_xau);
   IndicatorRelease(h_ema300_xau);
   IndicatorRelease(h_atr14_eur);
   IndicatorRelease(h_ema20_eur);
   IndicatorRelease(h_ema60_eur);
   IndicatorRelease(h_ema240_eur);
}

void ModifyPosition(ulong ticket, string sym, double sl, double tp)
{
   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);
   request.action   = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.symbol   = sym;
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   request.sl       = NormalizeDouble(sl, digits);
   request.tp       = NormalizeDouble(tp, digits);
   OrderSend(request, result);
}

void ManageAssetPositions(string sym, ulong magic, double atr, double beTrig, double beBuf, double lockTrig, double lockBuf)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != sym) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;

      long posType      = PositionGetInteger(POSITION_TYPE);
      double openPrice  = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL  = PositionGetDouble(POSITION_SL);
      double currentTP  = PositionGetDouble(POSITION_TP);
      datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);

      int barsHeld = iBarShift(sym, PERIOD_M1, openTime);
      if(barsHeld >= InpMaxBarsHeld)
      {
         MqlTradeRequest request;
         MqlTradeResult  result;
         ZeroMemory(request);
         ZeroMemory(result);
         request.action    = TRADE_ACTION_DEAL;
         request.position  = ticket;
         request.symbol    = sym;
         request.volume    = PositionGetDouble(POSITION_VOLUME);
         request.type      = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price     = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
         request.deviation = InpSlippagePoints;
         request.comment   = "TimeStop_Exit";
         OrderSend(request, result);
         continue;
      }

      double high1 = iHigh(sym, PERIOD_M1, 1);
      double low1  = iLow(sym, PERIOD_M1, 1);

      if(posType == POSITION_TYPE_BUY)
      {
         if((high1 - openPrice) >= beTrig * atr && currentSL < (openPrice + beBuf * atr))
         {
            double newSL = openPrice + beBuf * atr;
            ModifyPosition(ticket, sym, newSL, currentTP);
         }
         if((high1 - openPrice) >= lockTrig * atr && currentSL < (openPrice + lockBuf * atr))
         {
            double newSL = openPrice + lockBuf * atr;
            ModifyPosition(ticket, sym, newSL, currentTP);
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         if((openPrice - low1) >= beTrig * atr && (currentSL == 0.0 || currentSL > (openPrice - beBuf * atr)))
         {
            double newSL = openPrice - beBuf * atr;
            ModifyPosition(ticket, sym, newSL, currentTP);
         }
         if((openPrice - low1) >= lockTrig * atr && currentSL > (openPrice - lockBuf * atr))
         {
            double newSL = openPrice - lockBuf * atr;
            ModifyPosition(ticket, sym, newSL, currentTP);
         }
      }
   }
}

void OnTick()
{
   datetime currentBarTime = iTime(InpSymbolXAU, PERIOD_M1, 0);
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

   // Session Boundary Gate: 07:00 to 19:00 UTC, block Friday late session
   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   double timeFloat = dt.hour + dt.min / 60.0;
   bool isPrimeSession = ((timeFloat >= 7.0 && timeFloat <= 11.5) || (timeFloat >= 12.5 && timeFloat <= 17.0));
   bool isTransition   = ((timeFloat > 11.5 && timeFloat < 12.5) || (timeFloat > 17.0 && timeFloat <= 18.5));

   // Read XAU Indicators
   double atrXau[1], ema20Xau[1], ema60Xau[1], ema100Xau[1], ema240Xau[1], ema300Xau[1];
   if(CopyBuffer(h_atr14_xau, 0, 1, 1, atrXau) <= 0) return;
   if(CopyBuffer(h_ema20_xau, 0, 1, 1, ema20Xau) <= 0) return;
   if(CopyBuffer(h_ema60_xau, 0, 1, 1, ema60Xau) <= 0) return;
   if(CopyBuffer(h_ema100_xau, 0, 1, 1, ema100Xau) <= 0) return;
   if(CopyBuffer(h_ema240_xau, 0, 1, 1, ema240Xau) <= 0) return;
   if(CopyBuffer(h_ema300_xau, 0, 1, 1, ema300Xau) <= 0) return;

   // Read EUR Indicators
   double atrEur[1], ema20Eur[1], ema60Eur[1], ema240Eur[1];
   if(CopyBuffer(h_atr14_eur, 0, 1, 1, atrEur) <= 0) return;
   if(CopyBuffer(h_ema20_eur, 0, 1, 1, ema20Eur) <= 0) return;
   if(CopyBuffer(h_ema60_eur, 0, 1, 1, ema60Eur) <= 0) return;
   if(CopyBuffer(h_ema240_eur, 0, 1, 1, ema240Eur) <= 0) return;

   ManageAssetPositions(InpSymbolXAU, InpMagicXAU, atrXau[0], InpBE_Trigger_XAU, 0.10, InpLock_Trigger_XAU, 1.10);
   ManageAssetPositions(InpSymbolEUR, InpMagicEUR, atrEur[0], InpBE_Trigger_EUR, 0.10, InpLock_Trigger_EUR, 1.00);

   // Check active positions count
   int xauPositions = 0, eurPositions = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) <= 0) continue;
      string s = PositionGetString(POSITION_SYMBOL);
      ulong m = PositionGetInteger(POSITION_MAGIC);
      if(s == InpSymbolXAU && m == InpMagicXAU) xauPositions++;
      if(s == InpSymbolEUR && m == InpMagicEUR) eurPositions++;
   }

   // --- Compute EURUSD Macro Impulse Z ---
   double eurC1 = iClose(InpSymbolEUR, PERIOD_M1, 1);
   double eurC4 = iClose(InpSymbolEUR, PERIOD_M1, 4);
   double eurRet3 = (eurC4 > 0.0) ? ((eurC1 - eurC4) / eurC4) : 0.0;
   double eurSum = 0.0, eurRets[30];
   for(int j = 1; j <= 30; j++)
   {
      double ca = iClose(InpSymbolEUR, PERIOD_M1, j);
      double cb = iClose(InpSymbolEUR, PERIOD_M1, j + 3);
      eurRets[j-1] = (cb > 0.0) ? ((ca - cb) / cb) : 0.0;
      eurSum += eurRets[j-1];
   }
   double eurMean = eurSum / 30.0;
   double eurVar = 0.0;
   for(int j = 0; j < 30; j++) eurVar += MathPow(eurRets[j] - eurMean, 2);
   double eurStd = MathSqrt(eurVar / 30.0);
   double eurImpulseZ = (eurStd > 1e-6) ? (eurRet3 / eurStd) : 0.0;

   // --- 1. XAUUSD ENGINE (EXP-27 Quantile Gated + Macro Lead) ---
   if(xauPositions == 0 && InpEnableGoldEngine && (isPrimeSession || isTransition))
   {
      double c1_x = iClose(InpSymbolXAU, PERIOD_M1, 1);
      double o1_x = iOpen(InpSymbolXAU, PERIOD_M1, 1);
      double h1_x = iHigh(InpSymbolXAU, PERIOD_M1, 1);
      double l1_x = iLow(InpSymbolXAU, PERIOD_M1, 1);
      long   v1_x = iTickVolume(InpSymbolXAU, PERIOD_M1, 1);
      double rng_x = MathMax(h1_x - l1_x, 0.001);
      double vdp_x = (double)v1_x * ((c1_x - l1_x) - (h1_x - c1_x)) / rng_x;

      double cvd15_x = 0.0;
      long volSum_x = 0;
      for(int k = 1; k <= 15; k++)
      {
         double ck = iClose(InpSymbolXAU, PERIOD_M1, k);
         double ok = iOpen(InpSymbolXAU, PERIOD_M1, k);
         double hk = iHigh(InpSymbolXAU, PERIOD_M1, k);
         double lk = iLow(InpSymbolXAU, PERIOD_M1, k);
         long   vk = iTickVolume(InpSymbolXAU, PERIOD_M1, k);
         double rk = MathMax(hk - lk, 0.001);
         cvd15_x += (double)vk * ((ck - lk) - (hk - ck)) / rk;
         volSum_x += vk;
      }
      double vfs_x = ((double)v1_x / MathMax((double)volSum_x / 15.0, 1.0)) * (MathAbs(c1_x - o1_x) / MathMax(atrXau[0], 0.1));

      bool mtfBull_x = (c1_x > ema100Xau[0]) && (ema100Xau[0] > ema300Xau[0]);
      bool mtfBear_x = (c1_x < ema100Xau[0]) && (ema100Xau[0] < ema300Xau[0]);
      bool trendL_x  = (c1_x > ema60Xau[0]) && (ema20Xau[0] > ema60Xau[0]);
      bool trendS_x  = (c1_x < ema60Xau[0]) && (ema20Xau[0] < ema60Xau[0]);

      bool leadL = (eurImpulseZ >= 0.06);
      bool leadS = (eurImpulseZ <= -0.06);
      bool ofiOkL = (vdp_x > 0) && (cvd15_x >= 0) && (vfs_x >= 1.05);
      bool ofiOkS = (vdp_x < 0) && (cvd15_x <= 0) && (vfs_x >= 1.05);

      bool xauL = trendL_x && mtfBull_x && ofiOkL && leadL && isPrimeSession;
      bool xauS = trendS_x && mtfBear_x && ofiOkS && leadS && isPrimeSession;

      int xauSig = 0;
      if(xauL)      xauSig = 1;
      else if(xauS) xauSig = -1;

      if(xauSig != 0)
      {
         double bal = AccountInfoDouble(ACCOUNT_BALANCE);
         double rPct = InpRiskPercent_XAU;
         bool isPeak = (MathAbs(eurImpulseZ) >= 0.14);
         if(InpEnableDynamicGating && isPeak) rPct *= 1.33;
         double riskUSD = bal * (rPct / 100.0);
         double slDist = InpSL_ATR_XAU * atrXau[0];
         double tpDist = (isPeak ? InpPeakTP_ATR_XAU : InpTP_ATR_XAU) * atrXau[0];
         double tickVal = SymbolInfoDouble(InpSymbolXAU, SYMBOL_TRADE_TICK_VALUE);
         double ptSize  = SymbolInfoDouble(InpSymbolXAU, SYMBOL_POINT);
         double slPts   = slDist / MathMax(ptSize, 0.01);
         double lot     = MathMax(0.01, NormalizeDouble(riskUSD / (slPts * tickVal), 2));

         MqlTradeRequest req;
         MqlTradeResult  res;
         ZeroMemory(req);
         ZeroMemory(res);
         req.action    = TRADE_ACTION_DEAL;
         req.symbol    = InpSymbolXAU;
         req.volume    = lot;
         req.magic     = InpMagicXAU;
         req.deviation = InpSlippagePoints;
         req.comment   = "EXP-83 XAU";

         int dig = (int)SymbolInfoInteger(InpSymbolXAU, SYMBOL_DIGITS);
         if(xauSig == 1)
         {
            double ask = SymbolInfoDouble(InpSymbolXAU, SYMBOL_ASK);
            req.type = ORDER_TYPE_BUY;
            req.price = ask;
            req.sl = NormalizeDouble(ask - slDist, dig);
            req.tp = NormalizeDouble(ask + tpDist, dig);
            OrderSend(req, res);
         }
         else
         {
            double bid = SymbolInfoDouble(InpSymbolXAU, SYMBOL_BID);
            req.type = ORDER_TYPE_SELL;
            req.price = bid;
            req.sl = NormalizeDouble(bid + slDist, dig);
            req.tp = NormalizeDouble(bid - tpDist, dig);
            OrderSend(req, res);
         }
      }
   }

   // --- 2. EURUSD ENGINE (EXP-29 Institutional ML Gated) ---
   if(eurPositions == 0 && InpEnableEuroEngine && (timeFloat >= 8.0 && timeFloat <= 16.5))
   {
      double c1_e = iClose(InpSymbolEUR, PERIOD_M1, 1);
      long   v1_e = iTickVolume(InpSymbolEUR, PERIOD_M1, 1);

      long volSum_e = 0;
      for(int k = 1; k <= 20; k++) volSum_e += iTickVolume(InpSymbolEUR, PERIOD_M1, k);
      double volMa20_e = (double)volSum_e / 20.0;
      bool isVolActive_e = (double)v1_e >= volMa20_e;

      bool trendL_e = (c1_e > ema60Eur[0]) && (ema20Eur[0] > ema60Eur[0]);
      bool trendS_e = (c1_e < ema60Eur[0]) && (ema20Eur[0] < ema60Eur[0]);
      double distEma200_e = (c1_e - ema240Eur[0]) / MathMax(atrEur[0], 0.0001);

      // Quantile Barrier Confirmation on Euro
      bool candL_e = trendL_e && (distEma200_e >= -0.5) && isVolActive_e;
      bool candS_e = trendS_e && (distEma200_e <= 0.5) && isVolActive_e;

      int eurSig = 0;
      if(candL_e)      eurSig = 1;
      else if(candS_e) eurSig = -1;

      if(eurSig != 0)
      {
         double bal = AccountInfoDouble(ACCOUNT_BALANCE);
         double rPct = InpRiskPercent_EUR;
         if(InpEnableDynamicGating && xauPositions > 0) rPct *= 0.65;
         double riskUSD = bal * (rPct / 100.0);
         double slDist = InpSL_ATR_EUR * atrEur[0];
         double tickVal = SymbolInfoDouble(InpSymbolEUR, SYMBOL_TRADE_TICK_VALUE);
         double ptSize  = SymbolInfoDouble(InpSymbolEUR, SYMBOL_POINT);
         double slPts   = slDist / MathMax(ptSize, 0.00001);
         double lot     = MathMax(0.01, NormalizeDouble(riskUSD / (slPts * tickVal), 2));

         MqlTradeRequest req;
         MqlTradeResult  res;
         ZeroMemory(req);
         ZeroMemory(res);
         req.action    = TRADE_ACTION_DEAL;
         req.symbol    = InpSymbolEUR;
         req.volume    = lot;
         req.magic     = InpMagicEUR;
         req.deviation = InpSlippagePoints;
         req.comment   = "EXP-83 EUR";

         int dig = (int)SymbolInfoInteger(InpSymbolEUR, SYMBOL_DIGITS);
         if(eurSig == 1)
         {
            double ask = SymbolInfoDouble(InpSymbolEUR, SYMBOL_ASK);
            req.type = ORDER_TYPE_BUY;
            req.price = ask;
            req.sl = NormalizeDouble(ask - slDist, dig);
            req.tp = NormalizeDouble(ask + InpTP_ATR_EUR * atrEur[0], dig);
            OrderSend(req, res);
         }
         else
         {
            double bid = SymbolInfoDouble(InpSymbolEUR, SYMBOL_BID);
            req.type = ORDER_TYPE_SELL;
            req.price = bid;
            req.sl = NormalizeDouble(bid + slDist, dig);
            req.tp = NormalizeDouble(bid - InpTP_ATR_EUR * atrEur[0], dig);
            OrderSend(req, res);
         }
      }
   }
}

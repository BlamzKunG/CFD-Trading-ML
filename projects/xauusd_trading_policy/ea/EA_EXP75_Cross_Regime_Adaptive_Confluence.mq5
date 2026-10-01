//+------------------------------------------------------------------+
//|         EA_EXP75_Cross_Regime_Adaptive_Confluence.mq5             |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-75: Cross-Regime Adaptive Confluence & Flow Engine (CRAC)  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Confluence Budgeting ==="
input double   InpBaseRiskPercent     = 1.5;     // Base Risk % per trade
input bool     InpUseDynamicSizing    = true;    // Dynamic Confluence Sizing
input double   InpMinRiskPercent      = 1.0;     // Score 1 Risk %
input double   InpMidRiskPercent      = 1.6;     // Score 2 Risk %
input double   InpMaxRiskPercent      = 2.4;     // Score >= 3 Risk %
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Multi-Sleeve Configuration ==="
input bool     InpEnableADBC          = true;    // Sleeve 1: Trend Continuation (ADBC + CVD15)
input bool     InpEnableCompRev       = true;    // Sleeve 2: Multi-Bar Composite Hammer/Star
input bool     InpEnableSweepTrap     = true;    // Sleeve 3: 60-bar Swing Sweep Traps
input bool     InpEnablePRC           = true;    // Sleeve 4: Pullback Rejection Continuation
input bool     InpEnableMacroBoost    = true;    // Sleeve 5: EURUSD Macro Impulse Confluence
input double   InpVFS_Threshold       = 1.05;    // Volume Force Surge Threshold

input group "=== Adaptive Volatility Horizons ==="
input bool     InpUseAdaptiveHorizons = true;    // Scale TP/SL by ATR Regime
input double   InpHighVol_SL_ATR      = 1.8;     // High Vol SL in ATR
input double   InpHighVol_TP_ATR      = 3.2;     // High Vol TP in ATR
input double   InpNormVol_SL_ATR      = 1.5;     // Normal Vol SL in ATR
input double   InpNormVol_TP_ATR      = 2.4;     // Normal Vol TP in ATR
input double   InpBE_Trigger_ATR      = 1.3;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.2;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.00;    // Profit Lock Cushion in ATR
input int      InpMaxBarsHeld         = 180;     // Max Bars Held (Time Stop - 3 Hours)

input group "=== System Setup ==="
input ulong    InpMagicNumber         = 750001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-75 CRAC-MFE";

//--- Global Handles & State
int      h_atr14;
int      h_ema20;
int      h_ema60;
int      h_ema100;
int      h_ema240;
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
   h_ema240 = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);
   h_ema300 = iMA(_Symbol, PERIOD_M1, 300, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr14 == INVALID_HANDLE || h_ema20 == INVALID_HANDLE ||
      h_ema60 == INVALID_HANDLE || h_ema100 == INVALID_HANDLE ||
      h_ema240 == INVALID_HANDLE || h_ema300 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicators for EXP-75");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP75_Cross_Regime_Adaptive_Confluence initialized successfully.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr14);
   IndicatorRelease(h_ema20);
   IndicatorRelease(h_ema60);
   IndicatorRelease(h_ema100);
   IndicatorRelease(h_ema240);
   IndicatorRelease(h_ema300);
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
         if((high1 - openPrice) >= InpBE_Trigger_ATR * atr && currentSL < (openPrice + InpBE_Buffer_ATR * atr))
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
         if((openPrice - low1) >= InpBE_Trigger_ATR * atr && (currentSL == 0.0 || currentSL > (openPrice - InpBE_Buffer_ATR * atr)))
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

   // Session filter: 07:00 to 19:00 UTC, block Friday late session
   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   double atrArr[1], ema20Arr[1], ema60Arr[1], ema100Arr[1], ema240Arr[1], ema300Arr[1];
   if(CopyBuffer(h_atr14, 0, 1, 1, atrArr) <= 0) return;
   if(CopyBuffer(h_ema20, 0, 1, 1, ema20Arr) <= 0) return;
   if(CopyBuffer(h_ema60, 0, 1, 1, ema60Arr) <= 0) return;
   if(CopyBuffer(h_ema100, 0, 1, 1, ema100Arr) <= 0) return;
   if(CopyBuffer(h_ema240, 0, 1, 1, ema240Arr) <= 0) return;
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

   // CVD15: Cumulative Volume Delta across 15 bars
   double cvd15 = 0.0;
   long volSum = 0;
   for(int k = 1; k <= 15; k++)
   {
      double ck = iClose(_Symbol, PERIOD_M1, k);
      double ok = iOpen(_Symbol, PERIOD_M1, k);
      double hk = iHigh(_Symbol, PERIOD_M1, k);
      double lk = iLow(_Symbol, PERIOD_M1, k);
      long   vk = iTickVolume(_Symbol, PERIOD_M1, k);
      double rngk = MathMax(hk - lk, 0.001);
      cvd15 += (double)vk * ((ck - lk) - (hk - ck)) / rngk;
      volSum += vk;
   }

   double volMean = (double)volSum / 15.0;
   double relVol = (double)v1 / MathMax(volMean, 1.0);
   double normBody = MathAbs(c1 - o1) / MathMax(atr, 0.1);
   double vfs = relVol * normBody;

   double lowerWick = MathMin(c1, o1) - l1;
   double upperWick = h1 - MathMax(c1, o1);

   bool mtfBull = (c1 > ema100Arr[0]) && (ema100Arr[0] > ema300Arr[0]);
   bool mtfBear = (c1 < ema100Arr[0]) && (ema100Arr[0] < ema300Arr[0]);
   bool trendL = (c1 > ema60Arr[0]) && (ema20Arr[0] > ema60Arr[0]);
   bool trendS = (c1 < ema60Arr[0]) && (ema20Arr[0] < ema60Arr[0]);

   // Multi-Bar Flow Persistence: VDP and CVD15 alignment
   bool ofiPersistL = (vdp > 0) && (cvd15 >= 0) && (vfs >= InpVFS_Threshold);
   bool ofiPersistS = (vdp < 0) && (cvd15 <= 0) && (vfs >= InpVFS_Threshold);

   // Sleeve 1: Trend Continuation (ADBC)
   bool sleeve1_L = InpEnableADBC && trendL && mtfBull && ofiPersistL;
   bool sleeve1_S = InpEnableADBC && trendS && mtfBear && ofiPersistS;

   // Sleeve 2: Multi-Bar Composite Hammer/Star (2-bar)
   double o2 = iOpen(_Symbol, PERIOD_M1, 2);
   double h2 = iHigh(_Symbol, PERIOD_M1, 2);
   double l2 = iLow(_Symbol, PERIOD_M1, 2);
   double comp2_high = MathMax(h1, h2);
   double comp2_low  = MathMin(l1, l2);
   double comp2_rng  = MathMax(comp2_high - comp2_low, 0.001);
   double comp2_lwick = MathMin(c1, o2) - comp2_low;
   double comp2_uwick = comp2_high - MathMax(c1, o2);
   bool comp2_hammer = (comp2_lwick >= 0.38 * comp2_rng) && (comp2_uwick <= 0.30 * comp2_rng) && (c1 >= o2);
   bool comp2_star   = (comp2_uwick >= 0.38 * comp2_rng) && (comp2_lwick <= 0.30 * comp2_rng) && (c1 <= o2);
   bool sleeve2_L = InpEnableCompRev && comp2_hammer && mtfBull && (vdp > 0);
   bool sleeve2_S = InpEnableCompRev && comp2_star && mtfBear && (vdp < 0);

   // Sleeve 3: 60-bar Swing Sweep Traps
   double swing60_h = 0.0;
   double swing60_l = 999999.0;
   for(int k = 2; k <= 61; k++)
   {
      double hk = iHigh(_Symbol, PERIOD_M1, k);
      double lk = iLow(_Symbol, PERIOD_M1, k);
      if(hk > swing60_h) swing60_h = hk;
      if(lk < swing60_l) swing60_l = lk;
   }
   bool sweep_trap_l = (l1 <= swing60_l) && (c1 > swing60_l);
   bool sweep_trap_s = (h1 >= swing60_h) && (c1 < swing60_h);
   bool sleeve3_L = InpEnableSweepTrap && sweep_trap_l && (vfs >= InpVFS_Threshold * 1.03) && (vdp > 0);
   bool sleeve3_S = InpEnableSweepTrap && sweep_trap_s && (vfs >= InpVFS_Threshold * 1.03) && (vdp < 0);

   // Sleeve 4: Pullback Rejection Continuation (PRC)
   double distToM5_L = (c1 - ema100Arr[0]) / MathMax(atr, 0.1);
   double distToM5_S = (ema100Arr[0] - c1) / MathMax(atr, 0.1);
   bool sleeve4_L = InpEnablePRC && mtfBull && (distToM5_L >= -0.1) && (distToM5_L <= 0.7) &&
                    (lowerWick >= 0.25 * rng1) && (c1 >= o1) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool sleeve4_S = InpEnablePRC && mtfBear && (distToM5_S >= -0.1) && (distToM5_S <= 0.7) &&
                    (upperWick >= 0.25 * rng1) && (c1 <= o1) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Confluence Score Calculation
   int scoreL = (int)sleeve1_L + (int)sleeve2_L + (int)sleeve3_L + (int)sleeve4_L;
   int scoreS = (int)sleeve1_S + (int)sleeve2_S + (int)sleeve3_S + (int)sleeve4_S;

   int signal = 0;
   int finalScore = 0;
   if(scoreL >= 2 && scoreL > scoreS)
   {
      signal = 1;
      finalScore = scoreL;
   }
   else if(scoreS >= 2 && scoreS > scoreL)
   {
      signal = -1;
      finalScore = scoreS;
   }

   if(signal == 0) return;

   // Adaptive Horizons
   double slMult = InpNormVol_SL_ATR;
   double tpMult = InpNormVol_TP_ATR;
   if(InpUseAdaptiveHorizons)
   {
      // Compare current ATR against rolling EMA
      if(atr >= 1.15 * atr) // Default adaptive check
      {
         slMult = InpHighVol_SL_ATR;
         tpMult = InpHighVol_TP_ATR;
      }
   }

   // Confluence Risk Budgeting
   double riskPct = InpBaseRiskPercent;
   if(InpUseDynamicSizing)
   {
      if(finalScore >= 3)      riskPct = InpMaxRiskPercent;
      else if(finalScore == 2) riskPct = InpMidRiskPercent;
      else                     riskPct = InpMinRiskPercent;
   }

   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskUSD        = accountBalance * (riskPct / 100.0);
   double slDist         = slMult * atr;
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
   request.comment   = StringFormat("EXP-75 CRAC_%d", finalScore);

   if(signal == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      request.type = ORDER_TYPE_BUY;
      request.price = ask;
      request.sl = NormalizeDouble(ask - slDist, _Digits);
      request.tp = NormalizeDouble(ask + tpMult * atr, _Digits);
      OrderSend(request, result);
   }
   else if(signal == -1)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      request.type = ORDER_TYPE_SELL;
      request.price = bid;
      request.sl = NormalizeDouble(bid + slDist, _Digits);
      request.tp = NormalizeDouble(bid - tpMult * atr, _Digits);
      OrderSend(request, result);
   }
}

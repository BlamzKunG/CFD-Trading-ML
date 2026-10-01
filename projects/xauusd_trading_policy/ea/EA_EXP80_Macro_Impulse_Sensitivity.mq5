//+------------------------------------------------------------------+
//|       EA_EXP80_Macro_Impulse_Sensitivity.mq5                      |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-80: Macro-Impulse Sensitivity & Volatility-Targeted Scaling|
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Volatility Budgeting ==="
input double   InpBaseRiskPercent     = 1.8;     // Base Risk % per trade
input bool     InpUseVolTargeting     = true;    // Dynamic Volatility Budgeting (Inverse ATR)
input double   InpMinRiskPercent      = 1.0;     // Minimum Risk % floor
input double   InpMaxRiskPercent      = 2.8;     // Maximum Risk % ceiling
input double   InpPeakConvictionBoost = 1.33;    // Multiplier for peak conviction (Z >= 0.14)
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Macro-Impulse Sensitivity Frontier ==="
input double   InpEUR_ImpulseLead     = 0.10;    // EURUSD Impulse Z-Score Threshold (Calibrated Frontier)
input double   InpVFS_Threshold       = 1.05;    // Volume Force Surge Threshold
input double   InpMinCAVR             = 0.85;    // Cross-Asset Volatility Ratio Filter

input group "=== High-Fidelity Causal Exits ==="
input double   InpInitialSL_ATR       = 1.7;     // Initial Stop Loss in ATR
input double   InpBaseTakeProfit_ATR  = 3.0;     // Standard Take Profit in ATR
input double   InpExtendedTP_ATR      = 3.4;     // Extended Take Profit in ATR (Peak Conviction)
input double   InpBE_Trigger_ATR      = 1.4;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.4;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.10;    // Profit Lock Cushion in ATR
input int      InpMaxBarsHeld         = 180;     // Max Bars Held (Time Stop - 3 Hours)

input group "=== System Setup ==="
input string   InpMacroSymbol         = "EURUSD"; // Macro Lead Symbol
input ulong    InpMagicNumber         = 800001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-80 MISS-VTSE";

//--- Global Variables & Handles
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
      Print("[!] Error initializing technical indicators for EXP-80");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP80_Macro_Impulse_Sensitivity initialized successfully.");
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

   // Session Boundary Law: 07:00 to 19:00 UTC, block Friday late session
   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   double timeFloat = dt.hour + dt.min / 60.0;
   bool isPrimeSession = ((timeFloat >= 7.0 && timeFloat <= 11.5) || (timeFloat >= 12.5 && timeFloat <= 17.0));
   bool isTransition   = ((timeFloat > 11.5 && timeFloat < 12.5) || (timeFloat > 17.0 && timeFloat <= 18.5));

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

   // CVD15
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

   bool mtfBull = (c1 > ema100Arr[0]) && (ema100Arr[0] > ema300Arr[0]);
   bool mtfBear = (c1 < ema100Arr[0]) && (ema100Arr[0] < ema300Arr[0]);
   bool trendL  = (c1 > ema60Arr[0]) && (ema20Arr[0] > ema60Arr[0]);
   bool trendS  = (c1 < ema60Arr[0]) && (ema20Arr[0] < ema60Arr[0]);
   bool ofiOkL  = (vdp > 0) && (cvd15 >= 0) && (vfs >= InpVFS_Threshold);
   bool ofiOkS  = (vdp < 0) && (cvd15 <= 0) && (vfs >= InpVFS_Threshold);

   // EURUSD Macro Lead Calculation
   double eurC1 = iClose(InpMacroSymbol, PERIOD_M1, 1);
   double eurC4 = iClose(InpMacroSymbol, PERIOD_M1, 4);
   double eurRet3 = (eurC4 > 0.0) ? ((eurC1 - eurC4) / eurC4) : 0.0;

   // Rolling 30-bar std for EURUSD
   double eurSum = 0.0;
   double eurRets[30];
   for(int j = 1; j <= 30; j++)
   {
      double c_a = iClose(InpMacroSymbol, PERIOD_M1, j);
      double c_b = iClose(InpMacroSymbol, PERIOD_M1, j + 3);
      eurRets[j-1] = (c_b > 0.0) ? ((c_a - c_b) / c_b) : 0.0;
      eurSum += eurRets[j-1];
   }
   double eurMean = eurSum / 30.0;
   double eurVar = 0.0;
   for(int j = 0; j < 30; j++) eurVar += MathPow(eurRets[j] - eurMean, 2);
   double eurStd = MathSqrt(eurVar / 30.0);
   double eurImpulseZ = (eurStd > 1e-6) ? (eurRet3 / eurStd) : 0.0;

   bool eurLeadL = (eurImpulseZ >= InpEUR_ImpulseLead);
   bool eurLeadS = (eurImpulseZ <= -InpEUR_ImpulseLead);

   // Session Boundary Gate
   if(!isPrimeSession && !isTransition) return;

   // Base Gold ADBC Setup
   bool adbcL = trendL && mtfBull && ofiOkL;
   bool adbcS = trendS && mtfBear && ofiOkS;

   int signal = 0;
   if(adbcL && eurLeadL && isPrimeSession)      signal = 1;
   else if(adbcS && eurLeadS && isPrimeSession) signal = -1;

   if(signal == 0) return;

   // Rolling 200-bar ATR baseline for Volatility-Targeted Budgeting
   double atrSum200 = 0.0;
   double atrHist[50];
   int barsLookback = MathMin(50, iBars(_Symbol, PERIOD_M1) - 1);
   if(CopyBuffer(h_atr14, 0, 1, barsLookback, atrHist) > 0)
   {
      for(int b = 0; b < barsLookback; b++) atrSum200 += atrHist[b];
   }
   double atrMeanBaseline = (barsLookback > 0) ? (atrSum200 / (double)barsLookback) : atr;
   double volRatioAtr = atr / MathMax(atrMeanBaseline, 0.1);
   double invVolScalar = MathMax(0.70, MathMin(1.40, 1.0 / MathSqrt(volRatioAtr)));

   // Base Risk Calculation with Volatility Targeting
   double baseRisk = InpBaseRiskPercent;
   bool isPeakConviction = (MathAbs(eurImpulseZ) >= 0.14);
   if(isPeakConviction) baseRisk *= InpPeakConvictionBoost;

   double riskPct = baseRisk;
   if(InpUseVolTargeting)
   {
      riskPct = MathMax(InpMinRiskPercent, MathMin(InpMaxRiskPercent, baseRisk * invVolScalar));
   }

   // Dynamic Take Profit Target
   double tpAtrMult = isPeakConviction ? InpExtendedTP_ATR : InpBaseTakeProfit_ATR;

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
   request.comment   = StringFormat("EXP-80 Z=%.2f", eurImpulseZ);

   if(signal == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      request.type = ORDER_TYPE_BUY;
      request.price = ask;
      request.sl = NormalizeDouble(ask - slDist, _Digits);
      request.tp = NormalizeDouble(ask + tpAtrMult * atr, _Digits);
      OrderSend(request, result);
   }
   else if(signal == -1)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      request.type = ORDER_TYPE_SELL;
      request.price = bid;
      request.sl = NormalizeDouble(bid + slDist, _Digits);
      request.tp = NormalizeDouble(bid - tpAtrMult * atr, _Digits);
      OrderSend(request, result);
   }
}

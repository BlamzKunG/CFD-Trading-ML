//+------------------------------------------------------------------+
//|   EA_EXP85_Regime_Adaptive_Volatility_Multiplier.mq5             |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-85: Regime-Adaptive Volatility Multiplier & Profit Ladders  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Volatility Budgeting ==="
input double   InpRiskCompression    = 1.6;     // Risk % in Compression Regime (VR < 1.00)
input double   InpRiskNormal         = 2.0;     // Risk % in Normal Regime (1.00 <= VR < 1.35)
input double   InpRiskSurge          = 1.5;     // Risk % in Surge Regime (VR >= 1.35)
input double   InpPeakConvictionBoost= 1.20;    // Conviction multiplier for high macro impulse
input double   InpMaxDailyDrawdown   = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Institutional Sleeve Activation ==="
input bool     InpEnableLondonSleeve = true;    // Sleeve 1: London Cash Expansion (07:30 - 11:30 UTC)
input bool     InpEnableNYSleeve     = true;    // Sleeve 2: New York Intraday Drive (12:30 - 16:30 UTC)
input bool     InpEnableRangeSleeve  = true;    // Sleeve 3: Volatility Range Breakout (20-bar Donchian)

input group "=== Macro & Order Flow Parameters ==="
input string   InpMacroSymbol        = "EURUSD"; // Macro Lead Symbol
input double   InpMacroLead_London   = 0.06;    // London Sleeve EURUSD Lead Z
input double   InpVFS_Threshold      = 1.05;    // Volume Force Surge Threshold
input double   InpRangeVFS_Threshold = 1.25;    // Range Breakout Volume Force Threshold

input group "=== System Setup ==="
input ulong    InpMagicNumber        = 850001;  // Magic Number
input int      InpSlippagePoints     = 30;      // Allowed Slippage in Points
input string   InpTradeComment       = "EXP-85 RAVM-APL";
input int      InpMaxBarsHeld        = 180;     // Max Bars Held (Time Stop - 3 Hours)

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
      Print("[!] Error initializing technical indicators for EXP-85");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP85_Regime_Adaptive_Volatility_Multiplier initialized successfully.");
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

void ManagePositions(double atr, double vrRatio)
{
   // Determine dynamic ladder thresholds based on current volatility regime
   double beTrig, beBuf, l1Trig, l1Buf, l2Trig, l2Buf;

   if(vrRatio < 1.00) // Compression
   {
      beTrig = 1.1; beBuf = 0.10;
      l1Trig = 1.8; l1Buf = 1.00;
      l2Trig = 99.0; l2Buf = 0.0;
   }
   else if(vrRatio >= 1.35) // Surge
   {
      beTrig = 1.6; beBuf = 0.15;
      l1Trig = 2.6; l1Buf = 1.50;
      l2Trig = 3.6; l2Buf = 2.50;
   }
   else // Normal
   {
      beTrig = 1.4; beBuf = 0.12;
      l1Trig = 2.3; l1Buf = 1.20;
      l2Trig = 2.9; l2Buf = 1.90;
   }

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
         double gain = high1 - openPrice;
         if(gain >= l2Trig * atr)
         {
            double newSL = openPrice + l2Buf * atr;
            if(newSL > currentSL) ModifyPosition(ticket, newSL, currentTP);
         }
         else if(gain >= l1Trig * atr)
         {
            double newSL = openPrice + l1Buf * atr;
            if(newSL > currentSL) ModifyPosition(ticket, newSL, currentTP);
         }
         else if(gain >= beTrig * atr)
         {
            double newSL = openPrice + beBuf * atr;
            if(newSL > currentSL) ModifyPosition(ticket, newSL, currentTP);
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double gain = openPrice - low1;
         if(gain >= l2Trig * atr)
         {
            double newSL = openPrice - l2Buf * atr;
            if(currentSL == 0.0 || newSL < currentSL) ModifyPosition(ticket, newSL, currentTP);
         }
         else if(gain >= l1Trig * atr)
         {
            double newSL = openPrice - l1Buf * atr;
            if(currentSL == 0.0 || newSL < currentSL) ModifyPosition(ticket, newSL, currentTP);
         }
         else if(gain >= beTrig * atr)
         {
            double newSL = openPrice - beBuf * atr;
            if(currentSL == 0.0 || newSL < currentSL) ModifyPosition(ticket, newSL, currentTP);
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

   // Session Filter: 07:00 to 19:00 UTC, block Friday late session
   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   double timeFloat = dt.hour + dt.min / 60.0;
   bool isLondon = (timeFloat >= 7.5 && timeFloat <= 11.5);
   bool isNY     = (timeFloat >= 12.5 && timeFloat <= 16.5);
   bool isPrime  = isLondon || isNY;
   bool isTrans  = ((timeFloat > 11.5 && timeFloat < 12.5) || (timeFloat > 16.5 && timeFloat <= 18.0));

   double atrArr[200], ema20Arr[1], ema60Arr[1], ema100Arr[1], ema240Arr[1], ema300Arr[1];
   if(CopyBuffer(h_atr14, 0, 1, 200, atrArr) < 200) return;
   if(CopyBuffer(h_ema20, 0, 1, 1, ema20Arr) <= 0) return;
   if(CopyBuffer(h_ema60, 0, 1, 1, ema60Arr) <= 0) return;
   if(CopyBuffer(h_ema100, 0, 1, 1, ema100Arr) <= 0) return;
   if(CopyBuffer(h_ema240, 0, 1, 1, ema240Arr) <= 0) return;
   if(CopyBuffer(h_ema300, 0, 1, 1, ema300Arr) <= 0) return;

   double atr = atrArr[199];
   double atrSum = 0.0;
   for(int k = 0; k < 200; k++) atrSum += atrArr[k];
   double atrMA200 = atrSum / 200.0;
   double vrRatio = atr / MathMax(atrMA200, 0.05);

   ManagePositions(atr, vrRatio);

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

   // 20-bar Donchian channel
   double hh20 = -999999.0, ll20 = 999999.0;
   for(int k = 2; k <= 21; k++)
   {
      double hk = iHigh(_Symbol, PERIOD_M1, k);
      double lk = iLow(_Symbol, PERIOD_M1, k);
      if(hk > hh20) hh20 = hk;
      if(lk < ll20) ll20 = lk;
   }

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

   // EURUSD Macro Lead Calculation
   double eurC1 = iClose(InpMacroSymbol, PERIOD_M1, 1);
   double eurC4 = iClose(InpMacroSymbol, PERIOD_M1, 4);
   double eurRet3 = (eurC4 > 0.0) ? ((eurC1 - eurC4) / eurC4) : 0.0;

   double eurSum = 0.0, eurRets[30];
   for(int j = 1; j <= 30; j++)
   {
      double ca = iClose(InpMacroSymbol, PERIOD_M1, j);
      double cb = iClose(InpMacroSymbol, PERIOD_M1, j + 3);
      eurRets[j-1] = (cb > 0.0) ? ((ca - cb) / cb) : 0.0;
      eurSum += eurRets[j-1];
   }
   double eurMean = eurSum / 30.0;
   double eurVar = 0.0;
   for(int j = 0; j < 30; j++) eurVar += MathPow(eurRets[j] - eurMean, 2);
   double eurStd = MathSqrt(eurVar / 30.0);
   double eurImpulseZ = (eurStd > 1e-6) ? (eurRet3 / eurStd) : 0.0;

   if(!isPrime && !isTrans) return;

   // 1. Sleeve 1: London Cash Expansion
   bool ofiOkL = (vdp > 0) && (cvd15 >= 0) && (vfs >= InpVFS_Threshold);
   bool ofiOkS = (vdp < 0) && (cvd15 <= 0) && (vfs >= InpVFS_Threshold);
   bool s1_L = InpEnableLondonSleeve && isLondon && trendL && mtfBull && ofiOkL && (eurImpulseZ >= InpMacroLead_London);
   bool s1_S = InpEnableLondonSleeve && isLondon && trendS && mtfBear && ofiOkS && (eurImpulseZ <= -InpMacroLead_London);

   // 2. Sleeve 2: New York Intraday Drive
   bool s2_L = InpEnableNYSleeve && isNY && trendL && mtfBull && (vdp > 0) && (cvd15 > 0) && (vfs >= 1.10) && (eurImpulseZ > -0.5);
   bool s2_S = InpEnableNYSleeve && isNY && trendS && mtfBear && (vdp < 0) && (cvd15 < 0) && (vfs >= 1.10) && (eurImpulseZ < 0.5);

   // 3. Sleeve 3: Volatility Range Breakout (20-bar Donchian)
   bool s3_L = InpEnableRangeSleeve && isPrime && (c1 > hh20) && (vdp > 0) && (cvd15 > 0) && (vfs >= InpRangeVFS_Threshold) && (eurImpulseZ >= 0.02);
   bool s3_S = InpEnableRangeSleeve && isPrime && (c1 < ll20) && (vdp < 0) && (cvd15 < 0) && (vfs >= InpRangeVFS_Threshold) && (eurImpulseZ <= -0.02);

   int signal = 0;
   int sleeve = 0;

   if(s1_L)           { signal = 1;  sleeve = 1; }
   else if(s2_L)      { signal = 1;  sleeve = 2; }
   else if(s3_L)      { signal = 1;  sleeve = 3; }
   else if(s1_S)      { signal = -1; sleeve = 1; }
   else if(s2_S)      { signal = -1; sleeve = 2; }
   else if(s3_S)      { signal = -1; sleeve = 3; }

   if(signal == 0) return;

   // Dynamic Volatility-Adaptive Exits & Sizing
   double slMult, tpMult, riskPct;
   if(vrRatio < 1.00)
   {
      slMult = 1.4;
      tpMult = 2.4;
      riskPct = InpRiskCompression;
   }
   else if(vrRatio >= 1.35)
   {
      slMult = 1.8;
      tpMult = 4.5;
      riskPct = InpRiskSurge;
   }
   else
   {
      slMult = (sleeve == 3) ? 1.4 : 1.6;
      tpMult = (sleeve == 2) ? 3.4 : 3.2;
      riskPct = InpRiskNormal;
   }

   bool isPeak = (MathAbs(eurImpulseZ) >= 0.14);
   if(isPeak) riskPct *= InpPeakConvictionBoost;

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
   request.comment   = StringFormat("EXP-85 S%d_VR%.2f", sleeve, vrRatio);

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

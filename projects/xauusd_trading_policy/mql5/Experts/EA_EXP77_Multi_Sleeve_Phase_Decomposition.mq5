//+------------------------------------------------------------------+
//|       EA_EXP77_Multi_Sleeve_Phase_Decomposition.mq5               |
//|                                  Copyright 2026, BlamzKunG Quant |
//|   EXP-77: Multi-Sleeve Phase Decomposition & Portfolio Scaling   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Conviction Sizing ==="
input double   InpBaseRiskPercent     = 1.5;     // Base Risk % per trade
input bool     InpUseConvictionSizing = true;    // Dynamic Conviction Sizing
input double   InpTier1RiskPercent    = 1.2;     // Standard Single Phase Risk %
input double   InpTier2RiskPercent    = 1.8;     // High ML Conviction Risk %
input double   InpTier3RiskPercent    = 2.4;     // Multi-Phase Confluence Risk %
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Phase Sleeves Selection ==="
input bool     InpEnableSleeve1_ADBC  = true;    // Sleeve 1: Trend Expansion Momentum
input bool     InpEnableSleeve2_PRC   = true;    // Sleeve 2: Pullback Rejection Continuation
input bool     InpEnableSleeve3_Rev   = true;    // Sleeve 3: Composite 2-Bar Hammer/Star
input bool     InpEnableSleeve4_Sweep = true;    // Sleeve 4: Liquidity Sweep & TALP Traps
input double   InpVFS_Threshold       = 1.05;    // Volume Force Surge Threshold

input group "=== Causal Precision Exits ==="
input double   InpInitialSL_ATR       = 1.6;     // Initial Stop Loss in ATR
input double   InpTakeProfit_ATR      = 2.8;     // Take Profit in ATR
input double   InpBE_Trigger_ATR      = 1.3;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.2;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.00;    // Profit Lock Cushion in ATR
input int      InpMaxBarsHeld         = 180;     // Max Bars Held (Time Stop - 3 Hours)

input group "=== System Setup ==="
input ulong    InpMagicNumber         = 770001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-77 MSPD-PSE";

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
      Print("[!] Error initializing technical indicators for EXP-77");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("[+] EA_EXP77_Multi_Sleeve_Phase_Decomposition initialized successfully.");
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

   double lowerWick = MathMin(c1, o1) - l1;
   double upperWick = h1 - MathMax(c1, o1);

   bool mtfBull = (c1 > ema100Arr[0]) && (ema100Arr[0] > ema300Arr[0]);
   bool mtfBear = (c1 < ema100Arr[0]) && (ema100Arr[0] < ema300Arr[0]);
   bool trendL  = (c1 > ema60Arr[0]) && (ema20Arr[0] > ema60Arr[0]);
   bool trendS  = (c1 < ema60Arr[0]) && (ema20Arr[0] < ema60Arr[0]);
   bool ofiOkL  = (vdp > 0) && (cvd15 >= 0) && (vfs >= InpVFS_Threshold);
   bool ofiOkS  = (vdp < 0) && (cvd15 <= 0) && (vfs >= InpVFS_Threshold);

   // Phase 1: Trend Expansion Momentum (ADBC)
   bool s1_L = InpEnableSleeve1_ADBC && trendL && mtfBull && ofiOkL;
   bool s1_S = InpEnableSleeve1_ADBC && trendS && mtfBear && ofiOkS;

   // Phase 2: Pullback Rejection Continuation (PRC)
   double distToM5_L = (c1 - ema100Arr[0]) / MathMax(atr, 0.1);
   double distToM5_S = (ema100Arr[0] - c1) / MathMax(atr, 0.1);
   bool s2_L = InpEnableSleeve2_PRC && mtfBull && (distToM5_L >= -0.1) && (distToM5_L <= 0.7) &&
               (lowerWick >= 0.25 * rng1) && (c1 >= o1) && (vfs >= InpVFS_Threshold) && (vdp > 0);
   bool s2_S = InpEnableSleeve2_PRC && mtfBear && (distToM5_S >= -0.1) && (distToM5_S <= 0.7) &&
               (upperWick >= 0.25 * rng1) && (c1 <= o1) && (vfs >= InpVFS_Threshold) && (vdp < 0);

   // Phase 3: Composite 2-Bar Hammer/Star Reversals
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
   bool s3_L = InpEnableSleeve3_Rev && comp2_hammer && mtfBull && (vdp > 0);
   bool s3_S = InpEnableSleeve3_Rev && comp2_star && mtfBear && (vdp < 0);

   // Phase 4: Swing Sweep Traps & TALP Pinbar
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
   bool bullPinbar   = (lowerWick >= 0.38 * rng1) && (upperWick <= 0.28 * rng1) && (c1 >= o1);
   bool bearPinbar   = (upperWick >= 0.38 * rng1) && (lowerWick <= 0.28 * rng1) && (c1 <= o1);
   bool s4_L = InpEnableSleeve4_Sweep && mtfBull && (sweep_trap_l || bullPinbar) && (vfs >= InpVFS_Threshold * 1.05) && (vdp > 0);
   bool s4_S = InpEnableSleeve4_Sweep && mtfBear && (sweep_trap_s || bearPinbar) && (vfs >= InpVFS_Threshold * 1.05) && (vdp < 0);

   // Multi-Phase Portfolio Union
   int phaseCountL = (int)s1_L + (int)s2_L + (int)s3_L + (int)s4_L;
   int phaseCountS = (int)s1_S + (int)s2_S + (int)s3_S + (int)s4_S;

   int signal = 0;
   int activePhases = 0;
   if(phaseCountL >= 1 && phaseCountL > phaseCountS)
   {
      signal = 1;
      activePhases = phaseCountL;
   }
   else if(phaseCountS >= 1 && phaseCountS > phaseCountL)
   {
      signal = -1;
      activePhases = phaseCountS;
   }

   if(signal == 0) return;

   // Dynamic Conviction Budgeting
   double riskPct = InpBaseRiskPercent;
   if(InpUseConvictionSizing)
   {
      if(activePhases >= 2) riskPct = InpTier3RiskPercent;
      else                  riskPct = InpTier1RiskPercent;
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
   request.comment   = StringFormat("EXP-77 Phase_%d", activePhases);

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

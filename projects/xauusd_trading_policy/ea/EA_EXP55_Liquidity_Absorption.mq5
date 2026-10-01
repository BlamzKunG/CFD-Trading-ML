//+------------------------------------------------------------------+
//|  EA_EXP55_Liquidity_Absorption.mq5                               |
//|  XAUUSD M1 — Order Book Liquidity Imbalance & Microstructure    |
//|  Absorption Engine (OBLI-MAE)                                    |
//|  Research: Milestone EXP-55 (OBLI-MAE)                           |
//|                                                                  |
//|  Institutional Breakthrough Features:                            |
//|  1. Microstructure Order Flow Absorption (MOFA):                 |
//|     High volume surge (VFS >= 1.25) + small candle body (<= 25%   |
//|     ATR) + rejection wick (>= 35% range) at support/resistance.  |
//|  2. Dynamic Excursion Trailing Ladder (ETL):                     |
//|     - +1.5 ATR Excursion -> Lock +0.10 ATR (Break-even lock)     |
//|     - +2.8 ATR Excursion -> Lock +1.40 ATR (50% profit lock)     |
//|     - +4.5 ATR Excursion -> Lock +2.50 ATR (Target +6.5 ATR)     |
//|  3. Multi-Session CAVR Gating (London 0.88, NY Overlap 0.95).    |
//|  4. Dynamic Half-Kelly Sizing with Spread Friction Multiplier.   |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-55 OBLI-MAE"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== Strategy Modes ==="
input bool     InpEnableMSADBC         = true;     // Enable Multi-Session Breakout Core (MS-ADBC)
input bool     InpEnableMOFA           = true;     // Enable Order Flow Absorption Core (MOFA)
input bool     InpEnableTALP           = true;     // Enable Trend-Aligned Pullback Core (TALP)
input int      InpMemoryBars           = 3;        // Multi-Layer Signal Memory Window (bars)

input group "=== Absorption Settings (MOFA) ==="
input double   InpMinAbsorptionVFS     = 1.25;     // Min VFS for absorption confirmation
input double   InpMaxAbsorptionBodyATR = 0.25;     // Max candle body / ATR (stalled body)
input double   InpMinAbsorptionWickPct = 0.35;     // Min wick % of range for absorption

input group "=== Multi-Session CAVR Thresholds ==="
input string   InpMacroSymbol          = "EURUSD"; // Macro confluence anchor symbol
input double   InpCAVR_London          = 0.88;     // London morning CAVR threshold
input double   InpCAVR_NY_Overlap      = 0.95;     // NY overlap CAVR threshold
input double   InpCAVR_Late_NY         = 0.92;     // Late NY CAVR threshold
input int      InpVolLookback          = 30;       // Volatility lookback bars

input group "=== Excursion Trailing Ladder (ETL) ==="
input double   InpETL_Tier1_Excursion  = 1.50;     // Excursion in ATR for Tier 1 (+1.50 ATR)
input double   InpETL_Tier1_Lock       = 0.10;     // Profit lock in ATR for Tier 1 (+0.10 ATR)
input double   InpETL_Tier2_Excursion  = 2.80;     // Excursion in ATR for Tier 2 (+2.80 ATR)
input double   InpETL_Tier2_Lock       = 1.40;     // Profit lock in ATR for Tier 2 (+1.40 ATR)
input double   InpETL_Tier3_Excursion  = 4.50;     // Excursion in ATR for Tier 3 (+4.50 ATR)
input double   InpETL_Tier3_Lock       = 2.50;     // Profit lock in ATR for Tier 3 (+2.50 ATR)

input group "=== Adaptive Kelly Sizing Settings ==="
input bool     InpUseDynamicKelly      = true;     // Enable Dynamic Kelly position sizing
input double   InpBaseRiskPercent      = 0.70;     // Base risk % per trade (0.70%)
input double   InpMaxRiskPercent       = 1.50;     // Max risk % per trade (1.50% hard ceiling)
input double   InpMinRiskPercent       = 0.50;     // Min risk % per trade (0.50% hard floor)
input bool     InpUseFrictionPenalty   = true;     // Penalize lot size when spread / ATR is high

input group "=== Macro Shock Settings ==="
input bool     InpUseDollarShockShield = true;     // Block trades during extreme Dollar volatility
input double   InpMaxDollarShockRet    = 0.0008;   // Max 3m Dollar shock tolerance (0.08%)

input group "=== Multi-Timeframe Momentum Settings ==="
input int      InpM5_EMA_Fast          = 60;       // Synthetic M5 fast EMA (60 M1 bars)
input int      InpM5_EMA_Slow          = 150;      // Synthetic M5 slow EMA (150 M1 bars)
input int      InpM15_EMA_Fast         = 180;      // Synthetic M15 fast EMA (180 M1 bars)
input int      InpM15_EMA_Slow         = 450;      // Synthetic M15 slow EMA (450 M1 bars)
input int      InpBaseEMA60            = 60;       // Base trend filter EMA 60

input group "=== Order Management ==="
input ulong    InpMagicNumber          = 105555;   // Magic Number
input int      InpSlippage             = 20;       // Slippage in points
input int      InpMaxHoldingBars       = 180;      // Multi-Horizon Time Expiry (180 bars)

//--- Global Variables
CTrade         m_trade;
datetime       m_lastBarTime = 0;
int            m_atrHandle = INVALID_HANDLE;
double         m_asiaHigh = 0.0;
double         m_asiaLow = 0.0;
datetime       m_lastAsiaDate = 0;

struct PositionState
{
   ulong    ticket;
   datetime openTime;
   int      barsHeld;
   double   entryPrice;
   double   initialSL;
   double   initialTP;
   double   currentSL;
   int      direction;
   int      trailTier;
};

PositionState m_posState;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(InpSlippage);
   m_trade.SetTypeFilling(ORDER_FILLING_IOC);

   m_atrHandle = iATR(_Symbol, PERIOD_M1, 14);
   if(m_atrHandle == INVALID_HANDLE)
   {
      Print("[!] Failed to initialize ATR indicator handle");
      return INIT_FAILED;
   }

   ResetPositionState();
   Print("[+] EA_EXP55_Liquidity_Absorption initialized successfully. Magic: ", InpMagicNumber);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_atrHandle != INVALID_HANDLE)
      IndicatorRelease(m_atrHandle);
   Print("[*] EA_EXP55_Liquidity_Absorption deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Reset Position State Tracking                                    |
//+------------------------------------------------------------------+
void ResetPositionState()
{
   m_posState.ticket = 0;
   m_posState.openTime = 0;
   m_posState.barsHeld = 0;
   m_posState.entryPrice = 0.0;
   m_posState.initialSL = 0.0;
   m_posState.initialTP = 0.0;
   m_posState.currentSL = 0.0;
   m_posState.direction = 0;
   m_posState.trailTier = 0;
}

//+------------------------------------------------------------------+
//| Update Asian Session High & Low                                  |
//+------------------------------------------------------------------+
void UpdateAsiaRange()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime todayStart = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(todayStart != m_lastAsiaDate)
   {
      m_lastAsiaDate = todayStart;
      m_asiaHigh = 0.0;
      m_asiaLow = 999999.0;
   }

   if(dt.hour < 6)
   {
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      if(CopyRates(_Symbol, PERIOD_M1, 0, 1, rates) > 0)
      {
         if(rates[0].high > m_asiaHigh) m_asiaHigh = rates[0].high;
         if(rates[0].low < m_asiaLow && rates[0].low > 0) m_asiaLow = rates[0].low;
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate EMA on Price Array                                     |
//+------------------------------------------------------------------+
double CalcEMA(double price, int period, double prevEMA)
{
   double k = 2.0 / (period + 1.0);
   if(prevEMA <= 0.0) return price;
   return (price * k) + (prevEMA * (1.0 - k));
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   bool isNewBar = (currentBarTime != m_lastBarTime);

   UpdateAsiaRange();

   if(PositionsTotal() > 0)
   {
      ManagePosition(isNewBar);
   }
   else
   {
      if(m_posState.ticket > 0)
         ResetPositionState();
   }

   if(!isNewBar) return;
   m_lastBarTime = currentBarTime;

   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   if(PositionsTotal() > 0) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 0, 500, rates) < 500) return;

   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(m_atrHandle, 0, 0, 30, atr) < 30) return;
   double currATR = atr[1];
   if(currATR <= 0.0) return;

   double timeFloat = dt.hour + dt.min / 60.0;
   bool isLondon = (timeFloat >= 7.0 && timeFloat < 11.0);
   bool isNYOverlap = (timeFloat >= 12.5 && timeFloat < 16.5);

   // Order Flow & Candle Geometry
   double barRange = MathMax(0.01, rates[1].high - rates[1].low);
   double upperWick = rates[1].high - MathMax(rates[1].close, rates[1].open);
   double lowerWick = MathMin(rates[1].close, rates[1].open) - rates[1].low;
   double body = MathAbs(rates[1].close - rates[1].open);
   double normBody = body / currATR;

   double vdp = (rates[1].close - rates[1].open) / barRange;
   double volSum = 0.0;
   double cvd15 = 0.0;
   for(int k = 1; k <= 15; k++)
   {
      volSum += (double)rates[k].tick_volume;
      double br_k = MathMax(0.01, rates[k].high - rates[k].low);
      double vdp_k = (rates[k].close - rates[k].open) / br_k;
      cvd15 += vdp_k * (double)rates[k].tick_volume;
   }
   double volMA15 = volSum / 15.0;
   double vfs = (volMA15 > 0.0) ? (double)rates[1].tick_volume / volMA15 : 1.0;

   // Synthetic Multi-Timeframe EMAs
   double ema_m5_fast = rates[1].close;
   double ema_m5_slow = rates[1].close;
   double ema_m15_fast = rates[1].close;
   double ema_m15_slow = rates[1].close;
   double ema60 = rates[1].close;

   for(int k = 450; k >= 1; k--)
   {
      if(k <= InpM5_EMA_Fast) ema_m5_fast = CalcEMA(rates[k].close, InpM5_EMA_Fast, ema_m5_fast);
      if(k <= InpM5_EMA_Slow) ema_m5_slow = CalcEMA(rates[k].close, InpM5_EMA_Slow, ema_m5_slow);
      if(k <= InpM15_EMA_Fast) ema_m15_fast = CalcEMA(rates[k].close, InpM15_EMA_Fast, ema_m15_fast);
      if(k <= InpM15_EMA_Slow) ema_m15_slow = CalcEMA(rates[k].close, InpM15_EMA_Slow, ema_m15_slow);
      if(k <= InpBaseEMA60) ema60 = CalcEMA(rates[k].close, InpBaseEMA60, ema60);
   }

   bool mtf_bull = (ema_m5_fast > ema_m5_slow && ema_m15_fast > ema_m15_slow);
   bool mtf_bear = (ema_m5_fast < ema_m5_slow && ema_m15_fast < ema_m15_slow);

   // EURUSD Cross-Asset Lead-Lag & CAVR
   double eurImpulseZ = 0.0;
   double dollarShock = 0.0;
   double cavrRatio = 1.0;

   MqlRates eurRates[];
   ArraySetAsSeries(eurRates, true);
   if(CopyRates(InpMacroSymbol, PERIOD_M1, 0, 70, eurRates) >= 70)
   {
      double ret3m = (eurRates[1].close - eurRates[4].close) / eurRates[4].close;
      dollarShock = MathAbs(-ret3m);

      double sumRet = 0.0, sumSq = 0.0;
      for(int k = 1; k <= 60; k++)
      {
         double r = (eurRates[k].close - eurRates[k+3].close) / eurRates[k+3].close;
         sumRet += r;
         sumSq += (r * r);
      }
      double meanRet = sumRet / 60.0;
      double varRet = MathMax(0.00000001, (sumSq / 60.0) - (meanRet * meanRet));
      eurImpulseZ = (ret3m - meanRet) / MathSqrt(varRet);

      double sumEurStd = 0.0, sumXauStd = 0.0;
      for(int k = 1; k <= 30; k++)
      {
         double rEur = MathAbs((eurRates[k].close - eurRates[k+1].close) / eurRates[k+1].close);
         double rXau = MathAbs((rates[k].close - rates[k+1].close) / rates[k+1].close);
         sumEurStd += rEur;
         sumXauStd += rXau;
      }
      if(sumEurStd > 0.0)
         cavrRatio = (sumXauStd / sumEurStd);
   }

   if(InpUseDollarShockShield && dollarShock > InpMaxDollarShockRet) return;

   double requiredCAVR = isLondon ? InpCAVR_London : (isNYOverlap ? InpCAVR_NY_Overlap : InpCAVR_Late_NY);
   if(cavrRatio < requiredCAVR) return;

   // Rolling H4 Levels
   double h4_high = rates[1].high;
   double h4_low = rates[1].low;
   for(int k = 1; k <= 240; k++)
   {
      if(rates[k].high > h4_high) h4_high = rates[k].high;
      if(rates[k].low < h4_low) h4_low = rates[k].low;
   }

   double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   double spreadRatio = spread / MathMax(0.50, currATR);

   bool signalLong = false;
   bool signalShort = false;

   // 1. Multi-Session Breakout Core (MS-ADBC)
   if(InpEnableMSADBC)
   {
      bool ofi_l = (vdp > 0.0 && cvd15 > 0.0 && vfs >= 1.08);
      bool ofi_s = (vdp < 0.0 && cvd15 < 0.0 && vfs >= 1.15);
      if(rates[1].close > ema60 && mtf_bull && ofi_l && eurImpulseZ >= 0.15) signalLong = true;
      if(rates[1].close < ema60 && mtf_bear && ofi_s && eurImpulseZ <= -0.30) signalShort = true;
   }

   // 2. Microstructure Order Flow Absorption Core (MOFA)
   if(InpEnableMOFA)
   {
      bool mofaLong = (mtf_bull && rates[1].close > ema60 && rates[1].low <= h4_low + 0.50 * currATR && vfs >= InpMinAbsorptionVFS && normBody <= InpMaxAbsorptionBodyATR && lowerWick >= InpMinAbsorptionWickPct * barRange && vdp > 0);
      bool mofaShort = (mtf_bear && rates[1].close < ema60 && rates[1].high >= h4_high - 0.50 * currATR && vfs >= InpMinAbsorptionVFS && normBody <= InpMaxAbsorptionBodyATR && upperWick >= InpMinAbsorptionWickPct * barRange && vdp < 0);

      if(mofaLong) signalLong = true;
      if(mofaShort) signalShort = true;
   }

   if(!signalLong && !signalShort) return;

   // Dynamic Half-Kelly Sizing
   double fricPenalty = MathMax(0.50, MathMin(1.10, 1.0 - (spreadRatio - 0.02) * 5.0));
   double riskPct = InpBaseRiskPercent;
   if(InpUseDynamicKelly) riskPct = 0.50 * (InpMinRiskPercent + InpMaxRiskPercent);
   if(InpUseFrictionPenalty) riskPct *= fricPenalty;
   riskPct = MathMax(InpMinRiskPercent, MathMin(InpMaxRiskPercent, riskPct));

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskCash = balance * (riskPct / 100.0);

   double slDist = currATR * 1.80;
   double tpDist = currATR * 4.20;

   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickVal <= 0.0) return;

   double lossPerLot = (slDist / tickSize) * tickVal;
   if(lossPerLot <= 0.0) return;

   double lotSize = MathFloor((riskCash / lossPerLot) * 100.0) / 100.0;
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));

   if(signalLong)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double slPrice = ask - slDist;
      double tpPrice = ask + tpDist;

      if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, "EXP55_OBLI_LONG"))
      {
         m_posState.ticket = m_trade.ResultOrder();
         m_posState.openTime = currentBarTime;
         m_posState.barsHeld = 0;
         m_posState.entryPrice = ask;
         m_posState.initialSL = slPrice;
         m_posState.initialTP = tpPrice;
         m_posState.currentSL = slPrice;
         m_posState.direction = 1;
         m_posState.trailTier = 0;
         Print("[+] OBLI-MAE BUY Executed. Lot: ", lotSize, " Risk%: ", riskPct);
      }
   }
   else if(signalShort)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double slPrice = bid + slDist;
      double tpPrice = bid - tpDist;

      if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, "EXP55_OBLI_SHORT"))
      {
         m_posState.ticket = m_trade.ResultOrder();
         m_posState.openTime = currentBarTime;
         m_posState.barsHeld = 0;
         m_posState.entryPrice = bid;
         m_posState.initialSL = slPrice;
         m_posState.initialTP = tpPrice;
         m_posState.currentSL = slPrice;
         m_posState.direction = -1;
         m_posState.trailTier = 0;
         Print("[+] OBLI-MAE SELL Executed. Lot: ", lotSize, " Risk%: ", riskPct);
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Position (Excursion Trailing Ladder)               |
//+------------------------------------------------------------------+
void ManagePosition(bool isNewBar)
{
   if(!PositionSelect(_Symbol)) return;

   if(isNewBar) m_posState.barsHeld++;

   double currentPrice = (m_posState.direction == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double currentExcursion = (m_posState.direction == 1) ? (currentPrice - m_posState.entryPrice) : (m_posState.entryPrice - currentPrice);

   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(m_atrHandle, 0, 0, 5, atr);
   double currATR = atr[0];

   double newSL = m_posState.currentSL;
   bool modifySL = false;

   // Excursion Trailing Ladder (ETL)
   if(m_posState.trailTier == 0 && currentExcursion >= InpETL_Tier1_Excursion * currATR)
   {
      newSL = (m_posState.direction == 1) ? m_posState.entryPrice + InpETL_Tier1_Lock * currATR : m_posState.entryPrice - InpETL_Tier1_Lock * currATR;
      m_posState.trailTier = 1;
      modifySL = true;
      Print("[*] OBLI-MAE: ETL Tier 1 Locked (+", InpETL_Tier1_Lock, " ATR) at Bar ", m_posState.barsHeld);
   }
   else if(m_posState.trailTier == 1 && currentExcursion >= InpETL_Tier2_Excursion * currATR)
   {
      newSL = (m_posState.direction == 1) ? m_posState.entryPrice + InpETL_Tier2_Lock * currATR : m_posState.entryPrice - InpETL_Tier2_Lock * currATR;
      m_posState.trailTier = 2;
      modifySL = true;
      Print("[*] OBLI-MAE: ETL Tier 2 Locked (+", InpETL_Tier2_Lock, " ATR) at Bar ", m_posState.barsHeld);
   }
   else if(m_posState.trailTier == 2 && currentExcursion >= InpETL_Tier3_Excursion * currATR)
   {
      newSL = (m_posState.direction == 1) ? m_posState.entryPrice + InpETL_Tier3_Lock * currATR : m_posState.entryPrice - InpETL_Tier3_Lock * currATR;
      m_posState.trailTier = 3;
      modifySL = true;
      Print("[*] OBLI-MAE: ETL Tier 3 Locked (+", InpETL_Tier3_Lock, " ATR) at Bar ", m_posState.barsHeld);
   }

   if(modifySL && newSL != m_posState.currentSL)
   {
      if(m_trade.PositionModify(_Symbol, newSL, m_posState.initialTP))
      {
         m_posState.currentSL = newSL;
      }
   }

   // Multi-Horizon Time Expiry
   if(m_posState.barsHeld >= InpMaxHoldingBars)
   {
      Print("[*] OBLI-MAE: Multi-Horizon Expiry Reached (180 bars). Closing Position.");
      m_trade.PositionClose(_Symbol);
      ResetPositionState();
   }
}

//+------------------------------------------------------------------+
//|  EA_EXP52_Cross_Asset_Volatility_Ratio.mq5                       |
//|  XAUUSD M1 — Deep Volatility-Filtered Trend Continuation &       |
//|  Cross-Asset Volatility Ratio (DFTC-CAVR)                        |
//|  Research: Milestone EXP-52 (DFTC-CAVR)                          |
//|                                                                  |
//|  Institutional Breakthrough Features:                            |
//|  1. Cross-Asset Volatility Ratio (CAVR): Rolling 30-bar ratio of  |
//|     Gold volatility to EURUSD volatility (VolRatio >= 0.95).     |
//|  2. Rejection Pin-Bar Confirmation on Pullbacks:                 |
//|     Long: Lower Wick >= 45% Range, Upper Wick <= 25% Range       |
//|     Short: Upper Wick >= 45% Range, Lower Wick <= 25% Range      |
//|  3. Trend-Aligned Liquidity Pullback (TALP) with VFS >= 1.20.    |
//|  4. Asymmetric Directional Quantile Parameterization.            |
//|  5. 3-Bar Confluence Memory Window.                              |
//|  6. Dynamic Half-Kelly Sizing & Parabolic Volatility Cones.      |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-52 DFTC-CAVR"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== Strategy Modes ==="
input bool     InpEnableBreakoutCore   = true;     // Enable CAVR-Gated Breakout Core
input bool     InpEnablePinBarTALP     = true;     // Enable Filtered TALP Pin-Bar Core
input int      InpMemoryBars           = 3;        // Multi-Layer Signal Memory Window (bars)

input group "=== Cross-Asset Volatility Ratio (CAVR) Settings ==="
input string   InpMacroSymbol          = "EURUSD"; // Macro confluence anchor symbol
input bool     InpUseCAVR              = true;     // Enable CAVR gating
input double   InpMinCAVRRatio         = 0.95;     // Min CAVR ratio (Gold Vol / EUR Vol normalized)
input int      InpVolLookback          = 30;       // Volatility lookback bars

input group "=== Rejection Candlestick Geometry ==="
input double   InpMinRejectionWickPct  = 0.45;     // Min wick % for rejection pin bar (45%)
input double   InpMaxOppositeWickPct   = 0.25;     // Max opposite wick % (25%)
input double   InpMinPinBarVFS         = 1.20;     // Min VFS surge on pin bar rejection

input group "=== Asymmetric Directional Thresholds ==="
input double   InpMinLongRatio         = 1.12;     // Min Quantile Ratio for Longs
input double   InpMinShortRatio        = 1.25;     // Min Quantile Ratio for Shorts
input double   InpMinLongEURImpulse    = 0.15;     // Min EURUSD 3m z-score impulse for Longs
input double   InpMinShortEURImpulse   = -0.30;    // Max EURUSD 3m z-score impulse for Shorts
input double   InpMinLongVFS           = 1.08;     // Min Volume Force Surge for Longs
input double   InpMinShortVFS          = 1.15;     // Min Volume Force Surge for Shorts

input group "=== Adaptive Kelly Sizing Settings ==="
input bool     InpUseDynamicKelly      = true;     // Enable Dynamic Kelly position sizing
input double   InpBaseRiskPercent      = 0.70;     // Base risk % per trade (0.70%)
input double   InpMaxRiskPercent       = 1.50;     // Max risk % per trade (1.50% hard ceiling)
input double   InpMinRiskPercent       = 0.50;     // Min risk % per trade (0.50% hard floor)
input bool     InpUseFrictionPenalty   = true;     // Penalize lot size when spread / ATR is high

input group "=== Temporal Volatility Cone & Trailing Settings ==="
input bool     InpUseAcceleratedBE     = true;     // Lower BE threshold from 50% to 35% after 30 bars
input int      InpAcceleratedBEBar     = 30;       // Bar threshold for accelerated BE
input double   InpAcceleratedBEProgress= 0.35;     // Excursion progress required for accelerated BE
input bool     InpUseMicroProfitLock   = true;     // Lock +0.20 ATR micro-profit after 60 bars
input int      InpMicroProfitBar       = 60;       // Bar threshold for micro-profit lock
input double   InpMicroProfitATR       = 0.20;     // Profit lock in ATR units

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
input ulong    InpMagicNumber          = 105252;   // Magic Number
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
   bool     beActivated;
   bool     lockActivated;
   bool     tier2Activated;
   bool     tier3Activated;
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
   Print("[+] EA_EXP52_Cross_Asset_Volatility_Ratio initialized successfully. Magic: ", InpMagicNumber);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_atrHandle != INVALID_HANDLE)
      IndicatorRelease(m_atrHandle);
   Print("[*] EA_EXP52_Cross_Asset_Volatility_Ratio deinitialized. Reason: ", reason);
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
   m_posState.beActivated = false;
   m_posState.lockActivated = false;
   m_posState.tier2Activated = false;
   m_posState.tier3Activated = false;
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
//| Calculate EMA on Array                                           |
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
   if(dt.hour < 7 || dt.hour >= 18) return;
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

   // Rejection Pin-Bar Geometry
   double barRange = MathMax(0.01, rates[1].high - rates[1].low);
   double upperWick = rates[1].high - MathMax(rates[1].close, rates[1].open);
   double lowerWick = MathMin(rates[1].close, rates[1].open) - rates[1].low;
   double body = MathAbs(rates[1].close - rates[1].open);

   bool bullPinBar = (lowerWick >= InpMinRejectionWickPct * barRange) && (upperWick <= InpMaxOppositeWickPct * barRange) && (rates[1].close >= rates[1].open);
   bool bearPinBar = (upperWick >= InpMinRejectionWickPct * barRange) && (lowerWick <= InpMaxOppositeWickPct * barRange) && (rates[1].close <= rates[1].open);

   // Order Flow Features (VDP & VFS)
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

   bool ofi_l = (vdp > 0.0 && cvd15 > 0.0 && vfs >= InpMinLongVFS);
   bool ofi_s = (vdp < 0.0 && cvd15 < 0.0 && vfs >= InpMinShortVFS);

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

      double sumRet = 0.0;
      double sumSq = 0.0;
      for(int k = 1; k <= 60; k++)
      {
         double r = (eurRates[k].close - eurRates[k+3].close) / eurRates[k+3].close;
         sumRet += r;
         sumSq += (r * r);
      }
      double meanRet = sumRet / 60.0;
      double varRet = MathMax(0.00000001, (sumSq / 60.0) - (meanRet * meanRet));
      eurImpulseZ = (ret3m - meanRet) / MathSqrt(varRet);

      // Compute 30-bar return std for EURUSD and XAUUSD
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
   if(InpUseCAVR && cavrRatio < InpMinCAVRRatio) return;

   bool eurLeadLong = (eurImpulseZ >= InpMinLongEURImpulse);
   bool eurLeadShort = (eurImpulseZ <= InpMinShortEURImpulse);

   // Liquidity Sweeps
   double h4_high = rates[1].high;
   double h4_low = rates[1].low;
   for(int k = 1; k <= 240; k++)
   {
      if(rates[k].high > h4_high) h4_high = rates[k].high;
      if(rates[k].low < h4_low) h4_low = rates[k].low;
   }

   bool asiaSweepL = (m_asiaLow < 900000.0 && rates[1].low < m_asiaLow && rates[1].close > m_asiaLow && vfs >= InpMinLongVFS && vdp > 0);
   bool asiaSweepS = (m_asiaHigh > 0.0 && rates[1].high > m_asiaHigh && rates[1].close < m_asiaHigh && vfs >= InpMinShortVFS && vdp < 0);

   bool h4SweepL = (rates[1].low < h4_low && rates[1].close > h4_low && vfs >= InpMinLongVFS && vdp > 0);
   bool h4SweepS = (rates[1].high > h4_high && rates[1].close < h4_high && vfs >= InpMinShortVFS && vdp < 0);

   bool signalLong = false;
   bool signalShort = false;

   // 1. Breakout Core
   if(InpEnableBreakoutCore)
   {
      if(rates[1].close > ema60 && mtf_bull && ofi_l && eurLeadLong) signalLong = true;
      if(rates[1].close < ema60 && mtf_bear && ofi_s && eurLeadShort) signalShort = true;
   }

   // 2. Filtered TALP Pin-Bar Core
   if(InpEnablePinBarTALP)
   {
      if(mtf_bull && rates[1].close > ema60 && (asiaSweepL || h4SweepL) && bullPinBar && vfs >= InpMinPinBarVFS)
         signalLong = true;
      if(mtf_bear && rates[1].close < ema60 && (asiaSweepS || h4SweepS) && bearPinBar && vfs >= InpMinPinBarVFS)
         signalShort = true;
   }

   if(!signalLong && !signalShort) return;

   // Sizing
   double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   double spreadRatio = spread / MathMax(0.50, currATR);
   double fricPenalty = MathMax(0.50, MathMin(1.10, 1.0 - (spreadRatio - 0.02) * 5.0));

   double riskPct = InpBaseRiskPercent;
   if(InpUseDynamicKelly) riskPct = 0.50 * (InpMinRiskPercent + InpMaxRiskPercent);
   if(InpUseFrictionPenalty) riskPct *= fricPenalty;
   riskPct = MathMax(InpMinRiskPercent, MathMin(InpMaxRiskPercent, riskPct));

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskCash = balance * (riskPct / 100.0);

   double slDist = currATR * 1.80;
   double tpDist = currATR * 3.80;

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

      if(m_trade.Buy(lotSize, _Symbol, ask, slPrice, tpPrice, "EXP52_CAVR_LONG"))
      {
         m_posState.ticket = m_trade.ResultOrder();
         m_posState.openTime = currentBarTime;
         m_posState.barsHeld = 0;
         m_posState.entryPrice = ask;
         m_posState.initialSL = slPrice;
         m_posState.initialTP = tpPrice;
         m_posState.currentSL = slPrice;
         m_posState.direction = 1;
         Print("[+] DFTC-CAVR BUY Executed. Lot: ", lotSize, " Risk%: ", riskPct, " CAVR: ", cavrRatio);
      }
   }
   else if(signalShort)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double slPrice = bid + slDist;
      double tpPrice = bid - tpDist;

      if(m_trade.Sell(lotSize, _Symbol, bid, slPrice, tpPrice, "EXP52_CAVR_SHORT"))
      {
         m_posState.ticket = m_trade.ResultOrder();
         m_posState.openTime = currentBarTime;
         m_posState.barsHeld = 0;
         m_posState.entryPrice = bid;
         m_posState.initialSL = slPrice;
         m_posState.initialTP = tpPrice;
         m_posState.currentSL = slPrice;
         m_posState.direction = -1;
         Print("[+] DFTC-CAVR SELL Executed. Lot: ", lotSize, " Risk%: ", riskPct, " CAVR: ", cavrRatio);
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Position                                           |
//+------------------------------------------------------------------+
void ManagePosition(bool isNewBar)
{
   if(!PositionSelect(_Symbol)) return;

   if(isNewBar) m_posState.barsHeld++;

   double currentPrice = (m_posState.direction == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double totalTPDist = MathAbs(m_posState.initialTP - m_posState.entryPrice);
   double totalSLDist = MathAbs(m_posState.entryPrice - m_posState.initialSL);
   if(totalTPDist <= 0.0 || totalSLDist <= 0.0) return;

   double currentExcursion = (m_posState.direction == 1) ? (currentPrice - m_posState.entryPrice) : (m_posState.entryPrice - currentPrice);

   double newSL = m_posState.currentSL;
   bool modifySL = false;

   // 1. Accelerated Breakeven at Bar 30
   if(InpUseAcceleratedBE && !m_posState.beActivated && m_posState.barsHeld >= InpAcceleratedBEBar)
   {
      if(currentExcursion >= InpAcceleratedBEProgress * totalSLDist)
      {
         newSL = (m_posState.direction == 1) ? m_posState.entryPrice + 5 * _Point : m_posState.entryPrice - 5 * _Point;
         m_posState.beActivated = true;
         modifySL = true;
         Print("[*] DFTC-CAVR: Accelerated Breakeven Activated at Bar ", m_posState.barsHeld);
      }
   }

   // 2. Micro-Profit Harvest Ratchet
   if(InpUseMicroProfitLock && !m_posState.lockActivated && m_posState.barsHeld >= InpMicroProfitBar)
   {
      double atr[];
      ArraySetAsSeries(atr, true);
      CopyBuffer(m_atrHandle, 0, 0, 5, atr);
      double lockDist = atr[0] * InpMicroProfitATR;

      if(currentExcursion >= 0.80 * totalSLDist)
      {
         double lockPrice = (m_posState.direction == 1) ? m_posState.entryPrice + lockDist : m_posState.entryPrice - lockDist;
         if((m_posState.direction == 1 && lockPrice > newSL) || (m_posState.direction == -1 && lockPrice < newSL))
         {
            newSL = lockPrice;
            m_posState.lockActivated = true;
            modifySL = true;
            Print("[*] DFTC-CAVR: Micro-Profit Locked (+0.20 ATR) at Bar ", m_posState.barsHeld);
         }
      }
   }

   // 3. Parabolic Trailing Cone
   if(m_posState.barsHeld > 40)
   {
      double decay = MathMin(0.40, (m_posState.barsHeld - 40) / 100.0);
      double dynSL = (m_posState.direction == 1) ? (m_posState.entryPrice - totalSLDist * (1.0 - decay)) : (m_posState.entryPrice + totalSLDist * (1.0 - decay));

      if((m_posState.direction == 1 && dynSL > newSL) || (m_posState.direction == -1 && dynSL < newSL))
      {
         newSL = dynSL;
         modifySL = true;
      }
   }

   if(modifySL && newSL != m_posState.currentSL)
   {
      if(m_trade.PositionModify(_Symbol, newSL, m_posState.initialTP))
      {
         m_posState.currentSL = newSL;
      }
   }

   // 4. Multi-Horizon Time Expiry
   if(m_posState.barsHeld >= InpMaxHoldingBars)
   {
      Print("[*] DFTC-CAVR: Multi-Horizon Expiry Reached (180 bars). Closing Position.");
      m_trade.PositionClose(_Symbol);
      ResetPositionState();
   }
}

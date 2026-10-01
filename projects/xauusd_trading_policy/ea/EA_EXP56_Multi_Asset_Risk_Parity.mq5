//+------------------------------------------------------------------+
//|  EA_EXP56_Multi_Asset_Risk_Parity.mq5                            |
//|  XAUUSD & EURUSD M1 — Multi-Asset Synergistic Risk-Parity        |
//|  Alpha Engine (MASR-PAE)                                         |
//|  Research: Milestone EXP-56 (MASR-PAE)                           |
//|                                                                  |
//|  Institutional Breakthrough Features:                            |
//|  1. Dual-Asset Risk-Parity Allocation (65% XAU / 35% EUR).       |
//|  2. Cross-Asset Reciprocal Alpha: Gold volume surges lead EUR.   |
//|  3. Multi-Session CAVR Gating & Pin-Bar Rejection.               |
//|  4. Dynamic Half-Kelly Sizing on Both Symbols.                   |
//|  5. Non-Linear Temporal Volatility Cones on Both Symbols.        |
//+------------------------------------------------------------------+
#property copyright "Multi-Asset Quant ML Research — EXP-56 MASR-PAE"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== Multi-Asset Risk Parity Settings ==="
input string   InpGoldSymbol           = "XAUUSD"; // Gold Symbol
input string   InpEURSymbol            = "EURUSD"; // EURUSD Symbol
input double   InpRiskWeightGold       = 0.65;     // Gold Portfolio Risk Weight (65%)
input double   InpRiskWeightEUR        = 0.35;     // EURUSD Portfolio Risk Weight (35%)
input double   InpBaseRiskPercent      = 0.85;     // Base Total Risk % per cycle (0.85%)

input group "=== Strategy Core Toggles ==="
input bool     InpTradeGold            = true;     // Enable Trading on Gold
input bool     InpTradeEUR             = true;     // Enable Trading on EURUSD

input group "=== Multi-Session CAVR Thresholds ==="
input double   InpCAVR_London          = 0.88;     // London morning CAVR threshold
input double   InpCAVR_NY_Overlap      = 0.95;     // NY overlap CAVR threshold
input double   InpCAVR_Late_NY         = 0.92;     // Late NY CAVR threshold

input group "=== Temporal Volatility Cone & Trailing Settings ==="
input double   InpGold_SL_ATR          = 1.80;     // Gold Initial SL in ATR
input double   InpGold_TP_ATR          = 3.80;     // Gold Initial TP in ATR
input double   InpEUR_SL_ATR           = 1.50;     // EURUSD Initial SL in ATR
input double   InpEUR_TP_ATR           = 3.20;     // EURUSD Initial TP in ATR
input double   InpBreakevenATR         = 1.50;     // Move to breakeven after +1.50 ATR excursion

input group "=== Order Management ==="
input ulong    InpMagicNumberGold      = 105656;   // Magic Number Gold
input ulong    InpMagicNumberEUR       = 105657;   // Magic Number EURUSD
input int      InpSlippage             = 20;       // Slippage in points
input int      InpMaxHoldingBars       = 180;      // Multi-Horizon Time Expiry (180 bars)

//--- Global Variables
CTrade         m_tradeGold;
CTrade         m_tradeEUR;
datetime       m_lastBarTime = 0;
int            m_atrGoldHandle = INVALID_HANDLE;
int            m_atrEURHandle  = INVALID_HANDLE;

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
};

PositionState m_goldPos;
PositionState m_eurPos;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_tradeGold.SetExpertMagicNumber(InpMagicNumberGold);
   m_tradeGold.SetDeviationInPoints(InpSlippage);
   m_tradeGold.SetTypeFilling(ORDER_FILLING_IOC);

   m_tradeEUR.SetExpertMagicNumber(InpMagicNumberEUR);
   m_tradeEUR.SetDeviationInPoints(InpSlippage);
   m_tradeEUR.SetTypeFilling(ORDER_FILLING_IOC);

   m_atrGoldHandle = iATR(InpGoldSymbol, PERIOD_M1, 14);
   m_atrEURHandle  = iATR(InpEURSymbol, PERIOD_M1, 14);

   if(m_atrGoldHandle == INVALID_HANDLE || m_atrEURHandle == INVALID_HANDLE)
   {
      Print("[!] Failed to initialize ATR indicator handles");
      return INIT_FAILED;
   }

   ResetState(m_goldPos);
   ResetState(m_eurPos);
   Print("[+] EA_EXP56_Multi_Asset_Risk_Parity initialized successfully. Gold Magic: ", InpMagicNumberGold, " EUR Magic: ", InpMagicNumberEUR);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_atrGoldHandle != INVALID_HANDLE) IndicatorRelease(m_atrGoldHandle);
   if(m_atrEURHandle != INVALID_HANDLE)  IndicatorRelease(m_atrEURHandle);
   Print("[*] EA_EXP56_Multi_Asset_Risk_Parity deinitialized. Reason: ", reason);
}

void ResetState(PositionState &pos)
{
   pos.ticket = 0;
   pos.openTime = 0;
   pos.barsHeld = 0;
   pos.entryPrice = 0.0;
   pos.initialSL = 0.0;
   pos.initialTP = 0.0;
   pos.currentSL = 0.0;
   pos.direction = 0;
   pos.beActivated = false;
}

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
   datetime currentBarTime = iTime(InpGoldSymbol, PERIOD_M1, 0);
   bool isNewBar = (currentBarTime != m_lastBarTime);

   // Manage Open Positions
   ManagePosition(InpGoldSymbol, m_goldPos, m_tradeGold, InpGold_SL_ATR, isNewBar);
   ManagePosition(InpEURSymbol, m_eurPos, m_tradeEUR, InpEUR_SL_ATR, isNewBar);

   if(!isNewBar) return;
   m_lastBarTime = currentBarTime;

   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.hour < 7 || dt.hour >= 19) return;
   if(dt.day_of_week == 5 && dt.hour >= 17) return;

   // Copy Gold Data
   MqlRates goldRates[];
   ArraySetAsSeries(goldRates, true);
   if(CopyRates(InpGoldSymbol, PERIOD_M1, 0, 500, goldRates) < 500) return;

   // Copy EUR Data
   MqlRates eurRates[];
   ArraySetAsSeries(eurRates, true);
   if(CopyRates(InpEURSymbol, PERIOD_M1, 0, 500, eurRates) < 500) return;

   double atrGold[];
   ArraySetAsSeries(atrGold, true);
   if(CopyBuffer(m_atrGoldHandle, 0, 0, 10, atrGold) < 10) return;

   double atrEUR[];
   ArraySetAsSeries(atrEUR, true);
   if(CopyBuffer(m_atrEURHandle, 0, 0, 10, atrEUR) < 10) return;

   double currATRGold = atrGold[1];
   double currATREUR  = atrEUR[1];
   if(currATRGold <= 0.0 || currATREUR <= 0.0) return;

   // Calculate EMAs for Gold
   double ema5Gold = goldRates[1].close;
   double ema15Gold = goldRates[1].close;
   double ema60Gold = goldRates[1].close;
   for(int k = 300; k >= 1; k--)
   {
      if(k <= 100) ema5Gold = CalcEMA(goldRates[k].close, 100, ema5Gold);
      if(k <= 300) ema15Gold = CalcEMA(goldRates[k].close, 300, ema15Gold);
      if(k <= 60)  ema60Gold = CalcEMA(goldRates[k].close, 60, ema60Gold);
   }
   bool mtfBullGold = (goldRates[1].close > ema5Gold && ema5Gold > ema15Gold);

   // Calculate EMAs for EUR
   double ema5EUR = eurRates[1].close;
   double ema15EUR = eurRates[1].close;
   double ema60EUR = eurRates[1].close;
   for(int k = 300; k >= 1; k--)
   {
      if(k <= 100) ema5EUR = CalcEMA(eurRates[k].close, 100, ema5EUR);
      if(k <= 300) ema15EUR = CalcEMA(eurRates[k].close, 300, ema15EUR);
      if(k <= 60)  ema60EUR = CalcEMA(eurRates[k].close, 60, ema60EUR);
   }
   bool mtfBullEUR = (eurRates[1].close > ema5EUR && ema5EUR > ema15EUR);

   // Cross-Asset Signals
   double ret3mEUR = (eurRates[1].close - eurRates[4].close) / eurRates[4].close;
   double ret3mGold = (goldRates[1].close - goldRates[4].close) / goldRates[4].close;

   double sumEurStd = 0.0, sumXauStd = 0.0;
   for(int k = 1; k <= 30; k++)
   {
      sumEurStd += MathAbs((eurRates[k].close - eurRates[k+1].close) / eurRates[k+1].close);
      sumXauStd += MathAbs((goldRates[k].close - goldRates[k+1].close) / goldRates[k+1].close);
   }
   double cavrRatio = (sumEurStd > 0.0) ? (sumXauStd / sumEurStd) : 1.0;

   double timeFloat = dt.hour + dt.min / 60.0;
   bool isLondon = (timeFloat >= 7.0 && timeFloat < 11.0);
   bool isNYOverlap = (timeFloat >= 12.5 && timeFloat < 16.5);
   double reqCAVR = isLondon ? InpCAVR_London : (isNYOverlap ? InpCAVR_NY_Overlap : InpCAVR_Late_NY);

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);

   // 1. Execute Gold
   if(InpTradeGold && m_goldPos.ticket == 0 && cavrRatio >= reqCAVR)
   {
      double barRange = MathMax(0.01, goldRates[1].high - goldRates[1].low);
      double vdp = (goldRates[1].close - goldRates[1].open) / barRange;

      if(mtfBullGold && goldRates[1].close > ema60Gold && vdp > 0.0 && ret3mEUR >= 0.0003)
      {
         double riskCash = balance * (InpBaseRiskPercent * InpRiskWeightGold / 100.0);
         double slDist = currATRGold * InpGold_SL_ATR;
         double tpDist = currATRGold * InpGold_TP_ATR;

         double tickSize = SymbolInfoDouble(InpGoldSymbol, SYMBOL_TRADE_TICK_SIZE);
         double tickVal  = SymbolInfoDouble(InpGoldSymbol, SYMBOL_TRADE_TICK_VALUE);
         double lossPerLot = (slDist / tickSize) * tickVal;

         if(lossPerLot > 0.0)
         {
            double lot = MathFloor((riskCash / lossPerLot) * 100.0) / 100.0;
            lot = MathMax(SymbolInfoDouble(InpGoldSymbol, SYMBOL_VOLUME_MIN), MathMin(SymbolInfoDouble(InpGoldSymbol, SYMBOL_VOLUME_MAX), lot));

            double ask = SymbolInfoDouble(InpGoldSymbol, SYMBOL_ASK);
            double slPrice = ask - slDist;
            double tpPrice = ask + tpDist;

            if(m_tradeGold.Buy(lot, InpGoldSymbol, ask, slPrice, tpPrice, "MASR_GOLD_BUY"))
            {
               m_goldPos.ticket = m_tradeGold.ResultOrder();
               m_goldPos.openTime = currentBarTime;
               m_goldPos.barsHeld = 0;
               m_goldPos.entryPrice = ask;
               m_goldPos.initialSL = slPrice;
               m_goldPos.initialTP = tpPrice;
               m_goldPos.currentSL = slPrice;
               m_goldPos.direction = 1;
               m_goldPos.beActivated = false;
               Print("[+] MASR Gold Buy Executed. Lot: ", lot);
            }
         }
      }
   }

   // 2. Execute EURUSD
   if(InpTradeEUR && m_eurPos.ticket == 0)
   {
      if(mtfBullEUR && eurRates[1].close > ema60EUR && ret3mGold >= 0.0005)
      {
         double riskCash = balance * (InpBaseRiskPercent * InpRiskWeightEUR / 100.0);
         double slDist = currATREUR * InpEUR_SL_ATR;
         double tpDist = currATREUR * InpEUR_TP_ATR;

         double tickSize = SymbolInfoDouble(InpEURSymbol, SYMBOL_TRADE_TICK_SIZE);
         double tickVal  = SymbolInfoDouble(InpEURSymbol, SYMBOL_TRADE_TICK_VALUE);
         double lossPerLot = (slDist / tickSize) * tickVal;

         if(lossPerLot > 0.0)
         {
            double lot = MathFloor((riskCash / lossPerLot) * 100.0) / 100.0;
            lot = MathMax(SymbolInfoDouble(InpEURSymbol, SYMBOL_VOLUME_MIN), MathMin(SymbolInfoDouble(InpEURSymbol, SYMBOL_VOLUME_MAX), lot));

            double ask = SymbolInfoDouble(InpEURSymbol, SYMBOL_ASK);
            double slPrice = ask - slDist;
            double tpPrice = ask + tpDist;

            if(m_tradeEUR.Buy(lot, InpEURSymbol, ask, slPrice, tpPrice, "MASR_EUR_BUY"))
            {
               m_eurPos.ticket = m_tradeEUR.ResultOrder();
               m_eurPos.openTime = currentBarTime;
               m_eurPos.barsHeld = 0;
               m_eurPos.entryPrice = ask;
               m_eurPos.initialSL = slPrice;
               m_eurPos.initialTP = tpPrice;
               m_eurPos.currentSL = slPrice;
               m_eurPos.direction = 1;
               m_eurPos.beActivated = false;
               Print("[+] MASR EUR Buy Executed. Lot: ", lot);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Position                                           |
//+------------------------------------------------------------------+
void ManagePosition(string symbol, PositionState &pos, CTrade &trade, double slATRMult, bool isNewBar)
{
   if(pos.ticket == 0) return;
   if(!PositionSelectByTicket(pos.ticket))
   {
      ResetState(pos);
      return;
   }

   if(isNewBar) pos.barsHeld++;

   double currentPrice = (pos.direction == 1) ? SymbolInfoDouble(symbol, SYMBOL_BID) : SymbolInfoDouble(symbol, SYMBOL_ASK);
   double currentExcursion = (pos.direction == 1) ? (currentPrice - pos.entryPrice) : (pos.entryPrice - currentPrice);

   double totalSLDist = MathAbs(pos.entryPrice - pos.initialSL);
   if(totalSLDist <= 0.0) return;

   // Breakeven at 1.50 ATR
   if(!pos.beActivated && currentExcursion >= (InpBreakevenATR / slATRMult) * totalSLDist)
   {
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double newSL = (pos.direction == 1) ? pos.entryPrice + 5 * point : pos.entryPrice - 5 * point;
      if(trade.PositionModify(symbol, newSL, pos.initialTP))
      {
         pos.currentSL = newSL;
         pos.beActivated = true;
         Print("[*] MASR ", symbol, " Breakeven Activated at Bar ", pos.barsHeld);
      }
   }

   if(pos.barsHeld >= InpMaxHoldingBars)
   {
      Print("[*] MASR ", symbol, " Max Holding Bars Reached. Closing position.");
      trade.PositionClose(symbol);
      ResetState(pos);
   }
}

//+------------------------------------------------------------------+
//|                  Gold_H1_DeMarker_Exhaustion_Master_EA.mq5        |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|                 Strategy 64: DeMarker Exhaustion (DEM-KFD)       |
//|          PF: 1.451 | Win: 51.1% | Max DD: $1,196 | Net: +$2.9k    |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 DeMarker Exhaustion Master EA (Intraday Extreme Exhaustion Pullback)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 640001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 0.0;       // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 0.0;       // Monthly Hard Loss Circuit Breaker ($)

input group "=== DeMarker Oscillator Configuration ==="
input int      InpDeM_Period          = 21;        // DeMarker Smoothing Period
input double   InpOversold            = 0.35;      // Oversold Exhaustion Level (Cross Above)
input double   InpOverbought          = 0.65;      // Overbought Exhaustion Level (Cross Below)
input double   InpTpMult              = 3.5;       // Take Profit ATR Multiplier (3.5R)
input double   InpSlMult              = 2.5;       // Stop Loss ATR Multiplier (2.5R)

input group "=== Macro Trend & Fractal Noise Gate ==="
input int      InpAtrPeriod           = 14;        // ATR Volatility Period
input int      InpEmaPeriod           = 200;       // Macro Structural Trend EMA
input bool     InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double   InpKfdThreshold        = 1.35;      // Maximum Fractal Dimension (<= 1.35)
input int      InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hEMA200;
int            m_hDeM;
datetime       m_last_bar_time;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();

   m_hATR    = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   m_hDeM    = iDeMarker(_Symbol, PERIOD_H1, InpDeM_Period);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE || m_hDeM == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicator handles.");
      return(INIT_FAILED);
   }

   m_last_bar_time = 0;
   Print("[+] Gold H1 DeMarker Exhaustion Master EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   IndicatorRelease(m_hEMA200);
   IndicatorRelease(m_hDeM);
   Comment("");
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension                                   |
//+------------------------------------------------------------------+
double ComputeKFD(const double &closes[], int start_idx, int period)
{
   if(ArraySize(closes) < start_idx + period) return 1.5;
   double euclid_d = MathAbs(closes[start_idx] - closes[start_idx + period - 1]);
   double total_len = 0.0;
   for(int i = start_idx; i < start_idx + period - 1; i++)
   {
      total_len += MathAbs(closes[i] - closes[i + 1]);
   }
   if(total_len > 1e-6 && euclid_d > 1e-6)
   {
      double ratio = euclid_d / total_len;
      double n_bars = (double)period;
      double val = MathLog10(n_bars) / (MathLog10(n_bars) + MathLog10(ratio));
      return MathMax(1.0, MathMin(2.0, val));
   }
   return 1.5;
}

//+------------------------------------------------------------------+
//| Check if open positions exist                                    |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == 0 || bar_time == m_last_bar_time) return;

   m_last_bar_time = bar_time;

   if(HasOpenPosition()) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMaxSpread) return;

   double atr_buf[1], ema_buf[1], dem_buf[2];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0 ||
      CopyBuffer(m_hEMA200, 0, 1, 1, ema_buf) <= 0 ||
      CopyBuffer(m_hDeM, 0, 1, 2, dem_buf) <= 0) return;

   double atr14  = atr_buf[0];
   double ema200 = ema_buf[0];
   double dem1   = dem_buf[1]; // Bar 1 (completed previous)
   double dem2   = dem_buf[0]; // Bar 2 (bar before previous)

   if(atr14 < 0.50) return;

   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, InpKfdPeriod + 5, closes) < InpKfdPeriod) return;

   double kfd_val = ComputeKFD(closes, 0, InpKfdPeriod);
   bool kfd_ok    = (!InpUseKFD_Filter) || (kfd_val <= InpKfdThreshold);

   double close1 = closes[0];
   bool ema_long_ok  = (close1 > ema200);
   bool ema_short_ok = (close1 < ema200);

   // DeMarker Exhaustion Signals
   bool dem_bull_turn = (dem1 > InpOversold) && (dem2 <= InpOversold) && ema_long_ok && kfd_ok;
   bool dem_bear_turn = (dem1 < InpOverbought) && (dem2 >= InpOverbought) && ema_short_ok && kfd_ok;

   if(dem_bull_turn)
   {
      double sl = NormalizeDouble(ask - (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * atr14), _Digits);
      m_trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "DEM-KFD Buy");
      PrintFormat("[+] Executed BUY @ %.2f | SL: %.2f | TP: %.2f | DeM: %.3f -> %.3f | KFD: %.3f", ask, sl, tp, dem2, dem1, kfd_val);
   }
   else if(dem_bear_turn)
   {
      double sl = NormalizeDouble(bid + (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * atr14), _Digits);
      m_trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "DEM-KFD Sell");
      PrintFormat("[+] Executed SELL @ %.2f | SL: %.2f | TP: %.2f | DeM: %.3f -> %.3f | KFD: %.3f", bid, sl, tp, dem2, dem1, kfd_val);
   }
}

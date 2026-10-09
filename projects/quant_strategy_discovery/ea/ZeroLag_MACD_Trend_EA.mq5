//+------------------------------------------------------------------+
//|                                     ZeroLag_MACD_Trend_EA.mq5     |
//|               Quantitative Strategy Discovery Champion #1        |
//|                                  Asset: XAUUSD / Gold CFD        |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Trading Laboratory"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Strategy Parameters (Zero-Lag MACD) ==="
input int                InpFastPeriod     = 15;       // Fast EMA Period
input int                InpSlowPeriod     = 34;       // Slow EMA Period
input int                InpSignalPeriod   = 9;        // Signal Period
input int                InpAtrPeriod      = 14;       // ATR Period for Volatility Stop
input double             InpSlAtrMult      = 2.0;      // Stop Loss ATR Multiplier
input double             InpTpRrMult       = 4.0;      // Take Profit R:R Multiplier (4.0R)

input group "=== Money Management & Risk ==="
input double             InpFixedLot       = 0.10;     // Fixed Trade Lot Size
input double             InpRiskPercent    = 0.0;      // Dynamic Risk % of Balance (0.0 = use Fixed Lot)
input int                InpMaxSpreadPoints= 50;       // Max Allowed Spread (Points / $0.50 on Gold)
input ulong              InpMagicNumber    = 306001;   // EA Magic Number

//--- Global Variables
CTrade         m_trade;
int            m_atr_handle;
datetime       m_last_bar_time;

//+------------------------------------------------------------------+
//| Calculate Zero-Lag EMA buffer on price array                     |
//+------------------------------------------------------------------+
bool CalculateZeroLagEMA(const double &price[], int period, double &output[])
{
   int n = ArraySize(price);
   if(n < period * 2) return false;
   
   double alpha = 2.0 / (period + 1.0);
   double ema1[];
   double ema2[];
   ArrayResize(ema1, n);
   ArrayResize(ema2, n);
   ArrayResize(output, n);
   
   // 1st EMA pass
   ema1[0] = price[0];
   for(int i = 1; i < n; i++)
      ema1[i] = (price[i] * alpha) + (ema1[i - 1] * (1.0 - alpha));
      
   // 2nd EMA pass
   ema2[0] = ema1[0];
   for(int i = 1; i < n; i++)
      ema2[i] = (ema1[i] * alpha) + (ema2[i - 1] * (1.0 - alpha));
      
   // Zero-Lag = 2*EMA1 - EMA2
   for(int i = 0; i < n; i++)
      output[i] = (2.0 * ema1[i]) - ema2[i];
      
   return true;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   m_atr_handle = iATR(_Symbol, _Period, InpAtrPeriod);
   if(m_atr_handle == INVALID_HANDLE)
   {
      Print("[!] Error creating ATR indicator handle.");
      return INIT_FAILED;
   }

   m_last_bar_time = 0;
   Print("[+] ZeroLag MACD Champion EA initialized successfully on ", _Symbol);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_atr_handle != INVALID_HANDLE)
      IndicatorRelease(m_atr_handle);
}

//+------------------------------------------------------------------+
//| Check if a new candle has opened                                 |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time != m_last_bar_time)
   {
      m_last_bar_time = current_bar_time;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Count active positions for this EA                               |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Calculate Lot Size based on risk percentage or fixed lot         |
//+------------------------------------------------------------------+
double CalculateLotSize(double sl_distance_points)
{
   if(InpRiskPercent <= 0.0 || sl_distance_points <= 0.0)
      return InpFixedLot;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (InpRiskPercent / 100.0);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(tick_value <= 0.0 || tick_size <= 0.0)
      return InpFixedLot;

   double cost_per_point = tick_value * (point / tick_size);
   double calculated_lot = risk_amount / (sl_distance_points * cost_per_point);

   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   calculated_lot = MathFloor(calculated_lot / step_lot) * step_lot;
   if(calculated_lot < min_lot) calculated_lot = min_lot;
   if(calculated_lot > max_lot) calculated_lot = max_lot;

   return calculated_lot;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Execute strictly on New Bar Open to prevent repainting/noise
   if(!IsNewBar()) return;

   // Check spread filter
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)
   {
      PrintFormat("[*] Spread too high: %d points (Max: %d)", spread, InpMaxSpreadPoints);
      return;
   }

   // Ensure only 1 active trade at a time
   if(CountOpenPositions() > 0) return;

   // Fetch historical close prices
   int lookback = 300;
   MqlRates rates[];
   ArraySetAsSeries(rates, false); // index 0 = oldest, n-1 = newest completed
   int copied = CopyRates(_Symbol, _Period, 1, lookback, rates);
   if(copied < lookback) return;

   double close_prices[];
   ArrayResize(close_prices, lookback);
   for(int i = 0; i < lookback; i++)
      close_prices[i] = rates[i].close;

   // Calculate Fast ZL-EMA & Slow ZL-EMA
   double zl_fast[], zl_slow[];
   if(!CalculateZeroLagEMA(close_prices, InpFastPeriod, zl_fast)) return;
   if(!CalculateZeroLagEMA(close_prices, InpSlowPeriod, zl_slow)) return;

   // Compute ZL-MACD line
   double zl_macd[];
   ArrayResize(zl_macd, lookback);
   for(int i = 0; i < lookback; i++)
      zl_macd[i] = zl_fast[i] - zl_slow[i];

   // Compute Signal Line (EMA of ZL-MACD)
   double zl_signal[];
   ArrayResize(zl_signal, lookback);
   double sig_alpha = 2.0 / (InpSignalPeriod + 1.0);
   zl_signal[0] = zl_macd[0];
   for(int i = 1; i < lookback; i++)
      zl_signal[i] = (zl_macd[i] * sig_alpha) + (zl_signal[i - 1] * (1.0 - sig_alpha));

   // Read ATR value at bar 1
   double atr_val[1];
   if(CopyBuffer(m_atr_handle, 0, 1, 1, atr_val) <= 0) return;
   double current_atr = atr_val[0];
   if(current_atr <= 0.0) return;

   // Detect Crossover at bar 1 (rates[lookback-1] is bar 1, rates[lookback-2] is bar 2)
   int b1 = lookback - 1;
   int b2 = lookback - 2;

   bool bull_cross = (zl_macd[b2] <= zl_signal[b2]) && (zl_macd[b1] > zl_signal[b1]);
   bool bear_cross = (zl_macd[b2] >= zl_signal[b2]) && (zl_macd[b1] < zl_signal[b1]);

   double sl_distance = InpSlAtrMult * current_atr;
   double tp_distance = sl_distance * InpTpRrMult;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl_points = sl_distance / point;
   double lot = CalculateLotSize(sl_points);

   if(bull_cross)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - sl_distance, _Digits);
      double tp = NormalizeDouble(ask + tp_distance, _Digits);
      m_trade.Buy(lot, _Symbol, ask, sl, tp, "ZL_MACD_Bullish_4R");
      PrintFormat("[+] Executed BUY | Lot: %.2f | SL: %.2f | TP: %.2f | 4.0R Target", lot, sl, tp);
   }
   else if(bear_cross)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + sl_distance, _Digits);
      double tp = NormalizeDouble(bid - tp_distance, _Digits);
      m_trade.Sell(lot, _Symbol, bid, sl, tp, "ZL_MACD_Bearish_4R");
      PrintFormat("[+] Executed SELL | Lot: %.2f | SL: %.2f | TP: %.2f | 4.0R Target", lot, sl, tp);
   }
}

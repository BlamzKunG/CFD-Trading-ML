//+------------------------------------------------------------------+
//|                                  TTM_Squeeze_Expansion_EA.mq5     |
//|               Quantitative Strategy Discovery Champion #2        |
//|                                  Asset: XAUUSD / Gold CFD        |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Trading Laboratory"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Strategy Parameters (TTM Squeeze) ==="
input int                InpBbLength       = 20;       // Bollinger Bands Length
input double             InpBbMult         = 2.0;      // Bollinger Bands StdDev Multiplier
input double             InpKcMult         = 2.0;      // Keltner Channel ATR Multiplier
input int                InpMinSqueezeBars = 8;        // Minimum Consecutive Squeeze Bars Required
input int                InpEmaFilterPeriod= 200;      // Macro Trend EMA Filter Period
input int                InpAtrPeriod      = 14;       // ATR Period for Volatility Stop
input double             InpSlAtrMult      = 3.0;      // Stop Loss ATR Multiplier
input double             InpTpRrMult       = 3.0;      // Take Profit R:R Multiplier (3.0R)

input group "=== Money Management & Risk ==="
input double             InpFixedLot       = 0.10;     // Fixed Trade Lot Size
input double             InpRiskPercent    = 0.0;      // Dynamic Risk % of Balance (0.0 = use Fixed Lot)
input int                InpMaxSpreadPoints= 50;       // Max Allowed Spread (Points / $0.50 on Gold)
input ulong              InpMagicNumber    = 304001;   // EA Magic Number

//--- Global Variables
CTrade         m_trade;
int            m_atr_handle;
int            m_ema_handle;
datetime       m_last_bar_time;

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

   m_ema_handle = iMA(_Symbol, _Period, InpEmaFilterPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(m_ema_handle == INVALID_HANDLE)
   {
      Print("[!] Error creating EMA indicator handle.");
      return INIT_FAILED;
   }

   m_last_bar_time = 0;
   Print("[+] TTM Squeeze Champion EA initialized successfully on ", _Symbol);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_atr_handle != INVALID_HANDLE) IndicatorRelease(m_atr_handle);
   if(m_ema_handle != INVALID_HANDLE) IndicatorRelease(m_ema_handle);
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
   if(!IsNewBar()) return;

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   if(CountOpenPositions() > 0) return;

   int lookback = InpMinSqueezeBars + InpBbLength + 10;
   MqlRates rates[];
   ArraySetAsSeries(rates, true); // index 0 = current, 1 = completed bar 1
   int copied = CopyRates(_Symbol, _Period, 0, lookback, rates);
   if(copied < lookback) return;

   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_atr_handle, 0, 0, lookback, atr_buf) < lookback) return;

   double ema_buf[2];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(m_ema_handle, 0, 1, 2, ema_buf) < 2) return;

   // Check Squeeze state for previous bars
   // A bar is in squeeze if BB is strictly inside KC:
   // BB_lower > KC_lower AND BB_upper < KC_upper
   // Equivalent to: stddev * BbMult < atr * KcMult
   bool is_squeeze_history[];
   ArrayResize(is_squeeze_history, InpMinSqueezeBars + 2);

   for(int b = 1; b <= InpMinSqueezeBars + 1; b++)
   {
      // Calculate 20 SMA & StdDev for bar b
      double sum = 0.0;
      for(int k = 0; k < InpBbLength; k++)
         sum += rates[b + k].close;
      double sma = sum / InpBbLength;

      double var_sum = 0.0;
      for(int k = 0; k < InpBbLength; k++)
         var_sum += MathPow(rates[b + k].close - sma, 2.0);
      double stddev = MathSqrt(var_sum / InpBbLength);

      double bb_width = stddev * InpBbMult;
      double kc_width = atr_buf[b] * InpKcMult;

      is_squeeze_history[b] = (bb_width < kc_width);
   }

   // Condition 1: Bar 1 must be a Squeeze FIRE (is_squeeze == false)
   bool bar1_is_squeeze = is_squeeze_history[1];
   if(bar1_is_squeeze) return; // Still in squeeze, wait for fire

   // Condition 2: Bars 2 through (InpMinSqueezeBars + 1) must have been in squeeze
   int consecutive_squeeze = 0;
   for(int b = 2; b <= InpMinSqueezeBars + 1; b++)
   {
      if(is_squeeze_history[b])
         consecutive_squeeze++;
      else
         break;
   }

   if(consecutive_squeeze < InpMinSqueezeBars) return; // Insufficient coiling duration

   // Condition 3: Momentum Direction & Trend Filter
   double close1 = rates[1].close;
   double ema1 = ema_buf[0];
   double current_atr = atr_buf[1];
   if(current_atr <= 0.0) return;

   // Squeeze Momentum Delta
   double mid_price = (rates[1].high + rates[1].low) * 0.5;
   double delta = close1 - mid_price;

   double sl_distance = InpSlAtrMult * current_atr;
   double tp_distance = sl_distance * InpTpRrMult;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl_points = sl_distance / point;
   double lot = CalculateLotSize(sl_points);

   // Bullish Breakout Fire
   if(delta > 0 && close1 > ema1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - sl_distance, _Digits);
      double tp = NormalizeDouble(ask + tp_distance, _Digits);
      m_trade.Buy(lot, _Symbol, ask, sl, tp, "TTM_Squeeze_Fire_Bull_3R");
      PrintFormat("[+] Executed BUY (TTM Fire) | Coiling: %d bars | Lot: %.2f | SL: %.2f | TP: %.2f", consecutive_squeeze, lot, sl, tp);
   }
   // Bearish Breakout Fire
   else if(delta < 0 && close1 < ema1)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + sl_distance, _Digits);
      double tp = NormalizeDouble(bid - tp_distance, _Digits);
      m_trade.Sell(lot, _Symbol, bid, sl, tp, "TTM_Squeeze_Fire_Bear_3R");
      PrintFormat("[+] Executed SELL (TTM Fire) | Coiling: %d bars | Lot: %.2f | SL: %.2f | TP: %.2f", consecutive_squeeze, lot, sl, tp);
   }
}

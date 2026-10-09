//+------------------------------------------------------------------+
//|                                Supertrend_Trailing_Pro_EA.mq5     |
//|               Quantitative Strategy Discovery Champion #3        |
//|                                  Asset: XAUUSD / Gold CFD        |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Trading Laboratory"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Strategy Parameters (Supertrend) ==="
input int                InpAtrPeriod      = 14;       // ATR Volatility Period
input double             InpMultiplier     = 3.0;      // Supertrend ATR Multiplier
input bool               InpUseEmaFilter   = true;     // Enable Macro EMA Filter
input int                InpEmaPeriod      = 200;      // Macro Trend EMA Period

input group "=== Money Management & Risk ==="
input double             InpFixedLot       = 0.10;     // Fixed Trade Lot Size
input double             InpRiskPercent    = 0.0;      // Dynamic Risk % of Balance (0.0 = use Fixed Lot)
input int                InpMaxSpreadPoints= 50;       // Max Allowed Spread (Points / $0.50 on Gold)
input ulong              InpMagicNumber    = 303001;   // EA Magic Number

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

   m_ema_handle = iMA(_Symbol, _Period, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(m_ema_handle == INVALID_HANDLE)
   {
      Print("[!] Error creating EMA indicator handle.");
      return INIT_FAILED;
   }

   m_last_bar_time = 0;
   Print("[+] Supertrend Pro Trailing EA initialized successfully on ", _Symbol);
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
//| Compute Supertrend series on completed bars                      |
//+------------------------------------------------------------------+
void ComputeSupertrend(const MqlRates &rates[], const double &atr[], int n, int &trend[], double &st_lower[], double &st_upper[])
{
   ArrayResize(trend, n);
   ArrayResize(st_lower, n);
   ArrayResize(st_upper, n);

   trend[0] = 1;
   double med0 = (rates[0].high + rates[0].low) * 0.5;
   st_lower[0] = med0 - InpMultiplier * atr[0];
   st_upper[0] = med0 + InpMultiplier * atr[0];

   for(int i = 1; i < n; i++)
   {
      double med = (rates[i].high + rates[i].low) * 0.5;
      double basic_up = med + InpMultiplier * atr[i];
      double basic_low = med - InpMultiplier * atr[i];

      // Ratchet lower band upward
      if(basic_low > st_lower[i - 1] || rates[i - 1].close < st_lower[i - 1])
         st_lower[i] = basic_low;
      else
         st_lower[i] = st_lower[i - 1];

      // Ratchet upper band downward
      if(basic_up < st_upper[i - 1] || rates[i - 1].close > st_upper[i - 1])
         st_upper[i] = basic_up;
      else
         st_upper[i] = st_upper[i - 1];

      // Determine trend direction
      if(trend[i - 1] == 1)
      {
         if(rates[i].close < st_lower[i])
            trend[i] = -1;
         else
            trend[i] = 1;
      }
      else
      {
         if(rates[i].close > st_upper[i])
            trend[i] = 1;
         else
            trend[i] = -1;
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsNewBar()) return;

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   int lookback = 200;
   MqlRates rates[];
   ArraySetAsSeries(rates, false); // index 0 = oldest, n-1 = newest completed bar 1
   int copied = CopyRates(_Symbol, _Period, 1, lookback, rates);
   if(copied < lookback) return;

   double atr_buf[];
   ArraySetAsSeries(atr_buf, false);
   if(CopyBuffer(m_atr_handle, 0, 1, lookback, atr_buf) < lookback) return;

   double ema_buf[1];
   if(CopyBuffer(m_ema_handle, 0, 1, 1, ema_buf) < 1) return;
   double ema_val = ema_buf[0];

   int trend[];
   double st_lower[], st_upper[];
   ComputeSupertrend(rates, atr_buf, lookback, trend, st_lower, st_upper);

   int b1 = lookback - 1; // latest completed bar
   int b2 = lookback - 2; // previous completed bar

   int cur_trend = trend[b1];
   int prev_trend = trend[b2];
   double current_st_stop = (cur_trend == 1) ? st_lower[b1] : st_upper[b1];

   // 1. Manage Active Positions (Trailing Stop & Reverse Flip)
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         ulong ticket = PositionGetTicket(i);
         long pos_type = PositionGetInteger(POSITION_TYPE);
         double pos_sl = PositionGetDouble(POSITION_SL);

         if(pos_type == POSITION_TYPE_BUY)
         {
            // Close if trend flipped to Bearish
            if(cur_trend == -1)
            {
               m_trade.PositionClose(ticket);
               Print("[*] Closed BUY position due to Supertrend Bearish flip.");
               continue;
            }
            // Ratchet Trailing Stop Upward
            double new_sl = NormalizeDouble(st_lower[b1], _Digits);
            if(new_sl > pos_sl && new_sl < SymbolInfoDouble(_Symbol, SYMBOL_BID))
            {
               m_trade.PositionModify(ticket, new_sl, 0.0);
               PrintFormat("[*] Ratcheted BUY Trailing SL to: %.2f", new_sl);
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            // Close if trend flipped to Bullish
            if(cur_trend == 1)
            {
               m_trade.PositionClose(ticket);
               Print("[*] Closed SELL position due to Supertrend Bullish flip.");
               continue;
            }
            // Ratchet Trailing Stop Downward
            double new_sl = NormalizeDouble(st_upper[b1], _Digits);
            if((pos_sl == 0.0 || new_sl < pos_sl) && new_sl > SymbolInfoDouble(_Symbol, SYMBOL_ASK))
            {
               m_trade.PositionModify(ticket, new_sl, 0.0);
               PrintFormat("[*] Ratcheted SELL Trailing SL to: %.2f", new_sl);
            }
         }
      }
   }

   // 2. Check Entries on Fresh Trend Flip
   int active_positions = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         active_positions++;
   }

   if(active_positions == 0)
   {
      double close1 = rates[b1].close;
      double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

      // Bullish Trend Flip (prev: -1, cur: 1)
      if(prev_trend == -1 && cur_trend == 1)
      {
         if(!InpUseEmaFilter || close1 > ema_val)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = NormalizeDouble(st_lower[b1], _Digits);
            double sl_points = (ask - sl) / point;
            double lot = CalculateLotSize(sl_points);

            m_trade.Buy(lot, _Symbol, ask, sl, 0.0, "Supertrend_Bullish_Trail");
            PrintFormat("[+] Executed BUY | Lot: %.2f | Initial Trailing SL: %.2f", lot, sl);
         }
      }
      // Bearish Trend Flip (prev: 1, cur: -1)
      else if(prev_trend == 1 && cur_trend == -1)
      {
         if(!InpUseEmaFilter || close1 < ema_val)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = NormalizeDouble(st_upper[b1], _Digits);
            double sl_points = (sl - bid) / point;
            double lot = CalculateLotSize(sl_points);

            m_trade.Sell(lot, _Symbol, bid, sl, 0.0, "Supertrend_Bearish_Trail");
            PrintFormat("[+] Executed SELL | Lot: %.2f | Initial Trailing SL: %.2f", lot, sl);
         }
      }
   }
}

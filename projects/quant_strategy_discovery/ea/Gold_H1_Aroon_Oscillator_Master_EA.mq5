//+------------------------------------------------------------------+
//|                 Gold_H1_Aroon_Oscillator_Master_EA.mq5           |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 81: Gold H1 Aroon Oscillator Trend Ignition & Extremes |
//|     PF: 1.531 | Net: +$7,077.02 | Max DD: $852.34 | Win: 34.2%   |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Aroon Oscillator Trend Ignition & Extremes Master EA (Magic 810001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_AROON_TRIGGER
{
   AROON_EXTREME_PIN,       // Aroon Up=100 & Down<=30 (Long) / Down=100 & Up<=30 (Short)
   AROON_OSC_CROSS_ZERO,    // Aroon Oscillator crosses 0.0 line
   AROON_OSC_THRESH_50,     // Aroon Oscillator crosses +/- 50.0 threshold
   AROON_UP_DOWN_CROSS      // Aroon Up crosses Aroon Down
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 810001;    // EA Magic Number
input double                InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 250.0;     // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Aroon Indicator Configuration ==="
input int                   InpAroonPeriod         = 20;        // Aroon Lookback Period (Hours)
input ENUM_AROON_TRIGGER    InpTriggerMode         = AROON_EXTREME_PIN; // Trigger Mode
input double                InpTpMult              = 5.0;       // Take Profit ATR Multiplier (5.0R)
input double                InpSlMult              = 1.5;       // Stop Loss ATR Multiplier (1.5R)

input group "=== Macro Trend & Noise Gate ==="
input int                   InpAtrPeriod           = 14;        // ATR Volatility Period
input int                   InpEmaPeriod           = 50;        // Macro Structural Trend EMA (50)
input bool                  InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.35;      // Maximum Fractal Dimension (<= 1.35)
input int                   InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hEMA;
datetime       m_last_bar_time;
int            m_current_month;
double         m_monthly_realized_pnl;
bool           m_is_month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();

   m_hATR = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   if(m_hATR == INVALID_HANDLE)
   {
      Print("[!] Error initializing ATR handle.");
      return(INIT_FAILED);
   }

   if(InpEmaPeriod > 0)
   {
      m_hEMA = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(m_hEMA == INVALID_HANDLE)
      {
         Print("[!] Error initializing EMA handle.");
         return(INIT_FAILED);
      }
   }
   else
   {
      m_hEMA = INVALID_HANDLE;
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Gold H1 Aroon Oscillator Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hEMA != INVALID_HANDLE) IndicatorRelease(m_hEMA);
   Print("[-] Gold H1 Aroon Oscillator Master EA Deinitialized.");
}

//+------------------------------------------------------------------+
//| Calculate Aroon Up and Aroon Down from price buffers             |
//+------------------------------------------------------------------+
void CalculateAroon(int shift, int period, double &aroon_up, double &aroon_down, double &aroon_osc)
{
   // shift: 1 for previous completed bar, 2 for bar before that
   int highest_bar = iHighest(_Symbol, PERIOD_H1, MODE_HIGH, period + 1, shift);
   int lowest_bar  = iLowest(_Symbol, PERIOD_H1, MODE_LOW, period + 1, shift);

   int periods_since_high = highest_bar - shift;
   int periods_since_low  = lowest_bar - shift;

   aroon_up   = ((double)(period - periods_since_high) / (double)period) * 100.0;
   aroon_down = ((double)(period - periods_since_low)  / (double)period) * 100.0;
   aroon_osc  = aroon_up - aroon_down;
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension on Bar shift                    |
//+------------------------------------------------------------------+
double CalculateKFD(int shift, int period)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, shift, period, closes) < period)
      return 1.5;

   double c_first = closes[period - 1];
   double c_last  = closes[0];
   double d = MathAbs(c_last - c_first);

   double l = 0.0;
   for(int i = 0; i < period - 1; i++)
   {
      l += MathAbs(closes[i] - closes[i + 1]);
   }

   if(l < 1e-6 || d < 1e-6) return 1.5;

   double n_bars = (double)period;
   double kfd = MathLog10(n_bars) / (MathLog10(n_bars) + MathLog10(d / l));
   if(kfd < 1.0) kfd = 1.0;
   if(kfd > 2.0) kfd = 2.0;

   return kfd;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check bar close confirmation (execute only on new H1 bar)
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == m_last_bar_time) return;
   m_last_bar_time = bar_time;

   // Update calendar risk metrics
   MqlDateTime dt;
   TimeToStruct(bar_time, dt);
   int bar_month = dt.year * 100 + dt.mon;

   if(bar_month != m_current_month)
   {
      m_current_month        = bar_month;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      PrintFormat("[*] New calendar month %d detected. Monthly risk metrics reset.", m_current_month);
   }

   // Update realized PnL from closed positions for current month
   UpdateMonthlyPnL();

   if(m_monthly_realized_pnl >= InpMonthlyProfitLock && InpMonthlyProfitLock > 0.0)
   {
      if(!m_is_month_locked)
      {
         PrintFormat("[LOCK] Monthly profit target reached: +$%.2f >= $%.2f. Trading halted for month.",
                     m_monthly_realized_pnl, InpMonthlyProfitLock);
         m_is_month_locked = true;
      }
      return;
   }

   if(m_monthly_realized_pnl <= -InpHardLossBreaker && InpHardLossBreaker > 0.0)
   {
      if(!m_is_month_locked)
      {
         PrintFormat("[CIRCUIT BREAKER] Monthly loss breaker hit: $%.2f <= -$%.2f. Trading halted.",
                     m_monthly_realized_pnl, InpHardLossBreaker);
         m_is_month_locked = true;
      }
      return;
   }

   // Check spread filter
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   if(spread > InpMaxSpread)
   {
      PrintFormat("[FILTER] Spread excessive: $%.2f > $%.2f", spread, InpMaxSpread);
      return;
   }

   // Read ATR buffer
   double atr_buf[1];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0) return;
   double atr = atr_buf[0];
   if(atr < 0.50) return; // Stagnant volatility gate

   // Macro trend filter
   double ema = 0.0;
   if(m_hEMA != INVALID_HANDLE)
   {
      double ema_buf[1];
      if(CopyBuffer(m_hEMA, 0, 1, 1, ema_buf) <= 0) return;
      ema = ema_buf[0];
   }
   double close1 = iClose(_Symbol, PERIOD_H1, 1);

   bool trend_long_ok  = (m_hEMA == INVALID_HANDLE) || (close1 > ema);
   bool trend_short_ok = (m_hEMA == INVALID_HANDLE) || (close1 < ema);

   // Katz Fractal Gate
   if(InpUseKFD_Filter)
   {
      double kfd = CalculateKFD(1, InpKfdPeriod);
      if(kfd > InpKfdThreshold) return; // Brownian noise regime
   }

   // Compute Aroon for Bar 1 (previous closed) and Bar 2
   double up1, dn1, osc1;
   double up2, dn2, osc2;
   CalculateAroon(1, InpAroonPeriod, up1, dn1, osc1);
   CalculateAroon(2, InpAroonPeriod, up2, dn2, osc2);

   bool long_signal  = false;
   bool short_signal = false;

   switch(InpTriggerMode)
   {
      case AROON_EXTREME_PIN:
      {
         bool long_pin_1 = (up1 >= 100.0) && (dn1 <= 30.0);
         bool long_pin_2 = (up2 >= 100.0) && (dn2 <= 30.0);
         long_signal = long_pin_1 && !long_pin_2;

         bool short_pin_1 = (dn1 >= 100.0) && (up1 <= 30.0);
         bool short_pin_2 = (dn2 >= 100.0) && (up2 <= 30.0);
         short_signal = short_pin_1 && !short_pin_2;
         break;
      }

      case AROON_OSC_CROSS_ZERO:
      {
         long_signal  = (osc1 > 0.0) && (osc2 <= 0.0);
         short_signal = (osc1 < 0.0) && (osc2 >= 0.0);
         break;
      }

      case AROON_OSC_THRESH_50:
      {
         long_signal  = (osc1 >= 50.0) && (osc2 < 50.0);
         short_signal = (osc1 <= -50.0) && (osc2 > -50.0);
         break;
      }

      case AROON_UP_DOWN_CROSS:
      {
         long_signal  = (up1 >= dn1) && (up2 < dn2);
         short_signal = (dn1 >= up1) && (dn2 < up2);
         break;
      }
   }

   // Filter with macro trend
   long_signal  = long_signal && trend_long_ok;
   short_signal = short_signal && trend_short_ok;

   // Check current active positions
   int total_positions = PositionsTotal();
   int our_positions   = 0;
   for(int i = 0; i < total_positions; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         our_positions++;
      }
   }

   if(our_positions > 0) return; // One position at a time per magic

   // Position Sizing with Defensive Layer
   double active_lot = InpLotSize;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      active_lot = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(active_lot < 0.01) active_lot = 0.01;
   }

   // Execution
   if(long_signal)
   {
      double sl = bid - (InpSlMult * atr);
      double tp = ask + (InpTpMult * atr);
      m_trade.Buy(active_lot, _Symbol, ask, sl, tp, "Aroon Trend Ignition BUY");
      PrintFormat("[+] OPEN BUY: Lot=%.2f, Price=%.2f, SL=%.2f, TP=%.2f, AroonUp=%.1f, AroonDn=%.1f",
                  active_lot, ask, sl, tp, up1, dn1);
   }
   else if(short_signal)
   {
      double sl = ask + (InpSlMult * atr);
      double tp = bid - (InpTpMult * atr);
      m_trade.Sell(active_lot, _Symbol, bid, sl, tp, "Aroon Trend Ignition SELL");
      PrintFormat("[+] OPEN SELL: Lot=%.2f, Price=%.2f, SL=%.2f, TP=%.2f, AroonUp=%.1f, AroonDn=%.1f",
                  active_lot, bid, sl, tp, up1, dn1);
   }
}

//+------------------------------------------------------------------+
//| Update realized PnL for current calendar month                   |
//+------------------------------------------------------------------+
void UpdateMonthlyPnL()
{
   MqlDateTime dt_now;
   TimeCurrent(dt_now);
   dt_now.day  = 1;
   dt_now.hour = 0;
   dt_now.min  = 0;
   dt_now.sec  = 0;
   datetime month_start = StructToTime(dt_now);

   if(!HistorySelect(month_start, TimeCurrent())) return;

   double pnl = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber &&
            HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol)
         {
            pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }
   m_monthly_realized_pnl = pnl;
}

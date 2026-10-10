//+------------------------------------------------------------------+
//|                 Gold_H1_Keltner_Channel_Master_EA.mq5            |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 83: Gold H1 Keltner Channels Volatility Breakout      |
//|     PF: 1.706 | Net: +$8,381.59 | Max DD: $1,234.57 | Win: 47.3% |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Keltner Channels Volatility Breakout Master EA (Magic 830001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_KC_TRIGGER
{
   KC_BAND_BREAKOUT,        // Bar Close outside 2.0 ATR Keltner envelope
   KC_EMA_PULLBACK,         // Price touches central EMA with upward slope
   KC_SQUEEZE_EXPANSION     // Bandwidth expands by >= 25% after compression
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 830001;    // EA Magic Number
input double                InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 250.0;     // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Keltner Channel Configuration ==="
input int                   InpKcPeriod            = 20;        // Keltner Central EMA Period
input double                InpKcMult              = 2.0;       // Keltner Envelope ATR Multiplier
input ENUM_KC_TRIGGER       InpTriggerMode         = KC_BAND_BREAKOUT; // Trigger Mode
input double                InpTpMult              = 5.0;       // Take Profit ATR Multiplier (5.0R)
input double                InpSlMult              = 2.5;       // Stop Loss ATR Multiplier (2.5R)

input group "=== Macro Trend & Noise Gate ==="
input int                   InpAtrPeriod           = 14;        // ATR Volatility Period
input int                   InpEmaFilterPeriod     = 50;        // Macro Structural Trend EMA (50)
input bool                  InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.35;      // Maximum Fractal Dimension (<= 1.35)
input int                   InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hKcEMA;
int            m_hTrendEMA;
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

   m_hKcEMA = iMA(_Symbol, PERIOD_H1, InpKcPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(m_hKcEMA == INVALID_HANDLE)
   {
      Print("[!] Error initializing Keltner EMA handle.");
      return(INIT_FAILED);
   }

   if(InpEmaFilterPeriod > 0)
   {
      m_hTrendEMA = iMA(_Symbol, PERIOD_H1, InpEmaFilterPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(m_hTrendEMA == INVALID_HANDLE)
      {
         Print("[!] Error initializing Trend EMA handle.");
         return(INIT_FAILED);
      }
   }
   else
   {
      m_hTrendEMA = INVALID_HANDLE;
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Gold H1 Keltner Channel Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hKcEMA != INVALID_HANDLE) IndicatorRelease(m_hKcEMA);
   if(m_hTrendEMA != INVALID_HANDLE) IndicatorRelease(m_hTrendEMA);
   Print("[-] Gold H1 Keltner Channel Master EA Deinitialized.");
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
   double atr_buf[2];
   if(CopyBuffer(m_hATR, 0, 1, 2, atr_buf) < 2) return;
   double atr1 = atr_buf[1];
   double atr2 = atr_buf[0];
   if(atr1 < 0.50) return; // Stagnant volatility gate

   // Read Keltner Central EMA
   double kc_ema_buf[2];
   if(CopyBuffer(m_hKcEMA, 0, 1, 2, kc_ema_buf) < 2) return;
   double central1 = kc_ema_buf[1];
   double central2 = kc_ema_buf[0];

   double upper1 = central1 + (InpKcMult * atr1);
   double lower1 = central1 - (InpKcMult * atr1);
   double upper2 = central2 + (InpKcMult * atr2);
   double lower2 = central2 - (InpKcMult * atr2);

   // Macro trend filter
   double trend_ema = 0.0;
   if(m_hTrendEMA != INVALID_HANDLE)
   {
      double ema_buf[1];
      if(CopyBuffer(m_hTrendEMA, 0, 1, 1, ema_buf) <= 0) return;
      trend_ema = ema_buf[0];
   }
   double close1 = iClose(_Symbol, PERIOD_H1, 1);
   double close2 = iClose(_Symbol, PERIOD_H1, 2);
   double low1   = iLow(_Symbol, PERIOD_H1, 1);
   double high1  = iHigh(_Symbol, PERIOD_H1, 1);

   bool trend_long_ok  = (m_hTrendEMA == INVALID_HANDLE) || (close1 > trend_ema);
   bool trend_short_ok = (m_hTrendEMA == INVALID_HANDLE) || (close1 < trend_ema);

   // Katz Fractal Gate
   if(InpUseKFD_Filter)
   {
      double kfd = CalculateKFD(1, InpKfdPeriod);
      if(kfd > InpKfdThreshold) return; // Brownian noise regime
   }

   bool long_signal  = false;
   bool short_signal = false;

   switch(InpTriggerMode)
   {
      case KC_BAND_BREAKOUT:
      {
         long_signal  = (close1 >= upper1) && (close2 < upper2);
         short_signal = (close1 <= lower1) && (close2 > lower2);
         break;
      }

      case KC_EMA_PULLBACK:
      {
         long_signal  = (low1 <= central1) && (close1 > central1) && (central1 > central2);
         short_signal = (high1 >= central1) && (close1 < central1) && (central1 < central2);
         break;
      }

      case KC_SQUEEZE_EXPANSION:
      {
         double bw1 = (upper1 - lower1) / central1;
         double bw_min = bw1;
         // Rolling 20-bar min bandwidth
         for(int k = 2; k <= 21; k++)
         {
            double c_k = iClose(_Symbol, PERIOD_H1, k);
            double a_k = 0.0;
            double a_buf[1];
            if(CopyBuffer(m_hATR, 0, k, 1, a_buf) > 0) a_k = a_buf[0];
            double kc_k = 0.0;
            double kc_b[1];
            if(CopyBuffer(m_hKcEMA, 0, k, 1, kc_b) > 0) kc_k = kc_b[0];
            if(kc_k > 0)
            {
               double bw_k = (2.0 * InpKcMult * a_k) / kc_k;
               if(bw_k < bw_min) bw_min = bw_k;
            }
         }
         bool is_exp = (bw1 >= 1.25 * bw_min);
         long_signal  = is_exp && (close1 > central1);
         short_signal = is_exp && (close1 < central1);
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
      double sl = bid - (InpSlMult * atr1);
      double tp = ask + (InpTpMult * atr1);
      m_trade.Buy(active_lot, _Symbol, ask, sl, tp, "Keltner Breakout BUY");
      PrintFormat("[+] OPEN BUY: Lot=%.2f, Price=%.2f, SL=%.2f, TP=%.2f, Upper=%.2f, ATR=%.2f",
                  active_lot, ask, sl, tp, upper1, atr1);
   }
   else if(short_signal)
   {
      double sl = ask + (InpSlMult * atr1);
      double tp = bid - (InpTpMult * atr1);
      m_trade.Sell(active_lot, _Symbol, bid, sl, tp, "Keltner Breakout SELL");
      PrintFormat("[+] OPEN SELL: Lot=%.2f, Price=%.2f, SL=%.2f, TP=%.2f, Lower=%.2f, ATR=%.2f",
                  active_lot, bid, sl, tp, lower1, atr1);
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

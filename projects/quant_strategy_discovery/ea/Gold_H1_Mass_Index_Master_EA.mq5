//+------------------------------------------------------------------+
//|                   Gold_H1_Mass_Index_Master_EA.mq5               |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 87: Gold H1 Donald Dorsey's Mass Index Volatility      |
//|   Expansion & Reversal Bulge (MASS-VRB-KFD)                       |
//|     PF: 2.156 | Net: +$8,357.21 | Max DD: $632.46 | Win: 54.3%   |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Donald Dorsey Mass Index Volatility Expansion Master EA (Magic 870001)"
#property strict

#include <Trade\Trade.mqh>

//--- ENUM TRIGGER MODE ---
enum ENUM_MASS_TRIGGER
{
   MASS_EXPANSION_IGNITION,   // MI crosses above expansion threshold (e.g. 25.5) in trend direction
   DORSEY_REVERSAL_BULGE,     // Classic Dorsey: MI drops below bulge_low after bulge_high (Counter-trend)
   DORSEY_CONTINUATION_BULGE, // Trend Continuation: MI drops below bulge_low after bulge_high (With trend)
   MASS_COMPRESSION_TURN      // Range Contraction Exhaustion: MI dips below threshold and turns up
};

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 870001;    // EA Magic Number
input double                InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Donald Dorsey Mass Index Configuration ==="
input int                   InpEmaPeriod           = 7;         // Single/Double EMA Smoothing Period (7)
input int                   InpSumPeriod           = 25;        // Ratio Lookback Sum Window (25)
input ENUM_MASS_TRIGGER     InpTriggerMode         = MASS_EXPANSION_IGNITION; // Trigger Mechanism
input double                InpExpansionThreshold  = 25.5;      // Volatility Expansion Threshold (25.5)
input double                InpBulgeHigh           = 27.0;      // Dorsey Reversal Bulge Peak Threshold
input double                InpBulgeLow            = 26.5;      // Dorsey Reversal Bulge Resolution Threshold
input double                InpTpMult              = 3.5;       // Take Profit ATR Multiplier (3.5R)
input double                InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

input group "=== Macro Trend & Noise Gate ==="
input int                   InpAtrPeriod           = 14;        // ATR Volatility Period
input int                   InpTrendEmaPeriod      = 50;        // Macro Structural Trend EMA (50)
input bool                  InpUseKfdFilter        = true;      // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.35;      // Maximum Fractal Dimension (<= 1.35)
input int                   InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
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

   if(InpTrendEmaPeriod > 0)
   {
      m_hTrendEMA = iMA(_Symbol, PERIOD_H1, InpTrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
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

   Print("[+] Gold H1 Mass Index Master EA Initialized Successfully. Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hTrendEMA != INVALID_HANDLE) IndicatorRelease(m_hTrendEMA);
}

//+------------------------------------------------------------------+
//| Calculate Donald Dorsey Mass Index for a specific shift bar      |
//+------------------------------------------------------------------+
double CalculateMassIndex(int shift, int ema_period, int sum_period)
{
   int total_calc = sum_period + (ema_period * 4);
   int required_bars = shift + total_calc + 10;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 0, required_bars, rates) < required_bars)
      return 25.0;

   double hl[];
   ArrayResize(hl, total_calc);
   double alpha = 2.0 / (ema_period + 1.0);

   for(int k = 0; k < total_calc; k++)
   {
      int r_idx = shift + total_calc - 1 - k;
      hl[k] = rates[r_idx].high - rates[r_idx].low;
   }

   // EMA1: Single EMA of Range
   double ema1[];
   ArrayResize(ema1, total_calc);
   ema1[0] = hl[0];
   for(int k = 1; k < total_calc; k++)
      ema1[k] = (hl[k] * alpha) + (ema1[k - 1] * (1.0 - alpha));

   // EMA2: Double EMA of Range
   double ema2[];
   ArrayResize(ema2, total_calc);
   ema2[0] = ema1[0];
   for(int k = 1; k < total_calc; k++)
      ema2[k] = (ema1[k] * alpha) + (ema2[k - 1] * (1.0 - alpha));

   // Sum of Ratio over sum_period ending at index (total_calc - 1)
   double sum_ratio = 0.0;
   for(int k = total_calc - sum_period; k < total_calc; k++)
   {
      if(ema2[k] > 1e-6)
         sum_ratio += (ema1[k] / ema2[k]);
      else
         sum_ratio += 1.0;
   }

   return sum_ratio;
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension on H1                           |
//+------------------------------------------------------------------+
double CalculateKFD(int shift, int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, shift, period + 1, rates);
   if(copied < period + 1) return 1.5;

   double c_first = rates[period].close;
   double c_last  = rates[0].close;
   double euclid_d = MathAbs(c_last - c_first);

   double total_len = 0.0;
   for(int k = 0; k < period; k++)
   {
      total_len += MathAbs(rates[k].close - rates[k + 1].close);
   }

   if(total_len > 1e-6 && euclid_d > 1e-6)
   {
      double val = MathLog10(period) / (MathLog10(period) + MathLog10(euclid_d / total_len));
      return MathMax(1.0, MathMin(2.0, val));
   }
   return 1.5;
}

//+------------------------------------------------------------------+
//| Check Recent Bulge Peak within lookback window                   |
//+------------------------------------------------------------------+
bool CheckRecentBulge(int shift, int window, double high_threshold)
{
   for(int k = 1; k <= window; k++)
   {
      double mi_hist = CalculateMassIndex(shift + k, InpEmaPeriod, InpSumPeriod);
      if(mi_hist >= high_threshold)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Update Monthly PnL & ASAR Circuit Breakers                       |
//+------------------------------------------------------------------+
void UpdateMonthlyGovernance()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int this_month = dt.year * 100 + dt.mon;

   if(this_month != m_current_month)
   {
      m_current_month        = this_month;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      Print("[*] New calendar month initiated: ", this_month, ". Circuit breakers reset.");
   }

   datetime month_start;
   MqlDateTime dt_start = dt;
   dt_start.day = 1; dt_start.hour = 0; dt_start.min = 0; dt_start.sec = 0;
   month_start = StructToTime(dt_start);

   HistorySelect(month_start, TimeCurrent());
   int total_deals = HistoryDealsTotal();
   double realized = 0.0;

   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            realized += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            realized += HistoryDealGetDouble(ticket, DEAL_SWAP);
            realized += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   m_monthly_realized_pnl = realized;

   if(!m_is_month_locked)
   {
      if(InpMonthlyProfitLock > 0.0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
      {
         m_is_month_locked = true;
         Print("[🛡️] ASAR Monthly Profit Lock triggered! Target: $", InpMonthlyProfitLock,
               ", Realized: $", m_monthly_realized_pnl, ". Halting further entries for month.");
      }
      if(InpHardLossBreaker > 0.0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
      {
         m_is_month_locked = true;
         Print("[⚠️] ASAR Hard Loss Circuit Breaker triggered! Limit: -$", InpHardLossBreaker,
               ", Realized: $", m_monthly_realized_pnl, ". Halting further entries for month.");
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Dynamic Lot Sizing based on ASAR Health                |
//+------------------------------------------------------------------+
double GetDynamicLotSize()
{
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      double def_lot = InpLotSize * InpDefensiveMult;
      return MathMax(0.01, NormalizeDouble(def_lot, 2));
   }
   return InpLotSize;
}

//+------------------------------------------------------------------+
//| Check open position count for this strategy                      |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) > 0)
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            count++;
         }
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   UpdateMonthlyGovernance();

   // Strict Bar Confirmation: evaluate once per closed H1 bar
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == m_last_bar_time) return;
   m_last_bar_time = bar_time;

   if(m_is_month_locked) return;

   // Check spread filter
   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(spread > InpMaxSpread) return;

   // Only manage one position at a time
   if(CountOpenPositions() > 0) return;

   // Obtain ATR(14) from closed bar (shift=1)
   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) < 1) return;
   double c_atr = atr_buf[0];
   if(c_atr < 0.50) return;

   // Obtain Trend EMA from closed bar
   double trend_ema = 0.0;
   bool trend_up = true;
   bool trend_dn = true;
   if(m_hTrendEMA != INVALID_HANDLE)
   {
      double ema_buf[];
      ArraySetAsSeries(ema_buf, true);
      if(CopyBuffer(m_hTrendEMA, 0, 1, 1, ema_buf) < 1) return;
      trend_ema = ema_buf[0];
      double close1 = iClose(_Symbol, PERIOD_H1, 1);
      trend_up = (close1 > trend_ema);
      trend_dn = (close1 < trend_ema);
   }

   // Katz Fractal Gate
   if(InpUseKfdFilter)
   {
      double kfd = CalculateKFD(1, InpKfdPeriod);
      if(kfd > InpKfdThreshold) return;
   }

   // Compute Mass Index values on shift 1, 2, and 3
   double mi_now   = CalculateMassIndex(1, InpEmaPeriod, InpSumPeriod);
   double mi_prev  = CalculateMassIndex(2, InpEmaPeriod, InpSumPeriod);
   double mi_prev2 = CalculateMassIndex(3, InpEmaPeriod, InpSumPeriod);

   bool long_signal  = false;
   bool short_signal = false;

   if(InpTriggerMode == MASS_EXPANSION_IGNITION)
   {
      // Volatility expansion crosses above threshold
      bool crossed_up = (mi_prev < InpExpansionThreshold) && (mi_now >= InpExpansionThreshold);
      if(crossed_up)
      {
         if(trend_up) long_signal  = true;
         if(trend_dn) short_signal = true;
      }
   }
   else if(InpTriggerMode == DORSEY_REVERSAL_BULGE)
   {
      // Classic Dorsey counter-trend reversal
      bool recent_peak = CheckRecentBulge(1, 12, InpBulgeHigh);
      bool bulge_drop  = recent_peak && (mi_prev >= InpBulgeLow) && (mi_now < InpBulgeLow);
      if(bulge_drop)
      {
         if(trend_dn) long_signal  = true; // Exhaustion rally
         if(trend_up) short_signal = true; // Exhaustion selloff
      }
   }
   else if(InpTriggerMode == DORSEY_CONTINUATION_BULGE)
   {
      // Commodity trend resumption
      bool recent_peak = CheckRecentBulge(1, 12, InpBulgeHigh);
      bool bulge_drop  = recent_peak && (mi_prev >= InpBulgeLow) && (mi_now < InpBulgeLow);
      if(bulge_drop)
      {
         if(trend_up) long_signal  = true;
         if(trend_dn) short_signal = true;
      }
   }
   else if(InpTriggerMode == MASS_COMPRESSION_TURN)
   {
      // Contraction inflection upward
      bool inflected = (mi_prev <= InpExpansionThreshold) && (mi_now > mi_prev) && (mi_prev <= mi_prev2);
      if(inflected)
      {
         if(trend_up) long_signal  = true;
         if(trend_dn) short_signal = true;
      }
   }

   double lot = GetDynamicLotSize();

   // Execute Order at Open of new bar
   if(long_signal)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizeDouble(ask - (InpSlMult * c_atr), _Digits);
      double tp  = NormalizeDouble(ask + (InpTpMult * c_atr), _Digits);

      if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "MI-Expansion Long"))
      {
         Print("[+] BUY Executed: Ask=", ask, " SL=", sl, " TP=", tp, " MI=", mi_now, " Lot=", lot);
      }
      else
      {
         Print("[-] BUY Execution Failed: ", m_trade.ResultRetcodeDescription());
      }
   }
   else if(short_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizeDouble(bid + (InpSlMult * c_atr), _Digits);
      double tp  = NormalizeDouble(bid - (InpTpMult * c_atr), _Digits);

      if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "MI-Expansion Short"))
      {
         Print("[+] SELL Executed: Bid=", bid, " SL=", sl, " TP=", tp, " MI=", mi_now, " Lot=", lot);
      }
      else
      {
         Print("[-] SELL Execution Failed: ", m_trade.ResultRetcodeDescription());
      }
   }
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|                 Gold_H1_Kaufman_Bands_Master_EA.mq5               |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 98: Gold H1 Kaufman Adaptive Volatility Bands         |
//|   Dynamic Efficiency Expansion Envelopes (KAVB-KFD)              |
//|     Magic: 980001 | Timeframe: H1 | Symbol: XAUUSD               |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Kaufman Adaptive Volatility Bands Master EA (Magic 980001)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 980001;               // EA Magic Number
input double                InpLotSize             = 0.10;                 // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;                 // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 250.0;                // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;                // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;                // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;                 // Defensive Lot Multiplier (0.25x)

input group "=== Kaufman Adaptive Volatility Bands Configuration ==="
input int                   InpKamaPeriod          = 10;                   // KAMA / ER Lookback Period
input int                   InpFastEmaPeriod       = 2;                    // KAMA Fast EMA Period
input int                   InpSlowEmaPeriod       = 30;                   // KAMA Slow EMA Period
input double                InpBandMult            = 1.5;                  // Base ATR Band Multiplier
input double                InpErThreshold         = 0.40;                 // Minimum Efficiency Ratio (ER >= 0.40)
input double                InpTpMult              = 3.5;                  // Take Profit ATR Multiplier (3.5R)
input double                InpSlMult              = 2.5;                  // Stop Loss ATR Multiplier (2.5R)

input group "=== Structural Trend & Anti-Chaos Filters ==="
input int                   InpAtrPeriod           = 14;                   // ATR Volatility Period
input int                   InpTrendEmaPeriod      = 200;                  // Macro Structural Trend EMA
input bool                  InpUseKfdFilter        = true;                 // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.45;                 // Maximum Fractal Dimension (<= 1.45)
input int                   InpKfdPeriod           = 24;                   // Katz Fractal Window (Hours)

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

   m_hTrendEMA = iMA(_Symbol, PERIOD_H1, InpTrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(m_hTrendEMA == INVALID_HANDLE)
   {
      Print("[!] Error initializing Trend EMA handle.");
      return(INIT_FAILED);
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   PrintFormat("[+] Strategy 98 Initialized: KAMA(%d), BandMult=%.2f, ER_Thresh=%.2f, TP=%.1fR, SL=%.1fR, Magic=%d",
               InpKamaPeriod, InpBandMult, InpErThreshold, InpTpMult, InpSlMult, InpMagicNumber);
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
//| Katz Fractal Dimension Calculation                               |
//+------------------------------------------------------------------+
double CalculateKFD(int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, period + 1, rates);
   if(copied < period) return 1.5;

   double c_first = rates[period - 1].close;
   double c_last  = rates[0].close;
   double euclid_d = MathAbs(c_last - c_first);

   double total_len = 0.0;
   for(int i = 0; i < period - 1; i++)
   {
      total_len += MathAbs(rates[i].close - rates[i + 1].close);
   }

   if(total_len <= 1e-6 || euclid_d <= 1e-6) return 1.5;

   double val = MathLog10((double)period) / (MathLog10((double)period) + MathLog10(euclid_d / total_len));
   if(val < 1.0) val = 1.0;
   if(val > 2.0) val = 2.0;
   return val;
}

//+------------------------------------------------------------------+
//| Kaufman Adaptive Moving Average & Efficiency Ratio               |
//+------------------------------------------------------------------+
bool CalculateKamaAndER(int period, int shift, double &out_kama, double &out_er)
{
   int req_bars = period * 3 + 10;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, shift, req_bars, rates);
   if(copied < req_bars) return false;

   // Reverse array order for chronological KAMA calculation
   ArraySetAsSeries(rates, false);

   double fastest = 2.0 / (InpFastEmaPeriod + 1.0);
   double slowest = 2.0 / (InpSlowEmaPeriod + 1.0);
   double kama = rates[0].close;

   for(int i = period; i < req_bars; i++)
   {
      double change = MathAbs(rates[i].close - rates[i - period].close);
      double vol = 0.0;
      for(int j = 0; j < period; j++)
      {
         vol += MathAbs(rates[i - j].close - rates[i - j - 1].close);
      }
      double er = (vol > 1e-6) ? (change / vol) : 0.0;
      double sc = er * (fastest - slowest) + slowest;
      sc = sc * sc;
      kama = kama + sc * (rates[i].close - kama);

      if(i == req_bars - 1)
      {
         out_kama = kama;
         out_er = er;
      }
   }
   return true;
}

//+------------------------------------------------------------------+
//| ASAR Monthly PnL Auditor                                         |
//+------------------------------------------------------------------+
void UpdateMonthlyPnL()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int month_key = dt.year * 100 + dt.mon;

   if(month_key != m_current_month)
   {
      m_current_month = month_key;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked = false;
      PrintFormat("[*] S98: New Calendar Month %d. ASAR Risk Engine Reset.", month_key);
   }

   datetime start_of_month = D'2020.01.01';
   MqlDateTime m_start = dt;
   m_start.day = 1;
   m_start.hour = 0;
   m_start.min = 0;
   m_start.sec = 0;
   start_of_month = StructToTime(m_start);

   if(!HistorySelect(start_of_month, TimeCurrent())) return;

   double net_pnl = 0.0;
   int total_deals = HistoryDealsTotal();
   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            net_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            net_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            net_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }

   m_monthly_realized_pnl = net_pnl;

   if(InpMonthlyProfitLock > 0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      if(!m_is_month_locked)
      {
         m_is_month_locked = true;
         PrintFormat("[LOCK] S98 Monthly Profit Lock Active: Net PnL = $%.2f >= $%.2f",
                     m_monthly_realized_pnl, InpMonthlyProfitLock);
      }
   }

   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
      {
         m_is_month_locked = true;
         PrintFormat("[BREAKER] S98 Circuit Breaker Tripped: Net PnL = $%.2f <= -$%.2f",
                     m_monthly_realized_pnl, InpHardLossBreaker);
      }
   }
}

//+------------------------------------------------------------------+
//| Check Position Status                                            |
//+------------------------------------------------------------------+
bool HasOpenPosition(int &pos_type, ulong &pos_ticket)
{
   pos_type = 0;
   pos_ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            pos_ticket = ticket;
            pos_type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
            return true;
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == m_last_bar_time) return; // New H1 bar only

   UpdateMonthlyPnL();

   int pos_type = 0;
   ulong pos_ticket = 0;
   bool in_position = HasOpenPosition(pos_type, pos_ticket);

   m_last_bar_time = current_bar_time;

   if(in_position || m_is_month_locked) return;

   // Check Spread
   double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   if(spread > InpMaxSpread) return;

   // Copy ATR
   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0) return;
   double c_atr = atr_buf[0];
   if(c_atr < 0.5) return;

   // Macro Structural Trend EMA200
   double ema_buf[];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(m_hTrendEMA, 0, 1, 1, ema_buf) <= 0) return;
   double close1 = iClose(_Symbol, PERIOD_H1, 1);
   bool trend_up = (close1 > ema_buf[0]);
   bool trend_dn = (close1 < ema_buf[0]);

   // Katz Fractal Dimension Gate
   if(InpUseKfdFilter)
   {
      double kfd = CalculateKFD(InpKfdPeriod);
      if(kfd > InpKfdThreshold) return; // Planar chaos filter active
   }

   // Calculate KAMA & Efficiency Ratio (ER)
   double kama1 = 0.0, er1 = 0.0;
   if(!CalculateKamaAndER(InpKamaPeriod, 1, kama1, er1)) return;

   if(er1 < InpErThreshold) return; // Efficiency gate: ignore low-efficiency consolidation

   // Dynamic Kaufman Adaptive Band Width
   double band_width = InpBandMult * c_atr * (1.0 + (1.0 - er1));
   double upper_band = kama1 + band_width;
   double lower_band = kama1 - band_width;

   bool buy_signal  = (close1 > upper_band) && trend_up;
   bool sell_signal = (close1 < lower_band) && trend_dn;

   // Defensive Sizing
   double lots = InpLotSize;
   if(InpDefensiveThresh > 0 && m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      lots = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(lots < 0.01) lots = 0.01;
   }

   // Execute Entry
   if(buy_signal)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - (InpSlMult * c_atr), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * c_atr), _Digits);
      m_trade.Buy(lots, _Symbol, ask, sl, tp, "S98 KAVB BUY");
      PrintFormat("[ENTRY] S98 BUY: %.2f lots @ %.2f | SL: %.2f | TP: %.2f | UpperBand: %.2f | ER: %.2f",
                  lots, ask, sl, tp, upper_band, er1);
   }
   else if(sell_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + (InpSlMult * c_atr), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * c_atr), _Digits);
      m_trade.Sell(lots, _Symbol, bid, sl, tp, "S98 KAVB SELL");
      PrintFormat("[ENTRY] S98 SELL: %.2f lots @ %.2f | SL: %.2f | TP: %.2f | LowerBand: %.2f | ER: %.2f",
                  lots, bid, sl, tp, lower_band, er1);
   }
}
//+------------------------------------------------------------------+

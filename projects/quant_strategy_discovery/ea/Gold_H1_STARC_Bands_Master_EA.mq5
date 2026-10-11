//+------------------------------------------------------------------+
//|                  Gold_H1_STARC_Bands_Master_EA.mq5               |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|   Strategy 99: Gold H1 Manning Stoller STARCBands                |
//|   Linear Volatility Channel Expansion (STARC-ATR-KFD)            |
//|     Magic: 990001 | Timeframe: H1 | Symbol: XAUUSD               |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Manning Stoller STARCBands Master EA (Magic 990001)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong                 InpMagicNumber         = 990001;               // EA Magic Number
input double                InpLotSize             = 0.10;                 // Standard Lot Size (0.10 lots = 10 oz Gold)
input double                InpMaxSpread           = 0.60;                 // Maximum Allowable Spread ($)
input double                InpMonthlyProfitLock   = 200.0;                // Monthly Profit Lock Target ($)
input double                InpHardLossBreaker     = 250.0;                // Monthly Hard Loss Circuit Breaker ($)
input double                InpDefensiveThresh     = 120.0;                // Monthly Loss for Defensive Sizing ($)
input double                InpDefensiveMult       = 0.25;                 // Defensive Lot Multiplier (0.25x)

input group "=== Manning Stoller STARCBands Configuration ==="
input int                   InpSmaPeriod           = 14;                   // Centerline SMA Period (Default: 14)
input int                   InpAtrPeriod           = 14;                   // Volatility ATR Period (Default: 14)
input double                InpBandMultiplier      = 1.5;                  // Channel ATR Multiplier (1.5x)
input double                InpTpMult              = 5.5;                  // Take Profit ATR Multiplier (5.5R)
input double                InpSlMult              = 2.0;                  // Stop Loss ATR Multiplier (2.0R)

input group "=== Structural Trend & Anti-Chaos Filters ==="
input int                   InpTrendEmaPeriod      = 50;                   // Intermediate Trend EMA Period (50)
input bool                  InpUseKfdFilter        = true;                 // Enable Katz Fractal Gate
input double                InpKfdThreshold        = 1.40;                 // Maximum Fractal Dimension (<= 1.40)
input int                   InpKfdPeriod           = 24;                   // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hSMA;
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

   m_hSMA = iMA(_Symbol, PERIOD_H1, InpSmaPeriod, 0, MODE_SMA, PRICE_CLOSE);
   if(m_hSMA == INVALID_HANDLE)
   {
      Print("[!] Error initializing SMA handle.");
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

   PrintFormat("[+] Strategy 99 Initialized: SMA(%d), ATR(%d), Mult=%.2f, TP=%.1fR, SL=%.1fR, Magic=%d",
               InpSmaPeriod, InpAtrPeriod, InpBandMultiplier, InpTpMult, InpSlMult, InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_hATR != INVALID_HANDLE) IndicatorRelease(m_hATR);
   if(m_hSMA != INVALID_HANDLE) IndicatorRelease(m_hSMA);
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
      PrintFormat("[*] S99: New Calendar Month %d. ASAR Risk Engine Reset.", month_key);
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
         PrintFormat("[LOCK] S99 Monthly Profit Lock Active: Net PnL = $%.2f >= $%.2f",
                     m_monthly_realized_pnl, InpMonthlyProfitLock);
      }
   }

   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      if(!m_is_month_locked)
      {
         m_is_month_locked = true;
         PrintFormat("[BREAKER] S99 Circuit Breaker Tripped: Net PnL = $%.2f <= -$%.2f",
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
   if(current_bar_time == m_last_bar_time) return; // New H1 bar open only

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
   if(CopyBuffer(m_hATR, 0, 1, 2, atr_buf) < 2) return;
   double c_atr1 = atr_buf[0];
   double c_atr2 = atr_buf[1];
   if(c_atr1 < 0.5) return;

   // Copy SMA
   double sma_buf[];
   ArraySetAsSeries(sma_buf, true);
   if(CopyBuffer(m_hSMA, 0, 1, 2, sma_buf) < 2) return;
   double sma1 = sma_buf[0];
   double sma2 = sma_buf[1];

   // Copy Trend EMA50
   double ema_buf[];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(m_hTrendEMA, 0, 1, 1, ema_buf) < 1) return;
   double ema50 = ema_buf[0];

   double close1 = iClose(_Symbol, PERIOD_H1, 1);
   double close2 = iClose(_Symbol, PERIOD_H1, 2);

   bool trend_up = (close1 > ema50);
   bool trend_dn = (close1 < ema50);

   // Katz Fractal Dimension Gate
   if(InpUseKfdFilter)
   {
      double kfd = CalculateKFD(InpKfdPeriod);
      if(kfd > InpKfdThreshold) return; // Planar noise gate
   }

   // Compute STARC Bands
   double upper_band1 = sma1 + (InpBandMultiplier * c_atr1);
   double lower_band1 = sma1 - (InpBandMultiplier * c_atr1);
   double upper_band2 = sma2 + (InpBandMultiplier * c_atr2);
   double lower_band2 = sma2 - (InpBandMultiplier * c_atr2);

   // STARC Breakout Trigger
   bool buy_signal  = (close2 <= upper_band2) && (close1 > upper_band1) && trend_up;
   bool sell_signal = (close2 >= lower_band2) && (close1 < lower_band1) && trend_dn;

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
      double sl = NormalizeDouble(ask - (InpSlMult * c_atr1), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * c_atr1), _Digits);
      m_trade.Buy(lots, _Symbol, ask, sl, tp, "S99 STARC BUY");
      PrintFormat("[ENTRY] S99 BUY: %.2f lots @ %.2f | SL: %.2f | TP: %.2f | STARC Upper: %.2f",
                  lots, ask, sl, tp, upper_band1);
   }
   else if(sell_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + (InpSlMult * c_atr1), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * c_atr1), _Digits);
      m_trade.Sell(lots, _Symbol, bid, sl, tp, "S99 STARC SELL");
      PrintFormat("[ENTRY] S99 SELL: %.2f lots @ %.2f | SL: %.2f | TP: %.2f | STARC Lower: %.2f",
                  lots, bid, sl, tp, lower_band1);
   }
}
//+------------------------------------------------------------------+

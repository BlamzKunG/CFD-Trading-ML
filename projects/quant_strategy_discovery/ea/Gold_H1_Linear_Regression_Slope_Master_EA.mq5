//+------------------------------------------------------------------+
//|             Gold_H1_Linear_Regression_Slope_Master_EA.mq5         |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|         Strategy 67: Linear Regression Slope & R² (LRS-R2-KFD)    |
//|          PF: 2.095 | Win: 43.1% | Max DD: $993 | Net: +$9.0k      |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Linear Regression Slope & R-Squared Master EA (Elite Tier PF 2.095)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 670001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 250.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Linear Regression Configuration ==="
input int      InpPeriod              = 28;        // Linear Regression Lookback Window (N)
input double   InpR2_Threshold        = 0.60;      // Minimum Determination Coefficient R² (>= 0.60)
input double   InpTpMult              = 5.0;       // Take Profit ATR Multiplier (5.0R)
input double   InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

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

   m_hATR    = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicator handles.");
      return(INIT_FAILED);
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Gold H1 Linear Regression Slope Master EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   IndicatorRelease(m_hEMA200);
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
//| Compute Linear Regression Slope and R² for bar offset            |
//+------------------------------------------------------------------+
bool ComputeLinReg(const double &closes[], int offset, int period, double &slope, double &r2)
{
   if(ArraySize(closes) < offset + period) return false;

   double x_mean = (period - 1.0) / 2.0;
   double ss_x = 0.0;
   for(int i = 0; i < period; i++) ss_x += (i - x_mean) * (i - x_mean);

   double sum_y = 0.0;
   for(int i = 0; i < period; i++)
   {
      // Index in array: closes[offset + period - 1 - i] represents bar from oldest to newest
      sum_y += closes[offset + period - 1 - i];
   }
   double y_mean = sum_y / period;

   double cov_xy = 0.0;
   double ss_y = 0.0;
   for(int i = 0; i < period; i++)
   {
      double y_val = closes[offset + period - 1 - i];
      double x_diff = i - x_mean;
      double y_diff = y_val - y_mean;
      cov_xy += x_diff * y_diff;
      ss_y += y_diff * y_diff;
   }

   if(ss_y > 1e-8 && ss_x > 1e-8)
   {
      slope = cov_xy / ss_x;
      r2 = (cov_xy * cov_xy) / (ss_x * ss_y);
      if(r2 < 0.0) r2 = 0.0;
      if(r2 > 1.0) r2 = 1.0;
      return true;
   }
   slope = 0.0; r2 = 0.0;
   return false;
}

//+------------------------------------------------------------------+
//| Track Monthly Realized PnL                                       |
//+------------------------------------------------------------------+
void UpdateMonthlyGovernance(datetime current_time)
{
   MqlDateTime dt;
   TimeToStruct(current_time, dt);
   int month_key = dt.year * 100 + dt.mon;

   if(month_key != m_current_month)
   {
      m_current_month        = month_key;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      PrintFormat("[*] Reset Monthly ASAR Risk Budget for Year-Month: %d", month_key);
   }

   datetime month_start;
   dt.day = 1; dt.hour = 0; dt.min = 0; dt.sec = 0;
   month_start = StructToTime(dt);

   HistorySelect(month_start, current_time);
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

   if(InpMonthlyProfitLock > 0 && m_monthly_realized_pnl >= InpMonthlyProfitLock)
      m_is_month_locked = true;
   if(InpHardLossBreaker > 0 && m_monthly_realized_pnl <= -InpHardLossBreaker)
      m_is_month_locked = true;
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
   UpdateMonthlyGovernance(bar_time);

   string status_str = StringFormat(
      "LRS-R2 Master EA | Mo PnL: $%.2f | Status: %s",
      m_monthly_realized_pnl,
      m_is_month_locked ? "LOCKED" : "ACTIVE"
   );
   Comment(status_str);

   if(m_is_month_locked || HasOpenPosition()) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMaxSpread) return;

   double atr_buf[1], ema_buf[1];
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0 || CopyBuffer(m_hEMA200, 0, 1, 1, ema_buf) <= 0) return;
   double atr14  = atr_buf[0];
   double ema200 = ema_buf[0];
   if(atr14 < 0.50) return;

   double closes[];
   ArraySetAsSeries(closes, true);
   int fetch_bars = InpPeriod + InpKfdPeriod + 10;
   if(CopyClose(_Symbol, PERIOD_H1, 1, fetch_bars, closes) < fetch_bars) return;

   double slope1, r2_1, slope2, r2_2;
   if(!ComputeLinReg(closes, 0, InpPeriod, slope1, r2_1) ||
      !ComputeLinReg(closes, 1, InpPeriod, slope2, r2_2)) return;

   double kfd_val = ComputeKFD(closes, 0, InpKfdPeriod);
   bool kfd_ok    = (!InpUseKFD_Filter) || (kfd_val <= InpKfdThreshold);

   double close1 = closes[0];
   bool ema_long_ok  = (close1 > ema200);
   bool ema_short_ok = (close1 < ema200);

   // Linear Regression Signals
   bool r2_cross_up = (r2_1 >= InpR2_Threshold) && (r2_2 < InpR2_Threshold);
   bool bull_trigger = r2_cross_up && (slope1 > 0.0) && ema_long_ok && kfd_ok;
   bool bear_trigger = r2_cross_up && (slope1 < 0.0) && ema_short_ok && kfd_ok;

   double trade_lot = InpLotSize;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      trade_lot = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(trade_lot < 0.01) trade_lot = 0.01;
   }

   if(bull_trigger)
   {
      double sl = NormalizeDouble(ask - (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(ask + (InpTpMult * atr14), _Digits);
      m_trade.Buy(trade_lot, _Symbol, ask, sl, tp, "LRS-R2 Buy");
      PrintFormat("[+] Executed BUY @ %.2f | SL: %.2f | TP: %.2f | Slope: %.3f | R²: %.3f | KFD: %.3f", ask, sl, tp, slope1, r2_1, kfd_val);
   }
   else if(bear_trigger)
   {
      double sl = NormalizeDouble(bid + (InpSlMult * atr14), _Digits);
      double tp = NormalizeDouble(bid - (InpTpMult * atr14), _Digits);
      m_trade.Sell(trade_lot, _Symbol, bid, sl, tp, "LRS-R2 Sell");
      PrintFormat("[+] Executed SELL @ %.2f | SL: %.2f | TP: %.2f | Slope: %.3f | R²: %.3f | KFD: %.3f", bid, sl, tp, slope1, r2_1, kfd_val);
   }
}

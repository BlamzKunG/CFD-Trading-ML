//+------------------------------------------------------------------+
//|              Gold_H1_Quantum_Titan_Clean_Quant_Master_EA.mq5     |
//|               CFD Quantitative Strategy Discovery - Strategy 136 |
//|          Quantum Titan Clean Reverse-Engineered Master EA        |
//|                (Zero Martingale / Zero Recovery Grid)            |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Core B: H1 Swing Pivot Pullback ==="
input int    InpLookbackPeriod    = 30;     // Swing Pivot Lookback Window (Bars)
input double InpPullbackATR       = 0.5;    // Pullback Distance from Pivot (ATR Multiplier)
input int    InpATRPeriod         = 14;     // ATR Lookback Window
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input int    InpKFDPeriod         = 24;     // Katz Fractal Dimension Window
input double InpKFDThreshold      = 1.42;   // Maximum Permitted KFD (Trend Efficiency Gate)

input group "=== Institutional Risk & Targets (Zero-Martingale) ==="
input double InpTakeProfitMult    = 3.5;    // Take Profit (ATR Multiplier)
input double InpStopLossMult      = 2.5;    // Stop Loss (ATR Multiplier)
input double InpLotSize           = 0.10;   // Fixed Fractional Lot Size
input ulong  InpMagicNumber       = 136001; // EA Magic Number

input group "=== ASAR Calendar Risk Governance ==="
input double InpMonthlyProfitLock = 200.0;  // Monthly Profit Lock Target ($ USD)
input double InpMonthlyLossBreak  = 250.0;  // Monthly Loss Circuit Breaker ($ USD)

// Global variables
CTrade   trade;
int      handle_atr;
int      handle_ema200;
datetime last_bar_time;
int      current_month;
double   monthly_pnl;
bool     month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);

   handle_atr = iATR(_Symbol, PERIOD_H1, InpATRPeriod);
   handle_ema200 = iMA(_Symbol, PERIOD_H1, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE)
   {
      Print("[-] Error initializing indicators for Quantum Titan Clean Quant EA.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   current_month = -1;
   monthly_pnl = 0.0;
   month_locked = false;

   Print("[+] Gold H1 Quantum Titan Clean Quant Master EA (Strategy 136) initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_ema200);
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension (KFD)                           |
//+------------------------------------------------------------------+
double CalculateKFD(int shift)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, shift, InpKFDPeriod + 1, closes) <= InpKFDPeriod)
      return 1.5;

   double length = 0.0;
   double max_dist = 0.0;
   double p0 = closes[InpKFDPeriod];

   for(int i = InpKFDPeriod - 1; i >= 0; i--)
   {
      length += MathAbs(closes[i] - closes[i + 1]);
      double dist = MathAbs(closes[i] - p0);
      if(dist > max_dist) max_dist = dist;
   }

   if(length <= 0.0 || max_dist <= 0.0) return 1.5;
   double k = MathLog10((double)InpKFDPeriod) / (MathLog10((double)InpKFDPeriod) + MathLog10(max_dist / length));
   return MathMax(1.0, MathMin(2.0, k));
}

//+------------------------------------------------------------------+
//| Check if open position exists for this magic number              |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         ulong magic = PositionGetInteger(POSITION_MAGIC);
         if(magic == InpMagicNumber)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Update Monthly PnL and Check Circuit Breakers                    |
//+------------------------------------------------------------------+
void CheckMonthlyRiskCircuitBreaker()
{
   MqlDateTime dt;
   TimeCurrent(dt);

   if(dt.mon != current_month)
   {
      current_month = dt.mon;
      monthly_pnl = 0.0;
      month_locked = false;
      PrintFormat("[ASAR] New calendar month detected: %d. Resetting monthly PnL lock.", current_month);
   }

   // Aggregate closed trades PnL for current month
   datetime start_of_month;
   MqlDateTime start_dt = dt;
   start_dt.day = 1;
   start_dt.hour = 0;
   start_dt.min = 0;
   start_dt.sec = 0;
   start_of_month = StructToTime(start_dt);

   HistorySelect(start_of_month, TimeCurrent());
   double pnl_acc = 0.0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol &&
         HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber &&
         (HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT ||
          HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_INOUT))
      {
         pnl_acc += HistoryDealGetDouble(ticket, DEAL_PROFIT);
         pnl_acc += HistoryDealGetDouble(ticket, DEAL_SWAP);
         pnl_acc += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      }
   }

   monthly_pnl = pnl_acc;

   if(monthly_pnl >= InpMonthlyProfitLock)
   {
      if(!month_locked)
         PrintFormat("[ASAR] Monthly profit lock triggered! Current PnL: $%.2f >= Lock Target: $%.2f. Ceasing trades for month.",
                     monthly_pnl, InpMonthlyProfitLock);
      month_locked = true;
   }
   else if(monthly_pnl <= -InpMonthlyLossBreak)
   {
      if(!month_locked)
         PrintFormat("[ASAR] Monthly loss breaker triggered! Current PnL: $%.2f <= Loss Breaker: -$%.2f. Ceasing trades for month.",
                     monthly_pnl, InpMonthlyLossBreak);
      month_locked = true;
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Bar completion check (Operates strictly on completed H1 bar to prevent lookahead)
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == last_bar_time)
      return;

   last_bar_time = bar_time;

   CheckMonthlyRiskCircuitBreaker();

   if(month_locked)
      return;

   if(HasOpenPosition())
      return;

   // Get indicator buffers on confirmed bar 1
   double atr_val[1];
   double ema200_val[1];
   if(CopyBuffer(handle_atr, 0, 1, 1, atr_val) <= 0 ||
      CopyBuffer(handle_ema200, 0, 1, 1, ema200_val) <= 0)
      return;

   double c_atr = atr_val[0];
   double c_ema200 = ema200_val[0];
   if(c_atr <= 0.0) return;

   // Katz Fractal Dimension on bar 1
   double kfd = CalculateKFD(1);
   if(kfd > InpKFDThreshold)
      return; // Market is too turbulent / noisy

   // Copy bar 1 and bar 2 closes for confirmed pullback triggers
   double closes[2];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, 2, closes) < 2)
      return;

   double close_1 = closes[0]; // Bar 1
   double close_2 = closes[1]; // Bar 2

   // Calculate Swing Pivot High and Low over InpLookbackPeriod excluding bar 1
   // (i.e. from bar 2 to bar InpLookbackPeriod + 1)
   double highs[];
   double lows[];
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows, true);
   if(CopyHigh(_Symbol, PERIOD_H1, 2, InpLookbackPeriod, highs) < InpLookbackPeriod ||
      CopyLow(_Symbol, PERIOD_H1, 2, InpLookbackPeriod, lows) < InpLookbackPeriod)
      return;

   int highest_idx = ArrayMaximum(highs, 0, InpLookbackPeriod);
   int lowest_idx = ArrayMinimum(lows, 0, InpLookbackPeriod);

   double p_high = highs[highest_idx];
   double p_low = lows[lowest_idx];

   // Trend directions
   bool trend_bull = (close_1 > c_ema200);
   bool trend_bear = (close_1 < c_ema200);

   // Core B Pullback Trigger Logic
   double long_pullback_level = p_high - (InpPullbackATR * c_atr);
   double short_pullback_level = p_low + (InpPullbackATR * c_atr);

   bool buy_pullback = (close_1 <= long_pullback_level) && (close_2 > long_pullback_level);
   bool sell_pullback = (close_1 >= short_pullback_level) && (close_2 < short_pullback_level);

   bool buy_signal = buy_pullback && trend_bull;
   bool sell_signal = sell_pullback && trend_bear;

   // Execution with strict single-order SL and TP (NO Martingale, NO Recovery Grid)
   if(buy_signal)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - (InpStopLossMult * c_atr), _Digits);
      double tp = NormalizeDouble(ask + (InpTakeProfitMult * c_atr), _Digits);

      if(trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "QT-Clean-CoreB-Buy"))
      {
         PrintFormat("[+] BUY ORDER EXECUTED | Symbol: %s | Price: %.2f | SL: %.2f | TP: %.2f | KFD: %.3f",
                     _Symbol, ask, sl, tp, kfd);
      }
      else
      {
         PrintFormat("[-] BUY ORDER FAILED | Error: %d", GetLastError());
      }
   }
   else if(sell_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + (InpStopLossMult * c_atr), _Digits);
      double tp = NormalizeDouble(bid - (InpTakeProfitMult * c_atr), _Digits);

      if(trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "QT-Clean-CoreB-Sell"))
      {
         PrintFormat("[+] SELL ORDER EXECUTED | Symbol: %s | Price: %.2f | SL: %.2f | TP: %.2f | KFD: %.3f",
                     _Symbol, bid, sl, tp, kfd);
      }
      else
      {
         PrintFormat("[-] SELL ORDER FAILED | Error: %d", GetLastError());
      }
   }
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|              Gold_H1_Ghost_Scalper_Clean_Quant_Master_EA.mq5     |
//|               CFD Quantitative Strategy Discovery - Strategy 137 |
//|          Ghost Scalper Clean Multi-Lane Reverse-Engineered EA    |
//|                (Zero Martingale / Zero Recovery Grid)            |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Strategy Core: Multi-Lane Configuration ==="
input bool   InpEnableLaneA       = true;   // Enable Ghost Lane A (Medium Swing: Left 10 / Right 7)
input bool   InpEnableLaneB       = true;   // Enable Ghost Lane B (Fast Swing + Session: Left 13 / Right 3)
input bool   InpEnableLaneC       = true;   // Enable Ghost Lane C (Micro Swing: Left 7 / Right 5)
input bool   InpEnableLaneD       = true;   // Enable Ghost Lane D (Macro Swing: Left 26 / Right 20)

input group "=== Quantitative Filters & Noise Gating ==="
input bool   InpUseTrendFilter    = true;   // Enable 200 EMA Secular Trend Filter
input int    InpEMA200Period      = 200;    // Secular Trend EMA Period
input bool   InpUseKFDNoiseGate   = true;   // Enable Katz Fractal Dimension Noise Gate
input int    InpKFDPeriod         = 24;     // Katz Fractal Lookback Window
input double InpKFDThreshold      = 1.42;   // Maximum Katz Fractal Dimension (Efficiency Threshold)

input group "=== Institutional Risk & Targets (Zero-Martingale) ==="
input double InpLotSize           = 0.10;   // Institutional Lot Size per Lane
input ulong  InpBaseMagic         = 137000; // Base Magic Number (Lane A: 137001, B: 137002, etc.)

input group "=== ASAR Calendar Risk Governance ==="
input bool   InpUseASARGovernance = false;  // Enable ASAR Monthly Profit/Loss Circuit Breakers
input double InpMonthlyProfitLock = 2000.0; // Monthly Profit Lock Target ($ USD)
input double InpMonthlyLossBreak  = 2500.0; // Monthly Loss Circuit Breaker ($ USD)

// Struct to store lane definitions
struct LaneConfig
{
   bool   enabled;
   int    magic;
   string name;
   int    left_buy;
   int    right_buy;
   double offset_buy_pts;
   int    left_sell;
   int    right_sell;
   double offset_sell_pts;
   double sl_pts;
   double tp_pts;
   bool   use_session;
   int    start_sec;
   int    end_sec;
   double trail_act_pts;
   double trail_dist_pts;
   double trail_step_pts;
};

// Global variables
CTrade     trade;
LaneConfig lanes[4];
int        handle_ema200;
datetime   last_bar_time;
int        current_month;
double     monthly_pnl;
bool       month_locked;

//+------------------------------------------------------------------+
//| Initialize Lane Configurations                                   |
//+------------------------------------------------------------------+
void InitLanes()
{
   // Lane A: Medium Swing
   lanes[0].enabled         = InpEnableLaneA;
   lanes[0].magic           = (int)InpBaseMagic + 1;
   lanes[0].name            = "Ghost_A";
   lanes[0].left_buy        = 10;
   lanes[0].right_buy       = 7;
   lanes[0].offset_buy_pts  = -1.80; // $1.80 below swing high
   lanes[0].left_sell       = 10;
   lanes[0].right_sell      = 7;
   lanes[0].offset_sell_pts = 1.80;  // $1.80 above swing low
   lanes[0].sl_pts          = 5.00;  // $5.00 Stop Loss
   lanes[0].tp_pts          = 15.00; // $15.00 Take Profit (1:3 R:R)
   lanes[0].use_session     = false;
   lanes[0].start_sec       = 0;
   lanes[0].end_sec         = 86400;
   lanes[0].trail_act_pts   = 0.0;
   lanes[0].trail_dist_pts  = 0.90;
   lanes[0].trail_step_pts  = 0.30;

   // Lane B: Fast Swing + Session
   lanes[1].enabled         = InpEnableLaneB;
   lanes[1].magic           = (int)InpBaseMagic + 2;
   lanes[1].name            = "Ghost_B";
   lanes[1].left_buy        = 13;
   lanes[1].right_buy       = 3;
   lanes[1].offset_buy_pts  = -1.50; // $1.50 below swing high
   lanes[1].left_sell       = 10;
   lanes[1].right_sell      = 4;
   lanes[1].offset_sell_pts = 1.90;  // $1.90 above swing low
   lanes[1].sl_pts          = 5.00;  // $5.00 Stop Loss
   lanes[1].tp_pts          = 25.00; // $25.00 Take Profit (1:5 R:R)
   lanes[1].use_session     = true;
   lanes[1].start_sec       = 4500;  // 01:15 broker time
   lanes[1].end_sec         = 80100; // 22:15 broker time
   lanes[1].trail_act_pts   = 0.15;
   lanes[1].trail_dist_pts  = 1.15;
   lanes[1].trail_step_pts  = 0.40;

   // Lane C: Micro Swing
   lanes[2].enabled         = InpEnableLaneC;
   lanes[2].magic           = (int)InpBaseMagic + 3;
   lanes[2].name            = "Ghost_C";
   lanes[2].left_buy        = 7;
   lanes[2].right_buy       = 5;
   lanes[2].offset_buy_pts  = -2.20; // $2.20 below swing high
   lanes[2].left_sell       = 7;
   lanes[2].right_sell      = 5;
   lanes[2].offset_sell_pts = 2.20;  // $2.20 above swing low
   lanes[2].sl_pts          = 10.00; // $10.00 Stop Loss
   lanes[2].tp_pts          = 25.00; // $25.00 Take Profit (1:2.5 R:R)
   lanes[2].use_session     = false;
   lanes[2].start_sec       = 0;
   lanes[2].end_sec         = 86400;
   lanes[2].trail_act_pts   = 0.15;
   lanes[2].trail_dist_pts  = 0.90;
   lanes[2].trail_step_pts  = 0.20;

   // Lane D: Macro Swing
   lanes[3].enabled         = InpEnableLaneD;
   lanes[3].magic           = (int)InpBaseMagic + 4;
   lanes[3].name            = "Ghost_D";
   lanes[3].left_buy        = 26;
   lanes[3].right_buy       = 20;
   lanes[3].offset_buy_pts  = -1.80; // $1.80 below swing high
   lanes[3].left_sell       = 26;
   lanes[3].right_sell      = 20;
   lanes[3].offset_sell_pts = 1.80;  // $1.80 above swing low
   lanes[3].sl_pts          = 8.00;  // $8.00 Stop Loss
   lanes[3].tp_pts          = 17.00; // $17.00 Take Profit (1:2.125 R:R)
   lanes[3].use_session     = false;
   lanes[3].start_sec       = 0;
   lanes[3].end_sec         = 86400;
   lanes[3].trail_act_pts   = 1.00;
   lanes[3].trail_dist_pts  = 0.35;
   lanes[3].trail_step_pts  = 0.55;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);

   handle_ema200 = iMA(_Symbol, PERIOD_H1, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);
   if(handle_ema200 == INVALID_HANDLE)
   {
      Print("[-] Error initializing EMA200 indicator.");
      return INIT_FAILED;
   }

   InitLanes();

   last_bar_time = 0;
   current_month = -1;
   monthly_pnl = 0.0;
   month_locked = false;

   Print("[+] Gold H1 Ghost Scalper Clean Quant Master EA (Strategy 137) initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
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
//| Check if open position exists for a specific magic number        |
//+------------------------------------------------------------------+
bool HasOpenPosition(int magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == magic)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Manage Trailing Stop for Open Positions                          |
//+------------------------------------------------------------------+
void ManageTrailingStops()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      long magic = PositionGetInteger(POSITION_MAGIC);

      for(int lane_idx = 0; lane_idx < 4; lane_idx++)
      {
         if(magic == lanes[lane_idx].magic)
         {
            ulong ticket = PositionGetTicket(i);
            ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
            double cur_sl = PositionGetDouble(POSITION_SL);
            double cur_tp = PositionGetDouble(POSITION_TP);

            double act_pts  = lanes[lane_idx].trail_act_pts;
            double dist_pts = lanes[lane_idx].trail_dist_pts;
            double step_pts = lanes[lane_idx].trail_step_pts;

            if(type == POSITION_TYPE_BUY)
            {
               double pnl_pts = tick.bid - open_price;
               if(pnl_pts >= act_pts)
               {
                  double cand_sl = NormalizeDouble(tick.bid - dist_pts, _Digits);
                  if(cand_sl > cur_sl + step_pts)
                  {
                     trade.PositionModify(ticket, cand_sl, cur_tp);
                  }
               }
            }
            else if(type == POSITION_TYPE_SELL)
            {
               double pnl_pts = open_price - tick.ask;
               if(pnl_pts >= act_pts)
               {
                  double cand_sl = NormalizeDouble(tick.ask + dist_pts, _Digits);
                  if(cur_sl == 0.0 || cand_sl < cur_sl - step_pts)
                  {
                     trade.PositionModify(ticket, cand_sl, cur_tp);
                  }
               }
            }
            break;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check ASAR Monthly Circuit Breaker                               |
//+------------------------------------------------------------------+
void CheckMonthlyRiskCircuitBreaker()
{
   if(!InpUseASARGovernance) return;

   MqlDateTime dt;
   TimeCurrent(dt);

   if(dt.mon != current_month)
   {
      current_month = dt.mon;
      monthly_pnl = 0.0;
      month_locked = false;
   }

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
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol &&
         magic >= InpBaseMagic && magic <= InpBaseMagic + 4 &&
         (HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT ||
          HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_INOUT))
      {
         pnl_acc += HistoryDealGetDouble(ticket, DEAL_PROFIT);
         pnl_acc += HistoryDealGetDouble(ticket, DEAL_SWAP);
         pnl_acc += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      }
   }

   monthly_pnl = pnl_acc;

   if(monthly_pnl >= InpMonthlyProfitLock || monthly_pnl <= -InpMonthlyLossBreak)
      month_locked = true;
}

//+------------------------------------------------------------------+
//| Evaluate Swing on Bar Shift                                      |
//+------------------------------------------------------------------+
bool IsSwingHigh(int shift, int left_bars, int right_bars)
{
   double highs[];
   ArraySetAsSeries(highs, true);
   int total_needed = shift + left_bars + 1;
   if(CopyHigh(_Symbol, PERIOD_H1, 0, total_needed, highs) < total_needed)
      return false;

   double cand = highs[shift];
   for(int i = 1; i <= left_bars; i++)
   {
      if(highs[shift + i] >= cand) return false;
   }
   for(int i = 1; i <= right_bars; i++)
   {
      if(highs[shift - i] >= cand) return false;
   }
   return true;
}

bool IsSwingLow(int shift, int left_bars, int right_bars)
{
   double lows[];
   ArraySetAsSeries(lows, true);
   int total_needed = shift + left_bars + 1;
   if(CopyLow(_Symbol, PERIOD_H1, 0, total_needed, lows) < total_needed)
      return false;

   double cand = lows[shift];
   for(int i = 1; i <= left_bars; i++)
   {
      if(lows[shift + i] <= cand) return false;
   }
   for(int i = 1; i <= right_bars; i++)
   {
      if(lows[shift - i] <= cand) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Manage active trailing stops on tick
   ManageTrailingStops();

   // Bar completion check (Operates strictly on completed H1 bar to prevent lookahead)
   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == last_bar_time)
      return;

   last_bar_time = bar_time;

   CheckMonthlyRiskCircuitBreaker();
   if(month_locked) return;

   // Secular Trend EMA on confirmed bar 1
   double ema_val[1];
   if(CopyBuffer(handle_ema200, 0, 1, 1, ema_val) <= 0) return;
   double c_ema200 = ema_val[0];

   double closes[2];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, 2, closes) < 2) return;
   double close_1 = closes[0];

   bool trend_bull = InpUseTrendFilter ? (close_1 > c_ema200) : true;
   bool trend_bear = InpUseTrendFilter ? (close_1 < c_ema200) : true;

   // Katz Fractal Dimension on confirmed bar 1
   double kfd = CalculateKFD(1);
   bool kfd_ok = InpUseKFDNoiseGate ? (kfd <= InpKFDThreshold) : true;
   if(!kfd_ok) return;

   MqlDateTime dt;
   TimeCurrent(dt);
   int sec_of_day = dt.hour * 3600 + dt.min * 60 + dt.sec;

   // Evaluate each lane
   for(int idx = 0; idx < 4; idx++)
   {
      if(!lanes[idx].enabled) continue;
      if(HasOpenPosition(lanes[idx].magic)) continue;

      if(lanes[idx].use_session)
      {
         if(sec_of_day < lanes[idx].start_sec || sec_of_day >= lanes[idx].end_sec)
            continue;
      }

      // Check if swing high occurred at bar (1 + right_buy)
      // When bar 1 closed, right_buy bars have elapsed since shift = 1 + right_buy!
      int shift_buy = 1 + lanes[idx].right_buy;
      bool buy_swing = IsSwingHigh(shift_buy, lanes[idx].left_buy, lanes[idx].right_buy);

      int shift_sell = 1 + lanes[idx].right_sell;
      bool sell_swing = IsSwingLow(shift_sell, lanes[idx].left_sell, lanes[idx].right_sell);

      trade.SetExpertMagicNumber(lanes[idx].magic);

      if(buy_swing && trend_bull)
      {
         double highs[];
         ArraySetAsSeries(highs, true);
         CopyHigh(_Symbol, PERIOD_H1, shift_buy, 1, highs);
         double pivot_h = highs[0];
         double target_level = pivot_h + lanes[idx].offset_buy_pts;

         // Check if bar 1 crossed or touched this level
         double bar1_low = iLow(_Symbol, PERIOD_H1, 1);
         double bar1_high = iHigh(_Symbol, PERIOD_H1, 1);

         if(bar1_low <= target_level && target_level <= bar1_high)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = NormalizeDouble(ask - lanes[idx].sl_pts, _Digits);
            double tp = NormalizeDouble(ask + lanes[idx].tp_pts, _Digits);

            if(trade.Buy(InpLotSize, _Symbol, ask, sl, tp, lanes[idx].name + "_Buy"))
            {
               PrintFormat("[+] %s BUY EXECUTED | Entry: %.2f | SL: %.2f | TP: %.2f | KFD: %.3f",
                           lanes[idx].name, ask, sl, tp, kfd);
            }
         }
      }
      else if(sell_swing && trend_bear)
      {
         double lows[];
         ArraySetAsSeries(lows, true);
         CopyLow(_Symbol, PERIOD_H1, shift_sell, 1, lows);
         double pivot_l = lows[0];
         double target_level = pivot_l + lanes[idx].offset_sell_pts;

         double bar1_low = iLow(_Symbol, PERIOD_H1, 1);
         double bar1_high = iHigh(_Symbol, PERIOD_H1, 1);

         if(bar1_low <= target_level && target_level <= bar1_high)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = NormalizeDouble(bid + lanes[idx].sl_pts, _Digits);
            double tp = NormalizeDouble(bid - lanes[idx].tp_pts, _Digits);

            if(trade.Sell(InpLotSize, _Symbol, bid, sl, tp, lanes[idx].name + "_Sell"))
            {
               PrintFormat("[+] %s SELL EXECUTED | Entry: %.2f | SL: %.2f | TP: %.2f | KFD: %.3f",
                           lanes[idx].name, bid, sl, tp, kfd);
            }
         }
      }
   }
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|       Titan_Ghost_Supreme_Dual_Alpha_Portfolio_EA.mq5            |
//|               CFD Quantitative Strategy Discovery - Strategy 139 |
//|    5-in-1 Sovereign Portfolio: Quantum Titan + Ghost Scalper     |
//|                (Zero Martingale / Zero Recovery Grid)            |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Portfolio Configuration ==="
input double InpLotSize              = 0.10;   // Lot Size per Trade (Institutional Fractional)
input ulong  InpBaseMagic            = 139000; // Base Magic Number (139001 - 139005)

input group "=== Global Gating Filters ==="
input bool   InpUseTrendFilter       = true;   // Enable 200 EMA Secular Trend Filter
input int    InpEMA200Period         = 200;    // Secular Trend EMA Period
input bool   InpUseKFDNoiseGate      = true;   // Enable Katz Fractal Dimension Noise Gate
input int    InpKFDPeriod            = 24;     // Katz Fractal Lookback Window
input double InpKFDThreshold         = 1.42;   // Maximum Permitted Katz Fractal Dimension

input group "=== Engine 1: Quantum Titan Core B (Pivot Pullback) ==="
input bool   InpEnable_Titan_CoreB   = true;   // Enable Quantum Titan Core B Engine
input int    InpTitan_Lookback       = 30;     // Swing Lookback Window
input double InpTitan_PullbackATR    = 0.5;    // Pullback Distance (ATR Multiplier)
input double InpTitan_SL_ATR         = 2.5;    // Stop Loss (ATR Multiplier)
input double InpTitan_TP_ATR         = 3.5;    // Take Profit (ATR Multiplier)

input group "=== Engine 2: Ghost Scalper Lane A (Medium Swing) ==="
input bool   InpEnable_Ghost_A       = true;   // Enable Ghost Lane A (Left 10 / Right 7)
input double InpGhostA_OffsetPts     = 1.80;   // Offset Distance ($1.80)
input double InpGhostA_SL            = 5.00;   // Stop Loss ($5.00)
input double InpGhostA_TP            = 15.00;  // Take Profit ($15.00)
input double InpGhostA_TrailDist     = 0.90;   // Trailing Distance ($0.90)
input double InpGhostA_TrailStep     = 0.30;   // Trailing Step ($0.30)

input group "=== Engine 3: Ghost Scalper Lane B (Fast Swing + Session) ==="
input bool   InpEnable_Ghost_B       = true;   // Enable Ghost Lane B (Left 13/10 / Right 3/4)
input double InpGhostB_OffsetBuy     = -1.50;  // Offset Distance Buy (-$1.50)
input double InpGhostB_OffsetSell    = 1.90;   // Offset Distance Sell (+$1.90)
input double InpGhostB_SL            = 5.00;   // Stop Loss ($5.00)
input double InpGhostB_TP            = 25.00;  // Take Profit ($25.00)
input double InpGhostB_TrailAct      = 0.15;   // Trailing Activation ($0.15)
input double InpGhostB_TrailDist     = 1.15;   // Trailing Distance ($1.15)
input double InpGhostB_TrailStep     = 0.40;   // Trailing Step ($0.40)
input int    InpGhostB_StartSec      = 4500;   // 01:15 Broker Time
input int    InpGhostB_EndSec        = 80100;  // 22:15 Broker Time

input group "=== Engine 4: Ghost Scalper Lane C (Micro Swing) ==="
input bool   InpEnable_Ghost_C       = true;   // Enable Ghost Lane C (Left 7 / Right 5)
input double InpGhostC_OffsetPts     = 2.20;   // Offset Distance ($2.20)
input double InpGhostC_SL            = 10.00;  // Stop Loss ($10.00)
input double InpGhostC_TP            = 25.00;  // Take Profit ($25.00)
input double InpGhostC_TrailAct      = 0.15;   // Trailing Activation ($0.15)
input double InpGhostC_TrailDist     = 0.90;   // Trailing Distance ($0.90)
input double InpGhostC_TrailStep     = 0.20;   // Trailing Step ($0.20)

input group "=== Engine 5: Ghost Scalper Lane D (Macro Swing) ==="
input bool   InpEnable_Ghost_D       = true;   // Enable Ghost Lane D (Left 26 / Right 20)
input double InpGhostD_OffsetPts     = 1.80;   // Offset Distance ($1.80)
input double InpGhostD_SL            = 8.00;   // Stop Loss ($8.00)
input double InpGhostD_TP            = 17.00;  // Take Profit ($17.00)
input double InpGhostD_TrailAct      = 1.00;   // Trailing Activation ($1.00)
input double InpGhostD_TrailDist     = 0.35;   // Trailing Distance ($0.35)
input double InpGhostD_TrailStep     = 0.55;   // Trailing Step ($0.55)

// Global variables
CTrade   trade;
int      handle_atr;
int      handle_ema200;
datetime last_bar_time;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);

   handle_atr = iATR(_Symbol, PERIOD_H1, 14);
   handle_ema200 = iMA(_Symbol, PERIOD_H1, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE)
   {
      Print("[-] Error initializing indicator handles.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   Print("[+] Titan Ghost Supreme Dual Alpha Portfolio EA (Strategy 139) initialized successfully.");
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
//| Check if open position exists for a specific magic number        |
//+------------------------------------------------------------------+
bool HasOpenPosition(ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if((ulong)PositionGetInteger(POSITION_MAGIC) == magic)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Manage Trailing Stop for Ghost Lanes                             |
//+------------------------------------------------------------------+
void ManageTrailingStops()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      ulong magic = (ulong)PositionGetInteger(POSITION_MAGIC);
      ulong ticket = PositionGetTicket(i);
      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur_sl = PositionGetDouble(POSITION_SL);
      double cur_tp = PositionGetDouble(POSITION_TP);

      double act_pts = 0.0, dist_pts = 0.0, step_pts = 0.0;
      bool manage = false;

      if(magic == InpBaseMagic + 2) // Ghost A
      {
         act_pts = 0.0; dist_pts = InpGhostA_TrailDist; step_pts = InpGhostA_TrailStep; manage = true;
      }
      else if(magic == InpBaseMagic + 3) // Ghost B
      {
         act_pts = InpGhostB_TrailAct; dist_pts = InpGhostB_TrailDist; step_pts = InpGhostB_TrailStep; manage = true;
      }
      else if(magic == InpBaseMagic + 4) // Ghost C
      {
         act_pts = InpGhostC_TrailAct; dist_pts = InpGhostC_TrailDist; step_pts = InpGhostC_TrailStep; manage = true;
      }
      else if(magic == InpBaseMagic + 5) // Ghost D
      {
         act_pts = InpGhostD_TrailAct; dist_pts = InpGhostD_TrailDist; step_pts = InpGhostD_TrailStep; manage = true;
      }

      if(manage)
      {
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
      }
   }
}

//+------------------------------------------------------------------+
//| Evaluate Swing Fractal Condition                                 |
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
      if(highs[shift + i] >= cand) return false;
   for(int i = 1; i <= right_bars; i++)
      if(highs[shift - i] >= cand) return false;
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
      if(lows[shift + i] <= cand) return false;
   for(int i = 1; i <= right_bars; i++)
      if(lows[shift - i] <= cand) return false;
   return true;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   ManageTrailingStops();

   datetime bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(bar_time == last_bar_time) return;
   last_bar_time = bar_time;

   double atr_buf[1], ema_buf[1];
   if(CopyBuffer(handle_atr, 0, 1, 1, atr_buf) <= 0 ||
      CopyBuffer(handle_ema200, 0, 1, 1, ema_buf) <= 0)
      return;

   double c_atr = atr_buf[0];
   double c_ema200 = ema_buf[0];

   double closes[2];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, 2, closes) < 2) return;
   double close_1 = closes[0];
   double close_2 = closes[1];

   bool trend_bull = InpUseTrendFilter ? (close_1 > c_ema200) : true;
   bool trend_bear = InpUseTrendFilter ? (close_1 < c_ema200) : true;

   double kfd = CalculateKFD(1);
   bool kfd_ok = InpUseKFDNoiseGate ? (kfd <= InpKFDThreshold) : true;
   if(!kfd_ok) return;

   MqlDateTime dt;
   TimeCurrent(dt);
   int sec_of_day = dt.hour * 3600 + dt.min * 60 + dt.sec;

   double bar1_low = iLow(_Symbol, PERIOD_H1, 1);
   double bar1_high = iHigh(_Symbol, PERIOD_H1, 1);

   // ---------------------------------------------------------------
   // 1. ENGINE 1: QUANTUM TITAN CORE B (PIVOT PULLBACK)
   // ---------------------------------------------------------------
   if(InpEnable_Titan_CoreB && !HasOpenPosition(InpBaseMagic + 1))
   {
      double swing_highs[], swing_lows[];
      ArraySetAsSeries(swing_highs, true);
      ArraySetAsSeries(swing_lows, true);
      if(CopyHigh(_Symbol, PERIOD_H1, 2, InpTitan_Lookback, swing_highs) == InpTitan_Lookback &&
         CopyLow(_Symbol, PERIOD_H1, 2, InpTitan_Lookback, swing_lows) == InpTitan_Lookback)
      {
         int h_idx = ArrayMaximum(swing_highs, 0, InpTitan_Lookback);
         int l_idx = ArrayMinimum(swing_lows, 0, InpTitan_Lookback);
         double p_high = swing_highs[h_idx];
         double p_low = swing_lows[l_idx];

         double long_pb = p_high - (InpTitan_PullbackATR * c_atr);
         double short_pb = p_low + (InpTitan_PullbackATR * c_atr);

         bool buy_pb = (close_1 <= long_pb) && (close_2 > long_pb);
         bool sell_pb = (close_1 >= short_pb) && (close_2 < short_pb);

         trade.SetExpertMagicNumber(InpBaseMagic + 1);
         if(buy_pb && trend_bull)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = NormalizeDouble(ask - (InpTitan_SL_ATR * c_atr), _Digits);
            double tp = NormalizeDouble(ask + (InpTitan_TP_ATR * c_atr), _Digits);
            trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "Titan_CoreB_Buy");
         }
         else if(sell_pb && trend_bear)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = NormalizeDouble(bid + (InpTitan_SL_ATR * c_atr), _Digits);
            double tp = NormalizeDouble(bid - (InpTitan_TP_ATR * c_atr), _Digits);
            trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "Titan_CoreB_Sell");
         }
      }
   }

   // ---------------------------------------------------------------
   // 2. ENGINE 2: GHOST A (MEDIUM SWING)
   // ---------------------------------------------------------------
   if(InpEnable_Ghost_A && !HasOpenPosition(InpBaseMagic + 2))
   {
      trade.SetExpertMagicNumber(InpBaseMagic + 2);
      if(IsSwingHigh(1 + 7, 10, 7) && trend_bull)
      {
         double lvl = iHigh(_Symbol, PERIOD_H1, 1 + 7) - InpGhostA_OffsetPts;
         if(bar1_low <= lvl && lvl <= bar1_high)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade.Buy(InpLotSize, _Symbol, ask, NormalizeDouble(ask - InpGhostA_SL, _Digits), NormalizeDouble(ask + InpGhostA_TP, _Digits), "GhostA_Buy");
         }
      }
      else if(IsSwingLow(1 + 7, 10, 7) && trend_bear)
      {
         double lvl = iLow(_Symbol, PERIOD_H1, 1 + 7) + InpGhostA_OffsetPts;
         if(bar1_low <= lvl && lvl <= bar1_high)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade.Sell(InpLotSize, _Symbol, bid, NormalizeDouble(bid + InpGhostA_SL, _Digits), NormalizeDouble(bid - InpGhostA_TP, _Digits), "GhostA_Sell");
         }
      }
   }

   // ---------------------------------------------------------------
   // 3. ENGINE 3: GHOST B (FAST SWING + SESSION)
   // ---------------------------------------------------------------
   if(InpEnable_Ghost_B && !HasOpenPosition(InpBaseMagic + 3))
   {
      if(sec_of_day >= InpGhostB_StartSec && sec_of_day < InpGhostB_EndSec)
      {
         trade.SetExpertMagicNumber(InpBaseMagic + 3);
         if(IsSwingHigh(1 + 3, 13, 3) && trend_bull)
         {
            double lvl = iHigh(_Symbol, PERIOD_H1, 1 + 3) + InpGhostB_OffsetBuy;
            if(bar1_low <= lvl && lvl <= bar1_high)
            {
               double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
               trade.Buy(InpLotSize, _Symbol, ask, NormalizeDouble(ask - InpGhostB_SL, _Digits), NormalizeDouble(ask + InpGhostB_TP, _Digits), "GhostB_Buy");
            }
         }
         else if(IsSwingLow(1 + 4, 10, 4) && trend_bear)
         {
            double lvl = iLow(_Symbol, PERIOD_H1, 1 + 4) + InpGhostB_OffsetSell;
            if(bar1_low <= lvl && lvl <= bar1_high)
            {
               double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
               trade.Sell(InpLotSize, _Symbol, bid, NormalizeDouble(bid + InpGhostB_SL, _Digits), NormalizeDouble(bid - InpGhostB_TP, _Digits), "GhostB_Sell");
            }
         }
      }
   }

   // ---------------------------------------------------------------
   // 4. ENGINE 4: GHOST C (MICRO SWING)
   // ---------------------------------------------------------------
   if(InpEnable_Ghost_C && !HasOpenPosition(InpBaseMagic + 4))
   {
      trade.SetExpertMagicNumber(InpBaseMagic + 4);
      if(IsSwingHigh(1 + 5, 7, 5) && trend_bull)
      {
         double lvl = iHigh(_Symbol, PERIOD_H1, 1 + 5) - InpGhostC_OffsetPts;
         if(bar1_low <= lvl && lvl <= bar1_high)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade.Buy(InpLotSize, _Symbol, ask, NormalizeDouble(ask - InpGhostC_SL, _Digits), NormalizeDouble(ask + InpGhostC_TP, _Digits), "GhostC_Buy");
         }
      }
      else if(IsSwingLow(1 + 5, 7, 5) && trend_bear)
      {
         double lvl = iLow(_Symbol, PERIOD_H1, 1 + 5) + InpGhostC_OffsetPts;
         if(bar1_low <= lvl && lvl <= bar1_high)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade.Sell(InpLotSize, _Symbol, bid, NormalizeDouble(bid + InpGhostC_SL, _Digits), NormalizeDouble(bid - InpGhostC_TP, _Digits), "GhostC_Sell");
         }
      }
   }

   // ---------------------------------------------------------------
   // 5. ENGINE 5: GHOST D (MACRO SWING)
   // ---------------------------------------------------------------
   if(InpEnable_Ghost_D && !HasOpenPosition(InpBaseMagic + 5))
   {
      trade.SetExpertMagicNumber(InpBaseMagic + 5);
      if(IsSwingHigh(1 + 20, 26, 20) && trend_bull)
      {
         double lvl = iHigh(_Symbol, PERIOD_H1, 1 + 20) - InpGhostD_OffsetPts;
         if(bar1_low <= lvl && lvl <= bar1_high)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade.Buy(InpLotSize, _Symbol, ask, NormalizeDouble(ask - InpGhostD_SL, _Digits), NormalizeDouble(ask + InpGhostD_TP, _Digits), "GhostD_Buy");
         }
      }
      else if(IsSwingLow(1 + 20, 26, 20) && trend_bear)
      {
         double lvl = iLow(_Symbol, PERIOD_H1, 1 + 20) + InpGhostD_OffsetPts;
         if(bar1_low <= lvl && lvl <= bar1_high)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade.Sell(InpLotSize, _Symbol, bid, NormalizeDouble(bid + InpGhostD_SL, _Digits), NormalizeDouble(bid - InpGhostD_TP, _Digits), "GhostD_Sell");
         }
      }
   }
}
//+------------------------------------------------------------------+

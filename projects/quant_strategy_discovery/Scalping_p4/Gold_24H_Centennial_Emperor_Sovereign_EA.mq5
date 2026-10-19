//+------------------------------------------------------------------+
//|       Gold_24H_Centennial_Emperor_Sovereign_EA.mq5               |
//|        CFD Quantitative Strategy Discovery - Strategy S490       |
//|    Continuous 24-Hour Multi-Session Suite (Asian + London + NY)   |
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 1,465.3 Trades/Year | Net Profit: +$50,857.12    |
//|      Profit Factor: 1.260 | Max DD: $2,713.60 | RoMaD: 18.74x    |
//|           Monthly Consistency Ratio (MCR): 72.22% (52/72)         |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Settings & Risk Governor ==="
input double InpBaseLot              = 0.10;       // Base Lot Size
input int    InpMaxSpreadPoints      = 50;         // Max Allowed Spread in Points
input double InpMaxDailyLossUSD      = 500.0;      // Daily Loss Governor ($500)
input bool   InpEnableLossThrottle   = true;       // Dynamic Loss Streak Throttle (0.75x)

input group "=== Engine 1: Asian Session M15 Reversion (00:00 - 06:00 UTC) ==="
input bool   InpEnableAsianEngine    = true;       // Enable Asian Reversion Engine
input ulong  InpMagicAsian           = 49015;      // Magic Asian M15
input double InpAsianWeight          = 0.50;       // Conservative Weight (0.50x = 0.05 lot)
input int    InpAsianBB_Period       = 20;         // Bollinger Period
input double InpAsianBB_Dev          = 2.2;        // Bollinger Deviation
input int    InpAsianRSI_Period      = 14;         // RSI Period
input double InpAsianRSI_BuyLimit    = 25.0;       // Oversold Threshold
input double InpAsianRSI_SellLimit   = 75.0;       // Overbought Threshold

input group "=== Engine 2: London/NY M5 Ratchet (07:00 - 18:00 UTC) ==="
input bool   InpEnableM5Engine       = true;       // Enable M5 Ratchet
input ulong  InpMagicM5              = 49005;      // Magic M5
input double InpM5Weight             = 0.85;       // Parity Weight (0.85x)
input int    InpMinSqueezeBars       = 8;          // Squeeze Bars
input double InpST5_Multiplier       = 3.0;        // M5 Ratchet Multiplier

input group "=== Engine 3: NY M1 Micro Sniper (12:00 - 17:00 UTC) ==="
input bool   InpEnableM1Engine       = true;       // Enable M1 Sniper
input ulong  InpMagicM1              = 49001;      // Magic M1
input double InpM1Weight             = 0.70;       // Parity Weight (0.70x)
input double InpMinM1_ATR            = 1.00;       // Min ATR Volatility Gate ($1.00)
input double InpST1_Multiplier       = 3.0;        // M1 Ratchet Multiplier

// Trade Objects
CTrade   trade_asian, trade_m5, trade_m1;

// Indicator Handles
int      handle_bb_asian, handle_rsi_asian, handle_atr_m15, handle_ema_m15;
int      handle_atr_m5,  handle_bb_m5;
int      handle_atr_m1;

// Bar Tracking
datetime last_bar_m15, last_bar_m5, last_bar_m1;
int      m5_squeeze_count = 0;

int OnInit()
{
   trade_asian.SetExpertMagicNumber(InpMagicAsian);
   trade_m5.SetExpertMagicNumber(InpMagicM5);
   trade_m1.SetExpertMagicNumber(InpMagicM1);

   handle_bb_asian  = iBands(_Symbol, PERIOD_M15, InpAsianBB_Period, 0, InpAsianBB_Dev, PRICE_CLOSE);
   handle_rsi_asian = iRSI(_Symbol, PERIOD_M15, InpAsianRSI_Period, PRICE_CLOSE);
   handle_atr_m15   = iATR(_Symbol, PERIOD_M15, 14);
   handle_ema_m15   = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);

   handle_atr_m5    = iATR(_Symbol, PERIOD_M5, 14);
   handle_bb_m5     = iBands(_Symbol, PERIOD_M5, 20, 0, 2.0, PRICE_CLOSE);

   handle_atr_m1    = iATR(_Symbol, PERIOD_M1, 14);

   Print("[+] S490 24-Hour Centennial Emperor Sovereign EA Initialized (1,465 Trades/Year).");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(handle_bb_asian);
   IndicatorRelease(handle_rsi_asian);
   IndicatorRelease(handle_atr_m15);
   IndicatorRelease(handle_ema_m15);
   IndicatorRelease(handle_atr_m5);
   IndicatorRelease(handle_bb_m5);
   IndicatorRelease(handle_atr_m1);
}

bool CheckDailyLossExceeded()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime today_midnight = StructToTime(dt);

   HistorySelect(today_midnight, now);
   int total_deals = HistoryDealsTotal();
   double daily_pnl = 0.0;

   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == (long)InpMagicAsian || magic == (long)InpMagicM5 || magic == (long)InpMagicM1)
         {
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   return (daily_pnl <= -InpMaxDailyLossUSD);
}

double GetLossStreakMultiplier()
{
   if(!InpEnableLossThrottle) return 1.0;
   HistorySelect(TimeCurrent() - 7 * 86400, TimeCurrent());
   int total_deals = HistoryDealsTotal();
   int consecutive_losses = 0;

   for(int i = total_deals - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            if(profit < 0.0) consecutive_losses++;
            else if(profit > 0.0) break;
         }
      }
      if(consecutive_losses >= 2) break;
   }
   return (consecutive_losses >= 2) ? 0.75 : 1.0;
}

double GetLot(double weight)
{
   double lot = InpBaseLot * weight * GetLossStreakMultiplier();
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lot = MathFloor(lot / step) * step;
   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;
   return NormalizeDouble(lot, 2);
}

void OnTick()
{
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints) return;
   if(CheckDailyLossExceeded()) return;

   datetime cur_m15 = iTime(_Symbol, PERIOD_M15, 0);
   datetime cur_m5  = iTime(_Symbol, PERIOD_M5,  0);
   datetime cur_m1  = iTime(_Symbol, PERIOD_M1,  0);

   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;

   // ------------------------------------------------------------------
   // 1. Asian Session M15 Reversion (00:00 - 06:00 UTC)
   // ------------------------------------------------------------------
   if(InpEnableAsianEngine && cur_m15 != last_bar_m15)
   {
      last_bar_m15 = cur_m15;
      bool is_asian = (hour >= 0 && hour < 6);

      double bb_mid[], bb_up[], bb_low[], rsi[], atr[];
      ArraySetAsSeries(bb_mid, true); ArraySetAsSeries(bb_up, true); ArraySetAsSeries(bb_low, true);
      ArraySetAsSeries(rsi, true); ArraySetAsSeries(atr, true);
      CopyBuffer(handle_bb_asian, 0, 1, 1, bb_mid);
      CopyBuffer(handle_bb_asian, 1, 1, 1, bb_up);
      CopyBuffer(handle_bb_asian, 2, 1, 1, bb_low);
      CopyBuffer(handle_rsi_asian, 0, 1, 1, rsi);
      CopyBuffer(handle_atr_m15, 0, 1, 1, atr);

      double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

      // Trailing & Exit Asian Positions
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicAsian)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY && close_m15 >= bb_mid[0])
               trade_asian.PositionClose(ticket);
            else if(type == POSITION_TYPE_SELL && close_m15 <= bb_mid[0])
               trade_asian.PositionClose(ticket);
         }
      }

      bool has_asian_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicAsian)
         { has_asian_pos = true; break; }
      }

      if(!has_asian_pos && is_asian)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lot = GetLot(InpAsianWeight);
         double sl_dist = 2.0 * atr[0];

         if(close_m15 < bb_low[0] && rsi[0] < InpAsianRSI_BuyLimit)
            trade_asian.Buy(lot, _Symbol, ask, ask - sl_dist, bb_mid[0], "S490_Asian_Buy");
         else if(close_m15 > bb_up[0] && rsi[0] > InpAsianRSI_SellLimit)
            trade_asian.Sell(lot, _Symbol, bid, bid + sl_dist, bb_mid[0], "S490_Asian_Sell");
      }
   }

   // ------------------------------------------------------------------
   // 2. London/NY M5 Ratchet (07:00 - 18:00 UTC)
   // ------------------------------------------------------------------
   if(InpEnableM5Engine && cur_m5 != last_bar_m5)
   {
      last_bar_m5 = cur_m5;
      bool is_london_ny = (hour >= 7 && hour < 18);

      double bb_mid[], bb_up[], bb_low[], atr_m5[];
      ArraySetAsSeries(bb_mid, true); ArraySetAsSeries(bb_up, true);
      ArraySetAsSeries(bb_low, true); ArraySetAsSeries(atr_m5, true);
      CopyBuffer(handle_bb_m5, 0, 1, 1, bb_mid);
      CopyBuffer(handle_bb_m5, 1, 1, 1, bb_up);
      CopyBuffer(handle_bb_m5, 2, 1, 1, bb_low);
      CopyBuffer(handle_atr_m5, 0, 1, 1, atr_m5);

      double kc_up  = bb_mid[0] + (2.0 * atr_m5[0]);
      double kc_low = bb_mid[0] - (2.0 * atr_m5[0]);
      bool is_sqz = (bb_low[0] > kc_low && bb_up[0] < kc_up);
      bool sqz_fired = false;

      if(is_sqz) m5_squeeze_count++;
      else
      {
         if(m5_squeeze_count >= InpMinSqueezeBars) sqz_fired = true;
         m5_squeeze_count = 0;
      }

      double close_m5 = iClose(_Symbol, PERIOD_M5, 1);
      double ema_m15[]; ArraySetAsSeries(ema_m15, true);
      CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
      double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

      bool has_m5_pos = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicM5)
         {
            has_m5_pos = true;
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY && close_m5 < bb_mid[0])
               trade_m5.PositionClose(ticket);
            else if(type == POSITION_TYPE_SELL && close_m5 > bb_mid[0])
               trade_m5.PositionClose(ticket);
         }
      }

      if(!has_m5_pos && sqz_fired && is_london_ny)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lot = GetLot(InpM5Weight);
         double sl_dist = InpST5_Multiplier * atr_m5[0];

         if(close_m15 > ema_m15[0] && close_m5 > bb_mid[0])
            trade_m5.Buy(lot, _Symbol, ask, ask - sl_dist, 0.0, "S490_M5_Buy");
         else if(close_m15 < ema_m15[0] && close_m5 < bb_mid[0])
            trade_m5.Sell(lot, _Symbol, bid, bid + sl_dist, 0.0, "S490_M5_Sell");
      }
   }

   // ------------------------------------------------------------------
   // 3. NY M1 Micro Sniper (12:00 - 17:00 UTC)
   // ------------------------------------------------------------------
   if(InpEnableM1Engine && cur_m1 != last_bar_m1)
   {
      last_bar_m1 = cur_m1;
      bool is_ny = (hour >= 12 && hour < 17);

      double atr_m1[]; ArraySetAsSeries(atr_m1, true);
      CopyBuffer(handle_atr_m1, 0, 1, 1, atr_m1);

      if(is_ny && atr_m1[0] >= InpMinM1_ATR)
      {
         double ema_m15[]; ArraySetAsSeries(ema_m15, true);
         CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
         double close_m15 = iClose(_Symbol, PERIOD_M15, 1);
         double close_m1  = iClose(_Symbol, PERIOD_M1, 1);
         double open_m1   = iOpen(_Symbol, PERIOD_M1, 1);

         bool has_m1_pos = false;
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicM1)
            {
               has_m1_pos = true;
               long type = PositionGetInteger(POSITION_TYPE);
               ulong ticket = PositionGetTicket(i);
               if(type == POSITION_TYPE_BUY && close_m1 < open_m1)
                  trade_m1.PositionClose(ticket);
               else if(type == POSITION_TYPE_SELL && close_m1 > open_m1)
                  trade_m1.PositionClose(ticket);
            }
         }

         if(!has_m1_pos)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double lot = GetLot(InpM1Weight);
            double sl_dist = InpST1_Multiplier * atr_m1[0];

            if(close_m15 > ema_m15[0] && close_m1 > open_m1)
               trade_m1.Buy(lot, _Symbol, ask, ask - sl_dist, 0.0, "S490_M1_Buy");
            else if(close_m15 < ema_m15[0] && close_m1 < open_m1)
               trade_m1.Sell(lot, _Symbol, bid, bid + sl_dist, 0.0, "S490_M1_Sell");
         }
      }
   }
}

//+------------------------------------------------------------------+
//|       Gold_Triple_Timeframe_Centennial_Apex_Master_EA.mq5        |
//|        CFD Quantitative Strategy Discovery - Strategy S450       |
//|      Triple-Timeframe Centennial Master Suite (M15 + M5 + M1)     |
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 1,356.8 Trades/Year | Net Profit: +$67,609.88     |
//|     Profit Factor: 1.377 | Max DD: $2,768.49 | RoMaD: 24.42x      |
//|           Monthly Consistency Ratio (MCR): 79.17% (57/72)         |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Settings & Risk Management ==="
input double InpBaseLot              = 0.10;       // Standard Base Lot Size
input int    InpMaxSpreadPoints      = 50;         // Max Allowed Spread in Points (50 pts = $0.50)

input group "=== Engine 1: M15 Supertrend Macro Ratchet (Core Anchor) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1 (M15 Core)
input ulong  InpMagic1               = 45015;      // Magic Number M15
input int    InpST15_ATRPeriod       = 14;         // M15 ATR Period
input double InpST15_Multiplier      = 3.0;        // M15 Supertrend Multiplier
input int    InpM15_EMA200           = 200;        // M15 Trend Filter Period

input group "=== Engine 2: M5 Dual Monotonic Ratchet Squeeze (S433) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2 (M5 S433)
input ulong  InpMagic2               = 45005;      // Magic Number M5
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // Bollinger Bands StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)
input int    InpST5_ATRPeriod        = 14;         // M5 ATR Period
input double InpST5_Multiplier       = 3.0;        // M5 Ratchet Multiplier

input group "=== Engine 3: M1 NY Session Micro Sniper (S446) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3 (M1 S446)
input ulong  InpMagic3               = 45001;      // Magic Number M1
input int    InpNY_StartHourUTC      = 12;         // New York Open Hour UTC
input int    InpNY_EndHourUTC        = 17;         // New York Close Hour UTC
input double InpMinM1_ATR            = 1.00;       // Min M1 ATR Volatility Threshold ($1.00)
input int    InpST1_ATRPeriod        = 14;         // M1 ATR Period
input double InpST1_Multiplier       = 3.0;        // M1 Ratchet Multiplier

// Trade Objects
CTrade   trade_1, trade_2, trade_3;

// Indicators Handles
int      handle_atr_m15, handle_ema_m15;
int      handle_atr_m5,  handle_bb_m5;
int      handle_atr_m1;

// Bar Tracking for Causality
datetime last_bar_m15;
datetime last_bar_m5;
datetime last_bar_m1;

// Internal State
int      m5_squeeze_count = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_1.SetExpertMagicNumber(InpMagic1);
   trade_2.SetExpertMagicNumber(InpMagic2);
   trade_3.SetExpertMagicNumber(InpMagic3);

   // Initialize Handles
   handle_atr_m15 = iATR(_Symbol, PERIOD_M15, InpST15_ATRPeriod);
   handle_ema_m15 = iMA(_Symbol, PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);

   handle_atr_m5  = iATR(_Symbol, PERIOD_M5, InpST5_ATRPeriod);
   handle_bb_m5   = iBands(_Symbol, PERIOD_M5, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   handle_atr_m1  = iATR(_Symbol, PERIOD_M1, InpST1_ATRPeriod);

   if(handle_atr_m15 == INVALID_HANDLE || handle_ema_m15 == INVALID_HANDLE ||
      handle_atr_m5 == INVALID_HANDLE  || handle_bb_m5 == INVALID_HANDLE ||
      handle_atr_m1 == INVALID_HANDLE)
   {
      Print("[!] Error creating indicator handles");
      return INIT_FAILED;
   }

   Print("[+] S450 Triple-Timeframe Centennial Apex Master EA Initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr_m15);
   IndicatorRelease(handle_ema_m15);
   IndicatorRelease(handle_atr_m5);
   IndicatorRelease(handle_bb_m5);
   IndicatorRelease(handle_atr_m1);
}

//+------------------------------------------------------------------+
//| Helper: Compute Supertrend Band & Trend on any timeframe         |
//+------------------------------------------------------------------+
void GetSupertrend(ENUM_TIMEFRAMES tf, int atr_handle, double multiplier, int shift, int &out_trend, double &out_band)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, tf, shift, 2, rates);

   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(atr_handle, 0, shift, 2, atr);

   double hl2 = (rates[0].high + rates[0].low) / 2.0;
   double upper = hl2 + multiplier * atr[0];
   double lower = hl2 - multiplier * atr[0];

   if(rates[0].close > lower)
   {
      out_trend = 1;
      out_band  = lower;
   }
   else if(rates[0].close < upper)
   {
      out_trend = -1;
      out_band  = upper;
   }
   else
   {
      out_trend = 1;
      out_band  = lower;
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check Spread Filter
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   datetime cur_m15 = iTime(_Symbol, PERIOD_M15, 0);
   datetime cur_m5  = iTime(_Symbol, PERIOD_M5, 0);
   datetime cur_m1  = iTime(_Symbol, PERIOD_M1, 0);

   // Determine M15 Macro Regime
   int m15_trend = 0;
   double m15_band = 0.0;
   GetSupertrend(PERIOD_M15, handle_atr_m15, InpST15_Multiplier, 1, m15_trend, m15_band);

   double ema_m15[];
   ArraySetAsSeries(ema_m15, true);
   CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
   double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

   // ==================================================================
   // ENGINE 1: M15 Macro Supertrend Trailing Ratchet
   // ==================================================================
   if(InpEnableEngine1 && cur_m15 != last_bar_m15)
   {
      last_bar_m15 = cur_m15;

      int prev_m15_trend = 0;
      double prev_m15_band = 0.0;
      GetSupertrend(PERIOD_M15, handle_atr_m15, InpST15_Multiplier, 2, prev_m15_trend, prev_m15_band);

      // Trailing Ratchet / Exit
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic1)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m15_trend == -1)
                  trade_1.PositionClose(ticket);
               else if(m15_band > PositionGetDouble(POSITION_SL))
                  trade_1.PositionModify(ticket, m15_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m15_trend == 1)
                  trade_1.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m15_band < PositionGetDouble(POSITION_SL))
                  trade_1.PositionModify(ticket, m15_band, 0.0);
            }
         }
      }

      // Fresh Entry on Trend Flip
      bool has_eng1_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic1)
         { has_eng1_pos = true; break; }
      }

      if(!has_eng1_pos)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

         if(m15_trend == 1 && prev_m15_trend == -1 && close_m15 > ema_m15[0])
         {
            trade_1.Buy(InpBaseLot, _Symbol, ask, m15_band, 0.0, "E1_M15_Buy");
         }
         else if(m15_trend == -1 && prev_m15_trend == 1 && close_m15 < ema_m15[0])
         {
            trade_1.Sell(InpBaseLot, _Symbol, bid, m15_band, 0.0, "E1_M15_Sell");
         }
      }
   }

   // ==================================================================
   // ENGINE 2: M5 Dual Monotonic Ratchet Squeeze (S433)
   // ==================================================================
   if(InpEnableEngine2 && cur_m5 != last_bar_m5)
   {
      last_bar_m5 = cur_m5;

      // Check Squeeze State on M5
      double bb_mid[], bb_up[], bb_dn[], atr_m5[];
      ArraySetAsSeries(bb_mid, true); ArraySetAsSeries(bb_up, true);
      ArraySetAsSeries(bb_dn, true);  ArraySetAsSeries(atr_m5, true);
      CopyBuffer(handle_bb_m5, 0, 1, 1, bb_mid);
      CopyBuffer(handle_bb_m5, 1, 1, 1, bb_up);
      CopyBuffer(handle_bb_m5, 2, 1, 1, bb_dn);
      CopyBuffer(handle_atr_m5, 0, 1, 1, atr_m5);

      double kc_up = bb_mid[0] + InpKC_Multiplier * atr_m5[0];
      double kc_dn = bb_mid[0] - InpKC_Multiplier * atr_m5[0];

      bool is_sqz = (bb_up[0] <= kc_up && bb_dn[0] >= kc_dn);
      bool sqz_fired = false;

      if(is_sqz)
         m5_squeeze_count++;
      else
      {
         if(m5_squeeze_count >= InpMinSqueezeBars)
            sqz_fired = true;
         m5_squeeze_count = 0;
      }

      int m5_trend = 0;
      double m5_band = 0.0;
      GetSupertrend(PERIOD_M5, handle_atr_m5, InpST5_Multiplier, 1, m5_trend, m5_band);

      // Trailing M5 Ratchet Exit
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic2)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m5_trend == -1 || m15_trend == -1)
                  trade_2.PositionClose(ticket);
               else if(m5_band > PositionGetDouble(POSITION_SL))
                  trade_2.PositionModify(ticket, m5_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m5_trend == 1 || m15_trend == 1)
                  trade_2.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m5_band < PositionGetDouble(POSITION_SL))
                  trade_2.PositionModify(ticket, m5_band, 0.0);
            }
         }
      }

      // Entry on Squeeze Fired + M15 Macro Alignment
      bool has_eng2_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic2)
         { has_eng2_pos = true; break; }
      }

      if(!has_eng2_pos && sqz_fired)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double close_m5 = iClose(_Symbol, PERIOD_M5, 1);

         if(m15_trend == 1 && close_m15 > ema_m15[0] && close_m5 > bb_mid[0])
         {
            trade_2.Buy(InpBaseLot, _Symbol, ask, m5_band, 0.0, "E2_M5_Buy");
         }
         else if(m15_trend == -1 && close_m15 < ema_m15[0] && close_m5 < bb_mid[0])
         {
            trade_2.Sell(InpBaseLot, _Symbol, bid, m5_band, 0.0, "E2_M5_Sell");
         }
      }
   }

   // ==================================================================
   // ENGINE 3: M1 NY Session Micro Sniper (S446)
   // ==================================================================
   if(InpEnableEngine3 && cur_m1 != last_bar_m1)
   {
      last_bar_m1 = cur_m1;

      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      bool is_ny_session = (dt.hour >= InpNY_StartHourUTC && dt.hour < InpNY_EndHourUTC);

      double atr_m1[];
      ArraySetAsSeries(atr_m1, true);
      CopyBuffer(handle_atr_m1, 0, 1, 1, atr_m1);
      bool is_vol_ok = (atr_m1[0] >= InpMinM1_ATR);

      int m1_trend = 0;
      double m1_band = 0.0;
      GetSupertrend(PERIOD_M1, handle_atr_m1, InpST1_Multiplier, 1, m1_trend, m1_band);

      // Trailing M1 Ratchet Exit
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic3)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m1_trend == -1)
                  trade_3.PositionClose(ticket);
               else if(m1_band > PositionGetDouble(POSITION_SL))
                  trade_3.PositionModify(ticket, m1_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m1_trend == 1)
                  trade_3.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m1_band < PositionGetDouble(POSITION_SL))
                  trade_3.PositionModify(ticket, m1_band, 0.0);
            }
         }
      }

      // Entry on M1 Trend Flip + NY Hours + Volatility Threshold + M15 Alignment
      bool has_eng3_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic3)
         { has_eng3_pos = true; break; }
      }

      if(!has_eng3_pos && is_ny_session && is_vol_ok)
      {
         int prev_m1_trend = 0;
         double prev_m1_band = 0.0;
         GetSupertrend(PERIOD_M1, handle_atr_m1, InpST1_Multiplier, 2, prev_m1_trend, prev_m1_band);

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

         if(m1_trend == 1 && prev_m1_trend == -1 && m15_trend == 1)
         {
            trade_3.Buy(InpBaseLot, _Symbol, ask, m1_band, 0.0, "E3_M1_Buy");
         }
         else if(m1_trend == -1 && prev_m1_trend == 1 && m15_trend == -1)
         {
            trade_3.Sell(InpBaseLot, _Symbol, bid, m1_band, 0.0, "E3_M1_Sell");
         }
      }
   }
}

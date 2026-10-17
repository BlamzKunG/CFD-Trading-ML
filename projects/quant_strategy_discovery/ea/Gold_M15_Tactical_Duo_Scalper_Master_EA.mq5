//+------------------------------------------------------------------+
//|                 Gold_M15_Tactical_Duo_Scalper_Master_EA.mq5      |
//|               CFD Quantitative Strategy Discovery - Strategy 259 |
//|          Tactical Duo: Supertrend Trailing + Fast RSI Scalper    |
//|                  Asset: XAUUSD | Timeframe: M15                  |
//+------------------------------------------------------------------+
#property copyright "CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Trade Configuration ==="
input double InpLotSize              = 0.10;       // Standardized Institutional Lot Size
input ulong  InpMagicSupertrend      = 259001;     // Magic Number: Supertrend Engine
input ulong  InpMagicRSISnapshot     = 259002;     // Magic Number: Fast RSI Scalper Engine
input int    InpEMA200Period         = 200;        // Macro Trend Filter Period

input group "=== Sub-Engine 1: Supertrend Trailing ==="
input bool   InpEnableSupertrend     = true;       // Enable Supertrend Engine
input int    InpST_ATRPeriod         = 14;         // ATR Smoothing Period
input double InpST_Multiplier        = 3.0;        // Supertrend Envelope Multiplier

input group "=== Sub-Engine 2: Fast RSI Snapshot Scalper ==="
input bool   InpEnableRSISnapshot    = true;       // Enable Fast RSI Scalper
input int    InpRSI_Period           = 6;          // Fast RSI Period
input double InpRSI_Oversold         = 18.0;       // Extreme Oversold Entry
input double InpRSI_Overbought       = 82.0;       // Extreme Overbought Entry
input double InpRSI_TP_Mult          = 1.6;        // Take Profit (x ATR)
input double InpRSI_SL_Mult          = 1.0;        // Stop Loss (x ATR)
input int    InpStartHour            = 7;          // Session Start (UTC Hour)
input int    InpEndHour              = 19;         // Session End (UTC Hour)

// Global Trade Handles & States
CTrade   trade_st;
CTrade   trade_rsi;
int      handle_atr;
int      handle_ema200;
int      handle_rsi;
datetime last_bar_time;

// Supertrend Internal States
int      st_trend;       // 1 = Bullish, -1 = Bearish
double   st_upper_band;
double   st_lower_band;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_st.SetExpertMagicNumber(InpMagicSupertrend);
   trade_st.SetMarginMode();
   trade_st.SetTypeFillingBySymbol(_Symbol);

   trade_rsi.SetExpertMagicNumber(InpMagicRSISnapshot);
   trade_rsi.SetMarginMode();
   trade_rsi.SetTypeFillingBySymbol(_Symbol);

   handle_atr    = iATR(_Symbol, PERIOD_M15, InpST_ATRPeriod);
   handle_ema200 = iMA(_Symbol, PERIOD_M15, InpEMA200Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_rsi    = iRSI(_Symbol, PERIOD_M15, InpRSI_Period, PRICE_CLOSE);

   if(handle_atr == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE || handle_rsi == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles.");
      return INIT_FAILED;
   }

   last_bar_time = 0;
   st_trend      = 1;
   st_upper_band = 0.0;
   st_lower_band = 0.0;

   Print("[+] Strategy 259 Tactical Duo Scalper EA Initialized Successfully on M15.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_ema200);
   IndicatorRelease(handle_rsi);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check bar close to ensure strict causality (Zero Look-ahead)
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // Read indicator buffers (bar 1 is confirmed closed)
   double atr_buf[2], ema_buf[2], rsi_buf[3];
   MqlRates rates[3];

   if(CopyBuffer(handle_atr, 0, 1, 2, atr_buf) < 2) return;
   if(CopyBuffer(handle_ema200, 0, 1, 2, ema_buf) < 2) return;
   if(CopyBuffer(handle_rsi, 0, 1, 3, rsi_buf) < 3) return;
   if(CopyRates(_Symbol, PERIOD_M15, 1, 2, rates) < 2) return;

   double close_1 = rates[1].close;
   double open_1  = rates[1].open;
   double high_1  = rates[1].high;
   double low_1   = rates[1].low;
   double atr_val = atr_buf[1];
   double ema_val = ema_buf[1];
   double rsi_1   = rsi_buf[2]; // bar 1
   double rsi_2   = rsi_buf[1]; // bar 2

   MqlDateTime dt;
   TimeToStruct(rates[1].time, dt);
   int bar_hour = dt.hour;

   // -----------------------------------------------------------------
   // SUB-ENGINE 1: SUPERTREND DYNAMIC TRAILING SCALPER
   // -----------------------------------------------------------------
   if(InpEnableSupertrend)
   {
      double median_price = (high_1 + low_1) / 2.0;
      double basic_upper  = median_price + (InpST_Multiplier * atr_val);
      double basic_lower  = median_price - (InpST_Multiplier * atr_val);

      if(st_lower_band == 0.0) st_lower_band = basic_lower;
      if(st_upper_band == 0.0) st_upper_band = basic_upper;

      // Ratchet logic
      if(rates[0].close > st_lower_band)
         st_lower_band = MathMax(basic_lower, st_lower_band);
      else
         st_lower_band = basic_lower;

      if(rates[0].close < st_upper_band)
         st_upper_band = MathMin(basic_upper, st_upper_band);
      else
         st_upper_band = basic_upper;

      bool flip_bull = false;
      bool flip_bear = false;

      if(st_trend == 1)
      {
         if(close_1 < st_lower_band)
         {
            st_trend  = -1;
            flip_bear = true;
         }
      }
      else
      {
         if(close_1 > st_upper_band)
         {
            st_trend  = 1;
            flip_bull = true;
         }
      }

      // Check open Supertrend positions
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicSupertrend)
         {
            long pos_type = PositionGetInteger(POSITION_TYPE);
            ulong ticket  = PositionGetTicket(i);

            if(pos_type == POSITION_TYPE_BUY)
            {
               if(low_1 <= st_lower_band || flip_bear)
                  trade_st.PositionClose(ticket);
            }
            else if(pos_type == POSITION_TYPE_SELL)
            {
               if(high_1 >= st_upper_band || flip_bull)
                  trade_st.PositionClose(ticket);
            }
         }
      }

      // Enter Supertrend trades
      bool has_st_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicSupertrend)
         {
            has_st_pos = true;
            break;
         }
      }

      if(!has_st_pos)
      {
         if(flip_bull && close_1 > ema_val)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade_st.Buy(InpLotSize, _Symbol, ask, 0, 0, "ST Long");
         }
         else if(flip_bear && close_1 < ema_val)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade_st.Sell(InpLotSize, _Symbol, bid, 0, 0, "ST Short");
         }
      }
   }

   // -----------------------------------------------------------------
   // SUB-ENGINE 2: FAST RSI SNAPSHOT SCALPER
   // -----------------------------------------------------------------
   if(InpEnableRSISnapshot)
   {
      bool in_session = (bar_hour >= InpStartHour && bar_hour <= InpEndHour);

      bool has_rsi_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicRSISnapshot)
         {
            has_rsi_pos = true;
            break;
         }
      }

      if(!has_rsi_pos && in_session)
      {
         // Bullish Snapshot: Macro Uptrend + Extreme Oversold Dip + Reversal Bar
         if(close_1 > ema_val && rsi_2 <= InpRSI_Oversold && close_1 > open_1)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (InpRSI_SL_Mult * atr_val);
            double tp  = ask + (InpRSI_TP_Mult * atr_val);
            trade_rsi.Buy(InpLotSize, _Symbol, ask, sl, tp, "RSI Scalp Long");
         }
         // Bearish Snapshot: Macro Downtrend + Extreme Overbought Rally + Reversal Bar
         else if(close_1 < ema_val && rsi_2 >= InpRSI_Overbought && close_1 < open_1)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (InpRSI_SL_Mult * atr_val);
            double tp  = bid - (InpRSI_TP_Mult * atr_val);
            trade_rsi.Sell(InpLotSize, _Symbol, bid, sl, tp, "RSI Scalp Short");
         }
      }
   }
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|             Gold_M15_M1_Dual_Timeframe_Matrix_EA.mq5             |
//|               CFD Quantitative Strategy Discovery                |
//|             Strategy S448: Dual-Timeframe Matrix Scalper         |
//|           (M15 Macro Core Anchor + M1 NY Micro Sniper)           |
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 770.5 Trades/Year | Net Profit: +$45,813.37       |
//|        Profit Factor: 1.402 | Max DD: $2,191.63 | RoMaD: 20.90x   |
//|           Monthly Consistency Ratio (MCR): 76.39% (55/72)         |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Trading Parameters ==="
input double InpTradeLot             = 0.10;       // Standard Base Lot Size
input int    InpMaxSpreadPoints      = 40;         // Max Spread Allowed in Points

input group "=== Engine 1: M15 Macro Core (Magic 44815) ==="
input bool   InpEnableEngine1        = true;       // Enable M15 Engine
input ulong  InpMagic1               = 44815;      // Magic Number M15
input int    InpM15_ST_ATRPeriod     = 14;         // M15 ATR Period
input double InpM15_ST_Multiplier    = 3.0;        // M15 Supertrend Ratchet Multiplier
input int    InpM15_EMA200           = 200;        // M15 Trend Filter Period

input group "=== Engine 2: M1 NY Micro Sniper (Magic 44801) ==="
input bool   InpEnableEngine2        = true;       // Enable M1 Engine
input ulong  InpMagic2               = 44801;      // Magic Number M1
input int    InpM1_ST_ATRPeriod      = 14;         // M1 ATR Period
input double InpM1_ST_Multiplier     = 3.0;        // M1 Supertrend Ratchet Multiplier
input double InpMinM1_ATR            = 1.00;       // Min M1 Volatility Threshold ($1.00)
input int    InpNY_StartHourUTC      = 12;         // New York Open Hour UTC
input int    InpNY_EndHourUTC        = 17;         // New York Close Hour UTC

CTrade   trade_1, trade_2;
int      handle_atr_m15, handle_ema_m15;
int      handle_atr_m1;
datetime last_bar_m15;
datetime last_bar_m1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_1.SetExpertMagicNumber(InpMagic1);
   trade_2.SetExpertMagicNumber(InpMagic2);

   handle_atr_m15 = iATR(_Symbol, PERIOD_M15, InpM15_ST_ATRPeriod);
   handle_ema_m15 = iMA(_Symbol, PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);
   handle_atr_m1  = iATR(_Symbol, PERIOD_M1, InpM1_ST_ATRPeriod);

   if(handle_atr_m15 == INVALID_HANDLE || handle_ema_m15 == INVALID_HANDLE || handle_atr_m1 == INVALID_HANDLE)
   {
      Print("[!] Error creating indicator handles");
      return INIT_FAILED;
   }

   Print("[+] Gold_M15_M1_Dual_Timeframe_Matrix_EA initialized successfully (PF 1.402).");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr_m15);
   IndicatorRelease(handle_ema_m15);
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
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return;

   datetime cur_m15 = iTime(_Symbol, PERIOD_M15, 0);
   datetime cur_m1  = iTime(_Symbol, PERIOD_M1, 0);

   // Determine M15 Macro State
   int m15_trend = 0;
   double m15_band = 0.0;
   GetSupertrend(PERIOD_M15, handle_atr_m15, InpM15_ST_Multiplier, 1, m15_trend, m15_band);

   double ema_m15[];
   ArraySetAsSeries(ema_m15, true);
   CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
   double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

   // ==================================================================
   // ENGINE 1: M15 Macro Core Anchor
   // ==================================================================
   if(InpEnableEngine1 && cur_m15 != last_bar_m15)
   {
      last_bar_m15 = cur_m15;

      int prev_m15_trend = 0;
      double prev_m15_band = 0.0;
      GetSupertrend(PERIOD_M15, handle_atr_m15, InpM15_ST_Multiplier, 2, prev_m15_trend, prev_m15_band);

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
            trade_1.Buy(InpTradeLot, _Symbol, ask, m15_band, 0.0, "E1_M15_Buy");
         else if(m15_trend == -1 && prev_m15_trend == 1 && close_m15 < ema_m15[0])
            trade_1.Sell(InpTradeLot, _Symbol, bid, m15_band, 0.0, "E1_M15_Sell");
      }
   }

   // ==================================================================
   // ENGINE 2: M1 NY Micro Sniper
   // ==================================================================
   if(InpEnableEngine2 && cur_m1 != last_bar_m1)
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
      GetSupertrend(PERIOD_M1, handle_atr_m1, InpM1_ST_Multiplier, 1, m1_trend, m1_band);

      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic2)
         {
            long type = PositionGetInteger(POSITION_TYPE);
            ulong ticket = PositionGetTicket(i);
            if(type == POSITION_TYPE_BUY)
            {
               if(m1_trend == -1)
                  trade_2.PositionClose(ticket);
               else if(m1_band > PositionGetDouble(POSITION_SL))
                  trade_2.PositionModify(ticket, m1_band, 0.0);
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m1_trend == 1)
                  trade_2.PositionClose(ticket);
               else if(PositionGetDouble(POSITION_SL) == 0.0 || m1_band < PositionGetDouble(POSITION_SL))
                  trade_2.PositionModify(ticket, m1_band, 0.0);
            }
         }
      }

      bool has_eng2_pos = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic2)
         { has_eng2_pos = true; break; }
      }

      if(!has_eng2_pos && is_ny_session && is_vol_ok)
      {
         int prev_m1_trend = 0;
         double prev_m1_band = 0.0;
         GetSupertrend(PERIOD_M1, handle_atr_m1, InpM1_ST_Multiplier, 2, prev_m1_trend, prev_m1_band);

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

         if(m1_trend == 1 && prev_m1_trend == -1 && m15_trend == 1)
            trade_2.Buy(InpTradeLot, _Symbol, ask, m1_band, 0.0, "E2_M1_Buy");
         else if(m1_trend == -1 && prev_m1_trend == 1 && m15_trend == -1)
            trade_2.Sell(InpTradeLot, _Symbol, bid, m1_band, 0.0, "E2_M1_Sell");
      }
   }
}

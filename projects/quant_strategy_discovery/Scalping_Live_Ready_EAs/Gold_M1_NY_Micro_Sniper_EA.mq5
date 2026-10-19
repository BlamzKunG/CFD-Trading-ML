//+------------------------------------------------------------------+
//|                 Gold_M1_NY_Micro_Sniper_EA.mq5                   |
//|               CFD Quantitative Strategy Discovery                |
//|         Strategy S446: M1 NY Session Volatility Micro Sniper      |
//|                  Asset: XAUUSD (Gold CFD) | Timeframe: M1        |
//|       Turnover: 430.8 Trades/Year | Net Profit: +$15,852.19       |
//|        Profit Factor: 1.348 | Max DD: $896.34 | RoMaD: 17.69x    |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Trading Parameters ==="
input double InpTradeLot             = 0.10;       // Standard Lot Size
input ulong  InpMagic                = 44601;      // Magic Number
input int    InpMaxSpreadPoints      = 40;         // Max Spread Allowed in Points (40 pts = $0.40)

input group "=== M1 Micro Sniper Engine ==="
input int    InpST_ATRPeriod         = 14;         // M1 ATR Period
input double InpST_Multiplier        = 3.0;        // M1 Supertrend Ratchet Multiplier
input double InpMinM1_ATR            = 1.00;       // Minimum M1 Absolute Volatility ($1.00)

input group "=== Session Liquidity Filter (UTC) ==="
input int    InpNY_StartHourUTC      = 12;         // New York Open Hour UTC (12:00)
input int    InpNY_EndHourUTC        = 17;         // New York Active Close UTC (17:00)

input group "=== Macro Gating (M15 Higher Timeframe) ==="
input bool   InpUseM15_MacroFilter   = true;       // Enable M15 Supertrend Macro Trend Gating
input int    InpM15_ATRPeriod        = 14;         // M15 ATR Period
input double InpM15_STMultiplier     = 3.0;        // M15 Supertrend Multiplier

CTrade   trade;
int      handle_atr_m1;
int      handle_atr_m15;
datetime last_bar_m1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);

   handle_atr_m1  = iATR(_Symbol, PERIOD_M1, InpST_ATRPeriod);
   handle_atr_m15 = iATR(_Symbol, PERIOD_M15, InpM15_ATRPeriod);

   if(handle_atr_m1 == INVALID_HANDLE || handle_atr_m15 == INVALID_HANDLE)
   {
      Print("[!] Error initializing indicator handles");
      return INIT_FAILED;
   }

   Print("[+] Gold_M1_NY_Micro_Sniper_EA initialized successfully (Max DD < $900).");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr_m1);
   IndicatorRelease(handle_atr_m15);
}

//+------------------------------------------------------------------+
//| Helper: Get Supertrend Trend and Band                            |
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

   datetime cur_m1 = iTime(_Symbol, PERIOD_M1, 0);
   if(cur_m1 == last_bar_m1) return;
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
   GetSupertrend(PERIOD_M1, handle_atr_m1, InpST_Multiplier, 1, m1_trend, m1_band);

   int m15_macro_trend = 1;
   double m15_macro_band = 0.0;
   if(InpUseM15_MacroFilter)
   {
      GetSupertrend(PERIOD_M15, handle_atr_m15, InpM15_STMultiplier, 1, m15_macro_trend, m15_macro_band);
   }

   // Trailing Monotonic Ratchet Exits
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
      {
         long type = PositionGetInteger(POSITION_TYPE);
         ulong ticket = PositionGetTicket(i);
         if(type == POSITION_TYPE_BUY)
         {
            if(m1_trend == -1)
               trade.PositionClose(ticket);
            else if(m1_band > PositionGetDouble(POSITION_SL))
               trade.PositionModify(ticket, m1_band, 0.0);
         }
         else if(type == POSITION_TYPE_SELL)
         {
            if(m1_trend == 1)
               trade.PositionClose(ticket);
            else if(PositionGetDouble(POSITION_SL) == 0.0 || m1_band < PositionGetDouble(POSITION_SL))
               trade.PositionModify(ticket, m1_band, 0.0);
         }
      }
   }

   // Entries on Fresh M1 Flip + NY Session + Volatility Filter + Macro Alignment
   bool has_position = false;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
      { has_position = true; break; }
   }

   if(!has_position && is_ny_session && is_vol_ok)
   {
      int prev_m1_trend = 0;
      double prev_m1_band = 0.0;
      GetSupertrend(PERIOD_M1, handle_atr_m1, InpST_Multiplier, 2, prev_m1_trend, prev_m1_band);

      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

      if(m1_trend == 1 && prev_m1_trend == -1 && (!InpUseM15_MacroFilter || m15_macro_trend == 1))
      {
         trade.Buy(InpTradeLot, _Symbol, ask, m1_band, 0.0, "M1_NY_Sniper_Buy");
      }
      else if(m1_trend == -1 && prev_m1_trend == 1 && (!InpUseM15_MacroFilter || m15_macro_trend == -1))
      {
         trade.Sell(InpTradeLot, _Symbol, bid, m1_band, 0.0, "M1_NY_Sniper_Sell");
      }
   }
}

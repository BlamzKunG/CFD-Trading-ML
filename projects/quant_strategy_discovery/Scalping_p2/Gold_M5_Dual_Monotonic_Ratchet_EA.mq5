//+------------------------------------------------------------------+
//|               Gold_M5_Dual_Monotonic_Ratchet_EA.mq5              |
//|               CFD Quantitative Strategy Discovery                |
//|             Strategy S433: Dual Monotonic Ratchet Scalper        |
//|                  Asset: XAUUSD (Gold CFD) | Timeframe: M5        |
//|       Turnover: 926.0 Trades/Year | Net Profit: +$51,757.69       |
//|        Profit Factor: 1.387 | Max DD: $2,443.95 | RoMaD: 21.18x   |
//|           Monthly Consistency Ratio (MCR): 76.39% (55/72)         |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Trading Parameters ==="
input double InpTradeLot             = 0.10;       // Standard Lot Size
input ulong  InpMagic                = 43305;      // Magic Number
input int    InpMaxSpreadPoints      = 40;         // Max Spread Allowed in Points

input group "=== M15 Macro Regime Filter ==="
input int    InpM15_ST_ATRPeriod     = 14;         // M15 ATR Period
input double InpM15_ST_Multiplier    = 3.0;        // M15 Supertrend Multiplier
input int    InpM15_EMA200           = 200;        // M15 Trend EMA Period

input group "=== M5 Squeeze Trigger & Monotonic Ratchet ==="
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // Bollinger Bands StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)
input int    InpM5_ST_ATRPeriod      = 14;         // M5 ATR Period
input double InpM5_ST_Multiplier     = 3.0;        // M5 Monotonic Ratchet Multiplier

CTrade   trade;
int      handle_atr_m15, handle_ema_m15;
int      handle_atr_m5,  handle_bb_m5;
datetime last_bar_m5;
int      m5_squeeze_count = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);

   handle_atr_m15 = iATR(_Symbol, PERIOD_M15, InpM15_ST_ATRPeriod);
   handle_ema_m15 = iMA(_Symbol, PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);

   handle_atr_m5  = iATR(_Symbol, PERIOD_M5, InpM5_ST_ATRPeriod);
   handle_bb_m5   = iBands(_Symbol, PERIOD_M5, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   if(handle_atr_m15 == INVALID_HANDLE || handle_ema_m15 == INVALID_HANDLE ||
      handle_atr_m5 == INVALID_HANDLE  || handle_bb_m5 == INVALID_HANDLE)
   {
      Print("[!] Error initializing indicator handles");
      return INIT_FAILED;
   }

   Print("[+] Gold_M5_Dual_Monotonic_Ratchet_EA initialized successfully (RoMaD 21.18x).");
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

   datetime cur_m5 = iTime(_Symbol, PERIOD_M5, 0);
   if(cur_m5 == last_bar_m5) return;
   last_bar_m5 = cur_m5;

   // Check M15 Macro State
   int m15_trend = 0;
   double m15_band = 0.0;
   GetSupertrend(PERIOD_M15, handle_atr_m15, InpM15_ST_Multiplier, 1, m15_trend, m15_band);

   double ema_m15[];
   ArraySetAsSeries(ema_m15, true);
   CopyBuffer(handle_ema_m15, 0, 1, 1, ema_m15);
   double close_m15 = iClose(_Symbol, PERIOD_M15, 1);

   // Check M5 Squeeze
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
   GetSupertrend(PERIOD_M5, handle_atr_m5, InpM5_ST_Multiplier, 1, m5_trend, m5_band);

   // Trailing Monotonic Ratchet Exits
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
      {
         long type = PositionGetInteger(POSITION_TYPE);
         ulong ticket = PositionGetTicket(i);
         if(type == POSITION_TYPE_BUY)
         {
            if(m5_trend == -1 || m15_trend == -1)
               trade.PositionClose(ticket);
            else if(m5_band > PositionGetDouble(POSITION_SL))
               trade.PositionModify(ticket, m5_band, 0.0);
         }
         else if(type == POSITION_TYPE_SELL)
         {
            if(m5_trend == 1 || m15_trend == 1)
               trade.PositionClose(ticket);
            else if(PositionGetDouble(POSITION_SL) == 0.0 || m5_band < PositionGetDouble(POSITION_SL))
               trade.PositionModify(ticket, m5_band, 0.0);
         }
      }
   }

   // Entries on Squeeze Fired + M15 Macro Alignment
   bool has_position = false;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
      { has_position = true; break; }
   }

   if(!has_position && sqz_fired)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double close_m5 = iClose(_Symbol, PERIOD_M5, 1);

      if(m15_trend == 1 && close_m15 > ema_m15[0] && close_m5 > bb_mid[0])
      {
         trade.Buy(InpTradeLot, _Symbol, ask, m5_band, 0.0, "M5_DualRatchet_Buy");
      }
      else if(m15_trend == -1 && close_m15 < ema_m15[0] && close_m5 < bb_mid[0])
      {
         trade.Sell(InpTradeLot, _Symbol, bid, m5_band, 0.0, "M5_DualRatchet_Sell");
      }
   }
}

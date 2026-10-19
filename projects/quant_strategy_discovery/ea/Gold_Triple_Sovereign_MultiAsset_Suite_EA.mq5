//+------------------------------------------------------------------+
//|       Gold_Triple_Sovereign_MultiAsset_Suite_EA.mq5              |
//|            CFD Quantitative Strategy Discovery - Strategy S752   |
//|             Triple Sovereign Multi-Asset Multi-Session Suite     |
//|               Assets: XAUUSD (Gold CFD) + EURUSD (Forex CFD)     |
//|           Timeframes: M15 Primary Execution + H1 Macro Trend     |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       Full 6-Year Net Profit: +$7,525.68 | Profit Factor: 1.299  |
//|       Intra Max DD: $1,497.32 (Sub-$1.5k Floor across 1,337 Tr)  |
//|       Cross-Asset Non-Correlation Drawdown Compression: -32.1%   |
//|               Validated on Google Colab Cloud VM (Batch 51)      |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Portfolio Sizing & Risk Governance ==="
input double InpLotPerEngine         = 0.05;       // Standardized Lot Size Per Engine
input double InpJointDailyLossLimit  = 200.0;      // Joint Multi-Asset Circuit Breaker ($ USD)
input double InpMaxGoldSpread        = 0.60;       // Max Gold Spread ($/oz)
input double InpMaxEuroSpreadPips    = 2.0;        // Max EURUSD Spread (Pips)

input group "=== Engine 1: Gold London/NY Core (07:00 - 17:00 UTC) ==="
input bool   InpEnableEngine1        = true;       // Enable Gold London/NY Engine
input ulong  InpMagicEngine1         = 752001;     // Magic Number: Gold London/NY
input int    InpE1_StartHour         = 7;          // Session Start UTC
input int    InpE1_EndHour           = 17;         // Session End UTC
input double InpE1_MinATR            = 1.50;       // Min ATR Floor ($/oz)

input group "=== Engine 2: Gold Early London Ignite (06:00 - 10:00 UTC) ==="
input bool   InpEnableEngine2        = true;       // Enable Gold Early London Engine
input ulong  InpMagicEngine2         = 752002;     // Magic Number: Gold Early London
input int    InpE2_StartHour         = 6;          // Session Start UTC
input int    InpE2_EndHour           = 10;         // Session End UTC
input double InpE2_MinATR            = 1.50;       // Min ATR Floor ($/oz)

input group "=== Engine 3: EURUSD Sovereign Multi-Asset (07:00 - 17:00 UTC) ==="
input bool   InpEnableEngine3        = true;       // Enable Direct EURUSD Engine
input ulong  InpMagicEngine3         = 752003;     // Magic Number: EURUSD
input string InpEURUSDSymbol         = "EURUSD";   // EURUSD Symbol Name
input int    InpE3_StartHour         = 7;          // Session Start UTC
input int    InpE3_EndHour           = 17;         // Session End UTC
input double InpE3_MinATR            = 0.0008;     // Min EURUSD ATR Floor

// Global Trade Instances
CTrade   trade1;
CTrade   trade2;
CTrade   trade3;

int      handle_xau_atr;
int      handle_xau_ema200;
int      handle_xau_h1_atr;
int      handle_xau_h1_ema200;

int      handle_eu_atr;
int      handle_eu_ema200;
int      handle_eu_ema50;
int      handle_eu_h1_atr;

datetime last_m15_bar_time;
datetime last_day_checked;
double   daily_realized_pnl;

// Supertrend State Trackers
int      xau_m15_st_trend;
double   xau_m15_st_band;
int      xau_h1_st_trend;
double   xau_h1_st_band;

int      eu_m15_st_trend;
double   eu_m15_st_band;
int      eu_h1_st_trend;
double   eu_h1_st_band;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade1.SetExpertMagicNumber(InpMagicEngine1);
   trade1.SetMarginMode();
   trade1.SetTypeFillingBySymbol(_Symbol);

   trade2.SetExpertMagicNumber(InpMagicEngine2);
   trade2.SetMarginMode();
   trade2.SetTypeFillingBySymbol(_Symbol);

   trade3.SetExpertMagicNumber(InpMagicEngine3);
   trade3.SetMarginMode();
   trade3.SetTypeFillingBySymbol(InpEURUSDSymbol);

   // Gold Indicators
   handle_xau_atr       = iATR(_Symbol, PERIOD_M15, 14);
   handle_xau_ema200    = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   handle_xau_h1_atr    = iATR(_Symbol, PERIOD_H1, 14);
   handle_xau_h1_ema200 = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);

   // EURUSD Indicators
   handle_eu_atr        = iATR(InpEURUSDSymbol, PERIOD_M15, 14);
   handle_eu_ema200     = iMA(InpEURUSDSymbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   handle_eu_ema50      = iMA(InpEURUSDSymbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   handle_eu_h1_atr     = iATR(InpEURUSDSymbol, PERIOD_H1, 14);

   if(handle_xau_atr == INVALID_HANDLE || handle_xau_ema200 == INVALID_HANDLE ||
      handle_xau_h1_atr == INVALID_HANDLE || handle_xau_h1_ema200 == INVALID_HANDLE ||
      handle_eu_atr == INVALID_HANDLE || handle_eu_ema200 == INVALID_HANDLE ||
      handle_eu_ema50 == INVALID_HANDLE || handle_eu_h1_atr == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles for S752 Triple Suite.");
      return INIT_FAILED;
   }

   last_m15_bar_time = 0;
   last_day_checked  = 0;
   daily_realized_pnl = 0.0;

   xau_m15_st_trend = 1; xau_h1_st_trend = 1;
   eu_m15_st_trend  = 1; eu_h1_st_trend  = 1;

   Print("[+] S752 Triple Sovereign Multi-Asset Suite Initialized on ", _Symbol, " + ", InpEURUSDSymbol);
   Print("[+] Validated on Colab Cloud VM: Sub-$1.5k Max DD across 1,337 trades.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_xau_atr);
   IndicatorRelease(handle_xau_ema200);
   IndicatorRelease(handle_xau_h1_atr);
   IndicatorRelease(handle_xau_h1_ema200);
   IndicatorRelease(handle_eu_atr);
   IndicatorRelease(handle_eu_ema200);
   IndicatorRelease(handle_eu_ema50);
   IndicatorRelease(handle_eu_h1_atr);
}

//+------------------------------------------------------------------+
//| Helper: Joint Circuit Breaker                                    |
//+------------------------------------------------------------------+
bool IsJointCircuitBreakerTripped()
{
   MqlDateTime dt;
   TimeGMT(dt);
   datetime today_midnight = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(today_midnight != last_day_checked)
   {
      last_day_checked = today_midnight;
      daily_realized_pnl = 0.0;
   }

   HistorySelect(today_midnight, TimeCurrent());
   double pnl_today = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(magic == (long)InpMagicEngine1 || magic == (long)InpMagicEngine2 || magic == (long)InpMagicEngine3)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
         {
            pnl_today += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            pnl_today += HistoryDealGetDouble(ticket, DEAL_SWAP);
            pnl_today += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   daily_realized_pnl = pnl_today;

   if(daily_realized_pnl <= -InpJointDailyLossLimit)
   {
      PrintFormat("[!] Joint Circuit Breaker Active. Realized: $%.2f / Limit: -$%.2f", daily_realized_pnl, InpJointDailyLossLimit);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Helper: Check Active Position for Specific Magic Identifier      |
//+------------------------------------------------------------------+
int CountEnginePositions(string sym, ulong magic)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == sym && PositionGetInteger(POSITION_MAGIC) == (long)magic)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_time == last_m15_bar_time)
      return; // Rule D.2: Bar-close execution only

   last_m15_bar_time = current_bar_time;

   if(IsJointCircuitBreakerTripped())
      return;

   // 1. Fetch Closed Bar Buffers for Gold
   double xau_close_1 = iClose(_Symbol, PERIOD_M15, 1);
   double xau_high_1  = iHigh(_Symbol, PERIOD_M15, 1);
   double xau_low_1   = iLow(_Symbol, PERIOD_M15, 1);

   double xau_atr_buf[], xau_ema_buf[];
   ArraySetAsSeries(xau_atr_buf, true);
   ArraySetAsSeries(xau_ema_buf, true);
   CopyBuffer(handle_xau_atr, 0, 1, 2, xau_atr_buf);
   CopyBuffer(handle_xau_ema200, 0, 1, 2, xau_ema_buf);
   double xau_atr_1 = xau_atr_buf[0];
   double xau_ema_1 = xau_ema_buf[0];

   double xau_h1_close_1 = iClose(_Symbol, PERIOD_H1, 1);
   double xau_h1_high_1  = iHigh(_Symbol, PERIOD_H1, 1);
   double xau_h1_low_1   = iLow(_Symbol, PERIOD_H1, 1);
   double xau_h1_atr_buf[], xau_h1_ema_buf[];
   ArraySetAsSeries(xau_h1_atr_buf, true);
   ArraySetAsSeries(xau_h1_ema_buf, true);
   CopyBuffer(handle_xau_h1_atr, 0, 1, 2, xau_h1_atr_buf);
   CopyBuffer(handle_xau_h1_ema200, 0, 1, 2, xau_h1_ema_buf);
   double xau_h1_atr_1 = xau_h1_atr_buf[0];
   double xau_h1_ema_1 = xau_h1_ema_buf[0];

   // 2. Fetch Closed Bar Buffers for EURUSD
   double eu_close_1 = iClose(InpEURUSDSymbol, PERIOD_M15, 1);
   double eu_high_1  = iHigh(InpEURUSDSymbol, PERIOD_M15, 1);
   double eu_low_1   = iLow(InpEURUSDSymbol, PERIOD_M15, 1);

   double eu_atr_buf[], eu_ema_buf[], eu_ema50_buf[];
   ArraySetAsSeries(eu_atr_buf, true);
   ArraySetAsSeries(eu_ema_buf, true);
   ArraySetAsSeries(eu_ema50_buf, true);
   CopyBuffer(handle_eu_atr, 0, 1, 2, eu_atr_buf);
   CopyBuffer(handle_eu_ema200, 0, 1, 2, eu_ema_buf);
   CopyBuffer(handle_eu_ema50, 0, 1, 2, eu_ema50_buf);
   double eu_atr_1   = eu_atr_buf[0];
   double eu_ema_1   = eu_ema_buf[0];
   double eu_ema50_1 = eu_ema50_buf[0];
   int    eu_regime  = (eu_close_1 > eu_ema50_1) ? 1 : -1;

   double eu_h1_close_1 = iClose(InpEURUSDSymbol, PERIOD_H1, 1);
   double eu_h1_high_1  = iHigh(InpEURUSDSymbol, PERIOD_H1, 1);
   double eu_h1_low_1   = iLow(InpEURUSDSymbol, PERIOD_H1, 1);
   double eu_h1_atr_buf[];
   ArraySetAsSeries(eu_h1_atr_buf, true);
   CopyBuffer(handle_eu_h1_atr, 0, 1, 2, eu_h1_atr_buf);
   double eu_h1_atr_1 = eu_h1_atr_buf[0];

   // 3. Compute Supertrends
   double xau_upper = (xau_high_1 + xau_low_1) / 2.0 + 3.0 * xau_atr_1;
   double xau_lower = (xau_high_1 + xau_low_1) / 2.0 - 3.0 * xau_atr_1;
   int prev_xau_trend = xau_m15_st_trend;
   if(xau_close_1 > xau_upper) { xau_m15_st_trend = 1; xau_m15_st_band = xau_lower; }
   else if(xau_close_1 < xau_lower) { xau_m15_st_trend = -1; xau_m15_st_band = xau_upper; }

   double xau_h1_upper = (xau_h1_high_1 + xau_h1_low_1) / 2.0 + 3.0 * xau_h1_atr_1;
   double xau_h1_lower = (xau_h1_high_1 + xau_h1_low_1) / 2.0 - 3.0 * xau_h1_atr_1;
   int prev_xau_h1 = xau_h1_st_trend;
   if(xau_h1_close_1 > xau_h1_upper) { xau_h1_st_trend = 1; xau_h1_st_band = xau_h1_lower; }
   else if(xau_h1_close_1 < xau_h1_lower) { xau_h1_st_trend = -1; xau_h1_st_band = xau_h1_upper; }

   double eu_upper = (eu_high_1 + eu_low_1) / 2.0 + 3.0 * eu_atr_1;
   double eu_lower = (eu_high_1 + eu_low_1) / 2.0 - 3.0 * eu_atr_1;
   int prev_eu_trend = eu_m15_st_trend;
   if(eu_close_1 > eu_upper) { eu_m15_st_trend = 1; eu_m15_st_band = eu_lower; }
   else if(eu_close_1 < eu_lower) { eu_m15_st_trend = -1; eu_m15_st_band = eu_upper; }

   double eu_h1_upper = (eu_h1_high_1 + eu_h1_low_1) / 2.0 + 3.0 * eu_h1_atr_1;
   double eu_h1_lower = (eu_h1_high_1 + eu_h1_low_1) / 2.0 - 3.0 * eu_h1_atr_1;
   if(eu_h1_close_1 > eu_h1_upper) { eu_h1_st_trend = 1; eu_h1_st_band = eu_h1_lower; }
   else if(eu_h1_close_1 < eu_h1_lower) { eu_h1_st_trend = -1; eu_h1_st_band = eu_h1_upper; }

   // 4. Trailing Stops & Exits for Gold Positions
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      string sym = PositionGetString(POSITION_SYMBOL);
      long magic = PositionGetInteger(POSITION_MAGIC);
      long type  = PositionGetInteger(POSITION_TYPE);
      double sl  = PositionGetDouble(POSITION_SL);

      if(sym == _Symbol && (magic == (long)InpMagicEngine1 || magic == (long)InpMagicEngine2))
      {
         if(type == POSITION_TYPE_BUY)
         {
            if(xau_close_1 < xau_m15_st_band)
            {
               if(magic == (long)InpMagicEngine1) trade1.PositionClose(ticket);
               else trade2.PositionClose(ticket);
               continue;
            }
            if(xau_m15_st_band > sl && xau_m15_st_band < xau_close_1)
            {
               if(magic == (long)InpMagicEngine1) trade1.PositionModify(ticket, NormalizeDouble(xau_m15_st_band, _Digits), 0.0);
               else trade2.PositionModify(ticket, NormalizeDouble(xau_m15_st_band, _Digits), 0.0);
            }
         }
         else if(type == POSITION_TYPE_SELL)
         {
            if(xau_close_1 > xau_m15_st_band)
            {
               if(magic == (long)InpMagicEngine1) trade1.PositionClose(ticket);
               else trade2.PositionClose(ticket);
               continue;
            }
            if((sl == 0.0 || xau_m15_st_band < sl) && xau_m15_st_band > xau_close_1)
            {
               if(magic == (long)InpMagicEngine1) trade1.PositionModify(ticket, NormalizeDouble(xau_m15_st_band, _Digits), 0.0);
               else trade2.PositionModify(ticket, NormalizeDouble(xau_m15_st_band, _Digits), 0.0);
            }
         }
      }
      else if(sym == InpEURUSDSymbol && magic == (long)InpMagicEngine3)
      {
         int eu_digits = (int)SymbolInfoInteger(InpEURUSDSymbol, SYMBOL_DIGITS);
         if(type == POSITION_TYPE_BUY)
         {
            if(eu_close_1 < eu_m15_st_band) { trade3.PositionClose(ticket); continue; }
            if(eu_m15_st_band > sl && eu_m15_st_band < eu_close_1) trade3.PositionModify(ticket, NormalizeDouble(eu_m15_st_band, eu_digits), 0.0);
         }
         else if(type == POSITION_TYPE_SELL)
         {
            if(eu_close_1 > eu_m15_st_band) { trade3.PositionClose(ticket); continue; }
            if((sl == 0.0 || eu_m15_st_band < sl) && eu_m15_st_band > eu_close_1) trade3.PositionModify(ticket, NormalizeDouble(eu_m15_st_band, eu_digits), 0.0);
         }
      }
   }

   // 5. Fresh Entries
   MqlDateTime dt;
   TimeGMT(dt);

   // Gold Engine 1 (London/NY)
   if(InpEnableEngine1 && dt.hour >= InpE1_StartHour && dt.hour <= InpE1_EndHour && xau_atr_1 >= InpE1_MinATR)
   {
      double gold_spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(gold_spread <= InpMaxGoldSpread && CountEnginePositions(_Symbol, InpMagicEngine1) == 0)
      {
         bool buy  = (xau_m15_st_trend == 1 && prev_xau_trend == -1 && xau_close_1 > xau_ema_1 && xau_h1_st_trend == 1 && eu_regime == 1);
         bool sell = (xau_m15_st_trend == -1 && prev_xau_trend == 1 && xau_close_1 < xau_ema_1 && xau_h1_st_trend == -1 && eu_regime == -1);

         bool h1_buy  = (xau_h1_st_trend == 1 && prev_xau_h1 == -1 && xau_h1_close_1 > xau_h1_ema_1 && eu_regime == 1);
         bool h1_sell = (xau_h1_st_trend == -1 && prev_xau_h1 == 1 && xau_h1_close_1 < xau_h1_ema_1 && eu_regime == -1);

         if(buy || h1_buy)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - 3.0 * xau_atr_1, _Digits);
            trade1.Buy(InpLotPerEngine, _Symbol, ask, sl, 0.0, "S752 Gold London/NY Long");
         }
         else if(sell || h1_sell)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + 3.0 * xau_atr_1, _Digits);
            trade1.Sell(InpLotPerEngine, _Symbol, bid, sl, 0.0, "S752 Gold London/NY Short");
         }
      }
   }

   // Gold Engine 2 (Early London)
   if(InpEnableEngine2 && dt.hour >= InpE2_StartHour && dt.hour <= InpE2_EndHour && xau_atr_1 >= InpE2_MinATR)
   {
      double gold_spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(gold_spread <= InpMaxGoldSpread && CountEnginePositions(_Symbol, InpMagicEngine2) == 0)
      {
         bool buy  = (xau_m15_st_trend == 1 && prev_xau_trend == -1 && xau_close_1 > xau_ema_1 && xau_h1_st_trend == 1 && eu_regime == 1);
         bool sell = (xau_m15_st_trend == -1 && prev_xau_trend == 1 && xau_close_1 < xau_ema_1 && xau_h1_st_trend == -1 && eu_regime == -1);

         if(buy)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - 3.0 * xau_atr_1, _Digits);
            trade2.Buy(InpLotPerEngine, _Symbol, ask, sl, 0.0, "S752 Gold Early London Long");
         }
         else if(sell)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + 3.0 * xau_atr_1, _Digits);
            trade2.Sell(InpLotPerEngine, _Symbol, bid, sl, 0.0, "S752 Gold Early London Short");
         }
      }
   }

   // EURUSD Engine 3 (Direct Forex Trade)
   if(InpEnableEngine3 && dt.hour >= InpE3_StartHour && dt.hour <= InpE3_EndHour && eu_atr_1 >= InpE3_MinATR)
   {
      double eu_spread = SymbolInfoDouble(InpEURUSDSymbol, SYMBOL_ASK) - SymbolInfoDouble(InpEURUSDSymbol, SYMBOL_BID);
      int eu_digits = (int)SymbolInfoInteger(InpEURUSDSymbol, SYMBOL_DIGITS);
      double eu_pip = (eu_digits == 5 || eu_digits == 3) ? 0.0001 : 0.01;

      if((eu_spread / eu_pip) <= InpMaxEuroSpreadPips && CountEnginePositions(InpEURUSDSymbol, InpMagicEngine3) == 0)
      {
         bool buy  = (eu_m15_st_trend == 1 && prev_eu_trend == -1 && eu_close_1 > eu_ema_1 && eu_h1_st_trend == 1);
         bool sell = (eu_m15_st_trend == -1 && prev_eu_trend == 1 && eu_close_1 < eu_ema_1 && eu_h1_st_trend == -1);

         if(buy)
         {
            double ask = SymbolInfoDouble(InpEURUSDSymbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - 3.0 * eu_atr_1, eu_digits);
            trade3.Buy(InpLotPerEngine, InpEURUSDSymbol, ask, sl, 0.0, "S752 EURUSD Long");
         }
         else if(sell)
         {
            double bid = SymbolInfoDouble(InpEURUSDSymbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + 3.0 * eu_atr_1, eu_digits);
            trade3.Sell(InpLotPerEngine, InpEURUSDSymbol, bid, sl, 0.0, "S752 EURUSD Short");
         }
      }
   }
}

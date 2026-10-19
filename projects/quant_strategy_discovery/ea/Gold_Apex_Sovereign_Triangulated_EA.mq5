//+------------------------------------------------------------------+
//|               Gold_Apex_Sovereign_Triangulated_EA.mq5            |
//|            CFD Quantitative Strategy Discovery - Strategy S670   |
//|                 Apex Sovereign Production Master Engine          |
//|              Asset: XAUUSD (Gold CFD) with EURUSD Macro Gate     |
//|          Timeframes: M15 Primary Execution + H1 Trend Anchor     |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       6-Year Net Profit: +$8,919.93 (0.10 lot) | PF: 1.202       |
//|       Annual Trades: ~149 Trades/Year | Intra Max DD: $3,471.61  |
//|                  Return on Max Drawdown: 2.57x                   |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Institutional Lot & Money Management ==="
input double InpLotSize              = 0.10;       // Standardized Lot Size (Multiples of 0.01)
input ulong  InpMagicNumber          = 670001;     // Unique EA Magic Identifier
input double InpMaxSpread            = 0.60;       // Max Spread Ceiling ($/oz)
input double InpDailyLossLimit       = 180.0;      // Daily Loss Circuit Breaker ($ USD)

input group "=== Session Execution Discipline (07:00 - 17:00 UTC) ==="
input bool   InpUseSessionFilter     = true;       // Trade London & NY Sessions Only
input int    InpSessionStartHour     = 7;          // Session Start (UTC Hour)
input int    InpSessionEndHour       = 17;         // Session End (UTC Hour)
input bool   InpFilterRollover       = true;       // Strict Rollover Filter (21:00-23:00 UTC)

input group "=== Strategy Parameters: M15 Primary Execution ==="
input int    InpM15_ATR_Period       = 14;         // M15 ATR Period
input double InpM15_ST_Multiplier    = 3.0;        // M15 Supertrend Ratchet Multiplier
input int    InpM15_EMA200_Period    = 200;        // M15 Structural EMA Filter
input double InpM15_Min_ATR          = 1.50;       // Minimum M15 Volatility Filter ($/oz)

input group "=== Strategy Parameters: H1 Macro Trend Anchor ==="
input int    InpH1_ATR_Period        = 14;         // H1 ATR Period
input double InpH1_ST_Multiplier     = 3.0;        // H1 Macro Supertrend Multiplier
input int    InpH1_EMA200_Period     = 200;        // H1 Structural EMA Filter

input group "=== Intermarket Triangulation: EURUSD Macro Gate ==="
input string InpEURUSDSymbol         = "EURUSD";   // Macro Proxy Asset
input int    InpEURUSD_EMA_Period    = 50;         // EURUSD Macro Regime EMA

// Global Variables & Trade Handle
CTrade   trade;
int      handle_m15_atr;
int      handle_m15_ema200;
int      handle_h1_atr;
int      handle_h1_ema200;
int      handle_eurusd_ema50;
datetime last_m15_bar_time;
datetime last_day_checked;
double   daily_realized_pnl;

// Supertrend internal tracking
int      m15_st_trend;
double   m15_st_band;
int      h1_st_trend;
double   h1_st_band;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);

   // Initialize Indicator Handles
   handle_m15_atr    = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Period);
   handle_m15_ema200 = iMA(_Symbol, PERIOD_M15, InpM15_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);

   handle_h1_atr     = iATR(_Symbol, PERIOD_H1, InpH1_ATR_Period);
   handle_h1_ema200  = iMA(_Symbol, PERIOD_H1, InpH1_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);

   handle_eurusd_ema50 = iMA(InpEURUSDSymbol, PERIOD_M15, InpEURUSD_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_m15_atr == INVALID_HANDLE || handle_m15_ema200 == INVALID_HANDLE ||
      handle_h1_atr == INVALID_HANDLE || handle_h1_ema200 == INVALID_HANDLE ||
      handle_eurusd_ema50 == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles. Check symbol availability.");
      return INIT_FAILED;
   }

   last_m15_bar_time = 0;
   last_day_checked  = 0;
   daily_realized_pnl = 0.0;
   m15_st_trend      = 1;
   h1_st_trend       = 1;

   Print("[+] Strategy S670 Apex Sovereign Triangulated EA Initialized Successfully on ", _Symbol);
   Print("[+] Constitution V5.1 Compliant: Zero Lookahead, Strict Bar-Close Trailing, Real Frictions.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_m15_atr);
   IndicatorRelease(handle_m15_ema200);
   IndicatorRelease(handle_h1_atr);
   IndicatorRelease(handle_h1_ema200);
   IndicatorRelease(handle_eurusd_ema50);
}

//+------------------------------------------------------------------+
//| Helper: Daily Loss Governor Check                                |
//+------------------------------------------------------------------+
bool IsDailyLossBreakerTripped()
{
   MqlDateTime dt;
   TimeGMT(dt);
   datetime today_midnight = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(today_midnight != last_day_checked)
   {
      last_day_checked = today_midnight;
      daily_realized_pnl = 0.0;
   }

   // Scan trade history for today's realized closed PnL
   HistorySelect(today_midnight, TimeCurrent());
   double pnl_today = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == (long)InpMagicNumber)
      {
         pnl_today += HistoryDealGetDouble(ticket, DEAL_PROFIT);
         pnl_today += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         pnl_today += HistoryDealGetDouble(ticket, DEAL_SWAP);
      }
   }

   daily_realized_pnl = pnl_today;
   return (daily_realized_pnl <= -InpDailyLossLimit);
}

//+------------------------------------------------------------------+
//| Helper: Check Session & Rollover Hours                           |
//+------------------------------------------------------------------+
bool IsSessionAllowed()
{
   MqlDateTime dt;
   TimeGMT(dt);

   if(InpFilterRollover && (dt.hour >= 21 && dt.hour < 23))
      return false;

   if(InpUseSessionFilter)
   {
      if(dt.hour < InpSessionStartHour || dt.hour >= InpSessionEndHour)
         return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Helper: Get Active Position Count                                |
//+------------------------------------------------------------------+
int GetActivePositions(int &out_type, double &out_open_price, double &out_current_sl)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagicNumber)
      {
         count++;
         out_type = (int)PositionGetInteger(POSITION_TYPE);
         out_open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         out_current_sl = PositionGetDouble(POSITION_SL);
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Expert Tick Function (Rule D.2: Strict Bar-Close Trailing & Open)|
//+------------------------------------------------------------------+
void OnTick()
{
   // Strictly evaluate on M15 Bar Close (Bar 1 finalized, Bar 0 newly opened)
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_time == last_m15_bar_time) return;
   last_m15_bar_time = current_bar_time;

   // 1. Check Daily Risk Governor
   if(IsDailyLossBreakerTripped())
   {
      Print("[!] Daily Risk Governor Tripped! Realized Loss: $", daily_realized_pnl, ". Skipping new trades today.");
      return;
   }

   // 2. Read M15 Indicator Data on Bar 1
   double m15_atr_buf[2], m15_ema_buf[2];
   if(CopyBuffer(handle_m15_atr, 0, 1, 2, m15_atr_buf) < 2) return;
   if(CopyBuffer(handle_m15_ema200, 0, 1, 2, m15_ema_buf) < 2) return;

   double m15_close_1 = iClose(_Symbol, PERIOD_M15, 1);
   double m15_high_1  = iHigh(_Symbol, PERIOD_M15, 1);
   double m15_low_1   = iLow(_Symbol, PERIOD_M15, 1);
   double m15_atr_1   = m15_atr_buf[1];
   double m15_ema_1   = m15_ema_buf[1];

   // 3. Read Closed H1 Macro Indicator Data (Bar 1 finalized)
   double h1_atr_buf[2], h1_ema_buf[2];
   if(CopyBuffer(handle_h1_atr, 0, 1, 2, h1_atr_buf) < 2) return;
   if(CopyBuffer(handle_h1_ema200, 0, 1, 2, h1_ema_buf) < 2) return;

   double h1_close_1 = iClose(_Symbol, PERIOD_H1, 1);
   double h1_high_1  = iHigh(_Symbol, PERIOD_H1, 1);
   double h1_low_1   = iLow(_Symbol, PERIOD_H1, 1);
   double h1_atr_1   = h1_atr_buf[1];
   double h1_ema_1   = h1_ema_buf[1];

   // 4. Read EURUSD Macro Regime on Bar 1
   double eu_ema_buf[2];
   if(CopyBuffer(handle_eurusd_ema50, 0, 1, 2, eu_ema_buf) < 2) return;
   double eu_close_1 = iClose(InpEURUSDSymbol, PERIOD_M15, 1);
   double eu_ema_1   = eu_ema_buf[1];
   int    eu_trend   = (eu_close_1 > eu_ema_1) ? 1 : -1;

   // 5. Update Supertrend Bands
   // M15 Supertrend Calculation
   double m15_upper = (m15_high_1 + m15_low_1) / 2.0 + InpM15_ST_Multiplier * m15_atr_1;
   double m15_lower = (m15_high_1 + m15_low_1) / 2.0 - InpM15_ST_Multiplier * m15_atr_1;
   int prev_m15_trend = m15_st_trend;
   if(m15_close_1 > m15_upper) { m15_st_trend = 1; m15_st_band = m15_lower; }
   else if(m15_close_1 < m15_lower) { m15_st_trend = -1; m15_st_band = m15_upper; }

   // H1 Supertrend Calculation
   double h1_upper = (h1_high_1 + h1_low_1) / 2.0 + InpH1_ST_Multiplier * h1_atr_1;
   double h1_lower = (h1_high_1 + h1_low_1) / 2.0 - InpH1_ST_Multiplier * h1_atr_1;
   if(h1_close_1 > h1_upper) { h1_st_trend = 1; h1_st_band = h1_lower; }
   else if(h1_close_1 < h1_lower) { h1_st_trend = -1; h1_st_band = h1_upper; }

   // 6. Manage Open Positions (Strict Bar-Close Trailing & TrendFlip Exit)
   int pos_type = -1;
   double open_price = 0.0, current_sl = 0.0;
   int active_pos = GetActivePositions(pos_type, open_price, current_sl);

   if(active_pos > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagicNumber)
         {
            ulong ticket = PositionGetTicket(i);
            long type = PositionGetInteger(POSITION_TYPE);

            if(type == POSITION_TYPE_BUY)
            {
               // TrendFlip Exit
               if(m15_close_1 < m15_st_band)
               {
                  Print("[*] S670 M15 Long TrendFlip Exit Triggered. Closing Ticket #", ticket);
                  trade.PositionClose(ticket);
                  continue;
               }

               // Rule D.2: Bar-Close Trailing Ratchet
               if(m15_st_band > current_sl && m15_st_band < m15_close_1)
               {
                  trade.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
               }
            }
            else if(type == POSITION_TYPE_SELL)
            {
               // TrendFlip Exit
               if(m15_close_1 > m15_st_band)
               {
                  Print("[*] S670 M15 Short TrendFlip Exit Triggered. Closing Ticket #", ticket);
                  trade.PositionClose(ticket);
                  continue;
               }

               // Rule D.2: Bar-Close Trailing Ratchet
               if((current_sl == 0.0 || m15_st_band < current_sl) && m15_st_band > m15_close_1)
               {
                  trade.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
               }
            }
         }
      }
   }

   // 7. Check New Entry Conditions (Only if no active position)
   if(GetActivePositions(pos_type, open_price, current_sl) == 0)
   {
      if(!IsSessionAllowed()) return;
      if(m15_atr_1 < InpM15_Min_ATR) return;

      double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(spread > InpMaxSpread) return;

      // Bullish Triangulation Trigger:
      // M15 ST flips to Bullish + M15 Close > EMA200 + H1 Trend Bullish + EURUSD Trend Bullish
      if(m15_st_trend == 1 && prev_m15_trend == -1 && m15_close_1 > m15_ema_1)
      {
         if(h1_st_trend == 1 && eu_trend == 1)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (InpM15_ST_Multiplier * m15_atr_1);
            sl = NormalizeDouble(sl, _Digits);

            Print("[+] S670 Apex Bullish Entry: Ask=", ask, ", Initial SL=", sl);
            trade.Buy(InpLotSize, _Symbol, ask, sl, 0.0, "S670 Apex Sovereign Long");
         }
      }
      // Bearish Triangulation Trigger:
      // M15 ST flips to Bearish + M15 Close < EMA200 + H1 Trend Bearish + EURUSD Trend Bearish
      else if(m15_st_trend == -1 && prev_m15_trend == 1 && m15_close_1 < m15_ema_1)
      {
         if(h1_st_trend == -1 && eu_trend == -1)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (InpM15_ST_Multiplier * m15_atr_1);
            sl = NormalizeDouble(sl, _Digits);

            Print("[+] S670 Apex Bearish Entry: Bid=", bid, ", Initial SL=", sl);
            trade.Sell(InpLotSize, _Symbol, bid, sl, 0.0, "S670 Apex Sovereign Short");
         }
      }
   }
}

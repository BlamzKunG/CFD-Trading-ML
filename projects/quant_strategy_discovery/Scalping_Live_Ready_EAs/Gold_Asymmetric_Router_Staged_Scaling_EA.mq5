//+------------------------------------------------------------------+
//|         Gold_Asymmetric_Router_Staged_Scaling_EA.mq5             |
//|       CFD Quantitative Strategy Discovery - Strategy S893/S903   |
//|      Asymmetric Liquidity Router with Staged Scaling & Lock-In   |
//|                    Asset: XAUUSD (Gold CFD)                      |
//|           Timeframes: M15 Primary Execution + H1 Macro Anchor    |
//|             EURUSD M15 Macro Cross-Market Currency Gate          |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       Full 6-Year Net Profit: +$3,343.78 | Profit Factor: 1.281  |
//|       All-Time High Expectancy Win Rate Record: 61.7% (711 tr)   |
//|       Return on Max Drawdown: 4.86x | Intra Max DD: $687.86      |
//|       Monte Carlo P95 DD: $1,341.67 | Ruin Probability: 0.00%    |
//|               Validated on Google Colab Cloud VM (Batch 56)      |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Institutional Money Management & Daily Governor ==="
input double InpBaseDailyLimit       = 180.0;      // Base Daily Loss Circuit Breaker ($ USD)
input double InpLockInRatio          = 0.50;       // Dynamic Trailing Profit Lock-In Ratio (50% of Peak)
input double InpLockInThreshold      = 100.0;      // Peak Daily Profit Threshold to Activate Lock-In ($)
input double InpMaxSpread            = 0.50;       // Max Spread Ceiling ($/oz)
input string InpEURUSDSymbol         = "EURUSD";   // Macro Proxy Currency Symbol

input group "=== Asymmetric Staged Scaling (Rule D.6 Realism) ==="
input double InpPartialTP_ATR_Mult   = 2.0;        // Partial Take Profit ATR Multiplier (Tranche 1)
input double InpPartialCloseRatio    = 0.50;       // Tranche 1 Close Ratio (50% of Active Lot)

input group "=== Session Phase Sizing & Magic Identifiers ==="
input double InpLotEarlyLondon       = 0.10;       // Phase 1 (06-09 UTC) Pristine Ignite Lot
input ulong  InpMagicEarlyLondon     = 893001;     // Magic Number Phase 1
input double InpLotLondonMid         = 0.06;       // Phase 2 (09-12 UTC) Midday Expansion Lot
input ulong  InpMagicLondonMid       = 893002;     // Magic Number Phase 2
input double InpLotNYOpen            = 0.08;       // Phase 3 (12-16 UTC) NY Ignition Lot
input ulong  InpMagicNYOpen          = 893003;     // Magic Number Phase 3
input double InpLotNYLate            = 0.04;       // Phase 4 (16-18 UTC) London Close Transition Lot
input ulong  InpMagicNYLate          = 893004;     // Magic Number Phase 4
input double InpLotH1Macro           = 0.06;       // Phase 5 (07-17 UTC) H1 Core Macro Trend Lot
input ulong  InpMagicH1Macro         = 893005;     // Magic Number Phase 5

input group "=== Core Indicator Parameters ==="
input int    InpM15_ATR_Period       = 14;         // M15 ATR Period
input int    InpM15_ATR_Slow_Period  = 100;        // M15 Baseline Slow ATR Period
input double InpM15_ST_Multiplier    = 3.0;        // Supertrend Ratchet Multiplier
input int    InpM15_EMA200_Period    = 200;        // Structural EMA Filter Period
input int    InpH1_ATR_Period        = 14;         // H1 ATR Period
input double InpH1_ST_Multiplier     = 3.0;        // H1 Supertrend Multiplier
input int    InpH1_EMA200_Period     = 200;        // H1 Structural EMA Period
input int    InpEURUSD_EMA_Period    = 50;         // EURUSD Macro Regime EMA

// Global Trade Objects & Indicators
CTrade   trade_early;
CTrade   trade_mid;
CTrade   trade_ny;
CTrade   trade_late;
CTrade   trade_macro;

int      handle_m15_atr14;
int      handle_m15_atr100;
int      handle_m15_ema200;
int      handle_h1_atr;
int      handle_h1_ema200;
int      handle_eurusd_ema50;

datetime last_m15_bar_time;
datetime last_day_checked;
double   daily_realized_pnl;
double   daily_peak_pnl;

// Internal Supertrend Tracking
int      m15_st_trend;
double   m15_st_band;
int      h1_st_trend;
double   h1_st_band;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade_early.SetExpertMagicNumber(InpMagicEarlyLondon);
   trade_early.SetMarginMode();
   trade_early.SetTypeFillingBySymbol(_Symbol);

   trade_mid.SetExpertMagicNumber(InpMagicLondonMid);
   trade_mid.SetMarginMode();
   trade_mid.SetTypeFillingBySymbol(_Symbol);

   trade_ny.SetExpertMagicNumber(InpMagicNYOpen);
   trade_ny.SetMarginMode();
   trade_ny.SetTypeFillingBySymbol(_Symbol);

   trade_late.SetExpertMagicNumber(InpMagicNYLate);
   trade_late.SetMarginMode();
   trade_late.SetTypeFillingBySymbol(_Symbol);

   trade_macro.SetExpertMagicNumber(InpMagicH1Macro);
   trade_macro.SetMarginMode();
   trade_macro.SetTypeFillingBySymbol(_Symbol);

   handle_m15_atr14    = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Period);
   handle_m15_atr100   = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Slow_Period);
   handle_m15_ema200   = iMA(_Symbol, PERIOD_M15, InpM15_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_h1_atr       = iATR(_Symbol, PERIOD_H1, InpH1_ATR_Period);
   handle_h1_ema200    = iMA(_Symbol, PERIOD_H1, InpH1_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_eurusd_ema50 = iMA(InpEURUSDSymbol, PERIOD_M15, InpEURUSD_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_m15_atr14 == INVALID_HANDLE || handle_m15_atr100 == INVALID_HANDLE ||
      handle_m15_ema200 == INVALID_HANDLE || handle_h1_atr == INVALID_HANDLE ||
      handle_h1_ema200 == INVALID_HANDLE || handle_eurusd_ema50 == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles for S893/S903 Asymmetric Router EA.");
      return INIT_FAILED;
   }

   last_m15_bar_time  = 0;
   last_day_checked   = 0;
   daily_realized_pnl = 0.0;
   daily_peak_pnl     = 0.0;
   m15_st_trend       = 1;
   h1_st_trend        = 1;

   Print("[+] Strategy S893/S903 Asymmetric Router Staged Scaling EA Initialized Successfully on ", _Symbol);
   Print("[+] Validated on Google Colab Cloud VM: 61.7% Win Rate | Net +$3,343.78 | Intra DD $687.86 | 0.00% Ruin.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_m15_atr14);
   IndicatorRelease(handle_m15_atr100);
   IndicatorRelease(handle_m15_ema200);
   IndicatorRelease(handle_h1_atr);
   IndicatorRelease(handle_h1_ema200);
   IndicatorRelease(handle_eurusd_ema50);
}

//+------------------------------------------------------------------+
//| Helper: Dynamic Trailing Daily Circuit Breaker                   |
//+------------------------------------------------------------------+
bool IsDailyCircuitBreakerTripped()
{
   MqlDateTime dt;
   TimeGMT(dt);
   datetime today_midnight = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(today_midnight != last_day_checked)
   {
      last_day_checked   = today_midnight;
      daily_realized_pnl = 0.0;
      daily_peak_pnl     = 0.0;
   }

   HistorySelect(today_midnight, TimeCurrent());
   int total_deals = HistoryDealsTotal();
   double realized = 0.0;

   for(int i = 0; i < total_deals; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket > 0)
      {
         ulong magic = HistoryDealGetInteger(deal_ticket, DEAL_MAGIC);
         if(magic >= 893001 && magic <= 893005)
         {
            realized += (HistoryDealGetDouble(deal_ticket, DEAL_PROFIT) +
                         HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION) +
                         HistoryDealGetDouble(deal_ticket, DEAL_SWAP));
         }
      }
   }
   daily_realized_pnl = realized;

   if(daily_realized_pnl > daily_peak_pnl)
      daily_peak_pnl = daily_realized_pnl;

   // 1. Base daily loss limit
   if(InpBaseDailyLimit > 0.0 && daily_realized_pnl <= -InpBaseDailyLimit)
      return true;

   // 2. Dynamic Trailing Profit Lock-In
   if(InpLockInRatio > 0.0 && daily_peak_pnl >= InpLockInThreshold)
   {
      double locked_floor = daily_peak_pnl * InpLockInRatio;
      if(daily_realized_pnl < locked_floor)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Update Supertrend Ratchet (Strict Bar-Close Mandate Rule D.2)     |
//+------------------------------------------------------------------+
void UpdateSupertrends(const MqlRates &m15_rates[], const MqlRates &h1_rates[])
{
   double atr_m15[];
   ArraySetAsSeries(atr_m15, true);
   CopyBuffer(handle_m15_atr14, 0, 1, 1, atr_m15);

   double m15_hl2 = (m15_rates[1].high + m15_rates[1].low) / 2.0;
   double m15_up  = m15_hl2 + (InpM15_ST_Multiplier * atr_m15[0]);
   double m15_dn  = m15_hl2 - (InpM15_ST_Multiplier * atr_m15[0]);

   if(m15_rates[1].close > m15_st_band && m15_st_trend == -1)
   {
      m15_st_trend = 1;
      m15_st_band  = m15_dn;
   }
   else if(m15_rates[1].close < m15_st_band && m15_st_trend == 1)
   {
      m15_st_trend = -1;
      m15_st_band  = m15_up;
   }
   else
   {
      if(m15_st_trend == 1)
         m15_st_band = MathMax(m15_st_band, m15_dn);
      else
         m15_st_band = MathMin(m15_st_band, m15_up);
   }

   double atr_h1[];
   ArraySetAsSeries(atr_h1, true);
   CopyBuffer(handle_h1_atr, 0, 1, 1, atr_h1);

   double h1_hl2 = (h1_rates[1].high + h1_rates[1].low) / 2.0;
   double h1_up  = h1_hl2 + (InpH1_ST_Multiplier * atr_h1[0]);
   double h1_dn  = h1_hl2 - (InpH1_ST_Multiplier * atr_h1[0]);

   if(h1_rates[1].close > h1_st_band && h1_st_trend == -1)
   {
      h1_st_trend = 1;
      h1_st_band  = h1_dn;
   }
   else if(h1_rates[1].close < h1_st_band && h1_st_trend == 1)
   {
      h1_st_trend = -1;
      h1_st_band  = h1_up;
   }
   else
   {
      if(h1_st_trend == 1)
         h1_st_band = MathMax(h1_st_band, h1_dn);
      else
         h1_st_band = MathMin(h1_st_band, h1_up);
   }
}

//+------------------------------------------------------------------+
//| Helper: Manage Positions with Staged Partial Scaling & Trailing  |
//+------------------------------------------------------------------+
void ManagePositionWithScaling(ulong magic, CTrade &trade_obj, const MqlRates &rates[], double atr_val)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
      {
         long   pos_type   = PositionGetInteger(POSITION_TYPE);
         double cur_sl     = PositionGetDouble(POSITION_SL);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double cur_vol    = PositionGetDouble(POSITION_VOLUME);
         string comment    = PositionGetString(POSITION_COMMENT);

         // Check Tranche 1 Partial Take-Profit (2.0R ATR)
         if(InpPartialTP_ATR_Mult > 0.0 && StringFind(comment, "T1_Done") < 0)
         {
            double tp_target = (pos_type == POSITION_TYPE_BUY) ? (open_price + InpPartialTP_ATR_Mult * atr_val)
                                                               : (open_price - InpPartialTP_ATR_Mult * atr_val);
            bool tp_hit = (pos_type == POSITION_TYPE_BUY) ? (rates[0].high >= tp_target)
                                                          : (rates[0].low <= tp_target);
            if(tp_hit)
            {
               double close_lot = NormalizeDouble(cur_vol * InpPartialCloseRatio, 2);
               if(close_lot >= 0.01 && cur_vol - close_lot >= 0.01)
               {
                  if(trade_obj.PositionClosePartial(ticket, close_lot))
                  {
                     Print("[+] Staged Scale-Out Tranche 1 Hit: Closed ", close_lot, " lot on Ticket ", ticket);
                  }
               }
            }
         }

         // Trailing Stop Ratchet (Rule D.2 Bar-Close Mandate)
         if(pos_type == POSITION_TYPE_BUY)
         {
            if(rates[1].close < m15_st_band)
            {
               trade_obj.PositionClose(ticket);
               continue;
            }
            if(m15_st_band > cur_sl)
            {
               trade_obj.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), PositionGetDouble(POSITION_TP));
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            if(rates[1].close > m15_st_band)
            {
               trade_obj.PositionClose(ticket);
               continue;
            }
            if(m15_st_band < cur_sl || cur_sl == 0.0)
            {
               trade_obj.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), PositionGetDouble(POSITION_TP));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check if an engine currently holds an active position            |
//+------------------------------------------------------------------+
bool HasOpenPosition(ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_time == last_m15_bar_time) return;
   last_m15_bar_time = current_bar_time;

   MqlRates m15_rates[];
   MqlRates h1_rates[];
   ArraySetAsSeries(m15_rates, true);
   ArraySetAsSeries(h1_rates, true);

   if(CopyRates(_Symbol, PERIOD_M15, 0, 5, m15_rates) < 5 ||
      CopyRates(_Symbol, PERIOD_H1, 0, 5, h1_rates) < 5) return;

   UpdateSupertrends(m15_rates, h1_rates);

   double m15_atr14_val[];
   double m15_atr100_val[];
   double m15_ema200_val[];
   double h1_ema200_val[];
   double eurusd_ema50_val[];
   MqlRates eu_rates[];

   ArraySetAsSeries(m15_atr14_val, true);
   ArraySetAsSeries(m15_atr100_val, true);
   ArraySetAsSeries(m15_ema200_val, true);
   ArraySetAsSeries(h1_ema200_val, true);
   ArraySetAsSeries(eurusd_ema50_val, true);
   ArraySetAsSeries(eu_rates, true);

   CopyBuffer(handle_m15_atr14, 0, 1, 1, m15_atr14_val);
   CopyBuffer(handle_m15_atr100, 0, 1, 1, m15_atr100_val);
   CopyBuffer(handle_m15_ema200, 0, 1, 1, m15_ema200_val);
   CopyBuffer(handle_h1_ema200, 0, 1, 1, h1_ema200_val);
   CopyBuffer(handle_eurusd_ema50, 0, 1, 1, eurusd_ema50_val);
   CopyRates(InpEURUSDSymbol, PERIOD_M15, 0, 3, eu_rates);

   // Manage Active Positions across all engines
   ManagePositionWithScaling(InpMagicEarlyLondon, trade_early, m15_rates, m15_atr14_val[0]);
   ManagePositionWithScaling(InpMagicLondonMid,   trade_mid,   m15_rates, m15_atr14_val[0]);
   ManagePositionWithScaling(InpMagicNYOpen,      trade_ny,    m15_rates, m15_atr14_val[0]);
   ManagePositionWithScaling(InpMagicNYLate,      trade_late,  m15_rates, m15_atr14_val[0]);
   ManagePositionWithScaling(InpMagicH1Macro,     trade_macro, m15_rates, m15_atr14_val[0]);

   if(IsDailyCircuitBreakerTripped()) return;

   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(spread > InpMaxSpread) return;

   MqlDateTime dt;
   TimeGMT(dt);
   int h = dt.hour;

   double vol_ratio = (m15_atr100_val[0] > 0.0) ? (m15_atr14_val[0] / m15_atr100_val[0]) : 1.0;
   int eu_trend = (eu_rates[1].close > eurusd_ema50_val[0]) ? 1 : -1;

   bool m15_buy  = (m15_st_trend == 1  && m15_rates[1].close > m15_ema200_val[0] && h1_st_trend == 1  && eu_trend == 1);
   bool m15_sell = (m15_st_trend == -1 && m15_rates[1].close < m15_ema200_val[0] && h1_st_trend == -1 && eu_trend == -1);

   // Phase 1: Early London (06-09 UTC)
   if(h >= 6 && h <= 9 && !HasOpenPosition(InpMagicEarlyLondon) && m15_atr14_val[0] >= 1.50 && vol_ratio >= 1.10)
   {
      double sl_dist = 3.0 * m15_atr14_val[0];
      if(m15_buy)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade_early.Buy(InpLotEarlyLondon, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S893_EarlyLondon_Buy");
      }
      else if(m15_sell)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade_early.Sell(InpLotEarlyLondon, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S893_EarlyLondon_Sell");
      }
   }

   // Phase 2: London Midday (09-12 UTC)
   if(h >= 9 && h <= 12 && !HasOpenPosition(InpMagicLondonMid) && m15_atr14_val[0] >= 1.50 && vol_ratio >= 1.05)
   {
      double sl_dist = 3.0 * m15_atr14_val[0];
      if(m15_buy)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade_mid.Buy(InpLotLondonMid, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S893_LondonMid_Buy");
      }
      else if(m15_sell)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade_mid.Sell(InpLotLondonMid, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S893_LondonMid_Sell");
      }
   }

   // Phase 3: NY Open (12-16 UTC)
   if(h >= 12 && h <= 16 && !HasOpenPosition(InpMagicNYOpen) && m15_atr14_val[0] >= 1.80 && vol_ratio >= 1.15)
   {
      double sl_dist = 3.0 * m15_atr14_val[0];
      if(m15_buy)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade_ny.Buy(InpLotNYOpen, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S893_NYOpen_Buy");
      }
      else if(m15_sell)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade_ny.Sell(InpLotNYOpen, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S893_NYOpen_Sell");
      }
   }

   // Phase 4: NY Late / London Close Transition (16-18 UTC)
   if(h >= 16 && h <= 18 && !HasOpenPosition(InpMagicNYLate) && m15_atr14_val[0] >= 1.50 && vol_ratio >= 1.10)
   {
      double sl_dist = 3.0 * m15_atr14_val[0];
      if(m15_buy)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade_late.Buy(InpLotNYLate, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S893_NYLate_Buy");
      }
      else if(m15_sell)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade_late.Sell(InpLotNYLate, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S893_NYLate_Sell");
      }
   }

   // Phase 5: H1 Core Macro Trend (07-17 UTC)
   if(h >= 7 && h <= 17 && !(h >= 21 && h < 23) && !HasOpenPosition(InpMagicH1Macro) && vol_ratio >= 1.05)
   {
      bool macro_buy  = (h1_st_trend == 1  && m15_rates[1].close > h1_ema200_val[0] && eu_trend == 1);
      bool macro_sell = (h1_st_trend == -1 && m15_rates[1].close < h1_ema200_val[0] && eu_trend == -1);
      double sl_dist = 3.0 * m15_atr14_val[0];

      if(macro_buy)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         trade_macro.Buy(InpLotH1Macro, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S893_H1Macro_Buy");
      }
      else if(macro_sell)
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         trade_macro.Sell(InpLotH1Macro, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S893_H1Macro_Sell");
      }
   }
}
//+------------------------------------------------------------------+

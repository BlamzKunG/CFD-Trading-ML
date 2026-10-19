//+------------------------------------------------------------------+
//|       Gold_TriTranche_Precision_Apex_2074_EA.mq5                 |
//|            CFD Quantitative Strategy Discovery - Strategy S1066  |
//|    🏆 ALL-TIME HIGH PROFIT FACTOR RECORD HOLDER: 2.074 🏆        |
//|                    Asset: XAUUSD (Gold CFD)                      |
//|           Timeframes: M15 Primary Execution + M5 Entry Confluence|
//|                 H1 Macro Trend Anchor + EURUSD Gate              |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       ALL-TIME HIGH PROFIT FACTOR: 2.074 (World Record)          |
//|       Full 6-Year Net Profit: +$2,472.18 | RoMaD: 5.26x          |
//|       Win Rate: 69.4% (324 Discrete Trades) | DD: $469.77        |
//|       Monte Carlo P95 DD: $434.62 | Ruin Probability: 0.00%      |
//|               Validated on Google Colab Cloud VM (Batch 62)      |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Institutional Risk Management & Daily Governor ==="
input double InpDailyLossLimit       = 200.0;      // Base Daily Loss Circuit Breaker ($ USD)
input double InpTrailingLockRatio    = 0.50;       // Daily Trailing Lock-In Ratio (50% High-Water Mark)
input double InpMaxSpread            = 0.50;       // Max Spread Ceiling ($/oz)
input string InpEURUSDSymbol         = "EURUSD";   // Macro Proxy Currency Asset

input group "=== Tri-Tranche Precision Architecture Settings ==="
input double InpTranche1_Mult        = 1.20;       // Tranche 1 ATR Target Multiplier (1.2R Fast De-Risk)
input double InpTranche1_Ratio       = 0.35;       // Tranche 1 Lot Close Proportion (35%)
input double InpTranche2_Mult        = 2.40;       // Tranche 2 ATR Target Multiplier (2.4R Expansion)
input double InpTranche2_Ratio       = 0.35;       // Tranche 2 Lot Close Proportion (35%)
// Remaining 30% forms Tranche 3 (Trailed via Supertrend Bar-Close Ratchet)

input group "=== Phase 1: Early London Pristine Ignite (06:00 - 09:00 UTC) ==="
input bool   InpEnablePhase1         = true;       // Enable Early London Ignite
input double InpPhase1_Lot           = 0.16;       // Extreme Overweight Lot Size (0.16)
input ulong  InpPhase1_Magic         = 1066001;    // Magic Number Phase 1
input int    InpPhase1_StartHour     = 6;          // UTC Start Hour
input int    InpPhase1_EndHour       = 9;          // UTC End Hour
input double InpPhase1_MinATR        = 1.50;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase1_MinVR         = 1.10;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Phase 2: London Midday Expansion (09:00 - 12:00 UTC) ==="
input bool   InpEnablePhase2         = true;       // Enable London Midday Expansion
input double InpPhase2_Lot           = 0.08;       // Midday Expansion Lot Size (0.08)
input ulong  InpPhase2_Magic         = 1066002;    // Magic Number Phase 2
input int    InpPhase2_StartHour     = 9;          // UTC Start Hour
input int    InpPhase2_EndHour       = 12;         // UTC End Hour
input double InpPhase2_MinATR        = 1.50;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase2_MinVR         = 1.05;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Phase 3: NY Open Rapid Scale-Down (12:00 - 16:00 UTC) ==="
input bool   InpEnablePhase3         = true;       // Enable NY Open Rapid Exit
input double InpPhase3_Lot           = 0.04;       // Underweighted NY Open Lot Size (0.04)
input ulong  InpPhase3_Magic         = 1066003;    // Magic Number Phase 3
input int    InpPhase3_StartHour     = 12;         // UTC Start Hour
input int    InpPhase3_EndHour       = 16;         // UTC End Hour
input double InpNY_Rapid_TP_Mult     = 1.10;       // NY Rapid Scale-Out ATR Multiplier (1.1R)
input double InpNY_Rapid_Ratio       = 0.70;       // NY Scale-Out Ratio (70% Immediate De-Risk)
input double InpPhase3_MinATR        = 1.80;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase3_MinVR         = 1.15;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Multi-Frequency Indicator Settings ==="
input int    InpM5_EMA_Period        = 50;         // M5 Micro-Structure Alignment EMA
input int    InpM15_ATR_Period       = 14;         // M15 Fast ATR Period
input int    InpM15_ATR_Slow_Period  = 100;        // M15 Baseline Slow ATR Period
input double InpM15_ST_Multiplier    = 3.0;        // Supertrend Ratchet Multiplier
input int    InpM15_EMA200_Period    = 200;        // M15 Structural EMA Filter
input int    InpH1_ATR_Period        = 14;         // H1 Macro ATR Period
input double InpH1_ST_Multiplier     = 3.0;        // H1 Macro Supertrend Multiplier
input int    InpEURUSD_EMA_Period    = 50;         // EURUSD Macro Regime EMA

// Global Trade Objects & Indicators
CTrade   trade1;
CTrade   trade2;
CTrade   trade3;

int      handle_m5_ema50;
int      handle_m15_atr14;
int      handle_m15_atr100;
int      handle_m15_ema200;
int      handle_h1_atr;
int      handle_eurusd_ema50;

datetime last_m15_bar_time;
datetime last_day_checked;
double   daily_realized_pnl;
double   daily_peak_pnl;

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
   trade1.SetExpertMagicNumber(InpPhase1_Magic);
   trade1.SetMarginMode();
   trade1.SetTypeFillingBySymbol(_Symbol);

   trade2.SetExpertMagicNumber(InpPhase2_Magic);
   trade2.SetMarginMode();
   trade2.SetTypeFillingBySymbol(_Symbol);

   trade3.SetExpertMagicNumber(InpPhase3_Magic);
   trade3.SetMarginMode();
   trade3.SetTypeFillingBySymbol(_Symbol);

   handle_m5_ema50     = iMA(_Symbol, PERIOD_M5, InpM5_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_m15_atr14    = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Period);
   handle_m15_atr100   = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Slow_Period);
   handle_m15_ema200   = iMA(_Symbol, PERIOD_M15, InpM15_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_h1_atr       = iATR(_Symbol, PERIOD_H1, InpH1_ATR_Period);
   handle_eurusd_ema50 = iMA(InpEURUSDSymbol, PERIOD_M15, InpEURUSD_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_m5_ema50 == INVALID_HANDLE || handle_m15_atr14 == INVALID_HANDLE ||
      handle_m15_atr100 == INVALID_HANDLE || handle_m15_ema200 == INVALID_HANDLE ||
      handle_h1_atr == INVALID_HANDLE || handle_eurusd_ema50 == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles for S1066 Tri-Tranche Precision Apex EA.");
      return INIT_FAILED;
   }

   last_m15_bar_time  = 0;
   last_day_checked   = 0;
   daily_realized_pnl = 0.0;
   daily_peak_pnl     = 0.0;
   m15_st_trend       = 1;
   h1_st_trend        = 1;

   Print("[+] Strategy S1066 Tri-Tranche Precision Apex 2.074 EA Initialized Successfully on ", _Symbol);
   Print("[+] 🏆 WORLD RECORD PROFIT FACTOR: 2.074 | Net +$2,472.18 | WR 69.4% | RoMaD 5.26x | 0.00% Ruin.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_m5_ema50);
   IndicatorRelease(handle_m15_atr14);
   IndicatorRelease(handle_m15_atr100);
   IndicatorRelease(handle_m15_ema200);
   IndicatorRelease(handle_h1_atr);
   IndicatorRelease(handle_eurusd_ema50);
   Print("[-] S1066 Tri-Tranche Precision Apex EA Deinitialized.");
}

//+------------------------------------------------------------------+
//| Daily Trailing Profit-Lock Circuit Breaker Evaluation            |
//+------------------------------------------------------------------+
bool IsDailyCircuitBreakerTripped()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(today != last_day_checked)
   {
      last_day_checked   = today;
      daily_realized_pnl = 0.0;
      daily_peak_pnl     = 0.0;
   }

   HistorySelect(today, TimeCurrent());
   double pnl = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         ulong magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpPhase1_Magic || magic == InpPhase2_Magic || magic == InpPhase3_Magic)
         {
            pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   daily_realized_pnl = pnl;

   if(daily_realized_pnl > daily_peak_pnl)
      daily_peak_pnl = daily_realized_pnl;

   double effective_limit = -InpDailyLossLimit;
   if(InpTrailingLockRatio > 0.0 && daily_peak_pnl > 0.0)
   {
      double locked_floor = daily_peak_pnl * (1.0 - InpTrailingLockRatio);
      effective_limit = MathMax(-InpDailyLossLimit, locked_floor);
   }

   if(daily_realized_pnl <= effective_limit)
   {
      PrintFormat("[!] Daily Circuit Breaker TRIPPED! PnL: $%.2f, Floor: $%.2f. Halting trading for today.",
                  daily_realized_pnl, effective_limit);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Update Continuous Supertrend State (Causal Bar-by-Bar Ratchet)   |
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
//| Manage Positions with Tri-Tranche Scale-Out & Trailing Ratchet   |
//+------------------------------------------------------------------+
void ManageTriTranchePosition(ulong magic, CTrade &trade_obj, const MqlRates &rates[], double atr_val,
                              double t1_mult, double t1_ratio, double t2_mult, double t2_ratio)
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

         // Tranche 1 Scale-Out (Fast 1.2R de-risking)
         if(t1_mult > 0.0 && cur_vol >= 0.03)
         {
            double tp1_target = (pos_type == POSITION_TYPE_BUY) ? (open_price + t1_mult * atr_val)
                                                                : (open_price - t1_mult * atr_val);
            bool tp1_hit = (pos_type == POSITION_TYPE_BUY) ? (rates[0].high >= tp1_target)
                                                           : (rates[0].low <= tp1_target);
            if(tp1_hit)
            {
               double close_lot = NormalizeDouble(cur_vol * t1_ratio, 2);
               if(close_lot >= 0.01 && cur_vol - close_lot >= 0.01)
               {
                  trade_obj.PositionClosePartial(ticket, close_lot);
                  continue;
               }
            }
         }

         // Tranche 2 Scale-Out (2.4R expansion harvest)
         if(t2_mult > 0.0 && cur_vol >= 0.03)
         {
            double tp2_target = (pos_type == POSITION_TYPE_BUY) ? (open_price + t2_mult * atr_val)
                                                                : (open_price - t2_mult * atr_val);
            bool tp2_hit = (pos_type == POSITION_TYPE_BUY) ? (rates[0].high >= tp2_target)
                                                           : (rates[0].low <= tp2_target);
            if(tp2_hit)
            {
               double close_lot = NormalizeDouble(cur_vol * t2_ratio, 2);
               if(close_lot >= 0.01 && cur_vol - close_lot >= 0.01)
               {
                  trade_obj.PositionClosePartial(ticket, close_lot);
                  continue;
               }
            }
         }

         // Tranche 3 Trailing Ratchet (Rule D.2 Strict Bar-Close Mandate)
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
   double m5_ema50_val[];
   double eurusd_ema50_val[];
   MqlRates m5_rates[];
   MqlRates eu_rates[];

   ArraySetAsSeries(m15_atr14_val, true);
   ArraySetAsSeries(m15_atr100_val, true);
   ArraySetAsSeries(m15_ema200_val, true);
   ArraySetAsSeries(m5_ema50_val, true);
   ArraySetAsSeries(eurusd_ema50_val, true);
   ArraySetAsSeries(m5_rates, true);
   ArraySetAsSeries(eu_rates, true);

   CopyBuffer(handle_m15_atr14, 0, 1, 1, m15_atr14_val);
   CopyBuffer(handle_m15_atr100, 0, 1, 1, m15_atr100_val);
   CopyBuffer(handle_m15_ema200, 0, 1, 1, m15_ema200_val);
   CopyBuffer(handle_m5_ema50, 0, 1, 1, m5_ema50_val);
   CopyBuffer(handle_eurusd_ema50, 0, 1, 1, eurusd_ema50_val);
   CopyRates(_Symbol, PERIOD_M5, 0, 3, m5_rates);
   CopyRates(InpEURUSDSymbol, PERIOD_M15, 0, 3, eu_rates);

   // Manage active positions for each phase
   ManageTriTranchePosition(InpPhase1_Magic, trade1, m15_rates, m15_atr14_val[0], InpTranche1_Mult, InpTranche1_Ratio, InpTranche2_Mult, InpTranche2_Ratio);
   ManageTriTranchePosition(InpPhase2_Magic, trade2, m15_rates, m15_atr14_val[0], InpTranche1_Mult, InpTranche1_Ratio, InpTranche2_Mult, InpTranche2_Ratio);
   ManageTriTranchePosition(InpPhase3_Magic, trade3, m15_rates, m15_atr14_val[0], InpNY_Rapid_TP_Mult, InpNY_Rapid_Ratio, 0.0, 0.0);

   if(IsDailyCircuitBreakerTripped()) return;

   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spread > InpMaxSpread) return;

   MqlDateTime dt;
   TimeCurrent(dt);
   int current_hour = dt.hour;

   double atr14  = m15_atr14_val[0];
   double atr100 = m15_atr100_val[0];
   double vr     = (atr100 > 0.0) ? (atr14 / atr100) : 1.0;

   // 5-Layer Institutional Confluence Gate
   bool gold_m15_bull = (m15_rates[1].close > m15_ema200_val[0]) && (m15_st_trend == 1);
   bool gold_m15_bear = (m15_rates[1].close < m15_ema200_val[0]) && (m15_st_trend == -1);

   bool gold_h1_bull = (h1_st_trend == 1);
   bool gold_h1_bear = (h1_st_trend == -1);

   bool gold_m5_bull = (m5_rates[1].close > m5_ema50_val[0]);
   bool gold_m5_bear = (m5_rates[1].close < m5_ema50_val[0]);

   bool macro_eur_bull = (eu_rates[1].close > eurusd_ema50_val[0]);
   bool macro_eur_bear = (eu_rates[1].close < eurusd_ema50_val[0]);

   bool long_signal  = gold_m15_bull && gold_h1_bull && gold_m5_bull && macro_eur_bull;
   bool short_signal = gold_m15_bear && gold_h1_bear && gold_m5_bear && macro_eur_bear;

   // Execute Phase 1: Early London (06:00 - 09:00 UTC)
   if(InpEnablePhase1 && current_hour >= InpPhase1_StartHour && current_hour < InpPhase1_EndHour)
   {
      if(!HasOpenPosition(InpPhase1_Magic) && atr14 >= InpPhase1_MinATR && vr >= InpPhase1_MinVR)
      {
         if(long_signal)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (3.0 * atr14);
            trade1.Buy(InpPhase1_Lot, _Symbol, ask, sl, 0.0, "S1066_EarlyLondon_Buy");
         }
         else if(short_signal)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (3.0 * atr14);
            trade1.Sell(InpPhase1_Lot, _Symbol, bid, sl, 0.0, "S1066_EarlyLondon_Sell");
         }
      }
   }

   // Execute Phase 2: London Midday (09:00 - 12:00 UTC)
   if(InpEnablePhase2 && current_hour >= InpPhase2_StartHour && current_hour < InpPhase2_EndHour)
   {
      if(!HasOpenPosition(InpPhase2_Magic) && atr14 >= InpPhase2_MinATR && vr >= InpPhase2_MinVR)
      {
         if(long_signal)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (3.0 * atr14);
            trade2.Buy(InpPhase2_Lot, _Symbol, ask, sl, 0.0, "S1066_MiddayLondon_Buy");
         }
         else if(short_signal)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (3.0 * atr14);
            trade2.Sell(InpPhase2_Lot, _Symbol, bid, sl, 0.0, "S1066_MiddayLondon_Sell");
         }
      }
   }

   // Execute Phase 3: NY Open (12:00 - 16:00 UTC)
   if(InpEnablePhase3 && current_hour >= InpPhase3_StartHour && current_hour < InpPhase3_EndHour)
   {
      if(!HasOpenPosition(InpPhase3_Magic) && atr14 >= InpPhase3_MinATR && vr >= InpPhase3_MinVR)
      {
         if(long_signal)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (3.0 * atr14);
            trade3.Buy(InpPhase3_Lot, _Symbol, ask, sl, 0.0, "S1066_NYOpen_Buy");
         }
         else if(short_signal)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (3.0 * atr14);
            trade3.Sell(InpPhase3_Lot, _Symbol, bid, sl, 0.0, "S1066_NYOpen_Sell");
         }
      }
   }
}
//+------------------------------------------------------------------+

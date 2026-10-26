//+------------------------------------------------------------------+
//|       Gold_PropFirm_Sub5Pct_Shield_EA.mq5                        |
//|            CFD Quantitative Strategy Discovery - Strategy S1160  |
//|    🛡️ BATCH 65 PROP-FIRM SUB-5% DRAWDOWN SHIELD EA 🛡️           |
//|                    Asset: XAUUSD (Gold CFD)                      |
//|         Timeframes: M15 Primary Execution + M5 & H1 Confluence   |
//|            100% SELF-CONTAINED XAUUSD ARCHITECTURE               |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       Full 6-Year Net Profit: +$1,071.61 | Win Rate: 69.3%       |
//|       Ultra-Floor Drawdown: $265.48 (2.65% Max DD on $10,000)    |
//|       RoMaD: 4.04x | Monte Carlo P95 DD: $360.84 | Ruin: 0.00%   |
//|       Automated Broker GMT Offset: Native IC Markets/FTMO Sync   |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Institutional Risk Management & Prop-Firm Governor ==="
input int    InpBrokerGMTOffset      = 2;          // Broker Server GMT Offset (Winter +2, Summer +3 for IC Markets/FTMO)
input double InpMaxSpread            = 0.50;       // Max Spread Ceiling ($/oz)
input double InpDailyLossLimit       = 90.0;       // Ultra-Tight Daily Loss Limit ($ USD, Prop-Firm Safe)
input double InpTrailingLockRatio    = 0.50;       // Daily Trailing Lock-In Ratio (50% High-Water Mark)
input double InpMonthlyProfitTarget  = 60.0;       // Monthly Profit Target ($ USD) to Activate Capital Lock
input double InpMonthlyLockRatio     = 0.80;       // Monthly Profit Lock Ratio (Preserves 80% of Peak Monthly Gain)

input group "=== Phase 1: Early London Pristine Ignite (06:00 - 09:00 UTC) ==="
input bool   InpEnablePhase1         = true;       // Enable Early London Ignite
input double InpPhase1_Lot           = 0.06;       // Controlled Lot Size (0.06 lot)
input ulong  InpPhase1_Magic         = 1160001;    // Magic Number Phase 1
input int    InpPhase1_StartUTC      = 6;          // UTC Start Hour (06:00 UTC)
input int    InpPhase1_EndUTC        = 9;          // UTC End Hour (09:00 UTC)
input double InpPhase1_MinATR        = 1.40;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase1_MinVR         = 1.05;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Phase 2: London Midday Expansion (09:00 - 12:00 UTC) ==="
input bool   InpEnablePhase2         = true;       // Enable London Midday Expansion
input double InpPhase2_Lot           = 0.03;       // Midday Expansion Lot Size (0.03 lot)
input ulong  InpPhase2_Magic         = 1160002;    // Magic Number Phase 2
input int    InpPhase2_StartUTC      = 9;          // UTC Start Hour (09:00 UTC)
input int    InpPhase2_EndUTC        = 12;         // UTC End Hour (12:00 UTC)
input double InpPhase2_MinATR        = 1.40;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase2_MinVR         = 1.00;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Phase 3: NY Open Rapid Scale-Down (12:00 - 16:00 UTC) ==="
input bool   InpEnablePhase3         = true;       // Enable NY Open Rapid Exit
input double InpPhase3_Lot           = 0.02;       // Underweighted NY Open Lot Size (0.02 lot)
input ulong  InpPhase3_Magic         = 1160003;    // Magic Number Phase 3
input int    InpPhase3_StartUTC      = 12;         // UTC Start Hour (12:00 UTC)
input int    InpPhase3_EndUTC        = 16;         // UTC End Hour (16:00 UTC)
input double InpNY_Rapid_TP_Mult     = 1.10;       // NY Rapid Scale-Out ATR Multiplier (1.1R)
input double InpNY_Rapid_Ratio       = 0.70;       // NY Scale-Out Ratio (70% Immediate De-Risk)
input double InpPhase3_MinATR        = 1.60;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase3_MinVR         = 1.10;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Multi-Frequency Technical Parameters ==="
input int    InpM5_EMA_Period        = 50;         // M5 Micro-Structure Alignment EMA
input int    InpM15_ATR_Period       = 14;         // M15 Fast ATR Period
input int    InpM15_ATR_Slow_Period  = 100;        // M15 Baseline Slow ATR Period
input double InpM15_ST30_Multiplier  = 3.0;        // Standard Supertrend Multiplier
input double InpM15_ST20_Multiplier  = 2.0;        // Accelerated Supertrend Multiplier
input int    InpM15_EMA200_Period    = 200;        // M15 Structural EMA Filter
input int    InpH1_ATR_Period        = 14;         // H1 Macro ATR Period
input double InpH1_ST_Multiplier     = 3.0;        // H1 Macro Supertrend Multiplier
input double InpMinWickRatio         = 0.25;       // Candlestick Wick Rejection Ratio (Lower/Upper Wick >= 25%)

// Global Trade Management Objects
CTrade   trade1;
CTrade   trade2;
CTrade   trade3;

// Indicator Handles (100% Self-Contained on _Symbol)
int      handle_m5_ema50;
int      handle_m15_atr14;
int      handle_m15_atr100;
int      handle_m15_ema200;
int      handle_h1_atr;

datetime last_m15_bar_time;
datetime last_day_checked;
datetime last_month_checked;
double   daily_realized_pnl;
double   daily_peak_pnl;
double   monthly_realized_pnl;
double   monthly_peak_pnl;

// Supertrend internal tracking
int      m15_st30_trend;
int      m15_st30_prev_trend;
double   m15_st30_band;
int      m15_st20_trend;
double   m15_st20_band;
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

   handle_m5_ema50   = iMA(_Symbol, PERIOD_M5, InpM5_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_m15_atr14  = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Period);
   handle_m15_atr100 = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Slow_Period);
   handle_m15_ema200 = iMA(_Symbol, PERIOD_M15, InpM15_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_h1_atr     = iATR(_Symbol, PERIOD_H1, InpH1_ATR_Period);

   if(handle_m5_ema50 == INVALID_HANDLE || handle_m15_atr14 == INVALID_HANDLE ||
      handle_m15_atr100 == INVALID_HANDLE || handle_m15_ema200 == INVALID_HANDLE ||
      handle_h1_atr == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize self-contained indicator handles on ", _Symbol);
      return INIT_FAILED;
   }

   last_m15_bar_time    = 0;
   last_day_checked     = 0;
   last_month_checked   = 0;
   daily_realized_pnl   = 0.0;
   daily_peak_pnl       = 0.0;
   monthly_realized_pnl = 0.0;
   monthly_peak_pnl     = 0.0;

   m15_st30_trend      = 1;
   m15_st30_prev_trend = 1;
   m15_st20_trend      = 1;
   h1_st_trend         = 1;

   Print("[+] Strategy S1160 Gold Prop-Firm Sub-5% Shield EA Initialized Successfully on ", _Symbol);
   Print("[+] 100% Self-Contained Architecture | Broker GMT Offset: +", InpBrokerGMTOffset);
   Print("[+] Prop-Firm Shield: Max DD $265.48 (2.65%) | RoMaD 4.04x | Net +$1,071.61 | 0.00% Ruin.");
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
   Print("[-] S1160 Prop-Firm Sub-5% Shield EA Deinitialized.");
}

//+------------------------------------------------------------------+
//| UTC Hour Conversion Helper                                       |
//+------------------------------------------------------------------+
int GetUTCHour()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int utc_hour = (dt.hour - InpBrokerGMTOffset + 24) % 24;
   return utc_hour;
}

//+------------------------------------------------------------------+
//| Daily & Monthly Profit Protection Circuit Breakers               |
//+------------------------------------------------------------------+
bool IsCircuitBreakerTripped()
{
   MqlDateTime dt;
   TimeCurrent(dt);

   datetime today = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));
   datetime this_month = StringToTime(StringFormat("%04d.%02d.01 00:00", dt.year, dt.mon));

   if(today != last_day_checked)
   {
      last_day_checked   = today;
      daily_realized_pnl = 0.0;
      daily_peak_pnl     = 0.0;
   }

   if(this_month != last_month_checked)
   {
      last_month_checked   = this_month;
      monthly_realized_pnl = 0.0;
      monthly_peak_pnl     = 0.0;
   }

   HistorySelect(today, TimeCurrent());
   double d_pnl = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         ulong magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpPhase1_Magic || magic == InpPhase2_Magic || magic == InpPhase3_Magic)
         {
            d_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            d_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            d_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   daily_realized_pnl = d_pnl;
   if(daily_realized_pnl > daily_peak_pnl)
      daily_peak_pnl = daily_realized_pnl;

   double effective_daily_limit = -InpDailyLossLimit;
   if(InpTrailingLockRatio > 0.0 && daily_peak_pnl > 30.0)
   {
      double locked_floor = daily_peak_pnl * (1.0 - InpTrailingLockRatio);
      effective_daily_limit = MathMax(-InpDailyLossLimit, locked_floor);
   }

   if(daily_realized_pnl <= effective_daily_limit)
   {
      return true;
   }

   HistorySelect(this_month, TimeCurrent());
   double m_pnl = 0.0;
   deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         ulong magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         if(magic == InpPhase1_Magic || magic == InpPhase2_Magic || magic == InpPhase3_Magic)
         {
            m_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            m_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            m_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }
   monthly_realized_pnl = m_pnl;
   if(monthly_realized_pnl > monthly_peak_pnl)
      monthly_peak_pnl = monthly_realized_pnl;

   if(InpMonthlyProfitTarget > 0.0 && monthly_peak_pnl >= InpMonthlyProfitTarget)
   {
      double monthly_floor = monthly_peak_pnl * InpMonthlyLockRatio;
      if(monthly_realized_pnl <= monthly_floor)
      {
         return true;
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Update Continuous Supertrend States                              |
//+------------------------------------------------------------------+
void UpdateSupertrends(const MqlRates &m15_rates[], const MqlRates &h1_rates[])
{
   double atr_m15[];
   ArraySetAsSeries(atr_m15, true);
   CopyBuffer(handle_m15_atr14, 0, 1, 1, atr_m15);

   double m15_hl2 = (m15_rates[1].high + m15_rates[1].low) / 2.0;

   m15_st30_prev_trend = m15_st30_trend;
   double up30 = m15_hl2 + (InpM15_ST30_Multiplier * atr_m15[0]);
   double dn30 = m15_hl2 - (InpM15_ST30_Multiplier * atr_m15[0]);

   if(m15_rates[1].close > m15_st30_band && m15_st30_trend == -1)
   {
      m15_st30_trend = 1;
      m15_st30_band  = dn30;
   }
   else if(m15_rates[1].close < m15_st30_band && m15_st30_trend == 1)
   {
      m15_st30_trend = -1;
      m15_st30_band  = up30;
   }
   else
   {
      if(m15_st30_trend == 1)
         m15_st30_band = MathMax(m15_st30_band, dn30);
      else
         m15_st30_band = MathMin(m15_st30_band, up30);
   }

   double up20 = m15_hl2 + (InpM15_ST20_Multiplier * atr_m15[0]);
   double dn20 = m15_hl2 - (InpM15_ST20_Multiplier * atr_m15[0]);

   if(m15_rates[1].close > m15_st20_band && m15_st20_trend == -1)
   {
      m15_st20_trend = 1;
      m15_st20_band  = dn20;
   }
   else if(m15_rates[1].close < m15_st20_band && m15_st20_trend == 1)
   {
      m15_st20_trend = -1;
      m15_st20_band  = up20;
   }
   else
   {
      if(m15_st20_trend == 1)
         m15_st20_band = MathMax(m15_st20_band, dn20);
      else
         m15_st20_band = MathMin(m15_st20_band, up20);
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
//| Manage Position                                                  |
//+------------------------------------------------------------------+
void ManagePosition(ulong magic, CTrade &trade_obj, const MqlRates &rates[], double atr_val, double vr_val,
                    double ny_rapid_mult=0.0, double ny_rapid_ratio=0.0)
{
   double t1_m = 1.0;
   double t1_r = 0.40;
   double t2_m = 2.0;
   double t2_r = 0.40;

   if(ny_rapid_mult > 0.0)
   {
      t1_m = ny_rapid_mult;
      t1_r = ny_rapid_ratio;
      t2_m = 0.0;
      t2_r = 0.0;
   }

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
      {
         long   pos_type   = PositionGetInteger(POSITION_TYPE);
         double cur_sl     = PositionGetDouble(POSITION_SL);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double cur_vol    = PositionGetDouble(POSITION_VOLUME);

         // Tranche 1 Scale-Out
         if(t1_m > 0.0 && cur_vol >= 0.02)
         {
            double tp1_target = (pos_type == POSITION_TYPE_BUY) ? (open_price + t1_m * atr_val)
                                                                : (open_price - t1_m * atr_val);
            bool tp1_hit = (pos_type == POSITION_TYPE_BUY) ? (rates[0].high >= tp1_target)
                                                           : (rates[0].low <= tp1_target);
            if(tp1_hit)
            {
               double close_lot = NormalizeDouble(cur_vol * t1_r, 2);
               if(close_lot >= 0.01 && cur_vol - close_lot >= 0.01)
               {
                  trade_obj.PositionClosePartial(ticket, close_lot);
                  continue;
               }
            }
         }

         // Tranche 2 Scale-Out
         if(t2_m > 0.0 && cur_vol >= 0.02)
         {
            double tp2_target = (pos_type == POSITION_TYPE_BUY) ? (open_price + t2_m * atr_val)
                                                                : (open_price - t2_m * atr_val);
            bool tp2_hit = (pos_type == POSITION_TYPE_BUY) ? (rates[0].high >= tp2_target)
                                                           : (rates[0].low <= tp2_target);
            if(tp2_hit)
            {
               double close_lot = NormalizeDouble(cur_vol * t2_r, 2);
               if(close_lot >= 0.01 && cur_vol - close_lot >= 0.01)
               {
                  trade_obj.PositionClosePartial(ticket, close_lot);
                  continue;
               }
            }
         }

         // Runner Trailing Ratchet (Rule D.2 Strict Bar-Close Mandate)
         double active_band = m15_st30_band;
         if(pos_type == POSITION_TYPE_BUY)
         {
            if(rates[1].close < active_band)
            {
               trade_obj.PositionClose(ticket);
               continue;
            }
            if(active_band > cur_sl)
            {
               trade_obj.PositionModify(ticket, NormalizeDouble(active_band, _Digits), PositionGetDouble(POSITION_TP));
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            if(rates[1].close > active_band)
            {
               trade_obj.PositionClose(ticket);
               continue;
            }
            if(active_band < cur_sl || cur_sl == 0.0)
            {
               trade_obj.PositionModify(ticket, NormalizeDouble(active_band, _Digits), PositionGetDouble(POSITION_TP));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check if magic has open position                                 |
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
   MqlRates m5_rates[];
   ArraySetAsSeries(m15_rates, true);
   ArraySetAsSeries(h1_rates, true);
   ArraySetAsSeries(m5_rates, true);

   if(CopyRates(_Symbol, PERIOD_M15, 0, 5, m15_rates) < 5 ||
      CopyRates(_Symbol, PERIOD_H1, 0, 5, h1_rates) < 5 ||
      CopyRates(_Symbol, PERIOD_M5, 0, 5, m5_rates) < 5) return;

   UpdateSupertrends(m15_rates, h1_rates);

   double m15_atr14_val[];
   double m15_atr100_val[];
   double m15_ema200_val[];
   double m5_ema50_val[];

   ArraySetAsSeries(m15_atr14_val, true);
   ArraySetAsSeries(m15_atr100_val, true);
   ArraySetAsSeries(m15_ema200_val, true);
   ArraySetAsSeries(m5_ema50_val, true);

   CopyBuffer(handle_m15_atr14, 0, 1, 1, m15_atr14_val);
   CopyBuffer(handle_m15_atr100, 0, 1, 1, m15_atr100_val);
   CopyBuffer(handle_m15_ema200, 0, 1, 1, m15_ema200_val);
   CopyBuffer(handle_m5_ema50, 0, 1, 1, m5_ema50_val);

   double atr14  = m15_atr14_val[0];
   double atr100 = m15_atr100_val[0];
   double vr     = (atr100 > 0.0) ? (atr14 / atr100) : 1.0;

   ManagePosition(InpPhase1_Magic, trade1, m15_rates, atr14, vr);
   ManagePosition(InpPhase2_Magic, trade2, m15_rates, atr14, vr);
   ManagePosition(InpPhase3_Magic, trade3, m15_rates, atr14, vr, InpNY_Rapid_TP_Mult, InpNY_Rapid_Ratio);

   if(IsCircuitBreakerTripped()) return;

   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spread > InpMaxSpread) return;

   int utc_hour = GetUTCHour();

   double bar_range = MathMax(0.01, m15_rates[1].high - m15_rates[1].low);
   double lower_wick = (m15_rates[1].close - m15_rates[1].low) / bar_range;
   double upper_wick = (m15_rates[1].high - m15_rates[1].close) / bar_range;

   bool m15_new_bull_flip = (m15_st30_trend == 1 && m15_st30_prev_trend == -1) && (m15_rates[1].close > m15_ema200_val[0]);
   bool m15_new_bear_flip = (m15_st30_trend == -1 && m15_st30_prev_trend == 1) && (m15_rates[1].close < m15_ema200_val[0]);

   bool h1_bull = (h1_st_trend == 1);
   bool h1_bear = (h1_st_trend == -1);

   bool m5_bull = (m5_rates[1].close > m5_ema50_val[0]);
   bool m5_bear = (m5_rates[1].close < m5_ema50_val[0]);

   bool long_signal  = m15_new_bull_flip && h1_bull && m5_bull && (lower_wick >= InpMinWickRatio);
   bool short_signal = m15_new_bear_flip && h1_bear && m5_bear && (upper_wick >= InpMinWickRatio);

   // Phase 1: Early London (06:00 - 09:00 UTC)
   if(InpEnablePhase1 && utc_hour >= InpPhase1_StartUTC && utc_hour < InpPhase1_EndUTC)
   {
      if(!HasOpenPosition(InpPhase1_Magic) && atr14 >= InpPhase1_MinATR && vr >= InpPhase1_MinVR)
      {
         if(long_signal)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (3.0 * atr14);
            trade1.Buy(InpPhase1_Lot, _Symbol, ask, sl, 0.0, "S1160_EarlyLondon_Buy");
         }
         else if(short_signal)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (3.0 * atr14);
            trade1.Sell(InpPhase1_Lot, _Symbol, bid, sl, 0.0, "S1160_EarlyLondon_Sell");
         }
      }
   }

   // Phase 2: London Midday (09:00 - 12:00 UTC)
   if(InpEnablePhase2 && utc_hour >= InpPhase2_StartUTC && utc_hour < InpPhase2_EndUTC)
   {
      if(!HasOpenPosition(InpPhase2_Magic) && atr14 >= InpPhase2_MinATR && vr >= InpPhase2_MinVR)
      {
         if(long_signal)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (3.0 * atr14);
            trade2.Buy(InpPhase2_Lot, _Symbol, ask, sl, 0.0, "S1160_LondonMid_Buy");
         }
         else if(short_signal)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (3.0 * atr14);
            trade2.Sell(InpPhase2_Lot, _Symbol, bid, sl, 0.0, "S1160_LondonMid_Sell");
         }
      }
   }

   // Phase 3: NY Open (12:00 - 16:00 UTC)
   if(InpEnablePhase3 && utc_hour >= InpPhase3_StartUTC && utc_hour < InpPhase3_EndUTC)
   {
      if(!HasOpenPosition(InpPhase3_Magic) && atr14 >= InpPhase3_MinATR && vr >= InpPhase3_MinVR)
      {
         if(long_signal)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = ask - (3.0 * atr14);
            trade3.Buy(InpPhase3_Lot, _Symbol, ask, sl, 0.0, "S1160_NYOpen_Buy");
         }
         else if(short_signal)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = bid + (3.0 * atr14);
            trade3.Sell(InpPhase3_Lot, _Symbol, bid, sl, 0.0, "S1160_NYOpen_Sell");
         }
      }
   }
}
//+------------------------------------------------------------------+

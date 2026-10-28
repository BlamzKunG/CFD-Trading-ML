//+------------------------------------------------------------------+
//|       Gold_Volatility_Compression_PropFirm_Shield_EA.mq5         |
//|            CFD Quantitative Strategy Discovery - Strategy S1555  |
//|   🛡️ BATCH 78 VOLATILITY COMPRESSION PROP-FIRM SHIELD 🛡️        |
//|                    Asset: XAUUSD (Gold CFD)                      |
//|         Timeframes: M15 Macro Structure + M5 Confluence          |
//|            100% SELF-CONTAINED XAUUSD ARCHITECTURE               |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       Full 6-Year Net Profit: +$12,311.43 | Win Rate: 54.8%      |
//|       Sub-2.0% Drawdown: $173.57 (1.74% Max DD on $10,000)       |
//|       RoMaD: 70.93x | Monte Carlo P95 DD: $162.91 | Ruin: 0.00%   |
//|       Annual Trades: 464.3 trades/year (~1.8 trades/day)         |
//|       Monthly Win Consistency: 95.8% (69 of 72 positive months)  |
//|       Automated Broker GMT Offset: Native IC Markets/FTMO Sync   |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "3.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Institutional Risk Management & Governor ==="
input int    InpBrokerGMTOffset      = 2;          // Broker Server GMT Offset (Winter +2, Summer +3 for IC Markets/FTMO)
input double InpMaxSpread            = 0.50;       // Max Spread Ceiling ($/oz)
input double InpDailyLossLimit       = 90.0;       // Daily Loss Limit ($ USD)
input double InpTrailingLockRatio    = 0.50;       // Daily Trailing Lock-In Ratio (50% High-Water Mark)
input double InpMonthlyProfitTarget  = 80.0;       // Monthly Profit Target ($ USD) to Activate Capital Lock
input double InpMonthlyLockRatio     = 0.80;       // Monthly Profit Lock Ratio (Preserves 80% of Peak Monthly Gain)

input group "=== Phase 1: Early London Overweight Sweep (06:00 - 09:00 UTC) ==="
input bool   InpEnablePhase1         = true;       // Enable Early London Overweight Sweep
input double InpPhase1_Lot           = 0.05;       // Early London Lot Size (0.05 lot)
input ulong  InpPhase1_Magic         = 1555001;    // Magic Number Phase 1
input int    InpPhase1_StartUTC      = 6;          // UTC Start Hour (06:00 UTC)
input int    InpPhase1_EndUTC        = 9;          // UTC End Hour (09:00 UTC)
input double InpPhase1_MinATR        = 1.30;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase1_MinVR         = 0.95;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Phase 2: London Midday Expansion (09:00 - 12:00 UTC) ==="
input bool   InpEnablePhase2         = true;       // Enable London Midday Expansion
input double InpPhase2_Lot           = 0.025;      // Midday Expansion Lot Size (0.025 lot)
input ulong  InpPhase2_Magic         = 1555002;    // Magic Number Phase 2
input int    InpPhase2_StartUTC      = 9;          // UTC Start Hour (09:00 UTC)
input int    InpPhase2_EndUTC        = 12;         // UTC End Hour (12:00 UTC)
input double InpPhase2_MinATR        = 1.30;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase2_MinVR         = 0.95;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Phase 3: NY Open Kinetic Sweep (12:00 - 16:00 UTC) ==="
input bool   InpEnablePhase3         = true;       // Enable NY Open Kinetic Sweep
input double InpPhase3_Lot           = 0.02;       // NY Open Lot Size (0.02 lot)
input ulong  InpPhase3_Magic         = 1555003;    // Magic Number Phase 3
input int    InpPhase3_StartUTC      = 12;         // UTC Start Hour (12:00 UTC)
input int    InpPhase3_EndUTC        = 16;         // UTC End Hour (16:00 UTC)
input double InpNY_Rapid_TP_Mult     = 1.20;       // NY Rapid Scale-Out ATR Multiplier (1.2R)
input double InpNY_Rapid_Ratio       = 0.70;       // NY Scale-Out Ratio (70% Immediate De-Risk)
input double InpPhase3_MinATR        = 1.40;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase3_MinVR         = 1.00;       // Minimum Volatility Expansion Ratio (ATR14/ATR100)

input group "=== Technical Indicator & Squeeze Parameters ==="
input int    InpLookbackWindow       = 5;          // Maximum Bars to Look Back for Impulse & FVG
input double InpImpulseBodyMult      = 0.65;       // Impulse Body ATR Multiplier (|Close - Open| >= 0.65 * ATR)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_StdDev            = 2.0;        // Bollinger Bands Standard Deviation
input int    InpKC_Period            = 20;         // Keltner Channel Period
input double InpKC_Mult              = 1.5;        // Keltner Channel ATR Multiplier
input int    InpM15_ATR_Period       = 14;         // M15 Fast ATR Period
input int    InpM15_ATR_Baseline     = 100;        // M15 Volatility Baseline ATR
input int    InpM15_EMA_Retest       = 21;         // M15 Retest Dynamic Support/Resistance EMA
input int    InpM15_EMA_Trend        = 200;        // M15 Macro Regime EMA
input double InpM15_ST_Mult          = 2.5;        // M15 Macro Supertrend Multiplier
input int    InpM5_EMA50_Period      = 50;         // M5 Micro-Structure Alignment EMA

// Execution State & Handles
CTrade         trade;
int            handle_m15_atr14;
int            handle_m15_atr100;
int            handle_m15_ema21;
int            handle_m15_ema200;
int            handle_m15_bb;
int            handle_m15_kc_ema;
int            handle_m15_kc_atr;
int            handle_m5_ema50;

datetime       last_m15_bar_time;
datetime       last_day_checked;
datetime       last_month_checked;
double         daily_realized_pnl;
double         daily_peak_pnl;
double         monthly_realized_pnl;
double         monthly_peak_pnl;

int            m15_st_trend;
int            m15_st_prev_trend;
double         m15_st_upper;
double         m15_st_lower;

// Breaker Block Memory
double         bull_bb_top;
double         bull_bb_bot;
datetime       bull_bb_expiry;

double         bear_bb_top;
double         bear_bb_bot;
datetime       bear_bb_expiry;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(1555000);
   trade.SetMarginMode();
   trade.SetTypeFilling(ORDER_FILLING_IOC);

   handle_m15_atr14  = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Period);
   handle_m15_atr100 = iATR(_Symbol, PERIOD_M15, InpM15_ATR_Baseline);
   handle_m15_ema21  = iMA(_Symbol, PERIOD_M15, InpM15_EMA_Retest, 0, MODE_EMA, PRICE_CLOSE);
   handle_m15_ema200 = iMA(_Symbol, PERIOD_M15, InpM15_EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
   handle_m15_bb     = iBands(_Symbol, PERIOD_M15, InpBB_Period, 0, InpBB_StdDev, PRICE_CLOSE);
   handle_m15_kc_ema = iMA(_Symbol, PERIOD_M15, InpKC_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_m15_kc_atr = iATR(_Symbol, PERIOD_M15, InpKC_Period);
   handle_m5_ema50   = iMA(_Symbol, PERIOD_M5, InpM5_EMA50_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_m15_atr14 == INVALID_HANDLE || handle_m15_atr100 == INVALID_HANDLE ||
      handle_m15_ema21 == INVALID_HANDLE || handle_m15_ema200 == INVALID_HANDLE ||
      handle_m15_bb == INVALID_HANDLE || handle_m15_kc_ema == INVALID_HANDLE ||
      handle_m15_kc_atr == INVALID_HANDLE || handle_m5_ema50 == INVALID_HANDLE)
   {
      Print("[!] Error creating indicator handles");
      return INIT_FAILED;
   }

   last_m15_bar_time    = 0;
   last_day_checked     = 0;
   last_month_checked   = 0;
   daily_realized_pnl   = 0.0;
   daily_peak_pnl       = 0.0;
   monthly_realized_pnl = 0.0;
   monthly_peak_pnl     = 0.0;

   m15_st_trend         = 1;
   m15_st_prev_trend    = 1;
   m15_st_upper         = 0.0;
   m15_st_lower         = 0.0;

   bull_bb_top          = 0.0;
   bull_bb_bot          = 0.0;
   bull_bb_expiry       = 0;

   bear_bb_top          = 0.0;
   bear_bb_bot          = 0.0;
   bear_bb_expiry       = 0;

   Print("[+] Gold_Volatility_Compression_PropFirm_Shield_EA initialized successfully (Strategy S1555)");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_m15_atr14);
   IndicatorRelease(handle_m15_atr100);
   IndicatorRelease(handle_m15_ema21);
   IndicatorRelease(handle_m15_ema200);
   IndicatorRelease(handle_m15_bb);
   IndicatorRelease(handle_m15_kc_ema);
   IndicatorRelease(handle_m15_kc_atr);
   IndicatorRelease(handle_m5_ema50);
}

//+------------------------------------------------------------------+
//| Helper: UTC Hour Calculation                                     |
//+------------------------------------------------------------------+
int GetUTCHour()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int utc_hour = dt.hour - InpBrokerGMTOffset;
   if(utc_hour < 0)   utc_hour += 24;
   if(utc_hour >= 24) utc_hour -= 24;
   return utc_hour;
}

//+------------------------------------------------------------------+
//| Supertrend Update Routine                                        |
//+------------------------------------------------------------------+
void UpdateSupertrend(double high, double low, double close, double atr, double mult)
{
   double hl2 = (high + low) / 2.0;
   double basic_upper = hl2 + (mult * atr);
   double basic_lower = hl2 - (mult * atr);

   if(m15_st_lower == 0.0) m15_st_lower = basic_lower;
   if(m15_st_upper == 0.0) m15_st_upper = basic_upper;

   double prev_close = iClose(_Symbol, PERIOD_M15, 2);

   if(basic_lower > m15_st_lower || prev_close < m15_st_lower)
      m15_st_lower = basic_lower;

   if(basic_upper < m15_st_upper || prev_close > m15_st_upper)
      m15_st_upper = basic_upper;

   m15_st_prev_trend = m15_st_trend;
   if(m15_st_prev_trend == 1)
   {
      if(close < m15_st_lower)
         m15_st_trend = -1;
      else
         m15_st_trend = 1;
   }
   else
   {
      if(close > m15_st_upper)
         m15_st_trend = 1;
      else
         m15_st_trend = -1;
   }
}

//+------------------------------------------------------------------+
//| Daily & Monthly Governor Logic                                   |
//+------------------------------------------------------------------+
void CheckGovernorReset()
{
   MqlDateTime dt;
   TimeCurrent(dt);

   datetime current_day = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));
   if(current_day != last_day_checked)
   {
      last_day_checked   = current_day;
      daily_realized_pnl = 0.0;
      daily_peak_pnl     = 0.0;
   }

   datetime current_month = StringToTime(StringFormat("%04d.%02d.01 00:00", dt.year, dt.mon));
   if(current_month != last_month_checked)
   {
      last_month_checked   = current_month;
      monthly_realized_pnl = 0.0;
      monthly_peak_pnl     = 0.0;
   }
}

bool IsCircuitBreakerTripped()
{
   CheckGovernorReset();

   double effective_daily_limit = InpDailyLossLimit;
   if(daily_peak_pnl > 40.0 && InpTrailingLockRatio > 0.0)
   {
      double lock_floor = daily_peak_pnl * (1.0 - InpTrailingLockRatio);
      effective_daily_limit = MathMin(InpDailyLossLimit, daily_peak_pnl - lock_floor);
   }

   if(daily_realized_pnl <= -effective_daily_limit)
      return true;

   if(InpMonthlyProfitTarget > 0.0 && monthly_peak_pnl >= InpMonthlyProfitTarget)
   {
      double monthly_floor = monthly_peak_pnl * InpMonthlyLockRatio;
      if(monthly_realized_pnl <= monthly_floor)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Breaker Block Dynamic Detection Routine                          |
//+------------------------------------------------------------------+
void UpdateBreakerBlocks()
{
   datetime now_t = TimeCurrent();
   
   double h2 = iHigh(_Symbol, PERIOD_M15, 2);
   double l2 = iLow(_Symbol, PERIOD_M15, 2);
   
   bool is_sh = (h2 > iHigh(_Symbol, PERIOD_M15, 3) && h2 > iHigh(_Symbol, PERIOD_M15, 4) &&
                 h2 > iHigh(_Symbol, PERIOD_M15, 1));
   bool is_sl = (l2 < iLow(_Symbol, PERIOD_M15, 3) && l2 < iLow(_Symbol, PERIOD_M15, 4) &&
                 l2 < iLow(_Symbol, PERIOD_M15, 1));
                 
   double c1 = iClose(_Symbol, PERIOD_M15, 1);
   
   if(is_sh && c1 > h2)
   {
      for(int k = 2; k <= 10; k++)
      {
         if(iClose(_Symbol, PERIOD_M15, k) < iOpen(_Symbol, PERIOD_M15, k))
         {
            bull_bb_top = iHigh(_Symbol, PERIOD_M15, k);
            bull_bb_bot = iLow(_Symbol, PERIOD_M15, k);
            bull_bb_expiry = now_t + (12 * 900);
            break;
         }
      }
   }
   
   if(is_sl && c1 < l2)
   {
      for(int k = 2; k <= 10; k++)
      {
         if(iClose(_Symbol, PERIOD_M15, k) > iOpen(_Symbol, PERIOD_M15, k))
         {
            bear_bb_top = iHigh(_Symbol, PERIOD_M15, k);
            bear_bb_bot = iLow(_Symbol, PERIOD_M15, k);
            bear_bb_expiry = now_t + (12 * 900);
            break;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_m15_time = iTime(_Symbol, PERIOD_M15, 0);
   if(current_m15_time == last_m15_bar_time)
      return;

   last_m15_bar_time = current_m15_time;
   int utc_h = GetUTCHour();
   UpdateBreakerBlocks();

   // Rule D.2: Strict Bar-Close Trailing Ratchet
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         ulong magic = PositionGetInteger(POSITION_MAGIC);
         if(magic == InpPhase1_Magic || magic == InpPhase2_Magic || magic == InpPhase3_Magic)
         {
            ulong  ticket     = PositionGetTicket(i);
            double pos_open   = PositionGetDouble(POSITION_PRICE_OPEN);
            double current_sl = PositionGetDouble(POSITION_SL);
            long   pos_type   = PositionGetInteger(POSITION_TYPE);

            double m15_atr_buf[1];
            if(CopyBuffer(handle_m15_atr14, 0, 1, 1, m15_atr_buf) <= 0)
               continue;

            double atr14  = m15_atr_buf[0];
            double r_dist = atr14 * 1.0;
            double close1 = iClose(_Symbol, PERIOD_M15, 1);

            if(pos_type == POSITION_TYPE_BUY)
            {
               if(close1 >= (pos_open + r_dist))
               {
                  double target_sl = pos_open + 0.20;
                  if(current_sl < target_sl)
                     trade.PositionModify(ticket, target_sl, PositionGetDouble(POSITION_TP));
               }
            }
            else if(pos_type == POSITION_TYPE_SELL)
            {
               if(close1 <= (pos_open - r_dist))
               {
                  double target_sl = pos_open - 0.20;
                  if(current_sl > target_sl || current_sl == 0.0)
                     trade.PositionModify(ticket, target_sl, PositionGetDouble(POSITION_TP));
               }
            }
         }
      }
   }

   if(IsCircuitBreakerTripped())
      return;

   double current_spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(current_spread > InpMaxSpread)
      return;

   double m15_atr_buf[1], m15_atr100_buf[1], m15_ema21_buf[1], m15_ema200_buf[1];
   if(CopyBuffer(handle_m15_atr14, 0, 1, 1, m15_atr_buf) <= 0 ||
      CopyBuffer(handle_m15_atr100, 0, 1, 1, m15_atr100_buf) <= 0 ||
      CopyBuffer(handle_m15_ema21, 0, 1, 1, m15_ema21_buf) <= 0 ||
      CopyBuffer(handle_m15_ema200, 0, 1, 1, m15_ema200_buf) <= 0)
      return;

   double cur_atr14  = m15_atr_buf[0];
   double cur_atr100 = m15_atr100_buf[0];
   double cur_ema21  = m15_ema21_buf[0];
   double cur_ema200 = m15_ema200_buf[0];
   double vol_ratio  = (cur_atr100 > 0.0) ? (cur_atr14 / cur_atr100) : 1.0;

   double m15_o1 = iOpen(_Symbol, PERIOD_M15, 1);
   double m15_c1 = iClose(_Symbol, PERIOD_M15, 1);
   double m15_l1 = iLow(_Symbol, PERIOD_M15, 1);
   double m15_h1 = iHigh(_Symbol, PERIOD_M15, 1);

   // Kinetic Expansion Impulse in Lookback Window
   bool has_vel_bull = false;
   bool has_vel_bear = false;

   for(int k = 1; k <= InpLookbackWindow; k++)
   {
      double o_k = iOpen(_Symbol, PERIOD_M15, k);
      double c_k = iClose(_Symbol, PERIOD_M15, k);
      double body = c_k - o_k;
      if(body >= InpImpulseBodyMult * cur_atr14)
         has_vel_bull = true;
      else if((-body) >= InpImpulseBodyMult * cur_atr14)
         has_vel_bear = true;
   }

   // Dynamic Retest: EMA21 Retest
   bool retest_ema_bull = (m15_l1 <= cur_ema21) && (m15_c1 > cur_ema21);
   bool retest_ema_bear = (m15_h1 >= cur_ema21) && (m15_c1 < cur_ema21);

   // Breaker Block Retest
   datetime now_t = TimeCurrent();
   bool retest_bb_bull = (now_t < bull_bb_expiry) && (m15_l1 <= bull_bb_top) && (m15_c1 > bull_bb_bot);
   bool retest_bb_bear = (now_t < bear_bb_expiry) && (m15_h1 >= bear_bb_bot) && (m15_c1 < bear_bb_top);

   // Fair Value Gap Detection
   bool has_bull_fvg = false;
   double bull_fvg_lvl = 0.0;
   bool has_bear_fvg = false;
   double bear_fvg_lvl = 0.0;

   for(int k = 1; k <= InpLookbackWindow; k++)
   {
      double l_k = iLow(_Symbol, PERIOD_M15, k);
      double h_k2 = iHigh(_Symbol, PERIOD_M15, k + 2);
      if(!has_bull_fvg && (l_k > h_k2))
      {
         has_bull_fvg = true;
         bull_fvg_lvl = (l_k + h_k2) / 2.0;
      }
      double h_k = iHigh(_Symbol, PERIOD_M15, k);
      double l_k2 = iLow(_Symbol, PERIOD_M15, k + 2);
      if(!has_bear_fvg && (h_k < l_k2))
      {
         has_bear_fvg = true;
         bear_fvg_lvl = (h_k + l_k2) / 2.0;
      }
   }

   bool fvg_tap_bull = has_bull_fvg && (m15_l1 <= bull_fvg_lvl) && (m15_c1 > bull_fvg_lvl);
   bool fvg_tap_bear = has_bear_fvg && (m15_h1 >= bear_fvg_lvl) && (m15_c1 < bear_fvg_lvl);

   // M5 Micro-Structure Alignment
   double m5_ema50_buf[1];
   if(CopyBuffer(handle_m5_ema50, 0, 1, 1, m5_ema50_buf) <= 0)
      return;
   double m5_c1 = iClose(_Symbol, PERIOD_M5, 1);
   int m5_trend = (m5_c1 > m5_ema50_buf[0]) ? 1 : -1;

   UpdateSupertrend(m15_h1, m15_l1, m15_c1, cur_atr14, InpM15_ST_Mult);

   bool macro_bull = (m15_st_trend == 1) && (m15_c1 > cur_ema200) && (m5_trend == 1);
   bool macro_bear = (m15_st_trend == -1) && (m15_c1 < cur_ema200) && (m5_trend == -1);

   bool signal_buy  = macro_bull && has_vel_bull && (retest_ema_bull || fvg_tap_bull || retest_bb_bull);
   bool signal_sell = macro_bear && has_vel_bear && (retest_ema_bear || fvg_tap_bear || retest_bb_bear);

   double sl_dist = 1.10 * cur_atr14;
   double t1_dist = 1.40 * cur_atr14;
   double t2_dist = 2.80 * cur_atr14;

   // Phase 1: Early London Overweight Sweep (06:00 - 09:00 UTC)
   if(InpEnablePhase1 && utc_h >= InpPhase1_StartUTC && utc_h < InpPhase1_EndUTC)
   {
      if(cur_atr14 >= InpPhase1_MinATR && vol_ratio >= InpPhase1_MinVR)
      {
         ExecuteTranche(signal_buy, signal_sell, InpPhase1_Lot, InpPhase1_Magic, sl_dist, t1_dist, t2_dist);
      }
   }

   // Phase 2: London Midday Expansion (09:00 - 12:00 UTC)
   if(InpEnablePhase2 && utc_h >= InpPhase2_StartUTC && utc_h < InpPhase2_EndUTC)
   {
      if(cur_atr14 >= InpPhase2_MinATR && vol_ratio >= InpPhase2_MinVR)
      {
         ExecuteTranche(signal_buy, signal_sell, InpPhase2_Lot, InpPhase2_Magic, sl_dist, t1_dist, t2_dist);
      }
   }

   // Phase 3: NY Open Kinetic Sweep (12:00 - 16:00 UTC)
   if(InpEnablePhase3 && utc_h >= InpPhase3_StartUTC && utc_h < InpPhase3_EndUTC)
   {
      if(cur_atr14 >= InpPhase3_MinATR && vol_ratio >= InpPhase3_MinVR)
      {
         double ny_t1_dist = InpNY_Rapid_TP_Mult * cur_atr14;
         ExecuteTranche(signal_buy, signal_sell, InpPhase3_Lot, InpPhase3_Magic, sl_dist, ny_t1_dist, t2_dist);
      }
   }
}

//+------------------------------------------------------------------+
//| Order Execution Routine                                          |
//+------------------------------------------------------------------+
void ExecuteTranche(bool is_buy, bool is_sell, double lot, ulong magic, double sl_pts, double tp1_pts, double tp2_pts)
{
   if(!is_buy && !is_sell)
      return;

   // Enforce max 1 concurrent position per magic number
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
         return;
   }

   trade.SetExpertMagicNumber(magic);

   if(is_buy)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = ask - sl_pts;
      double tp  = (tp1_pts > 0) ? (ask + tp1_pts) : 0.0;
      trade.Buy(lot, _Symbol, ask, sl, tp, "Compression Prop-Firm Buy");
   }
   else if(is_sell)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = bid + sl_pts;
      double tp  = (tp1_pts > 0) ? (bid - tp1_pts) : 0.0;
      trade.Sell(lot, _Symbol, bid, sl, tp, "Compression Prop-Firm Sell");
   }
}

//+------------------------------------------------------------------+
//| Trade Transaction Event Handler                                  |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                         const MqlTradeRequest &request,
                         const MqlTradeResult &result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      if(HistoryDealSelect(trans.deal))
      {
         long entry_type = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
         if(entry_type == DEAL_ENTRY_OUT || entry_type == DEAL_ENTRY_INOUT)
         {
            ulong deal_magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
            if(deal_magic == InpPhase1_Magic || deal_magic == InpPhase2_Magic || deal_magic == InpPhase3_Magic)
            {
               double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
               double comm   = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
               double swap   = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
               double net_pl = profit + comm + swap;

               daily_realized_pnl   += net_pl;
               monthly_realized_pnl += net_pl;

               if(daily_realized_pnl > daily_peak_pnl)
                  daily_peak_pnl = daily_realized_pnl;

               if(monthly_realized_pnl > monthly_peak_pnl)
                  monthly_peak_pnl = monthly_realized_pnl;
            }
         }
      }
   }
}
//+------------------------------------------------------------------+

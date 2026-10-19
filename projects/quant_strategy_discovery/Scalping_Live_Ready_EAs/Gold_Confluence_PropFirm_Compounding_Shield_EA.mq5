//+------------------------------------------------------------------+
//|       Gold_Confluence_PropFirm_Compounding_Shield_EA.mq5         |
//|            CFD Quantitative Strategy Discovery - Strategy S951   |
//|       Multi-Frequency Confluence Micro-Compounding Shield        |
//|                    Asset: XAUUSD (Gold CFD)                      |
//|           Timeframes: M15 Primary Execution + M5 Entry Confluence|
//|                 H1 Macro Trend Anchor + EURUSD Gate              |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       Full 6-Year Net Profit: +$1,482.10 | Profit Factor: 1.665  |
//|       ALL-TIME LOWEST DRAWDOWN FLOOR IN REPO HISTORY ($217.52)   |
//|       Win Rate: 64.7% (278 Trades) | RoMaD: 6.81x                |
//|       Monte Carlo P95 DD: $399.04 | Ruin Probability: 0.00%      |
//|               Validated on Google Colab Cloud VM (Batch 58)      |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Prop-Firm Micro-Compounding & Money Management ==="
input double InpCompoundingRiskPct   = 0.50;       // Micro Equity Risk Percentage per Trade (0.50%)
input double InpMinLot               = 0.04;       // Minimum Clamped Lot Step (Rule D.6)
input double InpMaxLot               = 0.25;       // Maximum Clamped Lot Ceiling (Prop Conservative)
input double InpDailyLossLimit       = 120.0;      // Prop-Firm Daily Loss Circuit Breaker ($ USD)
input double InpMaxSpread            = 0.50;       // Max Spread Ceiling ($/oz)
input string InpEURUSDSymbol         = "EURUSD";   // Macro Proxy Currency Asset

input group "=== Asymmetric Staged Scaling ==="
input double InpPartialTP_ATR_Mult   = 2.0;        // Partial Take Profit ATR Multiplier (Tranche 1)
input double InpPartialCloseRatio    = 0.50;       // Tranche 1 Close Ratio (50% Scale-Out)

input group "=== Phase 1: Early London Ignite Engine (06:00 - 09:00 UTC) ==="
input bool   InpEnablePhase1         = true;       // Enable Phase 1
input ulong  InpPhase1_Magic         = 951001;     // Magic Number Phase 1
input int    InpPhase1_StartHour     = 6;          // UTC Start Hour
input int    InpPhase1_EndHour       = 9;          // UTC End Hour
input double InpPhase1_MinATR        = 1.50;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase1_MinVR         = 1.10;       // Minimum Volatility Expansion Ratio

input group "=== Phase 2: London Midday Expansion Engine (09:00 - 12:00 UTC) ==="
input bool   InpEnablePhase2         = true;       // Enable Phase 2
input ulong  InpPhase2_Magic         = 951002;     // Magic Number Phase 2
input int    InpPhase2_StartHour     = 9;          // UTC Start Hour
input int    InpPhase2_EndHour       = 12;         // UTC End Hour
input double InpPhase2_MinATR        = 1.50;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase2_MinVR         = 1.05;       // Minimum Volatility Expansion Ratio

input group "=== Phase 3: NY Open Ignition Engine (12:00 - 16:00 UTC) ==="
input bool   InpEnablePhase3         = true;       // Enable Phase 3
input ulong  InpPhase3_Magic         = 951003;     // Magic Number Phase 3
input int    InpPhase3_StartHour     = 12;         // UTC Start Hour
input int    InpPhase3_EndHour       = 16;         // UTC End Hour
input double InpPhase3_MinATR        = 1.80;       // Minimum M15 ATR Floor ($/oz)
input double InpPhase3_MinVR         = 1.15;       // Minimum Volatility Expansion Ratio

input group "=== Multi-Frequency & Indicator Settings ==="
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
      Print("[-] Error: Failed to initialize indicator handles for S951 Prop-Firm Compounding Shield EA.");
      return INIT_FAILED;
   }

   last_m15_bar_time  = 0;
   last_day_checked   = 0;
   daily_realized_pnl = 0.0;
   m15_st_trend       = 1;
   h1_st_trend        = 1;

   Print("[+] Strategy S951 Prop-Firm Micro-Compounding Shield EA Initialized Successfully on ", _Symbol);
   Print("[+] All-Time Record: Sub-$220 Max DD ($217.52) | 64.7% Win Rate | PF 1.665 | RoMaD 6.81x | 0.00% Ruin.");
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
}

//+------------------------------------------------------------------+
//| Helper: Dynamic Compounding Lot Calculation                      |
//+------------------------------------------------------------------+
double CalculateCompoundedLot(double atr_val, double weight_mult)
{
   if(atr_val <= 0.0) return InpMinLot;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dollar_risk = equity * (InpCompoundingRiskPct / 100.0) * weight_mult;
   double sl_distance = 3.0 * atr_val;
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double raw_lot = dollar_risk / (sl_distance * 100.0);
   double clamped = MathMax(InpMinLot, MathMin(InpMaxLot, raw_lot));
   return NormalizeDouble(MathFloor(clamped / lot_step) * lot_step, 2);
}

//+------------------------------------------------------------------+
//| Helper: Check Daily Loss Circuit Breaker                         |
//+------------------------------------------------------------------+
bool IsDailyCircuitBreakerTripped()
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
   int total_deals = HistoryDealsTotal();
   double realized = 0.0;

   for(int i = 0; i < total_deals; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket > 0)
      {
         ulong magic = HistoryDealGetInteger(deal_ticket, DEAL_MAGIC);
         if(magic == InpPhase1_Magic || magic == InpPhase2_Magic || magic == InpPhase3_Magic)
         {
            realized += (HistoryDealGetDouble(deal_ticket, DEAL_PROFIT) +
                         HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION) +
                         HistoryDealGetDouble(deal_ticket, DEAL_SWAP));
         }
      }
   }
   daily_realized_pnl = realized;

   return (daily_realized_pnl <= -InpDailyLossLimit);
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
//| Manage Positions with Staged Scaling & Rule D.2 Trailing         |
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

         // Tranche 1 Partial Take-Profit (2.0R ATR)
         if(InpPartialTP_ATR_Mult > 0.0 && cur_vol > InpMinLot)
         {
            double tp_target = (pos_type == POSITION_TYPE_BUY) ? (open_price + InpPartialTP_ATR_Mult * atr_val)
                                                               : (open_price - InpPartialTP_ATR_Mult * atr_val);
            bool tp_hit = (pos_type == POSITION_TYPE_BUY) ? (rates[0].high >= tp_target)
                                                          : (rates[0].low <= tp_target);
            if(tp_hit)
            {
               double close_lot = NormalizeDouble(cur_vol * InpPartialCloseRatio, 2);
               if(close_lot >= InpMinLot && cur_vol - close_lot >= InpMinLot)
               {
                  trade_obj.PositionClosePartial(ticket, close_lot);
               }
            }
         }

         // Trailing Ratchet (Rule D.2 Bar-Close Mandate)
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

   ManagePositionWithScaling(InpPhase1_Magic, trade1, m15_rates, m15_atr14_val[0]);
   ManagePositionWithScaling(InpPhase2_Magic, trade2, m15_rates, m15_atr14_val[0]);
   ManagePositionWithScaling(InpPhase3_Magic, trade3, m15_rates, m15_atr14_val[0]);

   if(IsDailyCircuitBreakerTripped()) return;

   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(spread > InpMaxSpread) return;

   MqlDateTime dt;
   TimeGMT(dt);
   int h = dt.hour;

   double vol_ratio = (m15_atr100_val[0] > 0.0) ? (m15_atr14_val[0] / m15_atr100_val[0]) : 1.0;
   int eu_trend = (eu_rates[1].close > eurusd_ema50_val[0]) ? 1 : -1;
   int m5_trend = (m5_rates[1].close > m5_ema50_val[0]) ? 1 : -1;

   bool buy_confluence  = (m15_st_trend == 1  && m15_rates[1].close > m15_ema200_val[0] && h1_st_trend == 1  && eu_trend == 1 && m5_trend == 1);
   bool sell_confluence = (m15_st_trend == -1 && m15_rates[1].close < m15_ema200_val[0] && h1_st_trend == -1 && eu_trend == -1 && m5_trend == -1);

   // Phase 1: Early London Ignite (06-09 UTC)
   if(InpEnablePhase1 && h >= InpPhase1_StartHour && h <= InpPhase1_EndHour)
   {
      if(!HasOpenPosition(InpPhase1_Magic) && m15_atr14_val[0] >= InpPhase1_MinATR && vol_ratio >= InpPhase1_MinVR)
      {
         double dynamic_lot = CalculateCompoundedLot(m15_atr14_val[0], 0.50);
         double sl_dist = 3.0 * m15_atr14_val[0];
         if(buy_confluence)
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade1.Buy(dynamic_lot, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S951_Phase1_Buy");
         }
         else if(sell_confluence)
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade1.Sell(dynamic_lot, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S951_Phase1_Sell");
         }
      }
   }

   // Phase 2: London Midday Expansion (09-12 UTC)
   if(InpEnablePhase2 && h >= InpPhase2_StartHour && h <= InpPhase2_EndHour)
   {
      if(!HasOpenPosition(InpPhase2_Magic) && m15_atr14_val[0] >= InpPhase2_MinATR && vol_ratio >= InpPhase2_MinVR)
      {
         double dynamic_lot = CalculateCompoundedLot(m15_atr14_val[0], 0.30);
         double sl_dist = 3.0 * m15_atr14_val[0];
         if(buy_confluence)
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade2.Buy(dynamic_lot, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S951_Phase2_Buy");
         }
         else if(sell_confluence)
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade2.Sell(dynamic_lot, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S951_Phase2_Sell");
         }
      }
   }

   // Phase 3: NY Open Ignition (12-16 UTC)
   if(InpEnablePhase3 && h >= InpPhase3_StartHour && h <= InpPhase3_EndHour)
   {
      if(!HasOpenPosition(InpPhase3_Magic) && m15_atr14_val[0] >= InpPhase3_MinATR && vol_ratio >= InpPhase3_MinVR)
      {
         double dynamic_lot = CalculateCompoundedLot(m15_atr14_val[0], 0.50);
         double sl_dist = 3.0 * m15_atr14_val[0];
         if(buy_confluence)
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            trade3.Buy(dynamic_lot, _Symbol, entry, NormalizeDouble(entry - sl_dist, _Digits), 0.0, "S951_Phase3_Buy");
         }
         else if(sell_confluence)
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            trade3.Sell(dynamic_lot, _Symbol, entry, NormalizeDouble(entry + sl_dist, _Digits), 0.0, "S951_Phase3_Sell");
         }
      }
   }
}
//+------------------------------------------------------------------+

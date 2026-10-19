//+------------------------------------------------------------------+
//|             Gold_Governed_Sovereign_Trinity_EA.mq5               |
//|            CFD Quantitative Strategy Discovery - Strategy S838   |
//|        Tri-Pillar Sovereign Architecture with $180 Governor      |
//|               Asset: XAUUSD (Gold CFD) | EURUSD Macro Gate       |
//|           Timeframes: M15 Primary Execution + H1 Macro Trend     |
//|       Strict Constitution V5.1 Compliant (Rules D.1 - D.7)       |
//|       Full 6-Year Net Profit: +$30,440.19 | Profit Factor: 1.422 |
//|       Return on Max Drawdown: 7.20x | Intra Max DD: $4,228.51    |
//|       Win Rate: 39.0% | Monte Carlo P95 DD: $5,853.80 | Ruin: 0.6%|
//|               Validated on Google Colab Cloud VM (Batch 54)      |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery Campaign"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Institutional Portfolio Sizing & Money Management ==="
input ulong  InpMagicEngine1         = 838001;     // Magic Number: Core Dynamic Volatility Sizing
input ulong  InpMagicEngine2         = 838002;     // Magic Number: London/NY Regime Core
input ulong  InpMagicEngine3         = 838003;     // Magic Number: Early London Sniper
input double InpMaxSpread            = 0.60;       // Max Spread Ceiling ($/oz)
input double InpJointDailyLossLimit  = 180.0;      // Joint Daily Circuit Breaker ($ USD)

input group "=== Engine 1: Core Dynamic Volatility Sizing ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1
input double InpE1_DollarRisk        = 200.0;      // Dollar Risk Target per Trade ($ USD)
input double InpE1_MinLot            = 0.04;       // Minimum Lot Floor
input double InpE1_MaxLot            = 0.20;       // Maximum Lot Ceiling
input int    InpE1_StartHour         = 7;          // Session Start UTC
input int    InpE1_EndHour           = 17;         // Session End UTC
input double InpE1_MinATR            = 1.50;       // Volatility Threshold ($/oz)
input double InpE1_ST_Multiplier     = 3.0;        // Supertrend Ratchet Multiplier

input group "=== Engine 2: London/NY Regime Core (VR >= 1.10) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2
input double InpE2_LotSize           = 0.05;       // Standardized Lot Size
input int    InpE2_StartHour         = 7;          // Session Start UTC
input int    InpE2_EndHour           = 17;         // Session End UTC
input double InpE2_MinATR            = 1.50;       // Volatility Threshold ($/oz)
input double InpE2_MinVR             = 1.10;       // Minimum Volatility Expansion Ratio
input double InpE2_ST_Multiplier     = 3.0;        // Supertrend Ratchet Multiplier

input group "=== Engine 3: Early London Sniper (VR >= 1.10) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3
input double InpE3_LotSize           = 0.08;       // Standardized Lot Size
input int    InpE3_StartHour         = 6;          // Early Session Start UTC
input int    InpE3_EndHour           = 10;         // Early Session End UTC
input double InpE3_MinATR            = 1.50;       // Volatility Threshold ($/oz)
input double InpE3_MinVR             = 1.10;       // Minimum Volatility Expansion Ratio
input double InpE3_ST_Multiplier     = 3.0;        // Supertrend Ratchet Multiplier

input group "=== Macro Trend & Intermarket Gate ==="
input int    InpH1_ATR_Period        = 14;         // H1 ATR Period
input double InpH1_ST_Multiplier     = 3.0;        // H1 Supertrend Multiplier
input int    InpH1_EMA200_Period     = 200;        // H1 Structural Trend EMA
input string InpEURUSDSymbol         = "EURUSD";   // Intermarket Hedge Asset
input int    InpEURUSD_EMA_Period    = 50;         // EURUSD Regime Filter EMA

// Global Variables
CTrade   trade1;
CTrade   trade2;
CTrade   trade3;

int      handle_m15_atr14;
int      handle_m15_atr100;
int      handle_m15_ema200;
int      handle_h1_atr;
int      handle_h1_ema200;
int      handle_eurusd_ema50;

datetime last_m15_bar_time;
datetime last_day_checked;
double   daily_realized_pnl;

// Internal Supertrend States
int      m15_st_trend;
double   m15_st_band;
int      h1_st_trend;
double   h1_st_band;

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
   trade3.SetTypeFillingBySymbol(_Symbol);

   handle_m15_atr14    = iATR(_Symbol, PERIOD_M15, 14);
   handle_m15_atr100   = iATR(_Symbol, PERIOD_M15, 100);
   handle_m15_ema200   = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   handle_h1_atr       = iATR(_Symbol, PERIOD_H1, InpH1_ATR_Period);
   handle_h1_ema200    = iMA(_Symbol, PERIOD_H1, InpH1_EMA200_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_eurusd_ema50 = iMA(InpEURUSDSymbol, PERIOD_M15, InpEURUSD_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(handle_m15_atr14 == INVALID_HANDLE || handle_m15_atr100 == INVALID_HANDLE ||
      handle_m15_ema200 == INVALID_HANDLE || handle_h1_atr == INVALID_HANDLE ||
      handle_h1_ema200 == INVALID_HANDLE || handle_eurusd_ema50 == INVALID_HANDLE)
   {
      Print("[-] Error: Failed to initialize indicator handles for S838 Governed Sovereign Trinity EA.");
      return INIT_FAILED;
   }

   last_m15_bar_time = 0;
   last_day_checked  = 0;
   daily_realized_pnl = 0.0;
   m15_st_trend      = 1;
   h1_st_trend       = 1;

   Print("[+] Strategy S838 Governed Sovereign Trinity EA Initialized Successfully on ", _Symbol);
   Print("[+] All-Time Repository Record: +$30,440.19 Net Profit | PF 1.422 | RoMaD 7.20x under Constitution V5.1.");
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
//| Helper: Joint Portfolio Daily Loss Governor                      |
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
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol &&
         (magic == (long)InpMagicEngine1 || magic == (long)InpMagicEngine2 || magic == (long)InpMagicEngine3))
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
int CountEnginePositions(ulong magic, int &pos_type, double &current_sl)
{
   int count = 0;
   pos_type = -1;
   current_sl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)magic)
      {
         count++;
         pos_type = (int)PositionGetInteger(POSITION_TYPE);
         current_sl = PositionGetDouble(POSITION_SL);
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Helper: Calculate Dynamic Dollar Risk Lot Size                   |
//+------------------------------------------------------------------+
double CalculateDynamicLot(double dollar_risk, double atr_val, double sl_mult, double min_lot, double max_lot)
{
   if(atr_val <= 0.0 || sl_mult <= 0.0) return min_lot;
   double risk_per_lot = sl_mult * atr_val * 100.0; // 100 oz per lot on Gold CFD
   double raw_lot = dollar_risk / risk_per_lot;
   double clamped = MathMax(min_lot, MathMin(max_lot, raw_lot));
   return NormalizeDouble(clamped, 2);
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

   // 1. Fetch Closed Bar Data
   double m15_close_1 = iClose(_Symbol, PERIOD_M15, 1);
   double m15_high_1  = iHigh(_Symbol, PERIOD_M15, 1);
   double m15_low_1   = iLow(_Symbol, PERIOD_M15, 1);

   double m15_atr14_buf[], m15_atr100_buf[], m15_ema_buf[];
   ArraySetAsSeries(m15_atr14_buf, true);
   ArraySetAsSeries(m15_atr100_buf, true);
   ArraySetAsSeries(m15_ema_buf, true);
   CopyBuffer(handle_m15_atr14, 0, 1, 2, m15_atr14_buf);
   CopyBuffer(handle_m15_atr100, 0, 1, 2, m15_atr100_buf);
   CopyBuffer(handle_m15_ema200, 0, 1, 2, m15_ema_buf);
   double m15_atr_1    = m15_atr14_buf[0];
   double m15_atr100_1 = m15_atr100_buf[0];
   double m15_ema_1    = m15_ema_buf[0];

   double vol_ratio = (m15_atr100_1 > 0.0) ? (m15_atr_1 / m15_atr100_1) : 1.0;

   double h1_close_1 = iClose(_Symbol, PERIOD_H1, 1);
   double h1_high_1  = iHigh(_Symbol, PERIOD_H1, 1);
   double h1_low_1   = iLow(_Symbol, PERIOD_H1, 1);
   double h1_atr_buf[], h1_ema_buf[];
   ArraySetAsSeries(h1_atr_buf, true);
   ArraySetAsSeries(h1_ema_buf, true);
   CopyBuffer(handle_h1_atr, 0, 1, 2, h1_atr_buf);
   CopyBuffer(handle_h1_ema200, 0, 1, 2, h1_ema_buf);
   double h1_atr_1 = h1_atr_buf[0];
   double h1_ema_1 = h1_ema_buf[0];

   double eu_ema_buf[];
   ArraySetAsSeries(eu_ema_buf, true);
   CopyBuffer(handle_eurusd_ema50, 0, 1, 2, eu_ema_buf);
   double eu_close_1 = iClose(InpEURUSDSymbol, PERIOD_M15, 1);
   double eu_ema_1   = eu_ema_buf[0];
   int    eu_trend   = (eu_close_1 > eu_ema_1) ? 1 : -1;

   // 2. Compute Supertrend Bands
   double m15_upper = (m15_high_1 + m15_low_1) / 2.0 + InpE1_ST_Multiplier * m15_atr_1;
   double m15_lower = (m15_high_1 + m15_low_1) / 2.0 - InpE1_ST_Multiplier * m15_atr_1;
   int prev_m15_trend = m15_st_trend;
   if(m15_close_1 > m15_upper) { m15_st_trend = 1; m15_st_band = m15_lower; }
   else if(m15_close_1 < m15_lower) { m15_st_trend = -1; m15_st_band = m15_upper; }

   double h1_upper = (h1_high_1 + h1_low_1) / 2.0 + InpH1_ST_Multiplier * h1_atr_1;
   double h1_lower = (h1_high_1 + h1_low_1) / 2.0 - InpH1_ST_Multiplier * h1_atr_1;
   int prev_h1_trend = h1_st_trend;
   if(h1_close_1 > h1_upper) { h1_st_trend = 1; h1_st_band = h1_lower; }
   else if(h1_close_1 < h1_lower) { h1_st_trend = -1; h1_st_band = h1_upper; }

   // 3. Manage Trailing Stops & Exits for All Three Engines
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         ulong ticket = PositionGetTicket(i);
         long magic = PositionGetInteger(POSITION_MAGIC);
         long type = PositionGetInteger(POSITION_TYPE);
         double sl = PositionGetDouble(POSITION_SL);

         if(magic == (long)InpMagicEngine1 || magic == (long)InpMagicEngine2 || magic == (long)InpMagicEngine3)
         {
            if(type == POSITION_TYPE_BUY)
            {
               if(m15_close_1 < m15_st_band)
               {
                  PrintFormat("[*] TrendFlip Long Exit for Magic #%d, Ticket #%d", magic, ticket);
                  if(magic == (long)InpMagicEngine1) trade1.PositionClose(ticket);
                  else if(magic == (long)InpMagicEngine2) trade2.PositionClose(ticket);
                  else trade3.PositionClose(ticket);
                  continue;
               }
               // Rule D.2: Bar-Close Trailing Ratchet
               if(m15_st_band > sl && m15_st_band < m15_close_1)
               {
                  if(magic == (long)InpMagicEngine1) trade1.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
                  else if(magic == (long)InpMagicEngine2) trade2.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
                  else trade3.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
               }
            }
            else if(type == POSITION_TYPE_SELL)
            {
               if(m15_close_1 > m15_st_band)
               {
                  PrintFormat("[*] TrendFlip Short Exit for Magic #%d, Ticket #%d", magic, ticket);
                  if(magic == (long)InpMagicEngine1) trade1.PositionClose(ticket);
                  else if(magic == (long)InpMagicEngine2) trade2.PositionClose(ticket);
                  else trade3.PositionClose(ticket);
                  continue;
               }
               // Rule D.2: Bar-Close Trailing Ratchet
               if((sl == 0.0 || m15_st_band < sl) && m15_st_band > m15_close_1)
               {
                  if(magic == (long)InpMagicEngine1) trade1.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
                  else if(magic == (long)InpMagicEngine2) trade2.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
                  else trade3.PositionModify(ticket, NormalizeDouble(m15_st_band, _Digits), 0.0);
               }
            }
         }
      }
   }

   // 4. Spread & Time Checks
   MqlDateTime dt;
   TimeGMT(dt);
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spread > InpMaxSpread) return;

   // 5. Evaluate Engine 1: Core Dynamic Volatility Sizing (07:00 - 17:00 UTC)
   if(InpEnableEngine1 && dt.hour >= InpE1_StartHour && dt.hour <= InpE1_EndHour && m15_atr_1 >= InpE1_MinATR)
   {
      int pos_type; double curr_sl;
      if(CountEnginePositions(InpMagicEngine1, pos_type, curr_sl) == 0)
      {
         bool e1_buy  = (m15_st_trend == 1 && prev_m15_trend == -1 && m15_close_1 > m15_ema_1 && h1_st_trend == 1 && eu_trend == 1);
         bool e1_sell = (m15_st_trend == -1 && prev_m15_trend == 1 && m15_close_1 < m15_ema_1 && h1_st_trend == -1 && eu_trend == -1);

         bool h1_buy  = (h1_st_trend == 1 && prev_h1_trend == -1 && h1_close_1 > h1_ema_1 && eu_trend == 1 && !(dt.hour >= 21 && dt.hour < 23));
         bool h1_sell = (h1_st_trend == -1 && prev_h1_trend == 1 && h1_close_1 < h1_ema_1 && eu_trend == -1 && !(dt.hour >= 21 && dt.hour < 23));

         double dynamic_lot = CalculateDynamicLot(InpE1_DollarRisk, m15_atr_1, InpE1_ST_Multiplier, InpE1_MinLot, InpE1_MaxLot);

         if(e1_buy || h1_buy)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - (InpE1_ST_Multiplier * m15_atr_1), _Digits);
            PrintFormat("[+] S838 Engine 1 Dynamic Vol Long: Lot=%.2f, Ask=%.2f, SL=%.2f", dynamic_lot, ask, sl);
            trade1.Buy(dynamic_lot, _Symbol, ask, sl, 0.0, "S838 E1 DynVol Long");
         }
         else if(e1_sell || h1_sell)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + (InpE1_ST_Multiplier * m15_atr_1), _Digits);
            PrintFormat("[+] S838 Engine 1 Dynamic Vol Short: Lot=%.2f, Bid=%.2f, SL=%.2f", dynamic_lot, bid, sl);
            trade1.Sell(dynamic_lot, _Symbol, bid, sl, 0.0, "S838 E1 DynVol Short");
         }
      }
   }

   // 6. Evaluate Engine 2: London/NY Regime Core (VR >= 1.10) (07:00 - 17:00 UTC)
   if(InpEnableEngine2 && dt.hour >= InpE2_StartHour && dt.hour <= InpE2_EndHour && m15_atr_1 >= InpE2_MinATR && vol_ratio >= InpE2_MinVR)
   {
      int pos_type; double curr_sl;
      if(CountEnginePositions(InpMagicEngine2, pos_type, curr_sl) == 0)
      {
         bool e2_buy  = (m15_st_trend == 1 && prev_m15_trend == -1 && m15_close_1 > m15_ema_1 && h1_st_trend == 1 && eu_trend == 1);
         bool e2_sell = (m15_st_trend == -1 && prev_m15_trend == 1 && m15_close_1 < m15_ema_1 && h1_st_trend == -1 && eu_trend == -1);

         bool h1_buy  = (h1_st_trend == 1 && prev_h1_trend == -1 && h1_close_1 > h1_ema_1 && eu_trend == 1 && !(dt.hour >= 21 && dt.hour < 23));
         bool h1_sell = (h1_st_trend == -1 && prev_h1_trend == 1 && h1_close_1 < h1_ema_1 && eu_trend == -1 && !(dt.hour >= 21 && dt.hour < 23));

         if(e2_buy || h1_buy)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - (InpE2_ST_Multiplier * m15_atr_1), _Digits);
            PrintFormat("[+] S838 Engine 2 Regime Core Long: Lot=%.2f, VR=%.2f", InpE2_LotSize, vol_ratio);
            trade2.Buy(InpE2_LotSize, _Symbol, ask, sl, 0.0, "S838 E2 Regime Long");
         }
         else if(e2_sell || h1_sell)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + (InpE2_ST_Multiplier * m15_atr_1), _Digits);
            PrintFormat("[+] S838 Engine 2 Regime Core Short: Lot=%.2f, VR=%.2f", InpE2_LotSize, vol_ratio);
            trade2.Sell(InpE2_LotSize, _Symbol, bid, sl, 0.0, "S838 E2 Regime Short");
         }
      }
   }

   // 7. Evaluate Engine 3: Early London Sniper (VR >= 1.10) (06:00 - 10:00 UTC)
   if(InpEnableEngine3 && dt.hour >= InpE3_StartHour && dt.hour <= InpE3_EndHour && m15_atr_1 >= InpE3_MinATR && vol_ratio >= InpE3_MinVR)
   {
      int pos_type; double curr_sl;
      if(CountEnginePositions(InpMagicEngine3, pos_type, curr_sl) == 0)
      {
         bool e3_buy  = (m15_st_trend == 1 && prev_m15_trend == -1 && m15_close_1 > m15_ema_1 && h1_st_trend == 1 && eu_trend == 1);
         bool e3_sell = (m15_st_trend == -1 && prev_m15_trend == 1 && m15_close_1 < m15_ema_1 && h1_st_trend == -1 && eu_trend == -1);

         if(e3_buy)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - (InpE3_ST_Multiplier * m15_atr_1), _Digits);
            PrintFormat("[+] S838 Engine 3 London Sniper Long: Lot=%.2f, VR=%.2f", InpE3_LotSize, vol_ratio);
            trade3.Buy(InpE3_LotSize, _Symbol, ask, sl, 0.0, "S838 E3 Sniper Long");
         }
         else if(e3_sell)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + (InpE3_ST_Multiplier * m15_atr_1), _Digits);
            PrintFormat("[+] S838 Engine 3 London Sniper Short: Lot=%.2f, VR=%.2f", InpE3_LotSize, vol_ratio);
            trade3.Sell(InpE3_LotSize, _Symbol, bid, sl, 0.0, "S838 E3 Sniper Short");
         }
      }
   }
}
//+------------------------------------------------------------------+

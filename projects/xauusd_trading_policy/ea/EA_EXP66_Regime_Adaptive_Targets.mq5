//+------------------------------------------------------------------+
//|                                EA_EXP66_Regime_Adaptive_Targets.mq5 |
//|                                  Copyright 2026, BlamzKunG Quant |
//|           EXP-66: Regime-Adaptive Target Optimization (RATO-SVAE) |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Risk & Allocation ==="
input double   InpBaseRiskPercent     = 1.5;     // Base Risk % per trade
input bool     InpUseDynamicSizing    = true;    // Use Dynamic Edge & Volatility Sizing
input double   InpMinRiskPercent      = 1.0;     // Min Risk %
input double   InpMaxRiskPercent      = 2.8;     // Max Risk %
input double   InpMaxDailyDrawdown    = 5.0;     // Max Daily Drawdown % (Circuit Breaker)

input group "=== Execution & Regime-Adaptive Targets ==="
input double   InpInitialSL_ATR       = 1.8;     // Initial Stop Loss in ATR
input bool     InpUseAdaptiveTarget   = true;    // Dynamically Scale TP by Volatility
input double   InpTP_LowVol_ATR       = 3.2;     // Target in Low Volatility Regime
input double   InpTP_Standard_ATR     = 3.8;     // Target in Standard Regime
input double   InpTP_HighVol_ATR      = 4.2;     // Target in High Volatility Regime
input double   InpBE_Trigger_ATR      = 1.5;     // Breakeven Activation in ATR
input double   InpBE_Buffer_ATR       = 0.10;    // Breakeven Cushion in ATR
input double   InpLock_Trigger_ATR    = 2.8;     // Profit Lock Activation in ATR
input double   InpLock_Buffer_ATR     = 1.20;    // Profit Lock Cushion in ATR

input group "=== Session Filters ==="
input bool     InpFilterSessions      = true;    // Restrict to London & NY Overlap
input int      InpLondonStartHour     = 7;
input int      InpLondonEndHour       = 11;
input int      InpNYStartHour         = 12;
input int      InpNYStartMinute       = 30;
input int      InpNYEndHour           = 16;
input int      InpNYEndMinute         = 30;

input group "=== System Setup ==="
input ulong    InpMagicNumber         = 660001;  // Magic Number
input int      InpSlippagePoints      = 30;      // Allowed Slippage in Points
input string   InpTradeComment        = "EXP-66 RATO-SVAE";

//--- Global Variables
int      h_atr14;
int      h_ema5;
int      h_ema15;
int      h_ema60;
int      h_ema200;
double   g_dailyStartEquity = 0.0;
int      g_lastDay = -1;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   h_atr14  = iATR(_Symbol, PERIOD_M1, 14);
   h_ema5   = iMA(_Symbol, PERIOD_M1, 5, 0, MODE_EMA, PRICE_CLOSE);
   h_ema15  = iMA(_Symbol, PERIOD_M1, 15, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60  = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   h_ema200 = iMA(_Symbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr14 == INVALID_HANDLE || h_ema5 == INVALID_HANDLE ||
      h_ema15 == INVALID_HANDLE || h_ema60 == INVALID_HANDLE || h_ema200 == INVALID_HANDLE)
   {
      Print("[!] Error creating technical indicator handles");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   MqlDateTime dt;
   TimeCurrent(dt);
   g_lastDay = dt.day;

   Print("[+] EA_EXP66_Regime_Adaptive_Targets Initialized Successfully");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr14);
   IndicatorRelease(h_ema5);
   IndicatorRelease(h_ema15);
   IndicatorRelease(h_ema60);
   IndicatorRelease(h_ema200);
}

//+------------------------------------------------------------------+
//| Check Session Time Validity                                      |
//+------------------------------------------------------------------+
bool IsValidSessionTime(datetime time_val)
{
   if(!InpFilterSessions) return true;

   MqlDateTime dt;
   TimeToStruct(time_val, dt);

   if(dt.day_of_week == 5 && dt.hour >= 18) return false;

   double time_float = dt.hour + (dt.min / 60.0);
   bool is_london = (time_float >= InpLondonStartHour && time_float < InpLondonEndHour);
   bool is_ny = (time_float >= (InpNYStartHour + InpNYStartMinute/60.0) &&
                 time_float < (InpNYEndHour + InpNYEndMinute/60.0));

   return (is_london || is_ny);
}

//+------------------------------------------------------------------+
//| Trailing Ladder Engine                                           |
//+------------------------------------------------------------------+
void ManageOpenPosition(double atr_val)
{
   if(PositionsTotal() == 0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      long pos_type = PositionGetInteger(POSITION_TYPE);
      double open_p  = PositionGetDouble(POSITION_PRICE_OPEN);
      double curr_sl = PositionGetDouble(POSITION_SL);
      double curr_tp = PositionGetDouble(POSITION_TP);
      double curr_p  = PositionGetDouble(POSITION_PRICE_CURRENT);

      MqlTradeRequest request;
      MqlTradeResult  result;
      ZeroMemory(request);
      ZeroMemory(result);

      request.action   = TRADE_ACTION_SLTP;
      request.position = ticket;
      request.symbol   = _Symbol;

      if(pos_type == POSITION_TYPE_BUY)
      {
         double profit_dist = curr_p - open_p;
         double new_sl = curr_sl;

         if(profit_dist >= InpBE_Trigger_ATR * atr_val && curr_sl < open_p)
            new_sl = open_p + InpBE_Buffer_ATR * atr_val;

         if(profit_dist >= InpLock_Trigger_ATR * atr_val && curr_sl < (open_p + InpLock_Buffer_ATR * atr_val))
            new_sl = open_p + InpLock_Buffer_ATR * atr_val;

         if(new_sl > curr_sl && new_sl < curr_p)
         {
            request.sl = NormalizeDouble(new_sl, _Digits);
            request.tp = curr_tp;
            OrderSend(request, result);
         }
      }
      else if(pos_type == POSITION_TYPE_SELL)
      {
         double profit_dist = open_p - curr_p;
         double new_sl = curr_sl;

         if(profit_dist >= InpBE_Trigger_ATR * atr_val && (curr_sl == 0.0 || curr_sl > open_p))
            new_sl = open_p - InpBE_Buffer_ATR * atr_val;

         if(profit_dist >= InpLock_Trigger_ATR * atr_val && curr_sl > (open_p - InpLock_Buffer_ATR * atr_val))
            new_sl = open_p - InpLock_Buffer_ATR * atr_val;

         if(new_sl > 0.0 && (curr_sl == 0.0 || new_sl < curr_sl) && new_sl > curr_p)
         {
            request.sl = NormalizeDouble(new_sl, _Digits);
            request.tp = curr_tp;
            OrderSend(request, result);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   bool is_new_bar = (current_bar_time != g_lastBarTime);

   double atr_arr[1];
   if(CopyBuffer(h_atr14, 0, 0, 1, atr_arr) <= 0) return;
   double atr_val = atr_arr[0];
   if(atr_val <= 0.0) return;

   ManageOpenPosition(atr_val);

   if(!is_new_bar) return;
   g_lastBarTime = current_bar_time;

   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != g_lastDay)
   {
      g_lastDay = dt.day;
      g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   }
   double current_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double daily_dd = (g_dailyStartEquity - current_equity) / g_dailyStartEquity * 100.0;
   if(daily_dd >= InpMaxDailyDrawdown) return;

   if(PositionsTotal() > 0) return;
   if(!IsValidSessionTime(current_bar_time)) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 65, rates) < 65) return;

   double c1 = rates[0].close;
   double o1 = rates[0].open;
   double h1 = rates[0].high;
   double l1 = rates[0].low;
   long   v1 = rates[0].tick_volume;

   double bar_range = MathMax(h1 - l1, 0.01);
   double upper_wick = h1 - MathMax(c1, o1);
   double lower_wick = MathMin(c1, o1) - l1;

   bool bull_pinbar = (lower_wick >= 0.38 * bar_range) && (upper_wick <= 0.28 * bar_range) && (c1 >= o1);
   bool bear_pinbar = (upper_wick >= 0.38 * bar_range) && (lower_wick <= 0.28 * bar_range) && (c1 <= o1);

   double vol_sum20 = 0.0;
   for(int i = 0; i < 20; i++) vol_sum20 += rates[i].tick_volume;
   double vol_ma20 = vol_sum20 / 20.0;
   double rel_vol = v1 / MathMax(vol_ma20, 1.0);
   double vfs = rel_vol * (MathAbs(c1 - o1) / atr_val);
   double vdp = v1 * ((c1 - l1) - (h1 - c1)) / bar_range;

   double swing_high_60 = -1.0;
   double swing_low_60  = 999999.0;
   for(int i = 1; i <= 60; i++)
   {
      if(rates[i].high > swing_high_60) swing_high_60 = rates[i].high;
      if(rates[i].low < swing_low_60)   swing_low_60  = rates[i].low;
   }

   bool sweep_trap_long  = (l1 <= swing_low_60) && (c1 > swing_low_60) && (vfs >= 1.10) && (vdp > 0);
   bool sweep_trap_short = (h1 >= swing_high_60) && (c1 < swing_high_60) && (vfs >= 1.10) && (vdp < 0);

   double ema5_arr[1], ema15_arr[1];
   CopyBuffer(h_ema5, 0, 1, 1, ema5_arr);
   CopyBuffer(h_ema15, 0, 1, 1, ema15_arr);

   bool mtf_bull = (c1 > ema5_arr[0]) && (ema5_arr[0] > ema15_arr[0]);
   bool mtf_bear = (c1 < ema5_arr[0]) && (ema5_arr[0] < ema15_arr[0]);

   bool fvg_retest_long  = (rates[0].low <= rates[2].close) && (c1 >= rates[2].high) && (lower_wick >= 0.25 * bar_range);
   bool fvg_retest_short = (rates[0].high >= rates[2].close) && (c1 <= rates[2].low) && (upper_wick >= 0.25 * bar_range);

   bool signal_long  = (bull_pinbar && mtf_bull && vfs >= 1.12) || sweep_trap_long || (fvg_retest_long && mtf_bull);
   bool signal_short = (bear_pinbar && mtf_bear && vfs >= 1.15) || sweep_trap_short || (fvg_retest_short && mtf_bear);

   if(!signal_long && !signal_short) return;

   // Sizing Calculation
   double risk_percent = InpBaseRiskPercent;
   if(InpUseDynamicSizing)
   {
      double edge_scale = (vfs - 1.0) * 0.50;
      risk_percent = MathMin(InpMaxRiskPercent, MathMax(InpMinRiskPercent, InpBaseRiskPercent + edge_scale));
   }

   // Target Regime Scaling
   double tp_mult = InpTP_Standard_ATR;
   if(InpUseAdaptiveTarget)
   {
      if(vfs > 1.30)
         tp_mult = InpTP_HighVol_ATR;
      else if(vfs < 1.10)
         tp_mult = InpTP_LowVol_ATR;
      else
         tp_mult = InpTP_Standard_ATR;
   }

   double account_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dollar_risk = account_balance * (risk_percent / 100.0);
   double sl_distance = InpInitialSL_ATR * atr_val;
   double point_val = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100.0;
   double lot_calc = dollar_risk / (sl_distance * 100.0);

   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double min_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(lot_calc / lot_step) * lot_step;
   lots = MathMin(max_lot, MathMax(min_lot, lots));

   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);

   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = lots;
   req.magic        = InpMagicNumber;
   req.deviation    = InpSlippagePoints;
   req.comment      = InpTradeComment;

   if(signal_long)
   {
      req.type   = ORDER_TYPE_BUY;
      req.price  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      req.sl     = NormalizeDouble(req.price - sl_distance, _Digits);
      req.tp     = NormalizeDouble(req.price + tp_mult * atr_val, _Digits);
      OrderSend(req, res);
   }
   else if(signal_short)
   {
      req.type   = ORDER_TYPE_SELL;
      req.price  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      req.sl     = NormalizeDouble(req.price + sl_distance, _Digits);
      req.tp     = NormalizeDouble(req.price - tp_mult * atr_val, _Digits);
      OrderSend(req, res);
   }
}
//+------------------------------------------------------------------+

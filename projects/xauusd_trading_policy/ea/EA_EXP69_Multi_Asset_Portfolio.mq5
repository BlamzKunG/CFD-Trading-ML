//+------------------------------------------------------------------+
//|                                EA_EXP69_Multi_Asset_Portfolio.mq5 |
//|                                  Copyright 2026, BlamzKunG Quant |
//|        EXP-69: Multi-Asset Dual-Sleeve Portfolio Allocation Engine |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG Quant"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Multi-Asset Allocation ==="
input string   InpGoldSymbol          = "XAUUSD"; // Gold Symbol
input string   InpForexSymbol         = "EURUSD"; // Forex Symbol
input double   InpGoldRiskPercent     = 1.5;      // Base Gold Risk %
input double   InpForexRiskPercent    = 0.6;      // Base Forex Risk %
input bool     InpUseDynamicSizing    = true;     // Enable Dynamic ML Edge Sizing
input double   InpMaxDailyDrawdown    = 5.0;      // Max Daily Portfolio Drawdown %

input group "=== Gold Parameters (XAUUSD) ==="
input double   InpXAU_InitialSL_ATR   = 1.8;      // Gold Stop Loss in ATR
input double   InpXAU_TakeProfit_ATR  = 3.2;      // Gold Target in ATR
input double   InpXAU_BE_Trigger_ATR  = 1.5;      // Gold Breakeven in ATR
input double   InpXAU_BE_Buffer_ATR   = 0.10;     // Gold Breakeven Cushion in ATR
input double   InpXAU_Lock_Trigger_ATR= 2.8;      // Gold Lock Trigger in ATR
input double   InpXAU_Lock_Buffer_ATR = 1.20;     // Gold Lock Cushion in ATR
input ulong    InpXAU_Magic           = 690001;   // Gold Magic Number

input group "=== Forex Parameters (EURUSD) ==="
input double   InpEUR_InitialSL_ATR   = 1.5;      // EURUSD Stop Loss in ATR
input double   InpEUR_TakeProfit_ATR  = 2.4;      // EURUSD Target in ATR
input double   InpEUR_BE_Trigger_ATR  = 1.2;      // EURUSD Breakeven in ATR
input double   InpEUR_BE_Buffer_ATR   = 0.05;     // EURUSD Breakeven Cushion in ATR
input ulong    InpEUR_Magic           = 690002;   // EURUSD Magic Number

input group "=== Session Filters ==="
input bool     InpFilterSessions      = true;     // Restrict to Liquid Sessions
input int      InpTradeStartHour      = 7;
input int      InpTradeEndHour        = 18;
input int      InpSlippagePoints      = 30;

//--- Global Handles & State
int      h_atr_xau, h_atr_eur;
int      h_ema20_xau, h_ema60_xau;
int      h_ema20_eur, h_ema60_eur;
double   g_dailyStartEquity = 0.0;
int      g_lastDay = -1;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   h_atr_xau = iATR(InpGoldSymbol, PERIOD_M1, 14);
   h_atr_eur = iATR(InpForexSymbol, PERIOD_M1, 14);

   h_ema20_xau = iMA(InpGoldSymbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60_xau = iMA(InpGoldSymbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);

   h_ema20_eur = iMA(InpForexSymbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h_ema60_eur = iMA(InpForexSymbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr_xau == INVALID_HANDLE || h_atr_eur == INVALID_HANDLE ||
      h_ema20_xau == INVALID_HANDLE || h_ema60_xau == INVALID_HANDLE ||
      h_ema20_eur == INVALID_HANDLE || h_ema60_eur == INVALID_HANDLE)
   {
      Print("[!] Error creating multi-asset technical indicator handles");
      return INIT_FAILED;
   }

   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   MqlDateTime dt;
   TimeCurrent(dt);
   g_lastDay = dt.day;

   Print("[+] EA_EXP69_Multi_Asset_Portfolio Initialized Successfully");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr_xau);
   IndicatorRelease(h_atr_eur);
   IndicatorRelease(h_ema20_xau);
   IndicatorRelease(h_ema60_xau);
   IndicatorRelease(h_ema20_eur);
   IndicatorRelease(h_ema60_eur);
}

//+------------------------------------------------------------------+
//| Manage Active Positions Across Both Sleeves                      |
//+------------------------------------------------------------------+
void ManagePortfolioPositions(double atr_x, double atr_e)
{
   if(PositionsTotal() == 0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      string pos_sym = PositionGetString(POSITION_SYMBOL);
      ulong  magic   = PositionGetInteger(POSITION_MAGIC);

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
      request.symbol   = pos_sym;

      // XAUUSD Position Management
      if(pos_sym == InpGoldSymbol && magic == InpXAU_Magic)
      {
         if(pos_type == POSITION_TYPE_BUY)
         {
            double dist = curr_p - open_p;
            double new_sl = curr_sl;
            if(dist >= InpXAU_BE_Trigger_ATR * atr_x && curr_sl < open_p)
               new_sl = open_p + InpXAU_BE_Buffer_ATR * atr_x;
            if(dist >= InpXAU_Lock_Trigger_ATR * atr_x && curr_sl < (open_p + InpXAU_Lock_Buffer_ATR * atr_x))
               new_sl = open_p + InpXAU_Lock_Buffer_ATR * atr_x;

            if(new_sl > curr_sl && new_sl < curr_p)
            {
               request.sl = NormalizeDouble(new_sl, (int)SymbolInfoInteger(pos_sym, SYMBOL_DIGITS));
               request.tp = curr_tp;
               OrderSend(request, result);
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            double dist = open_p - curr_p;
            double new_sl = curr_sl;
            if(dist >= InpXAU_BE_Trigger_ATR * atr_x && (curr_sl == 0.0 || curr_sl > open_p))
               new_sl = open_p - InpXAU_BE_Buffer_ATR * atr_x;
            if(dist >= InpXAU_Lock_Trigger_ATR * atr_x && curr_sl > (open_p - InpXAU_Lock_Buffer_ATR * atr_x))
               new_sl = open_p - InpXAU_Lock_Buffer_ATR * atr_x;

            if(new_sl > 0.0 && (curr_sl == 0.0 || new_sl < curr_sl) && new_sl > curr_p)
            {
               request.sl = NormalizeDouble(new_sl, (int)SymbolInfoInteger(pos_sym, SYMBOL_DIGITS));
               request.tp = curr_tp;
               OrderSend(request, result);
            }
         }
      }
      // EURUSD Position Management
      else if(pos_sym == InpForexSymbol && magic == InpEUR_Magic)
      {
         if(pos_type == POSITION_TYPE_BUY)
         {
            double dist = curr_p - open_p;
            double new_sl = curr_sl;
            if(dist >= InpEUR_BE_Trigger_ATR * atr_e && curr_sl < open_p)
               new_sl = open_p + InpEUR_BE_Buffer_ATR * atr_e;

            if(new_sl > curr_sl && new_sl < curr_p)
            {
               request.sl = NormalizeDouble(new_sl, (int)SymbolInfoInteger(pos_sym, SYMBOL_DIGITS));
               request.tp = curr_tp;
               OrderSend(request, result);
            }
         }
         else if(pos_type == POSITION_TYPE_SELL)
         {
            double dist = open_p - curr_p;
            double new_sl = curr_sl;
            if(dist >= InpEUR_BE_Trigger_ATR * atr_e && (curr_sl == 0.0 || curr_sl > open_p))
               new_sl = open_p - InpEUR_BE_Buffer_ATR * atr_e;

            if(new_sl > 0.0 && (curr_sl == 0.0 || new_sl < curr_sl) && new_sl > curr_p)
            {
               request.sl = NormalizeDouble(new_sl, (int)SymbolInfoInteger(pos_sym, SYMBOL_DIGITS));
               request.tp = curr_tp;
               OrderSend(request, result);
            }
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

   double atr_x_arr[1], atr_e_arr[1];
   if(CopyBuffer(h_atr_xau, 0, 0, 1, atr_x_arr) <= 0) return;
   if(CopyBuffer(h_atr_eur, 0, 0, 1, atr_e_arr) <= 0) return;
   double atr_x = atr_x_arr[0];
   double atr_e = atr_e_arr[0];
   if(atr_x <= 0.0 || atr_e <= 0.0) return;

   ManagePortfolioPositions(atr_x, atr_e);

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

   if(InpFilterSessions)
   {
      if(dt.day_of_week == 5 && dt.hour >= 18) return;
      if(dt.hour < InpTradeStartHour || dt.hour >= InpTradeEndHour) return;
   }

   // --- Evaluate XAUUSD Sleeve ---
   bool has_xau_pos = false;
   bool has_eur_pos = false;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong t = PositionGetTicket(i);
      if(t <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == InpGoldSymbol && PositionGetInteger(POSITION_MAGIC) == InpXAU_Magic) has_xau_pos = true;
      if(PositionGetString(POSITION_SYMBOL) == InpForexSymbol && PositionGetInteger(POSITION_MAGIC) == InpEUR_Magic) has_eur_pos = true;
   }

   MqlRates r_xau[];
   ArraySetAsSeries(r_xau, true);
   if(!has_xau_pos && CopyRates(InpGoldSymbol, PERIOD_M1, 1, 65, r_xau) >= 65)
   {
      double c1 = r_xau[0].close, o1 = r_xau[0].open, h1 = r_xau[0].high, l1 = r_xau[0].low;
      double rng = MathMax(h1 - l1, 0.01);
      double u_wick = h1 - MathMax(c1, o1);
      double l_wick = MathMin(c1, o1) - l1;
      bool bull_pin = (l_wick >= 0.38 * rng) && (u_wick <= 0.28 * rng) && (c1 >= o1);
      bool bear_pin = (u_wick >= 0.38 * rng) && (l_wick <= 0.28 * rng) && (c1 <= o1);

      double vol_sum = 0.0;
      for(int i = 0; i < 20; i++) vol_sum += r_xau[i].tick_volume;
      double rel_v = r_xau[0].tick_volume / MathMax(vol_sum / 20.0, 1.0);
      double vfs_x = rel_v * (MathAbs(c1 - o1) / atr_x);

      double ema20_x[1], ema60_x[1];
      CopyBuffer(h_ema20_xau, 0, 1, 1, ema20_x);
      CopyBuffer(h_ema60_xau, 0, 1, 1, ema60_x);
      bool mtf_bull_x = (c1 > ema20_x[0]) && (ema20_x[0] > ema60_x[0]);
      bool mtf_bear_x = (c1 < ema20_x[0]) && (ema20_x[0] < ema60_x[0]);

      if((bull_pin && mtf_bull_x && vfs_x >= 1.12) || (bear_pin && mtf_bear_x && vfs_x >= 1.15))
      {
         double dollar_risk = current_equity * (InpGoldRiskPercent / 100.0);
         double sl_dist = InpXAU_InitialSL_ATR * atr_x;
         double lots = MathFloor((dollar_risk / (sl_dist * 100.0)) / 0.01) * 0.01;
         lots = MathMin(10.0, MathMax(0.01, lots));

         MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
         req.action = TRADE_ACTION_DEAL; req.symbol = InpGoldSymbol; req.volume = lots;
         req.magic = InpXAU_Magic; req.deviation = InpSlippagePoints; req.comment = "EXP-69 Gold Sleeve";
         if(bull_pin)
         {
            req.type = ORDER_TYPE_BUY; req.price = SymbolInfoDouble(InpGoldSymbol, SYMBOL_ASK);
            req.sl = NormalizeDouble(req.price - sl_dist, (int)SymbolInfoInteger(InpGoldSymbol, SYMBOL_DIGITS));
            req.tp = NormalizeDouble(req.price + InpXAU_TakeProfit_ATR * atr_x, (int)SymbolInfoInteger(InpGoldSymbol, SYMBOL_DIGITS));
            OrderSend(req, res);
         }
         else
         {
            req.type = ORDER_TYPE_SELL; req.price = SymbolInfoDouble(InpGoldSymbol, SYMBOL_BID);
            req.sl = NormalizeDouble(req.price + sl_dist, (int)SymbolInfoInteger(InpGoldSymbol, SYMBOL_DIGITS));
            req.tp = NormalizeDouble(req.price - InpXAU_TakeProfit_ATR * atr_x, (int)SymbolInfoInteger(InpGoldSymbol, SYMBOL_DIGITS));
            OrderSend(req, res);
         }
      }
   }

   // --- Evaluate EURUSD Sleeve ---
   MqlRates r_eur[];
   ArraySetAsSeries(r_eur, true);
   if(!has_eur_pos && CopyRates(InpForexSymbol, PERIOD_M1, 1, 65, r_eur) >= 65)
   {
      double c1_e = r_eur[0].close, o1_e = r_eur[0].open, h1_e = r_eur[0].high, l1_e = r_eur[0].low;
      double rng_e = MathMax(h1_e - l1_e, 0.00001);
      double u_wick_e = h1_e - MathMax(c1_e, o1_e);
      double l_wick_e = MathMin(c1_e, o1_e) - l1_e;
      bool bull_pin_e = (l_wick_e >= 0.40 * rng_e) && (u_wick_e <= 0.25 * rng_e) && (c1_e >= o1_e);
      bool bear_pin_e = (u_wick_e >= 0.40 * rng_e) && (l_wick_e <= 0.25 * rng_e) && (c1_e <= o1_e);

      double ema20_e[1], ema60_e[1];
      CopyBuffer(h_ema20_eur, 0, 1, 1, ema20_e);
      CopyBuffer(h_ema60_eur, 0, 1, 1, ema60_e);
      bool mtf_bull_e = (c1_e > ema20_e[0]) && (ema20_e[0] > ema60_e[0]);
      bool mtf_bear_e = (c1_e < ema20_e[0]) && (ema20_e[0] < ema60_e[0]);

      if((bull_pin_e && mtf_bull_e) || (bear_pin_e && mtf_bear_e))
      {
         double dollar_risk_e = current_equity * (InpForexRiskPercent / 100.0);
         double sl_dist_e = InpEUR_InitialSL_ATR * atr_e;
         double lots_e = MathFloor((dollar_risk_e / (sl_dist_e * 100000.0)) / 0.01) * 0.01;
         lots_e = MathMin(10.0, MathMax(0.01, lots_e));

         MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
         req.action = TRADE_ACTION_DEAL; req.symbol = InpForexSymbol; req.volume = lots_e;
         req.magic = InpEUR_Magic; req.deviation = InpSlippagePoints; req.comment = "EXP-69 Forex Sleeve";
         if(bull_pin_e)
         {
            req.type = ORDER_TYPE_BUY; req.price = SymbolInfoDouble(InpForexSymbol, SYMBOL_ASK);
            req.sl = NormalizeDouble(req.price - sl_dist_e, (int)SymbolInfoInteger(InpForexSymbol, SYMBOL_DIGITS));
            req.tp = NormalizeDouble(req.price + InpEUR_TakeProfit_ATR * atr_e, (int)SymbolInfoInteger(InpForexSymbol, SYMBOL_DIGITS));
            OrderSend(req, res);
         }
         else
         {
            req.type = ORDER_TYPE_SELL; req.price = SymbolInfoDouble(InpForexSymbol, SYMBOL_BID);
            req.sl = NormalizeDouble(req.price + sl_dist_e, (int)SymbolInfoInteger(InpForexSymbol, SYMBOL_DIGITS));
            req.tp = NormalizeDouble(req.price - InpEUR_TakeProfit_ATR * atr_e, (int)SymbolInfoInteger(InpForexSymbol, SYMBOL_DIGITS));
            OrderSend(req, res);
         }
      }
   }
}
//+------------------------------------------------------------------+

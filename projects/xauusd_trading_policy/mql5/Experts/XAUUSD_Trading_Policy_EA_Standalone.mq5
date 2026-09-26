//+------------------------------------------------------------------+
//|                      XAUUSD_Trading_Policy_EA_Standalone.mq5     |
//|                    Copyright 2026, BlamzKunG (GitHub: BlamzKunG) |
//|               https://github.com/BlamzKunG/CFD-Trading-ML |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, BlamzKunG (GitHub: BlamzKunG)"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.00"
#property description "Autonomous Closed-Loop ML Trading Policy & Position Management EA for XAUUSD M1"
#property strict

// Action Definitions
#define ACTION_HOLD        0
#define ACTION_OPEN_LONG   1
#define ACTION_OPEN_SHORT  2
#define ACTION_ADD         3
#define ACTION_REDUCE      4
#define ACTION_CLOSE       5
#define ACTION_REVERSE     6

#define NUM_MARKET_FEATURES   31
#define NUM_POSITION_FEATURES 9
#define TOTAL_FEATURES        40

//--- Input Parameters
input group "=== ML Policy Configuration ==="
input string   InpModelFileName        = "xauusd_trading_policy.onnx"; // ONNX Model File in MQL5/Files
input bool     InpEnableDynamicManage  = true;                         // Enable Dynamic Position Management (ADD/REDUCE/REVERSE)
input double   InpMinConfidence        = 0.35;                         // Minimum Action Probability Threshold

input group "=== Risk & Order Management ==="
input double   InpBaseLot              = 0.05;                         // Base Lot Size
input double   InpMaxLot               = 0.50;                         // Maximum Allowed Lot Size
input int      InpMagicNumber          = 888123;                       // EA Magic Number
input int      InpSlippage             = 20;                           // Max Slippage (points)
input double   InpMaxSpreadPoints      = 35.0;                         // Max Spread Filter (points)
input bool     InpTradeNewBarOnly      = true;                         // Execute on New M1 Bar Only

//--- Forward declarations & internal state
long     g_onnx_handle      = INVALID_HANDLE;
int      g_h_atr14          = INVALID_HANDLE;
int      g_h_atr50          = INVALID_HANDLE;
int      g_h_ema20          = INVALID_HANDLE;
int      g_h_ema50          = INVALID_HANDLE;
int      g_h_ema200         = INVALID_HANDLE;
int      g_h_rsi14          = INVALID_HANDLE;

datetime g_last_bar_time    = 0;
datetime g_pos_entry_time   = 0;
datetime g_last_action_time = 0;
double   g_max_adv_atr      = 0.0;
double   g_max_fav_atr      = 0.0;
string   g_last_action_str  = "INITIALIZED";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("==================================================================");
   Print(" Initializing XAUUSD Autonomous Trading Policy EA (Standalone)   ");
   Print(" Author: BlamzKunG | Repo: BlamzKunG/CFD-Trading-ML    ");
   Print("==================================================================");

   // 1. Attempt to load ONNX Model
   g_onnx_handle = OnnxCreate(InpModelFileName, ONNX_DEFAULT);
   if(g_onnx_handle == INVALID_HANDLE)
   {
      PrintFormat("[EA Init] Warning: ONNX Model '%s' not found or failed to load (Error %d).", InpModelFileName, GetLastError());
      Print("[EA Init] EA will run in Adaptive Heuristic Engine mode until ONNX model is placed in MQL5/Files.");
   }
   else
   {
      PrintFormat("[EA Init] Success: ONNX Model '%s' successfully loaded!", InpModelFileName);
   }

   // 2. Initialize Core Indicator Handles
   g_h_atr14  = iATR(_Symbol, PERIOD_M1, 14);
   g_h_atr50  = iATR(_Symbol, PERIOD_M1, 50);
   g_h_ema20  = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_h_ema50  = iMA(_Symbol, PERIOD_M1, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_h_ema200 = iMA(_Symbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_h_rsi14  = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);

   if(g_h_atr14 == INVALID_HANDLE || g_h_ema200 == INVALID_HANDLE)
   {
      Print("[EA Init] Error creating indicator handles. Error: ", GetLastError());
      return INIT_FAILED;
   }

   g_last_bar_time = 0;
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_onnx_handle != INVALID_HANDLE)
   {
      OnnxRelease(g_onnx_handle);
      g_onnx_handle = INVALID_HANDLE;
   }
   IndicatorRelease(g_h_atr14);
   IndicatorRelease(g_h_atr50);
   IndicatorRelease(g_h_ema20);
   IndicatorRelease(g_h_ema50);
   IndicatorRelease(g_h_ema200);
   IndicatorRelease(g_h_rsi14);
   Comment("");
}

//+------------------------------------------------------------------+
//| Check for New M1 Bar                                             |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime cur_time = (datetime)SeriesInfoInteger(_Symbol, PERIOD_M1, SERIES_LASTBAR_DATE);
   if(cur_time != g_last_bar_time)
   {
      g_last_bar_time = cur_time;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Compute Scale-Invariant Market State Features (31)               |
//+------------------------------------------------------------------+
bool ExtractMarketFeatures(float &features[], double &out_atr14)
{
   ArrayResize(features, NUM_MARKET_FEATURES);
   ArrayInitialize(features, 0.0f);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 0, 205, rates) < 205) return false;

   double atr14_b[], atr50_b[], ema20_b[], ema50_b[], ema200_b[], rsi_b[];
   ArraySetAsSeries(atr14_b, true);
   ArraySetAsSeries(atr50_b, true);
   ArraySetAsSeries(ema20_b, true);
   ArraySetAsSeries(ema50_b, true);
   ArraySetAsSeries(ema200_b, true);
   ArraySetAsSeries(rsi_b, true);

   if(CopyBuffer(g_h_atr14, 0, 0, 5, atr14_b) < 1) return false;
   if(CopyBuffer(g_h_atr50, 0, 0, 5, atr50_b) < 1) return false;
   if(CopyBuffer(g_h_ema20, 0, 0, 5, ema20_b) < 1) return false;
   if(CopyBuffer(g_h_ema50, 0, 0, 5, ema50_b) < 1) return false;
   if(CopyBuffer(g_h_ema200, 0, 0, 5, ema200_b) < 1) return false;
   if(CopyBuffer(g_h_rsi14, 0, 0, 5, rsi_b) < 1) return false;

   double c0    = rates[0].close;
   double atr14 = MathMax(atr14_b[0], 0.01);
   double atr50 = MathMax(atr50_b[0], 0.01);
   out_atr14   = atr14;

   // 1. Multi-Horizon Log Returns
   features[0] = (float)MathLog(c0 / rates[1].close);
   features[1] = (float)MathLog(c0 / rates[3].close);
   features[2] = (float)MathLog(c0 / rates[5].close);
   features[3] = (float)MathLog(c0 / rates[15].close);
   features[4] = (float)MathLog(c0 / rates[30].close);
   features[5] = (float)MathLog(c0 / rates[60].close);

   // 2. Volatility & Normalized Movement
   features[6] = (float)(atr14 / c0);
   features[7] = (float)(atr14 / atr50);

   double sum_r = 0.0, sq_r = 0.0;
   for(int i = 0; i < 30; i++)
   {
      double r = MathLog(rates[i].close / rates[i+1].close);
      sum_r += r;
      sq_r += r * r;
   }
   double mean_r = sum_r / 30.0;
   features[8] = (float)MathSqrt(MathMax(0.0, (sq_r / 30.0) - (mean_r * mean_r)));

   features[9]  = (float)((c0 - rates[5].close) / atr14);
   features[10] = (float)((c0 - rates[15].close) / atr14);
   features[11] = (float)((c0 - rates[60].close) / atr14);

   // 3. Normalized Candlestick Microstructure
   double bar_rng = MathMax(rates[0].high - rates[0].low, 0.001);
   features[12] = (float)((c0 - rates[0].open) / atr14);
   features[13] = (float)(bar_rng / atr14);
   features[14] = (float)((rates[0].high - MathMax(rates[0].open, c0)) / bar_rng);
   features[15] = (float)((MathMin(rates[0].open, c0) - rates[0].low) / bar_rng);
   features[16] = (float)((c0 - rates[0].low) / bar_rng);

   // 4. Local Price Distribution
   double sum20 = 0.0, sq20 = 0.0;
   for(int i = 0; i < 20; i++) { sum20 += rates[i].close; sq20 += rates[i].close * rates[i].close; }
   double m20 = sum20 / 20.0;
   double std20 = MathSqrt(MathMax(0.0001, (sq20 / 20.0) - (m20 * m20)));
   features[17] = (float)((c0 - m20) / std20);

   double sum100 = 0.0, sq100 = 0.0;
   for(int i = 0; i < 100; i++) { sum100 += rates[i].close; sq100 += rates[i].close * rates[i].close; }
   double m100 = sum100 / 100.0;
   double std100 = MathSqrt(MathMax(0.0001, (sq100 / 100.0) - (m100 * m100)));
   features[18] = (float)((c0 - m100) / std100);

   double min60 = rates[0].low, max60 = rates[0].high;
   for(int i = 1; i < 60; i++)
   {
      if(rates[i].low < min60)   min60 = rates[i].low;
      if(rates[i].high > max60) max60 = rates[i].high;
   }
   features[19] = (float)((c0 - min60) / MathMax(0.001, max60 - min60));

   // 5. Momentum & Normalized EMA Distances
   features[20] = (float)((c0 - ema20_b[0]) / atr14);
   features[21] = (float)((c0 - ema50_b[0]) / atr14);
   features[22] = (float)((c0 - ema200_b[0]) / atr14);
   features[23] = (float)(rsi_b[0] / 100.0);

   // 6. Macro EMA Ratio
   features[24] = (float)MathLog(c0 / MathMax(0.01, ema200_b[0]));

   // 7. Volume Ratios
   double v20 = 0.0, v100 = 0.0;
   for(int i = 0; i < 100; i++)
   {
      if(i < 20) v20 += rates[i].tick_volume;
      v100 += rates[i].tick_volume;
   }
   features[25] = (float)(rates[0].tick_volume / MathMax(1.0, v20 / 20.0));
   features[26] = (float)(rates[0].tick_volume / MathMax(1.0, v100 / 100.0));

   // 8. Cyclic Time Context
   MqlDateTime dt;
   TimeToStruct(rates[0].time, dt);
   double hour_f = dt.hour + dt.min / 60.0;
   double pi2 = 2.0 * M_PI;
   features[27] = (float)MathSin(pi2 * hour_f / 24.0);
   features[28] = (float)MathCos(pi2 * hour_f / 24.0);
   features[29] = (float)MathSin(pi2 * dt.day_of_week / 5.0);
   features[30] = (float)MathCos(pi2 * dt.day_of_week / 5.0);

   return true;
}

//+------------------------------------------------------------------+
//| Get Position Details                                             |
//+------------------------------------------------------------------+
bool GetCurrentPosition(double &out_dir, double &out_lot, double &out_entry, double &out_sl, double &out_tp, ulong &out_ticket)
{
   out_dir = 0.0; out_lot = 0.0; out_entry = 0.0; out_sl = 0.0; out_tp = 0.0; out_ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         long pos_type = PositionGetInteger(POSITION_TYPE);
         out_dir    = (pos_type == POSITION_TYPE_BUY) ? 1.0 : -1.0;
         out_lot    = PositionGetDouble(POSITION_VOLUME);
         out_entry  = PositionGetDouble(POSITION_PRICE_OPEN);
         out_sl     = PositionGetDouble(POSITION_SL);
         out_tp     = PositionGetDouble(POSITION_TP);
         out_ticket = ticket;
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Trade Execution Helpers                                          |
//+------------------------------------------------------------------+
bool OpenTrade(ENUM_ORDER_TYPE order_type, double lot, double sl_price, double tp_price)
{
   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = _Symbol;
   request.volume       = NormalizeDouble(lot, 2);
   request.type         = order_type;
   request.price        = (order_type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   request.sl           = NormalizeDouble(sl_price, _Digits);
   request.tp           = NormalizeDouble(tp_price, _Digits);
   request.deviation    = InpSlippage;
   request.magic        = InpMagicNumber;
   request.comment      = "ML_Policy_Trade";
   request.type_filling = ORDER_FILLING_IOC;

   return OrderSend(request, result);
}

bool ClosePosition(ulong ticket, double lot)
{
   if(!PositionSelectByTicket(ticket)) return false;

   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

   long pos_type = PositionGetInteger(POSITION_TYPE);
   request.action       = TRADE_ACTION_DEAL;
   request.position     = ticket;
   request.symbol       = _Symbol;
   request.volume       = NormalizeDouble(lot, 2);
   request.type         = (pos_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   request.price        = (pos_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   request.deviation    = InpSlippage;
   request.magic        = InpMagicNumber;
   request.comment      = "ML_Policy_Close";
   request.type_filling = ORDER_FILLING_IOC;

   return OrderSend(request, result);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(InpTradeNewBarOnly && !IsNewBar()) return;

   // Spread Filter
   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   if(spread > InpMaxSpreadPoints)
   {
      Comment(StringFormat("Status: SPREAD_FILTERED | Spread: %.1f > Max: %.1f", spread, InpMaxSpreadPoints));
      return;
   }

   // 1. Extract Market Features
   float market_feats[];
   double atr14 = 0.0;
   if(!ExtractMarketFeatures(market_feats, atr14)) return;

   // 2. Extract Position Features
   double pos_dir = 0.0, pos_lot = 0.0, entry_price = 0.0, cur_sl = 0.0, cur_tp = 0.0;
   ulong  ticket = 0;
   bool in_position = GetCurrentPosition(pos_dir, pos_lot, entry_price, cur_sl, cur_tp, ticket);

   double cur_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(!in_position)
   {
      g_pos_entry_time = 0;
      g_max_adv_atr = 0.0;
      g_max_fav_atr = 0.0;
   }
   else
   {
      if(g_pos_entry_time == 0) g_pos_entry_time = TimeCurrent();
      double adv = (pos_dir > 0) ? (entry_price - cur_price) / atr14 : (cur_price - entry_price) / atr14;
      g_max_adv_atr = MathMax(g_max_adv_atr, adv);
   }

   float pos_feats[NUM_POSITION_FEATURES];
   pos_feats[0] = (float)pos_dir;
   pos_feats[1] = (float)(in_position ? MathMin(1.0, pos_lot / InpMaxLot) : 0.0);
   pos_feats[2] = (float)(in_position ? (cur_price - entry_price) / atr14 : 0.0);
   pos_feats[3] = (float)(in_position ? pos_dir * (cur_price - entry_price) / atr14 : 0.0);

   int bars_in_pos = (g_pos_entry_time > 0) ? (int)((TimeCurrent() - g_pos_entry_time) / 60) : 0;
   pos_feats[4] = (float)MathMin(1.0, bars_in_pos / 120.0);
   pos_feats[5] = (float)(cur_sl > 0 ? MathAbs(cur_price - cur_sl) / atr14 : 0.0);
   pos_feats[6] = (float)(cur_tp > 0 ? MathAbs(cur_price - cur_tp) / atr14 : 0.0);
   pos_feats[7] = (float)g_max_adv_atr;
   int bars_act = (g_last_action_time > 0) ? (int)((TimeCurrent() - g_last_action_time) / 60) : 60;
   pos_feats[8] = (float)MathMin(1.0, bars_act / 60.0);

   // Concatenate 40 inputs
   float input_tensor[TOTAL_FEATURES];
   for(int i = 0; i < NUM_MARKET_FEATURES; i++)   input_tensor[i] = market_feats[i];
   for(int j = 0; j < NUM_POSITION_FEATURES; j++) input_tensor[NUM_MARKET_FEATURES + j] = pos_feats[j];

   int    action = ACTION_HOLD;
   double size_frac = 0.5;
   double sl_atr = 2.0;
   double tp_atr = 3.5;

   // 3. Evaluate Policy Decision
   if(g_onnx_handle != INVALID_HANDLE)
   {
      float act_probs[7];
      float sz_pred[1];
      float ord_pred[2];
      if(OnnxRun(g_onnx_handle, ONNX_NO_CONVERSION, input_tensor, act_probs, sz_pred, ord_pred))
      {
         int best_a = 0;
         float best_p = act_probs[0];
         for(int a = 1; a < 7; a++)
         {
            if(act_probs[a] > best_p)
            {
               best_p = act_probs[a];
               best_a = a;
            }
         }
         action    = best_a;
         size_frac = MathMin(1.0, MathMax(0.1, (double)sz_pred[0]));
         sl_atr    = MathMin(4.0, MathMax(1.0, (double)ord_pred[0]));
         tp_atr    = MathMin(7.0, MathMax(1.5, (double)ord_pred[1]));
      }
   }
   else
   {
      // Adaptive Heuristic Fallback Policy
      float mom15 = market_feats[3];
      float z20   = market_feats[17];
      float dist_ema50 = market_feats[21];
      float rsi   = market_feats[23];

      if(!in_position)
      {
         if(mom15 > 0.0015 && z20 > 0.5 && dist_ema50 > 0.3 && rsi < 0.70)
            action = ACTION_OPEN_LONG;
         else if(mom15 < -0.0015 && z20 < -0.5 && dist_ema50 < -0.3 && rsi > 0.30)
            action = ACTION_OPEN_SHORT;
      }
      else
      {
         double unrl = pos_feats[3];
         if(unrl < -1.5)
            action = ACTION_CLOSE;
         else if(unrl > 2.5 && ((pos_dir > 0 && rsi > 0.8) || (pos_dir < 0 && rsi < 0.2)))
            action = ACTION_REDUCE;
      }
   }

   // 4. Execute Action
   double trade_lot = NormalizeDouble(MathMin(InpMaxLot, MathMax(InpBaseLot * size_frac, 0.01)), 2);

   if(!in_position)
   {
      if(action == ACTION_OPEN_LONG)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl  = ask - (sl_atr * atr14);
         double tp  = ask + (tp_atr * atr14);
         if(OpenTrade(ORDER_TYPE_BUY, trade_lot, sl, tp))
         {
            g_last_action_str = "OPENED_LONG";
            g_last_action_time = TimeCurrent();
         }
      }
      else if(action == ACTION_OPEN_SHORT)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl  = bid + (sl_atr * atr14);
         double tp  = bid - (tp_atr * atr14);
         if(OpenTrade(ORDER_TYPE_SELL, trade_lot, sl, tp))
         {
            g_last_action_str = "OPENED_SHORT";
            g_last_action_time = TimeCurrent();
         }
      }
   }
   else if(InpEnableDynamicManage)
   {
      if(action == ACTION_CLOSE)
      {
         if(ClosePosition(ticket, pos_lot))
         {
            g_last_action_str = "POLICY_CLOSED";
            g_last_action_time = TimeCurrent();
         }
      }
      else if(action == ACTION_REDUCE && pos_lot >= (InpBaseLot * 1.5))
      {
         double reduce_lot = NormalizeDouble(pos_lot * 0.5, 2);
         if(ClosePosition(ticket, reduce_lot))
         {
            g_last_action_str = "POLICY_REDUCED_50%";
            g_last_action_time = TimeCurrent();
         }
      }
      else if(action == ACTION_ADD && (pos_lot + trade_lot * 0.5) <= InpMaxLot)
      {
         double add_lot = NormalizeDouble(trade_lot * 0.5, 2);
         ENUM_ORDER_TYPE ot = (pos_dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
         if(OpenTrade(ot, add_lot, cur_sl, cur_tp))
         {
            g_last_action_str = "POLICY_ADDED_LOT";
            g_last_action_time = TimeCurrent();
         }
      }
      else if(action == ACTION_REVERSE)
      {
         if(ClosePosition(ticket, pos_lot))
         {
            ENUM_ORDER_TYPE ot = (pos_dir > 0) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
            double p = (ot == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = (ot == ORDER_TYPE_BUY) ? p - (sl_atr * atr14) : p + (sl_atr * atr14);
            double tp = (ot == ORDER_TYPE_BUY) ? p + (tp_atr * atr14) : p - (tp_atr * atr14);
            OpenTrade(ot, trade_lot, sl, tp);
            g_last_action_str = "POLICY_REVERSED";
            g_last_action_time = TimeCurrent();
         }
      }
   }

   // 5. On-Chart Dashboard
   string dash = "========================================================\n";
   dash += "   🚀 XAUUSD AUTONOMOUS ML POLICY EA (STANDALONE)      \n";
   dash += "   Author: BlamzKunG | Repo: BlamzKunG/CFD-Trading-ML\n";
   dash += "========================================================\n";
   dash += StringFormat(" Engine Mode:         %s\n", (g_onnx_handle != INVALID_HANDLE) ? "DEEP ONNX POLICY AGENT" : "ADAPTIVE HEURISTIC");
   dash += StringFormat(" Position State:      %s (Vol: %.2f Lots)\n", (pos_dir > 0 ? "LONG" : (pos_dir < 0 ? "SHORT" : "FLAT")), pos_lot);
   dash += StringFormat(" Unrealized PnL:      %.2f ATR (Entry: %.2f)\n", pos_feats[3], entry_price);
   dash += StringFormat(" ATR (14) Volatility: %.2f Points ($%.2f)\n", atr14 / _Point, atr14);
   dash += StringFormat(" Decision Action:     %d (Target SL: %.1f ATR | TP: %.1f ATR)\n", action, sl_atr, tp_atr);
   dash += StringFormat(" Last Action Event:   %s\n", g_last_action_str);
   dash += "========================================================\n";
   Comment(dash);
}

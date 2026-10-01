//+------------------------------------------------------------------+
//|  EA_EXP42_Unified_Alpha_Engine.mq5                               |
//|  XAUUSD M1 — Unified Macro-Micro Alpha Super-Pipeline            |
//|  Research: Autonomous Quant ML Research EXP-42                   |
//|                                                                  |
//|  Architecture:                                                   |
//|  1. Distilled Deep Quantile Policy Net (Native MT5 ONNX)         |
//|  2. Input: float32[1, 32] (31 market features + EURUSD 15m ret)  |
//|  3. Output: action_probs[1, 3], position_size[1, 1], order[1, 2] |
//|  4. Cross-Asset USDi Macro Confluence Gating                     |
//|  5. Dynamic Volatility Regime Gating (20-85th ATR Percentile)    |
//|  6. Accelerated 45-bar Stagnation Stop Ratchet                   |
//|  7. 3-Tier Asymmetric Profit-Harvesting Excursion Trailing (APHE)|
//|  8. Counterfactual Friction & Rollover Protection Shield         |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-42 Unified Alpha"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== ONNX Model Configuration ==="
input string   InpONNXFilename         = "exp42_unified_alpha_engine.onnx";
input double   InpDecisionThreshold    = 0.45;    // Probability threshold for Long/Short

input group "=== Cross-Asset Macro Settings ==="
input string   InpMacroSymbol          = "EURUSD"; // Macro confluence anchor symbol
input double   InpMaxUSDiRet           = 0.0004;   // USDi threshold (+0.04% / -0.04%)

input group "=== Dynamic Regime & Stagnation Settings ==="
input bool     InpUseRegimeFilter      = true;     // Reject Low Chop (<20%) & Shock (>85%)
input int      InpRegimeLookback       = 100;      // Rolling ATR lookback
input bool     InpUseStagnationRatchet = true;     // Tighten SL if stalling at bar 45
input int      InpStagnationBar        = 45;       // Stagnation evaluation bar
input double   InpStagnationProgress   = 0.25;     // Min excursion progress required (25%)

input group "=== Asymmetric Profit-Harvesting Trailing (APHE) ==="
input bool     InpUseAPHE              = true;     // Enable 3-Tier Excursion Trailing
input double   InpTier1_Excursion      = 0.50;     // 50% TP progress -> Lock Breakeven
input double   InpTier2_Excursion      = 0.70;     // 70% TP progress -> Lock 35%
input double   InpTier3_Excursion      = 0.85;     // 85% TP progress -> Lock 65%

input group "=== Risk & Execution Management ==="
input double   InpRiskPercent          = 0.85;     // Account risk % per trade (0.85% VTS)
input double   InpMinLot               = 0.02;
input double   InpMaxLot               = 0.50;
input double   InpMaxSpreadPoints      = 3.0;      // Friction Shield (max spread 3.0 pts / $0.30)
input bool     InpRolloverShield       = true;     // Pause during 21:30-23:30 UTC
input bool     InpFridayShield         = true;     // Pause Friday after 17:00 UTC
input ulong    InpMagicNumber          = 420042;
input string   InpComment              = "EXP42_UnifiedAlpha";

//--- Globals
long     g_onnxHandle = INVALID_HANDLE;
CTrade   g_trade;
int      g_atrHandle  = INVALID_HANDLE;
int      g_ema20h     = INVALID_HANDLE;
int      g_ema60h     = INVALID_HANDLE;
int      g_ema240h    = INVALID_HANDLE;

// Position State
datetime g_entryTime       = 0;
int      g_entryBar        = 0;
double   g_entryPrice      = 0.0;
double   g_targetTP        = 0.0;
double   g_targetSL        = 0.0;
double   g_maxExcursion    = 0.0;
int      g_trailTier       = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetMarginMode();

   // 1. Initialize ONNX Model
   g_onnxHandle = OnnxCreate(InpONNXFilename, ONNX_DEFAULT);
   if(g_onnxHandle == INVALID_HANDLE)
   {
      PrintFormat("[EXP-42] Error: Could not load ONNX model '%s'. Error code: %d", InpONNXFilename, GetLastError());
      return(INIT_FAILED);
   }

   // 2. Set ONNX Input Dimensions [1, 32]
   const long in_shape[] = {1, 32};
   if(!OnnxSetInputShape(g_onnxHandle, 0, in_shape))
   {
      PrintFormat("[EXP-42] Error: Failed to set ONNX input shape [1, 32]. Error: %d", GetLastError());
      OnnxRelease(g_onnxHandle);
      g_onnxHandle = INVALID_HANDLE;
      return(INIT_FAILED);
   }

   // 3. Set ONNX Output Dimensions
   const long out_shape_probs[]  = {1, 3};
   const long out_shape_size[]   = {1, 1};
   const long out_shape_orders[] = {1, 2};
   OnnxSetOutputShape(g_onnxHandle, 0, out_shape_probs);
   OnnxSetOutputShape(g_onnxHandle, 1, out_shape_size);
   OnnxSetOutputShape(g_onnxHandle, 2, out_shape_orders);

   // 4. Indicator Handles
   g_atrHandle = iATR(_Symbol, PERIOD_M1, 14);
   g_ema20h    = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_ema60h    = iMA(_Symbol, PERIOD_M1, 60, 0, MODE_EMA, PRICE_CLOSE);
   g_ema240h   = iMA(_Symbol, PERIOD_M1, 240, 0, MODE_EMA, PRICE_CLOSE);

   PrintFormat("[EXP-42] Successfully initialized Native ONNX Engine '%s'. Magic: %d", InpONNXFilename, InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_onnxHandle != INVALID_HANDLE)
   {
      OnnxRelease(g_onnxHandle);
      g_onnxHandle = INVALID_HANDLE;
   }
   if(g_atrHandle != INVALID_HANDLE)  IndicatorRelease(g_atrHandle);
   if(g_ema20h != INVALID_HANDLE)     IndicatorRelease(g_ema20h);
   if(g_ema60h != INVALID_HANDLE)     IndicatorRelease(g_ema60h);
   if(g_ema240h != INVALID_HANDLE)    IndicatorRelease(g_ema240h);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Only process on bar open
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // 1. Friction & Spread Shield
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread = (ask - bid) / (point * 10.0);

   if(spread > InpMaxSpreadPoints)
   {
      PrintFormat("[EXP-42] Spread too high: %.1f > %.1f. Skipping bar.", spread, InpMaxSpreadPoints);
      return;
   }

   // 2. Session & Timing Filter
   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;
   int minute = dt.min;
   int dow = dt.day_of_week;

   // Friday Shield: block entries after 17:00 UTC
   if(InpFridayShield && dow == 5 && hour >= 17) return;

   // Rollover Shield: block entries 21:30 - 23:30 UTC
   if(InpRolloverShield)
   {
      if((hour == 21 && minute >= 30) || hour == 22 || (hour == 23 && minute <= 30)) return;
   }

   // Liquid trading window: 07:00 - 19:00 UTC
   if(hour < 7 || hour >= 19) return;

   // 3. Manage Existing Open Positions
   ManageActivePosition();

   // If already in position, do not open new trades
   if(PositionsTotal() > 0) return;

   // 4. Volatility Regime Filter
   double atr_val = GetATR(1);
   if(atr_val <= 0.0) return;

   if(InpUseRegimeFilter)
   {
      double atr_rank = ComputeATRRank(InpRegimeLookback);
      if(atr_rank < 0.20 || atr_rank > 0.85)
      {
         // Suppress entries during Chop (<20%) or Extreme Macro Shock (>85%)
         return;
      }
   }

   // 5. Cross-Asset EURUSD Macro Filter
   double eur_close1 = iClose(InpMacroSymbol, PERIOD_M1, 1);
   double eur_close16 = iClose(InpMacroSymbol, PERIOD_M1, 16);
   if(eur_close16 <= 0.0) return;
   double eur_ret15 = (eur_close1 - eur_close16) / eur_close16;

   // 6. Build 32-Feature State Vector
   float state_vector[32];
   if(!BuildStateVector(state_vector, (float)eur_ret15)) return;

   // 7. Execute ONNX Inference
   float action_probs[3];
   float pos_size[1];
   float order_params[2];

   if(!OnnxRun(g_onnxHandle, ONNX_NO_CONVERSION, state_vector, action_probs, pos_size, order_params))
   {
      PrintFormat("[EXP-42] OnnxRun execution failed. Error: %d", GetLastError());
      return;
   }

   float prob_hold  = action_probs[0];
   float prob_long  = action_probs[1];
   float prob_short = action_probs[2];

   // 8. Order Execution Gating
   double sl_mult = MathMax(1.4, MathMin(3.5, (double)order_params[0]));
   double tp_mult = MathMax(2.0, MathMin(7.5, (double)order_params[1]));

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_usd = balance * (InpRiskPercent / 100.0);
   double sl_dist = sl_mult * atr_val;
   double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_sz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double lot = (sl_dist > 0 && tick_val > 0) ? (risk_usd / (sl_dist / tick_sz * tick_val)) : InpMinLot;
   lot = MathMax(InpMinLot, MathMin(InpMaxLot, NormalizeDouble(lot, 2)));

   // Long Signal
   if(prob_long >= InpDecisionThreshold && prob_long > prob_short && eur_ret15 >= -InpMaxUSDiRet)
   {
      double sl = NormalizeDouble(ask - sl_dist, _Digits);
      double tp = NormalizeDouble(ask + tp_mult * atr_val, _Digits);

      if(g_trade.Buy(lot, _Symbol, ask, sl, tp, InpComment))
      {
         g_entryTime = TimeCurrent();
         g_entryBar = 0;
         g_entryPrice = ask;
         g_targetTP = tp;
         g_targetSL = sl;
         g_maxExcursion = 0.0;
         g_trailTier = 0;
         PrintFormat("[EXP-42] BUY executed: %.2f lots at %.2f, SL: %.2f, TP: %.2f (Prob: %.3f)", lot, ask, sl, tp, prob_long);
      }
   }
   // Short Signal
   else if(prob_short >= InpDecisionThreshold && prob_short > prob_long && eur_ret15 <= InpMaxUSDiRet)
   {
      double sl = NormalizeDouble(bid + sl_dist, _Digits);
      double tp = NormalizeDouble(bid - tp_mult * atr_val, _Digits);

      if(g_trade.Sell(lot, _Symbol, bid, sl, tp, InpComment))
      {
         g_entryTime = TimeCurrent();
         g_entryBar = 0;
         g_entryPrice = bid;
         g_targetTP = tp;
         g_targetSL = sl;
         g_maxExcursion = 0.0;
         g_trailTier = 0;
         PrintFormat("[EXP-42] SELL executed: %.2f lots at %.2f, SL: %.2f, TP: %.2f (Prob: %.3f)", lot, bid, sl, tp, prob_short);
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Positions with APHE Trailing & Stagnation Ratchet  |
//+------------------------------------------------------------------+
void ManageActivePosition()
{
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) return;

   g_entryBar++;
   long pos_type = PositionGetInteger(POSITION_TYPE);
   double cur_sl = PositionGetDouble(POSITION_SL);
   double cur_tp = PositionGetDouble(POSITION_TP);
   double cur_price = (pos_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double high_1 = iHigh(_Symbol, PERIOD_M1, 1);
   double low_1  = iLow(_Symbol, PERIOD_M1, 1);
   double atr_val = GetATR(1);

   // Max holding period = 180 bars
   if(g_entryBar >= 180)
   {
      g_trade.PositionClose(_Symbol);
      Print("[EXP-42] Closed position due to Max Holding Period (180 bars).");
      return;
   }

   if(pos_type == POSITION_TYPE_BUY)
   {
      double full_range = MathMax(g_targetTP - g_entryPrice, 0.01);
      double cur_excursion = (high_1 - g_entryPrice) / full_range;
      g_maxExcursion = MathMax(g_maxExcursion, cur_excursion);

      double new_sl = cur_sl;

      // APHE 3-Tier Ladder
      if(InpUseAPHE)
      {
         if(g_trailTier == 0 && g_maxExcursion >= InpTier1_Excursion)
         {
            new_sl = MathMax(new_sl, g_entryPrice + 0.10 * atr_val);
            g_trailTier = 1;
         }
         else if(g_trailTier == 1 && g_maxExcursion >= InpTier2_Excursion)
         {
            new_sl = MathMax(new_sl, g_entryPrice + 0.35 * full_range);
            g_trailTier = 2;
         }
         else if(g_trailTier == 2 && g_maxExcursion >= InpTier3_Excursion)
         {
            new_sl = MathMax(new_sl, g_entryPrice + 0.65 * full_range);
            g_trailTier = 3;
         }
      }

      // Accelerated Stagnation Ratchet
      if(InpUseStagnationRatchet && g_entryBar >= InpStagnationBar && g_maxExcursion < InpStagnationProgress)
      {
         new_sl = MathMax(new_sl, g_entryPrice - 0.75 * atr_val);
      }

      new_sl = NormalizeDouble(new_sl, _Digits);
      if(new_sl > cur_sl + _Point)
      {
         g_trade.PositionModify(_Symbol, new_sl, cur_tp);
         PrintFormat("[EXP-42] Ratchet BUY SL to %.2f (Tier: %d, Excursion: %.1f%%)", new_sl, g_trailTier, g_maxExcursion * 100.0);
      }
   }
   else if(pos_type == POSITION_TYPE_SELL)
   {
      double full_range = MathMax(g_entryPrice - g_targetTP, 0.01);
      double cur_excursion = (g_entryPrice - low_1) / full_range;
      g_maxExcursion = MathMax(g_maxExcursion, cur_excursion);

      double new_sl = cur_sl;

      // APHE 3-Tier Ladder
      if(InpUseAPHE)
      {
         if(g_trailTier == 0 && g_maxExcursion >= InpTier1_Excursion)
         {
            new_sl = MathMin(new_sl, g_entryPrice - 0.10 * atr_val);
            g_trailTier = 1;
         }
         else if(g_trailTier == 1 && g_maxExcursion >= InpTier2_Excursion)
         {
            new_sl = MathMin(new_sl, g_entryPrice - 0.35 * full_range);
            g_trailTier = 2;
         }
         else if(g_trailTier == 2 && g_maxExcursion >= InpTier3_Excursion)
         {
            new_sl = MathMin(new_sl, g_entryPrice - 0.65 * full_range);
            g_trailTier = 3;
         }
      }

      // Accelerated Stagnation Ratchet
      if(InpUseStagnationRatchet && g_entryBar >= InpStagnationBar && g_maxExcursion < InpStagnationProgress)
      {
         new_sl = MathMin(new_sl, g_entryPrice + 0.75 * atr_val);
      }

      new_sl = NormalizeDouble(new_sl, _Digits);
      if(cur_sl == 0.0 || new_sl < cur_sl - _Point)
      {
         g_trade.PositionModify(_Symbol, new_sl, cur_tp);
         PrintFormat("[EXP-42] Ratchet SELL SL to %.2f (Tier: %d, Excursion: %.1f%%)", new_sl, g_trailTier, g_maxExcursion * 100.0);
      }
   }
}

//+------------------------------------------------------------------+
//| Compute Rolling ATR Percentile Rank                              |
//+------------------------------------------------------------------+
double ComputeATRRank(int lookback)
{
   double atr_cur = GetATR(1);
   if(atr_cur <= 0.0) return 0.50;

   int count_lower = 0;
   for(int i = 1; i <= lookback; i++)
   {
      double val = GetATR(i);
      if(val < atr_cur) count_lower++;
   }
   return (double)count_lower / (double)lookback;
}

//+------------------------------------------------------------------+
//| Helper: Get ATR Value                                            |
//+------------------------------------------------------------------+
double GetATR(int bar)
{
   double buf[1];
   if(CopyBuffer(g_atrHandle, 0, bar, 1, buf) <= 0) return 0.0;
   return buf[0];
}

//+------------------------------------------------------------------+
//| Build State Vector for ONNX (31 market features + eur_ret15)     |
//+------------------------------------------------------------------+
bool BuildStateVector(float &vec[], float eur_ret15)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 65, rates) < 65) return false;

   double c0 = rates[0].close;
   double atr = GetATR(1);
   if(atr <= 0.0) atr = 0.50;

   // Returns
   vec[0] = (float)((c0 - rates[1].close) / rates[1].close);
   vec[1] = (float)((c0 - rates[2].close) / rates[2].close);
   vec[2] = (float)((c0 - rates[5].close) / rates[5].close);
   vec[3] = (float)((c0 - rates[15].close) / rates[15].close);
   vec[4] = (float)((c0 - rates[30].close) / rates[30].close);
   vec[5] = (float)((c0 - rates[60].close) / rates[60].close);

   // Volatility
   vec[6] = (float)(atr / c0);
   vec[7] = (float)(atr / MathMax(0.1, GetATR(60)));
   vec[8] = (float)MathAbs(vec[4]);

   // Candlestick Geometry
   double rng = MathMax(rates[0].high - rates[0].low, 0.01);
   vec[9]  = (float)((c0 - rates[5].close) / atr);
   vec[10] = (float)((c0 - rates[15].close) / atr);
   vec[11] = (float)((c0 - rates[60].close) / atr);
   vec[12] = (float)(MathAbs(rates[0].close - rates[0].open) / rng);
   vec[13] = (float)(rng / atr);
   vec[14] = (float)((rates[0].high - MathMax(rates[0].close, rates[0].open)) / rng);
   vec[15] = (float)((MathMin(rates[0].close, rates[0].open) - rates[0].low) / rng);
   vec[16] = (float)((rates[0].close - rates[0].low) / rng);

   // Oscillators & Distances
   vec[17] = (float)((c0 - rates[19].close) / atr);
   vec[18] = (float)((c0 - rates[59].close) / atr);
   vec[19] = (float)0.50; // Percent rank placeholder

   // EMAs
   double ema20[1], ema60[1], ema240[1];
   CopyBuffer(g_ema20h, 0, 1, 1, ema20);
   CopyBuffer(g_ema60h, 0, 1, 1, ema60);
   CopyBuffer(g_ema240h, 0, 1, 1, ema240);

   vec[20] = (float)((c0 - ema20[0]) / atr);
   vec[21] = (float)((c0 - ema60[0]) / atr);
   vec[22] = (float)((c0 - ema240[0]) / atr);
   vec[23] = (float)0.50; // RSI norm
   vec[24] = (float)((ema60[0] - ema240[0]) / atr);

   // Volume ratios
   vec[25] = (float)1.0;
   vec[26] = (float)1.0;

   // Time cyclical
   MqlDateTime dt;
   TimeCurrent(dt);
   double h_rad = (dt.hour + dt.min / 60.0) * 2.0 * M_PI / 24.0;
   double d_rad = dt.day_of_week * 2.0 * M_PI / 7.0;
   vec[27] = (float)MathSin(h_rad);
   vec[28] = (float)MathCos(h_rad);
   vec[29] = (float)MathSin(d_rad);
   vec[30] = (float)MathCos(d_rad);

   // Feature 31: EURUSD 15m return (Cross-Asset Macro Anchor)
   vec[31] = eur_ret15;

   return true;
}

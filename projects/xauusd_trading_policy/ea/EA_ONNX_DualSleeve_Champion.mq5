//+------------------------------------------------------------------+
//|  EA_ONNX_DualSleeve_Champion.mq5                                 |
//|  XAUUSD M1 — ONNX Policy EA (xauusd_dual_sleeve_champion.onnx)  |
//|  Research: Autonomous Quant ML Research EXP-01 to EXP-27        |
//|                                                                  |
//|  Model: xauusd_dual_sleeve_champion.onnx                        |
//|  Input : float32[batch=1, 40]  (31 market + 9 position features)|
//|  Output: action_probs[1,7]  position_size[1,1]  order_params[1,2]|
//|                                                                  |
//|  Action mapping:                                                 |
//|    0=HOLD  1=OPEN_LONG  2=OPEN_SHORT                            |
//|    3=ADD   4=REDUCE     5=CLOSE     6=REVERSE                   |
//|                                                                  |
//|  Session / Safety filters (same as EXP-27 research):            |
//|    - Friday Shield: no new entries after 17:00 UTC              |
//|    - Liquid hours: 07:00–19:00 UTC only                         |
//|    - Daily loss limit halt                                      |
//|                                                                  |
//|  DEPLOYMENT:                                                     |
//|    Copy xauusd_dual_sleeve_champion.onnx  →  MQL5/Files/        |
//|    Copy xauusd_dual_sleeve_champion.onnx.data → MQL5/Files/     |
//|    Compile this EA in MetaEditor, attach to XAUUSD M1 chart     |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-27 ONNX"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== ONNX Model ==="
input string   InpOnnxFile         = "xauusd_dual_sleeve_champion.onnx";

input group "=== Trade Management ==="
input double   InpBaseLots         = 0.10;    // Base lot size (scaled by model position_size)
input double   InpMaxLots          = 0.28;    // Maximum allowed lots
input double   InpMinActionProb    = 0.45;    // Minimum probability to act (vs HOLD)
input double   InpBaseATRSL        = 2.0;     // Fallback SL multiplier (ATR) if model gives 0
input double   InpBaseATRTP        = 3.5;     // Fallback TP multiplier (ATR) if model gives 0

input group "=== Session Filter (UTC) ==="
input int      InpLiquidStart      = 7;       // Liquid session start hour (UTC)
input int      InpLiquidEnd        = 19;      // Liquid session end hour (UTC)
input bool     InpFridayShield     = true;    // Block new entries after 17:00 UTC Friday

input group "=== Risk Control ==="
input double   InpMaxDailyLoss     = 300.0;   // Max daily loss USD before halt
input int      InpMagicNumber      = 271000;
input string   InpComment          = "ONNX_DualSleeve";

//--- Feature normalization constants (from policy_metadata.json, features 0-30)
//    Applied as: norm = (raw - mean) / std
//    Position features (31-39) computed fresh each bar
static const double FEAT_MEANS[31] = {
   2.902e-07,  8.427e-07,  1.526e-06,  4.551e-06,  9.264e-06,  1.854e-05,  // ret_1..ret_60
   2.931e-04,  1.003,      2.179e-04,                                        // norm_atr14, atr_ratio, realized_vol_30
   0.012667,   0.058694,   0.213138,                                          // move_5_atr, move_15_atr, move_60_atr
   0.000877,   0.995575,   0.230709,   0.238502,   0.505627,                 // body, range, upper_wick, lower_wick, close_loc
   0.015220,   0.034802,   0.512495,                                          // z_score_20, z_score_100, pct_rank_60
   0.033861,   0.089002,   0.304067,   0.503124,   2.909e-05,                // dist_ema20,50,200_atr, rsi14_norm, macro_ema_ratio
   1.009265,   1.026436,                                                       // vol_ratio_20, vol_ratio_100
   0.024909,  -0.043878,   0.026115,  -0.006075                              // hour_sin, hour_cos, dow_sin, dow_cos
};
static const double FEAT_STDS[31] = {
   2.655e-04,  4.574e-04,  5.857e-04,  1.004e-03,  1.414e-03,  1.992e-03,  // ret_1..ret_60
   2.101e-04,  0.227339,   1.567e-04,                                        // norm_atr14, atr_ratio, realized_vol_30
   1.632858,   2.704607,   5.552315,                                          // move_5_atr..move_60_atr
   0.751291,   0.503462,   0.231517,   0.234143,   0.346155,                 // body..close_loc
   1.286906,   1.392210,   0.326089,                                          // z_score_20, z_score_100, pct_rank_60
   1.495368,   2.365639,   5.057927,   0.163588,   0.001807,                 // dist_ema20,50,200_atr, rsi14_norm, macro_ema_ratio
   0.422354,   0.567071,                                                       // vol_ratio_20, vol_ratio_100
   0.715079,   0.696383,   0.707043,   0.706934                              // hour_sin, hour_cos, dow_sin, dow_cos
};

//--- Globals
long     g_onnxHandle    = INVALID_HANDLE;
CTrade   g_trade;

double   g_dailyLoss     = 0.0;
datetime g_lastDayCheck  = 0;

// Position tracking (for position features)
double   g_entryPrice    = 0.0;
double   g_entrySL       = 0.0;
double   g_entryTP       = 0.0;
double   g_posDir        = 0.0;   // +1=long, -1=short, 0=flat
double   g_posSizeFrac   = 0.0;   // lot / MaxLots
int      g_barsInPos     = 0;
int      g_barsSinceAct  = 0;
double   g_maxAdverseDraw= 0.0;   // MAE in ATR

// Indicator handles
int      g_atr14h        = INVALID_HANDLE;
int      g_atr60h        = INVALID_HANDLE;
int      g_ema20h        = INVALID_HANDLE;
int      g_ema50h        = INVALID_HANDLE;
int      g_ema200h       = INVALID_HANDLE;
int      g_rsi14h        = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
{
   // Load ONNX model
   g_onnxHandle = OnnxCreate(InpOnnxFile, ONNX_DEFAULT);
   if(g_onnxHandle == INVALID_HANDLE)
   {
      Print("EA_ONNX: Failed to load ONNX model '", InpOnnxFile, "'. ",
            "Place the .onnx and .onnx.data files in MQL5/Files/");
      return(INIT_FAILED);
   }

   // Set input shape [1, 40]
   ulong inputShape[] = {1, 40};
   if(!OnnxSetInputShape(g_onnxHandle, 0, inputShape))
   {
      Print("EA_ONNX: Failed to set input shape");
      OnnxRelease(g_onnxHandle);
      return(INIT_FAILED);
   }

   // Set output shapes
   ulong outShape7[]  = {1, 7};
   ulong outShape1[]  = {1, 1};
   ulong outShape2[]  = {1, 2};
   OnnxSetOutputShape(g_onnxHandle, 0, outShape7);
   OnnxSetOutputShape(g_onnxHandle, 1, outShape1);
   OnnxSetOutputShape(g_onnxHandle, 2, outShape2);

   // Indicators
   g_atr14h  = iATR(Symbol(), PERIOD_M1, 14);
   g_atr60h  = iATR(Symbol(), PERIOD_M1, 60);
   g_ema20h  = iMA(Symbol(),  PERIOD_M1, 20,  0, MODE_EMA, PRICE_CLOSE);
   g_ema50h  = iMA(Symbol(),  PERIOD_M1, 50,  0, MODE_EMA, PRICE_CLOSE);
   g_ema200h = iMA(Symbol(),  PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_rsi14h  = iRSI(Symbol(), PERIOD_M1, 14, PRICE_CLOSE);

   if(g_atr14h==INVALID_HANDLE || g_atr60h==INVALID_HANDLE ||
      g_ema20h==INVALID_HANDLE  || g_ema50h==INVALID_HANDLE ||
      g_ema200h==INVALID_HANDLE || g_rsi14h==INVALID_HANDLE)
   {
      Print("EA_ONNX: Indicator handle creation failed");
      OnnxRelease(g_onnxHandle);
      return(INIT_FAILED);
   }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(20);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   Print("EA_ONNX DualSleeve Champion initialized | Model: ", InpOnnxFile,
         " | Magic: ", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_onnxHandle != INVALID_HANDLE) OnnxRelease(g_onnxHandle);
   IndicatorRelease(g_atr14h);
   IndicatorRelease(g_atr60h);
   IndicatorRelease(g_ema20h);
   IndicatorRelease(g_ema50h);
   IndicatorRelease(g_ema200h);
   IndicatorRelease(g_rsi14h);
}

//+------------------------------------------------------------------+
void OnTick()
{
   // New bar gate
   static datetime s_lastBar = 0;
   datetime curBar = iTime(Symbol(), PERIOD_M1, 0);
   if(curBar == s_lastBar) return;
   s_lastBar = curBar;

   g_barsSinceAct++;

   // Daily loss check
   ResetDailyLossIfNewDay();
   if(g_dailyLoss >= InpMaxDailyLoss)
   {
      Comment("EA_ONNX: Daily loss halt ($", InpMaxDailyLoss, " reached)");
      return;
   }

   // Session filter
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int h = dt.hour, m = dt.min, dow = dt.day_of_week;

   bool inLiquid = (h >= InpLiquidStart && h < InpLiquidEnd);
   bool fridayBlock = (InpFridayShield && dow == 5 && h >= 17);

   // --- Build feature vector ---
   float features[40];
   if(!BuildFeatures(features, dt))
      return;

   // --- Run ONNX inference ---
   float actionProbs[7], posSize[1], orderParams[2];
   if(!RunModel(features, actionProbs, posSize, orderParams))
      return;

   // Pick action with highest probability
   int bestAction = 0;
   float bestProb = actionProbs[0];
   for(int i = 1; i < 7; i++)
      if(actionProbs[i] > bestProb) { bestProb = actionProbs[i]; bestAction = i; }

   // Current position state
   bool hasPos  = HasOpenPosition();
   double atr[1];
   if(CopyBuffer(g_atr14h, 0, 0, 1, atr) <= 0) return;
   double atrVal = atr[0];
   if(atrVal <= 0) return;

   // Compute SL/TP from model output (order_params = [sl_mult, tp_mult])
   double sl_mult = (orderParams[0] > 0.5) ? (double)orderParams[0] : InpBaseATRSL;
   double tp_mult = (orderParams[1] > 0.5) ? (double)orderParams[1] : InpBaseATRTP;
   sl_mult = MathMax(1.2, MathMin(4.0, sl_mult));
   tp_mult = MathMax(1.5, MathMin(9.0, tp_mult));

   // Lot size from model (position_size output in [0,1] scaled to [BaseLots, MaxLots])
   double lots = InpBaseLots + (InpMaxLots - InpBaseLots) * (double)posSize[0];
   lots = MathMax(InpBaseLots, MathMin(InpMaxLots, NormalizeLots(lots)));

   // Minimum confidence gate
   if(bestProb < InpMinActionProb && bestAction != 3 && bestAction != 4 && bestAction != 5 && bestAction != 6)
      bestAction = 0; // force HOLD if not confident enough

   // === Execute action ===
   switch(bestAction)
   {
      case 0: // HOLD
         break;

      case 1: // OPEN_LONG
         if(!hasPos && !fridayBlock && inLiquid)
         {
            double entry = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
            double sl    = entry - sl_mult * atrVal;
            double tp    = entry + tp_mult * atrVal;
            if(g_trade.Buy(lots, Symbol(), entry, sl, tp,
                           StringFormat("%s_LONG", InpComment)))
            {
               g_posDir  = 1.0;
               g_posSizeFrac = lots / InpMaxLots;
               g_entryPrice  = entry;
               g_entrySL     = sl;
               g_entryTP     = tp;
               g_barsInPos   = 0;
               g_barsSinceAct= 0;
               g_maxAdverseDraw = 0.0;
               Print("ONNX → OPEN_LONG ", lots, " @ ", entry,
                     " | P(action)=", DoubleToString(bestProb,3),
                     " | SL=", DoubleToString(sl_mult,2), "x ATR",
                     " TP=", DoubleToString(tp_mult,2), "x ATR");
            }
         }
         break;

      case 2: // OPEN_SHORT
         if(!hasPos && !fridayBlock && inLiquid)
         {
            double entry = SymbolInfoDouble(Symbol(), SYMBOL_BID);
            double sl    = entry + sl_mult * atrVal;
            double tp    = entry - tp_mult * atrVal;
            if(g_trade.Sell(lots, Symbol(), entry, sl, tp,
                            StringFormat("%s_SHORT", InpComment)))
            {
               g_posDir  = -1.0;
               g_posSizeFrac = lots / InpMaxLots;
               g_entryPrice  = entry;
               g_entrySL     = sl;
               g_entryTP     = tp;
               g_barsInPos   = 0;
               g_barsSinceAct= 0;
               g_maxAdverseDraw = 0.0;
               Print("ONNX → OPEN_SHORT ", lots, " @ ", entry,
                     " | P(action)=", DoubleToString(bestProb,3),
                     " | SL=", DoubleToString(sl_mult,2), "x ATR",
                     " TP=", DoubleToString(tp_mult,2), "x ATR");
            }
         }
         break;

      case 5: // CLOSE
      case 6: // REVERSE (close first, reopen handled next bar)
         if(hasPos)
         {
            CloseAllPositions();
            ResetPositionState();
            Print("ONNX → CLOSE all positions | P(action)=", DoubleToString(bestProb,3));
         }
         break;

      case 3: // ADD — scale into existing
      case 4: // REDUCE — partial close (simplified: full close if prob high)
         // Simplified: ignore ADD/REDUCE, let SL/TP manage exits
         break;
   }

   // Track bars in position
   if(HasOpenPosition()) g_barsInPos++;

   // Update chart display
   UpdateDisplay(bestAction, bestProb, actionProbs, atrVal, sl_mult, tp_mult);
}

//+------------------------------------------------------------------+
bool BuildFeatures(float &feat[], const MqlDateTime &dt)
{
   // Gather raw market data
   double atr14[1], atr60[1], ema20[1], ema50[1], ema200[1], rsi14[1];
   if(CopyBuffer(g_atr14h,  0, 0, 1, atr14)  <= 0) return false;
   if(CopyBuffer(g_atr60h,  0, 0, 1, atr60)  <= 0) return false;
   if(CopyBuffer(g_ema20h,  0, 0, 1, ema20)  <= 0) return false;
   if(CopyBuffer(g_ema50h,  0, 0, 1, ema50)  <= 0) return false;
   if(CopyBuffer(g_ema200h, 0, 0, 1, ema200) <= 0) return false;
   if(CopyBuffer(g_rsi14h,  0, 0, 1, rsi14)  <= 0) return false;

   // Price history for returns
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(Symbol(), PERIOD_M1, 0, 65, closes) < 65) return false;

   double opens[], highs[], lows[];
   ArraySetAsSeries(opens, true);
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows,  true);
   if(CopyOpen(Symbol(),  PERIOD_M1, 0, 5, opens) < 5) return false;
   if(CopyHigh(Symbol(),  PERIOD_M1, 0, 5, highs) < 5) return false;
   if(CopyLow(Symbol(),   PERIOD_M1, 0, 5, lows)  < 5) return false;

   // Volume for vol_ratio
   long vols[];
   ArraySetAsSeries(vols, true);
   if(CopyTickVolume(Symbol(), PERIOD_M1, 0, 105, vols) < 105) return false;

   double close = closes[0];
   double open  = opens[0];
   double high  = highs[0];
   double low   = lows[0];
   double atr   = atr14[0];
   if(atr <= 0) return false;

   // === Compute 31 market features ===
   double raw[31];

   // 0-5: returns (ret_1 to ret_60)
   raw[0] = (closes[0] - closes[1])  / (closes[1] > 0 ? closes[1] : 1.0);
   raw[1] = (closes[0] - closes[3])  / (closes[3] > 0 ? closes[3] : 1.0);
   raw[2] = (closes[0] - closes[5])  / (closes[5] > 0 ? closes[5] : 1.0);
   raw[3] = (closes[0] - closes[15]) / (closes[15]> 0 ? closes[15]: 1.0);
   raw[4] = (closes[0] - closes[30]) / (closes[30]> 0 ? closes[30]: 1.0);
   raw[5] = (closes[0] - closes[60]) / (closes[60]> 0 ? closes[60]: 1.0);

   // 6: norm_atr14 = ATR14 / close
   raw[6] = atr / (close > 0 ? close : 1.0);

   // 7: atr_ratio = ATR14 / ATR60
   raw[7] = (atr60[0] > 0) ? atr / atr60[0] : 1.0;

   // 8: realized_vol_30 = std of 30 bar returns
   {
      double mu = 0.0;
      for(int i = 1; i <= 30; i++) mu += (closes[i-1] - closes[i]) / closes[i];
      mu /= 30.0;
      double vr = 0.0;
      for(int i = 1; i <= 30; i++)
      {
         double r = (closes[i-1] - closes[i]) / closes[i] - mu;
         vr += r * r;
      }
      raw[8] = MathSqrt(vr / 30.0);
   }

   // 9-11: move_N_atr = (close - close[N]) / ATR
   raw[9]  = (closes[0] - closes[5])  / atr;
   raw[10] = (closes[0] - closes[15]) / atr;
   raw[11] = (closes[0] - closes[60]) / atr;

   // 12-16: candle structure
   double barRange = high - low;
   double body     = MathAbs(close - open);
   raw[12] = (barRange > 0) ? body / barRange : 0.0;           // body_atr proxy (normalized)
   raw[13] = (atr > 0) ? barRange / atr : 1.0;                 // range_atr
   raw[14] = (barRange > 0) ? (high - MathMax(close,open)) / barRange : 0.0; // upper_wick_ratio
   raw[15] = (barRange > 0) ? (MathMin(close,open) - low) / barRange : 0.0;  // lower_wick_ratio
   raw[16] = (barRange > 0) ? (close - low) / barRange : 0.5;                // close_loc_in_bar

   // 17-18: z-score
   {
      double mu20 = 0.0, mu100 = 0.0;
      for(int i = 0; i < 20;  i++) mu20  += closes[i];
      for(int i = 0; i < 100; i++) mu100 += closes[i];
      mu20 /= 20.0; mu100 /= 100.0;
      double sd20 = 0.0, sd100 = 0.0;
      for(int i = 0; i < 20;  i++) sd20  += (closes[i]-mu20)*(closes[i]-mu20);
      for(int i = 0; i < 100; i++) sd100 += (closes[i]-mu100)*(closes[i]-mu100);
      sd20  = MathSqrt(sd20  / 20.0);
      sd100 = MathSqrt(sd100 / 100.0);
      raw[17] = (sd20  > 0) ? (close - mu20)  / sd20  : 0.0;  // z_score_20
      raw[18] = (sd100 > 0) ? (close - mu100) / sd100 : 0.0;  // z_score_100
   }

   // 19: pct_rank_60
   {
      int cnt = 0;
      for(int i = 1; i <= 60; i++) if(closes[i] < close) cnt++;
      raw[19] = cnt / 60.0;
   }

   // 20-22: dist_ema_atr
   raw[20] = (close - ema20[0])  / atr;  // dist_ema20_atr
   raw[21] = (close - ema50[0])  / atr;  // dist_ema50_atr
   raw[22] = (close - ema200[0]) / atr;  // dist_ema200_atr

   // 23: rsi14_norm  (RSI in [0,1])
   raw[23] = rsi14[0] / 100.0;

   // 24: macro_ema_ratio = EMA50 / EMA200
   raw[24] = (ema200[0] > 0) ? ema50[0] / ema200[0] : 1.0;

   // 25-26: volume ratios
   {
      double vol0 = (double)vols[0];
      double vma20 = 0.0, vma100 = 0.0;
      for(int i = 1; i <= 20;  i++) vma20  += (double)vols[i];
      for(int i = 1; i <= 100; i++) vma100 += (double)vols[i];
      vma20  /= 20.0;
      vma100 /= 100.0;
      raw[25] = (vma20  > 0) ? vol0 / vma20  : 1.0;
      raw[26] = (vma100 > 0) ? vol0 / vma100 : 1.0;
   }

   // 27-30: temporal cyclical encoding
   double hourAngle = 2.0 * M_PI * dt.hour / 24.0;
   double dowAngle  = 2.0 * M_PI * dt.day_of_week / 7.0;
   raw[27] = MathSin(hourAngle);  // hour_sin
   raw[28] = MathCos(hourAngle);  // hour_cos
   raw[29] = MathSin(dowAngle);   // dow_sin
   raw[30] = MathCos(dowAngle);   // dow_cos

   // Normalize market features
   for(int i = 0; i < 31; i++)
   {
      double s = (FEAT_STDS[i] > 1e-10) ? FEAT_STDS[i] : 1.0;
      feat[i] = (float)((raw[i] - FEAT_MEANS[i]) / s);
      feat[i] = (float)MathMax(-5.0, MathMin(5.0, feat[i])); // clip
   }

   // === Position features (31-39) — NOT normalized, raw values ===
   // pos_dir
   feat[31] = (float)g_posDir;

   // pos_size_frac
   feat[32] = (float)g_posSizeFrac;

   // entry_dist_atr
   double entryDist = (g_posDir != 0 && atr > 0) ?
                      g_posDir * (close - g_entryPrice) / atr : 0.0;
   feat[33] = (float)entryDist;

   // unrealized_pnl_atr (same as entry_dist in this simplified model)
   feat[34] = (float)entryDist;

   // time_in_pos_norm (normalized by 60 bars max)
   feat[35] = (float)MathMin(1.0, g_barsInPos / 60.0);

   // dist_to_sl_atr
   double distSL = (g_posDir > 0 && atr > 0) ? (close - g_entrySL) / atr :
                   (g_posDir < 0 && atr > 0) ? (g_entrySL - close) / atr : 0.0;
   feat[36] = (float)MathMax(0.0, distSL);

   // dist_to_tp_atr
   double distTP = (g_posDir > 0 && atr > 0) ? (g_entryTP - close) / atr :
                   (g_posDir < 0 && atr > 0) ? (close - g_entryTP) / atr : 0.0;
   feat[37] = (float)MathMax(0.0, distTP);

   // max_drawdown_atr (MAE so far)
   if(g_posDir > 0)  g_maxAdverseDraw = MathMax(g_maxAdverseDraw, (g_entryPrice - close) / atr);
   if(g_posDir < 0)  g_maxAdverseDraw = MathMax(g_maxAdverseDraw, (close - g_entryPrice) / atr);
   feat[38] = (float)MathMax(0.0, g_maxAdverseDraw);

   // bars_since_action_norm
   feat[39] = (float)MathMin(1.0, g_barsSinceAct / 60.0);

   return true;
}

//+------------------------------------------------------------------+
bool RunModel(const float &features[], float &actionProbs[], float &posSize[], float &orderParams[])
{
   // Prepare typed arrays for OnnxRun
   float inp[];  ArrayResize(inp, 40);
   float ap[];   ArrayResize(ap,  7);
   float ps[];   ArrayResize(ps,  1);
   float op[];   ArrayResize(op,  2);

   ArrayCopy(inp, features);

   if(!OnnxRun(g_onnxHandle,
               ONNX_NO_CONVERSION,
               inp, ap, ps, op))
   {
      Print("EA_ONNX: OnnxRun failed");
      return false;
   }

   ArrayCopy(actionProbs, ap);
   ArrayCopy(posSize,     ps);
   ArrayCopy(orderParams, op);
   return true;
}

//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 &&
         PositionGetString(POSITION_SYMBOL)  == Symbol() &&
         PositionGetInteger(POSITION_MAGIC)  == InpMagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 &&
         PositionGetString(POSITION_SYMBOL)  == Symbol() &&
         PositionGetInteger(POSITION_MAGIC)  == InpMagicNumber)
         g_trade.PositionClose(ticket);
   }
}

//+------------------------------------------------------------------+
void ResetPositionState()
{
   g_posDir         = 0.0;
   g_posSizeFrac    = 0.0;
   g_entryPrice     = 0.0;
   g_entrySL        = 0.0;
   g_entryTP        = 0.0;
   g_barsInPos      = 0;
   g_maxAdverseDraw = 0.0;
}

//+------------------------------------------------------------------+
double NormalizeLots(double lots)
{
   double step = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;
   return MathFloor(lots / step) * step;
}

//+------------------------------------------------------------------+
void ResetDailyLossIfNewDay()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d 00:00",
                                  dt.year, dt.mon, dt.day));
   if(today != g_lastDayCheck)
   {
      g_dailyLoss    = 0.0;
      g_lastDayCheck = today;
   }
}

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &req,
                        const MqlTradeResult      &res)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      ulong tk = trans.deal;
      if(HistoryDealSelect(tk))
      {
         if(HistoryDealGetInteger(tk, DEAL_MAGIC) == InpMagicNumber)
         {
            double profit = HistoryDealGetDouble(tk, DEAL_PROFIT);
            long   entry  = HistoryDealGetInteger(tk, DEAL_ENTRY);
            if((entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT) && profit < 0)
               g_dailyLoss += MathAbs(profit);

            // Reset position state when closed
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
               if(!HasOpenPosition()) ResetPositionState();
         }
      }
   }
}

//+------------------------------------------------------------------+
void UpdateDisplay(int action, double prob, const float &probs[],
                   double atr, double sl_m, double tp_m)
{
   static string actionNames[] = {"HOLD","OPEN_LONG","OPEN_SHORT","ADD","REDUCE","CLOSE","REVERSE"};
   string posStr = (g_posDir > 0) ? "LONG" : (g_posDir < 0) ? "SHORT" : "FLAT";

   Comment(
      "=== EA_ONNX DualSleeve Champion ===\n",
      "Model: ", InpOnnxFile, "\n",
      "Position: ", posStr,
      (g_posDir != 0 ? StringFormat(" | %d bars | MAE %.2f ATR", g_barsInPos, g_maxAdverseDraw) : ""), "\n",
      "Action: [", action, "] ", actionNames[action],
      " P=", DoubleToString(prob*100,1), "%\n",
      "  HOLD=",       DoubleToString(probs[0]*100,1), "%",
      " LONG=",        DoubleToString(probs[1]*100,1), "%",
      " SHORT=",       DoubleToString(probs[2]*100,1), "%",
      " CLOSE=",       DoubleToString(probs[5]*100,1), "%\n",
      "SL: ", DoubleToString(sl_m,2), "x ATR  TP: ", DoubleToString(tp_m,2), "x ATR\n",
      "ATR: ", DoubleToString(atr,2), " | Daily Loss: $", DoubleToString(g_dailyLoss,2)
   );
}
//+------------------------------------------------------------------+

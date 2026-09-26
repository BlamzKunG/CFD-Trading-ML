//+------------------------------------------------------------------+
//|                                        XAUUSD_Policy_Agent.mqh   |
//|                    Copyright 2026, BlamzKunG (GitHub: BlamzKunG) |
//|               https://github.com/BlamzKunG/CFD-Trading-ML |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG (GitHub: BlamzKunG)"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
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

//+------------------------------------------------------------------+
//| Class CXAUUSDPolicyAgent                                         |
//+------------------------------------------------------------------+
class CXAUUSDPolicyAgent
{
private:
   long             m_onnx_handle;
   string           m_model_file;
   bool             m_is_ready;

   // Indicator Handles
   int              m_h_atr14;
   int              m_h_atr50;
   int              m_h_ema20;
   int              m_h_ema50;
   int              m_h_ema200;
   int              m_h_rsi14;

   // Position tracking stats
   datetime         m_pos_entry_time;
   datetime         m_last_action_time;
   double           m_max_adv_atr;
   double           m_max_fav_atr;

public:
   CXAUUSDPolicyAgent()
   {
      m_onnx_handle      = INVALID_HANDLE;
      m_is_ready         = false;
      m_pos_entry_time   = 0;
      m_last_action_time = 0;
      m_max_adv_atr      = 0.0;
      m_max_fav_atr      = 0.0;
      m_h_atr14          = INVALID_HANDLE;
      m_h_atr50          = INVALID_HANDLE;
      m_h_ema20          = INVALID_HANDLE;
      m_h_ema50          = INVALID_HANDLE;
      m_h_ema200         = INVALID_HANDLE;
      m_h_rsi14          = INVALID_HANDLE;
   }

   ~CXAUUSDPolicyAgent()
   {
      Release();
   }

   bool Init(const string model_file)
   {
      m_model_file = model_file;

      // 1. Load ONNX Model
      m_onnx_handle = OnnxCreate(m_model_file, ONNX_DEFAULT);
      if(m_onnx_handle == INVALID_HANDLE)
      {
         PrintFormat("[Policy Agent] Warning: Could not load ONNX model %s (Error %d). Heuristic policy will be used until ONNX model is compiled.", m_model_file, GetLastError());
      }
      else
      {
         PrintFormat("[Policy Agent] ONNX Model %s loaded successfully!", m_model_file);
      }

      // 2. Initialize Indicator Handles
      m_h_atr14  = iATR(_Symbol, PERIOD_M1, 14);
      m_h_atr50  = iATR(_Symbol, PERIOD_M1, 50);
      m_h_ema20  = iMA(_Symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema50  = iMA(_Symbol, PERIOD_M1, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema200 = iMA(_Symbol, PERIOD_M1, 200, 0, MODE_EMA, PRICE_CLOSE);
      m_h_rsi14  = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);

      m_is_ready = true;
      return true;
   }

   void Release()
   {
      if(m_onnx_handle != INVALID_HANDLE)
      {
         OnnxRelease(m_onnx_handle);
         m_onnx_handle = INVALID_HANDLE;
      }
      IndicatorRelease(m_h_atr14);
      IndicatorRelease(m_h_atr50);
      IndicatorRelease(m_h_ema20);
      IndicatorRelease(m_h_ema50);
      IndicatorRelease(m_h_ema200);
      IndicatorRelease(m_h_rsi14);
      m_is_ready = false;
   }

   // Extract 31 Market Features
   bool ComputeMarketFeatures(float &features[], double &out_atr14)
   {
      ArrayResize(features, NUM_MARKET_FEATURES);
      ArrayInitialize(features, 0.0f);

      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      if(CopyRates(_Symbol, PERIOD_M1, 0, 205, rates) < 205) return false;

      double atr14_buf[], atr50_buf[], ema20_buf[], ema50_buf[], ema200_buf[], rsi_buf[];
      ArraySetAsSeries(atr14_buf, true);
      ArraySetAsSeries(atr50_buf, true);
      ArraySetAsSeries(ema20_buf, true);
      ArraySetAsSeries(ema50_buf, true);
      ArraySetAsSeries(ema200_buf, true);
      ArraySetAsSeries(rsi_buf, true);

      if(CopyBuffer(m_h_atr14, 0, 0, 5, atr14_buf) < 1) return false;
      if(CopyBuffer(m_h_atr50, 0, 0, 5, atr50_buf) < 1) return false;
      if(CopyBuffer(m_h_ema20, 0, 0, 5, ema20_buf) < 1) return false;
      if(CopyBuffer(m_h_ema50, 0, 0, 5, ema50_buf) < 1) return false;
      if(CopyBuffer(m_h_ema200, 0, 0, 5, ema200_buf) < 1) return false;
      if(CopyBuffer(m_h_rsi14, 0, 0, 5, rsi_buf) < 1) return false;

      double close0 = rates[0].close;
      double atr14  = MathMax(atr14_buf[0], 0.001);
      double atr50  = MathMax(atr50_buf[0], 0.001);
      out_atr14     = atr14;

      // 1. Multi-Horizon Log Returns
      features[0] = (float)MathLog(close0 / rates[1].close);
      features[1] = (float)MathLog(close0 / rates[3].close);
      features[2] = (float)MathLog(close0 / rates[5].close);
      features[3] = (float)MathLog(close0 / rates[15].close);
      features[4] = (float)MathLog(close0 / rates[30].close);
      features[5] = (float)MathLog(close0 / rates[60].close);

      // 2. Volatility & Normalized Movement
      features[6] = (float)(atr14 / close0);
      features[7] = (float)(atr14 / atr50);

      // Realized vol 30
      double sum_ret = 0.0, sum_sq = 0.0;
      for(int i = 0; i < 30; i++)
      {
         double r = MathLog(rates[i].close / rates[i+1].close);
         sum_ret += r;
         sum_sq += r * r;
      }
      double mean_r = sum_ret / 30.0;
      features[8] = (float)MathSqrt(MathMax(0.0, (sum_sq / 30.0) - (mean_r * mean_r)));

      features[9]  = (float)((close0 - rates[5].close) / atr14);
      features[10] = (float)((close0 - rates[15].close) / atr14);
      features[11] = (float)((close0 - rates[60].close) / atr14);

      // 3. Normalized Candlestick Microstructure
      double bar_rng = MathMax(rates[0].high - rates[0].low, 0.001);
      features[12] = (float)((close0 - rates[0].open) / atr14);
      features[13] = (float)(bar_rng / atr14);
      features[14] = (float)((rates[0].high - MathMax(rates[0].open, close0)) / bar_rng);
      features[15] = (float)((MathMin(rates[0].open, close0) - rates[0].low) / bar_rng);
      features[16] = (float)((close0 - rates[0].low) / bar_rng);

      // 4. Local Price Distribution (Z-Scores & Percentile Rank)
      double sum20 = 0.0, sq20 = 0.0;
      for(int i = 0; i < 20; i++) { sum20 += rates[i].close; sq20 += rates[i].close * rates[i].close; }
      double m20 = sum20 / 20.0;
      double std20 = MathSqrt(MathMax(0.0001, (sq20 / 20.0) - (m20 * m20)));
      features[17] = (float)((close0 - m20) / std20);

      double sum100 = 0.0, sq100 = 0.0;
      for(int i = 0; i < 100; i++) { sum100 += rates[i].close; sq100 += rates[i].close * rates[i].close; }
      double m100 = sum100 / 100.0;
      double std100 = MathSqrt(MathMax(0.0001, (sq100 / 100.0) - (m100 * m100)));
      features[18] = (float)((close0 - m100) / std100);

      double min60 = rates[0].low, max60 = rates[0].high;
      for(int i = 1; i < 60; i++)
      {
         if(rates[i].low < min60)   min60 = rates[i].low;
         if(rates[i].high > max60) max60 = rates[i].high;
      }
      features[19] = (float)((close0 - min60) / MathMax(0.001, max60 - min60));

      // 5. Momentum & Normalized EMA Distances
      features[20] = (float)((close0 - ema20_buf[0]) / atr14);
      features[21] = (float)((close0 - ema50_buf[0]) / atr14);
      features[22] = (float)((close0 - ema200_buf[0]) / atr14);
      features[23] = (float)(rsi_buf[0] / 100.0);

      // 6. Macro EMA Ratio
      features[24] = (float)MathLog(close0 / MathMax(0.01, ema200_buf[0]));

      // 7. Volume Ratios
      double v_sum20 = 0.0, v_sum100 = 0.0;
      for(int i = 0; i < 100; i++)
      {
         if(i < 20) v_sum20 += rates[i].tick_volume;
         v_sum100 += rates[i].tick_volume;
      }
      features[25] = (float)(rates[0].tick_volume / MathMax(1.0, v_sum20 / 20.0));
      features[26] = (float)(rates[0].tick_volume / MathMax(1.0, v_sum100 / 100.0));

      // 8. Cyclic Time Context
      MqlDateTime dt;
      TimeToStruct(rates[0].time, dt);
      double hour_float = dt.hour + dt.min / 60.0;
      double pi2 = 2.0 * M_PI;
      features[27] = (float)MathSin(pi2 * hour_float / 24.0);
      features[28] = (float)MathCos(pi2 * hour_float / 24.0);
      features[29] = (float)MathSin(pi2 * dt.day_of_week / 5.0);
      features[30] = (float)MathCos(pi2 * dt.day_of_week / 5.0);

      return true;
   }

   // Combine Market & Position State and Run Inference
   void EvaluatePolicy(
      const double pos_dir,
      const double pos_lot,
      const double entry_price,
      const double current_sl,
      const double current_tp,
      const double max_risk_lot,
      int &out_action,
      double &out_size_fraction,
      double &out_sl_atr,
      double &out_tp_atr
   )
   {
      float market_feats[];
      double atr14 = 0.0;
      if(!ComputeMarketFeatures(market_feats, atr14))
      {
         out_action = ACTION_HOLD;
         out_size_fraction = 0.5;
         out_sl_atr = 2.0;
         out_tp_atr = 3.0;
         return;
      }

      double close0 = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      
      // Update position tracking
      if(pos_dir == 0.0)
      {
         m_pos_entry_time   = 0;
         m_max_adv_atr      = 0.0;
         m_max_fav_atr      = 0.0;
      }
      else
      {
         if(m_pos_entry_time == 0) m_pos_entry_time = TimeCurrent();
         double cur_adv = 0.0;
         if(pos_dir > 0) cur_adv = MathMax(0.0, (entry_price - close0) / atr14);
         else            cur_adv = MathMax(0.0, (close0 - entry_price) / atr14);
         m_max_adv_atr = MathMax(m_max_adv_atr, cur_adv);
      }

      // Construct Position Features (9)
      float pos_feats[NUM_POSITION_FEATURES];
      pos_feats[0] = (float)pos_dir;
      pos_feats[1] = (float)(pos_dir != 0.0 ? MathMin(1.0, pos_lot / MathMax(0.01, max_risk_lot)) : 0.0);
      pos_feats[2] = (float)(pos_dir != 0.0 ? (close0 - entry_price) / atr14 : 0.0);
      pos_feats[3] = (float)(pos_dir != 0.0 ? pos_dir * (close0 - entry_price) / atr14 : 0.0);
      
      int bars_in_pos = (m_pos_entry_time > 0) ? (int)((TimeCurrent() - m_pos_entry_time) / 60) : 0;
      pos_feats[4] = (float)MathMin(1.0, bars_in_pos / 120.0);
      
      pos_feats[5] = (float)(current_sl > 0 ? MathAbs(close0 - current_sl) / atr14 : 0.0);
      pos_feats[6] = (float)(current_tp > 0 ? MathAbs(close0 - current_tp) / atr14 : 0.0);
      pos_feats[7] = (float)m_max_adv_atr;
      
      int bars_since_act = (m_last_action_time > 0) ? (int)((TimeCurrent() - m_last_action_time) / 60) : 60;
      pos_feats[8] = (float)MathMin(1.0, bars_since_act / 60.0);

      // Concatenate full 40 features
      float input_tensor[TOTAL_FEATURES];
      for(int i = 0; i < NUM_MARKET_FEATURES; i++)   input_tensor[i] = market_feats[i];
      for(int j = 0; j < NUM_POSITION_FEATURES; j++) input_tensor[NUM_MARKET_FEATURES + j] = pos_feats[j];

      // If ONNX is loaded, perform model inference
      if(m_onnx_handle != INVALID_HANDLE)
      {
         float action_probs[7];
         float size_pred[1];
         float order_pred[2];

         if(OnnxRun(m_onnx_handle, ONNX_NO_CONVERSION, input_tensor, action_probs, size_pred, order_pred))
         {
            // Select argmax action
            int best_a = 0;
            float best_p = action_probs[0];
            for(int a = 1; a < 7; a++)
            {
               if(action_probs[a] > best_p)
               {
                  best_p = action_probs[a];
                  best_a = a;
               }
            }

            out_action = best_a;
            out_size_fraction = MathMin(1.0, MathMax(0.1, (double)size_pred[0]));
            out_sl_atr = MathMin(4.0, MathMax(1.0, (double)order_pred[0]));
            out_tp_atr = MathMin(7.0, MathMax(1.5, (double)order_pred[1]));
            return;
         }
      }

      // Robust Heuristic Fallback Policy if ONNX is not yet loaded
      // Uses multi-horizon momentum, relative EMA position, and local z-scores
      float mom15 = market_feats[3]; // ret_15
      float z20   = market_feats[17];
      float rsi   = market_feats[23];
      float dist_ema50 = market_feats[21];

      out_size_fraction = 0.5;
      out_sl_atr = 2.0;
      out_tp_atr = 3.5;

      if(pos_dir == 0.0)
      {
         if(mom15 > 0.0015 && z20 > 0.5 && dist_ema50 > 0.3 && rsi < 0.70)
         {
            out_action = ACTION_OPEN_LONG;
         }
         else if(mom15 < -0.0015 && z20 < -0.5 && dist_ema50 < -0.3 && rsi > 0.30)
         {
            out_action = ACTION_OPEN_SHORT;
         }
         else
         {
            out_action = ACTION_HOLD;
         }
      }
      else
      {
         double unrl = pos_feats[3]; // unrealized pnl in atr
         if(unrl < -1.5)
         {
            out_action = ACTION_CLOSE; // Risk cut
         }
         else if(unrl > 2.5 && ((pos_dir > 0 && rsi > 0.8) || (pos_dir < 0 && rsi < 0.2)))
         {
            out_action = ACTION_REDUCE; // Partial take profit on exhaustion
         }
         else
         {
            out_action = ACTION_HOLD;
         }
      }
   }

   void RecordActionExecuted()
   {
      m_last_action_time = TimeCurrent();
   }
};

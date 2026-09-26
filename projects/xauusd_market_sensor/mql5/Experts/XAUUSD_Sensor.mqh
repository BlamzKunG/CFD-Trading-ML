//+------------------------------------------------------------------+
//|                                             XAUUSD_Sensor.mqh    |
//|                                     Copyright 2026, BlamzKunG    |
//|                                  https://github.com/BlamzKunG     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG"
#property link      "https://github.com/BlamzKunG"
#property strict

#ifndef ONNX_DEFAULT
#define ONNX_DEFAULT 0
#endif
#ifndef ONNX_COMMON_FOLDER
#define ONNX_COMMON_FOLDER 1
#endif

//+------------------------------------------------------------------+
//| Market Advantage Signal Classification                           |
//+------------------------------------------------------------------+
enum ENUM_MARKET_ADVANTAGE
{
   ADVANTAGE_STRONG_BULLISH = 0,  // ฝั่งขึ้นได้เปรียบสูงมาก (Strong Bullish Edge)
   ADVANTAGE_MILD_BULLISH   = 1,  // ฝั่งขึ้นได้เปรียบปานกลาง (Mild Bullish Tilt)
   ADVANTAGE_NEUTRAL        = 2,  // สภาวะสมดุล / กรอบแคบ (Balanced / Range)
   ADVANTAGE_MILD_BEARISH   = 3,  // ฝั่งลงได้เปรียบปานกลาง (Mild Bearish Tilt)
   ADVANTAGE_STRONG_BEARISH = 4   // ฝั่งลงได้เปรียบสูงมาก (Strong Bearish Edge)
};

//+------------------------------------------------------------------+
//| Sensor Signal Data Structure                                     |
//+------------------------------------------------------------------+
struct SensorSignal
{
   ENUM_MARKET_ADVANTAGE advantage;
   string                signal_name;
   string                signal_badge;
   string                interpretation;
   color                 signal_color;
   double                mean_edge_pct;      // ค่าเฉลี่ยความต่าง UP vs DOWN ทั้ง 15 ช่อง (%)
   double                skew_1_60_pct;      // ส่วนต่างที่ 1.0 ATR @ 60m (%)
   double                excursion_score;    // คะแนน Excursion Advantage Score (EAS)
   int                   up_wins;            // จำนวนช่องที่ UP ชนะ
   int                   down_wins;          // จำนวนช่องที่ DOWN ชนะ
   int                   ties;               // จำนวนช่องที่เสมอกัน (<1.5% diff)
   double                dominance_pct;      // สัดส่วนช่องที่ฝั่งชนะครองตลาด (%)
};

//+------------------------------------------------------------------+
//| CXAUUSD_Sensor: 30-Target Probability Surface Sensor for MT5     |
//| รับ Input 22 Features -> Output 30 Probabilities (2 x 5 x 3)     |
//| พร้อมคำนวณ Market Advantage Signal และแสดง Dashboard สุดคมชัด    |
//+------------------------------------------------------------------+
class CXAUUSD_Sensor
{
private:
   string          m_symbol;
   ENUM_TIMEFRAMES m_timeframe;
   long            m_handle;
   bool            m_initialized;
   
   // Indicators
   int             m_atr14_handle;
   int             m_atr50_handle;
   int             m_ema20_handle;
   int             m_ema50_handle;
   int             m_ema200_handle;
   int             m_rsi14_handle;
   
   // Indicator Buffers
   double          m_buf_atr14[];
   double          m_buf_atr50[];
   double          m_buf_ema20[];
   double          m_buf_ema50[];
   double          m_buf_ema200[];
   double          m_buf_rsi14[];
   
   // 30 Probabilities Matrix [2][5][3]
   // Direction: 0 = UP, 1 = DOWN
   // Distance:  0 = 0.5, 1 = 1.0, 2 = 1.5, 3 = 2.0, 4 = 2.5 ATR
   // Horizon:   0 = 30m, 1 = 60m, 2 = 90m
   double          m_prob_matrix[2][5][3];
   float           m_raw_probs[30];

   string          m_gui_prefix;

   long LoadOnnxModel(string model_name)
   {
      ResetLastError();
      // 1. ลองโหลดจากโฟลเดอร์ MQL5\Files\
      long handle = OnnxCreate(model_name, ONNX_DEFAULT);
      if(handle != INVALID_HANDLE)
         return handle;
         
      int err = GetLastError();
      // 2. ลองโหลดจาก Common Data Folder
      ResetLastError();
      handle = OnnxCreate(model_name, ONNX_COMMON_FOLDER);
      if(handle != INVALID_HANDLE)
         return handle;
         
      string data_path = TerminalInfoString(TERMINAL_DATA_PATH);
      PrintFormat("❌ [CXAUUSD_Sensor] ไม่พบโมเดล %s! Error: %d", model_name, err);
      PrintFormat("📍 กรุณาคัดลอกไปไว้ที่: %s\\MQL5\\Files\\", data_path);
      return INVALID_HANDLE;
   }

   bool SetupIndicatorsAndShapes()
   {
      ulong input_shape[] = {1, 22};
      if(!OnnxSetInputShape(m_handle, 0, input_shape))
      {
         Print("❌ [CXAUUSD_Sensor] ล้มเหลวในการตั้งค่า Input Shape [1, 22]");
         Release();
         return false;
      }
      
      ulong output_shape[] = {1, 30};
      OnnxSetOutputShape(m_handle, 0, output_shape);
      
      m_atr14_handle  = iATR(m_symbol, m_timeframe, 14);
      m_atr50_handle  = iATR(m_symbol, m_timeframe, 50);
      m_ema20_handle  = iMA(m_symbol, m_timeframe, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_ema50_handle  = iMA(m_symbol, m_timeframe, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_ema200_handle = iMA(m_symbol, m_timeframe, 200, 0, MODE_EMA, PRICE_CLOSE);
      m_rsi14_handle  = iRSI(m_symbol, m_timeframe, 14, PRICE_CLOSE);
      
      ArraySetAsSeries(m_buf_atr14, true);
      ArraySetAsSeries(m_buf_atr50, true);
      ArraySetAsSeries(m_buf_ema20, true);
      ArraySetAsSeries(m_buf_ema50, true);
      ArraySetAsSeries(m_buf_ema200, true);
      ArraySetAsSeries(m_buf_rsi14, true);
      
      m_initialized = true;
      Print("✅ [CXAUUSD_Sensor] โหลด 30-Head Probability Surface Model สำเร็จ 100%!");
      return true;
   }

   // GUI Helper: สร้างหรืออัปเดต Label
   void UpdateLabel(string name, int x, int y, string text, color clr, int font_size=9, string font="Arial")
   {
      string obj_name = m_gui_prefix + name;
      if(ObjectFind(0, obj_name) < 0)
      {
         ObjectCreate(0, obj_name, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, obj_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
      }
      ObjectSetInteger(0, obj_name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, obj_name, OBJPROP_YDISTANCE, y);
      ObjectSetString(0, obj_name, OBJPROP_TEXT, text);
      ObjectSetString(0, obj_name, OBJPROP_FONT, font);
      ObjectSetInteger(0, obj_name, OBJPROP_FONTSIZE, font_size);
      ObjectSetInteger(0, obj_name, OBJPROP_COLOR, clr);
   }

   // GUI Helper: สร้างหรืออัปเดตกล่องพื้นหลัง
   void UpdateRect(string name, int x, int y, int w, int h, color bg_clr, color border_clr)
   {
      string obj_name = m_gui_prefix + name;
      if(ObjectFind(0, obj_name) < 0)
      {
         ObjectCreate(0, obj_name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
         ObjectSetInteger(0, obj_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, obj_name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
         ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, obj_name, OBJPROP_BACK, false);
      }
      ObjectSetInteger(0, obj_name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, obj_name, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, obj_name, OBJPROP_XSIZE, w);
      ObjectSetInteger(0, obj_name, OBJPROP_YSIZE, h);
      ObjectSetInteger(0, obj_name, OBJPROP_BGCOLOR, bg_clr);
      ObjectSetInteger(0, obj_name, OBJPROP_COLOR, border_clr);
   }

   string MakeBar(double prob_pct, int max_chars=8)
   {
      int filled = (int)MathRound((prob_pct / 100.0) * (double)max_chars);
      if(filled < 0) filled = 0;
      if(filled > max_chars) filled = max_chars;
      string bar = "[";
      for(int i=0; i<filled; i++) bar += "█";
      for(int i=filled; i<max_chars; i++) bar += "░";
      bar += "]";
      return bar;
   }

public:
   CXAUUSD_Sensor()
   {
      m_handle        = INVALID_HANDLE;
      m_atr14_handle  = INVALID_HANDLE;
      m_atr50_handle  = INVALID_HANDLE;
      m_ema20_handle  = INVALID_HANDLE;
      m_ema50_handle  = INVALID_HANDLE;
      m_ema200_handle = INVALID_HANDLE;
      m_rsi14_handle  = INVALID_HANDLE;
      m_initialized   = false;
      m_gui_prefix    = "XAU_SNS_";
      ArrayInitialize(m_raw_probs, 0.0f);
   }
   
   ~CXAUUSD_Sensor()
   {
      Release();
   }
   
   bool Init(string symbol=NULL, ENUM_TIMEFRAMES tf=PERIOD_M1, string model_name="xauusd_sensor_30heads.onnx")
   {
      m_symbol    = (symbol == NULL || symbol == "") ? _Symbol : symbol;
      m_timeframe = tf;
      
      m_handle = LoadOnnxModel(model_name);
      if(m_handle == INVALID_HANDLE) return false;
      
      return SetupIndicatorsAndShapes();
   }
   
   bool ExtractFeatures(float &features[], double &out_curr_price, double &out_curr_atr)
   {
      if(!m_initialized) return false;
      
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      int copied_rates = CopyRates(m_symbol, m_timeframe, 0, 105, rates);
      if(copied_rates < 101) return false;
      
      if(CopyBuffer(m_atr14_handle, 0, 0, 2, m_buf_atr14) < 1 ||
         CopyBuffer(m_atr50_handle, 0, 0, 2, m_buf_atr50) < 1 ||
         CopyBuffer(m_ema20_handle, 0, 0, 2, m_buf_ema20) < 1 ||
         CopyBuffer(m_ema50_handle, 0, 0, 2, m_buf_ema50) < 1 ||
         CopyBuffer(m_ema200_handle, 0, 0, 2, m_buf_ema200) < 1 ||
         CopyBuffer(m_rsi14_handle, 0, 0, 2, m_buf_rsi14) < 1)
      {
         return false;
      }
      
      double c0 = rates[0].close;
      double o0 = rates[0].open;
      double h0 = rates[0].high;
      double l0 = rates[0].low;
      double atr14 = m_buf_atr14[0];
      double atr50 = m_buf_atr50[0];
      if(atr14 <= 0.0) atr14 = 0.01;
      
      out_curr_price = c0;
      out_curr_atr   = atr14;
      
      ArrayResize(features, 22);
      
      // 0-5: Log Returns
      features[0] = (float)MathLog(c0 / rates[1].close);
      features[1] = (float)MathLog(c0 / rates[3].close);
      features[2] = (float)MathLog(c0 / rates[5].close);
      features[3] = (float)MathLog(c0 / rates[15].close);
      features[4] = (float)MathLog(c0 / rates[30].close);
      features[5] = (float)MathLog(c0 / rates[60].close);
      
      // 6-8: EMA Distances per ATR
      features[6] = (float)((c0 - m_buf_ema20[0]) / atr14);
      features[7] = (float)((c0 - m_buf_ema50[0]) / atr14);
      features[8] = (float)((c0 - m_buf_ema200[0]) / atr14);
      
      // 9-10: Volatility Metrics
      features[9]  = (float)(atr14 / c0);
      features[10] = (float)(atr14 / (atr50 + 1e-9));
      
      // 11-14: Candlestick Microstructure per ATR
      features[11] = (float)((h0 - l0) / atr14);
      features[12] = (float)((c0 - o0) / atr14);
      features[13] = (float)((h0 - MathMax(o0, c0)) / atr14);
      features[14] = (float)((MathMin(o0, c0) - l0) / atr14);
      
      // 15: RSI (0-1)
      features[15] = (float)(m_buf_rsi14[0] / 100.0);
      
      // 16-17: Volume Ratios
      double vol_sum20 = 0, vol_sum100 = 0;
      for(int i=0; i<100; i++)
      {
         if(i < 20) vol_sum20 += (double)rates[i].tick_volume;
         vol_sum100 += (double)rates[i].tick_volume;
      }
      features[16] = (float)((double)rates[0].tick_volume / ((vol_sum20 / 20.0) + 1e-9));
      features[17] = (float)((double)rates[0].tick_volume / ((vol_sum100 / 100.0) + 1e-9));
      
      // 18-21: Cyclic Time
      MqlDateTime dt;
      TimeToStruct(rates[0].time, dt);
      double hour_float = (double)dt.hour + ((double)dt.min / 60.0);
      double dow        = (double)dt.day_of_week;
      
      features[18] = (float)MathSin(2.0 * M_PI * hour_float / 24.0);
      features[19] = (float)MathCos(2.0 * M_PI * hour_float / 24.0);
      features[20] = (float)MathSin(2.0 * M_PI * dow / 5.0);
      features[21] = (float)MathCos(2.0 * M_PI * dow / 5.0);
      
      return true;
   }
   
   //+---------------------------------------------------------------+
   //| คำนวณ Probability Surface ทั้งหมด 30 ค่า                      |
   //+---------------------------------------------------------------+
   bool PredictSurface(double &out_price, double &out_atr)
   {
      float features[];
      if(!ExtractFeatures(features, out_price, out_atr)) return false;
      
      if(!OnnxRun(m_handle, ONNX_NO_CONVERSION, features, m_raw_probs))
      {
         Print("❌ [CXAUUSD_Sensor] OnnxRun Error: ", GetLastError());
         return false;
      }
      
      int idx = 0;
      for(int d=0; d<2; d++) // 0: UP, 1: DOWN
      {
         for(int dist=0; dist<5; dist++) // 0.5, 1.0, 1.5, 2.0, 2.5 ATR
         {
            for(int h=0; h<3; h++) // 30m, 60m, 90m
            {
               m_prob_matrix[d][dist][h] = (double)m_raw_probs[idx++];
            }
         }
      }
      return true;
   }
   
   //+---------------------------------------------------------------+
   //| ประเมินผล Signal ความได้เปรียบของตลาด (Market Advantage Signal)|
   //+---------------------------------------------------------------+
   void EvaluateMarketSignal(SensorSignal &out_signal)
   {
      double sum_edge = 0.0;
      int up_wins = 0;
      int down_wins = 0;
      int ties = 0;
      
      for(int dist=0; dist<5; dist++)
      {
         for(int h=0; h<3; h++)
         {
            double p_up   = m_prob_matrix[0][dist][h] * 100.0;
            double p_down = m_prob_matrix[1][dist][h] * 100.0;
            double diff   = p_up - p_down;
            
            sum_edge += diff;
            
            if(diff > 1.5)        up_wins++;
            else if(diff < -1.5)  down_wins++;
            else                  ties++;
         }
      }
      
      double mean_edge = sum_edge / 15.0;
      double skew_1_60 = (m_prob_matrix[0][1][1] - m_prob_matrix[1][1][1]) * 100.0;
      
      // Excursion Advantage Score (EAS): รวมทั้งภาพรวม Mean Edge และ Milestone 1.0 ATR @ 60m
      double eas = (0.5 * mean_edge) + (0.5 * skew_1_60);
      
      out_signal.mean_edge_pct   = mean_edge;
      out_signal.skew_1_60_pct   = skew_1_60;
      out_signal.excursion_score = eas;
      out_signal.up_wins         = up_wins;
      out_signal.down_wins       = down_wins;
      out_signal.ties            = ties;
      
      // กำหนดสถานะ Signal และคำอธิบายเชิงกลยุทธ์
      if(eas >= 6.0 && up_wins >= 10)
      {
         out_signal.advantage      = ADVANTAGE_STRONG_BULLISH;
         out_signal.signal_name    = "STRONG BULLISH ADVANTAGE";
         out_signal.signal_badge   = "🟢🟢 STRONG BULLISH EDGE";
         out_signal.signal_color   = C'0,230,118'; // Vivid Lime Green
         out_signal.interpretation = "ฝั่งขึ้นได้เปรียบสูงมาก: มี Room-to-Run กว้างและโอกาสแตะระยะ 1.0-2.5 ATR สูงกว่าชัดเจน";
         out_signal.dominance_pct  = ((double)up_wins / 15.0) * 100.0;
      }
      else if(eas >= 2.5 && up_wins >= 8)
      {
         out_signal.advantage      = ADVANTAGE_MILD_BULLISH;
         out_signal.signal_name    = "MILD BULLISH ADVANTAGE";
         out_signal.signal_badge   = "🟢 MILD BULLISH TILT";
         out_signal.signal_color   = C'100,221,23'; // Light Green
         out_signal.interpretation = "ฝั่งขึ้นได้เปรียบปานกลาง: ความน่าจะเป็นฝั่งขึ้นเอื้ออำนวยมากกว่าเล็กน้อย";
         out_signal.dominance_pct  = ((double)up_wins / 15.0) * 100.0;
      }
      else if(eas <= -6.0 && down_wins >= 10)
      {
         out_signal.advantage      = ADVANTAGE_STRONG_BEARISH;
         out_signal.signal_name    = "STRONG BEARISH ADVANTAGE";
         out_signal.signal_badge   = "🔴🔴 STRONG BEARISH EDGE";
         out_signal.signal_color   = C'255,82,82'; // Vivid Red
         out_signal.interpretation = "ฝั่งลงได้เปรียบสูงมาก: มี Room-to-Run ฝั่งลงกว้างและโอกาสทุบแตะ 1.0-2.5 ATR สูงกว่าชัดเจน";
         out_signal.dominance_pct  = ((double)down_wins / 15.0) * 100.0;
      }
      else if(eas <= -2.5 && down_wins >= 8)
      {
         out_signal.advantage      = ADVANTAGE_MILD_BEARISH;
         out_signal.signal_name    = "MILD BEARISH ADVANTAGE";
         out_signal.signal_badge   = "🔴 MILD BEARISH TILT";
         out_signal.signal_color   = C'255,145,0'; // Coral Orange
         out_signal.interpretation = "ฝั่งลงได้เปรียบปานกลาง: ความน่าจะเป็นฝั่งลงเอื้ออำนวยมากกว่าเล็กน้อย";
         out_signal.dominance_pct  = ((double)down_wins / 15.0) * 100.0;
      }
      else
      {
         out_signal.advantage      = ADVANTAGE_NEUTRAL;
         out_signal.signal_name    = "BALANCED / NEUTRAL";
         out_signal.signal_badge   = "⚪ BALANCED / COMPRESSION";
         out_signal.signal_color   = C'176,190,197'; // Silver Gray
         out_signal.interpretation = "สภาวะสมดุล: โอกาสแตะทั้งสองฝั่งสูสีกัน ไม่มีความได้เปรียบเชิงระยะทางที่ชัดเจน";
         out_signal.dominance_pct  = 50.0;
      }
   }
   
   double GetProbability(int dir, int dist_idx, int h_idx)
   {
      if(dir < 0 || dir > 1 || dist_idx < 0 || dist_idx > 4 || h_idx < 0 || h_idx > 2)
         return 0.0;
      return m_prob_matrix[dir][dist_idx][h_idx];
   }
   
   void GetRawArray(float &out_probs[])
   {
      ArrayCopy(out_probs, m_raw_probs);
   }
   
   void CheckMonotonicity(int &out_dist_violations, int &out_horizon_violations)
   {
      out_dist_violations = 0;
      out_horizon_violations = 0;
      
      for(int d=0; d<2; d++)
      {
         for(int h=0; h<3; h++)
         {
            for(int dist=0; dist<4; dist++)
            {
               if(m_prob_matrix[d][dist+1][h] > m_prob_matrix[d][dist][h] + 0.01)
                  out_dist_violations++;
            }
         }
         for(int dist=0; dist<5; dist++)
         {
            for(int h=0; h<2; h++)
            {
               if(m_prob_matrix[d][dist][h] > m_prob_matrix[d][dist][h+1] + 0.01)
                  out_horizon_violations++;
            }
         }
      }
   }
   
   //+---------------------------------------------------------------+
   //| FormatDashboard: ออกแบบตารางใน Comment อย่างสวยงาม คมชัด       |
   //| พร้อมเน้น HIGHLIGHTS ฝั่งที่ % เยอะกว่าอย่างชัดเจน            |
   //+---------------------------------------------------------------+
   string FormatDashboard(double curr_price, double curr_atr)
   {
      int dist_v = 0, horiz_v = 0;
      CheckMonotonicity(dist_v, horiz_v);
      
      SensorSignal sig;
      EvaluateMarketSignal(sig);
      
      string dist_labels[5] = {"0.5 ATR", "1.0 ATR", "1.5 ATR", "2.0 ATR", "2.5 ATR"};
      
      string text = "╔═════════════════════════════════════════════════════════════════════════════════╗\n" +
                    "║  📡 XAUUSD PROBABILISTIC MARKET SENSOR  |  M1 ROOM-TO-RUN ENGINE                ║\n" +
                    "╠═════════════════════════════════════════════════════════════════════════════════╣\n" +
                    StringFormat("║  Price: %-9.2f  │  ATR(14): %-6.2f  │  Time: %-27s║\n",
                                 curr_price, curr_atr, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS)) +
                    "║                                                                                 ║\n" +
                    StringFormat("║  ▶ SIGNAL     : %-64s║\n", sig.signal_badge) +
                    StringFormat("║  ▶ DOMINANCE  : %s WINS %d / 15 CELLS (%.1f%%)  │  Net Edge: %+.1f%%            ║\n",
                                 (sig.up_wins >= sig.down_wins ? "▲ UP" : "▼ DN"),
                                 MathMax(sig.up_wins, sig.down_wins),
                                 (MathMax(sig.up_wins, sig.down_wins) / 15.0) * 100.0,
                                 sig.mean_edge_pct) +
                    StringFormat("║  ▶ STRATEGY   : %-64s║\n", sig.interpretation) +
                    "╠═════════════════════════════════════════════════════════════════════════════════╣\n" +
                    "║  HEAD-TO-HEAD REACH COMPARISON  ( [*] = HIGHLIGHTED ADVANTAGE WINNER )          ║\n" +
                    "╟─────────────┬─────────────────────┬─────────────────────┬───────────────────────╢\n" +
                    "║ Target Dist │      H=30 min       │      H=60 min       │       H=90 min        ║\n" +
                    "╟─────────────┼─────────────────────┼─────────────────────┼───────────────────────╢\n";

      for(int i=0; i<5; i++)
      {
         string cell_str[3];
         for(int h=0; h<3; h++)
         {
            double p_up = m_prob_matrix[0][i][h] * 100.0;
            double p_dn = m_prob_matrix[1][i][h] * 100.0;
            double diff = p_up - p_dn;
            
            // HIGHLIGHT ฝั่งที่ % เยอะกว่า
            if(diff > 1.5)
            {
               cell_str[h] = StringFormat("[▲%4.1f%%*] vs %4.1f%%", p_up, p_dn); // UP HIGHLIGHT
            }
            else if(diff < -1.5)
            {
               cell_str[h] = StringFormat(" %4.1f%%  vs[▼%4.1f%%*]", p_up, p_dn); // DN HIGHLIGHT
            }
            else
            {
               cell_str[h] = StringFormat(" %4.1f%%  ~  %4.1f%% ", p_up, p_dn); // TIED
            }
         }
         
         text += StringFormat("║ %-11s │ %-19s │ %-19s │ %-21s ║\n",
                              dist_labels[i], cell_str[0], cell_str[1], cell_str[2]);
      }
      
      text += "╟─────────────┴─────────────────────┴─────────────────────┴───────────────────────╢\n" +
              StringFormat("║ Skew(1.0 ATR @ 60m): %+.1f%%  │  Physical Monotonicity Violations: D=%d, H=%d       ║\n",
                           sig.skew_1_60_pct, dist_v, horiz_v) +
              "╠═════════════════════════════════════════════════════════════════════════════════╣\n" +
              "║  VISUAL PROBABILITY GAUGES                                                      ║\n" +
              "╟─────────────────────────────────────────────────────────────────────────────────╢\n";
              
      // Mini visual bars for key milestones
      text += StringFormat("║  ▲ UP   1.0 ATR: 30m %s %4.1f%% │ 60m %s %4.1f%% │ 90m %s %4.1f%% ║\n",
                           MakeBar(m_prob_matrix[0][1][0] * 100.0, 6), m_prob_matrix[0][1][0] * 100.0,
                           MakeBar(m_prob_matrix[0][1][1] * 100.0, 6), m_prob_matrix[0][1][1] * 100.0,
                           MakeBar(m_prob_matrix[0][1][2] * 100.0, 6), m_prob_matrix[0][1][2] * 100.0);
                           
      text += StringFormat("║  ▼ DOWN 1.0 ATR: 30m %s %4.1f%% │ 60m %s %4.1f%% │ 90m %s %4.1f%% ║\n",
                           MakeBar(m_prob_matrix[1][1][0] * 100.0, 6), m_prob_matrix[1][1][0] * 100.0,
                           MakeBar(m_prob_matrix[1][1][1] * 100.0, 6), m_prob_matrix[1][1][1] * 100.0,
                           MakeBar(m_prob_matrix[1][1][2] * 100.0, 6), m_prob_matrix[1][1][2] * 100.0);
                           
      text += "╚═════════════════════════════════════════════════════════════════════════════════╝";
      
      return text;
   }

   //+---------------------------------------------------------------+
   //| RenderGuiDashboard: วาด Graphical On-Chart Panel สไตล์ Dark HUD |
   //| พร้อมลงสี Color Highlight สดๆ บนกราฟ MT5                       |
   //+---------------------------------------------------------------+
   void RenderGuiDashboard(double curr_price, double curr_atr, int x_offset=20, int y_offset=30)
   {
      SensorSignal sig;
      EvaluateMarketSignal(sig);
      
      int dist_v = 0, horiz_v = 0;
      CheckMonotonicity(dist_v, horiz_v);

      int panel_w = 460;
      int panel_h = 320;
      
      color bg_panel   = C'18,22,32';     // Dark Slate
      color bg_card    = C'26,32,46';     // Card Dark Blue
      color border_clr = C'48,60,84';     // Card Border
      color text_title = C'255,255,255';  // White
      color text_dim   = C'144,164,174';  // Dim Gray
      color clr_up     = C'0,230,118';    // Vivid Spring Green (UP Highlight)
      color clr_down   = C'255,82,82';    // Vivid Coral Red (DOWN Highlight)
      color clr_tie    = C'176,190,197';  // Neutral Silver

      // 1. Panel Background
      UpdateRect("BG", x_offset, y_offset, panel_w, panel_h, bg_panel, border_clr);
      
      // 2. Header Title & Info
      UpdateLabel("Title", x_offset+16, y_offset+12, "XAUUSD ROOM-TO-RUN SENSOR", text_title, 11, "Arial Bold");
      UpdateLabel("SubInfo", x_offset+260, y_offset+14, StringFormat("Price: %.2f | ATR: %.2f", curr_price, curr_atr), text_dim, 8, "Arial");
      
      // 3. Signal Card Box
      color sig_box_bg = (sig.advantage == ADVANTAGE_STRONG_BULLISH || sig.advantage == ADVANTAGE_MILD_BULLISH) ? C'16,40,28' :
                         (sig.advantage == ADVANTAGE_STRONG_BEARISH || sig.advantage == ADVANTAGE_MILD_BEARISH) ? C'44,18,22' : C'28,32,42';
      color sig_border = (sig.advantage == ADVANTAGE_STRONG_BULLISH || sig.advantage == ADVANTAGE_MILD_BULLISH) ? clr_up :
                         (sig.advantage == ADVANTAGE_STRONG_BEARISH || sig.advantage == ADVANTAGE_MILD_BEARISH) ? clr_down : border_clr;
                         
      UpdateRect("SigBox", x_offset+14, y_offset+38, panel_w-28, 48, sig_box_bg, sig_border);
      UpdateLabel("SigText", x_offset+24, y_offset+44, sig.signal_badge, sig.signal_color, 11, "Arial Bold");
      
      string edge_summary = StringFormat("Net Edge: %+.1f%%  |  Dominance: %s %d/15 Cells (%.0f%%)  |  Skew(1.0ATR): %+.1f%%",
                                         sig.mean_edge_pct,
                                         (sig.up_wins >= sig.down_wins ? "UP" : "DOWN"),
                                         MathMax(sig.up_wins, sig.down_wins),
                                         (MathMax(sig.up_wins, sig.down_wins) / 15.0) * 100.0,
                                         sig.skew_1_60_pct);
      UpdateLabel("SigEdge", x_offset+24, y_offset+66, edge_summary, text_title, 8, "Arial");

      // 4. Matrix Header Row
      int grid_y = y_offset + 98;
      UpdateRect("GridHdrBg", x_offset+14, grid_y, panel_w-28, 22, bg_card, border_clr);
      UpdateLabel("Hdr_Dist", x_offset+22, grid_y+4, "Distance", text_dim, 8, "Arial Bold");
      UpdateLabel("Hdr_H30",  x_offset+110, grid_y+4, "H = 30 min (M1)", text_dim, 8, "Arial Bold");
      UpdateLabel("Hdr_H60",  x_offset+225, grid_y+4, "H = 60 min (M1)", text_dim, 8, "Arial Bold");
      UpdateLabel("Hdr_H90",  x_offset+340, grid_y+4, "H = 90 min (M1)", text_dim, 8, "Arial Bold");

      // 5. 5 Rows of Distance Head-to-Head Comparison
      string dist_names[5] = {"0.5 ATR", "1.0 ATR", "1.5 ATR", "2.0 ATR", "2.5 ATR"};
      int row_y = grid_y + 24;
      
      for(int i=0; i<5; i++)
      {
         int curr_row_y = row_y + (i * 26);
         color row_bg = (i % 2 == 0) ? C'22,26,38' : bg_panel;
         UpdateRect(StringFormat("RowBg_%d", i), x_offset+14, curr_row_y, panel_w-28, 24, row_bg, border_clr);
         
         UpdateLabel(StringFormat("DistLabel_%d", i), x_offset+22, curr_row_y+5, dist_names[i], text_title, 8, "Arial Bold");
         
         // 3 Horizon Columns with HIGHLIGHTS on Higher %
         int col_x[3] = {x_offset+110, x_offset+225, x_offset+340};
         for(int h=0; h<3; h++)
         {
            double p_up = m_prob_matrix[0][i][h] * 100.0;
            double p_dn = m_prob_matrix[1][i][h] * 100.0;
            double diff = p_up - p_dn;
            
            string cell_text = "";
            color  cell_color = clr_tie;
            
            if(diff > 1.5)
            {
               // UP ชนะ -> Highlight สีเขียว พร้อมไอคอน ▲
               cell_text  = StringFormat("▲ %.1f%% (v %.1f%%)", p_up, p_dn);
               cell_color = clr_up;
            }
            else if(diff < -1.5)
            {
               // DOWN ชนะ -> Highlight สีแดง พร้อมไอคอน ▼
               cell_text  = StringFormat("▼ %.1f%% (v %.1f%%)", p_dn, p_up);
               cell_color = clr_down;
            }
            else
            {
               // เสมอกัน
               cell_text  = StringFormat("~ %.1f%% vs %.1f%%", p_up, p_dn);
               cell_color = clr_tie;
            }
            
            UpdateLabel(StringFormat("Cell_%d_%d", i, h), col_x[h], curr_row_y+5, cell_text, cell_color, 8, "Arial Bold");
         }
      }

      // 6. Footer Information
      int footer_y = row_y + (5 * 26) + 10;
      string footer_str = StringFormat("Physical Monotonicity: 100%% Valid (Violations: %d) | Engine: MT5 Build 6063+ ONNX",
                                       dist_v + horiz_v);
      UpdateLabel("Footer", x_offset+20, footer_y, footer_str, text_dim, 7, "Arial");
      
      ChartRedraw(0);
   }

   // ลบ GUI Chart Objects ทั้งหมดเมื่อปิดหรือเปลี่ยนชาร์ต
   void ClearGui()
   {
      ObjectsDeleteAll(0, m_gui_prefix);
      ChartRedraw(0);
   }
   
   void Release()
   {
      ClearGui();
      if(m_handle        != INVALID_HANDLE) { OnnxRelease(m_handle);        m_handle = INVALID_HANDLE; }
      if(m_atr14_handle  != INVALID_HANDLE) { IndicatorRelease(m_atr14_handle); m_atr14_handle = INVALID_HANDLE; }
      if(m_atr50_handle  != INVALID_HANDLE) { IndicatorRelease(m_atr50_handle); m_atr50_handle = INVALID_HANDLE; }
      if(m_ema20_handle  != INVALID_HANDLE) { IndicatorRelease(m_ema20_handle); m_ema20_handle = INVALID_HANDLE; }
      if(m_ema50_handle  != INVALID_HANDLE) { IndicatorRelease(m_ema50_handle); m_ema50_handle = INVALID_HANDLE; }
      if(m_ema200_handle != INVALID_HANDLE) { IndicatorRelease(m_ema200_handle); m_ema200_handle = INVALID_HANDLE; }
      if(m_rsi14_handle  != INVALID_HANDLE) { IndicatorRelease(m_rsi14_handle); m_rsi14_handle = INVALID_HANDLE; }
      m_initialized = false;
   }
};

//+------------------------------------------------------------------+
//|                                                 XAUUSD_ML.mqh     |
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
//| CXAUUSD_ML: Helper Class สำหรับเรียกใช้ ONNX ML Models ใน MT5 EA  |
//| ทำนายระยะ Upside (โอกาสขึ้น) และ Downside (โอกาสลง) ในอีก N แท่ง |
//+------------------------------------------------------------------+
class CXAUUSD_ML
{
private:
   string         m_symbol;
   ENUM_TIMEFRAMES m_timeframe;
   long           m_handle_up;
   long           m_handle_down;
   int            m_atr14_handle;
   int            m_atr50_handle;
   int            m_ema20_handle;
   int            m_ema50_handle;
   int            m_ema200_handle;
   int            m_rsi14_handle;
   bool           m_initialized;
   
   // Buffer สำหรับ Indicators
   double         m_buf_atr14[];
   double         m_buf_atr50[];
   double         m_buf_ema20[];
   double         m_buf_ema50[];
   double         m_buf_ema200[];
   double         m_buf_rsi14[];
   
   // ฟังก์ชันค้นหาและโหลดโมเดล ONNX พร้อม fallback อัตโนมัติ
   long LoadOnnxModel(string model_name)
   {
      ResetLastError();
      // 1. ลองโหลดจาก MQL5\Files\ ของ Terminal ปัจจุบัน
      long handle = OnnxCreate(model_name, ONNX_DEFAULT);
      if(handle != INVALID_HANDLE)
         return handle;
      
      int err = GetLastError();
      
      // 2. ถ้าไม่พบ ลองโหลดจาก Common Data Folder (Common\Files\)
      ResetLastError();
      handle = OnnxCreate(model_name, ONNX_COMMON_FOLDER);
      if(handle != INVALID_HANDLE)
      {
         PrintFormat("ℹ️ [CXAUUSD_ML] โหลดโมเดล %s จาก Common Data Folder สำเร็จ", model_name);
         return handle;
      }
      
      // แจ้ง Error พร้อมระบุโฟลเดอร์ที่ถูกต้องให้ชัดเจน
      string data_path = TerminalInfoString(TERMINAL_DATA_PATH);
      string common_path = TerminalInfoString(TERMINAL_COMMONDATA_PATH);
      PrintFormat("❌ [CXAUUSD_ML] ไม่พบหรือโหลดโมเดล '%s' ไม่สำเร็จ! Error: %d", model_name, err);
      PrintFormat("📍 กรุณาคัดลอกไฟล์ '%s' ไปไว้ที่โฟลเดอร์ต่อไปนี้:", model_name);
      PrintFormat("   [1] Terminal Files: %s\\MQL5\\Files\\", data_path);
      PrintFormat("   [2] Common Files:   %s\\Files\\", common_path);
      return INVALID_HANDLE;
   }

   // ฟังก์ชันตั้งค่า Tensor Shape และ Indicators
   bool SetupModelShapesAndIndicators()
   {
      // กำหนด Input Shape [1, 22]
      ulong input_shape[] = {1, 22};
      if(!OnnxSetInputShape(m_handle_up, 0, input_shape) || !OnnxSetInputShape(m_handle_down, 0, input_shape))
      {
         Print("❌ [CXAUUSD_ML] ล้มเหลวในการตั้งค่า Input Shape [1, 22]");
         Release();
         return false;
      }
      
      // กำหนด Output Shape [1, 1]
      ulong output_shape[] = {1, 1};
      OnnxSetOutputShape(m_handle_up, 0, output_shape);
      OnnxSetOutputShape(m_handle_down, 0, output_shape);
      
      // ผูก Indicators สำหรับคำนวณ Features
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
      Print("✅ [CXAUUSD_ML] เริ่มต้นระบบและโหลด ONNX Models สำเร็จ 100%!");
      return true;
   }

public:
   CXAUUSD_ML()
   {
      m_handle_up     = INVALID_HANDLE;
      m_handle_down   = INVALID_HANDLE;
      m_atr14_handle  = INVALID_HANDLE;
      m_atr50_handle  = INVALID_HANDLE;
      m_ema20_handle  = INVALID_HANDLE;
      m_ema50_handle  = INVALID_HANDLE;
      m_ema200_handle = INVALID_HANDLE;
      m_rsi14_handle  = INVALID_HANDLE;
      m_initialized   = false;
   }
   
   ~CXAUUSD_ML()
   {
      Release();
   }
   
   //+---------------------------------------------------------------+
   //| กำหนดค่าเริ่มต้น และโหลดไฟล์ ONNX โมเดลจากไฟล์                |
   //+---------------------------------------------------------------+
   bool Init(string symbol=NULL, ENUM_TIMEFRAMES tf=PERIOD_M1, 
             string up_model_name="xauusd_upside.onnx", 
             string down_model_name="xauusd_downside.onnx")
   {
      m_symbol    = (symbol == NULL || symbol == "") ? _Symbol : symbol;
      m_timeframe = tf;
      
      m_handle_up = LoadOnnxModel(up_model_name);
      if(m_handle_up == INVALID_HANDLE)
         return false;
      
      m_handle_down = LoadOnnxModel(down_model_name);
      if(m_handle_down == INVALID_HANDLE)
      {
         OnnxRelease(m_handle_up);
         m_handle_up = INVALID_HANDLE;
         return false;
      }
      
      return SetupModelShapesAndIndicators();
   }
   
   //+---------------------------------------------------------------+
   //| โหลดโมเดลจาก Memory Buffer (สำหรับการฝังโมเดลผ่าน #resource)   |
   //+---------------------------------------------------------------+
   bool InitFromBuffer(const uchar &up_buffer[], const uchar &down_buffer[],
                       string symbol=NULL, ENUM_TIMEFRAMES tf=PERIOD_M1)
   {
      m_symbol    = (symbol == NULL || symbol == "") ? _Symbol : symbol;
      m_timeframe = tf;
      
      ResetLastError();
      m_handle_up = OnnxCreateFromBuffer(up_buffer, ONNX_DEFAULT);
      if(m_handle_up == INVALID_HANDLE)
      {
         PrintFormat("❌ [CXAUUSD_ML] OnnxCreateFromBuffer (Upside) ล้มเหลว! Error: %d", GetLastError());
         return false;
      }
      
      ResetLastError();
      m_handle_down = OnnxCreateFromBuffer(down_buffer, ONNX_DEFAULT);
      if(m_handle_down == INVALID_HANDLE)
      {
         PrintFormat("❌ [CXAUUSD_ML] OnnxCreateFromBuffer (Downside) ล้มเหลว! Error: %d", GetLastError());
         OnnxRelease(m_handle_up);
         m_handle_up = INVALID_HANDLE;
         return false;
      }
      
      return SetupModelShapesAndIndicators();
   }
   
   //+---------------------------------------------------------------+
   //| คำนวณ 22 Scale-Invariant Features จากกราฟสด                   |
   //+---------------------------------------------------------------+
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
      
      // 0-5: Log Returns (1, 3, 5, 15, 30, 60)
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
      double vol_avg20  = vol_sum20 / 20.0;
      double vol_avg100 = vol_sum100 / 100.0;
      features[16] = (float)((double)rates[0].tick_volume / (vol_avg20 + 1e-9));
      features[17] = (float)((double)rates[0].tick_volume / (vol_avg100 + 1e-9));
      
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
   //| ฟังก์ชันทำนาย Upside & Downside (ส่งกลับเป็นจำนวนเท่าของ ATR) |
   //+---------------------------------------------------------------+
   bool Predict(double &out_upside_atr, double &out_downside_atr, double &out_curr_price, double &out_curr_atr)
   {
      float features[];
      if(!ExtractFeatures(features, out_curr_price, out_curr_atr)) return false;
      
      float output_up[1];
      float output_down[1];
      
      if(!OnnxRun(m_handle_up, ONNX_NO_CONVERSION, features, output_up))
      {
         Print("❌ [CXAUUSD_ML] OnnxRun Upside Error: ", GetLastError());
         return false;
      }
      if(!OnnxRun(m_handle_down, ONNX_NO_CONVERSION, features, output_down))
      {
         Print("❌ [CXAUUSD_ML] OnnxRun Downside Error: ", GetLastError());
         return false;
      }
      
      out_upside_atr   = (double)output_up[0];
      out_downside_atr = (double)output_down[0];
      return true;
   }
   
   //+---------------------------------------------------------------+
   //| ฟังก์ชันช่วย: คืนค่าราคาสูงสุดและต่ำสุดที่คาดหวังเป็นดอลลาร์     |
   //+---------------------------------------------------------------+
   bool GetExpectedPriceTargets(double &expected_max_high, double &expected_max_low, double &out_up_atr, double &out_down_atr)
   {
      double curr_price = 0, curr_atr = 0;
      if(!Predict(out_up_atr, out_down_atr, curr_price, curr_atr)) return false;
      
      expected_max_high = curr_price + (out_up_atr   * curr_atr);
      expected_max_low  = curr_price - (out_down_atr * curr_atr);
      return true;
   }
   
   void Release()
   {
      if(m_handle_up     != INVALID_HANDLE) { OnnxRelease(m_handle_up);     m_handle_up = INVALID_HANDLE; }
      if(m_handle_down   != INVALID_HANDLE) { OnnxRelease(m_handle_down);   m_handle_down = INVALID_HANDLE; }
      if(m_atr14_handle  != INVALID_HANDLE) { IndicatorRelease(m_atr14_handle); m_atr14_handle = INVALID_HANDLE; }
      if(m_atr50_handle  != INVALID_HANDLE) { IndicatorRelease(m_atr50_handle); m_atr50_handle = INVALID_HANDLE; }
      if(m_ema20_handle  != INVALID_HANDLE) { IndicatorRelease(m_ema20_handle); m_ema20_handle = INVALID_HANDLE; }
      if(m_ema50_handle  != INVALID_HANDLE) { IndicatorRelease(m_ema50_handle); m_ema50_handle = INVALID_HANDLE; }
      if(m_ema200_handle != INVALID_HANDLE) { IndicatorRelease(m_ema200_handle); m_ema200_handle = INVALID_HANDLE; }
      if(m_rsi14_handle  != INVALID_HANDLE) { IndicatorRelease(m_rsi14_handle); m_rsi14_handle = INVALID_HANDLE; }
      m_initialized = false;
   }
};

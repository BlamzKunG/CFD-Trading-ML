//+------------------------------------------------------------------+
//|                                    XAUUSD_Market_Sensor_EA.mq5   |
//|                                      Copyright 2026, BlamzKunG   |
//|                                   https://github.com/BlamzKunG   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG"
#property link      "https://github.com/BlamzKunG"
#property version   "2.10"
#property strict

// ส่งโมเดล ONNX เข้าสู่ Strategy Tester อัตโนมัติ
#property tester_file "xauusd_sensor_30heads.onnx"

// เรียกใช้ Sensor Library (รองรับทั้งโฟลเดอร์ Experts/ และ Include/)
#if __has_include("XAUUSD_Sensor.mqh")
   #include "XAUUSD_Sensor.mqh"
#elif __has_include(<XAUUSD_Sensor.mqh>)
   #include <XAUUSD_Sensor.mqh>
#elif __has_include("..\Include\XAUUSD_Sensor.mqh")
   #include "..\Include\XAUUSD_Sensor.mqh"
#else
   #include <XAUUSD_Sensor.mqh>
#endif

//+------------------------------------------------------------------+
//| Dashboard Display Mode                                           |
//+------------------------------------------------------------------+
enum ENUM_DASHBOARD_TYPE
{
   DASH_BOTH         = 0, // ทั้ง Graphical HUD บนกราฟ และ Text ใน Comment
   DASH_GUI_ONLY     = 1, // เฉพาะ Graphical HUD บนกราฟ (สวยงามทันสมัย)
   DASH_COMMENT_ONLY = 2  // เฉพาะ Text ใน Comment (เหมาะกับ VPS/ประหยัดทรัพยากร)
};

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== Model & Engine Configuration ==="
input string              InpModelName         = "xauusd_sensor_30heads.onnx"; // ชื่อไฟล์โมเดล ONNX (อยู่ใน MQL5\Files\)

input group "=== Dashboard Visuals & Style ==="
input bool                InpShowDashboard     = true;                         // เปิดการแสดงผล Dashboard
input ENUM_DASHBOARD_TYPE InpDashboardType     = DASH_BOTH;                    // รูปแบบ Dashboard ที่ต้องการแสดงผล
input int                 InpGuiXOffset        = 20;                           // ตำแหน่งแกน X (พิกเซลจากขอบซ้าย)
input int                 InpGuiYOffset        = 30;                           // ตำแหน่งแกน Y (พิกเซลจากขอบบน)

input group "=== Market Signal & Alerts ==="
input bool                InpAlertOnSignal     = true;                         // ส่งเสียงและหน้าต่าง Alert เมื่อความได้เปรียบเปลี่ยน
input bool                InpPushNotification  = false;                        // ส่งแจ้งเตือนเข้ามือถือ MT5 App

input group "=== Data Logging ==="
input bool                InpLogToCSV          = true;                         // บันทึกค่า Probability 30 ช่องและ Signal ลง CSV
input string              InpCSVFileName       = "XAUUSD_Sensor_Log.csv";      // ชื่อไฟล์บันทึก CSV

// ตัวแปร Global
CXAUUSD_Sensor        gl_sensor;
int                   gl_file_handle      = INVALID_HANDLE;
ENUM_MARKET_ADVANTAGE gl_last_signal      = ADVANTAGE_NEUTRAL;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("🚀 [Market Sensor] Initializing 30-Target Probability Sensor for XAUUSD...");
   
   if(!gl_sensor.Init(_Symbol, PERIOD_M1, InpModelName))
   {
      string error_msg = StringFormat(
         "❌ [Market Sensor] ไม่พบหรือโหลดโมเดล %s ไม่สำเร็จ!\n\n" +
         "กรุณานำไฟล์โมเดลไปวางที่:\n%s\\MQL5\\Files\\",
         InpModelName, TerminalInfoString(TERMINAL_DATA_PATH)
      );
      Print(error_msg);
      Alert(error_msg);
      return INIT_FAILED;
   }
   
   // เปิดไฟล์ CSV สำหรับบันทึก Log
   if(InpLogToCSV)
   {
      ResetLastError();
      gl_file_handle = FileOpen(InpCSVFileName, FILE_WRITE | FILE_READ | FILE_CSV | FILE_ANSI, ",");
      if(gl_file_handle != INVALID_HANDLE)
      {
         if(FileSize(gl_file_handle) == 0)
         {
            string header = "datetime,close,atr14," +
                            "up_0.5_30,up_0.5_60,up_0.5_90," +
                            "up_1.0_30,up_1.0_60,up_1.0_90," +
                            "up_1.5_30,up_1.5_60,up_1.5_90," +
                            "up_2.0_30,up_2.0_60,up_2.0_90," +
                            "up_2.5_30,up_2.5_60,up_2.5_90," +
                            "down_0.5_30,down_0.5_60,down_0.5_90," +
                            "down_1.0_30,down_1.0_60,down_1.0_90," +
                            "down_1.5_30,down_1.5_60,down_1.5_90," +
                            "down_2.0_30,down_2.0_60,down_2.0_90," +
                            "down_2.5_30,down_2.5_60,down_2.5_90," +
                            "signal_name,net_edge_pct,skew_1_60,up_wins,down_wins,dist_v,horiz_v";
            FileWriteString(gl_file_handle, header + "\n");
         }
         else
         {
            FileSeek(gl_file_handle, 0, SEEK_END);
         }
         PrintFormat("📝 [Market Sensor] กำลังบันทึก Log สู่ไฟล์: MQL5\\Files\\%s", InpCSVFileName);
      }
      else
      {
         PrintFormat("⚠️ [Market Sensor] ไม่สามารถเปิดไฟล์ CSV ได้! Error: %d", GetLastError());
      }
   }
   
   Print("✅ [Market Sensor] ระบบ Sensor เริ่มต้นสมบูรณ์ พร้อมตรวจวัดสภาพตลาดและแสดง Dashboard!");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   gl_sensor.ClearGui();
   gl_sensor.Release();
   
   if(gl_file_handle != INVALID_HANDLE)
   {
      FileClose(gl_file_handle);
      gl_file_handle = INVALID_HANDLE;
   }
   
   Comment("");
   Print("🚪 [Market Sensor] ปิดระบบและเคลียร์หน้าจอเรียบร้อย");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // คำนวณเฉพาะแท่งใหม่ (New Bar M1) เพื่อประหยัด CPU
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;
   
   double curr_price = 0, curr_atr = 0;
   
   // 1. เรียกคำนวณ Probability Surface ทั้ง 30 ค่าใน 1 คำสั่ง
   if(gl_sensor.PredictSurface(curr_price, curr_atr))
   {
      // 2. คำนวณ Signal สภาวะความได้เปรียบของตลาด
      SensorSignal sig;
      gl_sensor.EvaluateMarketSignal(sig);
      
      // 3. แสดงผล Dashboard ตามโหมดที่เลือก
      if(InpShowDashboard)
      {
         if(InpDashboardType == DASH_BOTH || InpDashboardType == DASH_GUI_ONLY)
         {
            gl_sensor.RenderGuiDashboard(curr_price, curr_atr, InpGuiXOffset, InpGuiYOffset);
         }
         
         if(InpDashboardType == DASH_BOTH || InpDashboardType == DASH_COMMENT_ONLY)
         {
            string dashboard_text = gl_sensor.FormatDashboard(curr_price, curr_atr);
            Comment(dashboard_text);
         }
      }
      
      // 4. แจ้งเตือนเมื่อเกิดความได้เปรียบที่มีนัยสำคัญ (Signal Shift Alert)
      if(InpAlertOnSignal && sig.advantage != gl_last_signal)
      {
         if(sig.advantage == ADVANTAGE_STRONG_BULLISH || sig.advantage == ADVANTAGE_STRONG_BEARISH)
         {
            string alert_msg = StringFormat("📡 [XAUUSD Sensor] %s!\nNet Edge: %+.1f%% | UP Wins: %d/15 | Price: %.2f",
                                            sig.signal_badge, sig.mean_edge_pct, sig.up_wins, curr_price);
            Alert(alert_msg);
            
            if(InpPushNotification)
            {
               SendNotification(alert_msg);
            }
         }
         gl_last_signal = sig.advantage;
      }
      
      // 5. บันทึกข้อมูลลงไฟล์ CSV สำหรับวิเคราะห์ทางสถิติ
      if(InpLogToCSV && gl_file_handle != INVALID_HANDLE)
      {
         float probs[30];
         gl_sensor.GetRawArray(probs);
         
         int dist_v = 0, horiz_v = 0;
         gl_sensor.CheckMonotonicity(dist_v, horiz_v);
         
         string line = TimeToString(current_bar_time, TIME_DATE | TIME_SECONDS) + "," +
                       DoubleToString(curr_price, 2) + "," +
                       DoubleToString(curr_atr, 2);
                       
         for(int i=0; i<30; i++)
         {
            line += "," + DoubleToString(probs[i], 4);
         }
         
         line += "," + sig.signal_name + "," +
                 DoubleToString(sig.mean_edge_pct, 2) + "," +
                 DoubleToString(sig.skew_1_60_pct, 2) + "," +
                 IntegerToString(sig.up_wins) + "," +
                 IntegerToString(sig.down_wins) + "," +
                 IntegerToString(dist_v) + "," +
                 IntegerToString(horiz_v);
                 
         FileWriteString(gl_file_handle, line + "\n");
         FileFlush(gl_file_handle);
      }
   }
}

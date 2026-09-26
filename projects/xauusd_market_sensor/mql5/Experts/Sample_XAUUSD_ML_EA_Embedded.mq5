//+------------------------------------------------------------------+
//|                                Sample_XAUUSD_ML_EA_Embedded.mq5  |
//|                                     Copyright 2026, BlamzKunG    |
//|                                  https://github.com/BlamzKunG     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, BlamzKunG"
#property link      "https://github.com/BlamzKunG"
#property version   "1.05"
#property strict

//+------------------------------------------------------------------+
//| Embedded Resource Directive:                                     |
//| ฝังไฟล์โมเดล ONNX ลงในไฟล์ .ex5 โดยตรง                           |
//| * ตอนคอมไพล์ใน MetaEditor ไฟล์ต้องอยู่ใน MQL5\Files\            |
//| * หลังคอมไพล์เสร็จ ไฟล์ .ex5 จะเป็น Standalone ไม่ต้องพกพาโมเดลแยก |
//+------------------------------------------------------------------+
#resource "\\Files\\xauusd_upside.onnx"   as uchar ExtModelUp[]
#resource "\\Files\\xauusd_downside.onnx" as uchar ExtModelDown[]

// เรียกใช้ Header โมเดล AI และ Trade Library มาตรฐานของ MQL5
#include <Trade\Trade.mqh>
#include <XAUUSD_ML.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== ML Filter & Target Settings ==="
input double InpMinUpsideATR   = 1.0;            // ขั้นต่ำ Upside ATR สำหรับเปิด BUY
input double InpMinDownsideATR = 1.0;            // ขั้นต่ำ Downside ATR สำหรับเปิด SELL
input bool   InpDominantBias   = true;           // ต้องให้ฝั่งที่จะเข้ามีระยะไกลกว่าอีกฝั่งเท่านั้น

input group "=== EMA Trend Filter Settings ==="
input bool            InpUseEMAFilter = true;           // เปิดใช้งาน EMA Trend Filter
input int             InpEMAPeriod    = 200;            // ค่า Period ของ EMA (เช่น 200)
input ENUM_TIMEFRAMES InpEMATimeframe = PERIOD_CURRENT; // Timeframe สำหรับคำนวณ EMA

input group "=== Order & Risk Management ==="
input double InpFixedLot       = 0.01;           // ขนาด Lot Size
input bool   InpUseLineTargets = true;           // ใช้ TP/SL ตามระดับเส้นโมเดล AI (TP เส้นเป้าหมาย / SL เส้นฝั่งตรงข้าม)
input double InpDefaultSL_Pts  = 300.0;          // SL สำรอง (Points) หากระยะเส้นแคบเกินไป
input double InpDefaultTP_Pts  = 500.0;          // TP สำรอง (Points) หากระยะเส้นแคบเกินไป
input ulong  InpMagicNumber    = 123456;         // Magic Number สำหรับแยกออเดอร์
input bool   InpOneTradeOnly   = true;           // ถือออเดอร์ทีละ 1 ไม้เท่านั้น (ไม่เปิดซ้ำ)

input group "=== Trailing Stop Settings ==="
input bool   InpUseTrailing    = false;          // เปิดใช้งาน Trailing Stop (ตั้ง false เพื่อให้ราคาชนเส้น TP/SL ตามโมเดล)
input double InpTrailingStart  = 250.0;          // กำไรขั้นต่ำที่จะเริ่มขยับ SL (Points)
input double InpTrailingStop   = 150.0;          // ระยะห่าง SL จากราคาปัจจุบัน (Points)
input double InpTrailingStep   = 50.0;           // ขยับทีละกี่ Points (Step)

input group "=== Chart Visual Settings ==="
input bool   InpDrawLines      = true;           // แสดงเส้นระดับราคาบนกราฟ
input color  InpColorUpside    = clrDodgerBlue;  // สีเส้น Expected Upside
input color  InpColorDownside  = clrCrimson;     // สีเส้น Expected Downside
input int    InpLineWidth      = 1;              // ความหนาเส้น
input ENUM_LINE_STYLE InpLineStyle = STYLE_DASH; // รูปแบบเส้น

// ชื่อ Object บนกราฟ
#define OBJ_PREFIX         "ML_EA_"
#define OBJ_LINE_UPSIDE    "ML_EA_Upside_Target"
#define OBJ_LINE_DOWNSIDE  "ML_EA_Downside_Target"

// ตัวแปร Global
CXAUUSD_ML gl_ml;
CTrade     gl_trade;
int        gl_ema_handle = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Helper: ตรวจสอบจำนวน Position ที่ EA นี้เปิดอยู่                 |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Helper: ระบบจัดการ Trailing Stop                                 |
//+------------------------------------------------------------------+
void ApplyTrailingStop()
{
   if(!InpUseTrailing) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      ulong  ticket       = PositionGetInteger(POSITION_TICKET);
      long   pos_type     = PositionGetInteger(POSITION_TYPE);
      double open_price   = PositionGetDouble(POSITION_PRICE_OPEN);
      double current_sl   = PositionGetDouble(POSITION_SL);
      double current_tp   = PositionGetDouble(POSITION_TP);

      // Trailing สำหรับฝั่ง BUY
      if(pos_type == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if((bid - open_price) >= (InpTrailingStart * _Point))
         {
            double new_sl = NormalizeDouble(bid - (InpTrailingStop * _Point), _Digits);
            if(new_sl > current_sl + (InpTrailingStep * _Point))
            {
               if(gl_trade.PositionModify(ticket, new_sl, current_tp))
                  PrintFormat("🔄 [TRAILING BUY] อัปเดต SL ไม้ #%d สำเร็จ -> %.2f", ticket, new_sl);
            }
         }
      }
      // Trailing สำหรับฝั่ง SELL
      else if(pos_type == POSITION_TYPE_SELL)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if((open_price - ask) >= (InpTrailingStart * _Point))
         {
            double new_sl = NormalizeDouble(ask + (InpTrailingStop * _Point), _Digits);
            if(current_sl == 0.0 || new_sl < current_sl - (InpTrailingStep * _Point))
            {
               if(gl_trade.PositionModify(ticket, new_sl, current_tp))
                  PrintFormat("🔄 [TRAILING SELL] อัปเดต SL ไม้ #%d สำเร็จ -> %.2f", ticket, new_sl);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: สร้างหรือขยับเส้น HLine บนชาร์ต                          |
//+------------------------------------------------------------------+
void UpdateHLine(const string name, double price, color clr, string desc)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_STYLE, InpLineStyle);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, InpLineWidth);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   else
   {
      ObjectMove(0, name, 0, 0, price);
   }
   ObjectSetString(0, name, OBJPROP_TEXT, desc);
}

//+------------------------------------------------------------------+
//| Helper: ลบเส้น Object ทั้งหมดที่ EA สร้าง                       |
//+------------------------------------------------------------------+
void DeleteChartObjects()
{
   ObjectsDeleteAll(0, OBJ_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("🚀 [ML_EA Embedded] Initializing Embedded ML Engine for XAUUSD...");
   
   gl_trade.SetExpertMagicNumber(InpMagicNumber);
   gl_trade.SetDeviationInPoints(20);
   gl_trade.SetTypeFillingBySymbol(_Symbol);

   // สร้าง Handle สำหรับ EMA Trend Filter
   if(InpUseEMAFilter)
   {
      gl_ema_handle = iMA(_Symbol, InpEMATimeframe, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(gl_ema_handle == INVALID_HANDLE)
      {
         Print("❌ [ML_EA Embedded] ไม่สามารถสร้าง Handle สำหรับ EMA Trend Filter ได้!");
         return INIT_FAILED;
      }
      PrintFormat("📈 [ML_EA Embedded] เปิดใช้งาน EMA Trend Filter (%d) สำเร็จ", InpEMAPeriod);
   }

   // ตรวจสอบขนาดของ Embedded Buffer
   if(ArraySize(ExtModelUp) == 0 || ArraySize(ExtModelDown) == 0)
   {
      string msg = "❌ [ML_EA Embedded] ไฟล์ Resource ไม่ถูกต้องหรือว่างเปล่า!";
      Print(msg);
      Alert(msg);
      return INIT_FAILED;
   }
   
   // โหลดโมเดลตรงจาก Resource Memory Buffer
   if(!gl_ml.InitFromBuffer(ExtModelUp, ExtModelDown, _Symbol, PERIOD_M1))
   {
      string msg = "❌ [ML_EA Embedded] ล้มเหลวในการเริ่มต้นโมเดลจาก Embedded Memory Buffer!";
      Print(msg);
      Alert(msg);
      return INIT_FAILED;
   }
   
   Print("✅ [ML_EA Embedded] โหลดโมเดล AI ในตัวสำเร็จ 100% (Standalone พร้อมใช้งาน)!");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   gl_ml.Release();
   if(gl_ema_handle != INVALID_HANDLE)
   {
      IndicatorRelease(gl_ema_handle);
      gl_ema_handle = INVALID_HANDLE;
   }
   DeleteChartObjects();
   Comment("");
   Print("🚪 [ML_EA Embedded] ปิดระบบและลบเส้นแสดงผลเรียบร้อย");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // ตรวจสอบและขยับ Trailing Stop ทุกๆ Tick เพื่อความแม่นยำ
   ApplyTrailingStop();

   // รันการคำนวณโมเดลและการออกออเดอร์เฉพาะแท่งใหม่ (New Bar)
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;
   
   double exp_high = 0, exp_low = 0, up_atr = 0, down_atr = 0;
   
   if(gl_ml.GetExpectedPriceTargets(exp_high, exp_low, up_atr, down_atr))
   {
      double curr_close = iClose(_Symbol, PERIOD_CURRENT, 0);
      double dist_upside   = MathAbs(exp_high - curr_close);
      double dist_downside = MathAbs(curr_close - exp_low);
      
      bool is_upside_dominant   = (dist_upside > dist_downside);
      bool is_downside_dominant = (dist_downside > dist_upside);

      string distance_bias_text = "";
      if(is_upside_dominant)
      {
         double diff = dist_upside - dist_downside;
         distance_bias_text = StringFormat("🟢 UPSIDE ไกลกว่า (+%.2f pts | +%.2f ATR)", diff, (up_atr - down_atr));
      }
      else if(is_downside_dominant)
      {
         double diff = dist_downside - dist_upside;
         distance_bias_text = StringFormat("🔴 DOWNSIDE ไกลกว่า (+%.2f pts | +%.2f ATR)", diff, (down_atr - up_atr));
      }
      else
      {
         distance_bias_text = "⚪ ทั้งสองฝั่งมีระยะห่างเท่ากัน";
      }

      // คำนวณค่า EMA Trend Filter
      double ema_buf[1];
      double ema_val = 0.0;
      bool ema_buy_ok  = true;
      bool ema_sell_ok = true;
      string ema_desc  = "ปิดใช้งาน (Disabled)";

      if(InpUseEMAFilter && gl_ema_handle != INVALID_HANDLE)
      {
         if(CopyBuffer(gl_ema_handle, 0, 0, 1, ema_buf) > 0)
         {
            ema_val = ema_buf[0];
            ema_buy_ok  = (curr_close > ema_val);
            ema_sell_ok = (curr_close < ema_val);
            ema_desc = ema_buy_ok ? StringFormat("🟢 BULLISH (Close %.2f > EMA %.2f)", curr_close, ema_val) :
                                    StringFormat("🔴 BEARISH (Close %.2f < EMA %.2f)", curr_close, ema_val);
         }
         else
         {
            ema_buy_ok  = false;
            ema_sell_ok = false;
            ema_desc = "รอข้อมูล EMA...";
         }
      }

      // วาดหรืออัปเดตเส้นบนชาร์ต
      if(InpDrawLines)
      {
         UpdateHLine(OBJ_LINE_UPSIDE, exp_high, InpColorUpside, 
                     StringFormat("ML Upside Target: %.2f (+%.2f ATR)", exp_high, up_atr));
         UpdateHLine(OBJ_LINE_DOWNSIDE, exp_low, InpColorDownside, 
                     StringFormat("ML Downside Target: %.2f (-%.2f ATR)", exp_low, down_atr));
         ChartRedraw(0);
      }

      // อัปเดตข้อความบนหน้าจอกราฟ
      string comment_text = StringFormat(
         "=== 🤖 XAUUSD AI EXCURSION PREDICTOR (Embedded) ===\n" +
         "Current Price: %.2f\n" +
         "-----------------------------------------\n" +
         "📈 Expected Upside:   +%.2f ATR (High: %.2f | Dist: %.2f pts)\n" +
         "📉 Expected Downside: -%.2f ATR (Low:  %.2f | Dist: %.2f pts)\n" +
         "🎯 Dominant Side:     %s\n" +
         "📊 EMA Trend (%d):    %s\n" +
         "-----------------------------------------\n" +
         "BUY Signal:  %s (Need >= %.2f ATR & %s)\n" +
         "SELL Signal: %s (Need >= %.2f ATR & %s)\n" +
         "Active Position(s): %d",
         curr_close,
         up_atr, exp_high, dist_upside,
         down_atr, exp_low, dist_downside,
         distance_bias_text,
         InpEMAPeriod,
         ema_desc,
         (up_atr >= InpMinUpsideATR && is_upside_dominant && ema_buy_ok) ? "✅ PASS (READY)" : "⛔ SKIP", InpMinUpsideATR, (InpUseEMAFilter ? "Above EMA" : "No EMA"),
         (down_atr >= InpMinDownsideATR && is_downside_dominant && ema_sell_ok) ? "✅ PASS (READY)" : "⛔ SKIP", InpMinDownsideATR, (InpUseEMAFilter ? "Below EMA" : "No EMA"),
         CountOpenPositions()
      );
      Comment(comment_text);

      // ==========================================
      // 🚀 LOGIC การส่ง Order ตามระดับเส้นโมเดล AI
      // ==========================================
      if(InpOneTradeOnly && CountOpenPositions() > 0)
         return;

      double stops_level_pts = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double min_stop_dist   = stops_level_pts * _Point;

      // 1. ตรวจสอบเงื่อนไขฝั่ง BUY: Upside สูงกว่า + ATR ผ่านเกณฑ์ + กรองเทรนด์ EMA ขาขึ้น
      bool buy_filter_ok = (up_atr >= InpMinUpsideATR);
      bool buy_bias_ok   = (!InpDominantBias || is_upside_dominant);

      if(buy_filter_ok && buy_bias_ok && ema_buy_ok)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double tp  = 0.0;
         double sl  = 0.0;

         // Logic: เส้น Upside สูงกว่า -> TP = เส้น Upside (exp_high) / SL = เส้น Downside (exp_low)
         if(InpUseLineTargets)
         {
            tp = exp_high;
            sl = exp_low;

            // ตรวจสอบ Stop Level กับโบรกเกอร์เพื่อป้องกัน Order Error
            if((tp - ask) < min_stop_dist || tp <= ask)
               tp = (InpDefaultTP_Pts > 0) ? NormalizeDouble(ask + MathMax(InpDefaultTP_Pts * _Point, min_stop_dist + _Point), _Digits) : 0.0;

            if((ask - sl) < min_stop_dist || sl >= ask)
               sl = (InpDefaultSL_Pts > 0) ? NormalizeDouble(ask - MathMax(InpDefaultSL_Pts * _Point, min_stop_dist + _Point), _Digits) : 0.0;
         }
         else
         {
            if(InpDefaultTP_Pts > 0) tp = NormalizeDouble(ask + (InpDefaultTP_Pts * _Point), _Digits);
            if(InpDefaultSL_Pts > 0) sl = NormalizeDouble(ask - (InpDefaultSL_Pts * _Point), _Digits);
         }

         tp = NormalizeDouble(tp, _Digits);
         sl = NormalizeDouble(sl, _Digits);

         if(gl_trade.Buy(InpFixedLot, _Symbol, ask, sl, tp, "ML_AI_Buy"))
         {
            PrintFormat("✅ [BUY EXECUTED] Ask: %.2f | TP(Upside Line): %.2f | SL(Downside Line): %.2f | Upside: %.2f ATR", ask, tp, sl, up_atr);
            return;
         }
         else
         {
            PrintFormat("❌ [BUY ERROR] Code: %d", gl_trade.ResultRetcode());
         }
      }

      // 2. ตรวจสอบเงื่อนไขฝั่ง SELL: Downside สูงกว่า + ATR ผ่านเกณฑ์ + กรองเทรนด์ EMA ขาลง
      bool sell_filter_ok = (down_atr >= InpMinDownsideATR);
      bool sell_bias_ok   = (!InpDominantBias || is_downside_dominant);

      if(sell_filter_ok && sell_bias_ok && ema_sell_ok)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double tp  = 0.0;
         double sl  = 0.0;

         // Logic: เส้น Downside สูงกว่า -> TP = เส้น Downside (exp_low) / SL = เส้น Upside (exp_high)
         if(InpUseLineTargets)
         {
            tp = exp_low;
            sl = exp_high;

            // ตรวจสอบ Stop Level กับโบรกเกอร์เพื่อป้องกัน Order Error
            if((bid - tp) < min_stop_dist || tp >= bid)
               tp = (InpDefaultTP_Pts > 0) ? NormalizeDouble(bid - MathMax(InpDefaultTP_Pts * _Point, min_stop_dist + _Point), _Digits) : 0.0;

            if((sl - bid) < min_stop_dist || sl <= bid)
               sl = (InpDefaultSL_Pts > 0) ? NormalizeDouble(bid + MathMax(InpDefaultSL_Pts * _Point, min_stop_dist + _Point), _Digits) : 0.0;
         }
         else
         {
            if(InpDefaultTP_Pts > 0) tp = NormalizeDouble(bid - (InpDefaultTP_Pts * _Point), _Digits);
            if(InpDefaultSL_Pts > 0) sl = NormalizeDouble(bid + (InpDefaultSL_Pts * _Point), _Digits);
         }

         tp = NormalizeDouble(tp, _Digits);
         sl = NormalizeDouble(sl, _Digits);

         if(gl_trade.Sell(InpFixedLot, _Symbol, bid, sl, tp, "ML_AI_Sell"))
         {
            PrintFormat("✅ [SELL EXECUTED] Bid: %.2f | TP(Downside Line): %.2f | SL(Upside Line): %.2f | Downside: %.2f ATR", bid, tp, sl, down_atr);
            return;
         }
         else
         {
            PrintFormat("❌ [SELL ERROR] Code: %d", gl_trade.ResultRetcode());
         }
      }
   }
}

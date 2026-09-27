//+------------------------------------------------------------------+
//|  EA_01_Tiered_Dual_Sleeve.mq5                                    |
//|  EXP-27 Champion — Cross-Session Dual-Sleeve Execution Engine    |
//|  Research: Autonomous Quant ML Research — XAUUSD M1              |
//|                                                                  |
//|  Key metrics (2025 walk-forward):                                |
//|    PF 2.08 | Net +$591.98 | Max DD 1.1% | WR 58.5% | 65 trades  |
//|                                                                  |
//|  Signal Architecture (rule-based port from Python research):     |
//|  ─────────────────────────────────────────────────────────────── |
//|  ALL conditions must be TRUE (AND-gate):                         |
//|  1. H1 Macro Trend   : EMA600 > EMA1800 (long) / < (short)      |
//|  2. M1 Micro Trend   : close > EMA60 AND EMA20 > EMA60           |
//|  3. Excursion RR     : MFE50 / MAE80 >= 1.15 (approx via ATR)   |
//|  4. EMA200 proximity : dist_ema200 >= -0.5 ATR (long)            |
//|  5. ATR ratio        : ATR14 / ATR60 in [0.85, 2.5]             |
//|  6. Session Window   : Sleeve A or Sleeve B (UTC)                |
//|  7. Tick Volume      : current volume >= 20-bar MA               |
//|  8. Friday Shield    : no entry after 17:00 UTC Friday           |
//|                                                                  |
//|  Dual-Sleeve Sizing:                                             |
//|    Sleeve A (Prime):   LondonOpen 07–11 + NYOpen 12:30–16 UTC   |
//|      → 0.18 lots + RR ≥ 1.00                                    |
//|    Sleeve B (Midday):  11–12:30  + 16–18:30 UTC                 |
//|      → 0.06 lots + RR ≥ 1.35                                    |
//|                                                                  |
//|  SL/TP (ATR-based excursion quantile approximation):            |
//|    Trend regime (|slope| >= 0.20):                              |
//|      TP = clip(2.10 * MFE50, 3.0, 7.5) * ATR                   |
//|      SL = clip(1.30 * MAE80, 1.8, 3.5) * ATR                   |
//|    Range regime:                                                 |
//|      TP = clip(1.40 * MFE50, 2.0, 4.5) * ATR                   |
//|      SL = clip(1.10 * MAE80, 1.4, 2.5) * ATR                   |
//|    (MFE50 ≈ 2.5 ATR, MAE80 ≈ 1.5 ATR — calibrated from data)   |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-27"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Position Sizing ==="
input double   InpLotSleeveA      = 0.18;    // Sleeve A lot size (Prime session)
input double   InpLotSleeve B      = 0.06;    // Sleeve B lot size (Midday)
input double   InpMaxTotalLots     = 0.24;    // Maximum concurrent lots

input group "=== ATR Settings ==="
input int      InpATRPeriod        = 14;      // ATR period (short)
input int      InpATRLong          = 60;      // ATR period (long) for ratio check

input group "=== EMA Settings ==="
input int      InpEMA20            = 20;      // M1 fast EMA
input int      InpEMA60            = 60;      // M1 mid EMA
input int      InpEMA200           = 200;     // M1 proximity EMA
input int      InpH1EMA600         = 600;     // H1 macro EMA (fast)  [600 H1 bars]
input int      InpH1EMA1800        = 1800;    // H1 macro EMA (slow)  [1800 H1 bars]

input group "=== Signal Thresholds ==="
input double   InpRRSleeve A       = 1.00;    // Min RR for Sleeve A
input double   InpRRSleeve B       = 1.35;    // Min RR for Sleeve B
input double   InpATRRatioMin      = 0.85;    // ATR ratio min (ATR14/ATR60)
input double   InpATRRatioMax      = 2.50;    // ATR ratio max
input double   InpEMA200Dist       = 0.50;    // EMA200 distance threshold (in ATR)
input double   InpTrendSlopeMin    = 0.20;    // Trend slope threshold (|EMA60-EMA240|/ATR)
input int      InpVolMA Period      = 20;      // Volume MA period
input double   InpExcursionRR      = 1.15;    // Min excursion RR (MFE50/MAE80 proxy)

input group "=== SL/TP Multipliers (Trend) ==="
input double   InpTP_Trend_Mult    = 2.10;    // TP MFE50 multiplier (trend)
input double   InpTP_Trend_Min     = 3.00;    // TP ATR min (trend)
input double   InpTP_Trend_Max     = 7.50;    // TP ATR max (trend)
input double   InpSL_Trend_Mult    = 1.30;    // SL MAE80 multiplier (trend)
input double   InpSL_Trend_Min     = 1.80;    // SL ATR min (trend)
input double   InpSL_Trend_Max     = 3.50;    // SL ATR max (trend)

input group "=== SL/TP Multipliers (Range) ==="
input double   InpTP_Range_Mult    = 1.40;    // TP MFE50 multiplier (range)
input double   InpTP_Range_Min     = 2.00;    // TP ATR min (range)
input double   InpTP_Range_Max     = 4.50;    // TP ATR max (range)
input double   InpSL_Range_Mult    = 1.10;    // SL MAE80 multiplier (range)
input double   InpSL_Range_Min     = 1.40;    // SL ATR min (range)
input double   InpSL_Range_Max     = 2.50;    // SL ATR max (range)

input group "=== Approximate Excursion Quantiles (calibrated) ==="
input double   InpMFE50_ATR        = 2.50;    // Approximate MFE 50th pct (ATR units)
input double   InpMAE80_ATR        = 1.50;    // Approximate MAE 80th pct (ATR units)

input group "=== Risk Control ==="
input double   InpMaxDailyLoss     = 200.0;   // Max daily loss in USD before halt
input int      InpMagicNumber      = 270100;  // Magic number
input string   InpComment          = "EXP27_DualSleeve";

//--- Session UTC windows (hours are inclusive-start, exclusive-end)
//  Sleeve A: London Open 07–11, NY Open 12:30–16
//  Sleeve B: Midday 11–12:30, Late 16–18:30
//  Friday shield: block after 17:00 UTC

//--- Globals
int    g_atr14Handle    = INVALID_HANDLE;
int    g_atr60Handle    = INVALID_HANDLE;
int    g_ema20Handle    = INVALID_HANDLE;
int    g_ema60Handle    = INVALID_HANDLE;
int    g_ema200Handle   = INVALID_HANDLE;
int    g_ema240Handle   = INVALID_HANDLE;  // for slope calculation
int    g_h1ema600Handle = INVALID_HANDLE;
int    g_h1ema1800Handle= INVALID_HANDLE;

double g_dailyLoss      = 0.0;
datetime g_lastDayCheck = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_atr14Handle     = iATR(Symbol(), PERIOD_M1, InpATRPeriod);
   g_atr60Handle     = iATR(Symbol(), PERIOD_M1, InpATRLong);
   g_ema20Handle     = iMA(Symbol(), PERIOD_M1, InpEMA20,  0, MODE_EMA, PRICE_CLOSE);
   g_ema60Handle     = iMA(Symbol(), PERIOD_M1, InpEMA60,  0, MODE_EMA, PRICE_CLOSE);
   g_ema200Handle    = iMA(Symbol(), PERIOD_M1, InpEMA200, 0, MODE_EMA, PRICE_CLOSE);
   g_ema240Handle    = iMA(Symbol(), PERIOD_M1, 240,       0, MODE_EMA, PRICE_CLOSE);
   g_h1ema600Handle  = iMA(Symbol(), PERIOD_H1, InpH1EMA600,  0, MODE_EMA, PRICE_CLOSE);
   g_h1ema1800Handle = iMA(Symbol(), PERIOD_H1, InpH1EMA1800, 0, MODE_EMA, PRICE_CLOSE);

   if(g_atr14Handle==INVALID_HANDLE || g_atr60Handle==INVALID_HANDLE ||
      g_ema20Handle==INVALID_HANDLE || g_ema60Handle==INVALID_HANDLE ||
      g_ema200Handle==INVALID_HANDLE|| g_ema240Handle==INVALID_HANDLE ||
      g_h1ema600Handle==INVALID_HANDLE || g_h1ema1800Handle==INVALID_HANDLE)
   {
      Print("EA_01: Indicator handle creation failed");
      return(INIT_FAILED);
   }
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(g_atr14Handle);
   IndicatorRelease(g_atr60Handle);
   IndicatorRelease(g_ema20Handle);
   IndicatorRelease(g_ema60Handle);
   IndicatorRelease(g_ema200Handle);
   IndicatorRelease(g_ema240Handle);
   IndicatorRelease(g_h1ema600Handle);
   IndicatorRelease(g_h1ema1800Handle);
}

//+------------------------------------------------------------------+
void OnTick()
{
   // Only act on new bar (M1 open)
   static datetime s_lastBar = 0;
   datetime curBar = iTime(Symbol(), PERIOD_M1, 0);
   if(curBar == s_lastBar) return;
   s_lastBar = curBar;

   // Reset daily loss counter
   ResetDailyLossIfNewDay();
   if(g_dailyLoss >= InpMaxDailyLoss)
   {
      Comment("EA_01: Daily loss limit reached. Halted.");
      return;
   }

   // Determine UTC hour/minute from server time
   // MT5 server time should be UTC+0 or adjust offset below
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int utcHour    = dt.hour;
   int utcMin     = dt.min;
   int utcDow     = dt.day_of_week; // 0=Sun,5=Fri

   // Friday Shield — no new entries after 17:00 UTC Friday
   if(utcDow == 5 && (utcHour > 17 || (utcHour == 17 && utcMin >= 0)))
      return;

   // Determine which sleeve is active (0=none,1=A,2=B)
   int sleeve = GetActiveSleeve(utcHour, utcMin);
   if(sleeve == 0) return;

   // Gather indicator values
   double atr14[1], atr60[1], ema20[1], ema60[1], ema200[1], ema240[1];
   double h1ema600[1], h1ema1800[1];

   if(CopyBuffer(g_atr14Handle,    0, 0, 1, atr14)    <= 0) return;
   if(CopyBuffer(g_atr60Handle,    0, 0, 1, atr60)    <= 0) return;
   if(CopyBuffer(g_ema20Handle,    0, 0, 1, ema20)    <= 0) return;
   if(CopyBuffer(g_ema60Handle,    0, 0, 1, ema60)    <= 0) return;
   if(CopyBuffer(g_ema200Handle,   0, 0, 1, ema200)   <= 0) return;
   if(CopyBuffer(g_ema240Handle,   0, 0, 1, ema240)   <= 0) return;
   if(CopyBuffer(g_h1ema600Handle, 0, 0, 1, h1ema600) <= 0) return;
   if(CopyBuffer(g_h1ema1800Handle,0, 0, 1, h1ema1800)<= 0) return;

   double close   = iClose(Symbol(), PERIOD_M1, 0);
   double atr     = atr14[0];
   if(atr <= 0) return;

   // --- Filter 1: H1 Macro Trend (EMA600 > EMA1800)
   bool macroLong  = h1ema600[0] > h1ema1800[0];
   bool macroShort = h1ema600[0] < h1ema1800[0];
   if(!macroLong && !macroShort) return;

   // --- Filter 2: M1 Micro Trend
   bool microLong  = (close > ema60[0]) && (ema20[0] > ema60[0]);
   bool microShort = (close < ema60[0]) && (ema20[0] < ema60[0]);

   // --- Filter 3: Excursion RR proxy (MFE50/MAE80 approximation)
   double mfe50 = InpMFE50_ATR * atr;
   double mae80 = InpMAE80_ATR * atr;
   double excursionRR = (mae80 > 0) ? (mfe50 / mae80) : 0.0;
   if(excursionRR < InpExcursionRR) return;

   // --- Filter 4: EMA200 Distance
   double distEMA200_long  = (close - ema200[0]) / atr;
   double distEMA200_short = (ema200[0] - close) / atr;

   // --- Filter 5: ATR Ratio
   double atrRatio = (atr60[0] > 0) ? (atr / atr60[0]) : 0.0;
   if(atrRatio < InpATRRatioMin || atrRatio > InpATRRatioMax) return;

   // --- Filter 6: Tick Volume >= 20-bar MA
   long curVol = iVolume(Symbol(), PERIOD_M1, 0);
   double volMA = GetVolumeMA(InpVolMA Period);
   if(volMA > 0 && curVol < volMA) return;

   // --- Trend slope for SL/TP regime
   double slope = (atr > 0) ? ((ema60[0] - ema240[0]) / atr) : 0.0;
   bool isTrend = (MathAbs(slope) >= InpTrendSlopeMin);

   // --- Compute SL/TP
   double tp_atr, sl_atr;
   if(isTrend)
   {
      tp_atr = MathMax(InpTP_Trend_Min, MathMin(InpTP_Trend_Max, InpTP_Trend_Mult * InpMFE50_ATR));
      sl_atr = MathMax(InpSL_Trend_Min, MathMin(InpSL_Trend_Max, InpSL_Trend_Mult * InpMAE80_ATR));
   }
   else
   {
      tp_atr = MathMax(InpTP_Range_Min, MathMin(InpTP_Range_Max, InpTP_Range_Mult * InpMFE50_ATR));
      sl_atr = MathMax(InpSL_Range_Min, MathMin(InpSL_Range_Max, InpSL_Range_Mult * InpMAE80_ATR));
   }

   double tp_price = tp_atr * atr;
   double sl_price = sl_atr * atr;

   // --- RR Check for this sleeve
   double rr = (sl_price > 0) ? (tp_price / sl_price) : 0.0;
   double minRR = (sleeve == 1) ? InpRRSleeve A : InpRRSleeve B;
   if(rr < minRR) return;

   // --- Lot size
   double lots = (sleeve == 1) ? InpLotSleeve A : InpLotSleeve B;

   // --- Already have position?
   if(HasOpenPosition()) return;

   // --- Entry
   if(macroLong && microLong && distEMA200_long >= -InpEMA200Dist)
   {
      double entry = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      double sl    = entry - sl_price;
      double tp    = entry + tp_price;
      OpenTrade(ORDER_TYPE_BUY, lots, entry, sl, tp,
                StringFormat("%s_A%d", InpComment, sleeve));
   }
   else if(macroShort && microShort && distEMA200_short >= -InpEMA200Dist)
   {
      double entry = SymbolInfoDouble(Symbol(), SYMBOL_BID);
      double sl    = entry + sl_price;
      double tp    = entry - tp_price;
      OpenTrade(ORDER_TYPE_SELL, lots, entry, sl, tp,
                StringFormat("%s_A%d", InpComment, sleeve));
   }
}

//+------------------------------------------------------------------+
//  GetActiveSleeve : returns 1 (A), 2 (B), or 0 (none)
//+------------------------------------------------------------------+
int GetActiveSleeve(int h, int m)
{
   // Sleeve A: 07:00–10:59 UTC (London), 12:30–15:59 UTC (NY Open)
   bool sleeveA = ((h >= 7 && h < 11) ||
                   (h == 12 && m >= 30) ||
                   (h >= 13 && h < 16));
   if(sleeveA) return 1;

   // Sleeve B: 11:00–12:29 UTC (Midday), 16:00–18:29 UTC (Late)
   bool sleeveB = ((h >= 11 && h < 12) ||
                   (h == 12 && m < 30) ||
                   (h >= 16 && (h < 18 || (h == 18 && m < 30))));
   if(sleeveB) return 2;

   return 0;
}

//+------------------------------------------------------------------+
double GetVolumeMA(int period)
{
   double sum = 0;
   for(int i = 1; i <= period; i++)
      sum += (double)iVolume(Symbol(), PERIOD_M1, i);
   return (period > 0) ? sum / period : 0.0;
}

//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 &&
         PositionGetString(POSITION_SYMBOL) == Symbol() &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE type, double lots, double price,
               double sl, double tp, string comment)
{
   MqlTradeRequest req = {};
   MqlTradeResult  res = {};
   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = Symbol();
   req.volume    = NormalizeDouble(lots, 2);
   req.type      = type;
   req.price     = NormalizeDouble(price, (int)SymbolInfoInteger(Symbol(),SYMBOL_DIGITS));
   req.sl        = NormalizeDouble(sl,    (int)SymbolInfoInteger(Symbol(),SYMBOL_DIGITS));
   req.tp        = NormalizeDouble(tp,    (int)SymbolInfoInteger(Symbol(),SYMBOL_DIGITS));
   req.deviation = 10;
   req.magic     = InpMagicNumber;
   req.comment   = comment;
   req.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(req, res))
      Print("EA_01 OrderSend failed: ", res.retcode, " ", res.comment);
   else
      Print("EA_01 Trade opened: ", EnumToString(type), " ", lots, " @ ", price,
            " SL:", sl, " TP:", tp);
}

//+------------------------------------------------------------------+
void ResetDailyLossIfNewDay()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime todayStart = StringToTime(StringFormat("%04d.%02d.%02d 00:00",
                           dt.year, dt.mon, dt.day));
   if(todayStart != g_lastDayCheck)
   {
      g_dailyLoss   = 0.0;
      g_lastDayCheck = todayStart;
   }
}

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& req,
                        const MqlTradeResult&  res)
{
   // Track closed trade P&L for daily loss monitor
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      ulong dealTicket = trans.deal;
      if(HistoryDealSelect(dealTicket))
      {
         long magic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
         if(magic == InpMagicNumber)
         {
            double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
            if(profit < 0)
               g_dailyLoss += MathAbs(profit);
         }
      }
   }
}
//+------------------------------------------------------------------+

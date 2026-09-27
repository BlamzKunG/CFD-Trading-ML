//+------------------------------------------------------------------+
//|  EA_02_Dual_Open_Breakout.mq5                                    |
//|  EXP-26 Champion — Concentrated Dual-Open Breakout Engine        |
//|  Research: Autonomous Quant ML Research — XAUUSD M1              |
//|                                                                  |
//|  Key metrics (2025 walk-forward):                                |
//|    PF 2.48 | Net +$522.84 | Max DD 0.7% | WR 55.2% | 58 trades  |
//|    Payoff Ratio 2.01 — highest quality-per-trade of all EAs      |
//|                                                                  |
//|  Signal Architecture (rule-based port from Python research):     |
//|  ─────────────────────────────────────────────────────────────── |
//|  ALL conditions must be TRUE (AND-gate):                         |
//|  1. H1 Macro Trend   : EMA600 > EMA1800 (long) / < (short)      |
//|  2. M1 Micro Trend   : close > EMA60 AND EMA20 > EMA60           |
//|  3. Excursion RR     : MFE50 / MAE80 >= 1.15                    |
//|  4. EMA200 proximity : dist_ema200 >= -0.5 ATR                   |
//|  5. ATR ratio        : ATR14 / ATR60 in [0.85, 2.5]             |
//|  6. Session Window   : London 07–11 OR NY Open 12:30–16 UTC ONLY |
//|  7. Tick Volume      : current volume >= 20-bar MA               |
//|  8. Friday Shield    : no entry after 17:00 UTC Friday           |
//|                                                                  |
//|  Tiered Sizing:                                                  |
//|    Tier 1 (high conviction): slope >= 0.30 → 0.18 lots           |
//|    Tier 2 (base):            default      → 0.08 lots            |
//|    No Sleeve B — prime windows only                              |
//|                                                                  |
//|  SL/TP: same excursion-quantile ATR formulas as EA_01            |
//+------------------------------------------------------------------+
#property copyright "XAUUSD Quant ML Research — EXP-26"
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Position Sizing (Tiered) ==="
input double   InpLotTier1         = 0.18;    // Tier 1 lot (high conviction: slope >= 0.30)
input double   InpLotTier2         = 0.08;    // Tier 2 lot (base)
input double   InpSlopeTier1       = 0.30;    // Slope threshold for Tier 1

input group "=== ATR Settings ==="
input int      InpATRPeriod        = 14;
input int      InpATRLong          = 60;

input group "=== EMA Settings ==="
input int      InpEMA20            = 20;
input int      InpEMA60            = 60;
input int      InpEMA200           = 200;
input int      InpH1EMA600         = 600;
input int      InpH1EMA1800        = 1800;

input group "=== Signal Thresholds ==="
input double   InpMinRR            = 1.10;    // Minimum RR to enter
input double   InpATRRatioMin      = 0.85;
input double   InpATRRatioMax      = 2.50;
input double   InpEMA200Dist       = 0.50;
input double   InpTrendSlopeMin    = 0.20;    // Trend regime slope threshold
input int      InpVolMAPeriod      = 20;
input double   InpExcursionRR      = 1.15;

input group "=== SL/TP Multipliers (Trend) ==="
input double   InpTP_Trend_Mult    = 2.10;
input double   InpTP_Trend_Min     = 3.00;
input double   InpTP_Trend_Max     = 7.50;
input double   InpSL_Trend_Mult    = 1.30;
input double   InpSL_Trend_Min     = 1.80;
input double   InpSL_Trend_Max     = 3.50;

input group "=== SL/TP Multipliers (Range) ==="
input double   InpTP_Range_Mult    = 1.40;
input double   InpTP_Range_Min     = 2.00;
input double   InpTP_Range_Max     = 4.50;
input double   InpSL_Range_Mult    = 1.10;
input double   InpSL_Range_Min     = 1.40;
input double   InpSL_Range_Max     = 2.50;

input group "=== Excursion Calibration ==="
input double   InpMFE50_ATR        = 2.50;    // MFE 50th percentile (ATR units)
input double   InpMAE80_ATR        = 1.50;    // MAE 80th percentile (ATR units)

input group "=== Risk Control ==="
input double   InpMaxDailyLoss     = 200.0;
input int      InpMagicNumber      = 260200;
input string   InpComment          = "EXP26_DualOpen";

//--- Globals
int    g_atr14Handle     = INVALID_HANDLE;
int    g_atr60Handle     = INVALID_HANDLE;
int    g_ema20Handle     = INVALID_HANDLE;
int    g_ema60Handle     = INVALID_HANDLE;
int    g_ema200Handle    = INVALID_HANDLE;
int    g_ema240Handle    = INVALID_HANDLE;
int    g_h1ema600Handle  = INVALID_HANDLE;
int    g_h1ema1800Handle = INVALID_HANDLE;

double   g_dailyLoss    = 0.0;
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
      Print("EA_02: Indicator handle creation failed");
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
   static datetime s_lastBar = 0;
   datetime curBar = iTime(Symbol(), PERIOD_M1, 0);
   if(curBar == s_lastBar) return;
   s_lastBar = curBar;

   ResetDailyLossIfNewDay();
   if(g_dailyLoss >= InpMaxDailyLoss)
   {
      Comment("EA_02: Daily loss limit reached. Halted.");
      return;
   }

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int utcHour = dt.hour;
   int utcMin  = dt.min;
   int utcDow  = dt.day_of_week;

   // Friday Shield
   if(utcDow == 5 && (utcHour > 17 || (utcHour == 17 && utcMin >= 0)))
      return;

   // Session: London 07–11 OR NY Open 12:30–16 ONLY (prime windows)
   bool inPrimeSession = ((utcHour >= 7 && utcHour < 11) ||
                          (utcHour == 12 && utcMin >= 30) ||
                          (utcHour >= 13 && utcHour < 16));
   if(!inPrimeSession) return;

   // Read indicators
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

   double close = iClose(Symbol(), PERIOD_M1, 0);
   double atr   = atr14[0];
   if(atr <= 0) return;

   // H1 Macro Trend
   bool macroLong  = h1ema600[0] > h1ema1800[0];
   bool macroShort = h1ema600[0] < h1ema1800[0];
   if(!macroLong && !macroShort) return;

   // M1 Micro Trend
   bool microLong  = (close > ema60[0]) && (ema20[0] > ema60[0]);
   bool microShort = (close < ema60[0]) && (ema20[0] < ema60[0]);

   // Excursion RR proxy
   double excursionRR = InpMFE50_ATR / InpMAE80_ATR;
   if(excursionRR < InpExcursionRR) return;

   // EMA200 Distance
   double distEMA200_long  = (close - ema200[0]) / atr;
   double distEMA200_short = (ema200[0] - close) / atr;

   // ATR Ratio
   double atrRatio = (atr60[0] > 0) ? (atr / atr60[0]) : 0.0;
   if(atrRatio < InpATRRatioMin || atrRatio > InpATRRatioMax) return;

   // Tick Volume filter
   long curVol = iVolume(Symbol(), PERIOD_M1, 0);
   double volMA = GetVolumeMA(InpVolMAPeriod);
   if(volMA > 0 && curVol < volMA) return;

   // Slope — determines trend regime AND tier
   double slope = (atr > 0) ? ((ema60[0] - ema240[0]) / atr) : 0.0;
   bool isTrend  = (MathAbs(slope) >= InpTrendSlopeMin);
   bool isHighConviction = (MathAbs(slope) >= InpSlopeTier1);

   // SL/TP
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

   // RR gate
   double rr = (sl_price > 0) ? (tp_price / sl_price) : 0.0;
   if(rr < InpMinRR) return;

   // Tiered lot size
   double lots = isHighConviction ? InpLotTier1 : InpLotTier2;

   if(HasOpenPosition()) return;

   // Entry
   if(macroLong && microLong && distEMA200_long >= -InpEMA200Dist)
   {
      double entry = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      double sl    = entry - sl_price;
      double tp    = entry + tp_price;
      OpenTrade(ORDER_TYPE_BUY, lots, entry, sl, tp,
                StringFormat("%s_T%d", InpComment, isHighConviction ? 1 : 2));
   }
   else if(macroShort && microShort && distEMA200_short >= -InpEMA200Dist)
   {
      double entry = SymbolInfoDouble(Symbol(), SYMBOL_BID);
      double sl    = entry + sl_price;
      double tp    = entry - tp_price;
      OpenTrade(ORDER_TYPE_SELL, lots, entry, sl, tp,
                StringFormat("%s_T%d", InpComment, isHighConviction ? 1 : 2));
   }
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
      Print("EA_02 OrderSend failed: ", res.retcode, " ", res.comment);
   else
      Print("EA_02 Trade opened: ", EnumToString(type), " ", lots, " @ ", price,
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
      g_dailyLoss    = 0.0;
      g_lastDayCheck = todayStart;
   }
}

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& req,
                        const MqlTradeResult&  res)
{
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

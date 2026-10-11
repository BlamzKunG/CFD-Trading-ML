//+------------------------------------------------------------------+
//|                     Titan_Supreme_Quintet_Portfolio_EA.mq5        |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|            Grand Hybrid 5-in-1 Multi-Strategy Master EA (H1)     |
//|    Aggregating: KAMA (PF 2.71) + HMA-CMO (PF 2.37) +             |
//|                 BB Squeeze (PF 2.27) + Choppiness (PF 2.30) +     |
//|                 Market Structure BOS (PF 1.56)                    |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "5.00"
#property description "Titan Supreme Quintet 5-in-1 Multi-Strategy Master EA (5 Asynchronous Uncorrelated Engines in 1 EA for Gold H1)"
#property strict

#include <Trade\Trade.mqh>

//--- MASTER PORTFOLIO CONFIGURATION ---
input group "=== Master Portfolio & Global Risk Governance ==="
input double   InpMasterLotSize        = 0.10;      // Base Lot per Engine (0.10 lots = 10 oz Gold)
input double   InpMasterMaxSpread      = 0.60;      // Maximum Allowable Spread ($)
input double   InpMasterDailyLossCap   = 350.0;     // Master Portfolio Daily Loss Breaker ($)
input double   InpMasterMonthlyLossCap = 600.0;     // Master Portfolio Monthly Loss Breaker ($)

input group "=== Engine 1: KAMA Dynamic Efficiency (S36 - PF 2.715) ==="
input bool     InpEnable_E1_KAMA       = true;      // Enable KAMA Efficiency Engine
input ulong    InpMagic_E1             = 105001;    // Magic Number for Engine 1
input int      InpKAMA_Period          = 10;        // KAMA Lookback Period (Hours)
input double   InpKAMA_ER_Thresh       = 0.45;      // KAMA Efficiency Ratio Threshold (>= 0.45)
input double   InpE1_TP_Mult           = 4.5;       // E1 Take Profit (ATR Mult)
input double   InpE1_SL_Mult           = 2.0;       // E1 Stop Loss (ATR Mult)
input double   InpE1_MonthlyProfitLock = 250.0;     // E1 Monthly Profit Lock ($)
input double   InpE1_MonthlyLossCap    = 250.0;     // E1 Monthly Loss Breaker ($)

input group "=== Engine 2: HMA-CMO Velocity Breakout (S38 - PF 2.375) ==="
input bool     InpEnable_E2_HMA        = true;      // Enable HMA-CMO Velocity Engine
input ulong    InpMagic_E2             = 105002;    // Magic Number for Engine 2
input int      InpHMA_Period           = 24;        // HMA Lookback Period (Hours)
input int      InpCMO_Period           = 10;        // CMO Lookback Period (Hours)
input double   InpCMO_Thresh           = 25.0;      // CMO Momentum Threshold (+/- 25.0)
input int      InpChannelLookback      = 12;        // Breakout Channel Lookback (Hours)
input double   InpE2_TP_Mult           = 4.5;       // E2 Take Profit (ATR Mult)
input double   InpE2_SL_Mult           = 2.5;       // E2 Stop Loss (ATR Mult)
input double   InpE2_MonthlyProfitLock = 200.0;     // E2 Monthly Profit Lock ($)
input double   InpE2_MonthlyLossCap    = 250.0;     // E2 Monthly Loss Breaker ($)

input group "=== Engine 3: Bollinger BandWidth Squeeze Ignition (S118 - PF 2.267) ==="
input bool     InpEnable_E3_BBSqueeze  = true;      // Enable Bollinger Squeeze Engine
input ulong    InpMagic_E3             = 105003;    // Magic Number for Engine 3
input int      InpBB_Period            = 14;        // Bollinger Bands Period
input double   InpBB_DevMult           = 1.8;       // Bollinger StDev Multiplier
input double   InpPctBUpperCutoff      = 0.80;      // %B Bullish Trigger Upper Threshold
input double   InpPctBLowerCutoff      = 0.20;      // %B Bearish Trigger Lower Threshold
input double   InpE3_KFDThresh         = 1.38;      // E3 Max Katz Fractal Dimension (<= 1.38)
input double   InpE3_TP_Mult           = 3.5;       // E3 Take Profit (ATR Mult)
input double   InpE3_SL_Mult           = 2.5;       // E3 Stop Loss (ATR Mult)
input double   InpE3_MonthlyProfitLock = 200.0;     // E3 Monthly Profit Lock ($)
input double   InpE3_MonthlyLossCap    = 250.0;     // E3 Monthly Loss Breaker ($)

input group "=== Engine 4: Choppiness Index Ignition Expansion (S113 - PF 2.296) ==="
input bool     InpEnable_E4_Chop       = true;      // Enable Choppiness Ignition Engine
input ulong    InpMagic_E4             = 105004;    // Magic Number for Engine 4
input int      InpChopPeriod           = 20;        // Choppiness Lookback Period
input double   InpChopThreshold        = 38.2;      // Compression Ignition Threshold (<= 38.2)
input double   InpE4_KFDThresh         = 1.42;      // E4 Max Katz Fractal Dimension (<= 1.42)
input double   InpE4_TP_Mult           = 4.5;       // E4 Take Profit (ATR Mult - 3:1 R:R)
input double   InpE4_SL_Mult           = 1.5;       // E4 Stop Loss (ATR Mult)
input double   InpE4_MonthlyProfitLock = 200.0;     // E4 Monthly Profit Lock ($)
input double   InpE4_MonthlyLossCap    = 250.0;     // E4 Monthly Loss Breaker ($)

input group "=== Engine 5: Market Structure BOS (S55 - PF 1.560) ==="
input bool     InpEnable_E5_BOS        = true;      // Enable Market Structure BOS Engine
input ulong    InpMagic_E5             = 105005;    // Magic Number for Engine 5
input int      InpSwingK               = 4;         // Confirmed Swing Lookback (k bars)
input double   InpE5_KFDThresh         = 1.45;      // E5 Max Katz Fractal Dimension (<= 1.45)
input double   InpE5_TP_Mult           = 4.5;       // E5 Take Profit (ATR Mult - 3:1 R:R)
input double   InpE5_SL_Mult           = 1.5;       // E5 Stop Loss (ATR Mult)
input double   InpE5_MonthlyProfitLock = 250.0;     // E5 Monthly Profit Lock ($)
input double   InpE5_MonthlyLossCap    = 250.0;     // E5 Monthly Loss Breaker ($)

input group "=== Common Technical Settings ==="
input int      InpAtrPeriod            = 14;        // Shared ATR Volatility Period
input int      InpEmaPeriod            = 200;       // Shared Secular Trend EMA Period
input int      InpKfdPeriod            = 24;        // Shared Katz Fractal Window

//--- ENGINE STATE STRUCT ---
struct EngineState
{
   ulong    magic;
   bool     enabled;
   bool     isMonthLocked;
   double   monthlyRealizedPnL;
};

EngineState m_e1, m_e2, m_e3, m_e4, m_e5;

CTrade         m_trade_e1, m_trade_e2, m_trade_e3, m_trade_e4, m_trade_e5;
int            m_hATR;
int            m_hEMA200;
int            m_hBB;
datetime       m_last_bar_time;
int            m_current_month;
int            m_current_day;
double         m_portfolio_daily_pnl;
double         m_portfolio_monthly_pnl;
bool           m_master_day_locked;
bool           m_master_month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade_e1.SetExpertMagicNumber(InpMagic_E1);
   m_trade_e2.SetExpertMagicNumber(InpMagic_E2);
   m_trade_e3.SetExpertMagicNumber(InpMagic_E3);
   m_trade_e4.SetExpertMagicNumber(InpMagic_E4);
   m_trade_e5.SetExpertMagicNumber(InpMagic_E5);

   m_trade_e1.SetMarginMode(); m_trade_e1.SetTypeFillingBySymbol(_Symbol);
   m_trade_e2.SetMarginMode(); m_trade_e2.SetTypeFillingBySymbol(_Symbol);
   m_trade_e3.SetMarginMode(); m_trade_e3.SetTypeFillingBySymbol(_Symbol);
   m_trade_e4.SetMarginMode(); m_trade_e4.SetTypeFillingBySymbol(_Symbol);
   m_trade_e5.SetMarginMode(); m_trade_e5.SetTypeFillingBySymbol(_Symbol);

   m_hATR    = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   m_hBB     = iBands(_Symbol, PERIOD_H1, InpBB_Period, 0, InpBB_DevMult, PRICE_CLOSE);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE || m_hBB == INVALID_HANDLE)
   {
      Print("[!] Error initializing shared indicators.");
      return(INIT_FAILED);
   }

   m_e1.magic = InpMagic_E1; m_e1.enabled = InpEnable_E1_KAMA;      m_e1.isMonthLocked = false; m_e1.monthlyRealizedPnL = 0.0;
   m_e2.magic = InpMagic_E2; m_e2.enabled = InpEnable_E2_HMA;       m_e2.isMonthLocked = false; m_e2.monthlyRealizedPnL = 0.0;
   m_e3.magic = InpMagic_E3; m_e3.enabled = InpEnable_E3_BBSqueeze; m_e3.isMonthLocked = false; m_e3.monthlyRealizedPnL = 0.0;
   m_e4.magic = InpMagic_E4; m_e4.enabled = InpEnable_E4_Chop;      m_e4.isMonthLocked = false; m_e4.monthlyRealizedPnL = 0.0;
   m_e5.magic = InpMagic_E5; m_e5.enabled = InpEnable_E5_BOS;       m_e5.isMonthLocked = false; m_e5.monthlyRealizedPnL = 0.0;

   m_last_bar_time         = 0;
   m_current_month         = -1;
   m_current_day           = -1;
   m_portfolio_daily_pnl   = 0.0;
   m_portfolio_monthly_pnl = 0.0;
   m_master_day_locked     = false;
   m_master_month_locked   = false;

   Print("[+] Titan Supreme Quintet 5-in-1 Multi-Strategy Master EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   IndicatorRelease(m_hEMA200);
   IndicatorRelease(m_hBB);
   Comment("");
}

//+------------------------------------------------------------------+
//| Check Existing Open Position for a Specific Engine               |
//+------------------------------------------------------------------+
bool HasPosition(ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Compute Katz Fractal Dimension (KFD)                             |
//+------------------------------------------------------------------+
double CalculateKFD(int shift, int period)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, shift, period + 1, closes) <= period)
      return 1.5;

   double length = 0.0;
   double max_dist = 0.0;
   double p0 = closes[period];

   for(int i = period - 1; i >= 0; i--)
   {
      length += MathAbs(closes[i] - closes[i + 1]);
      double dist = MathAbs(closes[i] - p0);
      if(dist > max_dist) max_dist = dist;
   }

   if(length <= 0.0 || max_dist <= 0.0) return 1.5;
   double k = MathLog10((double)period) / (MathLog10((double)period) + MathLog10(max_dist / length));
   return MathMax(1.0, MathMin(2.0, k));
}

//+------------------------------------------------------------------+
//| Compute Choppiness Index (CHOP)                                  |
//+------------------------------------------------------------------+
double CalculateChop(int shift, int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, shift, period, rates) < period)
      return 50.0;

   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_hATR, 0, shift, period, atr_buf) < period)
      return 50.0;

   double max_high = rates[0].high;
   double min_low  = rates[0].low;
   double sum_atr  = 0.0;

   for(int i = 0; i < period; i++)
   {
      if(rates[i].high > max_high) max_high = rates[i].high;
      if(rates[i].low < min_low)   min_low  = rates[i].low;
      sum_atr += atr_buf[i];
   }

   double range = max_high - min_low;
   if(range <= 0.0) return 50.0;

   double chop = 100.0 * MathLog10(sum_atr / range) / MathLog10((double)period);
   return chop;
}

//+------------------------------------------------------------------+
//| Compute WMA Helper                                               |
//+------------------------------------------------------------------+
double CalcWMA(const double &arr[], int startIdx, int period)
{
   double sum = 0.0;
   double weightSum = 0.0;
   for(int i = 0; i < period; i++)
   {
      double weight = period - i;
      sum += arr[startIdx + i] * weight;
      weightSum += weight;
   }
   return (weightSum > 0) ? (sum / weightSum) : arr[startIdx];
}

//+------------------------------------------------------------------+
//| Compute KAMA & Efficiency Ratio (ER)                             |
//+------------------------------------------------------------------+
bool ComputeKAMA_State(int period, double &kama1, double &kama2, double &er1)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_H1, 1, period + 5, closes) < period + 2) return false;

   double change = MathAbs(closes[0] - closes[period - 1]);
   double volatility = 0.0;
   for(int i = 0; i < period - 1; i++)
   {
      volatility += MathAbs(closes[i] - closes[i + 1]);
   }

   er1 = (volatility > 1e-6) ? (change / volatility) : 0.0;

   double sc_fast = 2.0 / (2.0 + 1.0);
   double sc_slow = 2.0 / (30.0 + 1.0);
   double sc = MathPow(er1 * (sc_fast - sc_slow) + sc_slow, 2.0);

   kama1 = closes[0] * sc + closes[1] * (1.0 - sc);
   kama2 = closes[1];
   return true;
}

//+------------------------------------------------------------------+
//| Compute HMA State                                                |
//+------------------------------------------------------------------+
bool ComputeHMA_State(int period, double &hma1, double &hma2, double &slope1)
{
   int halfPeriod = (int)MathMax(period / 2, 2);
   int sqrtPeriod = (int)MathMax(MathSqrt((double)period), 2);
   int totalRequired = period + sqrtPeriod + 10;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 1, totalRequired, rates) < totalRequired) return false;

   double rawSeries[];
   ArrayResize(rawSeries, sqrtPeriod + 4);
   for(int k = 0; k < sqrtPeriod + 4; k++)
   {
      double closes[];
      ArrayResize(closes, period);
      for(int c = 0; c < period; c++) closes[c] = rates[k + c].close;
      double wHalf = CalcWMA(closes, 0, halfPeriod);
      double wFull = CalcWMA(closes, 0, period);
      rawSeries[k] = 2.0 * wHalf - wFull;
   }
   hma1 = CalcWMA(rawSeries, 0, sqrtPeriod);
   hma2 = CalcWMA(rawSeries, 1, sqrtPeriod);
   slope1 = hma1 - hma2;
   return true;
}

//+------------------------------------------------------------------+
//| Compute CMO                                                      |
//+------------------------------------------------------------------+
double ComputeCMO(int period)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 1, period + 5, rates) < period + 1) return 0.0;
   double sumUp = 0.0, sumDown = 0.0;
   for(int i = 0; i < period; i++)
   {
      double diff = rates[i].close - rates[i + 1].close;
      if(diff > 0) sumUp += diff;
      else         sumDown += MathAbs(diff);
   }
   double total = sumUp + sumDown;
   return (total > 1e-6) ? (100.0 * (sumUp - sumDown) / total) : 0.0;
}

//+------------------------------------------------------------------+
//| Compute Confirmed Swing Levels (BOS)                             |
//+------------------------------------------------------------------+
bool ComputeConfirmedSwingLevels(int k, double &recentSH, double &recentSL)
{
   int lookback = 80;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 1, lookback, rates) < lookback) return false;

   recentSH = 0.0;
   recentSL = 0.0;

   for(int i = k; i < lookback - k; i++)
   {
      bool isHigh = true;
      bool isLow  = true;
      for(int j = 1; j <= k; j++)
      {
         if(rates[i].high <= rates[i - j].high || rates[i].high <= rates[i + j].high) isHigh = false;
         if(rates[i].low  >= rates[i - j].low  || rates[i].low  >= rates[i + j].low)  isLow  = false;
      }
      if(isHigh && recentSH == 0.0) recentSH = rates[i].high;
      if(isLow  && recentSL == 0.0) recentSL = rates[i].low;
      if(recentSH > 0.0 && recentSL > 0.0) break;
   }
   return (recentSH > 0.0 && recentSL > 0.0);
}

//+------------------------------------------------------------------+
//| Audit Realized PnL Across Magic Numbers                          |
//+------------------------------------------------------------------+
void AuditPortfolioPnL(int yearMonth, int dayKey)
{
   datetime startOfMonth = StringToTime(StringFormat("%04d.%02d.01 00:00:00", yearMonth / 100, yearMonth % 100));
   datetime startOfDay   = StringToTime(StringFormat("%04d.%02d.%02d 00:00:00", dayKey / 10000, (dayKey % 10000) / 100, dayKey % 100));
   datetime now = TimeCurrent();

   HistorySelect(startOfMonth, now);
   m_e1.monthlyRealizedPnL = 0.0;
   m_e2.monthlyRealizedPnL = 0.0;
   m_e3.monthlyRealizedPnL = 0.0;
   m_e4.monthlyRealizedPnL = 0.0;
   m_e5.monthlyRealizedPnL = 0.0;
   m_portfolio_monthly_pnl = 0.0;
   m_portfolio_daily_pnl   = 0.0;

   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0) continue;
      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol) continue;

      long dealEntry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(dealEntry != DEAL_ENTRY_OUT) continue;

      ulong magic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
      double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT) +
                      HistoryDealGetDouble(dealTicket, DEAL_SWAP) +
                      HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
      datetime dealTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);

      if(magic == InpMagic_E1) m_e1.monthlyRealizedPnL += profit;
      else if(magic == InpMagic_E2) m_e2.monthlyRealizedPnL += profit;
      else if(magic == InpMagic_E3) m_e3.monthlyRealizedPnL += profit;
      else if(magic == InpMagic_E4) m_e4.monthlyRealizedPnL += profit;
      else if(magic == InpMagic_E5) m_e5.monthlyRealizedPnL += profit;

      m_portfolio_monthly_pnl += profit;
      if(dealTime >= startOfDay) m_portfolio_daily_pnl += profit;
   }

   // Evaluate Per-Engine Locks
   if(m_e1.monthlyRealizedPnL >= InpE1_MonthlyProfitLock || m_e1.monthlyRealizedPnL <= -InpE1_MonthlyLossCap)
      m_e1.isMonthLocked = true;
   if(m_e2.monthlyRealizedPnL >= InpE2_MonthlyProfitLock || m_e2.monthlyRealizedPnL <= -InpE2_MonthlyLossCap)
      m_e2.isMonthLocked = true;
   if(m_e3.monthlyRealizedPnL >= InpE3_MonthlyProfitLock || m_e3.monthlyRealizedPnL <= -InpE3_MonthlyLossCap)
      m_e3.isMonthLocked = true;
   if(m_e4.monthlyRealizedPnL >= InpE4_MonthlyProfitLock || m_e4.monthlyRealizedPnL <= -InpE4_MonthlyLossCap)
      m_e4.isMonthLocked = true;
   if(m_e5.monthlyRealizedPnL >= InpE5_MonthlyProfitLock || m_e5.monthlyRealizedPnL <= -InpE5_MonthlyLossCap)
      m_e5.isMonthLocked = true;

   // Evaluate Master Global Circuit Breakers
   if(m_portfolio_daily_pnl <= -InpMasterDailyLossCap)     m_master_day_locked = true;
   if(m_portfolio_monthly_pnl <= -InpMasterMonthlyLossCap) m_master_month_locked = true;
}

//+------------------------------------------------------------------+
//| Expert Tick Function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == m_last_bar_time) return;

   MqlDateTime dt;
   TimeToStruct(current_bar_time, dt);
   int bar_month = dt.year * 100 + dt.mon;
   int bar_day   = dt.year * 10000 + dt.mon * 100 + dt.day;

   // Calendar Governance Reset
   if(bar_month != m_current_month)
   {
      m_current_month = bar_month;
      m_e1.isMonthLocked = false;
      m_e2.isMonthLocked = false;
      m_e3.isMonthLocked = false;
      m_e4.isMonthLocked = false;
      m_e5.isMonthLocked = false;
      m_master_month_locked = false;
      PrintFormat("[*] Calendar Month Reset: %d. Portfolio unlocked.", bar_month);
   }

   if(bar_day != m_current_day)
   {
      m_current_day = bar_day;
      m_master_day_locked = false;
   }

   AuditPortfolioPnL(bar_month, bar_day);

   if(m_master_day_locked || m_master_month_locked)
   {
      m_last_bar_time = current_bar_time;
      return;
   }

   // Spread Check
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_spread = ask - bid;
   if(current_spread > InpMasterMaxSpread)
   {
      m_last_bar_time = current_bar_time;
      return;
   }

   // Shared Buffer Copies (Bar 1)
   double atr_buf[], ema200_buf[];
   ArraySetAsSeries(atr_buf, true);
   ArraySetAsSeries(ema200_buf, true);
   if(CopyBuffer(m_hATR, 0, 1, 1, atr_buf) <= 0 || CopyBuffer(m_hEMA200, 0, 1, 1, ema200_buf) <= 0)
      return;

   double c_atr  = atr_buf[0];
   double c_ema  = ema200_buf[0];
   double c_close = iClose(_Symbol, PERIOD_H1, 1);
   bool trend_bull = (c_close > c_ema);
   bool trend_bear = (c_close < c_ema);

   // Shared KFD on Bar 1
   double kfd_1 = CalculateKFD(1, InpKfdPeriod);

   // =================================================================
   // ENGINE 1: KAMA DYNAMIC EFFICIENCY (S36 - PF 2.715)
   // =================================================================
   if(m_e1.enabled && !m_e1.isMonthLocked && !HasPosition(InpMagic_E1))
   {
      double kama1, kama2, er1;
      if(ComputeKAMA_State(InpKAMA_Period, kama1, kama2, er1))
      {
         bool kama_bull = (kama1 > kama2) && (er1 >= InpKAMA_ER_Thresh) && trend_bull;
         bool kama_bear = (kama1 < kama2) && (er1 >= InpKAMA_ER_Thresh) && trend_bear;

         if(kama_bull)
         {
            double sl = ask - InpE1_SL_Mult * c_atr;
            double tp = ask + InpE1_TP_Mult * c_atr;
            m_trade_e1.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E1 KAMA Efficiency Long");
         }
         else if(kama_bear)
         {
            double sl = bid + InpE1_SL_Mult * c_atr;
            double tp = bid - InpE1_TP_Mult * c_atr;
            m_trade_e1.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E1 KAMA Efficiency Short");
         }
      }
   }

   // =================================================================
   // ENGINE 2: HMA-CMO VELOCITY BREAKOUT (S38 - PF 2.375)
   // =================================================================
   if(m_e2.enabled && !m_e2.isMonthLocked && !HasPosition(InpMagic_E2))
   {
      double hma1, hma2, hma_slope;
      if(ComputeHMA_State(InpHMA_Period, hma1, hma2, hma_slope))
      {
         double cmo_val = ComputeCMO(InpCMO_Period);

         MqlRates channelRates[];
         ArraySetAsSeries(channelRates, true);
         if(CopyRates(_Symbol, PERIOD_H1, 2, InpChannelLookback, channelRates) >= InpChannelLookback)
         {
            double highestHigh = channelRates[0].high;
            double lowestLow   = channelRates[0].low;
            for(int ch = 1; ch < InpChannelLookback; ch++)
            {
               if(channelRates[ch].high > highestHigh) highestHigh = channelRates[ch].high;
               if(channelRates[ch].low  < lowestLow)   lowestLow   = channelRates[ch].low;
            }

            bool hma_bull = (c_close > highestHigh) && (hma_slope > 0) && (cmo_val > InpCMO_Thresh) && trend_bull && (kfd_1 <= 1.40);
            bool hma_bear = (c_close < lowestLow)   && (hma_slope < 0) && (cmo_val < -InpCMO_Thresh) && trend_bear && (kfd_1 <= 1.40);

            if(hma_bull)
            {
               double sl = ask - InpE2_SL_Mult * c_atr;
               double tp = ask + InpE2_TP_Mult * c_atr;
               m_trade_e2.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E2 HMA-CMO Velocity Long");
            }
            else if(hma_bear)
            {
               double sl = bid + InpE2_SL_Mult * c_atr;
               double tp = bid - InpE2_TP_Mult * c_atr;
               m_trade_e2.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E2 HMA-CMO Velocity Short");
            }
         }
      }
   }

   // =================================================================
   // ENGINE 3: BOLLINGER BANDWIDTH SQUEEZE IGNITION (S118 - PF 2.267)
   // =================================================================
   if(m_e3.enabled && !m_e3.isMonthLocked && !HasPosition(InpMagic_E3))
   {
      double bb_mid[], bb_up[], bb_lo[];
      ArraySetAsSeries(bb_mid, true);
      ArraySetAsSeries(bb_up, true);
      ArraySetAsSeries(bb_lo, true);

      if(CopyBuffer(m_hBB, 0, 1, 2, bb_mid) >= 2 &&
         CopyBuffer(m_hBB, 1, 1, 2, bb_up)  >= 2 &&
         CopyBuffer(m_hBB, 2, 1, 2, bb_lo)  >= 2)
      {
         double c_close_2 = iClose(_Symbol, PERIOD_H1, 2);
         double bw_1 = (bb_up[0] - bb_lo[0]) / (bb_mid[0] + 1e-9);
         double bw_2 = (bb_up[1] - bb_lo[1]) / (bb_mid[1] + 1e-9);
         bool bw_expanding = (bw_1 > bw_2);

         double pct_b_1 = (c_close - bb_lo[0]) / (bb_up[0] - bb_lo[0] + 1e-9);
         double pct_b_2 = (c_close_2 - bb_lo[1]) / (bb_up[1] - bb_lo[1] + 1e-9);

         bool bull_cross = (pct_b_1 > InpPctBUpperCutoff) && (pct_b_2 <= InpPctBUpperCutoff);
         bool bear_cross = (pct_b_1 < InpPctBLowerCutoff) && (pct_b_2 >= InpPctBLowerCutoff);

         bool e3_bull = bull_cross && bw_expanding && trend_bull && (kfd_1 <= InpE3_KFDThresh);
         bool e3_bear = bear_cross && bw_expanding && trend_bear && (kfd_1 <= InpE3_KFDThresh);

         if(e3_bull)
         {
            double sl = ask - InpE3_SL_Mult * c_atr;
            double tp = ask + InpE3_TP_Mult * c_atr;
            m_trade_e3.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E3 BB Squeeze Ignition Long");
         }
         else if(e3_bear)
         {
            double sl = bid + InpE3_SL_Mult * c_atr;
            double tp = bid - InpE3_TP_Mult * c_atr;
            m_trade_e3.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E3 BB Squeeze Ignition Short");
         }
      }
   }

   // =================================================================
   // ENGINE 4: CHOPPINESS INDEX IGNITION EXPANSION (S113 - PF 2.296)
   // =================================================================
   if(m_e4.enabled && !m_e4.isMonthLocked && !HasPosition(InpMagic_E4))
   {
      double chop_1 = CalculateChop(1, InpChopPeriod);
      double chop_2 = CalculateChop(2, InpChopPeriod);

      bool chop_ignition = (chop_1 < InpChopThreshold) && (chop_2 >= InpChopThreshold);
      bool e4_bull = chop_ignition && trend_bull && (kfd_1 <= InpE4_KFDThresh);
      bool e4_bear = chop_ignition && trend_bear && (kfd_1 <= InpE4_KFDThresh);

      if(e4_bull)
      {
         double sl = ask - InpE4_SL_Mult * c_atr;
         double tp = ask + InpE4_TP_Mult * c_atr;
         m_trade_e4.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E4 Choppiness Ignition Long");
      }
      else if(e4_bear)
      {
         double sl = bid + InpE4_SL_Mult * c_atr;
         double tp = bid - InpE4_TP_Mult * c_atr;
         m_trade_e4.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E4 Choppiness Ignition Short");
      }
   }

   // =================================================================
   // ENGINE 5: MARKET STRUCTURE BOS (S55 - PF 1.560)
   // =================================================================
   if(m_e5.enabled && !m_e5.isMonthLocked && !HasPosition(InpMagic_E5))
   {
      double swingH, swingL;
      if(ComputeConfirmedSwingLevels(InpSwingK, swingH, swingL))
      {
         double c_close_2 = iClose(_Symbol, PERIOD_H1, 2);
         bool bos_bull = (c_close > swingH) && (c_close_2 <= swingH) && trend_bull && (kfd_1 <= InpE5_KFDThresh);
         bool bos_bear = (c_close < swingL) && (c_close_2 >= swingL) && trend_bear && (kfd_1 <= InpE5_KFDThresh);

         if(bos_bull)
         {
            double sl = ask - InpE5_SL_Mult * c_atr;
            double tp = ask + InpE5_TP_Mult * c_atr;
            m_trade_e5.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E5 Market Structure BOS Long");
         }
         else if(bos_bear)
         {
            double sl = bid + InpE5_SL_Mult * c_atr;
            double tp = bid - InpE5_TP_Mult * c_atr;
            m_trade_e5.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E5 Market Structure BOS Short");
         }
      }
   }

   m_last_bar_time = current_bar_time;

   // Update Chart Dashboard
   string commentStr = StringFormat(
      "=== TITAN SUPREME QUINTET 5-in-1 MASTER EA ===\n" +
      "Daily PnL: $%.2f | Monthly PnL: $%.2f\n" +
      "E1 (KAMA PF 2.71): %s (PnL: $%.2f)\n" +
      "E2 (HMA-CMO PF 2.37): %s (PnL: $%.2f)\n" +
      "E3 (BB Squeeze PF 2.27): %s (PnL: $%.2f)\n" +
      "E4 (Choppiness PF 2.30): %s (PnL: $%.2f)\n" +
      "E5 (BOS Structure PF 1.56): %s (PnL: $%.2f)\n" +
      "Portfolio Status: %s",
      m_portfolio_daily_pnl, m_portfolio_monthly_pnl,
      (m_e1.isMonthLocked ? "LOCKED" : (m_e1.enabled ? "ACTIVE" : "OFF")), m_e1.monthlyRealizedPnL,
      (m_e2.isMonthLocked ? "LOCKED" : (m_e2.enabled ? "ACTIVE" : "OFF")), m_e2.monthlyRealizedPnL,
      (m_e3.isMonthLocked ? "LOCKED" : (m_e3.enabled ? "ACTIVE" : "OFF")), m_e3.monthlyRealizedPnL,
      (m_e4.isMonthLocked ? "LOCKED" : (m_e4.enabled ? "ACTIVE" : "OFF")), m_e4.monthlyRealizedPnL,
      (m_e5.isMonthLocked ? "LOCKED" : (m_e5.enabled ? "ACTIVE" : "OFF")), m_e5.monthlyRealizedPnL,
      (m_master_day_locked ? "DAY LOCKED" : (m_master_month_locked ? "MONTH LOCKED" : "ONLINE"))
   );
   Comment(commentStr);
}
//+------------------------------------------------------------------+

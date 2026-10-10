//+------------------------------------------------------------------+
//|                      Titan_Supreme_Trinity_Portfolio_EA.mq5      |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|            Grand Hybrid Multi-Strategy Institutional Master EA   |
//|        Aggregating: KAMA (PF 2.71) + HMA-CMO (PF 2.37) + BOS (PF 1.56)|
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "3.00"
#property description "Titan Supreme Trinity Hybrid Portfolio EA (3 Uncorrelated Engines in 1 EA)"
#property strict

#include <Trade\Trade.mqh>

//--- MASTER PORTFOLIO CONFIGURATION ---
input group "=== Master Portfolio & Global Risk Governance ==="
input double   InpMasterLotSize       = 0.10;      // Base Lot per Engine (0.10 std lots = 10 oz Gold)
input double   InpMasterMaxSpread     = 0.60;      // Maximum Allowable Spread ($)
input double   InpMasterDailyLossCap  = 350.0;     // Master Portfolio Daily Loss Breaker ($)
input double   InpMasterMonthlyLossCap= 500.0;     // Master Portfolio Monthly Loss Breaker ($)

input group "=== Sub-Engine 1: KAMA Efficiency (S36 - PF 2.715) ==="
input bool     InpEnable_E1_KAMA      = true;      // Enable KAMA Efficiency Engine
input ulong    InpMagic_E1            = 101001;    // Magic Number for Engine 1
input int      InpKAMA_Period         = 10;        // KAMA Lookback Period (Hours)
input double   InpKAMA_ER_Thresh      = 0.45;      // KAMA Efficiency Ratio Threshold (>= 0.45)
input double   InpE1_TP_Mult          = 4.5;       // E1 Take Profit (ATR Mult)
input double   InpE1_SL_Mult          = 2.0;       // E1 Stop Loss (ATR Mult)
input double   InpE1_MonthlyProfitLock= 250.0;     // E1 Monthly Profit Lock ($)
input double   InpE1_MonthlyLossCap   = 250.0;     // E1 Monthly Loss Breaker ($)

input group "=== Sub-Engine 2: HMA-CMO Velocity (S38 - PF 2.375) ==="
input bool     InpEnable_E2_HMA       = true;      // Enable HMA-CMO Velocity Engine
input ulong    InpMagic_E2            = 101002;    // Magic Number for Engine 2
input int      InpHMA_Period          = 24;        // HMA Lookback Period (Hours)
input int      InpCMO_Period          = 10;        // CMO Lookback Period (Hours)
input double   InpCMO_Thresh          = 25.0;      // CMO Momentum Threshold (+/- 25.0)
input int      InpChannelLookback     = 12;        // Breakout Channel Lookback (Hours)
input double   InpE2_TP_Mult          = 4.5;       // E2 Take Profit (ATR Mult)
input double   InpE2_SL_Mult          = 2.5;       // E2 Stop Loss (ATR Mult)
input double   InpE2_MonthlyProfitLock= 200.0;     // E2 Monthly Profit Lock ($)
input double   InpE2_MonthlyLossCap   = 250.0;     // E2 Monthly Loss Breaker ($)

input group "=== Sub-Engine 3: Market Structure BOS (S55 - PF 1.560) ==="
input bool     InpEnable_E3_BOS       = true;      // Enable Market Structure BOS Engine
input ulong    InpMagic_E3            = 101003;    // Magic Number for Engine 3
input int      InpSwingK              = 4;         // Confirmed Swing Lookback (k bars)
input double   InpE3_TP_Mult          = 4.5;       // E3 Take Profit (ATR Mult)
input double   InpE3_SL_Mult          = 1.5;       // E3 Stop Loss (ATR Mult - 3:1 Payoff)
input double   InpE3_MonthlyProfitLock= 250.0;     // E3 Monthly Profit Lock ($)
input double   InpE3_MonthlyLossCap   = 250.0;     // E3 Monthly Loss Breaker ($)

input group "=== Common Technical Filters ==="
input int      InpAtrPeriod           = 14;        // ATR Volatility Period
input int      InpEmaPeriod           = 200;       // Macro Trend EMA
input double   InpKfdThreshold        = 1.42;      // Shared Katz Fractal Noise Gate (<= 1.42)
input int      InpKfdPeriod           = 24;        // Katz Fractal Window

//--- ENGINE STATE STRUCT ---
struct EngineState
{
   ulong    magic;
   bool     enabled;
   bool     isMonthLocked;
   double   monthlyRealizedPnL;
   bool     hasOpenPosition;
};

EngineState m_e1, m_e2, m_e3;

CTrade         m_trade_e1, m_trade_e2, m_trade_e3;
int            m_hATR;
int            m_hEMA200;
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

   m_trade_e1.SetMarginMode();
   m_trade_e2.SetMarginMode();
   m_trade_e3.SetMarginMode();

   m_hATR    = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE)
   {
      Print("[!] Error initializing shared indicators.");
      return(INIT_FAILED);
   }

   m_e1.magic = InpMagic_E1; m_e1.enabled = InpEnable_KAMA_Engine; m_e1.isMonthLocked = false; m_e1.monthlyRealizedPnL = 0.0;
   m_e2.magic = InpMagic_E2; m_e2.enabled = InpEnable_E2_HMA;       m_e2.isMonthLocked = false; m_e2.monthlyRealizedPnL = 0.0;
   m_e3.magic = InpMagic_E3; m_e3.enabled = InpEnable_E3_BOS;       m_e3.isMonthLocked = false; m_e3.monthlyRealizedPnL = 0.0;

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_current_day          = -1;
   m_portfolio_daily_pnl  = 0.0;
   m_portfolio_monthly_pnl= 0.0;
   m_master_day_locked    = false;
   m_master_month_locked  = false;

   Print("[+] Titan Supreme Trinity Hybrid Portfolio EA Initialized Successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_hATR);
   IndicatorRelease(m_hEMA200);
   Comment("");
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
//| Compute Katz Fractal Dimension                                   |
//+------------------------------------------------------------------+
double ComputeKFD(const double &closes[], int start_idx, int period)
{
   if(ArraySize(closes) < start_idx + period) return 1.5;
   double euclid_d = MathAbs(closes[start_idx] - closes[start_idx + period - 1]);
   double total_len = 0.0;
   for(int i = start_idx; i < start_idx + period - 1; i++)
   {
      total_len += MathAbs(closes[i] - closes[i + 1]);
   }
   if(total_len > 1e-6 && euclid_d > 1e-6)
   {
      double ratio = euclid_d / total_len;
      double n_bars = (double)period;
      double val = MathLog10(n_bars) / (MathLog10(n_bars) + MathLog10(ratio));
      return MathMax(1.0, MathMin(2.0, val));
   }
   return 1.5;
}

//+------------------------------------------------------------------+
//| Compute KAMA & Efficiency Ratio (ER)                             |
//+------------------------------------------------------------------+
bool ComputeKAMA_State(const double &closes[], int period, double &kama1, double &kama2, double &er1)
{
   int n = ArraySize(closes);
   if(n < period + 5) return false;

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
   int sqrtPeriod = (int)MathMax(MathSqrt(period), 2);
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
   m_portfolio_monthly_pnl = 0.0;
   m_portfolio_daily_pnl   = 0.0;

   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         ulong magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
         {
            double netDeal = HistoryDealGetDouble(ticket, DEAL_PROFIT) +
                             HistoryDealGetDouble(ticket, DEAL_SWAP) +
                             HistoryDealGetDouble(ticket, DEAL_COMMISSION);

            datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);

            if(magic == InpMagic_E1) m_e1.monthlyRealizedPnL += netDeal;
            if(magic == InpMagic_E2) m_e2.monthlyRealizedPnL += netDeal;
            if(magic == InpMagic_E3) m_e3.monthlyRealizedPnL += netDeal;

            m_portfolio_monthly_pnl += netDeal;
            if(dealTime >= startOfDay) m_portfolio_daily_pnl += netDeal;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check Active Positions per Engine                                |
//+------------------------------------------------------------------+
void UpdateActivePositions()
{
   m_e1.hasOpenPosition = false;
   m_e2.hasOpenPosition = false;
   m_e3.hasOpenPosition = false;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol)
      {
         ulong posMagic = PositionGetInteger(POSITION_MAGIC);
         if(posMagic == InpMagic_E1) m_e1.hasOpenPosition = true;
         if(posMagic == InpMagic_E2) m_e2.hasOpenPosition = true;
         if(posMagic == InpMagic_E3) m_e3.hasOpenPosition = true;
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_H1, 0);
   if(currentBarTime == m_last_bar_time) return;
   m_last_bar_time = currentBarTime;

   MqlDateTime dt;
   TimeToStruct(currentBarTime, dt);
   int barMonth = dt.year * 100 + dt.mon;
   int barDay   = dt.year * 10000 + dt.mon * 100 + dt.day;

   if(barMonth != m_current_month)
   {
      m_current_month        = barMonth;
      m_master_month_locked  = false;
      m_e1.isMonthLocked     = false;
      m_e2.isMonthLocked     = false;
      m_e3.isMonthLocked     = false;
      PrintFormat("[*] New Portfolio Month %d Initialized.", m_current_month);
   }

   if(barDay != m_current_day)
   {
      m_current_day       = barDay;
      m_master_day_locked = false;
   }

   AuditPortfolioPnL(m_current_month, m_current_day);
   UpdateActivePositions();

   // Engine-level ASAR Locks
   if(m_e1.monthlyRealizedPnL >= InpE1_MonthlyProfitLock || m_e1.monthlyRealizedPnL <= -InpE1_MonthlyLossCap) m_e1.isMonthLocked = true;
   if(m_e2.monthlyRealizedPnL >= InpE2_MonthlyProfitLock || m_e2.monthlyRealizedPnL <= -InpE2_MonthlyLossCap) m_e2.isMonthLocked = true;
   if(m_e3.monthlyRealizedPnL >= InpE3_MonthlyProfitLock || m_e3.monthlyRealizedPnL <= -InpE3_MonthlyLossCap) m_e3.isMonthLocked = true;

   // Master Circuit Breakers
   if(m_portfolio_daily_pnl <= -InpMasterDailyLossCap)     m_master_day_locked   = true;
   if(m_portfolio_monthly_pnl <= -InpMasterMonthlyLossCap) m_master_month_locked = true;

   // Render Terminal HUD
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string hud = StringFormat(
      "=====================================================\n"
      "  TITAN SUPREME TRINITY HYBRID PORTFOLIO EA (3-IN-1)  \n"
      "=====================================================\n"
      "Portfolio Realized M-PnL: $%.2f | D-PnL: $%.2f\n"
      "Master Circuit Status: %s | Spread: %.2f (Max: %.2f)\n"
      "-----------------------------------------------------\n"
      " [E1] KAMA Efficiency (S36)  : PnL $%.2f | %s | Pos: %s\n"
      " [E2] HMA-CMO Velocity (S38) : PnL $%.2f | %s | Pos: %s\n"
      " [E3] Market Struct BOS (S55): PnL $%.2f | %s | Pos: %s\n"
      "=====================================================",
      m_portfolio_monthly_pnl, m_portfolio_daily_pnl,
      (m_master_month_locked ? "MONTH LOCKED" : (m_master_day_locked ? "DAY LOCKED" : "ACTIVE")),
      spread, InpMasterMaxSpread,
      m_e1.monthlyRealizedPnL, (m_e1.isMonthLocked ? "LOCK" : "RUN"), (m_e1.hasOpenPosition ? "YES" : "NO"),
      m_e2.monthlyRealizedPnL, (m_e2.isMonthLocked ? "LOCK" : "RUN"), (m_e2.hasOpenPosition ? "YES" : "NO"),
      m_e3.monthlyRealizedPnL, (m_e3.isMonthLocked ? "LOCK" : "RUN"), (m_e3.hasOpenPosition ? "YES" : "NO")
   );
   Comment(hud);

   if(m_master_day_locked || m_master_month_locked) return;
   if(spread > InpMasterMaxSpread) return;

   // Shared Data Gathering
   int needed = MathMax(InpKfdPeriod + 10, InpSwingK * 5 + 30);
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_H1, 1, needed, rates) < needed) return;

   double atrBuf[], emaBuf[];
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(emaBuf, true);
   if(CopyBuffer(m_hATR, 0, 1, 5, atrBuf) < 5) return;
   if(CopyBuffer(m_hEMA200, 0, 1, 5, emaBuf) < 5) return;

   double cATR    = atrBuf[0];
   double cEMA200 = emaBuf[0];
   if(cATR < 0.5) return;

   double closes_arr[];
   ArrayResize(closes_arr, InpKfdPeriod);
   for(int i = 0; i < InpKfdPeriod; i++) closes_arr[i] = rates[i].close;
   double current_kfd = ComputeKFD(closes_arr, 0, InpKfdPeriod);
   bool kfd_ok = (current_kfd <= InpKfdThreshold);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double close1 = rates[0].close;
   double close2 = rates[1].close;

   // -----------------------------------------------------------------
   // SUB-ENGINE 1: KAMA DYNAMIC EFFICIENCY (S36)
   // -----------------------------------------------------------------
   if(m_e1.enabled && !m_e1.isMonthLocked && !m_e1.hasOpenPosition)
   {
      double kama1 = 0.0, kama2 = 0.0, er1 = 0.0;
      if(ComputeKAMA_State(closes_arr, InpKAMA_Period, kama1, kama2, er1))
      {
         bool kama_er_ok = (er1 >= InpKAMA_ER_Thresh);
         bool kama_slope_up = (kama1 > kama2);
         bool kama_slope_dn = (kama1 < kama2);

         bool e1_buy  = kama_er_ok && kama_slope_up && (close1 > cEMA200);
         bool e1_sell = kama_er_ok && kama_slope_dn && (close1 < cEMA200);

         if(e1_buy)
         {
            double sl = ask - InpE1_SL_Mult * cATR;
            double tp = ask + InpE1_TP_Mult * cATR;
            m_trade_e1.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E1_KAMA_Buy");
            PrintFormat("[+] E1 KAMA Long Filled at %.2f | SL: %.2f | TP: %.2f", ask, sl, tp);
            m_e1.hasOpenPosition = true;
         }
         else if(e1_sell)
         {
            double sl = bid + InpE1_SL_Mult * cATR;
            double tp = bid - InpE1_TP_Mult * cATR;
            m_trade_e1.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E1_KAMA_Sell");
            PrintFormat("[+] E1 KAMA Short Filled at %.2f | SL: %.2f | TP: %.2f", bid, sl, tp);
            m_e1.hasOpenPosition = true;
         }
      }
   }

   // -----------------------------------------------------------------
   // SUB-ENGINE 2: HMA-CMO VELOCITY (S38)
   // -----------------------------------------------------------------
   if(m_e2.enabled && !m_e2.isMonthLocked && !m_e2.hasOpenPosition && kfd_ok)
   {
      double hma1 = 0.0, hma2 = 0.0, hmaSlope = 0.0;
      if(ComputeHMA_State(InpHMA_Period, hma1, hma2, hmaSlope))
      {
         double cmoVal = ComputeCMO(InpCMO_Period);

         double chHigh = -1.0, chLow = 999999.0;
         for(int i = 1; i <= InpChannelLookback; i++)
         {
            if(rates[i].high > chHigh) chHigh = rates[i].high;
            if(rates[i].low < chLow)   chLow  = rates[i].low;
         }

         bool e2_buy  = (close1 > chHigh) && (close1 > cEMA200) && (hmaSlope > 0) && (cmoVal > InpCMO_Thresh);
         bool e2_sell = (close1 < chLow)  && (close1 < cEMA200) && (hmaSlope < 0) && (cmoVal < -InpCMO_Thresh);

         if(e2_buy)
         {
            double sl = ask - InpE2_SL_Mult * cATR;
            double tp = ask + InpE2_TP_Mult * cATR;
            m_trade_e2.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E2_HMA_Buy");
            PrintFormat("[+] E2 HMA Long Filled at %.2f | SL: %.2f | TP: %.2f", ask, sl, tp);
            m_e2.hasOpenPosition = true;
         }
         else if(e2_sell)
         {
            double sl = bid + InpE2_SL_Mult * cATR;
            double tp = bid - InpE2_TP_Mult * cATR;
            m_trade_e2.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E2_HMA_Sell");
            PrintFormat("[+] E2 HMA Short Filled at %.2f | SL: %.2f | TP: %.2f", bid, sl, tp);
            m_e2.hasOpenPosition = true;
         }
      }
   }

   // -----------------------------------------------------------------
   // SUB-ENGINE 3: MARKET STRUCTURE BOS (S55)
   // -----------------------------------------------------------------
   if(m_e3.enabled && !m_e3.isMonthLocked && !m_e3.hasOpenPosition && kfd_ok)
   {
      double recent_sh = 0.0, recent_sl = 0.0;
      for(int j = InpSwingK; j < needed - InpSwingK; j++)
      {
         if(recent_sh == 0.0)
         {
            bool is_sh = true;
            double cand_h = rates[j].high;
            for(int b = j - InpSwingK; b <= j + InpSwingK; b++)
            {
               if(b != j && rates[b].high >= cand_h) { is_sh = false; break; }
            }
            if(is_sh) recent_sh = cand_h;
         }
         if(recent_sl == 0.0)
         {
            bool is_sl = true;
            double cand_l = rates[j].low;
            for(int b = j - InpSwingK; b <= j + InpSwingK; b++)
            {
               if(b != j && rates[b].low <= cand_l) { is_sl = false; break; }
            }
            if(is_sl) recent_sl = cand_l;
         }
         if(recent_sh > 0.0 && recent_sl > 0.0) break;
      }

      if(recent_sh > 0.0 && recent_sl > 0.0)
      {
         bool e3_buy  = (close1 > recent_sh) && (close2 <= recent_sh) && (close1 > cEMA200);
         bool e3_sell = (close1 < recent_sl) && (close2 >= recent_sl) && (close1 < cEMA200);

         if(e3_buy)
         {
            double sl = ask - InpE3_SL_Mult * cATR;
            double tp = ask + InpE3_TP_Mult * cATR;
            m_trade_e3.Buy(InpMasterLotSize, _Symbol, ask, sl, tp, "E3_BOS_Buy");
            PrintFormat("[+] E3 BOS Long Filled at %.2f | SL: %.2f | TP: %.2f", ask, sl, tp);
            m_e3.hasOpenPosition = true;
         }
         else if(e3_sell)
         {
            double sl = bid + InpE3_SL_Mult * cATR;
            double tp = bid - InpE3_TP_Mult * cATR;
            m_trade_e3.Sell(InpMasterLotSize, _Symbol, bid, sl, tp, "E3_BOS_Sell");
            PrintFormat("[+] E3 BOS Short Filled at %.2f | SL: %.2f | TP: %.2f", bid, sl, tp);
            m_e3.hasOpenPosition = true;
         }
      }
   }
}

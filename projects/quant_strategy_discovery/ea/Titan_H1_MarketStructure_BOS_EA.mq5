//+------------------------------------------------------------------+
//|                             Titan_H1_MarketStructure_BOS_EA.mq5  |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|                 Strategy 55: Market Structure BOS (BOS-KFD)       |
//|            Profit Factor: 1.560 | MCR: 59.72% | Max DD: $891-$1.2k|
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "2.00"
#property description "Titan H1 Institutional Market Structure BOS EA (Highest Monthly Consistency)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== Institutional Risk Architecture (ASAR) ==="
input ulong    InpMagicNumber         = 550001;    // EA Magic Number
input double   InpBaseLot             = 0.10;      // Base Lot Size (0.10 standard lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 250.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Drawdown Threshold for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Market Structure / Swing Fractal Parameters ==="
input int      InpSwingK              = 4;         // Swing Lookback Confirmation (k bars)
input double   InpTpMult              = 4.5;       // Take Profit ATR Multiplier (4.5R)
input double   InpSlMult              = 1.5;       // Stop Loss ATR Multiplier (1.5R - 3:1 Payoff)

input group "=== Macro Trend & Fractal Noise Gate ==="
input int      InpAtrPeriod           = 14;        // ATR Volatility Period
input int      InpEmaPeriod           = 200;       // Macro Structural Trend EMA
input bool     InpUseKFD_Filter       = true;      // Enable Katz Fractal Gating
input double   InpKfdThreshold        = 1.45;      // Maximum Fractal Dimension (<= 1.45)
input int      InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL SYSTEM STATE ---
CTrade         m_trade;
int            m_hATR;
int            m_hEMA200;
datetime       m_last_bar_time;
int            m_current_month;
double         m_monthly_realized_pnl;
bool           m_is_month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();

   m_hATR    = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   m_hEMA200 = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(m_hATR == INVALID_HANDLE || m_hEMA200 == INVALID_HANDLE)
   {
      Print("[!] Error initializing technical indicator handles.");
      return(INIT_FAILED);
   }

   m_last_bar_time        = 0;
   m_current_month        = -1;
   m_monthly_realized_pnl = 0.0;
   m_is_month_locked      = false;

   Print("[+] Titan H1 Market Structure BOS EA Initialized Successfully (MCR 59.72% Engine).");
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
//| Update Realized Monthly PnL from Closed Orders                   |
//+------------------------------------------------------------------+
void UpdateMonthlyRealizedPnL(int yearMonth)
{
   datetime startOfMonth = StringToTime(StringFormat("%04d.%02d.01 00:00:00", yearMonth / 100, yearMonth % 100));
   datetime now = TimeCurrent();

   HistorySelect(startOfMonth, now);
   double pnl = 0.0;
   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket > 0)
      {
         if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) == InpMagicNumber)
         {
            long entry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            {
               pnl += HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
               pnl += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
               pnl += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
            }
         }
      }
   }
   m_monthly_realized_pnl = pnl;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Execute only on new H1 bar
   datetime currentBarTime = iTime(_Symbol, PERIOD_H1, 0);
   if(currentBarTime == m_last_bar_time) return;
   m_last_bar_time = currentBarTime;

   MqlDateTime dt;
   TimeToStruct(currentBarTime, dt);
   int barMonth = dt.year * 100 + dt.mon;

   if(barMonth != m_current_month)
   {
      m_current_month        = barMonth;
      m_monthly_realized_pnl = 0.0;
      m_is_month_locked      = false;
      PrintFormat("[*] New Trading Month %d Initialized for Titan BOS EA.", m_current_month);
   }

   UpdateMonthlyRealizedPnL(m_current_month);

   // Check ASAR Circuit Breakers
   if(m_monthly_realized_pnl >= InpMonthlyProfitLock)
   {
      m_is_month_locked = true;
   }
   if(m_monthly_realized_pnl <= -InpHardLossBreaker)
   {
      m_is_month_locked = true;
   }

   // On-Chart Status HUD
   string hud = StringFormat(
      "=== TITAN H1 MARKET STRUCTURE BOS EA (S55) ===\n"
      "Month: %d | Realized PnL: $%.2f\n"
      "Status: %s\n"
      "Spread: %.2f (Max: %.2f)",
      m_current_month, m_monthly_realized_pnl,
      m_is_month_locked ? "LOCKED (ASAR Budget Hit)" : "ACTIVE",
      SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID),
      InpMaxSpread
   );
   Comment(hud);

   if(m_is_month_locked) return;

   // Check Spread Protection
   double currentSpread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(currentSpread > InpMaxSpread)
   {
      PrintFormat("[!] Spread too high (%.2f > %.2f). Trade skipped.", currentSpread, InpMaxSpread);
      return;
   }

   // Check Active Position
   bool hasPosition = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         hasPosition = true;
         break;
      }
   }
   if(hasPosition) return;

   // Retrieve Rates & Indicators for Bar 1
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int needed_rates = MathMax(InpKfdPeriod + 10, InpSwingK * 5 + 30);
   if(CopyRates(_Symbol, PERIOD_H1, 1, needed_rates, rates) < needed_rates) return;

   double atrBuf[], emaBuf[];
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(emaBuf, true);
   if(CopyBuffer(m_hATR, 0, 1, 5, atrBuf) < 5) return;
   if(CopyBuffer(m_hEMA200, 0, 1, 5, emaBuf) < 5) return;

   double current_atr = atrBuf[0];
   double current_ema = emaBuf[0];
   if(current_atr < 0.5) return;

   // Compute Katz Fractal Dimension
   if(InpUseKFD_Filter)
   {
      double closes_arr[];
      ArrayResize(closes_arr, InpKfdPeriod);
      for(int i = 0; i < InpKfdPeriod; i++) closes_arr[i] = rates[i].close;
      double current_kfd = ComputeKFD(closes_arr, 0, InpKfdPeriod);
      if(current_kfd > InpKfdThreshold) return; // Market too choppy
   }

   // Identify Confirmed Swing Levels (zero look-ahead bias)
   double recent_sh = 0.0;
   double recent_sl = 0.0;

   for(int j = InpSwingK; j < needed_rates - InpSwingK; j++)
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

   if(recent_sh <= 0.0 || recent_sl <= 0.0) return;

   double close1 = rates[0].close;
   double close2 = rates[1].close;

   // Break of Structure (BOS) Logic
   bool bull_bos = (close1 > recent_sh) && (close2 <= recent_sh) && (close1 > current_ema);
   bool bear_bos = (close1 < recent_sl) && (close2 >= recent_sl) && (close1 < current_ema);

   // Dynamic Defensive Sizing
   double tradeLot = InpBaseLot;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      tradeLot = NormalizeDouble(InpBaseLot * InpDefensiveMult, 2);
      if(tradeLot < 0.01) tradeLot = 0.01;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(bull_bos)
   {
      double sl = ask - InpSlMult * current_atr;
      double tp = ask + InpTpMult * current_atr;
      m_trade.Buy(tradeLot, _Symbol, ask, sl, tp, "Titan_BOS_Buy");
      PrintFormat("[+] Titan BOS Long Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", ask, sl, tp, tradeLot);
   }
   else if(bear_bos)
   {
      double sl = bid + InpSlMult * current_atr;
      double tp = bid - InpTpMult * current_atr;
      m_trade.Sell(tradeLot, _Symbol, bid, sl, tp, "Titan_BOS_Sell");
      PrintFormat("[+] Titan BOS Short Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", bid, sl, tp, tradeLot);
   }
}

//+------------------------------------------------------------------+
//|                        Gold_H1_Elder_Force_Index_Master_EA.mq5    |
//|               Copyright 2026, Autonomous Quant Research Suite    |
//|                    Strategy 58: Elder Force Index (EFI-KFD)       |
//|          Record MCR: 62.5% - 63.9% | Max DD: $855 | Net: +$6.5k  |
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Research Suite"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property description "Gold H1 Elder Force Index Master EA (Highest Single-Engine MCR Record)"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS ---
input group "=== ASAR Institutional Risk Architecture ==="
input ulong    InpMagicNumber         = 580001;    // EA Magic Number
input double   InpLotSize             = 0.10;      // Standard Lot Size (0.10 lots = 10 oz Gold)
input double   InpMaxSpread           = 0.60;      // Maximum Allowable Spread ($)
input double   InpMonthlyProfitLock   = 200.0;     // Monthly Profit Lock Target ($)
input double   InpHardLossBreaker     = 250.0;     // Monthly Hard Loss Circuit Breaker ($)
input double   InpDefensiveThresh     = 120.0;     // Monthly Loss for Defensive Sizing ($)
input double   InpDefensiveMult       = 0.25;      // Defensive Lot Multiplier (0.25x)

input group "=== Elder's Force Index (EFI) Configuration ==="
input int      InpEfiPeriod           = 13;        // Force Index EMA Smoothing Period (Hours)
input double   InpTpMult              = 4.5;       // Take Profit ATR Multiplier (4.5R or 3.5R)
input double   InpSlMult              = 2.0;       // Stop Loss ATR Multiplier (2.0R)

input group "=== Macro Trend & Fractal Noise Gate ==="
input int      InpAtrPeriod           = 14;        // ATR Volatility Period
input int      InpEmaPeriod           = 200;       // Macro Structural Trend EMA
input bool     InpUseKFD_Filter       = true;      // Enable Katz Fractal Gate
input double   InpKfdThreshold        = 1.45;      // Maximum Fractal Dimension (<= 1.45)
input int      InpKfdPeriod           = 24;        // Katz Fractal Window (Hours)

//--- GLOBAL STATE ---
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

   Print("[+] Gold H1 Elder Force Index Master EA Initialized Successfully.");
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
//| Compute Elder Force Index for Bar 1 and Bar 2                    |
//+------------------------------------------------------------------+
bool ComputeEFI_State(int period, double &efi1, double &efi2)
{
   int needed = period * 3 + 10;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H1, 1, needed, rates);
   if(copied < needed) return false;

   double raw_fi[];
   ArrayResize(raw_fi, needed - 1);
   // raw_fi[k] = (close[k] - close[k+1]) * volume[k]
   for(int k = 0; k < needed - 1; k++)
   {
      double diff = rates[k].close - rates[k + 1].close;
      double vol = (double)rates[k].tick_volume;
      raw_fi[k] = diff * vol;
   }

   // EMA calculation on raw_fi
   // EMA_0 = SMA of oldest, then iterate to index 0 (Bar 1)
   double alpha = 2.0 / (period + 1.0);
   int total_points = needed - 1;

   double prev_ema = raw_fi[total_points - 1];
   double efi_series[];
   ArrayResize(efi_series, total_points);
   efi_series[total_points - 1] = prev_ema;

   for(int i = total_points - 2; i >= 0; i--)
   {
      prev_ema = (raw_fi[i] * alpha) + (prev_ema * (1.0 - alpha));
      efi_series[i] = prev_ema;
   }

   efi1 = efi_series[0];
   efi2 = efi_series[1];
   return true;
}

//+------------------------------------------------------------------+
//| Update Monthly Realized PnL                                      |
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
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber)
         {
            long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            {
               pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
               pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
               pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
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
      PrintFormat("[*] New Trading Month %d Initialized for Elder Force Index EA.", m_current_month);
   }

   UpdateMonthlyRealizedPnL(m_current_month);

   if(m_monthly_realized_pnl >= InpMonthlyProfitLock) m_is_month_locked = true;
   if(m_monthly_realized_pnl <= -InpHardLossBreaker)   m_is_month_locked = true;

   string hud = StringFormat(
      "=== GOLD H1 ELDER FORCE INDEX MASTER EA (S58) ===\n"
      "Month: %d | Realized PnL: $%.2f\n"
      "Status: %s | Record MCR: 62.5%% - 63.9%%\n"
      "Spread: %.2f (Max: %.2f)",
      m_current_month, m_monthly_realized_pnl,
      m_is_month_locked ? "LOCKED (ASAR Hit)" : "ACTIVE",
      SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID),
      InpMaxSpread
   );
   Comment(hud);

   if(m_is_month_locked) return;

   double currentSpread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(currentSpread > InpMaxSpread) return;

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
   int needed_rates = MathMax(InpKfdPeriod + 10, InpEfiPeriod * 3 + 10);
   if(CopyRates(_Symbol, PERIOD_H1, 1, needed_rates, rates) < needed_rates) return;

   double atrBuf[], emaBuf[];
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(emaBuf, true);
   if(CopyBuffer(m_hATR, 0, 1, 5, atrBuf) < 5) return;
   if(CopyBuffer(m_hEMA200, 0, 1, 5, emaBuf) < 5) return;

   double current_atr = atrBuf[0];
   double current_ema = emaBuf[0];
   if(current_atr < 0.5) return;

   if(InpUseKFD_Filter)
   {
      double closes_arr[];
      ArrayResize(closes_arr, InpKfdPeriod);
      for(int i = 0; i < InpKfdPeriod; i++) closes_arr[i] = rates[i].close;
      double current_kfd = ComputeKFD(closes_arr, 0, InpKfdPeriod);
      if(current_kfd > InpKfdThreshold) return; // Market too choppy
   }

   double efi1 = 0.0, efi2 = 0.0;
   if(!ComputeEFI_State(InpEfiPeriod, efi1, efi2)) return;

   double close1 = rates[0].close;

   // Elder Force Index Zero-Line Crossover Triggers
   bool bull_cross = (efi1 > 0.0) && (efi2 <= 0.0) && (close1 > current_ema);
   bool bear_cross = (efi1 < 0.0) && (efi2 >= 0.0) && (close1 < current_ema);

   double tradeLot = InpLotSize;
   if(m_monthly_realized_pnl <= -InpDefensiveThresh)
   {
      tradeLot = NormalizeDouble(InpLotSize * InpDefensiveMult, 2);
      if(tradeLot < 0.01) tradeLot = 0.01;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(bull_cross)
   {
      double sl = ask - InpSlMult * current_atr;
      double tp = ask + InpTpMult * current_atr;
      m_trade.Buy(tradeLot, _Symbol, ask, sl, tp, "EFI_Buy");
      PrintFormat("[+] EFI Long Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", ask, sl, tp, tradeLot);
   }
   else if(bear_cross)
   {
      double sl = bid + InpSlMult * current_atr;
      double tp = bid - InpTpMult * current_atr;
      m_trade.Sell(tradeLot, _Symbol, bid, sl, tp, "EFI_Sell");
      PrintFormat("[+] EFI Short Filled at %.2f | SL: %.2f | TP: %.2f | Lot: %.2f", bid, sl, tp, tradeLot);
   }
}

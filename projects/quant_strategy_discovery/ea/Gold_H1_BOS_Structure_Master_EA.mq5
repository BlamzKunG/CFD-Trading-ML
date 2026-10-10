//+------------------------------------------------------------------+
//|                                Gold_H1_BOS_Structure_Master_EA.mq5 |
//|                     Copyright 2026, Quantitative Research Suite |
//|                                      https://antigravity.cfd.ai |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Autonomous Quant Research Suite"
#property link      "https://antigravity.cfd.ai"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Strategy 55: Market Structure BOS Settings ==="
input ulong  InpMagicNumber        = 550001;        // Magic Number
input double InpLotSize            = 0.10;          // Standard Lot Size
input int    InpSwingK             = 4;             // Swing Lookback (k bars)
input int    InpAtrPeriod          = 14;            // ATR Period
input int    InpEmaPeriod          = 200;           // Macro Trend EMA Period
input int    InpKfdPeriod          = 24;            // Katz Fractal Dimension Period
input double InpKfdThreshold       = 1.45;          // Katz Fractal Dimension Threshold
input double InpTpMult             = 4.5;           // Take Profit Multiplier (ATR)
input double InpSlMult             = 1.5;           // Stop Loss Multiplier (ATR)

input group "=== ASAR Risk Management ==="
input double InpMonthlyProfitLock  = 250.0;         // Monthly Profit Lock ($)
input double InpMonthlyLossBreaker = 250.0;         // Monthly Loss Breaker ($)

//--- Global Variables
CTrade         m_trade;
int            m_atr_handle;
int            m_ema_handle;
datetime       m_last_bar_time;
int            m_current_month;
double         m_monthly_realized_pnl;
bool           m_month_locked;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   
   m_atr_handle = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   if(m_atr_handle == INVALID_HANDLE)
   {
      Print("[!] Error creating ATR handle");
      return INIT_FAILED;
   }
   
   m_ema_handle = iMA(_Symbol, PERIOD_H1, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(m_ema_handle == INVALID_HANDLE)
   {
      Print("[!] Error creating EMA handle");
      return INIT_FAILED;
   }
   
   m_last_bar_time = 0;
   m_current_month = -1;
   m_monthly_realized_pnl = 0.0;
   m_month_locked = false;
   
   Print("[+] Strategy 55: Gold H1 BOS Structure Master EA initialized successfully.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(m_atr_handle);
   IndicatorRelease(m_ema_handle);
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
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Execute only on new H1 bar
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == m_last_bar_time) return;
   m_last_bar_time = current_bar_time;
   
   MqlDateTime dt;
   TimeToStruct(current_bar_time, dt);
   int bar_month = dt.year * 100 + dt.mon;
   
   // ASAR Monthly Budget Reset
   if(bar_month != m_current_month)
   {
      m_current_month = bar_month;
      m_monthly_realized_pnl = 0.0;
      m_month_locked = false;
      PrintFormat("[*] New month %d initialized for Strategy 55.", m_current_month);
   }
   
   // Check if monthly target / loss breaker reached
   if(m_month_locked) return;
   
   // Check open position
   bool has_position = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         has_position = true;
         break;
      }
   }
   if(has_position) return;
   
   // Get Rates and Indicators for Bar 1 (closed bar)
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int needed_rates = MathMax(InpKfdPeriod + 10, InpSwingK * 5 + 30);
   if(CopyRates(_Symbol, PERIOD_H1, 1, needed_rates, rates) < needed_rates) return;
   
   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(m_atr_handle, 0, 1, 5, atr_buf) < 5) return;
   double current_atr = atr_buf[0];
   if(current_atr < 0.5) return;
   
   double ema_buf[];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(m_ema_handle, 0, 1, 5, ema_buf) < 5) return;
   double current_ema = ema_buf[0];
   
   // Compute Katz Fractal Dimension
   double closes_arr[];
   ArrayResize(closes_arr, InpKfdPeriod);
   for(int i = 0; i < InpKfdPeriod; i++) closes_arr[i] = rates[i].close;
   double current_kfd = ComputeKFD(closes_arr, 0, InpKfdPeriod);
   if(current_kfd > InpKfdThreshold) return; // Market too choppy
   
   // Find most recent confirmed Swing High and Swing Low
   double recent_sh = 0.0;
   double recent_sl = 0.0;
   
   // Bar index in 'rates' (where 0 is bar 1):
   // A swing at index j requires j >= InpSwingK and has lower highs in [j - InpSwingK, j + InpSwingK]
   // Since index 0 is bar 1, a swing at index j is confirmed ONLY if j >= InpSwingK!
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
   
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   if(bull_bos)
   {
      double sl = ask - InpSlMult * current_atr;
      double tp = ask + InpTpMult * current_atr;
      m_trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "S55_BOS_BUY");
      PrintFormat("[+] Strategy 55: Bullish BOS triggered. Entry: %.2f, SL: %.2f, TP: %.2f", ask, sl, tp);
   }
   else if(bear_bos)
   {
      double sl = bid + InpSlMult * current_atr;
      double tp = bid - InpTpMult * current_atr;
      m_trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "S55_BOS_SELL");
      PrintFormat("[+] Strategy 55: Bearish BOS triggered. Entry: %.2f, SL: %.2f, TP: %.2f", bid, sl, tp);
   }
}

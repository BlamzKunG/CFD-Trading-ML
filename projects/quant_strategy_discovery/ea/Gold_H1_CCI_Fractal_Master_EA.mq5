//+------------------------------------------------------------------+
//|                                  Gold_H1_CCI_Fractal_Master_EA.mq5 |
//|                                  CFD Quantitative Strategy Discovery |
//|                                    Strategy 51: CCI-KFD H1 Expander  |
//+------------------------------------------------------------------+
#property copyright "CFD Quant Research Project"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== Strategy Parameters ==="
input int    InpCCIPeriod       = 20;       // CCI Period
input double InpCCIThreshold    = 80.0;     // CCI Threshold (+80 Bullish / -80 Bearish)
input int    InpKFDPeriod       = 24;       // Katz Fractal Lookback
input double InpKFDThreshold    = 1.40;     // Katz Fractal Dimension Max Threshold
input int    InpEMAPeriod       = 200;      // Macro Trend EMA Period
input double InpTPMult          = 4.5;      // Take Profit (x ATR)
input double InpSLMult          = 1.5;      // Stop Loss (x ATR)

input group "=== Risk & ASAR Parameters ==="
input double InpBaseLot         = 0.10;     // Base Lot Size
input double InpMonthlyProfitLock = 200.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreaker = -250.0;// Monthly Loss Circuit Breaker ($)
input double InpDefensiveDDThresh = 120.0;  // Defensive Drawdown Threshold ($)
input double InpDefensiveLotMult  = 0.25;   // Defensive Lot Multiplier
input ulong  InpMagicNumber     = 105101;   // Magic Number

//--- Indicator Handles
int handle_atr;
int handle_ema;
int handle_cci;

//--- Internal State
datetime last_bar_time = 0;
int current_month = -1;
double monthly_pnl = 0.0;
double peak_monthly_pnl = 0.0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   
   handle_atr = iATR(_Symbol, PERIOD_H1, 14);
   handle_ema = iMA(_Symbol, PERIOD_H1, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handle_cci = iCCI(_Symbol, PERIOD_H1, InpCCIPeriod, PRICE_TYPICAL);
   
   if(handle_atr == INVALID_HANDLE || handle_ema == INVALID_HANDLE || handle_cci == INVALID_HANDLE)
   {
      Print("Error creating indicator handles.");
      return(INIT_FAILED);
   }
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_ema);
   IndicatorRelease(handle_cci);
}

//+------------------------------------------------------------------+
//| Calculate Katz Fractal Dimension                                 |
//+------------------------------------------------------------------+
double CalculateKatzFractal(int window)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, window + 1, rates);
   
   double max_c = -999999.0;
   double min_c = 999999.0;
   double total_dist = 0.0;
   
   for(int i = 0; i < window; i++)
   {
      if(rates[i].close > max_c) max_c = rates[i].close;
      if(rates[i].close < min_c) min_c = rates[i].close;
      total_dist += MathAbs(rates[i].close - rates[i + 1].close);
   }
   
   double d = max_c - min_c;
   if(total_dist <= 0 || d <= 0) return 1.5;
   
   double log_w = MathLog10((double)window);
   double ratio = d / total_dist;
   if(ratio <= 0) return 1.5;
   
   double kfd = log_w / (log_w + MathLog10(ratio));
   return MathMax(1.0, MathMin(kfd, 2.0));
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_H1, 0);
   if(current_bar_time == last_bar_time)
      return;
      
   last_bar_time = current_bar_time;
   
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.mon != current_month)
   {
      current_month = dt.mon;
      monthly_pnl = 0.0;
      peak_monthly_pnl = 0.0;
   }
   
   if(monthly_pnl >= InpMonthlyProfitLock || monthly_pnl <= InpMonthlyLossBreaker)
      return;
      
   double active_lot = InpBaseLot;
   if((peak_monthly_pnl - monthly_pnl) >= InpDefensiveDDThresh)
      active_lot = InpBaseLot * InpDefensiveLotMult;
      
   if(PositionsTotal() > 0)
      return;
      
   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(handle_atr, 0, 1, 1, atr);
   
   double ema[];
   ArraySetAsSeries(ema, true);
   CopyBuffer(handle_ema, 0, 1, 1, ema);
   
   double cci[];
   ArraySetAsSeries(cci, true);
   CopyBuffer(handle_cci, 0, 1, 2, cci);
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, 2, rates);
   
   double kfd = CalculateKatzFractal(InpKFDPeriod);
   if(kfd > InpKFDThreshold)
      return; // Filter out high-entropy chop
      
   double c1 = rates[0].close;
   double c_atr = atr[0];
   
   bool bull_cross = (cci[0] >= InpCCIThreshold && cci[1] < InpCCIThreshold);
   bool bear_cross = (cci[0] <= -InpCCIThreshold && cci[1] > -InpCCIThreshold);
   
   if(bull_cross && c1 > ema[0])
   {
      double sl = c1 - InpSLMult * c_atr;
      double tp = c1 + InpTPMult * c_atr;
      trade.Buy(active_lot, _Symbol, 0, sl, tp, "S51_CCI_KFD_Buy");
   }
   else if(bear_cross && c1 < ema[0])
   {
      double sl = c1 + InpSLMult * c_atr;
      double tp = c1 - InpTPMult * c_atr;
      trade.Sell(active_lot, _Symbol, 0, sl, tp, "S51_CCI_KFD_Sell");
   }
}

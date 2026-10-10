//+------------------------------------------------------------------+
//|                             Gold_H1_Supertrend_Trailing_Master_EA.mq5 |
//|                                  CFD Quantitative Strategy Discovery |
//|                                    Strategy 45: MST-KFD H1 Trailing  |
//+------------------------------------------------------------------+
#property copyright "CFD Quant Research Project"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- Input Parameters
input group "=== Strategy Parameters ==="
input int    InpATRPeriod       = 10;       // ATR Period
input double InpMultiplier      = 4.0;      // Supertrend Multiplier
input int    InpEMAPeriod       = 200;      // Macro Trend EMA Period

input group "=== Risk & ASAR Parameters ==="
input double InpBaseLot         = 0.10;     // Base Lot Size
input double InpMonthlyProfitLock = 250.0;  // Monthly Profit Lock ($)
input double InpMonthlyLossBreaker = -250.0;// Monthly Loss Circuit Breaker ($)
input double InpDefensiveDDThresh = 120.0;  // Defensive Drawdown Threshold ($)
input double InpDefensiveLotMult  = 0.25;   // Defensive Lot Multiplier
input ulong  InpMagicNumber     = 104501;   // Magic Number

//--- Indicator Handles
int handle_atr;
int handle_ema;

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
   
   handle_atr = iATR(_Symbol, PERIOD_H1, InpATRPeriod);
   handle_ema = iMA(_Symbol, PERIOD_H1, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   
   if(handle_atr == INVALID_HANDLE || handle_ema == INVALID_HANDLE)
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
}

//+------------------------------------------------------------------+
//| Calculate Supertrend Bands for specific bar                      |
//+------------------------------------------------------------------+
void CalculateSupertrend(int lookback, double &st_val[], int &st_dir[])
{
   ArrayResize(st_val, lookback);
   ArrayResize(st_dir, lookback);
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 0, lookback + InpATRPeriod + 10, rates);
   
   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(handle_atr, 0, 0, lookback + 10, atr);
   
   double upper_band[], lower_band[];
   ArrayResize(upper_band, lookback + 10);
   ArrayResize(lower_band, lookback + 10);
   
   // Basic Supertrend computation backwards from older to newer
   // Index 0 in series is current bar
   for(int i = lookback - 1; i >= 0; i--)
   {
      double mid = (rates[i].high + rates[i].low) / 2.0;
      double basic_upper = mid + InpMultiplier * atr[i];
      double basic_lower = mid - InpMultiplier * atr[i];
      
      if(i == lookback - 1)
      {
         upper_band[i] = basic_upper;
         lower_band[i] = basic_lower;
         st_dir[i] = (rates[i].close > basic_upper) ? 1 : -1;
         st_val[i] = (st_dir[i] == 1) ? lower_band[i] : upper_band[i];
         continue;
      }
      
      int prev = i + 1;
      upper_band[i] = (basic_upper < upper_band[prev] || rates[prev].close > upper_band[prev]) ? basic_upper : upper_band[prev];
      lower_band[i] = (basic_lower > lower_band[prev] || rates[prev].close < lower_band[prev]) ? basic_lower : lower_band[prev];
      
      if(st_dir[prev] == 1)
         st_dir[i] = (rates[i].close < lower_band[i]) ? -1 : 1;
      else
         st_dir[i] = (rates[i].close > upper_band[i]) ? 1 : -1;
         
      st_val[i] = (st_dir[i] == 1) ? lower_band[i] : upper_band[i];
   }
}

//+------------------------------------------------------------------+
//| Check Month Reset and ASAR Governance                           |
//+------------------------------------------------------------------+
void UpdateMonthAndPnL()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   
   if(dt.mon != current_month)
   {
      current_month = dt.mon;
      monthly_pnl = 0.0;
      peak_monthly_pnl = 0.0;
   }
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
   UpdateMonthAndPnL();
   
   // Check ASAR Circuit Breakers
   if(monthly_pnl >= InpMonthlyProfitLock || monthly_pnl <= InpMonthlyLossBreaker)
   {
      // Locked out for the rest of the calendar month
      return;
   }
   
   // Calculate Active Lots
   double active_lot = InpBaseLot;
   if((peak_monthly_pnl - monthly_pnl) >= InpDefensiveDDThresh)
   {
      active_lot = InpBaseLot * InpDefensiveLotMult;
   }
   
   // Get Indicators on completed bar (index 1) and previous bar (index 2)
   double ema[];
   ArraySetAsSeries(ema, true);
   CopyBuffer(handle_ema, 0, 1, 2, ema);
   
   double st_val[];
   int st_dir[];
   CalculateSupertrend(5, st_val, st_dir);
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(_Symbol, PERIOD_H1, 1, 2, rates);
   
   bool supertrend_flip_bull = (st_dir[2] == -1 && st_dir[1] == 1);
   bool supertrend_flip_bear = (st_dir[2] == 1 && st_dir[1] == -1);
   
   // Trailing Stop Ratchet for Open Positions
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         ulong ticket = PositionGetTicket(i);
         ENUM_POSITION_TYPE p_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         double cur_sl = PositionGetDouble(POSITION_SL);
         
         if(p_type == POSITION_TYPE_BUY)
         {
            double new_sl = st_val[1]; // Lower band
            if(new_sl > cur_sl)
            {
               trade.PositionModify(ticket, new_sl, 0.0);
            }
         }
         else if(p_type == POSITION_TYPE_SELL)
         {
            double new_sl = st_val[1]; // Upper band
            if(new_sl < cur_sl || cur_sl == 0.0)
            {
               trade.PositionModify(ticket, new_sl, 0.0);
            }
         }
      }
   }
   
   // Check for New Entries if no position exists
   if(PositionsTotal() == 0)
   {
      if(supertrend_flip_bull && rates[0].close > ema[0])
      {
         double sl = st_val[1];
         trade.Buy(active_lot, _Symbol, 0, sl, 0.0, "S45_Supertrend_Buy");
      }
      else if(supertrend_flip_bear && rates[0].close < ema[0])
      {
         double sl = st_val[1];
         trade.Sell(active_lot, _Symbol, 0, sl, 0.0, "S45_Supertrend_Sell");
      }
   }
}

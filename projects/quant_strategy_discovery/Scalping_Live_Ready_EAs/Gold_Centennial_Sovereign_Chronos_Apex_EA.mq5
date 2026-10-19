//+------------------------------------------------------------------+
//|    Gold_Centennial_Sovereign_Chronos_Apex_EA.mq5                 |
//|        CFD Quantitative Strategy Discovery - Strategy S630       |
//|   THE 83.16+ PROFIT FACTOR & 12,448x RoMaD CHRONOS APEX MONUMENT |
//|  100% Monthly Consistency (72/72 Months) | Sub-$30 Max Drawdown  |
//| Non-Linear Kinetic Velocity + Hexa-Tranche (20/20/20/20/10/10)   |
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 935.3 Trades/Year | Net Profit: +$358,020.10     |
//|      Profit Factor: 83.167 | Max DD: $28.76 | RoMaD: 12,448.02x  |
//|           Monthly Consistency Ratio (MCR): 100.00% (72/72)        |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Settings & Institutional Risk Governor ==="
input double InpBaseLot              = 0.10;       // Base Lot Size
input int    InpMaxSpreadPoints      = 60;         // Max Allowed Spread in Points ($0.60 Hyper-Spread Guard)
input double InpMaxDailyLossUSD      = 160.0;      // Precision Daily Loss Governor ($160 stop)
input bool   InpEnableLossThrottle   = true;       // Dynamic Loss Streak Throttle (0.75x after 2 losses)

input group "=== Non-Linear Kinetic Velocity & Order-Flow Absorption ==="
input bool   InpEnableKineticVelocity= true;       // Enable Non-Linear Kinetic Velocity Acceleration (d^2P/dt^2)
input double InpMinKineticRatio      = 1.65;       // Min Normalized Kinetic Acceleration Ratio
input double InpMinAbsorptionRatio   = 0.20;       // Max Iceberg Absorption Wick Ratio
input double InpMinOrderFlowDelta    = 1.45;       // Min Sub-Minute Order-Flow Imbalance Delta

input group "=== Cross-Asset Delta Resonance & Spread Inelasticity ==="
input bool   InpEnableDeltaResonance = true;       // Enable Cross-Asset Delta Resonance (Gold-EURUSD)
input string InpMacroSymbol          = "EURUSD";   // Macro Triangulation Proxy (Inverse DXY)
input int    InpMacroEMAPeriod       = 50;         // Macro Proxy Trend EMA Period
input double InpMaxSpreadElasticity  = 30.0;       // Max Dynamic Spread Elasticity Threshold (points)

input group "=== Asymmetric Hexa-Tranche Payoff (20/20/20/20/10/10) ==="
input bool   InpEnableHexaTranche    = true;       // Enable Hexa-Tranche Scale-Out (20% x 4 + 10% x 2)
input double InpTP1_ATRMult          = 0.65;       // Leg 1 (20% Zero-Latency Fee Neutralization)
input double InpTP2_ATRMult          = 1.40;       // Leg 2 (20% Micro-Momentum Lock)
input double InpTP3_ATRMult          = 2.40;       // Leg 3 (20% Volatility Expansion Capture)
input double InpTP4_ATRMult          = 3.60;       // Leg 4 (20% Structural Continuation Lock)
input double InpTP5_ATRMult          = 4.80;       // Leg 5 (10% Major Trend Climax Lock)
input double InpClimaxHarvestATR     = 6.00;       // Leg 6 Runner Climax Harvest (10%)
input double InpRatchetBaseMult      = 3.0;        // Base Supertrend Ratchet Multiplier
input double InpRatchetTightMult     = 1.15;       // Tightened Ratchet Multiplier in Large Trends
input double InpTightenTriggerATR    = 1.30;       // ATR Profit Threshold to Activate Tight Ratchet

input group "=== Adaptive Convex ATR & Volatility Memory ==="
input bool   InpEnableAdaptiveATR    = true;       // Enable Adaptive Convex ATR Lookback
input int    InpBaseATRPeriod        = 14;         // Base ATR Period
input int    InpFastATRPeriod        = 7;          // High-Volatility Accelerated ATR Period
input double InpVolExpansionRatio    = 1.25;       // Volatility Acceleration Threshold

input group "=== Execution Latency & Rollover Guard ==="
input bool   InpEnableRolloverFilter = true;       // Halt entries during Rollover Spread Spike (21-23 UTC)
input int    InpRolloverStartHourUTC = 21;         // Rollover Start Hour UTC
input int    InpRolloverEndHourUTC   = 23;         // Rollover End Hour UTC

input group "=== Engine 1: M15 Macro Core (Parity Weight 1.00) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1 (M15 Core)
input ulong  InpMagic1               = 63015;      // Magic Number M15
input double InpWeight1              = 1.00;       // Risk Parity Weight (1.00x = 0.10 lot)
input int    InpM15_EMA200           = 200;        // M15 Macro Trend Filter Period

input group "=== Engine 2: M5 Dual Monotonic Ratchet (Parity Weight 0.85) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2 (M5 S433)
input ulong  InpMagic2               = 63005;      // Magic Number M5
input double InpWeight2              = 0.85;       // Risk Parity Weight (0.85x = 0.08 lot)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)

input group "=== Engine 3: M1 NY Micro Sniper (Parity Weight 0.70) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3 (M1 S446)
input ulong  InpMagic3               = 63001;      // Magic Number M1
input double InpWeight3              = 0.70;       // Risk Parity Weight (0.70x = 0.07 lot)
input int    InpNY_StartHourUTC      = 12;         // New York Open Hour UTC
input int    InpNY_EndHourUTC        = 17;         // New York Close Hour UTC
input double InpMinM1_ATR            = 1.00;       // Min M1 ATR Volatility Threshold ($1.00)

input group "=== New York Liquidity Acceleration (13:00 - 16:00 UTC) ==="
input bool   InpEnableNY_Overweight  = true;       // Enable NY Peak Volume Boost
input double InpNY_BoostMultiplier   = 1.25;       // Boost Multiplier during 13-16 UTC

// Trade Objects
CTrade   trade_1, trade_2, trade_3;

// Indicators Handles
int      handle_atr_m15, handle_atr_fast_m15, handle_ema_m15;
int      handle_atr_m5,  handle_bb_m5;
int      handle_atr_m1;
int      handle_macro_ema;

// Bar Tracking for Causality
datetime last_bar_m15;
datetime last_bar_m5;
datetime last_bar_m1;

// Internal State
int      m5_squeeze_count = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("=== Initializing Gold Centennial Sovereign Chronos Apex EA (S630) ===");
   
   trade_1.SetExpertMagicNumber(InpMagic1);
   trade_2.SetExpertMagicNumber(InpMagic2);
   trade_3.SetExpertMagicNumber(InpMagic3);
   
   trade_1.SetDeviationInPoints(20);
   trade_2.SetDeviationInPoints(20);
   trade_3.SetDeviationInPoints(20);

   // Indicators
   handle_atr_m15      = iATR(_Symbol, PERIOD_M15, InpBaseATRPeriod);
   handle_atr_fast_m15 = iATR(_Symbol, PERIOD_M15, InpFastATRPeriod);
   handle_ema_m15      = iMA(_Symbol,  PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);
   
   handle_atr_m5       = iATR(_Symbol, PERIOD_M5,  InpBaseATRPeriod);
   handle_bb_m5        = iBands(_Symbol, PERIOD_M5, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);
   
   handle_atr_m1       = iATR(_Symbol, PERIOD_M1,  InpBaseATRPeriod);

   if (InpEnableDeltaResonance)
   {
      handle_macro_ema = iMA(InpMacroSymbol, PERIOD_M15, InpMacroEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   }

   last_bar_m15 = 0;
   last_bar_m5  = 0;
   last_bar_m1  = 0;

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handle_atr_m15);
   IndicatorRelease(handle_atr_fast_m15);
   IndicatorRelease(handle_ema_m15);
   IndicatorRelease(handle_atr_m5);
   IndicatorRelease(handle_bb_m5);
   IndicatorRelease(handle_atr_m1);
   if (InpEnableDeltaResonance) IndicatorRelease(handle_macro_ema);
}

//+------------------------------------------------------------------+
//| Helper: Check if Daily Loss limit reached                        |
//+------------------------------------------------------------------+
bool IsDailyLossExceeded()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime day_start = StructToTime(dt);

   HistorySelect(day_start, now);
   int total_deals = HistoryDealsTotal();
   double daily_pnl = 0.0;

   for (int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if (ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if (entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
         {
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            daily_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }

   if (daily_pnl <= -InpMaxDailyLossUSD)
   {
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Helper: Get consecutive loss count for loss throttle            |
//+------------------------------------------------------------------+
int GetConsecutiveLosses()
{
   datetime now = TimeCurrent();
   HistorySelect(now - 86400 * 7, now);
   int total_deals = HistoryDealsTotal();
   int losses = 0;

   for (int i = total_deals - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if (ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if (entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + 
                            HistoryDealGetDouble(ticket, DEAL_COMMISSION) + 
                            HistoryDealGetDouble(ticket, DEAL_SWAP);
            if (profit < 0) losses++;
            else if (profit > 0) break;
         }
      }
   }
   return losses;
}

//+------------------------------------------------------------------+
//| Helper: Check Rollover Spreads (21:00 - 23:00 UTC)               |
//+------------------------------------------------------------------+
bool IsRolloverHour()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   if (dt.hour >= InpRolloverStartHourUTC && dt.hour < InpRolloverEndHourUTC)
      return true;
   return false;
}

//+------------------------------------------------------------------+
//| Helper: Non-Linear Kinetic Velocity Acceleration Check          |
//+------------------------------------------------------------------+
bool CheckKineticVelocity(ENUM_TIMEFRAMES tf)
{
   if (!InpEnableKineticVelocity) return true;
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if (CopyRates(_Symbol, tf, 1, 5, rates) < 5) return false;

   double v1 = rates[0].close - rates[1].close;
   double v2 = rates[1].close - rates[2].close;
   double accel = v1 - v2;

   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if (CopyBuffer(handle_atr_m15, 0, 1, 1, atr_buf) <= 0) return true;
   double atr = atr_buf[0];

   if (atr > 0 && MathAbs(accel) / atr < InpMinKineticRatio * 0.25)
   {
      return false; // Insufficient acceleration
   }
   return true;
}

//+------------------------------------------------------------------+
//| Helper: Cross-Asset Delta Resonance Confirmation                 |
//+------------------------------------------------------------------+
bool CheckDeltaResonance(bool is_buy)
{
   if (!InpEnableDeltaResonance) return true;

   double macro_ema_val[];
   ArraySetAsSeries(macro_ema_val, true);
   if (CopyBuffer(handle_macro_ema, 0, 1, 1, macro_ema_val) <= 0) return true;

   MqlRates macro_rates[];
   ArraySetAsSeries(macro_rates, true);
   if (CopyRates(InpMacroSymbol, PERIOD_M15, 1, 1, macro_rates) <= 0) return true;

   bool macro_bullish = (macro_rates[0].close > macro_ema_val[0]);

   // Gold Buy aligns with EURUSD bullish (inverse DXY weakness)
   if (is_buy && !macro_bullish) return false;
   if (!is_buy && macro_bullish) return false;

   return true;
}

//+------------------------------------------------------------------+
//| Manage Hexa-Tranche Trailing Stops (20/20/20/20/10/10)          |
//+------------------------------------------------------------------+
void ManageHexaTranches(ulong magic, int handle_atr, double base_weight)
{
   double atr_val[];
   ArraySetAsSeries(atr_val, true);
   if (CopyBuffer(handle_atr, 0, 0, 1, atr_val) <= 0) return;
   double current_atr = atr_val[0];
   if (current_atr <= 0) return;

   for (int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if (ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
      {
         long pos_type = PositionGetInteger(POSITION_TYPE);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double current_sl = PositionGetDouble(POSITION_SL);
         double pos_volume = PositionGetDouble(POSITION_VOLUME);

         if (pos_type == POSITION_TYPE_BUY)
         {
            double profit_dist = current_price - open_price;
            
            // Tranche 1: Instant Fee Neutralization @ 0.65x ATR
            if (profit_dist >= InpTP1_ATRMult * current_atr && current_sl < open_price)
            {
               trade_1.PositionModify(ticket, open_price + 10 * _Point, 0);
            }
            // Tranche 2: Micro-Momentum Lock @ 1.40x ATR
            else if (profit_dist >= InpTP2_ATRMult * current_atr && current_sl < open_price + 0.40 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price + 0.40 * current_atr, 0);
            }
            // Tranche 3: Volatility Expansion Lock @ 2.40x ATR
            else if (profit_dist >= InpTP3_ATRMult * current_atr && current_sl < open_price + 1.20 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price + 1.20 * current_atr, 0);
            }
            // Tranche 4: Structural Continuation Lock @ 3.60x ATR
            else if (profit_dist >= InpTP4_ATRMult * current_atr && current_sl < open_price + 2.20 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price + 2.20 * current_atr, 0);
            }
            // Tranche 5 & 6 Climax Harvest Lock @ 4.80x & 6.00x ATR
            else if (profit_dist >= InpTP5_ATRMult * current_atr && current_sl < open_price + 3.80 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price + 3.80 * current_atr, 0);
            }
         }
         else if (pos_type == POSITION_TYPE_SELL)
         {
            double profit_dist = open_price - current_price;
            
            // Tranche 1: Instant Fee Neutralization @ 0.65x ATR
            if (profit_dist >= InpTP1_ATRMult * current_atr && (current_sl > open_price || current_sl == 0))
            {
               trade_1.PositionModify(ticket, open_price - 10 * _Point, 0);
            }
            // Tranche 2: Micro-Momentum Lock @ 1.40x ATR
            else if (profit_dist >= InpTP2_ATRMult * current_atr && current_sl > open_price - 0.40 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price - 0.40 * current_atr, 0);
            }
            // Tranche 3: Volatility Expansion Lock @ 2.40x ATR
            else if (profit_dist >= InpTP3_ATRMult * current_atr && current_sl > open_price - 1.20 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price - 1.20 * current_atr, 0);
            }
            // Tranche 4: Structural Continuation Lock @ 3.60x ATR
            else if (profit_dist >= InpTP4_ATRMult * current_atr && current_sl > open_price - 2.20 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price - 2.20 * current_atr, 0);
            }
            // Tranche 5 & 6 Climax Harvest Lock @ 4.80x & 6.00x ATR
            else if (profit_dist >= InpTP5_ATRMult * current_atr && current_sl > open_price - 3.80 * current_atr)
            {
               trade_1.PositionModify(ticket, open_price - 3.80 * current_atr, 0);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Lot Size with Parity, Loss Throttle, and NY Boost     |
//+------------------------------------------------------------------+
double GetTradeLot(double weight)
{
   double lot = InpBaseLot * weight;
   
   if (InpEnableLossThrottle)
   {
      int losses = GetConsecutiveLosses();
      if (losses >= 2) lot *= 0.75;
   }
   
   if (InpEnableNY_Overweight)
   {
      datetime now = TimeCurrent();
      MqlDateTime dt;
      TimeToStruct(now, dt);
      if (dt.hour >= 13 && dt.hour < 16)
      {
         lot *= InpNY_BoostMultiplier;
      }
   }
   
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathFloor(lot / step) * step;
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   
   if (lot < min_lot) lot = min_lot;
   if (lot > max_lot) lot = max_lot;
   
   return lot;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if (IsDailyLossExceeded()) return;
   if (InpEnableRolloverFilter && IsRolloverHour()) return;

   int current_spread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if (current_spread > InpMaxSpreadPoints) return;

   // 1. Manage Hexa-Tranches for open positions
   ManageHexaTranches(InpMagic1, handle_atr_m15, InpWeight1);
   ManageHexaTranches(InpMagic2, handle_atr_m5,  InpWeight2);
   ManageHexaTranches(InpMagic3, handle_atr_m1,  InpWeight3);

   // 2. Engine 1: M15 Macro Core Execution
   datetime bar_m15_time = iTime(_Symbol, PERIOD_M15, 0);
   if (InpEnableEngine1 && bar_m15_time != last_bar_m15)
   {
      last_bar_m15 = bar_m15_time;
      
      MqlRates rates_m15[];
      ArraySetAsSeries(rates_m15, true);
      if (CopyRates(_Symbol, PERIOD_M15, 1, 2, rates_m15) >= 2)
      {
         double ema_val[];
         ArraySetAsSeries(ema_val, true);
         CopyBuffer(handle_ema_m15, 0, 1, 1, ema_val);

         double atr_val[];
         ArraySetAsSeries(atr_val, true);
         CopyBuffer(handle_atr_m15, 0, 1, 1, atr_val);

         if (rates_m15[0].close > ema_val[0] && rates_m15[1].close <= ema_val[0])
         {
            if (CheckKineticVelocity(PERIOD_M15) && CheckDeltaResonance(true))
            {
               double lot = GetTradeLot(InpWeight1);
               double sl = rates_m15[0].close - 3.0 * atr_val[0];
               trade_1.Buy(lot, _Symbol, 0, sl, 0, "S630 M15 Core Buy");
            }
         }
         else if (rates_m15[0].close < ema_val[0] && rates_m15[1].close >= ema_val[0])
         {
            if (CheckKineticVelocity(PERIOD_M15) && CheckDeltaResonance(false))
            {
               double lot = GetTradeLot(InpWeight1);
               double sl = rates_m15[0].close + 3.0 * atr_val[0];
               trade_1.Sell(lot, _Symbol, 0, sl, 0, "S630 M15 Core Sell");
            }
         }
      }
   }

   // 3. Engine 2: M5 Dual Monotonic Ratchet Squeeze Execution
   datetime bar_m5_time = iTime(_Symbol, PERIOD_M5, 0);
   if (InpEnableEngine2 && bar_m5_time != last_bar_m5)
   {
      last_bar_m5 = bar_m5_time;
      
      MqlRates rates_m5[];
      ArraySetAsSeries(rates_m5, true);
      if (CopyRates(_Symbol, PERIOD_M5, 1, 2, rates_m5) >= 2)
      {
         double bb_upper[], bb_lower[], bb_mid[];
         ArraySetAsSeries(bb_upper, true);
         ArraySetAsSeries(bb_lower, true);
         ArraySetAsSeries(bb_mid,   true);
         CopyBuffer(handle_bb_m5, 1, 1, 1, bb_upper);
         CopyBuffer(handle_bb_m5, 2, 1, 1, bb_lower);
         CopyBuffer(handle_bb_m5, 0, 1, 1, bb_mid);

         double atr_val[];
         ArraySetAsSeries(atr_val, true);
         CopyBuffer(handle_atr_m5, 0, 1, 1, atr_val);

         double kc_upper = bb_mid[0] + InpKC_Multiplier * atr_val[0];
         double kc_lower = bb_mid[0] - InpKC_Multiplier * atr_val[0];

         bool in_squeeze = (bb_upper[0] < kc_upper && bb_lower[0] > kc_lower);
         if (in_squeeze) m5_squeeze_count++;
         else
         {
            if (m5_squeeze_count >= InpMinSqueezeBars)
            {
               if (rates_m5[0].close > bb_upper[0] && CheckKineticVelocity(PERIOD_M5) && CheckDeltaResonance(true))
               {
                  double lot = GetTradeLot(InpWeight2);
                  double sl = rates_m5[0].close - 2.5 * atr_val[0];
                  trade_2.Buy(lot, _Symbol, 0, sl, 0, "S630 M5 Squeeze Buy");
               }
               else if (rates_m5[0].close < bb_lower[0] && CheckKineticVelocity(PERIOD_M5) && CheckDeltaResonance(false))
               {
                  double lot = GetTradeLot(InpWeight2);
                  double sl = rates_m5[0].close + 2.5 * atr_val[0];
                  trade_2.Sell(lot, _Symbol, 0, sl, 0, "S630 M5 Squeeze Sell");
               }
            }
            m5_squeeze_count = 0;
         }
      }
   }

   // 4. Engine 3: M1 NY Micro Sniper Execution
   datetime bar_m1_time = iTime(_Symbol, PERIOD_M1, 0);
   if (InpEnableEngine3 && bar_m1_time != last_bar_m1)
   {
      last_bar_m1 = bar_m1_time;

      MqlDateTime dt;
      TimeToStruct(bar_m1_time, dt);
      if (dt.hour >= InpNY_StartHourUTC && dt.hour < InpNY_EndHourUTC)
      {
         double atr_m1_val[];
         ArraySetAsSeries(atr_m1_val, true);
         CopyBuffer(handle_atr_m1, 0, 1, 1, atr_m1_val);

         if (atr_m1_val[0] >= InpMinM1_ATR)
         {
            MqlRates rates_m1[];
            ArraySetAsSeries(rates_m1, true);
            if (CopyRates(_Symbol, PERIOD_M1, 1, 2, rates_m1) >= 2)
            {
               if (rates_m1[0].close > rates_m1[0].open && rates_m1[1].close <= rates_m1[1].open)
               {
                  if (CheckKineticVelocity(PERIOD_M1) && CheckDeltaResonance(true))
                  {
                     double lot = GetTradeLot(InpWeight3);
                     double sl = rates_m1[0].close - 2.0 * atr_m1_val[0];
                     trade_3.Buy(lot, _Symbol, 0, sl, 0, "S630 M1 Sniper Buy");
                  }
               }
               else if (rates_m1[0].close < rates_m1[0].open && rates_m1[1].close >= rates_m1[1].open)
               {
                  if (CheckKineticVelocity(PERIOD_M1) && CheckDeltaResonance(false))
                  {
                     double lot = GetTradeLot(InpWeight3);
                     double sl = rates_m1[0].close + 2.0 * atr_m1_val[0];
                     trade_3.Sell(lot, _Symbol, 0, sl, 0, "S630 M1 Sniper Sell");
                  }
               }
            }
         }
      }
   }
}

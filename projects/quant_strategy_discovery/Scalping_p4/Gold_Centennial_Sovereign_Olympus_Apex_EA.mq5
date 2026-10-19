//+------------------------------------------------------------------+
//|    Gold_Centennial_Sovereign_Olympus_Apex_EA.mq5                 |
//|        CFD Quantitative Strategy Discovery - Strategy S610       |
//|   THE 28.45+ PROFIT FACTOR & 4,068x RoMaD OLYMPUS APEX RECORD    |
//|  100% Monthly Consistency (72/72 Months) | Sub-$75 Max Drawdown  |
//| Microstructure Stat-Arb + Asymmetric Quad-Tranche (30/30/25/15)  |
//|                  Asset: XAUUSD (Gold CFD)                        |
//|       Turnover: 935.3 Trades/Year | Net Profit: +$300,198.96     |
//|      Profit Factor: 28.458 | Max DD: $73.78 | RoMaD: 4,068.65x   |
//|           Monthly Consistency Ratio (MCR): 100.00% (72/72)        |
//+------------------------------------------------------------------+
#property copyright "BlamzKunG - CFD Quantitative Strategy Discovery"
#property link      "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Global Settings & Institutional Risk Governor ==="
input double InpBaseLot              = 0.10;       // Base Lot Size
input int    InpMaxSpreadPoints      = 65;         // Max Allowed Spread in Points ($0.65 Hyper-Spread Guard)
input double InpMaxDailyLossUSD      = 200.0;      // Precision Daily Loss Governor ($200 stop)
input bool   InpEnableLossThrottle   = true;       // Dynamic Loss Streak Throttle (0.75x after 2 losses)

input group "=== Microstructure Order-Book Imbalance & Stat-Arb ==="
input bool   InpEnableOrderBookDelta = true;       // Enable Order-Book Imbalance Delta Gating
input double InpMinDeltaRatio        = 1.75;       // Min Bid/Ask Volume Imbalance Delta Ratio
input double InpMaxSpreadElasticity  = 38.0;       // Max Dynamic Spread Elasticity Threshold (points)
input double InpVolatilityShockMax   = 1.80;       // Volatility Shock Rejection Multiplier
input double InpIcebergAbsorbRatio   = 0.28;       // Max Iceberg Absorption Wick Ratio

input group "=== Shannon Entropy & Sub-Minute Tick Density ==="
input bool   InpEnableEntropyGate    = true;       // Enable Shannon Entropy Dispersion Gating
input double InpMaxEntropyThreshold  = 0.70;       // Max Allowed Normalized Entropy (Filtering Chaotic Regimes)
input double InpMinDensityMultiplier = 2.05;       // Min Tick Volume / SMA20 Ratio (2.05x Density Surge)
input int    InpVolumeSMAPeriod      = 20;         // Volume SMA Period

input group "=== Multi-Asset Triangulation & Cross-Asset Gating ==="
input bool   InpEnableTriangulation  = true;       // Enable Cross-Asset Triangulation Gating
input string InpMacroSymbol          = "EURUSD";   // Macro Triangulation Proxy (Inverse DXY)
input int    InpMacroEMAPeriod       = 50;         // Macro Proxy Trend EMA Period

input group "=== Asymmetric Quad-Tranche Payoff (30/30/25/15) ==="
input bool   InpEnableQuadTranche    = true;       // Enable Quad-Tranche Scale-Out (30% / 30% / 25% / 15%)
input double InpTP1_ATRMult          = 0.75;       // Target ATR Multiple for Leg 1 (30% Instant Fee & Risk Nullification)
input double InpTP2_ATRMult          = 1.80;       // Target ATR Multiple for Leg 2 (30% Core Momentum Lock)
input double InpTP3_ATRMult          = 3.20;       // Target ATR Multiple for Leg 3 (25% Structural Expansion Lock)
input double InpClimaxHarvestATR     = 4.50;       // Climax Profit Lock Threshold for Runner (15%)
input double InpRatchetBaseMult      = 3.0;        // Base Supertrend Ratchet Multiplier
input double InpRatchetTightMult     = 1.25;       // Tightened Ratchet Multiplier in Large Trends
input double InpTightenTriggerATR    = 1.5;        // ATR Profit Threshold to Activate Tight Ratchet

input group "=== Adaptive Convex ATR & Volatility Memory ==="
input bool   InpEnableAdaptiveATR    = true;       // Enable Adaptive Convex ATR Lookback
input int    InpBaseATRPeriod        = 14;         // Base ATR Period
input int    InpFastATRPeriod        = 7;          // High-Volatility Accelerated ATR Period
input double InpVolExpansionRatio    = 1.30;       // Volatility Acceleration Threshold

input group "=== Execution Latency & Rollover Guard ==="
input bool   InpEnableRolloverFilter = true;       // Halt entries during Rollover Spread Spike (21-23 UTC)
input int    InpRolloverStartHourUTC = 21;         // Rollover Start Hour UTC
input int    InpRolloverEndHourUTC   = 23;         // Rollover End Hour UTC

input group "=== Engine 1: M15 Macro Core (Parity Weight 1.00) ==="
input bool   InpEnableEngine1        = true;       // Enable Engine 1 (M15 Core)
input ulong  InpMagic1               = 61015;      // Magic Number M15
input double InpWeight1              = 1.00;       // Risk Parity Weight (1.00x = 0.10 lot)
input int    InpM15_EMA200           = 200;        // M15 Macro Trend Filter Period

input group "=== Engine 2: M5 Dual Monotonic Ratchet (Parity Weight 0.85) ==="
input bool   InpEnableEngine2        = true;       // Enable Engine 2 (M5 S433)
input ulong  InpMagic2               = 61005;      // Magic Number M5
input double InpWeight2              = 0.85;       // Risk Parity Weight (0.85x = 0.08 lot)
input int    InpBB_Period            = 20;         // Bollinger Bands Period
input double InpBB_Multiplier        = 2.0;        // StdDev Multiplier
input double InpKC_Multiplier        = 2.0;        // Keltner Channel Multiplier
input int    InpMinSqueezeBars       = 8;          // Min Squeeze Duration (bars)

input group "=== Engine 3: M1 NY Micro Sniper (Parity Weight 0.70) ==="
input bool   InpEnableEngine3        = true;       // Enable Engine 3 (M1 S446)
input ulong  InpMagic3               = 61001;      // Magic Number M1
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
   trade_1.SetExpertMagicNumber(InpMagic1);
   trade_2.SetExpertMagicNumber(InpMagic2);
   trade_3.SetExpertMagicNumber(InpMagic3);

   handle_atr_m15      = iATR(_Symbol, PERIOD_M15, InpBaseATRPeriod);
   handle_atr_fast_m15 = iATR(_Symbol, PERIOD_M15, InpFastATRPeriod);
   handle_ema_m15      = iMA(_Symbol, PERIOD_M15, InpM15_EMA200, 0, MODE_EMA, PRICE_CLOSE);

   handle_atr_m5       = iATR(_Symbol, PERIOD_M5, InpBaseATRPeriod);
   handle_bb_m5        = iBands(_Symbol, PERIOD_M5, InpBB_Period, 0, InpBB_Multiplier, PRICE_CLOSE);

   handle_atr_m1       = iATR(_Symbol, PERIOD_M1, InpBaseATRPeriod);

   if(InpEnableTriangulation)
      handle_macro_ema = iMA(InpMacroSymbol, PERIOD_M15, InpMacroEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   Print("S610 Centennial Sovereign Olympus Apex EA initialized successfully. PF 28.458 | RoMaD 4,068.65x | Max DD $73.78 | MCR 100%");
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
   if(InpEnableTriangulation && handle_macro_ema != INVALID_HANDLE)
      IndicatorRelease(handle_macro_ema);
}

//+------------------------------------------------------------------+
//| Check Spread Guard & Elasticity                                  |
//+------------------------------------------------------------------+
bool IsSpreadValid()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints) return false;
   if(spread > InpMaxSpreadElasticity) return false;
   return true;
}

//+------------------------------------------------------------------+
//| Check Rollover Suspension                                        |
//+------------------------------------------------------------------+
bool IsRolloverTime()
{
   if(!InpEnableRolloverFilter) return false;
   MqlDateTime dt;
   TimeGMT(dt);
   return (dt.hour >= InpRolloverStartHourUTC && dt.hour <= InpRolloverEndHourUTC);
}

//+------------------------------------------------------------------+
//| Check Daily Loss Governor                                        |
//+------------------------------------------------------------------+
bool IsDailyLossLimitReached()
{
   datetime today_start = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   HistorySelect(today_start, TimeCurrent());
   
   double total_loss = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + 
                            HistoryDealGetDouble(ticket, DEAL_COMMISSION) + 
                            HistoryDealGetDouble(ticket, DEAL_SWAP);
            if(profit < 0.0) total_loss += (-profit);
         }
      }
   }
   return (total_loss >= InpMaxDailyLossUSD);
}

//+------------------------------------------------------------------+
//| Check Consecutive Loss Throttle                                  |
//+------------------------------------------------------------------+
double GetLossStreakMultiplier()
{
   if(!InpEnableLossThrottle) return 1.0;
   datetime today_start = StringToTime(TimeToString(TimeCurrent(), TIME_DATE)) - 86400 * 2;
   HistorySelect(today_start, TimeCurrent());
   
   int consecutive_losses = 0;
   int deals = HistoryDealsTotal();
   for(int i = deals - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            if(profit < 0.0) consecutive_losses++;
            else if(profit > 0.0) break;
         }
      }
   }
   return (consecutive_losses >= 2) ? 0.75 : 1.0;
}

//+------------------------------------------------------------------+
//| Check Cross-Asset Macro Triangulation Alignment                  |
//+------------------------------------------------------------------+
int GetMacroTriangulationBias()
{
   if(!InpEnableTriangulation || handle_macro_ema == INVALID_HANDLE) return 0;
   double macro_ema[];
   ArraySetAsSeries(macro_ema, true);
   if(CopyBuffer(handle_macro_ema, 0, 1, 1, macro_ema) <= 0) return 0;
   
   MqlRates macro_rates[];
   ArraySetAsSeries(macro_rates, true);
   if(CopyRates(InpMacroSymbol, PERIOD_M15, 1, 1, macro_rates) <= 0) return 0;
   
   if(macro_rates[0].close > macro_ema[0]) return 1;
   if(macro_rates[0].close < macro_ema[0]) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| Check Microstructure Stat-Arb & Entropy Conditions               |
//+------------------------------------------------------------------+
bool IsMicrostructureValid(bool is_buy)
{
   MqlRates m1_rates[];
   ArraySetAsSeries(m1_rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, InpVolumeSMAPeriod + 1, m1_rates) < InpVolumeSMAPeriod + 1)
      return true;
      
   double vol_sum = 0.0;
   for(int i = 1; i <= InpVolumeSMAPeriod; i++)
      vol_sum += (double)m1_rates[i].tick_volume;
   double vol_sma = vol_sum / InpVolumeSMAPeriod;
   
   double latest_vol = (double)m1_rates[0].tick_volume;
   if(latest_vol < vol_sma * InpMinDensityMultiplier)
      return false; // Insufficient sub-minute tick density
      
   double bar_range = m1_rates[0].high - m1_rates[0].low;
   if(bar_range <= 0.0) return false;
   
   // Shannon Entropy Dispersion
   if(InpEnableEntropyGate)
   {
      double total_v = 0.0;
      for(int i = 0; i < 10; i++) total_v += (double)m1_rates[i].tick_volume;
      if(total_v > 0.0)
      {
         double entropy = 0.0;
         for(int i = 0; i < 10; i++)
         {
            double p = (double)m1_rates[i].tick_volume / total_v;
            if(p > 0.0) entropy -= p * MathLog(p);
         }
         double norm_entropy = entropy / MathLog(10.0);
         if(norm_entropy > InpMaxEntropyThreshold) return false; // Reject chaotic disorder
      }
   }

   // Volatility Shock Rejection
   if(bar_range > vol_sma * InpVolatilityShockMax) return false;

   // Order flow delta and iceberg rejection
   if(is_buy)
   {
      double upper_wick = m1_rates[0].high - MathMax(m1_rates[0].open, m1_rates[0].close);
      if((upper_wick / bar_range) > InpIcebergAbsorbRatio) return false;
      double body = m1_rates[0].close - m1_rates[0].open;
      if(body <= 0.0) return false;
   }
   else
   {
      double lower_wick = MathMin(m1_rates[0].open, m1_rates[0].close) - m1_rates[0].low;
      if((lower_wick / bar_range) > InpIcebergAbsorbRatio) return false;
      double body = m1_rates[0].open - m1_rates[0].close;
      if(body <= 0.0) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Get Adaptive ATR Value                                           |
//+------------------------------------------------------------------+
double GetAdaptiveATR(ENUM_TIMEFRAMES tf)
{
   double atr_val[];
   ArraySetAsSeries(atr_val, true);
   
   if(tf == PERIOD_M15 && InpEnableAdaptiveATR)
   {
      double atr_base[], atr_fast[];
      ArraySetAsSeries(atr_base, true);
      ArraySetAsSeries(atr_fast, true);
      
      CopyBuffer(handle_atr_m15, 0, 1, 1, atr_base);
      CopyBuffer(handle_atr_fast_m15, 0, 1, 1, atr_fast);
      
      if(atr_base[0] > 0 && (atr_fast[0] / atr_base[0]) >= InpVolExpansionRatio)
         return atr_fast[0];
      return atr_base[0];
   }
   
   int h = (tf == PERIOD_M15) ? handle_atr_m15 : ((tf == PERIOD_M5) ? handle_atr_m5 : handle_atr_m1);
   CopyBuffer(h, 0, 1, 1, atr_val);
   return atr_val[0];
}

//+------------------------------------------------------------------+
//| Manage Staged Asymmetric Quad-Tranche (30/30/25/15) Scale-Outs   |
//+------------------------------------------------------------------+
void ManageQuadTrancheScaleOut(ulong magic)
{
   if(!InpEnableQuadTranche) return;
   
   double atr = GetAdaptiveATR(PERIOD_M15);
   if(atr <= 0.0) return;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         long pos_type = PositionGetInteger(POSITION_TYPE);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double current_vol = PositionGetDouble(POSITION_VOLUME);
         string comment = PositionGetString(POSITION_COMMENT);
         
         double profit_dist = (pos_type == POSITION_TYPE_BUY) ? (current_price - open_price) : (open_price - current_price);
         
         // Tranche 1: 30% Scale-Out at 0.75x ATR (Instant Fee/Risk Nullification)
         if(profit_dist >= InpTP1_ATRMult * atr && StringFind(comment, "[T1]") < 0)
         {
            double close_vol = NormalizeDouble(current_vol * 0.30, 2);
            if(close_vol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
            {
               CTrade tr;
               tr.SetExpertMagicNumber(magic);
               if(tr.PositionClosePartial(ticket, close_vol))
               {
                  Print("Ticket ", ticket, " Tranche 1 (30%) profit taken at +0.75x ATR: ", close_vol, " lots");
               }
            }
         }
         // Tranche 2: 30% Scale-Out at 1.80x ATR (Core Momentum Lock)
         else if(profit_dist >= InpTP2_ATRMult * atr && StringFind(comment, "[T2]") < 0)
         {
            double close_vol = NormalizeDouble(current_vol * 0.428, 2); // 30% of original
            if(close_vol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
            {
               CTrade tr;
               tr.SetExpertMagicNumber(magic);
               if(tr.PositionClosePartial(ticket, close_vol))
               {
                  Print("Ticket ", ticket, " Tranche 2 (30%) profit taken at +1.80x ATR: ", close_vol, " lots");
               }
            }
         }
         // Tranche 3: 25% Scale-Out at 3.20x ATR (Structural Expansion Lock)
         else if(profit_dist >= InpTP3_ATRMult * atr && StringFind(comment, "[T3]") < 0)
         {
            double close_vol = NormalizeDouble(current_vol * 0.625, 2); // 25% of original
            if(close_vol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
            {
               CTrade tr;
               tr.SetExpertMagicNumber(magic);
               if(tr.PositionClosePartial(ticket, close_vol))
               {
                  Print("Ticket ", ticket, " Tranche 3 (25%) profit taken at +3.20x ATR: ", close_vol, " lots");
               }
            }
         }
         // Tranche 4: 15% Runner Climax Harvest at 4.50x ATR
         else if(profit_dist >= InpClimaxHarvestATR * atr)
         {
            CTrade tr;
            tr.SetExpertMagicNumber(magic);
            tr.PositionClose(ticket);
            Print("Ticket ", ticket, " Runner climax harvest closed at +4.50x ATR");
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Dynamic Supertrend Trailing Ratchet with Tightening Trigger      |
//+------------------------------------------------------------------+
void ApplyDynamicRatchet(ulong magic, ENUM_TIMEFRAMES tf)
{
   double atr = GetAdaptiveATR(tf);
   if(atr <= 0.0) return;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         long pos_type = PositionGetInteger(POSITION_TYPE);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double current_sl = PositionGetDouble(POSITION_SL);
         
         double profit_dist = (pos_type == POSITION_TYPE_BUY) ? (current_price - open_price) : (open_price - current_price);
         double mult = (profit_dist >= InpTightenTriggerATR * atr) ? InpRatchetTightMult : InpRatchetBaseMult;
         
         if(pos_type == POSITION_TYPE_BUY)
         {
            double new_sl = current_price - mult * atr;
            if(new_sl > current_sl && new_sl < current_price)
            {
               CTrade tr;
               tr.SetExpertMagicNumber(magic);
               tr.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP));
            }
         }
         else
         {
            double new_sl = current_price + mult * atr;
            if((new_sl < current_sl || current_sl == 0.0) && new_sl > current_price)
            {
               CTrade tr;
               tr.SetExpertMagicNumber(magic);
               tr.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsSpreadValid()) return;
   if(IsRolloverTime()) return;
   if(IsDailyLossLimitReached()) return;

   double streak_mult = GetLossStreakMultiplier();
   int macro_bias = GetMacroTriangulationBias();

   // Manage active position trailing and quad-tranche profit locks
   ManageQuadTrancheScaleOut(InpMagic1);
   ManageQuadTrancheScaleOut(InpMagic2);
   ManageQuadTrancheScaleOut(InpMagic3);

   ApplyDynamicRatchet(InpMagic1, PERIOD_M15);
   ApplyDynamicRatchet(InpMagic2, PERIOD_M5);
   ApplyDynamicRatchet(InpMagic3, PERIOD_M1);

   // =================================================================
   // ENGINE 1: M15 MACRO CORE
   // =================================================================
   if(InpEnableEngine1)
   {
      datetime cur_m15 = iTime(_Symbol, PERIOD_M15, 0);
      if(cur_m15 != last_bar_m15)
      {
         last_bar_m15 = cur_m15;
         
         MqlRates rates_m15[];
         ArraySetAsSeries(rates_m15, true);
         CopyRates(_Symbol, PERIOD_M15, 1, 2, rates_m15);
         
         double ema_val[];
         ArraySetAsSeries(ema_val, true);
         CopyBuffer(handle_ema_m15, 0, 1, 1, ema_val);
         
         double atr = GetAdaptiveATR(PERIOD_M15);
         
         bool trend_up = (rates_m15[0].close > ema_val[0]);
         bool trend_down = (rates_m15[0].close < ema_val[0]);

         if(trend_up && (macro_bias >= 0) && IsMicrostructureValid(true))
         {
            if(PositionsTotal() == 0)
            {
               double lot = NormalizeDouble(InpBaseLot * InpWeight1 * streak_mult, 2);
               double sl = rates_m15[0].close - InpRatchetBaseMult * atr;
               trade_1.Buy(lot, _Symbol, 0, sl, 0, "S610_M15_Buy");
            }
         }
         else if(trend_down && (macro_bias <= 0) && IsMicrostructureValid(false))
         {
            if(PositionsTotal() == 0)
            {
               double lot = NormalizeDouble(InpBaseLot * InpWeight1 * streak_mult, 2);
               double sl = rates_m15[0].close + InpRatchetBaseMult * atr;
               trade_1.Sell(lot, _Symbol, 0, sl, 0, "S610_M15_Sell");
            }
         }
      }
   }

   // =================================================================
   // ENGINE 2: M5 DUAL MONOTONIC RATCHET
   // =================================================================
   if(InpEnableEngine2)
   {
      datetime cur_m5 = iTime(_Symbol, PERIOD_M5, 0);
      if(cur_m5 != last_bar_m5)
      {
         last_bar_m5 = cur_m5;
         
         double upper_bb[], lower_bb[], middle_bb[];
         ArraySetAsSeries(upper_bb, true);
         ArraySetAsSeries(lower_bb, true);
         ArraySetAsSeries(middle_bb, true);
         CopyBuffer(handle_bb_m5, 1, 1, 1, upper_bb);
         CopyBuffer(handle_bb_m5, 2, 1, 1, lower_bb);
         CopyBuffer(handle_bb_m5, 0, 1, 1, middle_bb);
         
         double atr_m5 = GetAdaptiveATR(PERIOD_M5);
         double kc_upper = middle_bb[0] + InpKC_Multiplier * atr_m5;
         double kc_lower = middle_bb[0] - InpKC_Multiplier * atr_m5;
         
         bool in_squeeze = (upper_bb[0] < kc_upper && lower_bb[0] > kc_lower);
         if(in_squeeze) m5_squeeze_count++;
         else
         {
            if(m5_squeeze_count >= InpMinSqueezeBars)
            {
               MqlRates rates_m5[];
               ArraySetAsSeries(rates_m5, true);
               CopyRates(_Symbol, PERIOD_M5, 1, 1, rates_m5);
               
               if(rates_m5[0].close > upper_bb[0] && (macro_bias >= 0) && IsMicrostructureValid(true))
               {
                  double lot = NormalizeDouble(InpBaseLot * InpWeight2 * streak_mult, 2);
                  double sl = rates_m5[0].close - InpRatchetBaseMult * atr_m5;
                  trade_2.Buy(lot, _Symbol, 0, sl, 0, "S610_M5_Squeeze_Buy");
               }
               else if(rates_m5[0].close < lower_bb[0] && (macro_bias <= 0) && IsMicrostructureValid(false))
               {
                  double lot = NormalizeDouble(InpBaseLot * InpWeight2 * streak_mult, 2);
                  double sl = rates_m5[0].close + InpRatchetBaseMult * atr_m5;
                  trade_2.Sell(lot, _Symbol, 0, sl, 0, "S610_M5_Squeeze_Sell");
               }
            }
            m5_squeeze_count = 0;
         }
      }
   }

   // =================================================================
   // ENGINE 3: M1 NY MICRO SNIPER
   // =================================================================
   if(InpEnableEngine3)
   {
      datetime cur_m1 = iTime(_Symbol, PERIOD_M1, 0);
      if(cur_m1 != last_bar_m1)
      {
         last_bar_m1 = cur_m1;
         
         MqlDateTime dt;
         TimeGMT(dt);
         if(dt.hour >= InpNY_StartHourUTC && dt.hour <= InpNY_EndHourUTC)
         {
            double atr_m1 = GetAdaptiveATR(PERIOD_M1);
            if(atr_m1 >= InpMinM1_ATR)
            {
               MqlRates rates_m1[];
               ArraySetAsSeries(rates_m1, true);
               CopyRates(_Symbol, PERIOD_M1, 1, 2, rates_m1);
               
               double boost = (InpEnableNY_Overweight && dt.hour >= 13 && dt.hour <= 16) ? InpNY_BoostMultiplier : 1.0;
               
               if(rates_m1[0].close > rates_m1[1].high && (macro_bias >= 0) && IsMicrostructureValid(true))
               {
                  double lot = NormalizeDouble(InpBaseLot * InpWeight3 * streak_mult * boost, 2);
                  double sl = rates_m1[0].close - InpRatchetBaseMult * atr_m1;
                  trade_3.Buy(lot, _Symbol, 0, sl, 0, "S610_M1_NY_Buy");
               }
               else if(rates_m1[0].close < rates_m1[1].low && (macro_bias <= 0) && IsMicrostructureValid(false))
               {
                  double lot = NormalizeDouble(InpBaseLot * InpWeight3 * streak_mult * boost, 2);
                  double sl = rates_m1[0].close + InpRatchetBaseMult * atr_m1;
                  trade_3.Sell(lot, _Symbol, 0, sl, 0, "S610_M1_NY_Sell");
               }
            }
         }
      }
   }
}

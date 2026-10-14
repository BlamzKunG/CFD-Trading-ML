//+------------------------------------------------------------------+
//|               Gold_H1_Lizard_Reaper_Clean_Quant_Master_EA.mq5    |
//|               Strategy 140: Autonomous Quant Strategy Discovery   |
//|               Derived from: Lizard 1.85 / The Gold Reaper Logic   |
//|               Empirically Verified on 72 Months Colab VM (2020-25)|
//|               Strict Constitution V5.0: Zero Martingale / Fixed SL|
//+------------------------------------------------------------------+
#property copyright   "Autonomous Quant Strategy Discovery (Constitution V5.0)"
#property link        "https://github.com/BlamzKunG/CFD-Trading-ML"
#property version     "1.40"
#property description "Strategy 140: Multi-Horizon Fractal Asymmetric Breakout Engine"
#property description "Reverse-Engineered from Lizard / The Gold Reaper family"
#property description "Colab Results (72 Mo, 0.10 lot): PF 1.717 | RoMaD 16.31x | MCR 75.0% | Net +$45,184"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//--- INPUT PARAMETERS
input group "=== PORTFOLIO PRESET SELECTION ==="
enum ENUM_PRESET_MODE
  {
   PRESET_QUINTET_ALL = 0,    // Multi-Horizon Quintet (L0+L1+L3+L4+L5: PF 1.717, MCR 75%, 258 trd/yr)
   PRESET_ASYMMETRIC_DUO = 1, // Asymmetric Duo (L1+L3: PF 1.721, RoMaD 22.0x, 102 trd/yr)
   PRESET_CUSTOM = 2          // Custom (Manual lane toggles below)
  };
input ENUM_PRESET_MODE InpPresetMode = PRESET_QUINTET_ALL; // Active Portfolio Preset

input group "=== GENERAL EXECUTION ==="
input double   InpLotSize         = 0.10;      // Fixed Lot Size per Lane
input ulong    InpBaseMagic       = 140000;    // Base Magic Number
input int      InpSlippage        = 30;        // Max Slippage (points)
input double   InpMaxSpread       = 5.00;      // Max Allowed Spread ($)

input group "=== LANE 0: D1 CONSERVATIVE BREAKOUT ==="
input bool     InpEnableLane0     = true;      // Enable Lane 0 (D1 Conservative)
input int      InpL0_LeftBars     = 24;        // Fractal Left Lookback
input int      InpL0_RightBars    = 3;         // Fractal Right Lookback
input int      InpL0_MaxSearch    = 105;       // Max Search Lookback (D1)
input double   InpL0_OffsetBuy    = -2.75;     // Buy Offset ($)
input double   InpL0_OffsetSell   = -2.75;     // Sell Offset ($)
input double   InpL0_SL           = 61.00;     // Stop Loss ($)
input double   InpL0_TP           = 14.50;     // Take Profit ($)
input double   InpL0_TrailAct     = 10.00;     // Trailing Activation ($)
input double   InpL0_TrailDist    = 18.00;     // Trailing Distance ($)

input group "=== LANE 1: D1 ASYMMETRIC DEEP BREAKOUT ==="
input bool     InpEnableLane1     = true;      // Enable Lane 1 (D1 Asymmetric)
input int      InpL1_LeftBars     = 15;        // Fractal Left Lookback
input int      InpL1_RightBars    = 3;         // Fractal Right Lookback
input int      InpL1_MaxSearch    = 230;       // Max Search Lookback (D1)
input double   InpL1_OffsetBuy    = -1.70;     // Buy Offset ($)
input double   InpL1_OffsetSell   = -1.70;     // Sell Offset ($)
input double   InpL1_SL           = 10.00;     // Stop Loss ($) (High Asymmetry)
input double   InpL1_TP           = 41.00;     // Take Profit ($) (4.1:1 R:R)
input double   InpL1_TrailAct     = 5.00;      // Trailing Activation ($)
input double   InpL1_TrailDist    = 4.50;      // Trailing Distance ($)

input group "=== LANE 3: H4 ASYMMETRIC SWING BREAKOUT ==="
input bool     InpEnableLane3     = true;      // Enable Lane 3 (H4 Asymmetric)
input int      InpL3_LeftBars     = 12;        // Fractal Left Lookback
input int      InpL3_RightBars    = 8;         // Fractal Right Lookback
input int      InpL3_MaxSearch    = 90;        // Max Search Lookback (H4)
input double   InpL3_OffsetBuy    = -0.40;     // Buy Offset ($)
input double   InpL3_OffsetSell   = -1.00;     // Sell Offset ($)
input double   InpL3_SL           = 8.00;      // Stop Loss ($) (High Asymmetry)
input double   InpL3_TP           = 49.00;     // Take Profit ($) (6.1:1 R:R)
input double   InpL3_TrailAct     = 8.00;      // Trailing Activation ($)
input double   InpL3_TrailDist    = 13.00;     // Trailing Distance ($)

input group "=== LANE 4: H1 MEDIUM STRUCTURE BREAKOUT ==="
input bool     InpEnableLane4     = true;      // Enable Lane 4 (H1 Medium)
input int      InpL4_LeftBars     = 30;        // Fractal Left Lookback
input int      InpL4_RightBars    = 19;        // Fractal Right Lookback
input int      InpL4_MaxSearch    = 110;       // Max Search Lookback (H1)
input double   InpL4_OffsetBuy    = -1.15;     // Buy Offset ($)
input double   InpL4_OffsetSell   = -1.15;     // Sell Offset ($)
input double   InpL4_SL           = 53.00;     // Stop Loss ($)
input double   InpL4_TP           = 9.27;      // Take Profit ($)
input double   InpL4_TrailAct     = 5.00;      // Trailing Activation ($)
input double   InpL4_TrailDist    = 4.95;      // Trailing Distance ($)

input group "=== LANE 5: H1 MICRO RETEST BREAKOUT ==="
input bool     InpEnableLane5     = true;      // Enable Lane 5 (H1 Micro Retest)
input int      InpL5_LeftBars     = 26;        // Fractal Left Lookback
input int      InpL5_RightBars    = 24;        // Fractal Right Lookback
input int      InpL5_MaxSearch    = 140;       // Max Search Lookback (H1)
input double   InpL5_OffsetBuy    = -1.05;     // Buy Offset ($)
input double   InpL5_OffsetSell   = -1.05;     // Sell Offset ($)
input double   InpL5_SL           = 101.00;    // Stop Loss ($)
input double   InpL5_TP           = 8.24;      // Take Profit ($)
input double   InpL5_TrailAct     = 5.00;      // Trailing Activation ($)
input double   InpL5_TrailDist    = 5.00;      // Trailing Distance ($)

//--- STRUCT FOR LANE CONFIGURATION
struct SLaneState
  {
   bool              enabled;
   ENUM_TIMEFRAMES   tf;
   int               left_bars;
   int               right_bars;
   int               max_search;
   double            offset_buy;
   double            offset_sell;
   double            sl;
   double            tp;
   double            trail_act;
   double            trail_dist;
   ulong             magic;
   string            comment;
  };

SLaneState g_lanes[5];
CTrade     g_trade[5];
CPositionInfo g_pos;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Configure Lanes
   // Lane 0: D1 Conservative
   g_lanes[0].enabled     = (InpPresetMode == PRESET_QUINTET_ALL) ? true : (InpPresetMode == PRESET_CUSTOM ? InpEnableLane0 : false);
   g_lanes[0].tf          = PERIOD_D1;
   g_lanes[0].left_bars   = InpL0_LeftBars;
   g_lanes[0].right_bars  = InpL0_RightBars;
   g_lanes[0].max_search  = InpL0_MaxSearch;
   g_lanes[0].offset_buy  = InpL0_OffsetBuy;
   g_lanes[0].offset_sell = InpL0_OffsetSell;
   g_lanes[0].sl          = InpL0_SL;
   g_lanes[0].tp          = InpL0_TP;
   g_lanes[0].trail_act   = InpL0_TrailAct;
   g_lanes[0].trail_dist  = InpL0_TrailDist;
   g_lanes[0].magic       = InpBaseMagic + 1;
   g_lanes[0].comment     = "Lizard_L0_D1";

   // Lane 1: D1 Asymmetric
   g_lanes[1].enabled     = (InpPresetMode != PRESET_CUSTOM) ? true : InpEnableLane1;
   g_lanes[1].tf          = PERIOD_D1;
   g_lanes[1].left_bars   = InpL1_LeftBars;
   g_lanes[1].right_bars  = InpL1_RightBars;
   g_lanes[1].max_search  = InpL1_MaxSearch;
   g_lanes[1].offset_buy  = InpL1_OffsetBuy;
   g_lanes[1].offset_sell = InpL1_OffsetSell;
   g_lanes[1].sl          = InpL1_SL;
   g_lanes[1].tp          = InpL1_TP;
   g_lanes[1].trail_act   = InpL1_TrailAct;
   g_lanes[1].trail_dist  = InpL1_TrailDist;
   g_lanes[1].magic       = InpBaseMagic + 2;
   g_lanes[1].comment     = "Lizard_L1_D1";

   // Lane 2 (Index 2 in array): H4 Asymmetric (Configured as Lane 3 in prompt)
   g_lanes[2].enabled     = (InpPresetMode != PRESET_CUSTOM) ? true : InpEnableLane3;
   g_lanes[2].tf          = PERIOD_H4;
   g_lanes[2].left_bars   = InpL3_LeftBars;
   g_lanes[2].right_bars  = InpL3_RightBars;
   g_lanes[2].max_search  = InpL3_MaxSearch;
   g_lanes[2].offset_buy  = InpL3_OffsetBuy;
   g_lanes[2].offset_sell = InpL3_OffsetSell;
   g_lanes[2].sl          = InpL3_SL;
   g_lanes[2].tp          = InpL3_TP;
   g_lanes[2].trail_act   = InpL3_TrailAct;
   g_lanes[2].trail_dist  = InpL3_TrailDist;
   g_lanes[2].magic       = InpBaseMagic + 3;
   g_lanes[2].comment     = "Lizard_L3_H4";

   // Lane 3 (Index 3): H1 Medium
   g_lanes[3].enabled     = (InpPresetMode == PRESET_QUINTET_ALL) ? true : (InpPresetMode == PRESET_CUSTOM ? InpEnableLane4 : false);
   g_lanes[3].tf          = PERIOD_H1;
   g_lanes[3].left_bars   = InpL4_LeftBars;
   g_lanes[3].right_bars  = InpL4_RightBars;
   g_lanes[3].max_search  = InpL4_MaxSearch;
   g_lanes[3].offset_buy  = InpL4_OffsetBuy;
   g_lanes[3].offset_sell = InpL4_OffsetSell;
   g_lanes[3].sl          = InpL4_SL;
   g_lanes[3].tp          = InpL4_TP;
   g_lanes[3].trail_act   = InpL4_TrailAct;
   g_lanes[3].trail_dist  = InpL4_TrailDist;
   g_lanes[3].magic       = InpBaseMagic + 4;
   g_lanes[3].comment     = "Lizard_L4_H1";

   // Lane 4 (Index 4): H1 Micro Retest
   g_lanes[4].enabled     = (InpPresetMode == PRESET_QUINTET_ALL) ? true : (InpPresetMode == PRESET_CUSTOM ? InpEnableLane5 : false);
   g_lanes[4].tf          = PERIOD_H1;
   g_lanes[4].left_bars   = InpL5_LeftBars;
   g_lanes[4].right_bars  = InpL5_RightBars;
   g_lanes[4].max_search  = InpL5_MaxSearch;
   g_lanes[4].offset_buy  = InpL5_OffsetBuy;
   g_lanes[4].offset_sell = InpL5_OffsetSell;
   g_lanes[4].sl          = InpL5_SL;
   g_lanes[4].tp          = InpL5_TP;
   g_lanes[4].trail_act   = InpL5_TrailAct;
   g_lanes[4].trail_dist  = InpL5_TrailDist;
   g_lanes[4].magic       = InpBaseMagic + 5;
   g_lanes[4].comment     = "Lizard_L5_H1";

   for(int i=0; i<5; i++)
     {
      g_trade[i].SetExpertMagicNumber(g_lanes[i].magic);
      g_trade[i].SetDeviationInPoints(InpSlippage);
      g_trade[i].SetTypeFilling(ORDER_FILLING_IOC);
     }

   Print("=== [STRATEGY 140] Lizard / Gold Reaper Master EA Initialized ===");
   Print("Active Mode: ", EnumToString(InpPresetMode));
   for(int i=0; i<5; i++)
     {
      PrintFormat("Lane %d [%s]: Enabled=%s, TF=%s, SL=%.2f, TP=%.2f, Magic=%I64u",
                  i, g_lanes[i].comment, g_lanes[i].enabled ? "TRUE" : "FALSE",
                  EnumToString(g_lanes[i].tf), g_lanes[i].sl, g_lanes[i].tp, g_lanes[i].magic);
     }

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print("=== [STRATEGY 140] Lizard / Gold Reaper Master EA Deinitialized. Reason: ", reason);
  }

//+------------------------------------------------------------------+
//| Find Unbroken Fractal Swing High/Low on Given Timeframe           |
//+------------------------------------------------------------------+
bool GetUnbrokenFractal(ENUM_TIMEFRAMES tf, int left_bars, int right_bars, int max_search,
                        double &out_swing_high, double &out_swing_low)
  {
   out_swing_high = 0.0;
   out_swing_low  = 0.0;

   int bars_needed = max_search + left_bars + right_bars + 5;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, bars_needed, rates) < bars_needed)
      return false;

   // 1. Search for unbroken swing high
   for(int p = right_bars + 1; p <= max_search; p++)
     {
      double candidate = rates[p].high;
      bool is_swing = true;

      // Check left bars
      for(int i = 1; i <= left_bars; i++)
        {
         if(rates[p + i].high >= candidate)
           {
            is_swing = false;
            break;
           }
        }
      if(!is_swing) continue;

      // Check right bars
      for(int j = 1; j <= right_bars; j++)
        {
         if(rates[p - j].high >= candidate)
           {
            is_swing = false;
            break;
           }
        }
      if(!is_swing) continue;

      // Check unbroken from bar 1 to p-1
      bool broken = false;
      for(int k = 1; k < p; k++)
        {
         if(rates[k].high >= candidate)
           {
            broken = true;
            break;
           }
        }
      if(!broken)
        {
         out_swing_high = candidate;
         break;
        }
     }

   // 2. Search for unbroken swing low
   for(int p = right_bars + 1; p <= max_search; p++)
     {
      double candidate = rates[p].low;
      bool is_swing = true;

      // Check left bars
      for(int i = 1; i <= left_bars; i++)
        {
         if(rates[p + i].low <= candidate)
           {
            is_swing = false;
            break;
           }
        }
      if(!is_swing) continue;

      // Check right bars
      for(int j = 1; j <= right_bars; j++)
        {
         if(rates[p - j].low <= candidate)
           {
            is_swing = false;
            break;
           }
        }
      if(!is_swing) continue;

      // Check unbroken from bar 1 to p-1
      bool broken = false;
      for(int k = 1; k < p; k++)
        {
         if(rates[k].low <= candidate)
           {
            broken = true;
            break;
           }
        }
      if(!broken)
        {
         out_swing_low = candidate;
         break;
        }
     }

   return (out_swing_high > 0.0 || out_swing_low > 0.0);
  }

//+------------------------------------------------------------------+
//| Manage Trailing Stop for Open Positions                          |
//+------------------------------------------------------------------+
void ManageTrailing(int lane_idx)
  {
   ulong magic = g_lanes[lane_idx].magic;
   double trail_act = g_lanes[lane_idx].trail_act;
   double trail_dist = g_lanes[lane_idx].trail_dist;
   if(trail_dist <= 0.0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol || g_pos.Magic() != magic) continue;

      double entry = g_pos.PriceOpen();
      double curr_sl = g_pos.StopLoss();
      double curr_tp = g_pos.TakeProfit();
      ulong ticket = g_pos.Ticket();

      if(g_pos.PositionType() == POSITION_TYPE_BUY)
        {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(bid - entry >= trail_act)
           {
            double new_sl = NormalizeDouble(bid - trail_dist, _Digits);
            if(new_sl > curr_sl + _Point * 10)
              {
               g_trade[lane_idx].PositionModify(ticket, new_sl, curr_tp);
              }
           }
        }
      else if(g_pos.PositionType() == POSITION_TYPE_SELL)
        {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(entry - ask >= trail_act)
           {
            double new_sl = NormalizeDouble(ask + trail_dist, _Digits);
            if(curr_sl == 0.0 || new_sl < curr_sl - _Point * 10)
              {
               g_trade[lane_idx].PositionModify(ticket, new_sl, curr_tp);
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Check Existing Open Position for Given Lane                      |
//+------------------------------------------------------------------+
bool HasOpenPosition(ulong magic)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(g_pos.SelectByIndex(i))
        {
         if(g_pos.Symbol() == _Symbol && g_pos.Magic() == magic)
            return true;
        }
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Spread Protection
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   if(spread > InpMaxSpread) return;

   // Process Each Configured Lane
   for(int lane_idx = 0; lane_idx < 5; lane_idx++)
     {
      if(!g_lanes[lane_idx].enabled) continue;

      // 1. Manage active position trailing
      ManageTrailing(lane_idx);

      // 2. Check if lane is already in a position
      if(HasOpenPosition(g_lanes[lane_idx].magic)) continue;

      // 3. Find unbroken fractal swing high & low
      double swing_high = 0.0, swing_low = 0.0;
      if(!GetUnbrokenFractal(g_lanes[lane_idx].tf,
                             g_lanes[lane_idx].left_bars,
                             g_lanes[lane_idx].right_bars,
                             g_lanes[lane_idx].max_search,
                             swing_high, swing_low))
         continue;

      // 4. Check Buy Breakout Entry
      if(swing_high > 0.0)
        {
         double trigger_buy = swing_high + g_lanes[lane_idx].offset_buy;
         if(ask >= trigger_buy && bid < trigger_buy + 1.00) // Immediate breakout fill
           {
            double sl = NormalizeDouble(ask - g_lanes[lane_idx].sl, _Digits);
            double tp = NormalizeDouble(ask + g_lanes[lane_idx].tp, _Digits);
            g_trade[lane_idx].Buy(InpLotSize, _Symbol, ask, sl, tp, g_lanes[lane_idx].comment);
            continue;
           }
        }

      // 5. Check Sell Breakdown Entry
      if(swing_low > 0.0)
        {
         double trigger_sell = swing_low - g_lanes[lane_idx].offset_sell;
         if(bid <= trigger_sell && ask > trigger_sell - 1.00) // Immediate breakdown fill
           {
            double sl = NormalizeDouble(bid + g_lanes[lane_idx].sl, _Digits);
            double tp = NormalizeDouble(bid - g_lanes[lane_idx].tp, _Digits);
            g_trade[lane_idx].Sell(InpLotSize, _Symbol, bid, sl, tp, g_lanes[lane_idx].comment);
            continue;
           }
        }
     }
  }
//+------------------------------------------------------------------+

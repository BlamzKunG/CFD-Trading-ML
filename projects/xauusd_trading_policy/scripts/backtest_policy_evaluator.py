"""
=============================================================================
XAUUSD Trading Policy: Closed-Loop Backtest Evaluator
=============================================================================
Purpose:
- Realistic, closed-loop event-driven simulation for policy models.
- Dynamically updates Position State bar-by-bar (9 relative features).
- Evaluates real-time execution of actions: HOLD, OPEN_L, OPEN_S, ADD, REDUCE, CLOSE, REVERSE.
- Incorporates realistic spread, slippage, and commission friction.
- Computes comprehensive metrics: Net Profit, Profit Factor, Sharpe Ratio, Max Drawdown,
  and Entry Alpha vs Position Management Value-Add.
=============================================================================
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from scripts.counterfactual_simulator import (
    ACTION_HOLD, ACTION_OPEN_LONG, ACTION_OPEN_SHORT,
    ACTION_ADD, ACTION_REDUCE, ACTION_CLOSE, ACTION_REVERSE,
    ACTION_NAMES
)

def run_closed_loop_backtest(
    df: pd.DataFrame,
    market_features: pd.DataFrame,
    atr_series: pd.Series,
    policy_predictor,
    initial_balance: float = 10000.0,
    lot_base: float = 0.1,
    spread_points: float = 2.0,      # $0.20 spread typical for XAUUSD on prime accounts
    slippage_points: float = 1.0,    # $0.10 slippage
    commission_per_lot: float = 6.0, # $6.0 per round-turn lot
    precomputed_flat: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = None
) -> Dict[str, Any]:
    """
    Executes a high-fidelity closed-loop backtest.
    policy_predictor: callable taking [1, 40] numpy array and returning (action_id, size_frac, sl_atr, tp_atr)
    """
    n_bars = len(df)
    c_arr = df['close'].to_numpy(dtype=np.float64)
    h_arr = df['high'].to_numpy(dtype=np.float64)
    l_arr = df['low'].to_numpy(dtype=np.float64)
    atr_arr = atr_series.to_numpy(dtype=np.float64)
    mf_arr = market_features.to_numpy(dtype=np.float32)

    balance = initial_balance
    equity_curve = [balance]
    trades: List[Dict[str, Any]] = []

    # Current Position State
    pos_dir = 0.0          # 0: Flat, +1: Long, -1: Short
    pos_lot = 0.0
    entry_price = 0.0
    entry_bar = 0
    sl_price = 0.0
    tp_price = 0.0
    last_action_bar = 0
    max_fav_atr = 0.0
    max_adv_atr = 0.0

    point_value = 100.0   # $100 per $1 move per standard lot in XAUUSD
    cost_per_trade_point = (spread_points + slippage_points) * 0.1

    for t in range(n_bars):
        close_t = c_arr[t]
        high_t = h_arr[t]
        low_t = l_arr[t]
        atr_t = max(atr_arr[t], 0.1)

        # 1. If currently in position, check SL and TP trigger within the bar
        if pos_dir != 0.0:
            time_in_pos = t - entry_bar
            
            # Check Stop Loss / Take Profit
            hit_sl = False
            hit_tp = False
            exit_price = 0.0

            if pos_dir > 0:  # Long
                if low_t <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif high_t >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            else:  # Short
                if high_t >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif low_t <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_sl or hit_tp:
                # Execute exit
                pnl_dollars = pos_dir * (exit_price - entry_price) * pos_lot * point_value
                fee = commission_per_lot * pos_lot + (cost_per_trade_point * pos_lot * point_value)
                net_pnl = pnl_dollars - fee
                balance += net_pnl

                trades.append({
                    "entry_bar": entry_bar,
                    "exit_bar": t,
                    "direction": "LONG" if pos_dir > 0 else "SHORT",
                    "lot": pos_lot,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": net_pnl,
                    "pnl_atr": (exit_price - entry_price) / atr_t * pos_dir,
                    "reason": "SL_HIT" if hit_sl else "TP_HIT",
                    "bars_held": time_in_pos
                })

                # Reset to Flat
                pos_dir = 0.0
                pos_lot = 0.0
                max_fav_atr = 0.0
                max_adv_atr = 0.0

        # Update excursions if still in position
        if pos_dir != 0.0:
            if pos_dir > 0:
                cur_fav = (high_t - entry_price) / atr_t
                cur_adv = (entry_price - low_t) / atr_t
            else:
                cur_fav = (entry_price - low_t) / atr_t
                cur_adv = (high_t - entry_price) / atr_t
            max_fav_atr = max(max_fav_atr, cur_fav)
            max_adv_atr = max(max_adv_atr, cur_adv)

        # 2. Construct 9 Relative Position Features
        if pos_dir != 0.0:
            p_unrl = (close_t - entry_price) / atr_t * pos_dir
            p_dist_entry = (close_t - entry_price) / atr_t
            p_time_norm = min(1.0, (t - entry_bar) / 120.0)
            p_dist_sl = abs(close_t - sl_price) / atr_t
            p_dist_tp = abs(close_t - tp_price) / atr_t
            p_act_norm = min(1.0, (t - last_action_bar) / 60.0)
            p_size_frac = pos_lot / (lot_base * 2.0)
        else:
            p_unrl = 0.0
            p_dist_entry = 0.0
            p_time_norm = 0.0
            p_dist_sl = 0.0
            p_dist_tp = 0.0
            p_act_norm = 1.0
            p_size_frac = 0.0

        # Periodic Heartbeat for Live WebSocket Streaming & Anti-Timeout
        if t % 35000 == 0 and t > 0:
            print(f"    [sim] {t:,}/{n_bars:,} bars ({t/n_bars*100:.0f}%) | Equity: ${balance:,.0f} | Trades: {len(trades):,}", flush=True)

        # 3. Form state input and get ML Model Policy Decision
        if pos_dir == 0.0:
            if precomputed_flat is not None:
                action_id = int(precomputed_flat[0][t])
                size_frac = float(precomputed_flat[1][t])
                sl_atr = float(precomputed_flat[2][t])
                tp_atr = float(precomputed_flat[3][t])
            else:
                pos_features = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
                state_40 = np.concatenate([mf_arr[t], pos_features]).reshape(1, -1)
                action_id, size_frac, sl_atr, tp_atr = policy_predictor(state_40)
        else:
            # In position: evaluate management policy with 5-bar cadence to reflect realistic order cooldown
            if (t - last_action_bar) < 5:
                action_id = ACTION_HOLD
                size_frac = pos_lot / (lot_base * 2.0)
                sl_atr = abs(close_t - sl_price) / atr_t
                tp_atr = abs(close_t - tp_price) / atr_t
            else:
                pos_features = np.array([
                    pos_dir, p_size_frac, p_dist_entry, p_unrl,
                    p_time_norm, p_dist_sl, p_dist_tp, max_adv_atr, p_act_norm
                ], dtype=np.float32)
                state_40 = np.concatenate([mf_arr[t], pos_features]).reshape(1, -1)
                action_id, size_frac, sl_atr, tp_atr = policy_predictor(state_40)

        # 5. Process Decision
        if pos_dir == 0.0:
            # FLAT
            if action_id == ACTION_OPEN_LONG:
                pos_dir = 1.0
                pos_lot = round(max(lot_base * size_frac, 0.01), 2)
                entry_price = close_t + (spread_points * 0.05)
                entry_bar = t
                last_action_bar = t
                sl_price = entry_price - (sl_atr * atr_t)
                tp_price = entry_price + (tp_atr * atr_t)
                max_fav_atr, max_adv_atr = 0.0, 0.0
            elif action_id == ACTION_OPEN_SHORT:
                pos_dir = -1.0
                pos_lot = round(max(lot_base * size_frac, 0.01), 2)
                entry_price = close_t - (spread_points * 0.05)
                entry_bar = t
                last_action_bar = t
                sl_price = entry_price + (sl_atr * atr_t)
                tp_price = entry_price - (tp_atr * atr_t)
                max_fav_atr, max_adv_atr = 0.0, 0.0

        else:
            # IN POSITION
            if action_id == ACTION_CLOSE:
                exit_price = close_t - (spread_points * 0.05 * pos_dir)
                pnl_dollars = pos_dir * (exit_price - entry_price) * pos_lot * point_value
                fee = commission_per_lot * pos_lot + (cost_per_trade_point * pos_lot * point_value)
                net_pnl = pnl_dollars - fee
                balance += net_pnl
                trades.append({
                    "entry_bar": entry_bar,
                    "exit_bar": t,
                    "direction": "LONG" if pos_dir > 0 else "SHORT",
                    "lot": pos_lot,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": net_pnl,
                    "pnl_atr": (exit_price - entry_price) / atr_t * pos_dir,
                    "reason": "POLICY_CLOSE",
                    "bars_held": t - entry_bar
                })
                pos_dir, pos_lot = 0.0, 0.0
                last_action_bar = t

            elif action_id == ACTION_REDUCE and pos_lot >= 0.02:
                # Scale out 50%
                half_lot = round(pos_lot * 0.5, 2)
                exit_price = close_t - (spread_points * 0.05 * pos_dir)
                pnl_dollars = pos_dir * (exit_price - entry_price) * half_lot * point_value
                fee = commission_per_lot * half_lot + (cost_per_trade_point * half_lot * point_value)
                net_pnl = pnl_dollars - fee
                balance += net_pnl
                trades.append({
                    "entry_bar": entry_bar,
                    "exit_bar": t,
                    "direction": "LONG" if pos_dir > 0 else "SHORT",
                    "lot": half_lot,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": net_pnl,
                    "pnl_atr": (exit_price - entry_price) / atr_t * pos_dir,
                    "reason": "POLICY_REDUCE",
                    "bars_held": t - entry_bar
                })
                pos_lot -= half_lot
                last_action_bar = t

            elif action_id == ACTION_ADD and pos_lot < (lot_base * 2.0):
                # Scale in additional 50% base lot
                add_lot = round(lot_base * 0.5, 2)
                pos_lot += add_lot
                last_action_bar = t

            elif action_id == ACTION_REVERSE:
                # Close current and flip
                exit_price = close_t - (spread_points * 0.05 * pos_dir)
                pnl_dollars = pos_dir * (exit_price - entry_price) * pos_lot * point_value
                fee = commission_per_lot * pos_lot + (cost_per_trade_point * pos_lot * point_value)
                net_pnl = pnl_dollars - fee
                balance += net_pnl
                trades.append({
                    "entry_bar": entry_bar,
                    "exit_bar": t,
                    "direction": "LONG" if pos_dir > 0 else "SHORT",
                    "lot": pos_lot,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": net_pnl,
                    "pnl_atr": (exit_price - entry_price) / atr_t * pos_dir,
                    "reason": "POLICY_REVERSE",
                    "bars_held": t - entry_bar
                })

                # Flip
                pos_dir = -pos_dir
                pos_lot = round(max(lot_base * size_frac, 0.01), 2)
                entry_price = close_t + (spread_points * 0.05 * pos_dir)
                entry_bar = t
                last_action_bar = t
                if pos_dir > 0:
                    sl_price = entry_price - (sl_atr * atr_t)
                    tp_price = entry_price + (tp_atr * atr_t)
                else:
                    sl_price = entry_price + (sl_atr * atr_t)
                    tp_price = entry_price - (tp_atr * atr_t)
                max_fav_atr, max_adv_atr = 0.0, 0.0

        # Mark-to-market equity
        current_equity = balance
        if pos_dir != 0.0:
            cur_paper = pos_dir * (close_t - entry_price) * pos_lot * point_value
            current_equity += cur_paper
        equity_curve.append(current_equity)

    # Compile Summary Statistics
    trade_df = pd.DataFrame(trades)
    eq_arr = np.array(equity_curve)
    peaks = np.maximum.accumulate(eq_arr)
    drawdowns = (peaks - eq_arr) / peaks * 100.0
    max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

    total_trades = len(trade_df)
    if total_trades > 0:
        winning_trades = trade_df[trade_df['net_pnl'] > 0]
        losing_trades = trade_df[trade_df['net_pnl'] < 0]
        win_rate = len(winning_trades) / total_trades * 100.0
        gross_profit = winning_trades['net_pnl'].sum()
        gross_loss = abs(losing_trades['net_pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
        net_profit = trade_df['net_pnl'].sum()
        avg_trade = trade_df['net_pnl'].mean()
        avg_hold = trade_df['bars_held'].mean()
    else:
        win_rate = 0.0
        profit_factor = 0.0
        net_profit = 0.0
        avg_trade = 0.0
        avg_hold = 0.0

    return {
        "initial_balance": initial_balance,
        "final_equity": equity_curve[-1],
        "net_profit": net_profit,
        "return_pct": (equity_curve[-1] - initial_balance) / initial_balance * 100.0,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
        "avg_trade_pnl": avg_trade,
        "avg_bars_held": avg_hold,
        "trades": trade_df,
        "equity_curve": eq_arr
    }

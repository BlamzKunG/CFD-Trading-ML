#!/usr/bin/env python3
"""
===============================================================================
SCALPING PRECISION DISCOVERY BATCH 2: STRATEGIES 211 - 220
MACRO REGIME GATING & ASYMMETRIC REWARD/RISK ON XAUUSD (M5 & M15)
===============================================================================
Target Asset: XAUUSD (Gold)
Timeframes: M5 and M15 (Cross-Timeframe Evaluation)
Friction: Spread $0.25 ($25/lot) + Commission $6.00/lot ($0.60/0.10 lot)
Target Annual Volume: ~250 - 600+ Trades/Year

Key Upgrades from Batch 1:
  1. Macro Trend Filter: Align entries with Higher-Timeframe trend (H1 EMA 50 / 200).
  2. Asymmetric Risk-to-Reward: TP 2.8x - 3.5x ATR, SL 1.4x - 1.6x ATR.
  3. Dynamic Breakeven Stop: Move SL to entry price once price reaches +1.0x ATR.
  4. Session & Volatility Gating: Filter out low-liquidity chop (focus London & NY).
===============================================================================
"""

import os
import sys
import gc
import time
import json
import numpy as np
import pandas as pd

if os.path.exists("/content/CFD-Trading-ML"):
    REPO_ROOT = "/content/CFD-Trading-ML"
else:
    REPO_ROOT = "/root/CFD-Trading-ML"

DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")

def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_ema(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    ema[0] = series[0]
    alpha = 2.0 / (period + 1.0)
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_rsi(closes: np.ndarray, period: int = 7) -> np.ndarray:
    n = len(closes)
    rsi = np.full(n, 50.0, dtype=np.float64)
    diffs = np.diff(closes)
    gains = np.where(diffs > 0, diffs, 0.0)
    losses = np.where(diffs < 0, -diffs, 0.0)
    if len(gains) < period:
        return rsi
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(diffs)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def run_precision_scalping_backtest(opens, highs, lows, closes, atr, bull_sigs, bear_sigs, months, dates,
                                    tp_mult=3.0, sl_mult=1.5, be_mult=1.0, max_bars_hold=36,
                                    spread_pts=0.25, comm_dollars=0.60):
    """
    Precision scalping engine with Dynamic Breakeven Stop:
    - Moves SL to Entry + 0.10 once price achieves +be_mult * ATR into profit.
    - Captures asymmetrical trends while cutting downside variance.
    """
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0
    be_price = 0.0
    be_active = False
    point_value = 100.0

    for i in range(250, n - 1):
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            # Dynamic Breakeven check
            if not be_active:
                if pos_type == 1 and highs[i] >= (entry_price + be_mult * atr[entry_idx]):
                    be_active = True
                    sl_price = max(sl_price, entry_price + 0.10)
                elif pos_type == -1 and lows[i] <= (entry_price - be_mult * atr[entry_idx]):
                    be_active = True
                    sl_price = min(sl_price, entry_price - 0.10)

            # Time exit
            if (i - entry_idx) >= max_bars_hold:
                exit_price = opens[i]
                if pos_type == 1:
                    exit_price -= spread_pts
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars
                trades.append({"pnl": pnl, "month": months[entry_idx]})
                in_pos = False
                continue

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars
                trades.append({"pnl": pnl, "month": months[entry_idx]})
                in_pos = False
                continue

        if not in_pos:
            atr_val = atr[i]
            if atr_val <= 0.50:  # Minimum volatility filter
                continue
            if bull_sigs[i]:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
                be_active = False
            elif bear_sigs[i]:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * atr_val)
                tp_price = entry_price - (tp_mult * atr_val)
                be_active = False

    if not trades:
        return {
            "total_trades": 0, "annual_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0
        }

    pnls = np.array([t["pnl"] for t in trades])
    net_profit = np.sum(pnls)
    gross_win = np.sum(pnls[pnls > 0])
    gross_loss = abs(np.sum(pnls[pnls < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    win_rate = (len(pnls[pnls > 0]) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = np.max(dd) if len(dd) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    df_trades = pd.DataFrame(trades)
    m_pnl = df_trades.groupby("month")["pnl"].sum()
    total_months = len(m_pnl)
    win_months = np.sum(m_pnl > 0)
    mcr = (win_months / total_months * 100.0) if total_months > 0 else 0.0
    annual_trades = round(len(trades) / 6.0, 1)

    return {
        "total_trades": len(trades),
        "annual_trades": annual_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2)
    }

# =============================================================================
# STRATEGIES 211 - 220: PRECISION LOGICS
# =============================================================================

def gen_s211_macro_rsi_reversal(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S211: Macro-Filtered Fast RSI Reversal (Buy pullback in uptrend, Sell rally in downtrend)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_ema50 = compute_ema(closes, 50 * tf_bars_per_h1)
    macro_ema200 = compute_ema(closes, 200 * tf_bars_per_h1)
    rsi = compute_rsi(closes, period=7)
    
    for i in range(200 * tf_bars_per_h1, n):
        # Macro Bullish: Close > EMA50 > EMA200
        if closes[i] > macro_ema50[i] > macro_ema200[i]:
            if rsi[i - 1] <= 22 and rsi[i] > 22 and closes[i] > opens[i]:
                bull[i] = True
        # Macro Bearish: Close < EMA50 < EMA200
        elif closes[i] < macro_ema50[i] < macro_ema200[i]:
            if rsi[i - 1] >= 78 and rsi[i] < 78 and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s212_macro_ema_ribbon_pullback(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S212: Macro-Filtered EMA Ribbon Dynamic Pullback"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_ema100 = compute_ema(closes, 100 * tf_bars_per_h1)
    fast_ema = compute_ema(closes, 8)
    med_ema = compute_ema(closes, 21)
    
    for i in range(100 * tf_bars_per_h1, n):
        bar_range = highs[i] - lows[i]
        if bar_range <= 0:
            continue
        # Only during active session (07:00 - 19:00 UTC)
        if 7 <= hours[i] <= 19:
            if closes[i] > macro_ema100[i] and fast_ema[i] > med_ema[i]:
                if lows[i] <= med_ema[i] and closes[i] > fast_ema[i]:
                    lower_wick = min(opens[i], closes[i]) - lows[i]
                    if (lower_wick / bar_range) >= 0.40:
                        bull[i] = True
            elif closes[i] < macro_ema100[i] and fast_ema[i] < med_ema[i]:
                if highs[i] >= med_ema[i] and closes[i] < fast_ema[i]:
                    upper_wick = highs[i] - max(opens[i], closes[i])
                    if (upper_wick / bar_range) >= 0.40:
                        bear[i] = True
    return bull, bear

def gen_s213_volatility_asian_sweep(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S213: Asian Liquidity Sweep with ATR Threshold & London Timing"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    asia_high, asia_low = 0.0, 999999.0

    for i in range(1, n):
        h = hours[i]
        if h == 0 and hours[i-1] != 0:
            asia_high = highs[i]
            asia_low = lows[i]
        elif 0 <= h < 6:
            asia_high = max(asia_high, highs[i])
            asia_low = min(asia_low, lows[i])
        elif 7 <= h <= 10:  # London Open window only
            if atr[i] >= 1.50:  # Sufficient volatility to overcome friction
                # Bearish sweep: swept above by at least 0.3 ATR then closed back down
                if highs[i] > (asia_high + 0.25 * atr[i]) and closes[i] < asia_high:
                    bear[i] = True
                elif lows[i] < (asia_low - 0.25 * atr[i]) and closes[i] > asia_low:
                    bull[i] = True
    return bull, bear

def gen_s214_squeeze_with_volume_ignition(opens, highs, lows, closes, volumes, hours, atr, tf_bars_per_h1):
    """S214: Bollinger Bandwidth Squeeze with Volume Surge Ignition"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    period = 20
    sma = pd.Series(closes).rolling(period).mean().values
    std = pd.Series(closes).rolling(period).std().values
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    bandwidth = (upper - lower) / np.where(sma > 0, sma, 1.0)
    bw_min = pd.Series(bandwidth).rolling(30).min().values
    vol_sma = pd.Series(volumes).rolling(20).mean().values
    macro_ema50 = compute_ema(closes, 50 * tf_bars_per_h1)

    for i in range(50 * tf_bars_per_h1, n):
        if (7 <= hours[i] <= 19) and bandwidth[i - 1] <= bw_min[i - 1] * 1.08:
            if volumes[i] >= 1.5 * vol_sma[i]:
                if closes[i] > upper[i] and closes[i] > macro_ema50[i]:
                    bull[i] = True
                elif closes[i] < lower[i] and closes[i] < macro_ema50[i]:
                    bear[i] = True
    return bull, bear

def gen_s215_dual_tf_supertrend_scalp(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S215: Dual-Timeframe Supertrend Scalper (M5/M15 entry with H1 direction)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_atr = compute_atr(highs, lows, closes, 14 * tf_bars_per_h1)
    macro_trend = np.where(closes > compute_ema(closes, 50 * tf_bars_per_h1), 1, -1)
    fast_upper = (highs + lows) / 2.0 + 1.8 * atr
    fast_lower = (highs + lows) / 2.0 - 1.8 * atr
    trend = np.ones(n, dtype=np.int32)

    for i in range(50 * tf_bars_per_h1, n):
        if closes[i - 1] > fast_lower[i - 1]:
            fast_lower[i] = max(fast_lower[i], fast_lower[i - 1])
        if closes[i - 1] < fast_upper[i - 1]:
            fast_upper[i] = min(fast_upper[i], fast_upper[i - 1])

        if trend[i - 1] == 1:
            if closes[i] < fast_lower[i]:
                trend[i] = -1
                if macro_trend[i] == -1 and (7 <= hours[i] <= 19):
                    bear[i] = True
            else:
                trend[i] = 1
        else:
            if closes[i] > fast_upper[i]:
                trend[i] = 1
                if macro_trend[i] == 1 and (7 <= hours[i] <= 19):
                    bull[i] = True
            else:
                trend[i] = -1
    return bull, bear

def gen_s216_institutional_fvg_discount_premium(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S216: FVG Mitigation in Institutional Discount/Premium Zones"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    
    # 24-hour rolling high/low to determine discount/premium
    rolling_h = pd.Series(highs).rolling(24 * tf_bars_per_h1).max().values
    rolling_l = pd.Series(lows).rolling(24 * tf_bars_per_h1).min().values
    eq = (rolling_h + rolling_l) / 2.0

    for i in range(24 * tf_bars_per_h1, n):
        # Bullish FVG in Discount (price < Equilibrium)
        if closes[i] < eq[i]:
            if lows[i - 2] > highs[i - 4] and (lows[i - 2] - highs[i - 4]) >= 0.3 * atr[i]:
                fvg_top = lows[i - 2]
                fvg_bot = highs[i - 4]
                if lows[i] <= fvg_top and closes[i] >= fvg_bot and closes[i] > opens[i]:
                    bull[i] = True
        # Bearish FVG in Premium (price > Equilibrium)
        elif closes[i] > eq[i]:
            if highs[i - 2] < lows[i - 4] and (lows[i - 4] - highs[i - 2]) >= 0.3 * atr[i]:
                fvg_bot = highs[i - 2]
                fvg_top = lows[i - 4]
                if highs[i] >= fvg_bot and closes[i] <= fvg_top and closes[i] < opens[i]:
                    bear[i] = True
    return bull, bear

def gen_s217_vwap_mean_reversion_range_gated(opens, highs, lows, closes, volumes, hours, atr, tf_bars_per_h1):
    """S217: VWAP Mean Reversion with ADX/Chop Gating (Avoid Trending blowouts)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    
    # Compute daily VWAP
    cum_pv = 0.0
    cum_v = 0.0
    typical_price = (highs + lows + closes) / 3.0
    vwap = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if i > 0 and hours[i] == 0 and hours[i - 1] != 0:
            cum_pv = 0.0
            cum_v = 0.0
        v = volumes[i] if volumes[i] > 0 else 1.0
        cum_pv += typical_price[i] * v
        cum_v += v
        vwap[i] = cum_pv / cum_v if cum_v > 0 else closes[i]

    dist = closes - vwap
    # Check if market is in range: 50-period EMA slope is nearly flat
    ema50 = compute_ema(closes, 50)
    ema_slope = np.abs(ema50 - np.roll(ema50, 10)) / np.where(atr > 0, atr, 1.0)

    for i in range(50, n):
        atr_val = atr[i]
        if atr_val <= 0:
            continue
        # Non-trending market: slope < 0.6
        if ema_slope[i] <= 0.60:
            if dist[i] <= -2.2 * atr_val and closes[i] > opens[i]:
                bull[i] = True
            elif dist[i] >= 2.2 * atr_val and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s218_micro_pinbar_confluence(opens, highs, lows, closes, volumes, hours, atr, tf_bars_per_h1):
    """S218: Microstructure Pinbar at Session Key Levels with Macro Alignment"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_ema50 = compute_ema(closes, 50 * tf_bars_per_h1)
    vol_sma = pd.Series(volumes).rolling(20).mean().values

    for i in range(50 * tf_bars_per_h1, n):
        bar_range = highs[i] - lows[i]
        if bar_range <= 0 or atr[i] <= 0:
            continue
        body = abs(closes[i] - opens[i])
        lower_wick = min(opens[i], closes[i]) - lows[i]
        upper_wick = highs[i] - max(opens[i], closes[i])

        if (7 <= hours[i] <= 19) and volumes[i] >= 1.4 * vol_sma[i] and bar_range >= 0.7 * atr[i]:
            # Bullish rejection conforming to macro uptrend
            if closes[i] > macro_ema50[i] and (lower_wick / bar_range) >= 0.55 and body <= 0.25 * bar_range:
                bull[i] = True
            # Bearish rejection conforming to macro downtrend
            elif closes[i] < macro_ema50[i] and (upper_wick / bar_range) >= 0.55 and body <= 0.25 * bar_range:
                bear[i] = True
    return bull, bear

def gen_s219_keltner_chande_momentum(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S219: Keltner Channel Breakout with Chande Momentum Oscillator (CMO) Filter"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    ema20 = compute_ema(closes, 20)
    upper_kc = ema20 + 1.6 * atr
    lower_kc = ema20 - 1.6 * atr
    
    # CMO 14
    diffs = np.diff(closes)
    diffs = np.insert(diffs, 0, 0.0)
    pos_sum = pd.Series(np.where(diffs > 0, diffs, 0.0)).rolling(14).sum().values
    neg_sum = pd.Series(np.where(diffs < 0, -diffs, 0.0)).rolling(14).sum().values
    total_sum = pos_sum + neg_sum
    cmo = np.where(total_sum > 0, 100.0 * (pos_sum - neg_sum) / total_sum, 0.0)

    for i in range(25, n):
        if 7 <= hours[i] <= 19:
            if closes[i] > upper_kc[i] and closes[i - 1] <= upper_kc[i - 1] and cmo[i] >= 35.0:
                bull[i] = True
            elif closes[i] < lower_kc[i] and closes[i - 1] >= lower_kc[i - 1] and cmo[i] <= -35.0:
                bear[i] = True
    return bull, bear

def gen_s220_london_breakout_box(opens, highs, lows, closes, hours, atr, tf_bars_per_h1):
    """S220: London Opening Box (06:00 - 07:00 UTC) Range Breakout"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    box_high, box_low = 0.0, 999999.0

    for i in range(1, n):
        h = hours[i]
        if h == 6:
            box_high = max(box_high if hours[i-1] == 6 else highs[i], highs[i])
            box_low = min(box_low if hours[i-1] == 6 else lows[i], lows[i])
        elif 7 <= h <= 11:
            box_size = box_high - box_low
            if box_size >= 1.0 * atr[i]:
                if closes[i] > box_high and closes[i - 1] <= box_high:
                    bull[i] = True
                elif closes[i] < box_low and closes[i - 1] >= box_low:
                    bear[i] = True
    return bull, bear

# =============================================================================
# BATCH EXECUTION RUNNER
# =============================================================================

def main():
    t_start = time.time()
    timeframes = ["M15", "M5"]
    print("=" * 105)
    print("🚀 SCALPING PRECISION DISCOVERY BATCH 2: STRATEGIES 211 - 220")
    print(f"📊 Multi-Timeframe Matrix: {', '.join(timeframes)} on XAUUSD (2020-2025)")
    print(f"🎯 Target Volume: ~250-600 Trades/Year | Friction: Spread $0.25 + Comm $6.00/Lot")
    print("⚙️  Engine Upgrade: Dynamic Breakeven Stop + Macro Trend Gating + Session Hours")
    print("=" * 105)

    strategy_registry = [
        ("S211", "Macro-Filtered Fast RSI Reversal", gen_s211_macro_rsi_reversal),
        ("S212", "Macro-Filtered EMA Ribbon Pullback", gen_s212_macro_ema_ribbon_pullback),
        ("S213", "Volatility Asian Sweep with London Timing", gen_s213_volatility_asian_sweep),
        ("S214", "Squeeze with Volume Ignition", gen_s214_squeeze_with_volume_ignition),
        ("S215", "Dual-Timeframe Supertrend Scalper", gen_s215_dual_tf_supertrend_scalp),
        ("S216", "FVG Mitigation in Discount/Premium", gen_s216_institutional_fvg_discount_premium),
        ("S217", "VWAP Mean Reversion with Chop Gating", gen_s217_vwap_mean_reversion_range_gated),
        ("S218", "Micro Pinbar at Session Confluence", gen_s218_micro_pinbar_confluence),
        ("S219", "Keltner Breakout with CMO Filter", gen_s219_keltner_chande_momentum),
        ("S220", "London Opening Box Range Breakout", gen_s220_london_breakout_box)
    ]

    all_matrix_results = []

    for tf in timeframes:
        parquet_file = os.path.join(DATA_DIR, f"XAUUSD_{tf}.parquet")
        if not os.path.exists(parquet_file):
            print(f"[!] Warning: File {parquet_file} not found. Skipping {tf}...")
            continue

        print(f"\n>>> [TIMEFRAME: {tf}] Loading data from {parquet_file}...")
        df = pd.read_parquet(parquet_file)
        n_bars = len(df)
        print(f"    Loaded {n_bars:,} bars ({df.index[0]} to {df.index[-1]})")

        opens = df['open'].values.astype(np.float64)
        highs = df['high'].values.astype(np.float64)
        lows = df['low'].values.astype(np.float64)
        closes = df['close'].values.astype(np.float64)
        volumes = df['tick_volume'].values.astype(np.float64) if 'tick_volume' in df.columns else np.ones(n_bars, dtype=np.float64)
        hours = df.index.hour.values
        months = df.index.strftime('%Y-%m').values
        dates = df.index.strftime('%Y-%m-%d').values
        
        atr = compute_atr(highs, lows, closes, 14)
        tf_bars_per_h1 = 12 if tf == "M5" else 4
        del df
        gc.collect()

        tp_mult = 3.0 if tf == "M5" else 2.8
        sl_mult = 1.5 if tf == "M5" else 1.4
        be_mult = 1.0
        max_bars = 28 if tf == "M5" else 18

        for sid, sname, gen_func in strategy_registry:
            t0 = time.time()
            if sid in ["S214", "S217", "S218"]:
                bull, bear = gen_func(opens, highs, lows, closes, volumes, hours, atr, tf_bars_per_h1)
            else:
                bull, bear = gen_func(opens, highs, lows, closes, hours, atr, tf_bars_per_h1)

            metrics = run_precision_scalping_backtest(
                opens, highs, lows, closes, atr, bull, bear, months, dates,
                tp_mult=tp_mult, sl_mult=sl_mult, be_mult=be_mult, max_bars_hold=max_bars
            )
            dur = round(time.time() - t0, 2)

            # Strict Champion criteria
            if metrics["pf"] >= 1.50 and metrics["net_profit"] > 0 and metrics["annual_trades"] >= 200:
                status = "🏆 CHAMPION SCALPER"
            elif metrics["net_profit"] > 0 and metrics["annual_trades"] >= 100:
                status = "TACTICAL CANDIDATE"
            else:
                status = "NEEDS REFINEMENT"

            entry = {
                "strategy_id": sid,
                "strategy_name": sname,
                "timeframe": tf,
                "total_trades": metrics["total_trades"],
                "annual_trades": metrics["annual_trades"],
                "net_profit": metrics["net_profit"],
                "pf": metrics["pf"],
                "win_rate": metrics["win_rate"],
                "max_dd": metrics["max_dd"],
                "romad": metrics["romad"],
                "mcr": metrics["mcr"],
                "status": status,
                "compute_time_s": dur
            }
            all_matrix_results.append(entry)
            print(f"  [{tf}] {sid}: {sname:<45} | Tr/Yr: {metrics['annual_trades']:<5} | Net: ${metrics['net_profit']:<9.2f} | PF: {metrics['pf']:<5.3f} | DD: ${metrics['max_dd']:<8.2f} | MCR: {metrics['mcr']:<5.1f}% | {status} ({dur}s)", flush=True)

        del opens, highs, lows, closes, volumes, hours, months, dates, atr
        gc.collect()

    print("\n" + "=" * 105)
    print("🏆 BATCH 2 PRECISION SCALPING LEADERBOARD SUMMARY (2020-2025)")
    print("=" * 105)
    df_matrix = pd.DataFrame(all_matrix_results)
    if not df_matrix.empty:
        df_matrix.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
        print(df_matrix[["strategy_id", "timeframe", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_precision_batch_211_220_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_precision_batch_211_220_matrix.csv")

    with open(out_json, "w") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_runtime_s": round(time.time() - t_start, 2),
            "results": all_matrix_results
        }, f, indent=2)

    df_matrix.to_csv(out_csv, index=False)
    print(f"\n[+] Saved Matrix Results to:\n    - {out_json}\n    - {out_csv}")
    print("=" * 105)

if __name__ == "__main__":
    main()

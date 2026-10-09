#!/usr/bin/env python3
"""
Diagnostic: Inspect the exact losing months of Strategy 17 to determine root causes
"""
import os
import json
import pandas as pd
import numpy as np

def main():
    champ_path = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_17_monthly_budget_champion.json"
    with open(champ_path, "r") as f:
        data = json.load(f)

    series = data.get("monthly_series", {})
    df = pd.DataFrame(list(series.items()), columns=["month", "pnl"])
    df["pnl"] = df["pnl"].astype(float)
    df["profitable"] = df["pnl"] > 0

    print("=== STRATEGY 17: MONTHLY BREAKDOWN ===")
    print(f"Total Months: {len(df)}")
    print(f"Winning Months: {int(df['profitable'].sum())} ({df['profitable'].mean()*100:.2f}%)")
    print(f"Losing Months: {int((~df['profitable']).sum())}")

    losing = df[~df['profitable']].sort_values("pnl")
    print("\nWorst 10 Losing Months:")
    print(losing.head(10).to_string(index=False))

    print("\nMonthly PnL by Year:")
    df["year"] = df["month"].str.slice(0, 4)
    print(df.groupby("year")["pnl"].agg(["count", lambda x: (x > 0).sum(), "sum"]).rename(columns={"<lambda_0>": "win_months"}))

if __name__ == "__main__":
    main()

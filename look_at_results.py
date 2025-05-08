import pandas as pd

df = pd.read_csv("data_with_metrics.csv")

df = df[df["old_rank"] > 64]

df['profit_pct'] = df['pred_profit'] / df['buy_price'] * 100

top_10_hitters = (
    df
    .sort_values(by="profit_pct", ascending=False)
    [["name","pred_profit","buy_price","pred_quick_sell_value","profit_pct","mu_pitcher","mu_hitter"]]
)

print(top_10_hitters.head(20))

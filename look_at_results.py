import pandas as pd

df = pd.read_csv("players_with_stats_with_preds.csv")

hitters = df[(df["is_hitter"] == False) & (df["old_rank"] >= 60)]

top_10_hitters = hitters\
    .sort_values(by="mu_pitcher", ascending=True)\
    [["name", "old_rank", "mu_pitcher", "low95_pitcher", "high95_pitcher"]]

print(top_10_hitters.head(20))

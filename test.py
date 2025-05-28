import pandas as pd

df1 = pd.read_csv("pitcher_stats.csv")
df2 = pd.read_csv("model/training_data/pitcher_stats.csv")

master_df = (
    pd.concat([df1, df2], ignore_index=True)
      .drop_duplicates(subset=["uuid", "update"])
)

master_df.to_csv("master_pitcher.csv", index=False)
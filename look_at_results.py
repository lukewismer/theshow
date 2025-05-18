import pandas as pd

df = pd.read_csv("hitter_stats.csv")

aj = df[df["name"] == "Aaron Judge"]

# Get unique update values as a list
years = aj["update"].unique().tolist()

print(years)
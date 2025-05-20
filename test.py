import pandas as pd

df = pd.read_csv("inference/web_data.csv")

print(df.columns.to_list())
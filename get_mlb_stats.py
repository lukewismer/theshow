import requests
import pandas as pd
from datetime import datetime

# First lets lookup the roster updates
date = datetime(2025, 5, 2) # May 2nd

df = pd.read_csv("players.csv")

for i, row in df.iterrows():
    id = row["mlb_id"]
    hitter = row["is_hitter"]

    if hitter:
        groups = "hitting"
    else:
        groups = "pitching"

    url = f"https://statsapi.mlb.com/api/v1/stats?stats=career&personId={id}"
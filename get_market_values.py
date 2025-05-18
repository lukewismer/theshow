import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
import time
import random

url = "https://mlb25.theshow.com/apis/listing"
df = pd.read_csv("data.csv")

def qs_value(ovr):
    if ovr < 65: return 5
    if 65 <= ovr < 75: return 25
    if ovr == 75: return 50
    if ovr == 76: return 75
    if ovr == 77: return 100
    if ovr == 78: return 125
    if ovr == 79: return 150
    if ovr == 80: return 400
    if ovr == 81: return 600
    if ovr == 82: return 900
    if ovr == 83: return 1200
    if ovr == 84: return 1500
    if ovr == 85: return 3000
    if ovr == 86: return 3750
    if ovr == 87: return 4500
    if ovr == 88: return 5500
    if ovr == 89: return 7000
    if ovr == 90: return 8000
    if ovr == 91: return 9000
    if ovr >= 92: return 10000
    return 0

def fetch_metrics(row):
    print(row.uuid)
    time.sleep(random.uniform(0.1, 0.7))
    data = requests.get(f"{url}?uuid={row.uuid}").json()
    sell = data["best_sell_price"]
    buy = max(data["best_buy_price"], qs_value(row.old_rank))
    cur = row.old_rank
    if row.is_hitter:
        pred = int(round(cur + row.mu_hitter))
        low  = int(round(cur + row.low95_hitter))
        high = int(round(cur + row.high95_hitter))
    else:
        pred = int(round(cur + row.mu_pitcher))
        low  = int(round(cur + row.low95_pitcher))
        high = int(round(cur + row.high95_pitcher))
    return {
        "sell_price": sell,
        "buy_price": buy,
        "current_quick_sell": qs_value(cur),
        "pred_quick_sell_value": qs_value(pred),
        "low_qs_value": qs_value(low),
        "high_qs_value": qs_value(high),
        "pred_profit": qs_value(pred) - buy,
        "price_above_qs": buy - qs_value(cur)
    }

with ThreadPoolExecutor(max_workers=4) as exe:
    results = list(exe.map(fetch_metrics, df.itertuples(index=False)))

metrics_df = pd.DataFrame(results)
df = pd.concat([df.reset_index(drop=True), metrics_df], axis=1)
df.to_csv("data_with_metrics.csv", index=False)

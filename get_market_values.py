import pandas as pd
import requests

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

metrics = {
    "sell_price": [],
    "buy_price": [],
    "current_quick_sell": [],
    "pred_quick_sell_value": [],
    "low_qs_value": [],
    "high_qs_value": [],
    "pred_profit": [],
    "price_above_qs": []
}

for _, row in df.iterrows():
    f_url = f"{url}?uuid={row['uuid']}"
    print(f_url)
    data = requests.get(f_url).json()
    sell = data["best_sell_price"]
    buy = max(data["best_buy_price"], qs_value(row["old_rank"]))
    cur = row["old_rank"]
    if row["is_hitter"]:
        pred = int(round(cur + row["mu_hitter"]))
        low  = int(round(cur + row["low95_hitter"]))
        high = int(round(cur + row["high95_hitter"]))
    else:
        pred = int(round(cur + row["mu_pitcher"]))
        low  = int(round(cur + row["low95_pitcher"]))
        high = int(round(cur + row["high95_pitcher"]))
    metrics["sell_price"].append(sell)
    metrics["buy_price"].append(buy)
    metrics["current_quick_sell"].append(qs_value(cur))
    metrics["pred_quick_sell_value"].append(qs_value(pred))
    metrics["low_qs_value"].append(qs_value(low))
    metrics["high_qs_value"].append(qs_value(high))
    metrics["pred_profit"].append(qs_value(pred) - buy)
    metrics["price_above_qs"].append(buy - qs_value(cur))

for col, vals in metrics.items():
    df[col] = vals

df.to_csv("data_with_metrics.csv", index=False)

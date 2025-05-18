import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_CSV   = "../old_csv/players_2025.csv"
OUTPUT_CSV  = "../old_csv/players_with_stats_cur.csv"

def clean_splits(splits: dict) -> dict:
    for key in ("groundOutsToAirouts", "catchersInterference", "groundIntoDoublePlay"):
        splits.pop(key, None)
    return splits

def fetch_and_clean(person_id, group, stat_type,
                    prefix="", start_date=None, end_date=None):
    """
    Wrap /people/{id}/stats, adding startDate and/or endDate if provided.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
        f"?stats={stat_type}&group={group}"
    )
    if start_date:
        url += f"&startDate={start_date}"
    if end_date:
        url += f"&endDate={end_date}"

    resp = requests.get(url)
    resp.raise_for_status()
    stats_arr = resp.json().get("stats", [])
    if not stats_arr or not stats_arr[0].get("splits"):
        return {}
    stat_block = stats_arr[0]["splits"][0].get("stat", {})
    cleaned = clean_splits(stat_block)
    return {f"{prefix}{k}": v for k, v in cleaned.items()}

def process_player_update(p, label, update_dt, prev_dt):
    """
    Build one row for player p at update label/update_dt.
    """
    pid   = p["mlb_id"]
    print(f"Updating {p['name']} {pid}")
    group = "hitting" if p.get("is_hitter", False) else "pitching"

    update_str   = update_dt.strftime("%m/%d/%Y")
    prev_str     = prev_dt.strftime("%m/%d/%Y")
    three_weeks  = (update_dt - timedelta(weeks=3)).strftime("%m/%d/%Y")
    season_start = SEASON_START.strftime("%m/%d/%Y")

    row = dict(p)
    row["update"] = label

    # vintage career stats up to update
    row.update(fetch_and_clean(pid, group,
                               stat_type="byDateRange",
                               start_date="01/01/1995",
                               end_date=update_str))

    # season-to-date
    row.update(fetch_and_clean(pid, group,
                               stat_type="byDateRange",
                               prefix="season_",
                               start_date=season_start,
                               end_date=update_str))

    # last 3 weeks
    row.update(fetch_and_clean(pid, group,
                               stat_type="byDateRange",
                               prefix="3wk_",
                               start_date=three_weeks,
                               end_date=update_str))

    # since previous update
    row.update(fetch_and_clean(pid, group,
                               stat_type="byDateRange",
                               prefix="since_prev_",
                               start_date=prev_str,
                               end_date=update_str))
    return row

''' 2024 Dates Used
# 1) Define your update snapshots
updates = [
    ("2024_1", datetime(2024,  4, 26)),
    ("2024_2", datetime(2024,  5, 17)),
    ("2024_3", datetime(2024,  6,   7)),
    ("2024_4", datetime(2024,  6,  28)),
    ("2024_5", datetime(2024,  7,  26)),
    ("2024_6", datetime(2024,  8,  29)),
    ("2024_7", datetime(2024, 10,   4)),
    ("2024_8", datetime(2024, 11,   8)),
]
'''

'''2023 Dates Used
updates = [
    ("2023_1", datetime(2023,  4, 21)),
    ("2023_2", datetime(2023,  5, 12)),
    ("2023_3", datetime(2023,  6,   2)),
    ("2023_4", datetime(2023,  6,  30)),
    ("2023_5", datetime(2023,  7,  24)),
    ("2023_6", datetime(2023,  8,  11)),
    ("2023_7", datetime(2023, 9,   8)),
    ("2023_8", datetime(2023, 10,   6)),
    ("2023_9", datetime(2023, 11,   10))
]
'''

'''#2022 Dates Used
updates = [
    ("2022_1", datetime(2022,  4, 29)),
    ("2022_2", datetime(2022,  5, 13)),
    ("2022_3", datetime(2022,  5, 26)),
    ("2022_4", datetime(2022,  6,  10)),
    ("2022_5", datetime(2022,  6,  24)),
    ("2022_6", datetime(2022,  7,  15)),
    ("2022_7", datetime(2022, 7,   29)),
    ("2022_8", datetime(2022, 8,   19)),
    ("2022_9", datetime(2022, 9,   1)),
    ("2022_10", datetime(2022, 9,   16)),
    ("2022_11", datetime(2022, 10,   7)),
    ("2022_12", datetime(2022, 11,   11))
]'''


'''#2021 Dates Used
updates = [
    ("2021_1", datetime(2021,  4, 30)),
    ("2021_2", datetime(2021,  5, 14)),
    ("2021_3", datetime(2021,  5, 28)),
    ("2021_4", datetime(2021,  6,  11)),
    ("2021_5", datetime(2021,  6,  25)),
    ("2021_6", datetime(2021,  7,  9)),
    ("2021_7", datetime(2021, 7,   31)),
    ("2021_8", datetime(2021, 8,   13)),
    ("2021_9", datetime(2021, 8,   27)),
    ("2021_10", datetime(2021, 9,   17)),
    ("2021_11", datetime(2021, 10,   1)),
    ("2021_12", datetime(2021, 11,   5))
]'''


''' 2025 dates used 
updates = [
    ("2025_1", datetime(2025,  5, 2)),
]
'''

# Current prediction
updates = [
    ("2025_2", datetime(2025, 5, 9))
]

# Season start date for season‐to‐date queries
SEASON_START = datetime(2025, 3, 28)

# 2) Load your base roster
players_df = pd.read_csv(INPUT_CSV)
all_rows = []

# 3) Loop through each update, but parallelize the inner per-player work
for idx, (label, update_dt) in enumerate(updates):
    prev_dt = updates[idx-1][1] if idx > 0 else SEASON_START

    # build a list of tasks
    tasks = [
        (p.to_dict(), label, update_dt, prev_dt)
        for _, p in players_df.iterrows()
    ]

    # process them in parallel
    with ThreadPoolExecutor(max_workers=8) as exe:
        futures = [exe.submit(process_player_update, *t) for t in tasks]
        for fut in as_completed(futures):
            try:
                all_rows.append(fut.result())
            except Exception as e:
                # you can log fut and the exception if needed
                print("Error in task:", e)

# 4) Build and save
result = pd.DataFrame(all_rows)
result.to_csv(OUTPUT_CSV, index=False)
print(f"Saved {len(result)} rows ({len(updates)} updates) to {OUTPUT_CSV}")

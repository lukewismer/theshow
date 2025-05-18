import os
import pandas as pd
import requests
from datetime import datetime

UPDATE_IDS = {
    2021: [
        ("2021_1",  1,  "04/30/2021"),
        ("2021_2",  2,  "05/14/2021"),
        ("2021_3",  3,  "05/28/2021"),
        ("2021_4",  4,  "06/11/2021"),
        ("2021_5",  6,  "06/25/2021"),
        ("2021_6",  8,  "07/09/2021"),
        ("2021_7", 11,  "07/31/2021"),
        ("2021_8", 13,  "08/13/2021"),
        ("2021_9", 15,  "08/27/2021"),
        ("2021_10",18, "10/01/2021"),
        ("2021_11",20, "10/01/2021"),
        ("2021_12",21, "11/05/2021"),
    ],
    2022: [
        ("2022_1",  1,  "04/29/2022"),
        ("2022_2",  3,  "05/13/2022"),
        ("2022_3",  5,  "05/26/2022"),
        ("2022_4",  6,  "06/10/2022"),
        ("2022_5",  8,  "06/24/2022"),
        ("2022_6", 11,  "07/15/2022"),
        ("2022_7", 12,  "07/29/2022"),
        ("2022_8", 15,  "08/19/2022"),
        ("2022_9", 17,  "09/01/2022"),
        ("2022_10",19, "09/16/2022"),
        ("2022_11",21, "10/07/2022"),
        ("2022_12",22, "11/11/2022"),
    ],
    2023: [
        ("2023_1",  1,  "04/21/2023"),
        ("2023_2",  4,  "05/12/2023"),
        ("2023_3",  7,  "06/02/2023"),
        ("2023_4", 11,  "06/30/2023"),
        ("2023_5", 15,  "07/24/2023"),
        ("2023_6", 17,  "08/11/2023"),
        ("2023_7", 21,  "09/08/2023"),
        ("2023_8", 25,  "10/06/2023"),
        ("2023_9", 26,  "11/10/2023"),
    ],
    2024: [
        ("2024_1",  4,  "04/26/2024"),
        ("2024_2",  7,  "05/17/2024"),
        ("2024_3", 10,  "06/07/2024"),
        ("2024_4", 13,  "06/28/2024"),
        ("2024_5", 15,  "07/26/2024"),
        ("2024_6", 18,  "08/29/2024"),
        ("2024_7", 22,  "10/04/2024"),
        ("2024_8", 23,  "11/08/2024"),
    ],
    2025: [
        ("2025_1",  5,  "05/02/2025"),
    ],
    0: [
        ("current", None, datetime.now().strftime("%m/%d/%Y")),
    ],
}

MASTER_UPDATES = "players_updates_cur.csv"

def merge_updates(input_csv, year, cache_dir='.'):
    master_path = os.path.join(cache_dir, MASTER_UPDATES)

    players_df = pd.read_csv(input_csv, dtype=str)

    if year == 0:
        today = datetime.now().strftime("%m/%d/%Y")
        rows = []
        for _, p in players_df.iterrows():
            rec = p.to_dict()
            rec.update({
                "season":     "0",
                "update":     "current",
                "date":       today,
                "new_rank":   rec.get("ovr"),
                "old_rank":   rec.get("ovr"),
                "new_rarity": rec.get("rarity"),
                "old_rarity": rec.get("rarity"),
                "delta_rank": 0
            })
            rows.append(rec)

        pd.DataFrame(rows).astype(str).to_csv(master_path, index=False)
        print(f"Written {len(rows)} current players → {master_path}")
        return master_path

    if "year" in players_df.columns:
        players_df = players_df[players_df["year"] == str(year)]

    if os.path.exists(master_path):
        master_df = pd.read_csv(master_path, dtype=str)
        seen = set(zip(master_df["uuid"],
                       master_df["season"],
                       master_df["date"]))
    else:
        master_df = pd.DataFrame()
        seen = set()

    rows = []
    api_base = f"https://mlb{str(year)[2:]}.theshow.com/apis/roster_update"
    for label, uid, date in UPDATE_IDS[year]:
        if uid is None:
            continue
        resp = requests.get(f"{api_base}?id={uid}")
        resp.raise_for_status()
        for change in resp.json().get("attribute_changes", []):
            puid = change["obfuscated_id"]
            key = (puid, str(year), date)
            if key in seen or puid not in players_df["uuid"].values:
                continue

            base = players_df.loc[players_df["uuid"] == puid].iloc[0].to_dict()
            base.update({
                "season":     str(year),
                "update":     label,
                "date":       date,
                "new_rank":   change.get("current_rank"),
                "old_rank":   change.get("old_rank"),
                "new_rarity": change.get("current_rarity"),
                "old_rarity": change.get("old_rarity"),
                "delta_rank": (change.get("current_rank") or 0)
                              - (change.get("old_rank")     or 0),
            })
            rows.append(base)
            seen.add(key)

    if rows:
        new_df = pd.DataFrame(rows).astype(str)
        combined = pd.concat([master_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=["uuid", "season", "update"], keep="first"
        )
        combined.to_csv(master_path, index=False)
        print(f"Appended {len(new_df)} updates for {year} → {master_path}")
    else:
        print(f"No new updates for {year}")

    return master_path

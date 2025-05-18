import requests
import pandas as pd
from datetime import datetime

# roster update IDs by year
UPDATE_IDS = {
    2021: [
        ("2021_1",  1), ("2021_2",  2), ("2021_3",  3), ("2021_4",  4),
        ("2021_5",  6), ("2021_6",  8), ("2021_7", 11), ("2021_8", 13),
        ("2021_9", 15), ("2021_10",18),("2021_11",20),("2021_12",21),
    ],
    2022: [
        ("2022_1",  1), ("2022_2",  3), ("2022_3",  5), ("2022_4",  6),
        ("2022_5",  8), ("2022_6",11),  ("2022_7",12), ("2022_8",15),
        ("2022_9",17), ("2022_10",19),("2022_11",21),("2022_12",22),
    ],
    2023: [
        ("2023_1",  1), ("2023_2",  4), ("2023_3",  7),
        ("2023_4", 11), ("2023_5", 15), ("2023_6",17),
        ("2023_7",21),  ("2023_8",25),  ("2023_9",26),
    ],
    2024: [
        ("2024_1",  4), ("2024_2",  7), ("2024_3",10), ("2024_4",13),
        ("2024_5",15),  ("2024_6",18),  ("2024_7",22), ("2024_8",23),
    ],
    2025: [
        ("2025_1",  5),
    ],
    0: [
        # just a placeholder—actual API calls skipped for year=0
        ("current", None),
    ],
}

def merge_roster_updates_for_year(year: int):
    """
    Reads players_with_stats_cur.csv, merges in roster-update info,
    or for year=0 simply backfills new/old rank & rarity from ovr/rarity,
    and writes out players_with_stats_merged_cur.csv
    """
    if year not in UPDATE_IDS:
        raise ValueError(f"No update-ID mapping defined for year {year}")

    # filenames & API base
    if year == 0:
        input_csv  = "../old_csv/players_with_stats_cur.csv"
        output_csv = "../old_csv/players_with_stats_merged_cur.csv"
    else:
        input_csv  = f"players_with_stats_{year}.csv"
        output_csv = f"players_with_stats_merged_{year}.csv"

    df = pd.read_csv(input_csv, dtype={"uuid": str}, low_memory=False)

    # if year=0, skip API calls entirely
    if year == 0:
        # replicate one row per player, per update label (which is just "current")
        # but df already has one row per player/update (for current, only "current")
        merged = df.copy()
        # fill columns
        merged["new_rank"]   = merged["ovr"]
        merged["old_rank"]   = merged["ovr"]
        merged["new_rarity"] = merged["rarity"]
        merged["old_rarity"] = merged["rarity"]
        merged["delta_rank"] = 0

        # cast to int
        merged["new_rank"] = merged["new_rank"].astype(int)
        merged["old_rank"] = merged["old_rank"].astype(int)

        merged.to_csv(output_csv, index=False)
        print(f"[current] wrote {len(merged)} rows → {output_csv}")
        return

    # otherwise, collect all actual updates via API
    api_base   = f"https://mlb{str(year)[-2]}.theshow.com/apis/roster_update"
    all_updates = []
    for label, rid in UPDATE_IDS[year]:
        url  = f"{api_base}?id={rid}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json() or {}
        for upd in data.get("attribute_changes", []):
            all_updates.append({
                "uuid":       str(upd.get("obfuscated_id", "")),
                "update":     label,
                "new_rank":   upd.get("current_rank"),
                "old_rank":   upd.get("old_rank"),
                "new_rarity": upd.get("current_rarity"),
                "old_rarity": upd.get("old_rarity"),
            })

    updates_df = pd.DataFrame(all_updates)

    # merge on both keys
    merged = df.merge(
        updates_df,
        on=["uuid", "update"],
        how="left",
    )

    fallbacks = {
        "new_rank":   "ovr",
        "old_rank":   "ovr",
        "new_rarity": "rarity",
        "old_rarity": "rarity",
    }
    for col, fb in fallbacks.items():
        merged[col] = merged.get(col).fillna(merged[fb])

    merged["new_rank"]   = merged["new_rank"].astype(int)
    merged["old_rank"]   = merged["old_rank"].astype(int)
    merged["delta_rank"] = merged["new_rank"] - merged["old_rank"]

    # write out
    merged.to_csv(output_csv, index=False)
    print(f"[{year}] wrote {len(merged)} rows → {output_csv}")


if __name__ == "__main__":
    merge_roster_updates_for_year(0)

# inference/pipeline.py

import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(__file__))

from inference.live_series    import get_live_series
from inference.player_ids     import resolve_ids
from inference.roster_updates import merge_updates
from inference.stats_fetcher  import StatsFetcher

import hitter_inference   
import pitcher_inference   


def run(cache_dir="./inference/"):
    os.makedirs(cache_dir, exist_ok=True)

    year = 2025
    print(f"Processing {year}")

    ls_csv = get_live_series(year, cache_dir)

    pid_csv = resolve_ids(ls_csv, year, cache_dir)

    merged_csv = merge_updates(pid_csv, 0, cache_dir)

    fetcher     = StatsFetcher()
    hitter_csv  = os.path.join(cache_dir, "hitter_stats_cur.csv")
    pitcher_csv = os.path.join(cache_dir, "pitcher_stats_cur.csv")

    print("Fetching hitter stats…")
    fetcher.run_hitters(merged_csv, out_path=hitter_csv)

    print("Fetching pitcher stats…")
    fetcher.run_pitchers(merged_csv, out_path=pitcher_csv)

    print("Running hitter inference…")
    cwd = os.getcwd()
    os.chdir(cache_dir)          
    hitter_inference.main()       
    os.chdir(cwd)                  

    print("Running pitcher inference…")
    df_pitch = pitcher_inference.infer_pitchers()
    pitcher_out = os.path.join(cache_dir, "pitcher_stats_with_delta_preds.csv")
    df_pitch.to_csv(pitcher_out, index=False)

    hitter_out = os.path.join(cache_dir, "hitter_stats_with_delta_preds.csv")
    print("Done!")
    print(f"  Hitters → {hitter_out}")
    print(f"  Pitchers → {pitcher_out}")

    hitter_out = "inference/hitter_stats_with_delta_preds.csv"
    pitcher_out = "inference/pitcher_stats_with_delta_preds.csv"

    print("Merging hitter + pitcher data into web_data.csv…")
    df_hit = pd.read_csv(hitter_out, dtype=str)
    df_pit = pd.read_csv(pitcher_out, dtype=str)
    web_df = pd.concat([df_hit, df_pit], ignore_index=True)

    project_root = os.path.dirname(cache_dir) or "."
    web_path = os.path.join(project_root, "web_data.csv")
    web_df.to_csv(web_path, index=False)
    print(f"  Written merged data → {web_path}")
    
    from firebase_utils import upload_web_data
    upload_web_data(web_path)
    to_remove = [
        ls_csv,
        pid_csv,
        merged_csv,
        hitter_csv,
        pitcher_csv,
        hitter_out,
        pitcher_out
    ]
    
    print("Cleaning up intermediary files…")
    for path in to_remove:
        try:
            os.remove(path)
            print(f"  Removed {path}")
        except OSError:
            pass


if __name__ == "__main__":
    run()

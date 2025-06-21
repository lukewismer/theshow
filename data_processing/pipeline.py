from data_processing.live_series import get_live_series
from data_processing.player_ids import resolve_ids
from data_processing.roster_updates import merge_updates
from data_processing.hitter_game_logs import HitterGameLogs
from data_processing.pitcher_game_logs import PitcherGameLogs
from data_processing.stats_fetcher import StatsFetcher


def run(years, cache_dir='.'):
    for year in years:
        print(f"Processing {year}")
        ls = get_live_series(year, cache_dir)
        ls = "live_series.csv"
        pid = resolve_ids(ls, year, cache_dir)
        pid = "players.csv"
        merged = merge_updates(pid, year, cache_dir)
    merged = "players_updates.csv"
    stats_fetcher = StatsFetcher()
    stats = stats_fetcher.run(merged)
    stats.to_csv("data_processing/master_hitting.py")
    print(f"Completed {year}, output → {merged}")

if __name__=='__main__':
    years=[2021,2022,2023,2024,2025]
    run(years)
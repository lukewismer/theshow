import os
import time
import requests
import pandas as pd

def get_live_series(year, cache_dir='.'):
    """
    Fetches all Live Series cards for a given year and
    appends them into one live_series.csv (with a `year` column).
    Returns the path to live_series.csv.
    """
    base_url = f'https://mlb{str(year)[2:]}.theshow.com/apis'
    out_file = os.path.join(cache_dir, 'live_series_cur.csv')

    if os.path.exists(out_file):
        existing = pd.read_csv(out_file, dtype=str)
        seen = set(existing['uuid'])
    else:
        existing = pd.DataFrame()
        seen = set()

    session = requests.Session()
    page = 1
    new_cards = []
    while True:
        print(f"Fetching Live Series page {page} for {year}…")
        resp = session.get(
            f"{base_url}/items?type=mlb_card&page={page}",
            timeout=80
        )
        resp.raise_for_status()
        items = resp.json().get('items', [])
        if not items:
            break

        for card in items:
            uid = card.get('uuid')
            if card.get('series') == 'Live' and uid not in seen:
                card['year'] = year
                new_cards.append(card)
                seen.add(uid)

        page += 1
        time.sleep(0.2)

    if new_cards:
        df = pd.concat([existing, pd.DataFrame(new_cards)], ignore_index=True)

        df = df.drop_duplicates(subset=['uuid', 'year'], keep='first')
        for idx, row in df.iterrows():
            if row.get('name') == 'Shohei Ohtani':
                df.at[idx, 'display_position'] = 'DH'

        drop_cols = [
            "type", "img", "sc_baked_img", "short_description", "series",
            "series_texture_name", "series_year", "display_secondary_positions",
            "jersey_number", "born", "hit_rank_image", "fielding_rank_image",
            "pitches", "quirks", "is_sellable", "has_augment", "augment_text",
            "augment_end_date", "has_matchup", "stars", "trend",
            "has_rank_change", "event", "set_name", "is_live_set",
            "ui_anim_index", "locations"
        ]
        df = df.drop(columns=drop_cols, errors='ignore')

        df.to_csv(out_file, index=False)
        print(f"Appended {len(new_cards)} cards for {year} → {out_file}")
    else:
        print(f"No new Live Series cards for {year}")

    return out_file
import os
import pandas as pd
import requests
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

def strip_accents(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )

def _lookup_player(row, season, base_url):
    search_name = row['search_name']
    print(search_name)
    pos         = row.get('display_position', '')
    num         = row.get('jersey_number')

    session = requests.Session()
    resp = session.get(f"{base_url}/api/v1/people/search?names={search_name}")
    resp.raise_for_status()
    people = resp.json().get('people', [])

    # exact accent-free name match
    pattern = re.compile(rf"^{re.escape(search_name)}$", re.IGNORECASE)
    mlb_id = None
    for p in people:
        if pattern.match(strip_accents(p.get('fullName', ''))):
            mlb_id = p['id']
            break

    # fallback to position & number
    if not mlb_id:
        for p in people:
            if (pos and num and
                p.get('primaryNumber') == num and
                p.get('primaryPosition', {}).get('abbreviation') == pos):
                mlb_id = p['id']
                break

    if not mlb_id:
        # no match, skip
        return None

    rec = row.drop(labels=['search_name']).to_dict()
    rec.update({'mlb_id': mlb_id, 'season': season})
    return rec

def resolve_ids(input_csv, season, cache_dir='.'):
    """
    Reads live_series.csv, parallelizes the MLB ID lookup for one season,
    and appends results into players.csv (deduped on uuid+season).
    Returns the path to players.csv.
    """
    master_file = os.path.join(cache_dir, 'players.csv')
    base_url    = 'https://statsapi.mlb.com'

    if os.path.exists(master_file):
        existing = pd.read_csv(master_file, dtype=str)
        seen = set(zip(existing['uuid'], existing['season']))
    else:
        existing = pd.DataFrame()
        seen = set()

    df = pd.read_csv(input_csv, dtype=str)
    df = df[df['year'] == str(season)].copy()
    df['search_name'] = df['name'].apply(strip_accents)

    fetched = []
    with ThreadPoolExecutor(max_workers=6) as exe:
        futures = {
            exe.submit(_lookup_player, row, season, base_url): idx
            for idx, (_, row) in enumerate(df.iterrows())
        }
        for fut in as_completed(futures):
            rec = fut.result()
            if rec and (rec['uuid'], str(season)) not in seen:
                fetched.append(rec)
                seen.add((rec['uuid'], str(season)))

    if fetched:
        new_df = pd.DataFrame(fetched)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['uuid', 'season'], keep='first')
        combined.to_csv(master_file, index=False)
        print(f"Appended {len(fetched)} players for season {season} → {master_file}")
    else:
        print(f"No new players found for season {season}")

    return master_file
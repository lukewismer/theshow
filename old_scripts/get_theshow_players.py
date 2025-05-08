import requests
import pandas as pd
import time
import os

def get_all_live_series_cards_df(year):
    BASE_URL = f"https://mlb{year}.theshow.com/apis"
    csv_file = f"live_series_{year}.csv"
    if os.path.exists(csv_file):
        existing = pd.read_csv(csv_file, encoding='utf-8')
        seen = set(existing['uuid'])
    else:
        existing = pd.DataFrame()
        seen = set()

    session = requests.Session()
    page = 1
    new_cards = []

    while True:
        print("Getting page " + str(page))
        url = f"{BASE_URL}/items?type=mlb_card&page={page}"
        for attempt in range(5):
            try:
                resp = session.get(url, timeout=80)
                resp.raise_for_status()
                break
            except requests.RequestException as e:
                print(f"Page {page} error (try {attempt+1}/5): {e}")
                time.sleep(2 ** attempt)
        else:
            print(f"Failed page {page} after 5 tries.")
            return

        items = resp.json().get('items', [])
        if not items:
            break

        for card in items:
            uid = card.get("uuid")
            if card.get("series") == "Live" and card.get("team") != "Free Agents" and uid not in seen:
                new_cards.append(card)
                seen.add(uid)

        page += 1

    if new_cards:
        df = pd.concat([existing, pd.DataFrame(new_cards)], ignore_index=True)
        df.to_csv(csv_file, index=False, encoding='utf-8')
        print(f"Appended {len(new_cards)} cards to {csv_file}")
    else:
        print("No new cards found.")

get_all_live_series_cards_df(20)

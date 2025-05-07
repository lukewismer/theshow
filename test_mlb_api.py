import requests
import pandas as pd

df = pd.read_csv("live_series_25.csv")

base_url = "https://statsapi.mlb.com"

ls_players = []

for i, row in df.iterrows():
    print(f"fetching {row['name']}")
    name = row["name"]
    pos = row["display_position"]
    jersey_number = row["jersey_number"]

    # Search for player
    url = f"{base_url}/api/v1/people/search?names={name}"
    req = requests.get(url)
    try:
        req.raise_for_status()
    except Exception as e:
        print(e)

    data = req.json()

    mlb_id = None
    if len(data["people"]) > 1:
        for people in data["people"]:
            if people["primaryPosition"]['abbreviation'] == pos and people["primaryNumber"] == jersey_number:
                mlb_id = people['id']
    else:
        if len(data["people"]) > 0:
            mlb_id = data["people"][0]["id"]

    if mlb_id is None:
        print(f"No MLB ID found for {name!r} ({pos}/{jersey_number})")
        continue
    
    new_player = {
        **row.drop(["type", "img", "sc_baked_img", "short_description", "series", "series_texture_name",
                           "series_year", "hit_rank_image", "fielding_rank_image", "quirks", "has_augment",
                           "augment_text", "is_sellable", "augment_end_date", "has_matchup", "stars", "trend", "set_name",
                           "event", "is_live_set", "ui_anim_index", "locations"]).to_dict(),
        "season": 2025,
        "mlb_id": mlb_id
    }

    ls_players.append(new_player)

new_df = pd.DataFrame(ls_players)
new_df.to_csv("players.csv")


    
    

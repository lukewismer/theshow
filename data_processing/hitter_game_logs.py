import pandas as pd
import requests
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class HitterGameLogs:

    def __init__(self):
        self.base_url = "https://statsapi.mlb.com/api/v1"
        evts = requests.get(f"{self.base_url}/eventTypes").json()
        self.event_types = {e["code"]: e for e in evts}
        self.sess = requests.Session()

        self._pbp_cache = {}

    def run(self, player_id, date, season):
        g3, g1, gs = self.get_players_games(player_id, date, season)

        s3 = self.process_games(player_id, g3)
        s1 = self.process_games(player_id, g1)
        ss = self.process_games(player_id, gs)

        def flatten_stats(label, ids, stats):
            out = {}
            gp = len(ids)
            out[f"{label}_gp"] = gp
            for split, agg in stats.items():
                out[f"{label}_{split}_gp"] = gp
                for stat_name, value in agg.items():
                    out[f"{label}_{split}_{stat_name}"] = value
            return out

        row = {}
        row.update(flatten_stats("season", gs, ss))
        row.update(flatten_stats("3wk",    g3, s3))
        row.update(flatten_stats("1wk",    g1, s1))
        return pd.DataFrame([row])
    
    def get_plays(self, game_id):
        # return from cache or fetch once
        if game_id not in self._pbp_cache:
            resp = self.sess.get(f"{self.base_url}/game/{game_id}/playByPlay").json()
            self._pbp_cache[game_id] = resp["allPlays"]
        return self._pbp_cache[game_id]

    def process_games(self, player_id, game_ids):
        splits = {"vl": [], "vr": [], "risp": []}

        # fetch each game’s allPlays exactly once, in parallel
        with ThreadPoolExecutor(max_workers=6) as exe:
            futures = {exe.submit(self.get_plays, gid): gid for gid in game_ids}
            for fut in as_completed(futures):
                all_plays = fut.result()
                self._accumulate_player_plays(player_id, all_plays, splits)

        return {k: self.aggregate_results(v) for k, v in splits.items()}

    def aggregate_results(self, plays):
        h       = sum(p["h"]   for p in plays)
        doubles = sum(p["2b"]  for p in plays)
        triples = sum(p["3b"]  for p in plays)
        hr      = sum(p["hr"]  for p in plays)
        tb      = sum(p["tb"]  for p in plays)
        so      = sum(p["so"]  for p in plays)
        pa      = sum(p["pa"]  for p in plays)
        bb      = sum(p["bb"]  for p in plays)
        hbp     = sum(p.get("hbp", 0) for p in plays)
        ab      = sum(p["ab"]  for p in plays)
        rbi     = sum(p["rbi"] for p in plays)
        pitches = sum(p["pitches"] for p in plays)
        sf      = sum(p["sac_fly"] for p in plays)

        avg_base    = h / ab if ab > 0 else 0
        obp_denom   = ab + bb + hbp + sf
        obp_base    = (h + bb + hbp) / obp_denom if obp_denom > 0 else 0
        slug_base   = tb / ab if ab > 0 else 0
        ops_base    = obp_base + slug_base
        babip_denom = ab - so - hr + sf
        babip_base  = (h - hr) / babip_denom if babip_denom > 0 else 0
        ppa_base    = pitches / pa if pa > 0 else 0

        return {
            "h":               h,
            "2b":              doubles,
            "3b":              triples,
            "hr":              hr,
            "tb":              tb,
            "so":              so,
            "pa":              pa,
            "bb":              bb,
            "hbp":             hbp,
            "ab":              ab,
            "rbi":             rbi,
            "pitches_per_pa":  round(ppa_base, 4),
            "avg":             round(avg_base, 4),
            "obp":             round(obp_base, 4),
            "slug":            round(slug_base, 4),
            "ops":             round(ops_base, 4),
            "babip":           round(babip_base, 4)
        }

    def _accumulate_player_plays(self, player_id, all_plays, splits):
        for play in all_plays:
            if int(play["matchup"]["batter"]["id"]) != int(player_id):
                continue

            pr = play["result"]
            code = pr.get("eventType")
            if not code:
                continue

            code = play["result"]["eventType"]
            evt  = self.event_types.get(code, {})
            pit  = play["matchup"]["pitchHand"]["code"]
            key  = "vl" if pit == "L" else "vr"
            risp = (play["matchup"]["splits"]["menOnBase"] == "RISP")

            pr, cnt = play["result"], play["count"]
            res = {
                "rbi": pr["rbi"],
                "h":   int(evt.get("hit", False)),
                "2b":  int(code=="double"),
                "3b":  int(code=="triple"),
                "hr":  int(code=="home_run"),
                "tb":  1*(code=="single") + 2*(code=="double")
                      + 3*(code=="triple") + 4*(code=="home_run"),
                "so":  int(code in {
                          "strikeout","strike_out",
                          "strikeout_double_play",
                          "strikeout_triple_play"}),
                "pa":  int(evt.get("plateAppearance", False)),
                "bb":  int(code in {"walk","intent_walk"}),
                "ab":  int(evt.get("plateAppearance", False)
                          and code not in {
                              "walk","intent_walk",
                              "hit_by_pitch","sac_fly",
                              "sac_fly_double_play","sac_bunt",
                              "sac_bunt_double_play",
                              "catcher_interf","batter_interference",
                              "fan_interference",
                              "os_ruling_pending_primary"
                          }),
                "pitches": int(cnt["balls"]) + int(cnt["strikes"]),
                "sac_fly": int(code.startswith("sac_fly")),
                "hbp":     int(code=="hit_by_pitch")
            }

            splits[key].append(res)
            if risp:
                splits["risp"].append(res)

    def get_players_games(self, player_id, date, season):
        res = self.sess.get(
            f"{self.base_url}/people/{player_id}/stats",
            params={"stats":"gameLog","season":season}
        ).json()

        stats = res.get("stats") or []
        # if no stats or no splits, return empty lists
        if not stats or not stats[0].get("splits"):
            return [], [], []

        splits_data = stats[0]["splits"]
        target = datetime.datetime.strptime(date, "%m/%d/%Y").date()

        g3, g1, gs = [], [], []
        for s in splits_data:
            gd = datetime.datetime.strptime(s["date"], "%Y-%m-%d").date()
            if gd > target:
                continue
            pk = s["game"]["gamePk"]
            gs.append(pk)
            if target - gd <= datetime.timedelta(weeks=3):
                g3.append(pk)
            if target - gd <= datetime.timedelta(weeks=1):
                g1.append(pk)

        return g3, g1, gs
 
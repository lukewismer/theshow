import pandas as pd
import requests
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class PitcherGameLogs:

    def __init__(self):
        self.base_url = "https://statsapi.mlb.com/api/v1"
        # 1) Pre-load event types once
        evts = requests.get(f"{self.base_url}/eventTypes").json()
        self.event_types = {e["code"]: e for e in evts}
        # 2) Session for pooling
        self.sess = requests.Session()
        # 3) PBP cache
        self._pbp_cache = {}

    def run(self, player_id, date, season):
        # get 3wk, 1wk, season game lists
        g3, g1, gs = self.get_player_games(player_id, date, season)

        # process in any order; each game is fetched only once
        s3 = self.process_games(player_id, g3)
        s1 = self.process_games(player_id, g1)
        ss = self.process_games(player_id, gs)

        def flatten(label, ids, stats):
            out = {}
            gp = len(ids)
            out[f"{label}_gp"] = gp
            for split, agg in stats.items():
                out[f"{label}_{split}_gp"] = gp
                for stat, val in agg.items():
                    out[f"{label}_{split}_{stat}"] = val
            return out

        row = {}
        row.update(flatten("season", gs, ss))
        row.update(flatten("3wk",    g3, s3))
        row.update(flatten("1wk",    g1, s1))
        return pd.DataFrame([row])

    def get_plays(self, game_id):
        # fetch once per game, cache the allPlays list
        if game_id not in self._pbp_cache:
            resp = self.sess.get(
                f"{self.base_url}/game/{game_id}/playByPlay"
            ).json()
            self._pbp_cache[game_id] = resp["allPlays"]
        return self._pbp_cache[game_id]

    def process_games(self, player_id, game_ids):
        splits = {"ovr": [], "risp": []}

        # pull every game's PBP in parallel, then accumulate
        with ThreadPoolExecutor(max_workers=8) as exe:
            futures = {exe.submit(self.get_plays, gid): gid for gid in game_ids}
            for fut in as_completed(futures):
                all_plays = fut.result()
                self._accumulate_plays(player_id, all_plays, splits)

        return {k: self.aggregate_results(v) for k, v in splits.items()}

    def _accumulate_plays(self, player_id, all_plays, splits):
        for play in all_plays:
            if int(play["matchup"]["pitcher"]["id"]) != int(player_id):
                continue

            pr = play["result"]
            code = pr.get("eventType")
            if not code:
                continue
            code = pr["eventType"]
            evt  = self.event_types.get(code, {})
            risp = (play["matchup"]["splits"]["menOnBase"] == "RISP")

            # count outs as 1 per out recorded
            outs = 1 if pr.get("isOut") else 0
            cnt  = play["count"]
            balls, strikes = int(cnt["balls"]), int(cnt["strikes"])

            rec = {
                "outs":       outs,
                "hits":       int(evt.get("hit", False)),
                "earnedRuns": pr.get("rbi", 0),
                "runs":       0,  # you can compute this same way if needed
                "homeRuns":   int(code == "home_run"),
                "baseOnBalls":int(code in {"walk","intent_walk"}),
                "strikeOuts": int(code in {"strikeout","strike_out"}),
                "pitches":    balls + strikes,
                "strikes":    strikes,
                "sac_fly":    int(code.startswith("sac_fly")),
                "hbp":        int(code == "hit_by_pitch"),
                "2b":         int(code == "double"),
                "3b":         int(code == "triple"),
                "hr":         int(code == "home_run"),
                "tb":         (1*(code=="single") + 2*(code=="double")
                              + 3*(code=="triple") + 4*(code=="home_run"))
            }

            splits["ovr"].append(rec)
            if risp:
                splits["risp"].append(rec)

    def aggregate_results(self, events):
        gp      = len(events)
        outs    = sum(e.get("outs", 0)         for e in events)
        hits    = sum(e.get("hits", 0)         for e in events)
        er      = sum(e.get("earnedRuns", 0)   for e in events)
        hr      = sum(e.get("homeRuns", 0)     for e in events)
        bb      = sum(e.get("baseOnBalls", 0)  for e in events)
        k       = sum(e.get("strikeOuts", 0)   for e in events)
        tb      = sum(e.get("tb", 0)           for e in events)
        sf      = sum(e.get("sac_fly", 0)      for e in events)
        P       = sum(e.get("pitches", 0)     for e in events)
        S       = sum(e.get("strikes", 0)     for e in events)
        hbp     = sum(e.get("hbp", 0)         for e in events)

        IP      = round(outs / 3, 2) if outs else 0
        BF      = hits + bb + hbp + outs
        AB      = BF - bb - hbp - sf

        BAA     = round(hits / outs, 4)       if outs else 0
        WHIP    = round((hits + bb) / IP, 4)  if IP   else 0
        CS_pct  = round(S / P, 4)             if P    else 0
        R9      = round(er / IP * 9, 4)       if IP   else 0
        K9      = round(k / IP * 9, 4)        if IP   else 0
        BB9     = round(bb / IP * 9, 4)       if IP   else 0
        HR9     = round(hr / IP * 9, 4)       if IP   else 0
        H9      = round(hits / IP * 9, 4)     if IP   else 0
        KBB     = round(k / bb, 4)            if bb   else 0
        PPG     = round(P / gp, 4)            if gp   else 0

        BABIP   = round((hits - hr) / (BF - k - hr), 4) \
                if (BF - k - hr) > 0 else 0
        OBPA    = round((hits + bb + hbp) / BF, 4)      if BF else 0
        SLGA    = round(tb / AB, 4)                    if AB else 0
        OPSA    = round(OBPA + SLGA, 4)

        return {
            "GP":   gp,
            "IP":   IP,
            "H":    hits,
            "ER":   er,
            "HR":   hr,
            "BB":   bb,
            "K":    k,
            "P":    P,
            "P/G":  PPG,
            "BAA":  BAA,
            "WHIP": WHIP,
            "CS%":  CS_pct,
            "R/9":  R9,
            "K/9":  K9,
            "BB/9": BB9,
            "HR/9": HR9,
            "H/9":  H9,
            "K/BB": KBB,
            "BABIP":BABIP,
            "OBA":  OBPA,
            "SLGA": SLGA,
            "OPS":  OPSA
        }

    def get_player_games(self, player_id, date, season):
        """
        Returns (3wk_ids, 1wk_ids, season_to_date_ids).
        If the player has no gameLog splits, returns three empty lists.
        """
        res = self.sess.get(
            f"{self.base_url}/people/{player_id}/stats",
            params={"stats": "gameLog", "season": season}
        ).json()

        stats = res.get("stats", [])
        # bullet‐proof: no stats returned
        if not stats or not stats[0].get("splits"):
            return [], [], []

        splits_data = stats[0]["splits"]
        target = datetime.datetime.strptime(date, "%m/%d/%Y").date()

        g3, g1, gs = [], [], []
        for s in splits_data:
            game_date = datetime.datetime.strptime(s["date"], "%Y-%m-%d").date()
            if game_date > target:
                continue
            pk = s["game"]["gamePk"]
            gs.append(pk)
            if target - game_date <= datetime.timedelta(weeks=3):
                g3.append(pk)
            if target - game_date <= datetime.timedelta(weeks=1):
                g1.append(pk)

        return g3, g1, gs
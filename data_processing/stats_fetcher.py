
import pandas as pd
import requests
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_processing.hitter_game_logs import HitterGameLogs
from data_processing.pitcher_game_logs import PitcherGameLogs


class StatsFetcher():

    def __init__(self):
        self.hitter_game_logs = HitterGameLogs()
        self.pitcher_game_logs = PitcherGameLogs()
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.sess = requests.Session()

    def run(self, file):
        master = pd.read_csv(file)
        hitters = master[master["is_hitter"]]
        #pitchers = master[~master["is_hitter"]]

        final_hitters = self._parallel_process(
            hitters, self._process_one_hitter, max_workers=8
        )
        final_hitters.to_csv("hitter_stats_cur.csv", index=False)
        #final_pitchers = self._parallel_process(
            #pitchers, self._process_one_pitcher, max_workers=8
        #)
        
        #final_pitchers.to_csv("pitcher_stats.csv", index=False)

    def _parallel_process(self, df, fn, max_workers=8):
        """
        Generic: run `fn(row)` for each row in df, in parallel.
        `fn` returns a single‐row DataFrame.
        """
        rows = []
        with ThreadPoolExecutor(max_workers=max_workers) as exe:
            future_to_idx = {
                exe.submit(fn, idx, row): idx
                for idx, row in df.iterrows()
            }
            for fut in as_completed(future_to_idx):
                try:
                    rows.append(fut.result())
                except Exception as e:
                    idx = future_to_idx[fut]
                    name = df.iloc[idx]["name"]
                    print(f"⚠️ Skipping {name} due to error: {e}")
        return pd.concat(rows, ignore_index=True)

    def _process_one_hitter(self, idx, row):
        print(row["name"])
        gl_df     = self.hitter_game_logs.run(
                        row["mlb_id"], row["date"], row["year"]
                    )
        career_df = self.get_hitter_career(
                        row["mlb_id"], row["year"]
                    )
        return pd.concat(
            [row.to_frame().T.reset_index(drop=True),
             gl_df.reset_index(drop=True),
             career_df.reset_index(drop=True)],
            axis=1
        )

    def _process_one_pitcher(self, idx, row):
        print(row["name"])
        gl_df     = self.pitcher_game_logs.run(
                        row["mlb_id"], row["date"], row["year"]
                    )
        career_df = self.get_pitcher_career(
                        row["mlb_id"], row["year"]
                    )
        return pd.concat(
            [row.to_frame().T.reset_index(drop=True),
             gl_df.reset_index(drop=True),
             career_df.reset_index(drop=True)],
            axis=1
        )
    
    def process_hitters(self, df: pd.DataFrame):
        rows = []

        for _, row in df.iterrows():
            print(row["name"])
            gl_df = self.hitter_game_logs.run(
                row["mlb_id"], row["date"], row["year"]
            )
            career_df = self.get_hitter_career(
                row["mlb_id"], row["year"]
            )
            combined = pd.concat(
                [row.to_frame().T, gl_df.reset_index(drop=True), career_df],
                axis=1
            )
            rows.append(combined)

        # stack them back into one big DataFrame
        final = pd.concat(rows, ignore_index=True)
        return final

    def get_hitter_career(self, player_id, cutoff_year):
        years     = list(range(2000, datetime.datetime.now().year + 1))
        seasons   = years[:years.index(cutoff_year)]
        season_str = ",".join(str(y) for y in seasons)

        url = (
            f"{self.base_url}/people/{player_id}/stats"
            f"?stats=statSplits&leagueListId=mlb_hist"
            f"&group=hitting&gameType=R&sitCodes=vl,vr,risp"
            f"&seasons={season_str}"
        )
        data = requests.get(url).json()

        buckets = {"vl": [], "vr": [], "risp": []}
        for s in data["stats"][0]["splits"]:
            code = s["split"]["code"]
            if code in buckets:
                buckets[code].append(s["stat"])

        def aggregate_career(stats_list):
            GP   = sum(s["gamesPlayed"]      for s in stats_list)
            AB   = sum(s["atBats"]           for s in stats_list)
            H    = sum(s["hits"]             for s in stats_list)
            BB   = sum(s["baseOnBalls"]      for s in stats_list)
            HBP  = sum(s["hitByPitch"]       for s in stats_list)
            SF   = sum(s["sacFlies"]         for s in stats_list)
            TB   = sum(s["totalBases"]       for s in stats_list)
            RBI  = sum(s["rbi"]              for s in stats_list)
            P    = sum(int(s["numberOfPitches"]) if "numberOfPitches" in s else 0 for s in stats_list)

            AVG  = round(H / AB, 4)                  if AB else 0
            OBP  = round((H + BB + HBP) / (AB + BB + HBP + SF), 4) \
                   if (AB + BB + HBP + SF) else 0
            SLG  = round(TB / AB, 4)                 if AB else 0
            OPS  = round(OBP + SLG, 4)
            BABIP= round(
                     (H - sum(s["homeRuns"] for s in stats_list))
                     / (AB
                        - sum(s["strikeOuts"] for s in stats_list)
                        - sum(s["homeRuns"] for s in stats_list)
                        + SF),
                     4
                   ) if (AB
                          - sum(s["strikeOuts"] for s in stats_list)
                          - sum(s["homeRuns"] for s in stats_list)
                          + SF) else 0

            return {
                "GP":    GP,
                "AB":    AB,
                "H":     H,
                "BB":    BB,
                "HBP":   HBP,
                "SF":    SF,
                "TB":    TB,
                "RBI":   RBI,
                "P":     P,
                "AVG":   AVG,
                "OBP":   OBP,
                "SLG":   SLG,
                "OPS":   OPS,
                "BABIP": BABIP
            }

        career = {
            split: aggregate_career(stats)
            for split, stats in buckets.items()
        }
        career["ovr"] = aggregate_career(buckets["vl"] + buckets["vr"])

        def flatten_career(career_dict):
            row = {}
            for split, agg in career_dict.items():
                for stat_name, val in agg.items():
                    row[f"ovr_{split}_{stat_name}"] = val
            return row

        df = pd.DataFrame([flatten_career(career)])
        return df

    def process_pitchers(self, df: pd.DataFrame):
        rows = []

        for _, row in df.iterrows():
            print(row["name"])
            gl_df = self.pitcher_game_logs.run(
                row["mlb_id"], row["date"], row["year"]
            )
            career_df = self.get_pitcher_career(
                row["mlb_id"], row["year"]
            )
            combined = pd.concat(
                [row.to_frame().T, gl_df.reset_index(drop=True), career_df],
                axis=1
            )
            rows.append(combined)

        final = pd.concat(rows, ignore_index=True)
        return final

    def get_pitcher_career(self, player_id, cutoff_year):
        """
        Returns a 1xN DataFrame of career pitching splits (overall + RISP),
        with columns prefixed ovr_{split}_{stat}.  Safely returns zeros if
        no data is present.
        """
        years     = list(range(2000, datetime.datetime.now().year + 1))
        seasons   = years[:years.index(cutoff_year)]
        season_str = ",".join(str(y) for y in seasons)

        risp_url = (
            f"{self.base_url}/people/{player_id}/stats"
            f"?stats=statSplits&leagueListId=mlb_hist"
            f"&group=pitching&gameType=R&sitCodes=risp"
            f"&seasons={season_str}"
        )
        risp_data = requests.get(risp_url).json()
        risp_splits = (risp_data.get("stats") or [])
        risp_stats = []
        if risp_splits and risp_splits[0].get("splits"):
            risp_stats = [
                sp["stat"]
                for sp in risp_splits[0]["splits"]
                if sp.get("split", {}).get("code") == "risp"
            ]

        # 2) Career overall splits
        ovr_url = (
            f"{self.base_url}/people/{player_id}/stats"
            f"?stats=career&leagueListId=mlb_hist"
            f"&group=pitching&gameType=R"
        )
        ovr_data = requests.get(ovr_url).json()
        ovr_splits = (ovr_data.get("stats") or [])
        ovr_stats = []
        if ovr_splits and ovr_splits[0].get("splits"):
            o = ovr_splits[0]["splits"]
            if o:
                ovr_stats = [o[0]["stat"]]

        def agg(stats_list):
            GP  = sum(int(s.get("gamesPlayed", 0))       for s in stats_list)
            GS  = sum(int(s.get("gamesStarted",  0))     for s in stats_list)
            CG  = sum(int(s.get("completeGames", 0))     for s in stats_list)
            SHO = sum(int(s.get("shutouts",      0))     for s in stats_list)
            W   = sum(int(s.get("wins",          0))     for s in stats_list)
            L   = sum(int(s.get("losses",        0))     for s in stats_list)
            SV  = sum(int(s.get("saves",         0))     for s in stats_list)
            SVO = sum(int(s.get("saveOpportunities",0))  for s in stats_list)
            HLD = sum(int(s.get("holds",         0))     for s in stats_list)

            IP  = sum(float(s.get("inningsPitched", 0))  for s in stats_list)
            H   = sum(int(s.get("hits",          0))     for s in stats_list)
            R   = sum(int(s.get("runs",          0))     for s in stats_list)
            ER  = sum(int(s.get("earnedRuns",    0))     for s in stats_list)
            HR  = sum(int(s.get("homeRuns",      0))     for s in stats_list)
            BB  = sum(int(s.get("baseOnBalls",   0))     for s in stats_list)
            K   = sum(int(s.get("strikeOuts",    0))     for s in stats_list)
            P   = sum(int(s.get("numberOfPitches",0))    for s in stats_list)

            ERA   = round(ER / IP * 9, 4)     if IP else 0
            WHIP  = round((BB + H) / IP, 4)   if IP else 0
            BF    = sum(int(s.get("battersFaced", 0)) for s in stats_list)
            BA_A  = round(H / BF, 4)          if BF else 0
            HBP   = sum(int(s.get("hitByPitch", 0)) for s in stats_list)
            OBPA  = round((H + BB + HBP) / BF, 4) if BF else 0
            TB    = sum(int(s.get("totalBases",   0)) for s in stats_list)
            AB    = sum(int(s.get("atBats",        0)) for s in stats_list)
            SLGA  = round(TB / AB, 4)          if AB else 0
            OPSA  = round(OBPA + SLGA, 4)

            K9    = round(K / IP * 9, 4)       if IP else 0
            BB9   = round(BB / IP * 9, 4)      if IP else 0
            HR9   = round(HR / IP * 9, 4)      if IP else 0
            H9    = round(H / IP * 9, 4)       if IP else 0
            KBB   = round(K / BB, 4)           if BB else 0
            PPG   = round(P / GP, 4)           if GP else 0
            CS_pct= round(sum(int(s.get("strikes", 0)) for s in stats_list) / P, 4) \
                    if P else 0

            BABIP = round((H - HR) / (AB - K - HR), 4) \
                    if (AB - K - HR) > 0 else 0

            return {
                "GP":   GP,  "GS":  GS,  "CG":  CG,  "SHO": SHO,
                "W":    W,   "L":   L,   "ERA": ERA, "SV":  SV,
                "SVO":  SVO, "HLD": HLD, "IP":  round(IP,1),
                "H":    H,   "R":   R,   "ER":  ER,   "HR":  HR,
                "BB":   BB,  "K":   K,   "P":   P,    "P/G": PPG,
                "BAA":  BA_A,"WHIP":WHIP,"CS%": CS_pct,
                "R/9": round(ER/IP*9,4) if IP else 0,
                "K/9": K9,  "BB/9":BB9,  "HR/9":HR9, "H/9": H9,
                "K/BB":KBB, "BABIP":BABIP,"OBA":OBPA,
                "SLGA":SLGA,"OPS": OPSA
            }

        career = {
            "ovr": agg(ovr_stats),
            "risp": agg(risp_stats)
        }

        flat = {
            f"ovr_{split}_{stat}": val
            for split, agg in career.items()
            for stat, val in agg.items()
        }
        return pd.DataFrame([flat])
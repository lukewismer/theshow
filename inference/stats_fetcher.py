#!/usr/bin/env python3
import os
import pandas as pd
import requests
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_processing.hitter_game_logs import HitterGameLogs
from data_processing.pitcher_game_logs import PitcherGameLogs

class StatsFetcher:
    def __init__(self):
        self.hitter_game_logs  = HitterGameLogs()
        self.pitcher_game_logs = PitcherGameLogs()
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.sess     = requests.Session()

    def run_hitters(self, master_file, out_path="hitter_stats_cur.csv"):
        master = pd.read_csv(master_file, dtype=str)
        subset = master[master.is_hitter == "True"]
        return self._run_group(subset, out_path, self._process_one_hitter)

    def run_pitchers(self, master_file, out_path="pitcher_stats_cur.csv"):
        master = pd.read_csv(master_file, dtype=str)
        subset = master[master.is_hitter == "False"]
        return self._run_group(subset, out_path, self._process_one_pitcher)

    def _run_group(self, df, out_path, process_fn):
        # identify already processed rows
        processed = set()
        if os.path.exists(out_path):
            done = pd.read_csv(out_path, dtype=str)
            processed = set(zip(done.mlb_id, done.date))

        to_do = df[~df.apply(lambda r: (r.mlb_id, r.date) in processed, axis=1)]
        # process all in parallel
        success_rows, failed_rows = self._parallel_process(to_do, process_fn)

        # retry any failures once
        if failed_rows:
            retries, still_failed = self._parallel_process(pd.DataFrame(failed_rows), process_fn)
            success_rows = pd.concat([success_rows, retries], ignore_index=True)

        # write output (overwrite existing)
        if not success_rows.empty:
            success_rows.to_csv(out_path, index=False)
        return success_rows

    def _parallel_process(self, df, fn, max_workers=6):
        rows, failed = [], []
        with ThreadPoolExecutor(max_workers=max_workers) as exe:
            futures = {exe.submit(self._retry_wrapper, fn, idx, row): row for idx, row in df.iterrows()}
            for fut in as_completed(futures):
                row = futures[fut]
                try:
                    rows.append(fut.result())
                except Exception:
                    failed.append(row.to_dict())
        result_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
        return result_df, failed

    def _retry_wrapper(self, fn, idx, row, max_attempts=5, delay=1):
        last_exc = None
        for _ in range(max_attempts):
            try:
                return fn(idx, row)
            except Exception as e:
                last_exc = e
                time.sleep(delay)
        raise last_exc

    def _process_one_hitter(self, idx, row):
        gl = self.hitter_game_logs.run(row.mlb_id, row.date, row.year)
        cr = self.get_hitter_career(row.mlb_id, row.year)
        return pd.concat([row.to_frame().T.reset_index(drop=True),
                          gl.reset_index(drop=True),
                          cr.reset_index(drop=True)], axis=1)

    def _process_one_pitcher(self, idx, row):
        gl = self.pitcher_game_logs.run(row.mlb_id, row.date, row.year)
        cr = self.get_pitcher_career(row.mlb_id, row.year)
        return pd.concat([row.to_frame().T.reset_index(drop=True),
                          gl.reset_index(drop=True),
                          cr.reset_index(drop=True)], axis=1)

    def get_hitter_career(self, player_id, cutoff_year):
        cutoff_year  = int(cutoff_year)
        current_year = datetime.datetime.now().year
        seasons = [y for y in range(2000, current_year) if y < cutoff_year]
        season_str = ",".join(map(str, seasons))
        url = f"{self.base_url}/people/{player_id}/stats?stats=statSplits&leagueListId=mlb_hist&group=hitting&gameType=R&sitCodes=vl,vr,risp&seasons={season_str}"
        data = self.sess.get(url).json()
        buckets = {"vl": [], "vr": [], "risp": []}
        for s in data["stats"][0]["splits"]:
            code = s["split"]["code"]
            if code in buckets:
                buckets[code].append(s["stat"])
        def agg(lst):
            GP   = sum(s["gamesPlayed"]   for s in lst)
            AB   = sum(s["atBats"]        for s in lst)
            H    = sum(s["hits"]          for s in lst)
            BB   = sum(s["baseOnBalls"]   for s in lst)
            HBP  = sum(s["hitByPitch"]    for s in lst)
            SF   = sum(s["sacFlies"]      for s in lst)
            TB   = sum(s["totalBases"]    for s in lst)
            RBI  = sum(s["rbi"]           for s in lst)
            NUMP = sum(int(s.get("numberOfPitches",0)) for s in lst)
            AVG  = round(H/AB,4) if AB else 0
            OBP  = round((H+BB+HBP)/(AB+BB+HBP+SF),4) if (AB+BB+HBP+SF) else 0
            SLG  = round(TB/AB,4) if AB else 0
            OPS  = round(OBP+SLG,4)
            HR   = sum(s.get("homeRuns",0) for s in lst)
            SO   = sum(s.get("strikeOuts",0) for s in lst)
            BABIP = round((H - HR)/(AB - SO - HR + SF),4) if (AB - SO - HR + SF)>0 else 0
            return {"GP":GP,"AB":AB,"H":H,"BB":BB,"HBP":HBP,"SF":SF,"TB":TB,"RBI":RBI,"P":NUMP,"AVG":AVG,"OBP":OBP,"SLG":SLG,"OPS":OPS,"BABIP":BABIP}
        career = {sp:agg(lst) for sp,lst in buckets.items()}
        career["ovr"] = agg(buckets["vl"]+buckets["vr"])
        flat = {}
        for sp,d in career.items():
            for k,v in d.items():
                flat[f"ovr_{sp}_{k}"] = v
        return pd.DataFrame([flat])

    def get_pitcher_career(self, player_id, cutoff_year):
        cutoff_year  = int(cutoff_year)
        current_year = datetime.datetime.now().year
        seasons = [y for y in range(2000, current_year) if y < cutoff_year]
        season_str = ",".join(map(str, seasons))
        risp_url = f"{self.base_url}/people/{player_id}/stats?stats=statSplits&leagueListId=mlb_hist&group=pitching&gameType=R&sitCodes=risp&seasons={season_str}"
        risp = self.sess.get(risp_url).json().get("stats",[])
        risp_stats = []
        if risp and risp[0].get("splits"):
            risp_stats = [sp["stat"] for sp in risp[0]["splits"] if sp["split"]["code"]=="risp"]
        ovr_url = f"{self.base_url}/people/{player_id}/stats?stats=career&leagueListId=mlb_hist&group=pitching&gameType=R"
        ovr = self.sess.get(ovr_url).json().get("stats",[])
        ovr_stats = ovr[0].get("splits",[])[:1]
        def agg(lst):
            GP  = sum(int(s.get("gamesPlayed",0)) for s in lst)
            GS  = sum(int(s.get("gamesStarted",0))  for s in lst)
            CG  = sum(int(s.get("completeGames",0)) for s in lst)
            SHO = sum(int(s.get("shutouts",0))     for s in lst)
            W   = sum(int(s.get("wins",0))         for s in lst)
            L   = sum(int(s.get("losses",0))       for s in lst)
            SV  = sum(int(s.get("saves",0))        for s in lst)
            SVO = sum(int(s.get("saveOpportunities",0)) for s in lst)
            HLD = sum(int(s.get("holds",0))        for s in lst)
            IP  = sum(float(s.get("inningsPitched",0)) for s in lst)
            H   = sum(int(s.get("hits",0))         for s in lst)
            R   = sum(int(s.get("runs",0))         for s in lst)
            ER  = sum(int(s.get("earnedRuns",0))   for s in lst)
            HR  = sum(int(s.get("homeRuns",0))     for s in lst)
            BB  = sum(int(s.get("baseOnBalls",0))  for s in lst)
            K   = sum(int(s.get("strikeOuts",0))   for s in lst)
            P   = sum(int(s.get("numberOfPitches",0)) for s in lst)
            ERA  = round(ER/IP*9,4) if IP else 0
            WHIP = round((BB+H)/IP,4) if IP else 0
            BF   = sum(int(s.get("battersFaced",0)) for s in lst)
            BA   = round(H/BF,4) if BF else 0
            HBP  = sum(int(s.get("hitByPitch",0)) for s in lst)
            OBPA = round((H+BB+HBP)/BF,4) if BF else 0
            return {"GP":GP,"GS":GS,"CG":CG,"SHO":SHO,"W":W,"L":L,"SV":SV,"SVO":SVO,"HLD":HLD,
                    "IP":round(IP,1),"H":H,"R":R,"ER":ER,"HR":HR,"BB":BB,"K":K,"P":P,
                    "ERA":ERA,"WHIP":WHIP,"BAA":BA,"OBA":OBPA}
        career = {"ovr":agg(ovr_stats),"risp":agg(risp_stats)}
        flat = {}
        for sp,d in career.items():
            for k,v in d.items():
                flat[f"ovr_{sp}_{k}"] = v
        return pd.DataFrame([flat])

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("master_csv")
    p.add_argument("--hitters", action="store_true")
    p.add_argument("--pitchers", action="store_true")
    args = p.parse_args()
    fetcher = StatsFetcher()
    if args.hitters or (not args.pitchers and not args.hitters):
        fetcher.run_hitters(args.master_csv)
    if args.pitchers or (not args.pitchers and not args.hitters):
        fetcher.run_pitchers(args.master_csv)

from flask import Flask, render_template, request, jsonify, abort
import pandas as pd
import io
import firebase_admin
from firebase_admin import credentials, storage
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    "storageBucket": "theshow-587b1.firebasestorage.app"
})
bucket = storage.bucket()

def load_web_data():
    blob = bucket.blob("web_data.csv")
    content = blob.download_as_string()
    df = pd.read_csv(io.BytesIO(content))

    df['confidence_range'] = df['predicted_rank_high'] - df['predicted_rank_low']
    df['confidence_percentage'] = 100 - (df['confidence_range'] * 5)
    df['confidence_percentage'] = df['confidence_percentage'].clip(0, 100)

    df = df.fillna(0)

    num_cols = df.select_dtypes(include='number').columns.tolist()
    pred_cols = [c for c in num_cols if 'pred' in c.lower()]
    df[pred_cols] = df[pred_cols].round(2)
    return df

# Flask app setup
app = Flask(__name__)

df = load_web_data()
full_data  = df.to_dict(orient="records")
judge_data = df[df['name'] == 'Aaron Judge'].iloc[0].to_dict()

@app.context_processor
def inject_globals():
    all_players = [{"name": p["name"], "uuid": p["uuid"]} for p in full_data]
    return {
        "active_page": request.endpoint,
        "all_players": all_players
    }

# QuickSell mapping function

def qs_value(ovr):
    if ovr < 65:        return 5
    if 65  <= ovr < 75: return 25
    if ovr == 75:       return 50
    if ovr == 76:       return 75
    if ovr == 77:       return 100
    if ovr == 78:       return 125
    if ovr == 79:       return 150
    if ovr == 80:       return 400
    if ovr == 81:       return 600
    if ovr == 82:       return 900
    if ovr == 83:       return 1200
    if ovr == 84:       return 1500
    if ovr == 85:       return 3000
    if ovr == 86:       return 3750
    if ovr == 87:       return 4500
    if ovr == 88:       return 5500
    if ovr == 89:       return 7000
    if ovr == 90:       return 8000
    if ovr == 91:       return 9000
    if ovr >= 92:       return 10000
    return 0

# Build lookups for overalls and predictions
uuid_to_ovr    = {p['uuid']: p['ovr'] for p in full_data}
uuid_to_low    = {p['uuid']: p['predicted_rank_low']  for p in full_data}
uuid_to_high   = {p['uuid']: p['predicted_rank_high'] for p in full_data}
uuid_to_avg   = {p['uuid']: p['predicted_rank'] for p in full_data}

# Basic routes
@app.route("/")
def index():
    return render_template("index.html", full_data=full_data, judge_data=judge_data)

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/predictions")
def predictions():
    return render_template("predictions.html", full_data=full_data)

@app.route("/investment")
def investment():
    return render_template("investment.html", full_data=full_data)

@app.route("/account")
def account():
    return render_template("account.html")

@app.context_processor
def inject_active_page():
    return {'active_page': request.endpoint}

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Market price cache setup\ n
MLB_API = "https://mlb25.theshow.com"
_cache = {"ts": 0, "data": {}}
_lock  = threading.Lock()

def _reload_cache():
    """
    Fetch all pages of /apis/listings.json in parallel threads,
    then rebuild _cache["data"] at once under a lock.
    """
    session = requests.Session()
    resp = session.get(f"{MLB_API}/apis/listings.json", params={"type": "mlb_card", "page": 1}, timeout=10)
    resp.raise_for_status()
    j1 = resp.json()
    total_pages = j1.get("total_pages", 1)

    def fetch_page(page_num):
        try:
            r = session.get(f"{MLB_API}/apis/listings.json",
                            params={"type": "mlb_card", "page": page_num},
                            timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"Failed to fetch page {page_num}: {e}")
            return None

    pages = list(range(1, total_pages + 1))

    new_data = {}
    max_workers = min(8, total_pages)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page = {executor.submit(fetch_page, p): p for p in pages}

        for future in as_completed(future_to_page):
            page_num = future_to_page[future]
            result = future.result()
            if result and "listings" in result:
                for L in result["listings"]:
                    item = L["item"]
                    new_data[item["uuid"]] = {
                        "buy":  L.get("best_sell_price"),
                        "sell": L.get("best_buy_price")
                    }
            else:
                print(f"Warning: page {page_num} returned no data or failed.")

    with _lock:
        _cache["ts"]   = time.time()
        _cache["data"] = new_data

def get_market_data():
    if time.time() - _cache["ts"] > 300:
        _reload_cache()
    with _lock:
        return dict(_cache["data"])

@app.route("/api/market_price/<uuid>")
def market_price(uuid):
    info = get_market_data().get(uuid, {}).copy()

    low_f  = uuid_to_low.get(uuid)
    avg_f  = uuid_to_avg.get(uuid)
    high_f = uuid_to_high.get(uuid)

    ovr = uuid_to_ovr.get(uuid)
    if ovr is not None:
        info["qs_actual"] = qs_value(ovr)

    low_i  = int(round(low_f))  if low_f  is not None else None
    avg_i  = int(round(avg_f))  if avg_f  is not None else None
    high_i = int(round(high_f)) if high_f is not None else None

    if low_i is not None:
        info["qs_pred_low"]  = qs_value(low_i)
    if avg_i is not None:
        info["qs_pred"]      = qs_value(avg_i)
    if high_i is not None:
        info["qs_pred_high"] = qs_value(high_i)

    buy = info.get("buy")
    if buy is not None:
        if "qs_pred_low"  in info:
            info["predicted_profit_low"]  = info["qs_pred_low"]  - buy
        if "qs_pred"      in info:
            info["predicted_profit"]      = info["qs_pred"]      - buy
        if "qs_pred_high" in info:
            info["predicted_profit_high"] = info["qs_pred_high"] - buy

        if all(k in info for k in ("predicted_profit_low",
                                   "predicted_profit",
                                   "predicted_profit_high")):
            p_low, p_mid, p_high = 0.025, 0.95, 0.025
            ev = (
                p_low  * info["predicted_profit_low"] +
                p_mid  * info["predicted_profit"] +
                p_high * info["predicted_profit_high"]
            )
            info["predicted_ev_profit"] = round(ev, 2)

        if "predicted_profit" in info and buy != 0:
            pct = (info["predicted_profit"] / buy) * 100
            info["predicted_profit_pct"] = round(pct, 2)
        else:
            info["predicted_profit_pct"] = 0.0
        info["market_price"] = buy

    return jsonify(info)

@app.route("/player/<uuid>")
def player(uuid):
    player = next((p for p in full_data if p["uuid"] == uuid), None)
    if not player:
        abort(404)

    info = get_market_data().get(uuid, {}).copy()

    low_f  = uuid_to_low.get(uuid)
    avg_f  = uuid_to_avg.get(uuid)
    high_f = uuid_to_high.get(uuid)

    ovr = uuid_to_ovr.get(uuid)
    if ovr is not None:
        info["qs_actual"] = qs_value(ovr)

    low_i  = int(round(low_f))  if low_f  is not None else None
    avg_i  = int(round(avg_f))  if avg_f  is not None else None
    high_i = int(round(high_f)) if high_f is not None else None

    if low_i is not None:
        info["qs_pred_low"]  = qs_value(low_i)
    if avg_i is not None:
        info["qs_pred"]      = qs_value(avg_i)
    if high_i is not None:
        info["qs_pred_high"] = qs_value(high_i)

    buy = info.get("buy")
    if buy is not None:
        if "qs_pred_low"  in info:
            info["predicted_profit_low"]  = info["qs_pred_low"]  - buy
        if "qs_pred"      in info:
            info["predicted_profit"]      = info["qs_pred"]      - buy
        if "qs_pred_high" in info:
            info["predicted_profit_high"] = info["qs_pred_high"] - buy

        if all(k in info for k in ("predicted_profit_low",
                                   "predicted_profit",
                                   "predicted_profit_high")):
            p_low, p_mid, p_high = 0.025, 0.95, 0.025
            ev = (
                p_low  * info["predicted_profit_low"] +
                p_mid  * info["predicted_profit"] +
                p_high * info["predicted_profit_high"]
            )
            info["predicted_ev_profit"] = ev

        if "predicted_profit" in info and buy != 0:
            pct = (info["predicted_profit"] / buy) * 100
            info["predicted_profit_pct"] = round(pct, 2)
        else:
            info["predicted_profit_pct"] = 0.0

        if "predicted_profit_low" in info and buy != 0:
            pct = (info["predicted_profit_low"] / buy) * 100
            info["predicted_profit_pct_low"] = round(pct, 2)
        else:
            info["predicted_profit_pct_low"] = 0.0

        if "predicted_profit_high" in info and buy != 0:
            pct = (info["predicted_profit_high"] / buy) * 100
            info["predicted_profit_pct_high"] = round(pct, 2)
        else:
            info["predicted_profit_pct_high"] = 0.0
        
        info["market_price"] = buy

    merged = player.copy()
    merged.update(info)

    return render_template("player.html", player=merged)

if __name__ == "__main__":
    app.run(debug=True)

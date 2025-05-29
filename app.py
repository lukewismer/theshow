from flask import Flask, render_template, request
import pandas as pd
import io
import firebase_admin
from firebase_admin import credentials, storage

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    "storageBucket": "theshow-587b1.firebasestorage.app"
})
bucket = storage.bucket()

def load_web_data():
    """Download web_data.csv from Firebase Storage via Firebase Admin SDK."""
    blob = bucket.blob("web_data.csv")
    content = blob.download_as_string()
    df = pd.read_csv(io.BytesIO(content))

    df['confidence_range'] = df['predicted_rank_high'] - df['predicted_rank_low']
    df['confidence_percentage'] = 100 - (df['confidence_range'] * 5)
    df['confidence_percentage'] = df['confidence_percentage'].clip(0, 100)

    return df

app = Flask(__name__)

df = load_web_data()
full_data = df.to_dict(orient="records")

judge_data = df[df['name'] == 'Aaron Judge'].iloc[0].to_dict()

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

if __name__ == "__main__":
    app.run(debug=True)

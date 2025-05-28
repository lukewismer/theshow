from flask import Flask, render_template
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
    return pd.read_csv(io.BytesIO(content))

app = Flask(__name__)

df = load_web_data()
full_data = df.to_dict(orient="records")

@app.route("/")
def index():
    return render_template("index.html", full_data=full_data)

@app.route("/login")
def login():
    return None

if __name__ == "__main__":
    app.run(debug=True)

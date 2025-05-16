from flask import Flask, render_template, request, jsonify
import pandas as pd
import os

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data_with_metrics.csv')
# debug: print out where Flask is looking
print(f"→ Looking for data file at: {DATA_FILE}")

# sanity check
if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"Could not find data file at {DATA_FILE}. "
                            "Make sure you placed data_with_metrics.csv next to app.py.")
try:
    df = pd.read_csv(DATA_FILE)
except FileNotFoundError:
    df = pd.DataFrame()

full_data = df.to_dict(orient='records')

@app.route('/')
def index():
    return render_template('index.html', full_data=full_data)

if __name__ == '__main__':
    app.run(debug=True)
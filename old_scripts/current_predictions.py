import pandas as pd
import numpy as np
import torch
import joblib

z = 1.96

# 1) Load metadata
feature_cols = joblib.load("feature_cols.pkl")
num_cols     = joblib.load("num_cols.pkl")
cat_cols     = joblib.load("cat_cols.pkl")
scaler       = joblib.load("scaler.pkl")
encoder      = joblib.load("encoder.pkl")

# 2) Read the full original CSV
df_orig = pd.read_csv("players_with_stats_merged_cur.csv", dtype={"uuid": str})

# 3) Build a working copy for features
df_feat = df_orig.copy()
df_feat = df_feat.apply(pd.to_numeric, errors="coerce").fillna(0)

# 4) Align feature columns
for c in feature_cols:
    if c not in df_feat.columns:
        df_feat[c] = 0
df_feat = df_feat[feature_cols]

# 5) Transform to X
X_num = scaler.transform(df_feat[num_cols])
X_cat = encoder.transform(df_feat[cat_cols]) if cat_cols else np.empty((len(df_feat),0))
X     = np.hstack([X_num, X_cat])

# 6) Predict and attach back to df_orig
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class BayesianRankNet(torch.nn.Module):
    def __init__(self, in_dim, hiddens=[1024,512,256,128,64]):
        super().__init__()
        layers, prev = [], in_dim
        for h in hiddens:
            layers += [torch.nn.Linear(prev,h), torch.nn.ReLU()]
            prev = h
        self.body = torch.nn.Sequential(*layers)
        self.mu   = torch.nn.Linear(prev,1)
        self.lv   = torch.nn.Linear(prev,1)
    def forward(self,x):
        h = self.body(x)
        return self.mu(h), self.lv(h).clamp(-10,2)

for role in ["hitter","pitcher"]:
    ckpt   = torch.load(f"best_model_zero_infl_{role}.pt", map_location=device)
    in_dim = ckpt["body.0.weight"].shape[1]
    model  = BayesianRankNet(in_dim).to(device)
    model.load_state_dict(ckpt)
    model.eval()

    with torch.no_grad():
        xb      = torch.tensor(X, dtype=torch.float32).to(device)
        mu, lv  = model(xb)
        mu_np   = mu.cpu().numpy().flatten()
        var_np  = np.exp(lv.cpu().numpy().flatten())
        sigma   = np.sqrt(var_np)
        low95   = mu_np - z * sigma
        high95  = mu_np + z * sigma

    # attach three columns per role
    df_orig[f"mu_{role}"]         = mu_np
    df_orig[f"low95_{role}"]      = low95
    df_orig[f"high95_{role}"]     = high95

# then save
df_orig.to_csv("players_with_stats_with_preds.csv", index=False)
print("Saved players_with_stats_with_preds.csv with original metadata + predictions.")

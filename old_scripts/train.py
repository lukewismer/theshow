import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.metrics import precision_score, recall_score
import joblib


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

df = (
    pd.read_csv("train.csv", dtype={"uuid": str}, low_memory=False)
      .apply(pd.to_numeric, errors="coerce")
      .fillna(0)
)


exclude = [
    "uuid", "update", "ovr", "rarity", "new_rarity", "new_rank",
    "delta_rank", "name", "mlb_id", "display_secondary_positions"
]
feature_cols = [c for c in df.columns if c not in exclude]

groups = {
    "hitter":  df[df["is_hitter"]].reset_index(drop=True),
    "pitcher": df[~df["is_hitter"]].reset_index(drop=True)
}

X_full   = df[feature_cols]
num_cols = X_full.select_dtypes(include=np.number).columns.tolist()
cat_cols = X_full.select_dtypes(exclude=np.number).columns.tolist()

scaler  = StandardScaler().fit(X_full[num_cols])
encoder = (
    OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    .fit(X_full[cat_cols])
) if cat_cols else None


joblib.dump(feature_cols, "feature_cols.pkl")
joblib.dump(num_cols,       "num_cols.pkl")
joblib.dump(cat_cols,       "cat_cols.pkl")
joblib.dump(scaler,         "scaler.pkl")
if encoder:
    joblib.dump(encoder,    "encoder.pkl")

class BayesianRankNet(nn.Module):
    def __init__(self, in_dim, hiddens=[1024,512,256,128,64]):
        super().__init__()
        layers, prev = [], in_dim
        for h in hiddens:
            layers += [nn.Linear(prev,h), nn.ReLU()]
            prev = h
        self.body = nn.Sequential(*layers)
        self.mu   = nn.Linear(prev,1)
        self.lv   = nn.Linear(prev,1)
    def forward(self,x):
        h = self.body(x)
        return self.mu(h), self.lv(h).clamp(-10,2)

def zero_infl_nll(mu, logvar, y):
    var  = torch.exp(logvar) + 1e-6
    inv  = 1.0 / var
    base = 0.5 * (torch.log(var) + (y-mu)**2 * inv + np.log(2*np.pi))
    w    = torch.where(y.abs()>1e-6,
                       torch.tensor(2.0, device=y.device),
                       torch.tensor(1.0, device=y.device))
    return (base * w).mean()

class RosterDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
    def __len__(self): return len(self.y)
    def __getitem__(self, i): return self.X[i], self.y[i]

for role, subdf in groups.items():
    print(f"\n===== Training {role} model =====")
    X_df = subdf[feature_cols]
    y    = subdf["delta_rank"].astype(np.float32).values

    X_num = scaler.transform(X_df[num_cols])
    X_cat = encoder.transform(X_df[cat_cols]) if encoder else np.empty((len(X_df),0))
    X     = np.hstack([X_num, X_cat])

    kf, best_state, best_rmse = KFold(5, shuffle=True, random_state=0), None, float("inf")
    for fold, (tr, va) in enumerate(kf.split(X), 1):
        X_tr, y_tr = X[tr], y[tr]
        X_va, y_va = X[va], y[va]

        w_tr    = np.where(y_tr != 0, 2.0, 1.0)
        sampler = WeightedRandomSampler(w_tr, len(w_tr), True)
        tr_loader = DataLoader(RosterDataset(X_tr, y_tr), batch_size=128, sampler=sampler)
        va_loader = DataLoader(RosterDataset(X_va, y_va), batch_size=128)

        model = BayesianRankNet(X.shape[1]).to(device)
        opt   = torch.optim.Adam(model.parameters(), lr=1e-3)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=100, eta_min=1e-5)
        L1    = 1e-5

        for ep in range(1, 101):
            model.train()
            for xb, yb in tr_loader:
                xb, yb = xb.to(device), yb.to(device)
                mu, lv = model(xb)
                loss   = zero_infl_nll(mu, lv, yb) + L1 * sum(p.abs().sum() for p in model.parameters())
                opt.zero_grad()
                loss.backward()
                opt.step()
            sched.step()

        model.eval()
        preds, truths = [], []
        with torch.no_grad():
            for xb, yb in va_loader:
                xb, yb = xb.to(device), yb.to(device)
                preds.append(model(xb)[0].cpu().numpy().flatten())
                truths.append(yb.cpu().numpy().flatten())
        preds, truths = np.concatenate(preds), np.concatenate(truths)
        rmse = np.sqrt(((preds - truths) ** 2).mean())

        print(f" {role} Fold {fold} — RMSE={rmse:.3f}")
        if rmse < best_rmse:
            best_rmse, best_state = rmse, model.cpu().state_dict()

    torch.save(best_state, f"best_model_zero_infl_{role}.pt")
    print(f"Saved best {role} (RMSE={best_rmse:.3f})")

"""
hitter_inference.py

Run this script to infer hitter attribute changes and overall rank predictions
with low, mean, and high scenarios.
"""
import os
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
import sklearn

MODEL_DIR   = "../model"
INPUT_CSV   = "hitter_stats_cur.csv"
OUTPUT_CSV  = "hitter_stats_with_delta_preds.csv"
Z           = 1.96

def main():
    df = pd.read_csv(INPUT_CSV, low_memory=False)
    df = df[df.is_hitter & (df['3wk_gp'] > 0)]
    df["old_rank"] = df["ovr"]

    meta_cols = [c for c in ['uuid','name','old_rank'] if c in df.columns]
    df_meta = df[meta_cols].reset_index(drop=True)

    scaler_all = joblib.load(os.path.join(MODEL_DIR, "scaler_all_xgb.joblib"))
    enc_cat    = joblib.load(os.path.join(MODEL_DIR, "onehot_encoder_all_xgb.joblib"))

    for c in scaler_all.feature_names_in_:
        if c not in df.columns:
            df[c] = 0

    X_num = scaler_all.transform(df[scaler_all.feature_names_in_].fillna(0))
    X_cat = enc_cat.transform(df[[]])  
    X_all = np.hstack([X_num, X_cat])
    feat_names = list(scaler_all.feature_names_in_)

    hitting_stats = [
        ('contact_right','contact_right_new'),
        ('contact_left', 'contact_left_new'),
        ('power_right',  'power_right_new'),
        ('power_left',   'power_left_new'),
        ('plate_vision','plate_vision_new'),
        ('plate_discipline','plate_discipline_new'),
        ('batting_clutch','batting_clutch_new')
    ]
    stat_targets = [new for _, new in hitting_stats]

    mu_models = {}
    for stat in stat_targets:
        m = xgb.Booster()
        m.load_model(os.path.join(MODEL_DIR, f"{stat}_xgb_mu_all.json"))
        mu_models[stat] = m

    sigma_models = {}
    for stat in stat_targets:
        s = xgb.XGBRegressor()
        s.load_model(os.path.join(MODEL_DIR, f"{stat}_xgb_logvar_all.json"))
        sigma_models[stat] = s

    dmat = xgb.DMatrix(X_all, feature_names=feat_names)
    mus    = np.column_stack([mu_models[s].predict(dmat) for s in stat_targets])
    sigmas = np.column_stack([np.sqrt(np.exp(sigma_models[s].predict(X_all))) for s in stat_targets])

    pred_df = pd.DataFrame(mus, columns=[f"{s}_pred" for s in stat_targets])
    pred_low  = mus - Z * sigmas
    pred_high = mus + Z * sigmas

    for i, (old, new) in enumerate(hitting_stats):
        pred_df[f"{new}_low"]   = pred_low[:, i]
        pred_df[f"{new}_high"]  = pred_high[:, i]
        pred_df[f"{old}_change_low"]  = pred_df[f"{new}_low"]  - df[old].values
        pred_df[f"{old}_change_pred"] = pred_df[f"{new}_pred"] - df[old].values
        pred_df[f"{old}_change_high"] = pred_df[f"{new}_high"] - df[old].values

    def make_delta_dmatrix(attr_preds):
        df_attr = pd.DataFrame(attr_preds, columns=[f"{s}_pred" for s in stat_targets])
        for old, new in hitting_stats:
            df_attr[f"{old}_delta"] = df_attr[f"{new}_pred"].values - df[old].values
        feature_cols = [f"{old}_delta" for old,_ in hitting_stats]
        return xgb.DMatrix(df_attr[feature_cols].values, feature_names=feature_cols)

    dmat_low  = make_delta_dmatrix(pred_low)
    dmat_mu   = make_delta_dmatrix(mus)
    dmat_high = make_delta_dmatrix(pred_high)

    delta_booster = xgb.Booster()
    delta_booster.load_model(os.path.join(MODEL_DIR, "delta_agg_full.json"))

    df_meta["delta_rank_low"]  = delta_booster.predict(dmat_low)
    df_meta["delta_rank_pred"] = delta_booster.predict(dmat_mu)
    df_meta["delta_rank_high"] = delta_booster.predict(dmat_high)

    df_meta["predicted_rank_low"]  = df_meta["old_rank"] + df_meta["delta_rank_low"]
    df_meta["predicted_rank"]      = df_meta["old_rank"] + df_meta["delta_rank_pred"]
    df_meta["predicted_rank_high"] = df_meta["old_rank"] + df_meta["delta_rank_high"]

    for c in [
        "delta_rank_low","delta_rank_pred","delta_rank_high",
        "predicted_rank_low","predicted_rank","predicted_rank_high"
    ]:
        df_meta[c] = df_meta[c].round(2)

    out = pd.concat([df_meta, df.reset_index(drop=True), pred_df], axis=1)
    out.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved updated predictions → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

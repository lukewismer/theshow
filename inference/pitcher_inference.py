import os
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
import sklearn

def infer_pitchers(
    input_csv="./inference/pitcher_stats_cur.csv",
    model_dir="./model",
    z=1.96
):
    df = pd.read_csv(input_csv, low_memory=False)
    df = df[~df.is_hitter & (df["3wk_gp"] > 0)]

    meta_cols = [c for c in ["uuid","name","old_rank"] if c in df.columns]
    df_meta   = df[meta_cols].reset_index(drop=True)

    scaler  = joblib.load(os.path.join(model_dir, "scaler_pitcher.joblib"))
    enc_cat = joblib.load(os.path.join(model_dir, "onehot_encoder_pitcher.joblib"))

    for c in scaler.feature_names_in_:
        if c not in df.columns:
            df[c] = 0

    X_num   = scaler.transform(df[scaler.feature_names_in_].fillna(0))
    X_cat   = enc_cat.transform(df[[]])
    X_all   = np.hstack([X_num, X_cat])
    feat_names = list(scaler.feature_names_in_) + enc_cat.get_feature_names_out([]).tolist()

    attributes = [
        ("k_per_bf",        "k_per_bf_new"),
        ("bb_per_bf",       "bb_per_bf_new"),
        ("hr_per_bf",       "hr_per_bf_new"),
        ("pitching_clutch", "pitching_clutch_new"),
        ("stamina",         "stamina_new"),
    ]
    stat_targets = [new for _, new in attributes]

    mu_models = {}
    for stat in stat_targets:
        m = xgb.Booster()
        m.load_model(os.path.join(model_dir, f"{stat}_mu_all.json"))
        mu_models[stat] = m

    sigma_models = {}
    for stat in stat_targets:
        s = xgb.XGBRegressor()
        s.load_model(os.path.join(model_dir, f"{stat}_logvar_all.json"))
        sigma_models[stat] = s

    dmat = xgb.DMatrix(X_all, feature_names=feat_names)
    mus  = np.column_stack([mu_models[s].predict(dmat) for s in stat_targets])
    sigmas = np.column_stack([
        np.sqrt(np.exp(sigma_models[s].predict(X_all)))
        for s in stat_targets
    ])

    pred_df  = pd.DataFrame(mus, columns=[f"{s}_pred" for s in stat_targets])
    pred_low  = mus - z * sigmas
    pred_high = mus + z * sigmas

    for i, (old, new) in enumerate(attributes):
        pred_df[f"{new}_low"]       = pred_low[:, i]
        pred_df[f"{new}_high"]      = pred_high[:, i]
        pred_df[f"{old}_change_low"]  = pred_df[f"{new}_low"]  - df[old].values
        pred_df[f"{old}_change_pred"] = pred_df[f"{new}_pred"] - df[old].values
        pred_df[f"{old}_change_high"] = pred_df[f"{new}_high"] - df[old].values

    def build_delta_dmatrix(arr):
        tmp = pd.DataFrame(arr, columns=[f"{s}_pred" for s in stat_targets])
        for old, new in attributes:
            tmp[f"{old}_delta"] = tmp[f"{new}_pred"] - df[old].values
        cols = [f"{old}_delta" for old, _ in attributes]
        return xgb.DMatrix(tmp[cols].values, feature_names=cols)

    atts_low  = pred_low
    atts_mu   = mus
    atts_high = pred_high

    d_low  = build_delta_dmatrix(atts_low)
    d_mu   = build_delta_dmatrix(atts_mu)
    d_high = build_delta_dmatrix(atts_high)

    agg = xgb.Booster()
    agg.load_model(os.path.join(model_dir, "pitcher_delta_agg_full.json"))

    df_meta["delta_rank_low"]  = agg.predict(d_low)
    df_meta["delta_rank_pred"] = agg.predict(d_mu)
    df_meta["delta_rank_high"] = agg.predict(d_high)

    df_meta["predicted_rank_low"]  = df_meta["old_rank"] + df_meta["delta_rank_low"]
    df_meta["predicted_rank"]      = df_meta["old_rank"] + df_meta["delta_rank_pred"]
    df_meta["predicted_rank_high"] = df_meta["old_rank"] + df_meta["delta_rank_high"]

    for c in [
        "delta_rank_low","delta_rank_pred","delta_rank_high",
        "predicted_rank_low","predicted_rank","predicted_rank_high"
    ]:
        df_meta[c] = df_meta[c].round(2)

    return pd.concat([df_meta, df.reset_index(drop=True), pred_df], axis=1)

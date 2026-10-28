"""Train and evaluate M2 on world v2. Users: A fits the app-fingerprint model, B fits M2 (80 % train / 20 % calibration),
C is the held-out test set; all splits are by user. Needs the M1 outputs of paibo_bip/m1/train_m1.py.

Heads: req_soon (a bearer request within 60 s), next class, per-class set (ordered 5QI list), time to request (p10/p50/p90),
GBR of the next GBR flow, plus deterministic DRB count / S-NSSAI. Output of each classifier is calibrated on held-out users.

Run: python -m paibo_bip.m2.train_m2 [--m1 small_ft|student]
"""
import argparse
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

from ..evaluate_grouped import cluster_bootstrap, ece
from ..world2 import spec as S
from ..world2.generate import generate_world
from ..world2.instants import UserIndex, dominant_active_class
from ..m1.train_m1 import M1_FEATURE_NAMES, WORLD
from .heads import (ALWAYS, CATEGORICAL, FAMILIES, BinaryHead, MultiHead, QuantileHead, ValueHead, columns, design,
                    mask_training_rows, testbed_profile)

M1_DIR = os.environ.get("PAIBO_M1_DIR", os.path.expanduser("~/paibo_gpu_ai_experiment/m1_v1"))
OUT = os.environ.get("PAIBO_M2_DIR", os.path.expanduser("~/paibo_gpu_ai_experiment/m2_v1"))
FP_COLS = ["thr_mean", "thr_max", "thr_std", "thr_last10", "thr_trend", "active_frac", "iat_mean", "pkt_mean", "burst", "idle_s"]
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]
SEED = 0


def drb_rule(classes):
    """Recommended DRB count from a set of predicted flow classes: one DRB per GBR flow, one shared DRB per slice for
    non-GBR flows (the QoS-consolidation rule; deterministic)."""
    classes = list(classes)
    gbr = sum(bool(S.CLASS_IS_GBR[c]) for c in classes)
    slices = {int(S.CLASS_SST[c]) for c in classes if not S.CLASS_IS_GBR[c]}
    return gbr + len(slices)


def macro_f1(y, p):
    return float(f1_score(y, p, labels=list(range(S.K)), average="macro", zero_division=0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m1", default="small_ft")
    ap.add_argument("--no-ablation", action="store_true")
    ap.add_argument("--ordinal", action="store_true", help="no categorical splits (needed for the C export)")
    ap.add_argument("--robust", action="store_true", help="train with missing-feature (deployment profile) masking")
    a = ap.parse_args()
    CATMODE = not a.ordinal
    tag = a.m1 + ("_ordinal" if a.ordinal else "") + ("_robust" if a.robust else "")
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time()-t0:5.0f}s] {s}", flush=True)

    df = pd.read_pickle(os.path.join(M1_DIR, "instants.pkl"))
    split = {k: np.array(v) for k, v in json.load(open(os.path.join(M1_DIR, "split.json"))).items()}
    m1 = np.load(os.path.join(M1_DIR, f"m1_features_{a.m1}.npy"))
    for i, n in enumerate(M1_FEATURE_NAMES):
        df[n] = m1[:, i]
    uid = df["uid"].to_numpy()
    in_A = np.isin(uid, np.concatenate([split["A_train"], split["A_val"]]))
    in_B, in_C = np.isin(uid, split["B"]), np.isin(uid, split["C"])
    rng = np.random.default_rng(SEED)
    b_users = split["B"].copy(); rng.shuffle(b_users)
    cal_users = set(b_users[: len(b_users) // 5].tolist())
    in_Bcal = in_B & np.isin(uid, list(cal_users))
    in_Btr = in_B & ~in_Bcal
    log(f"instants {len(df)}: A {in_A.sum()}, B-train {in_Btr.sum()}, B-calibration {in_Bcal.sum()}, C-test {in_C.sum()}")


    users = generate_world(WORLD)
    uix = {u.uid: UserIndex(u) for u in users}
    idxA = np.where(in_A & (df["thr_mean"].to_numpy() > 0))[0]
    dom = np.array([dominant_active_class(uix[int(df["uid"].iat[i])], float(df["t"].iat[i])) for i in idxA])
    ok = dom >= 0
    fp = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.1, early_stopping=False, random_state=0)
    fp.fit(df[FP_COLS].to_numpy()[idxA[ok]], dom[ok])
    act = df["thr_mean"].to_numpy() > 0
    P = np.zeros((len(df), S.K))
    P[act] = fp.predict_proba(df[FP_COLS].to_numpy()[act])[:, np.argsort(fp.classes_)] if len(fp.classes_) == S.K else 0
    for c in range(S.K):
        df[f"fp_p{c}"] = P[:, c]
    df["fp_applicable"] = act.astype(float)
    idxC = np.where(in_C & act)[0]
    domC = np.array([dominant_active_class(uix[int(df["uid"].iat[i])], float(df["t"].iat[i])) for i in idxC])
    okC = domC >= 0
    fp_acc = float((P[idxC[okC]].argmax(1) == domC[okC]).mean())
    log(f"fingerprint model: accuracy of the active app from flow characteristics on held-out users = {fp_acc:.3f} (n={okC.sum()})")

    results = {"m1_variant": a.m1, "fingerprint_accuracy_C": fp_acc, "sizes": {}, "user_split": "by user: A fingerprint, B M2 (80/20 cal), C test"}
    cols = columns()
    X, cat = design(df, cols, CATMODE)
    if a.robust:
        Xm, _ = design(mask_training_rows(df, SEED + 7), cols, CATMODE)
        Xtr, Xcal = Xm[in_Btr], Xm[in_Bcal]
    else:
        Xtr, Xcal = X[in_Btr], X[in_Bcal]
    Xte = X[in_C]
    Xte_tb, _ = design(testbed_profile(df[in_C]), cols, CATMODE)
    d_tr, d_cal, d_te = df[in_Btr], df[in_Bcal], df[in_C]
    results["n_features"] = len(cols)


    h1 = BinaryHead(cat).fit(Xtr, d_tr.req_soon.to_numpy(), Xcal, d_cal.req_soon.to_numpy())
    p1, p1raw, y1 = h1.predict_proba(Xte), h1.raw_proba(Xte), d_te.req_soon.to_numpy()
    ev = d_te.ev_type.to_numpy()
    base_rate = {e: float(d_tr.req_soon[d_tr.ev_type == e].mean()) for e in (0, 1)}
    pb = np.array([base_rate[e] for e in ev])
    ho = ev == 1
    results["req_soon"] = {
        "auroc_all": float(roc_auc_score(y1, p1)), "auroc_handover_events": float(roc_auc_score(y1[ho], p1[ho])),
        "auprc_handover_events": float(average_precision_score(y1[ho], p1[ho])),
        "base_rate_handover": float(y1[ho].mean()),
        "baseline_event_type_auroc_handover": float(roc_auc_score(y1[ho], pb[ho])) if len(set(pb[ho])) > 1 else 0.5,
        "brier_calibrated": float(np.mean((p1 - y1) ** 2)), "brier_uncalibrated": float(np.mean((p1raw - y1) ** 2)),
        "ece_calibrated": ece(np.maximum(p1, 1 - p1), ((p1 >= 0.5) == (y1 == 1)).astype(float)),
        "brier_baseline_event_type": float(np.mean((pb - y1) ** 2))}
    log(f"head req_soon: {results['req_soon']}")


    pos = lambda d: d.req_soon.to_numpy() == 1
    h2 = MultiHead(cat).fit(Xtr[pos(d_tr)], d_tr.next_cls.to_numpy()[pos(d_tr)], Xcal[pos(d_cal)], d_cal.next_cls.to_numpy()[pos(d_cal)])
    Pte = pos(d_te)
    p2 = h2.predict_proba(Xte[Pte])
    y2 = d_te.next_cls.to_numpy()[Pte]
    pred2 = p2.argmax(1)
    top = np.argsort(-p2, axis=1)
    ytr = d_tr.next_cls.to_numpy()[pos(d_tr)]
    maj = int(np.bincount(ytr, minlength=S.K).argmax())
    dt, dp = d_te[Pte], d_tr[pos(d_tr)]
    last1 = dt.last1_cls.to_numpy()
    hist_maj = dt[[f"hist_logfreq_{c}" for c in range(S.K)]].to_numpy().argmax(1)
    cond = dp.groupby(["group_obs", "ev_type"]).next_cls.agg(lambda s: int(s.value_counts().index[0]))
    cond_pred = np.array([cond.get((g, e), maj) for g, e in zip(dt.group_obs, dt.ev_type)])
    results["next_class"] = {
        "n": int(len(y2)), "accuracy": float((pred2 == y2).mean()), "macro_f1": macro_f1(y2, pred2),
        "top2": float((top[:, :2] == y2[:, None]).any(1).mean()), "top3": float((top[:, :3] == y2[:, None]).any(1).mean()),
        "baseline_global_majority": float((y2 == maj).mean()),
        "baseline_last_request_class": float((np.where(last1 >= 0, last1, maj) == y2).mean()),
        "baseline_history_majority": float((hist_maj == y2).mean()),
        "baseline_group_event_conditional": float((cond_pred == y2).mean()),
        "brier": float(np.mean(np.sum((p2 - np.eye(S.K)[y2]) ** 2, axis=1))),
        "ece": ece(p2.max(1), (pred2 == y2).astype(float))}
    cluster = dt.uid.to_numpy()
    masks = {t: p2.max(1) >= t for t in THRESHOLDS}
    boot = cluster_bootstrap(cluster, pred2 == y2, masks, np.random.default_rng(1))
    results["next_class"]["gate"] = {f"t{t}": {"coverage": float(masks[t].mean()),
                                                "accuracy_accepted": float((pred2 == y2)[masks[t]].mean()) if masks[t].any() else None,
                                                "lift_ci95": boot[f"t{t}"]["lift_ci95"]} for t in THRESHOLDS}
    log(f"head next_class: { {k: (round(v, 3) if isinstance(v, float) else v) for k, v in results['next_class'].items() if k != 'gate'} }")

    p1_tb, p2_tb = h1.predict_proba(Xte_tb), h2.predict_proba(Xte_tb[Pte])
    results["testbed_profile_inputs_missing"] = {
        "note": "same held-out users, but the features the ns-3 gNB cannot observe are set to NaN",
        "unavailable": sorted(set(__import__("paibo_bip.m2.heads", fromlist=["x"]).TESTBED_UNAVAILABLE)),
        "req_soon_auroc_handover": float(roc_auc_score(y1[ho], p1_tb[ho])),
        "next_class_accuracy": float((p2_tb.argmax(1) == y2).mean()), "next_class_top2": float((np.argsort(-p2_tb, axis=1)[:, :2] == y2[:, None]).any(1).mean()),
        "next_class_macro_f1": macro_f1(y2, p2_tb.argmax(1))}
    log(f"testbed-profile inputs: {results['testbed_profile_inputs_missing']}")


    h3 = [BinaryHead(cat).fit(Xtr, d_tr[f"in_H_{c}"].to_numpy(), Xcal, d_cal[f"in_H_{c}"].to_numpy()) for c in range(S.K)]
    P3 = np.stack([h.predict_proba(Xte) for h in h3], axis=1)
    Y3 = d_te[[f"in_H_{c}" for c in range(S.K)]].to_numpy()
    sets_pred = P3 >= 0.5
    tp = (sets_pred & (Y3 == 1)).sum(); fpn = (sets_pred & (Y3 == 0)).sum(); fnn = ((~sets_pred) & (Y3 == 1)).sum()
    results["class_set"] = {"per_class_auroc": {S.CLASSES[c]: float(roc_auc_score(Y3[:, c], P3[:, c])) for c in range(S.K) if 0 < Y3[:, c].sum() < len(Y3)},
                            "micro_f1_at_0.5": float(2 * tp / max(2 * tp + fpn + fnn, 1)),
                            "exact_set_match_at_0.5": float((sets_pred == (Y3 == 1)).all(1).mean())}
    log(f"head class_set: {results['class_set']}")


    h4 = QuantileHead(cat).fit(Xtr[pos(d_tr)], d_tr.t_req_s.to_numpy()[pos(d_tr)])
    qt = h4.predict(Xte[Pte])
    yt = dt.t_req_s.to_numpy()
    med_base = float(np.median(dp.t_req_s))
    hoP = dt.ev_type.to_numpy() == 1
    results["time_to_request_s"] = {
        "mae_median_all": float(np.abs(qt[:, 1] - yt).mean()), "mae_baseline_global_median": float(np.abs(med_base - yt).mean()),
        "mae_median_handover": float(np.abs(qt[hoP, 1] - yt[hoP]).mean()), "mae_baseline_handover": float(np.abs(np.median(dp.t_req_s[dp.ev_type == 1]) - yt[hoP]).mean()),
        "p10_p90_coverage": float(((yt >= qt[:, 0]) & (yt <= qt[:, 2])).mean())}
    log(f"head time: {results['time_to_request_s']}")


    gp = lambda d: (d.gbr_first_kbps.to_numpy() > 0)
    h5 = ValueHead(cat).fit(Xtr[gp(d_tr)], d_tr.gbr_first_kbps.to_numpy()[gp(d_tr)])
    Gte = gp(d_te)
    g_pred, g_true = h5.predict(Xte[Gte]), d_te.gbr_first_kbps.to_numpy()[Gte]


    ach = d_te.achievable_kbps.to_numpy()[Gte]
    feas_true, feas_pred = ach >= g_true, ach >= g_pred
    results["gbr_kbps"] = {"n": int(Gte.sum()), "mae_gbt": float(np.abs(g_pred - g_true).mean()),
                           "feasibility_flag_accuracy": float((feas_true == feas_pred).mean()),
                           "feasibility_flag_baseline_always_feasible": float(feas_true.mean()),
                           "mae_baseline_global_median": float(np.abs(np.median(d_tr.gbr_first_kbps[gp(d_tr)]) - g_true).mean()),
                           "mae_baseline_last_gbr": float(np.abs(np.where(d_te.last_gbr_kbps.to_numpy()[Gte] > 0, d_te.last_gbr_kbps.to_numpy()[Gte], np.median(d_tr.gbr_first_kbps[gp(d_tr)])) - g_true).mean()),
                           "relative_error_median": float(np.median(np.abs(g_pred - g_true) / g_true))}
    log(f"head gbr: {results['gbr_kbps']}")


    sub = d_te[[f"sub_slice_{s}" for s in (1, 2, 3)]].to_numpy()
    drb_pred, sst_pred = [], []
    for i in np.where(d_te.req_soon.to_numpy() == 1)[0]:
        pset = [c for c in range(S.K) if P3[i, c] >= 0.5] or [int(P3[i].argmax())]
        allowed = [c for c in pset if sub[i, S.CLASS_SST[c] - 1] > 0] or pset
        drb_pred.append(drb_rule(allowed))
        top1 = int(np.argmax([P3[i, c] if sub[i, S.CLASS_SST[c] - 1] > 0 else -1 for c in range(S.K)]))
        sst_pred.append(int(S.CLASS_SST[top1]))
    pi = d_te.req_soon.to_numpy() == 1
    drb_true, sst_true = d_te.drb_count.to_numpy()[pi], d_te.target_sst.to_numpy()[pi]
    results["drb_and_slice"] = {"drb_accuracy": float((np.array(drb_pred) == drb_true).mean()),
                                "drb_mae": float(np.abs(np.array(drb_pred) - drb_true).mean()),
                                "drb_baseline_always_1_accuracy": float((drb_true == 1).mean()),
                                "sst_accuracy": float((np.array(sst_pred) == sst_true).mean()),
                                "sst_baseline_majority": float((sst_true == np.bincount(sst_true).argmax()).mean())}
    log(f"drb/slice: {results['drb_and_slice']}")


    results["sizes"] = {"req_soon_nodes": h1.nodes(), "next_class_nodes": h2.nodes(), "class_set_nodes": sum(h.nodes() for h in h3),
                        "time_nodes": h4.nodes(), "gbr_nodes": h5.nodes()}
    results["sizes"]["total_tree_nodes"] = int(sum(results["sizes"].values()))
    joblib.dump({"cols": cols, "cat": cat, "h1": h1, "h2": h2, "h3": h3, "h4": h4, "h5": h5, "fp": fp, "m1": a.m1, "ordinal": a.ordinal, "fp_cols": FP_COLS},
                os.path.join(OUT, f"m2_models_{tag}.joblib"))
    results["sizes"]["serialized_mb"] = round(os.path.getsize(os.path.join(OUT, f"m2_models_{tag}.joblib")) / 1e6, 2)
    log(f"sizes: {results['sizes']}")


    if not a.no_ablation:
        abl = {}
        full = {"auroc_ho": results["req_soon"]["auroc_handover_events"], "next_acc": results["next_class"]["accuracy"]}
        for fam in list(FAMILIES) + ["event_type_only_baseline"]:
            cols_f = (list(ALWAYS) if fam == "event_type_only_baseline" else columns(drop=(fam,)))
            Xf, catf = design(df, cols_f, CATMODE)
            g1 = BinaryHead(catf).fit(Xf[in_Btr], d_tr.req_soon.to_numpy(), Xf[in_Bcal], d_cal.req_soon.to_numpy())
            pa = g1.predict_proba(Xf[in_C])
            g2 = MultiHead(catf).fit(Xf[in_Btr][pos(d_tr)], d_tr.next_cls.to_numpy()[pos(d_tr)], Xf[in_Bcal][pos(d_cal)], d_cal.next_cls.to_numpy()[pos(d_cal)])
            pb2 = g2.predict_proba(Xf[in_C][Pte]).argmax(1)
            abl[fam] = {"auroc_ho": float(roc_auc_score(y1[ho], pa[ho])), "next_acc": float((pb2 == y2).mean())}
            abl[fam]["delta_auroc_ho"] = abl[fam]["auroc_ho"] - full["auroc_ho"]
            abl[fam]["delta_next_acc"] = abl[fam]["next_acc"] - full["next_acc"]
            log(f"ablation (drop {fam}): {abl[fam]}")
        results["ablation_drop_one_family"] = {"full": full, **abl}

    json.dump(results, open(os.path.join(OUT, f"m2_results_{tag}.json"), "w"), indent=2, sort_keys=True)
    log("done")


if __name__ == "__main__":
    main()

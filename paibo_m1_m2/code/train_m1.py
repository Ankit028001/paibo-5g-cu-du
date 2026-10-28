"""M1: per-UE traffic forecasting. Chronos-Bolt-Small fine-tuned on the world-v2 traffic windows, and a 14.5 M-parameter
student DISTILLED from it (custom smaller Chronos-Bolt architecture, trained from random init on the teacher's outputs
plus the data).

Task: from the last 60 s of a UE's per-second throughput (kbit/s) forecast the next 30 s (9 quantiles).
Applicability: Chronos normalises by the context's scale, so an all-zero (idle) context is degenerate; M1 is trained on and
applied to contexts with activity only. For idle contexts the forecast is zero and `m1_applicable = 0` (the start of a new
flow from idle is not predictable from traffic history; that is M2's job).

User split (by user, fixed seed): A (50 %) trains M1 (85 % train / 15 % val), B (25 %) is reserved for M2, C (25 %) is the test set.
Run: python -m paibo_bip.m1.train_m1
"""
import copy
import json
import os
import time

import numpy as np
import torch
from chronos import ChronosBoltPipeline
from chronos.chronos_bolt import ChronosBoltModelForForecasting
from transformers import AutoConfig

from ..world2 import spec as S
from ..world2.generate import World2Config, generate_world
from ..world2.instants import FORECAST_H, UserIndex, build_dataset, dense_windows, future_throughput

OUT = os.environ.get("PAIBO_M1_DIR", os.path.expanduser("~/paibo_gpu_ai_experiment/m1_v1"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
QUANTILES = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
WORLD = World2Config(n_users=600, hours=48.0, seed=0, coupling=float(os.environ.get("PAIBO_COUPLING", "0")))
STUDENT_ARCH = dict(d_model=320, d_ff=1280, num_layers=5, num_heads=5, d_kv=64)
FT_STEPS, FT_LR, FT_BS = 2500, 2e-5, 128
DISTILL_STEPS, DISTILL_LR, DISTILL_BS, DISTILL_ALPHA = 3000, 6e-4, 512, 1.0
SEED = 0


def user_split(n):
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(n)
    a, b = perm[: n // 2], perm[n // 2: (3 * n) // 4]
    c = perm[(3 * n) // 4:]
    na = int(0.85 * len(a))
    return {"A_train": a[:na], "A_val": a[na:], "B": b, "C": c}


def active(ctx):
    return (ctx > 0).any(axis=1)



def load_chronos(name):
    return ChronosBoltPipeline.from_pretrained(f"amazon/chronos-bolt-{name}", device_map=DEVICE, dtype=torch.float32).model


def make_student():
    cfg = AutoConfig.from_pretrained("amazon/chronos-bolt-tiny")
    for k, v in STUDENT_ARCH.items():
        setattr(cfg, k, v)
    return ChronosBoltModelForForecasting(cfg).to(DEVICE)


def n_params(m):
    return int(sum(p.numel() for p in m.parameters()))


@torch.no_grad()
def forecast(model, ctx, bs=1024):
    """(N,60) -> (N,9,30) quantile forecasts; zeros for idle contexts."""
    model.eval()
    out = np.zeros((len(ctx), len(QUANTILES), FORECAST_H), np.float32)
    idx = np.where(active(ctx))[0]
    for i in range(0, len(idx), bs):
        j = idx[i:i + bs]
        q = model(context=torch.from_numpy(ctx[j]).to(DEVICE)).quantile_preds[:, :, :FORECAST_H]
        out[j] = q.float().cpu().numpy()
    return np.clip(out, 0.0, None)


def tgt64(t):
    x = torch.full((len(t), 64), float("nan"), device=DEVICE)
    x[:, :FORECAST_H] = torch.from_numpy(t).to(DEVICE)
    return x


def run_finetune(model, ctx, tgt, vctx, vtgt, steps, lr, bs, log):
    rng = np.random.default_rng(SEED)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    best, best_state = 1e18, None
    for step in range(1, steps + 1):
        model.train()
        i = rng.integers(0, len(ctx), bs)
        out = model(context=torch.from_numpy(ctx[i]).to(DEVICE), target=tgt64(tgt[i]))
        opt.zero_grad(); out.loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 250 == 0 or step == steps:
            v = val_loss(model, vctx, vtgt)
            log(f"  step {step:5d} train_loss {out.loss.item():.4f} val_loss {v:.4f}")
            if v < best:
                best, best_state = v, copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    return best


@torch.no_grad()
def val_loss(model, ctx, tgt, bs=1024):
    model.eval()
    tot, n = 0.0, 0
    for i in range(0, len(ctx), bs):
        c, t = ctx[i:i + bs], tgt[i:i + bs]
        out = model(context=torch.from_numpy(c).to(DEVICE), target=tgt64(t))
        tot += out.loss.item() * len(c); n += len(c)
    return tot / n


def run_distill(student, teacher, ctx, tgt, vctx, vtgt, steps, lr, bs, alpha, log):
    rng = np.random.default_rng(SEED + 1)
    teacher.eval()
    opt = torch.optim.AdamW(student.parameters(), lr=lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.05)
    best, best_state = 1e18, None
    for step in range(1, steps + 1):
        student.train()
        i = rng.integers(0, len(ctx), bs)
        c = torch.from_numpy(ctx[i]).to(DEVICE)
        with torch.no_grad():
            qt = teacher(context=c).quantile_preds[:, :, :FORECAST_H]
        out = student(context=c, target=tgt64(tgt[i]))
        scale = c.abs().mean(dim=1).clamp_min(1.0)[:, None, None]
        d = ((out.quantile_preds[:, :, :FORECAST_H] - qt).abs() / scale).mean()
        loss = out.loss + alpha * d
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        opt.step(); sched.step()
        if step % 250 == 0 or step == steps:
            v = val_loss(student, vctx, vtgt)
            log(f"  step {step:5d} loss {loss.item():.4f} (task {out.loss.item():.4f} distill {d.item():.4f}) val_loss {v:.4f}")
            if v < best:
                best, best_state = v, copy.deepcopy(student.state_dict())
    student.load_state_dict(best_state)
    return best



def metrics(q, y, ctx):
    """q (N,9,H) quantile forecasts, y (N,H) truth."""
    med = q[:, 4, :]
    mae = np.abs(med - y).mean()
    pin = 0.0
    for k, tau in enumerate(QUANTILES):
        e = y - q[:, k, :]
        pin += np.maximum(tau * e, (tau - 1) * e).mean()
    pin /= len(QUANTILES)
    cover = ((y >= q[:, 0, :]) & (y <= q[:, 8, :])).mean()
    return {"mae_kbps": float(mae), "mean_pinball_kbps": float(pin), "p10_p90_coverage": float(cover)}


def baseline_mae(ctx, y):
    last = ctx[:, -1:]
    mean10 = ctx[:, -10:].mean(axis=1, keepdims=True)
    return {"naive_last_mae_kbps": float(np.abs(last - y).mean()), "mean_last10_mae_kbps": float(np.abs(mean10 - y).mean()),
            "zero_mae_kbps": float(np.abs(y).mean())}


def m1_features(q, ctx):
    """Summary of a forecast for M2 (all zeros + applicable=0 for idle contexts)."""
    n = len(ctx)
    ap = active(ctx).astype(np.float32)
    med, lo, hi = q[:, 4, :], q[:, 0, :], q[:, 8, :]
    last10 = ctx[:, -10:].mean(axis=1)
    f = np.zeros((n, 9), np.float32)
    f[:, 0] = ap
    f[:, 1] = med.mean(1); f[:, 2] = med.max(1); f[:, 3] = hi.mean(1); f[:, 4] = lo.mean(1)
    f[:, 5] = med[:, :5].mean(1); f[:, 6] = med[:, -5:].mean(1)
    f[:, 7] = f[:, 1] / (last10 + 1.0)
    f[:, 8] = (hi - lo).mean(1) / (f[:, 1] + 1.0)
    return f


M1_FEATURE_NAMES = ["m1_applicable", "m1_mean_med", "m1_max_med", "m1_p90_mean", "m1_p10_mean", "m1_first5_med",
                    "m1_last5_med", "m1_ratio_last10", "m1_spread"]


def _setup(log):
    users = generate_world(WORLD)
    split = user_split(len(users))
    log(f"world: {len(users)} users x {WORLD.hours} h; split A_train {len(split['A_train'])} A_val {len(split['A_val'])} "
        f"B {len(split['B'])} C {len(split['C'])}")

    def windows(ids, per_user, seed):
        return dense_windows([users[i] for i in ids], WORLD.hours, per_user, seed)

    d = {}
    d["ctx_tr"], d["y_tr"], _ = windows(split["A_train"], 500, 1)
    d["ctx_va"], d["y_va"], _ = windows(split["A_val"], 300, 2)
    d["ctx_te"], d["y_te"], _ = windows(split["C"], 300, 3)
    for k in ("tr", "va", "te"):
        d["m" + k] = active(d["ctx_" + k])
    log(f"dense windows: train {len(d['ctx_tr'])} ({d['mtr'].mean():.2f} active), val {len(d['ctx_va'])}, "
        f"test {len(d['ctx_te'])} ({d['mte'].mean():.2f} active)")
    return users, split, d


def _event_data(users, log):
    """RRC-event instants of all users, their 60 s contexts and the true next 30 s (cached on disk)."""
    p = os.path.join(OUT, "instants.pkl")
    if os.path.exists(p) and os.path.exists(os.path.join(OUT, "future30.npy")):
        import pandas as pd
        return pd.read_pickle(p), np.load(os.path.join(OUT, "series.npy")), np.load(os.path.join(OUT, "future30.npy"))
    df, series = build_dataset(users, WORLD)
    fut = np.zeros((len(df), FORECAST_H), np.float32)
    uix = {u.uid: UserIndex(u) for u in users}
    for r, (uid, t) in enumerate(zip(df["uid"].to_numpy(), df["t"].to_numpy())):
        fut[r] = future_throughput(uix[int(uid)], float(t))
    df.to_pickle(p)
    np.save(os.path.join(OUT, "series.npy"), series)
    np.save(os.path.join(OUT, "future30.npy"), fut)
    log(f"event instants built: {len(df)}")
    return df, series, fut


def _load_results():
    p = os.path.join(OUT, "m1_results.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def _save_results(r):
    json.dump(r, open(os.path.join(OUT, "m1_results.json"), "w"), indent=2)


def _event_features(name, model, users, split, log, results):
    df, series, fut = _event_data(users, log)
    ctx_ev = series[:, :, 0].astype(np.float32)
    in_c = df["uid"].isin(split["C"]).to_numpy()
    ev_act = active(ctx_ev)
    sel = in_c & ev_act
    ev = results.setdefault("test_event_instants_active", {})
    ev["n"] = int(sel.sum())
    ev.update(baseline_mae(ctx_ev[sel], fut[sel]))
    qe = forecast(model, ctx_ev)
    np.save(os.path.join(OUT, f"m1_features_{name}.npy"), m1_features(qe, ctx_ev))
    ev[name] = metrics(qe[sel], fut[sel], ctx_ev[sel])
    json.dump({"names": M1_FEATURE_NAMES}, open(os.path.join(OUT, "m1_feature_names.json"), "w"))
    json.dump({k: v.tolist() for k, v in split.items()}, open(os.path.join(OUT, "split.json"), "w"))
    log(f"event-instant forecasts + M1 features saved for {name}: {ev[name]}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "small", "features_small", "student"])
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    logf = open(os.path.join(OUT, "train_log.txt"), "a")

    def log(s):
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    t0 = time.time()
    users, split, d = _setup(log)
    results = _load_results()
    results.update({"split_sizes": {k: int(len(v)) for k, v in split.items()}, "horizon_s": FORECAST_H, "context_s": S.WINDOW_S,
                    "applicability": "contexts with any activity; idle contexts get zero forecast (m1_applicable = 0)"})
    mtr, mva, mte = d["mtr"], d["mva"], d["mte"]
    ctx_tr, y_tr, ctx_va, y_va, ctx_te, y_te = (d[k] for k in ("ctx_tr", "y_tr", "ctx_va", "y_va", "ctx_te", "y_te"))
    results.setdefault("test_dense_active", {}).update({"n": int(mte.sum()), **baseline_mae(ctx_te[mte], y_te[mte])})
    small_path = os.path.join(OUT, "m1_small_finetuned.pt")

    if a.stage in ("all", "small"):
        small = load_chronos("small")
        results.setdefault("params", {})["small"] = n_params(small)
        q = forecast(small, ctx_te)
        results["test_dense_active"]["small_zero_shot"] = metrics(q[mte], y_te[mte], ctx_te[mte])
        log(f"Small zero-shot: {results['test_dense_active']['small_zero_shot']}")
        log("fine-tuning Chronos-Bolt-Small (full) ...")
        run_finetune(small, ctx_tr[mtr], y_tr[mtr], ctx_va[mva], y_va[mva], FT_STEPS, FT_LR, FT_BS, log)
        q = forecast(small, ctx_te)
        results["test_dense_active"]["small_finetuned"] = metrics(q[mte], y_te[mte], ctx_te[mte])
        log(f"Small fine-tuned: {results['test_dense_active']['small_finetuned']}  [{time.time()-t0:.0f}s]")
        torch.save(small.state_dict(), small_path)
        _save_results(results)

    if a.stage in ("all", "features_small"):
        small = load_chronos("small")
        small.load_state_dict(torch.load(small_path, map_location=DEVICE))
        results.setdefault("params", {})["small"] = n_params(small)
        q = forecast(small, ctx_te)
        results["test_dense_active"]["small_finetuned"] = metrics(q[mte], y_te[mte], ctx_te[mte])
        _event_features("small_ft", small, users, split, log, results)
        _save_results(results)

    if a.stage in ("all", "student"):
        teacher = load_chronos("small")
        teacher.load_state_dict(torch.load(small_path, map_location=DEVICE))
        student = make_student()
        results.setdefault("params", {})["student"] = n_params(student)
        log(f"student architecture {STUDENT_ARCH}: {results['params']['student']/1e6:.2f} M parameters; distilling "
            f"{DISTILL_STEPS} steps at batch {DISTILL_BS} ...")
        run_distill(student, teacher, ctx_tr[mtr], y_tr[mtr], ctx_va[mva], y_va[mva], DISTILL_STEPS, DISTILL_LR, DISTILL_BS,
                    DISTILL_ALPHA, log)
        q = forecast(student, ctx_te)
        results["test_dense_active"]["student_distilled"] = metrics(q[mte], y_te[mte], ctx_te[mte])
        log(f"Student distilled: {results['test_dense_active']['student_distilled']}  [{time.time()-t0:.0f}s]")
        torch.save(student.state_dict(), os.path.join(OUT, "m1_student_distilled.pt"))
        _event_features("student", student, users, split, log, results)
        _save_results(results)

    log(json.dumps(results, indent=2))
    log(f"stage {a.stage} done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

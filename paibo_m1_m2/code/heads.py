"""M2 heads: gradient-boosted trees (sklearn HistGradientBoosting) with a logistic / temperature calibration layer.

Feature families (the paper's (i)-(vi) plus radio, cell context and the M1 forecast):
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

K = 6
FAMILIES = {
    "traffic_history": ["thr_mean", "thr_max", "thr_std", "thr_last10", "thr_trend", "active_frac", "iat_mean", "pkt_mean",
                        "burst", "idle_s"],
    "app_fingerprint": [f"fp_p{c}" for c in range(K)] + ["fp_applicable"],
    "mobility": ["speed_now", "speed_mean60", "since_ho_s", "ho_last600", "dwell_s"],
    "time_of_day": ["hour_sin", "hour_cos", "hour", "dow", "weekend"],
    "slice_registration": ["sub_slice_1", "sub_slice_2", "sub_slice_3", "sla_max_gbr_kbps", "group_obs", "capability", "dnn",
                           "slice_util_1", "slice_util_2", "slice_util_3"],
    "bearer_history": ["n_past"] + [f"hist_logfreq_{c}" for c in range(K)] + ["last1_cls", "last2_cls", "last3_cls",
                       "last_gbr_kbps", "last_mbr_kbps", "since_last_req_s", "mean_dur_min"],
    "radio": ["rsrp", "sinr", "cqi", "bler", "achievable_kbps"],
    "cell_context": ["cell_load", "cu_headroom", "cell_flows"],
    "m1_forecast": ["m1_applicable", "m1_mean_med", "m1_max_med", "m1_p90_mean", "m1_p10_mean", "m1_first5_med",
                    "m1_last5_med", "m1_ratio_last10", "m1_spread"],
}
ALWAYS = ["ev_type"]
CATEGORICAL = ["group_obs", "capability", "dnn", "last1_cls", "last2_cls", "last3_cls", "ev_type"]





TESTBED_UNAVAILABLE = ["dwell_s", "rsrp", "sinr", "cqi", "bler", "achievable_kbps", "cell_load", "cu_headroom", "cell_flows",
                       "slice_util_1", "slice_util_2", "slice_util_3", "mean_dur_min"]
MASKABLE_FAMILIES = ["mobility", "radio", "cell_context", "traffic_history", "app_fingerprint", "m1_forecast"]


def testbed_profile(df):
    out = df.copy()
    out[[c for c in TESTBED_UNAVAILABLE if c in out.columns]] = np.nan
    return out


def mask_training_rows(df, seed, p_profile=0.4, p_family=0.15):
    """Deployment-robust training: 40 % of rows get the testbed availability profile, and each maskable family is
    independently dropped from 15 % of the rows, so the trees learn sensible behaviour when inputs are missing."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    prof = rng.random(len(df)) < p_profile
    cols = [c for c in TESTBED_UNAVAILABLE if c in out.columns]
    out.loc[prof, cols] = np.nan
    for fam in MASKABLE_FAMILIES:
        fcols = [c for c in FAMILIES[fam] if c in out.columns]
        m = rng.random(len(df)) < p_family
        out.loc[m, fcols] = np.nan
    return out


def columns(drop=(), only=None):
    fams = [f for f in FAMILIES if (only is None or f in only) and f not in drop]
    cols = list(ALWAYS)
    for f in fams:
        cols += FAMILIES[f]
    return cols


def design(df, cols, categorical=True):
    """DataFrame -> float matrix and categorical mask. categorical=False ("ordinal" mode) keeps every column numeric with no
    categorical splits: required by the C export (no bitset splits) and what the embedded model uses."""
    X = df[cols].to_numpy(dtype=np.float64).copy()
    cat = np.zeros(len(cols), bool)
    if categorical:
        for i, c in enumerate(cols):
            if c in CATEGORICAL:
                cat[i] = True
                if c.startswith("last"):
                    X[:, i] += 1.0
    return X, cat


GB = dict(max_iter=150, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
          early_stopping=False, random_state=0)


def n_nodes(model):
    return int(sum(len(p.nodes) for stage in model._predictors for p in stage))


class BinaryHead:
    """GBT classifier + logistic (Platt) calibration on its raw score, fitted on held-out users."""

    def __init__(self, cat):
        self.gb = HistGradientBoostingClassifier(categorical_features=cat if cat.any() else None, **GB)
        self.platt = None

    def fit(self, X, y, Xv, yv):
        self.gb.fit(X, y)
        s = self.gb.decision_function(Xv).reshape(-1, 1)
        self.platt = LogisticRegression(C=1e6, max_iter=1000).fit(s, yv)
        return self

    def predict_proba(self, X):
        return self.platt.predict_proba(self.gb.decision_function(X).reshape(-1, 1))[:, 1]

    def raw_proba(self, X):
        return self.gb.predict_proba(X)[:, 1]

    def nodes(self):
        return n_nodes(self.gb)


class MultiHead:
    """GBT multi-class + temperature calibration (a one-parameter logistic/softmax calibrator)."""

    def __init__(self, cat, k=K):
        self.gb = HistGradientBoostingClassifier(categorical_features=cat if cat.any() else None, **GB)
        self.k, self.T = k, 1.0

    def fit(self, X, y, Xv, yv):
        self.gb.fit(X, y)
        p = self._raw(Xv)
        grid = np.linspace(0.4, 3.0, 53)
        nll = []
        for T in grid:
            z = np.log(np.clip(p, 1e-6, 1)) / T
            z -= z.max(1, keepdims=True)
            q = np.exp(z); q /= q.sum(1, keepdims=True)
            nll.append(-np.log(np.clip(q[np.arange(len(yv)), yv], 1e-9, 1)).mean())
        self.T = float(grid[int(np.argmin(nll))])
        return self

    def _raw(self, X):
        p = np.full((len(X), self.k), 1e-6)
        pr = self.gb.predict_proba(X)
        for j, c in enumerate(self.gb.classes_):
            p[:, int(c)] = pr[:, j]
        return p / p.sum(1, keepdims=True)

    def predict_proba(self, X):
        z = np.log(np.clip(self._raw(X), 1e-6, 1)) / self.T
        z -= z.max(1, keepdims=True)
        q = np.exp(z)
        return q / q.sum(1, keepdims=True)

    def nodes(self):
        return n_nodes(self.gb)


class QuantileHead:
    """Log-space quantile regressors (e.g. time to first request, p10 / p50 / p90)."""

    def __init__(self, cat, quantiles=(0.1, 0.5, 0.9)):
        self.q = quantiles
        self.models = [HistGradientBoostingRegressor(loss="quantile", quantile=q, categorical_features=cat if cat.any() else None,
                                                     **GB) for q in quantiles]

    def fit(self, X, y):
        ly = np.log1p(y)
        for m in self.models:
            m.fit(X, ly)
        return self

    def predict(self, X):
        out = np.stack([np.expm1(m.predict(X)) for m in self.models], axis=1)
        return np.sort(np.clip(out, 0.0, None), axis=1)

    def nodes(self):
        return sum(n_nodes(m) for m in self.models)


class ValueHead:
    def __init__(self, cat):
        self.m = HistGradientBoostingRegressor(categorical_features=cat if cat.any() else None, **GB)

    def fit(self, X, y):
        self.m.fit(X, np.log1p(y))
        return self

    def predict(self, X):
        return np.clip(np.expm1(self.m.predict(X)), 0.0, None)

    def nodes(self):
        return n_nodes(self.m)

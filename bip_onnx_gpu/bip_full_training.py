"""
Full BIP training pipeline on paibo_bip_dataset_no_leakage.csv
13 features -> onset_time_ms (per-UE target, constant across its 30s sequence)

STEP  1: Environment check
STEP  2: Load data
STEP  3: Build per-UE sequences (group by rnti, sorted by sec)
STEP  4: Train/test split (by UE, 80/20)
STEP  5: Scale (fit on train only)
STEP  6: Build LSTM model
STEP  7: Train on GPU
STEP  8: Evaluate (5% tolerance accuracy formula)
STEP  9: Export to ONNX
STEP 10: ONNX GPU inference benchmark
STEP 11: Save results + summary

Run inside WSL with the onnxrt-gpu-venv activated:
    source ~/onnxrt-gpu-venv/bin/activate
    python bip_full_training.py
"""
import json
import os
import time

import numpy as np
import onnx
import onnxruntime as ort
import pandas as pd
import psutil
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

# ---------------------------------------------------------------------------
# STEP 1 - Environment check
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 1 - ENVIRONMENT CHECK")
print("=" * 70)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"torch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"Device selected: {DEVICE}")

# ---------------------------------------------------------------------------
# STEP 2 - Load data
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 2 - LOAD DATA")
print("=" * 70)
DATA_PATH = "/mnt/c/Users/user/Downloads/Samsung/paibo_bip_dataset_no_leakage.csv"
df = pd.read_csv(DATA_PATH)
print(f"Loaded: {DATA_PATH}  shape={df.shape}")

FEATURES = [
    "throughput_mbps", "class_encoded", "avgSinrDb", "avgMcs", "pdcpMeanDelayS",
    "jitter_ms", "meanDelayMs", "prb_utilization_pct", "packetSizeBytes",
    "perUeCapBps", "cell_throughput_mbps", "tb_count", "bearer_setup_latency_ms",
]
TARGET = "onset_time_ms"
print(f"Features ({len(FEATURES)}): {FEATURES}")
print(f"Target: {TARGET}")
assert df[FEATURES + [TARGET]].isna().sum().sum() == 0, "nulls present in selected columns"

# ---------------------------------------------------------------------------
# STEP 3 - Build per-UE sequences (group by rnti, sorted by sec)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 3 - BUILD PER-UE SEQUENCES")
print("=" * 70)
rntis = sorted(df["rnti"].unique())
SEQ_LEN = df.groupby("rnti").size().min()  # 30 (seconds) per UE
print(f"Number of UEs (sequences): {len(rntis)}, sequence length: {SEQ_LEN}")

X_list, y_list = [], []
for r in rntis:
    sub = df[df["rnti"] == r].sort_values("sec")
    assert len(sub) == SEQ_LEN, f"UE {r} has {len(sub)} rows, expected {SEQ_LEN}"
    X_list.append(sub[FEATURES].values.astype(np.float32))
    target_vals = sub[TARGET].values
    assert np.allclose(target_vals, target_vals[0]), f"UE {r} onset_time_ms not constant across its sequence"
    y_list.append(target_vals[0])

X_all = np.stack(X_list)          # (n_ue, seq_len, n_features)
y_all = np.array(y_list, dtype=np.float32)  # (n_ue,)
print(f"X_all shape: {X_all.shape}, y_all shape: {y_all.shape}")

# ---------------------------------------------------------------------------
# STEP 4 - Train/test split (by UE, 80/20)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 4 - TRAIN/TEST SPLIT (80/20 BY UE)")
print("=" * 70)
rng = np.random.default_rng(20260901)
n = len(rntis)
perm = rng.permutation(n)
split = int(n * 0.8)
train_idx, test_idx = perm[:split], perm[split:]
X_train_raw, y_train_raw = X_all[train_idx], y_all[train_idx]
X_test_raw, y_test_raw = X_all[test_idx], y_all[test_idx]
print(f"Train UEs: {len(train_idx)}, Test UEs: {len(test_idx)}")

# ---------------------------------------------------------------------------
# STEP 5 - Scale (fit on train only, to avoid test leakage)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 5 - SCALE (MinMaxScaler, fit on TRAIN only)")
print("=" * 70)
n_feat = len(FEATURES)
scaler_X = MinMaxScaler()
scaler_X.fit(X_train_raw.reshape(-1, n_feat))

def scale_X(arr):
    shp = arr.shape
    return scaler_X.transform(arr.reshape(-1, n_feat)).reshape(shp).astype(np.float32)

X_train = scale_X(X_train_raw)
X_test = scale_X(X_test_raw)

scaler_y = MinMaxScaler()
y_train = scaler_y.fit_transform(y_train_raw.reshape(-1, 1)).flatten().astype(np.float32)
y_test = scaler_y.transform(y_test_raw.reshape(-1, 1)).flatten().astype(np.float32)
print("Scaling complete. X_train:", X_train.shape, "X_test:", X_test.shape)

# ---------------------------------------------------------------------------
# STEP 6 - Build LSTM model
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 6 - BUILD LSTM MODEL")
print("=" * 70)

class BIPProxyLSTM(nn.Module):
    def __init__(self, input_size=13, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

model = BIPProxyLSTM(input_size=n_feat).to(DEVICE)
print(model)
print(f"Model parameters: {sum(p.numel() for p in model.parameters())}")

# ---------------------------------------------------------------------------
# STEP 7 - Train on GPU
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 7 - TRAIN ON GPU")
print("=" * 70)
EPOCHS = 130
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=15, factor=0.5, min_lr=1e-6)
criterion = nn.MSELoss()

X_train_t = torch.tensor(X_train).to(DEVICE)
y_train_t = torch.tensor(y_train).unsqueeze(1).to(DEVICE)

process = psutil.Process()
mem_before = process.memory_info().rss / (1024 * 1024)
wall_start, cpu_start = time.time(), time.process_time()

import datetime

train_losses = []
model.train()
for epoch in range(1, EPOCHS + 1):
    epoch_t0 = time.perf_counter()
    optimizer.zero_grad()
    output = model(X_train_t)
    loss = criterion(output, y_train_t)
    loss.backward()
    optimizer.step()
    scheduler.step(loss)
    train_losses.append(loss.item())
    epoch_ms = (time.perf_counter() - epoch_t0) * 1000
    now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"  [{now}] Epoch {epoch:3d}/{EPOCHS} | Loss: {loss.item():.6f} | "
          f"LR: {optimizer.param_groups[0]['lr']:.6f} | step_time: {epoch_ms:.3f}ms")

cpu_time = time.process_time() - cpu_start
wall_time = time.time() - wall_start
memory_used = process.memory_info().rss / (1024 * 1024) - mem_before
print(f"\nTraining complete: CPU={cpu_time:.2f}s Wall={wall_time:.2f}s Mem={memory_used:.2f}MB BestLoss={min(train_losses):.6f}")

# ---------------------------------------------------------------------------
# STEP 8 - Evaluate (5% tolerance accuracy formula)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 8 - EVALUATE (5% TOLERANCE ACCURACY)")
print("=" * 70)

def calculate_accuracy(model, X, y_true_scaled, scaler_y, device, label):
    model.eval()
    with torch.no_grad():
        y_pred_scaled = model(torch.tensor(X).to(device)).cpu().numpy()
    y_pred = scaler_y.inverse_transform(y_pred_scaled)
    y_actual = scaler_y.inverse_transform(y_true_scaled.reshape(-1, 1))
    within_tol = np.abs(y_pred - y_actual) <= (0.05 * y_actual)
    acc = np.mean(within_tol) * 100
    mae = np.mean(np.abs(y_pred - y_actual))
    rmse = np.sqrt(np.mean((y_pred - y_actual) ** 2))
    print(f"  [{label}] n={len(y_actual)} accuracy(5% tol)={acc:.2f}%  MAE={mae:.4f}ms  RMSE={rmse:.4f}ms")
    return acc, mae, rmse

acc_train, mae_train, rmse_train = calculate_accuracy(model, X_train, y_train, scaler_y, DEVICE, "TRAIN")
acc_test, mae_test, rmse_test = calculate_accuracy(model, X_test, y_test, scaler_y, DEVICE, "TEST")

# ---------------------------------------------------------------------------
# STEP 9 - Export to ONNX
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 9 - EXPORT TO ONNX")
print("=" * 70)
model.eval()
dummy_input = torch.randn(1, SEQ_LEN, n_feat).to(DEVICE)
onnx_path = os.path.expanduser("~/bip_full_model.onnx")
torch.onnx.export(model, dummy_input, onnx_path,
                   input_names=["ue_telemetry"], output_names=["onset_time_pred"],
                   dynamic_axes={"ue_telemetry": {0: "batch_size"}, "onset_time_pred": {0: "batch_size"}},
                   opset_version=17)
onnx.checker.check_model(onnx_path)
print(f"ONNX model saved and validated: {onnx_path}")

# ---------------------------------------------------------------------------
# STEP 10 - ONNX GPU inference benchmark
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 10 - ONNX GPU INFERENCE BENCHMARK")
print("=" * 70)
sess = ort.InferenceSession(onnx_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
print(f"ONNX providers: {sess.get_providers()}")
for _ in range(10):
    sess.run(None, {"ue_telemetry": X_test})
latencies = []
for _ in range(100):
    t0 = time.perf_counter()
    sess.run(None, {"ue_telemetry": X_test})
    latencies.append((time.perf_counter() - t0) * 1000)
mean_latency, p95_latency = np.mean(latencies), np.percentile(latencies, 95)
throughput = 1000.0 / mean_latency
print(f"Mean latency: {mean_latency:.3f}ms  P95: {p95_latency:.3f}ms  Throughput: {throughput:.1f} inf/sec")

# ---------------------------------------------------------------------------
# STEP 11 - Save results + summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 11 - SAVE RESULTS + FINAL SUMMARY")
print("=" * 70)
results = {
    "BIP_full_LSTM_13feat": {
        "dataset": DATA_PATH, "n_ue_total": int(n), "n_train": int(len(train_idx)), "n_test": int(len(test_idx)),
        "seq_len": int(SEQ_LEN), "n_features": int(n_feat), "features": FEATURES, "target": TARGET,
        "epochs": int(EPOCHS), "best_loss": float(min(train_losses)),
        "cpu_time_s": float(cpu_time), "wall_time_s": float(wall_time), "memory_mb": float(memory_used),
        "train_accuracy_5pct": float(acc_train), "test_accuracy_5pct": float(acc_test),
        "train_mae_ms": float(mae_train), "test_mae_ms": float(mae_test),
        "train_rmse_ms": float(rmse_train), "test_rmse_ms": float(rmse_test),
        "onnx_mean_latency_ms": float(mean_latency), "onnx_p95_latency_ms": float(p95_latency),
        "throughput_inf_per_sec": float(throughput), "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }
}
json_path = os.path.expanduser("~/bip_full_training_results.json")
with open(json_path, "w") as f:
    json.dump(results, f, indent=2)
csv_path = os.path.expanduser("~/bip_full_training_results.csv")
pd.DataFrame([results["BIP_full_LSTM_13feat"]]).to_csv(csv_path, index=False)

print(f"Saved: {json_path}")
print(f"Saved: {csv_path}")

print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)
print(f"{'Metric':<32}{'Value':<20}")
print("-" * 70)
print(f"{'UEs (train/test)':<32}{f'{len(train_idx)}/{len(test_idx)}':<20}")
print(f"{'Sequence length':<32}{SEQ_LEN:<20}")
print(f"{'Best Train Loss':<32}{min(train_losses):<20.6f}")
print(f"{'Train Accuracy (5% tol)':<32}{acc_train:<20.2f}")
print(f"{'Test Accuracy (5% tol)':<32}{acc_test:<20.2f}")
print(f"{'Train MAE (ms)':<32}{mae_train:<20.4f}")
print(f"{'Test MAE (ms)':<32}{mae_test:<20.4f}")
print(f"{'Test RMSE (ms)':<32}{rmse_test:<20.4f}")
print(f"{'ONNX Mean Latency (ms)':<32}{mean_latency:<20.3f}")
print(f"{'ONNX P95 Latency (ms)':<32}{p95_latency:<20.3f}")
print(f"{'Throughput (inf/sec)':<32}{throughput:<20.1f}")
print("=" * 70)

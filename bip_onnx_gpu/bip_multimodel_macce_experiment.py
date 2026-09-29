import json
import os
import time

import numpy as np
import onnx
import onnxruntime as ort
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler


OUTPUT_DIR = os.path.expanduser("~/paibo_gpu_ai_experiment")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

DATA_PATH = "/mnt/c/Users/user/Downloads/Samsung/paibo_bip_dataset_no_leakage.csv"

FEATURE_COLUMNS = [
    "throughput_mbps", "class_encoded", "avgSinrDb", "avgMcs", "pdcpMeanDelayS",
    "jitter_ms", "meanDelayMs", "prb_utilization_pct", "packetSizeBytes",
    "perUeCapBps", "cell_throughput_mbps", "tb_count",
]
TARGET_COLUMN = "bearer_setup_latency_ms"
NUM_FEATURES = len(FEATURE_COLUMNS)
EPOCHS = 130
ACCURACY_TOLERANCE = 0.05  # a prediction counts as "correct" if it's within 5% of the true value

df = pd.read_csv(DATA_PATH)
ue_ids = sorted(df["rnti"].unique())

sequences = []
targets = []
for ue_id in ue_ids:
    ue_rows = df[df["rnti"] == ue_id].sort_values("sec")
    sequences.append(ue_rows[FEATURE_COLUMNS].values.astype(np.float32))
    targets.append(ue_rows[TARGET_COLUMN].values[0])

X = np.stack(sequences)              # shape: (num_ues, timesteps_per_ue, num_features)
y = np.array(targets, dtype=np.float32)
SEQ_LEN = X.shape[1]


all_indices = np.arange(len(ue_ids))
train_indices, test_indices = train_test_split(all_indices, test_size=0.30, random_state=42)

X_train_raw, y_train_raw = X[train_indices], y[train_indices]
X_test_raw, y_test_raw = X[test_indices], y[test_indices]

feature_scaler = MinMaxScaler()
feature_scaler.fit(X_train_raw.reshape(-1, NUM_FEATURES))

def scale_features(sequences_array):
    flat = sequences_array.reshape(-1, NUM_FEATURES)
    scaled_flat = feature_scaler.transform(flat)
    return scaled_flat.reshape(sequences_array.shape).astype(np.float32)

X_train = scale_features(X_train_raw)
X_test = scale_features(X_test_raw)

target_scaler = MinMaxScaler()
y_train = target_scaler.fit_transform(y_train_raw.reshape(-1, 1)).flatten().astype(np.float32)
y_test = target_scaler.transform(y_test_raw.reshape(-1, 1)).flatten().astype(np.float32)

X_train_gpu = torch.tensor(X_train).to(DEVICE)
X_test_gpu = torch.tensor(X_test).to(DEVICE)
y_train_gpu = torch.tensor(y_train).unsqueeze(1).to(DEVICE)


class LightLSTM(nn.Module):
    def __init__(self, num_features, hidden_size=32):
        super().__init__()
        self.lstm = nn.LSTM(num_features, hidden_size, batch_first=True)
        self.output_layer = nn.Linear(hidden_size, 1)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        last_timestep = lstm_out[:, -1, :]
        return self.output_layer(last_timestep)


def train(model, X_train_in, y_train_in):
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=15, factor=0.5, min_lr=1e-6)
    loss_fn = nn.MSELoss()

    model.train()
    start_time = time.time()
    losses = []
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        predictions = model(X_train_in)
        loss = loss_fn(predictions, y_train_in)
        loss.backward()
        optimizer.step()
        scheduler.step(loss)
        losses.append(loss.item())
    train_time_seconds = time.time() - start_time

    return losses, train_time_seconds


def evaluate(model, X_in, y_true_scaled):
    model.eval()
    with torch.no_grad():
        y_pred_scaled = model(X_in).cpu().numpy()

    y_pred = target_scaler.inverse_transform(y_pred_scaled)
    y_true = target_scaler.inverse_transform(y_true_scaled.reshape(-1, 1))

    error = np.abs(y_pred - y_true)
    accuracy_pct = np.mean(error <= ACCURACY_TOLERANCE * y_true) * 100
    mae = np.mean(error)
    rmse = np.sqrt(np.mean(error ** 2))
    return accuracy_pct, mae, rmse

model = LightLSTM(NUM_FEATURES).to(DEVICE)
losses, train_time_seconds = train(model, X_train_gpu, y_train_gpu)

train_accuracy, train_mae, train_rmse = evaluate(model, X_train_gpu, y_train)
test_accuracy, test_mae, test_rmse = evaluate(model, X_test_gpu, y_test)

print(f"Test Accuracy: {test_accuracy:.2f}%")
print(f"Test MAE: {test_mae:.4f} ms")
print(f"Test RMSE: {test_rmse:.4f} ms")


model.eval()
onnx_path = f"{OUTPUT_DIR}/LightLSTM_bearer_setup.onnx"
example_input = torch.randn(1, SEQ_LEN, NUM_FEATURES).to(DEVICE)
torch.onnx.export(
    model, example_input, onnx_path,
    input_names=["input"], output_names=["macce_pred"],
    dynamic_axes={"input": {0: "batch"}, "macce_pred": {0: "batch"}},
    opset_version=17,
)
onnx.checker.check_model(onnx_path)

session = ort.InferenceSession(onnx_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
X_test_numpy = X_test_gpu.cpu().numpy()

# A few warm-up runs before timing, so the GPU is "warmed up".
for _ in range(10):
    session.run(None, {"input": X_test_numpy})

inference_times_ms = []
for _ in range(100):
    start = time.perf_counter()
    session.run(None, {"input": X_test_numpy})
    inference_times_ms.append((time.perf_counter() - start) * 1000)

mean_latency_ms = float(np.mean(inference_times_ms))
p95_latency_ms = float(np.percentile(inference_times_ms, 95))



results = {
    "params": sum(p.numel() for p in model.parameters()),
    "best_loss": float(min(losses)),
    "train_wall_s": float(train_time_seconds),
    "train_accuracy_5pct": float(train_accuracy),
    "test_accuracy_5pct": float(test_accuracy),
    "train_mae_ms": float(train_mae),
    "test_mae_ms": float(test_mae),
    "train_rmse_ms": float(train_rmse),
    "test_rmse_ms": float(test_rmse),
    "onnx_mean_latency_ms": mean_latency_ms,
    "onnx_p95_latency_ms": p95_latency_ms,
    "onnx_path": onnx_path,
}


with open(f"{OUTPUT_DIR}/bearer_setup_experiment_results.json", "w") as f:
    json.dump(results, f, indent=2)

pd.DataFrame({"LightLSTM": results}).T.to_csv(f"{OUTPUT_DIR}/bearer_setup_experiment_results.csv")

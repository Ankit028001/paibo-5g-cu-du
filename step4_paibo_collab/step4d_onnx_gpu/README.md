> **Step 4d — ONNX on GPU, Lightweight Model Accuracy (Sep 2026)**

# Task 4d — ONNX on GPU, Lightweight Model Accuracy

**Requested (Sukhdeep Singh email, "Step 3: PAIBO Collab Project",
2026-09-09):** "On the GPU try to run ONNX and also try to run
lightweight models and check the accuracy of the models."

**What was done:**
- Trained a lightweight PyTorch model (LightLSTM) on the KPI dataset,
  exported it to ONNX (`torch.onnx.export`), validated the export with
  `onnx.checker.check_model`, and ran GPU inference via
  `onnxruntime.InferenceSession` with `CUDAExecutionProvider` (CPU
  fallback available).
- Benchmarked GPU inference latency (warmup + 100-run timing, mean/p95 ms).
- Measured model accuracy via a 5%-tolerance metric
  (`test_accuracy_5pct`) plus MAE/RMSE, on both train and test splits.
- Fixed a bug where the results-dump step wrote an undefined `summary`
  variable instead of the computed `results` dict.

**Status:** Done

**Files in this folder:**
- `README.md` (this file)
- `bip_full_training.py`, `bip_multimodel_macce_experiment.py`,
  `check_gpu_windows.py`, `run.sh`

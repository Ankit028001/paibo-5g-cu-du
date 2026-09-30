#!/bin/bash
# Activates the GPU-enabled onnxruntime venv and runs the BIP MAC-CE ONNX experiment.
source ~/onnxrt-gpu-venv/bin/activate
cd "$(dirname "$0")"
python3 bip_multimodel_macce_experiment.py

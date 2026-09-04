# PAIBO Validation Plan — Result Types 1-4

THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION STUDY. None of the four
PAIBO result types below can be produced from ns-3 or from the existing
OAI captures, because the feature they describe (Bearer Intent Predictor,
shadow bearers, the Bearer Hint RRC message, MAC-CE micro-reconfiguration,
RL-based SDAP consolidation) is not implemented in either. All four require
a separate Python-side simulation/model pipeline, not this validation
script, which is read-only against existing RAN-simulator output.

## Result Type 1 — Bearer Setup Latency (target: 8-12ms PAIBO vs 100-200ms 3GPP)
- Data needed: per-bearer-event timestamps for NGAP arrival, RRC processing
  start/end, RRCReconfiguration sent, UE apply, RRCReconfigurationComplete,
  bearer-active, for both a PAIBO-enabled path and a 3GPP-baseline path.
- Producing script (not yet written/run): a dedicated Python simulation of
  the PAIBO shadow-bearer/Bearer-Hint flow (referred to in the task as
  `1_generate_traffic.py` / `compare_baseline.py`-style scripts); ns-3 and
  OAI as currently configured do not implement this flow at all.
- Expected output format: one row per simulated bearer-setup event, columns
  matching `bearer_setup_latency_ms` (per UE) and
  `cell_mean_bearer_latency_ms` / `cell_pct_ues_lt_12ms_latency` (per cell).
- Per-UE calculation: bearer_setup_latency_ms = bearer_active_timestamp -
  attach_start_timestamp, per simulated bearer event.
- Per-cell calculation: mean/p50/p90/p99 of the per-UE latency across all
  UEs at that scaling level; % of UEs under 12ms and under 50ms thresholds.
- Baseline for comparison: the same event sequence run through a
  3GPP-reactive model (full RRCReconfiguration round trip, no
  pre-configuration) instead of the PAIBO shadow-bearer path.

## Result Type 2 — DRB Count Reduction (RL-SDAP consolidation)
- Data needed: per-UE count of active DRBs, with and without RL-based QoS
  flow-to-DRB consolidation.
- Producing script (not yet written/run): a Python RL training/eval script
  for the SDAP consolidation policy (referred to in the task as
  `3_train_rl_sdap.py`); no such policy exists in this study.
- Expected output format: one row per UE per scaling level with
  `active_drb_count` (post-consolidation) and a baseline column
  (pre-consolidation, one DRB per QoS flow).
- Per-UE calculation: active_drb_count = number of distinct DRBs the RL
  policy assigns to that UE's QoS flows.
- Per-cell calculation: cell_total_drb_count = sum over UEs;
  cell_mean_drb_per_ue = mean over UEs; reduction % = 1 - (RL total / baseline total).
- Baseline for comparison: static 1-DRB-per-QoS-flow mapping (no consolidation).

## Result Type 3 — MAC-CE Adaptation Latency (target: <1ms)
- Data needed: timestamp of an adaptation trigger (e.g. RLC mode-switch
  decision) and timestamp of the corresponding RLC/PDCP parameter update
  taking effect.
- Producing script (not yet written/run): a real-time trace capture from
  an OAI stack with a MAC-CE micro-reconfiguration channel implemented, or
  a dedicated discrete-event simulation of that channel; not present in
  either the ns-3 or OAI setups used in this study.
- Expected output format: one row per adaptation event with
  `macce_adaptation_latency_ms` (per UE, per event).
- Per-UE calculation: macce_adaptation_latency_ms = parameter_update_timestamp
  - adaptation_trigger_timestamp, per event, then averaged per UE.
- Per-cell calculation: cell_mean_macce_latency_ms = mean across all UEs and
  events; % of adaptations completing under 1ms.
- Baseline for comparison: full RRCReconfiguration latency for the same
  parameter change (the ~100ms figure quoted in the patent deck).

## Result Type 4 — BIP ML Model Accuracy (target: confidence > 0.80)
- Data needed: a trained Bearer Intent Predictor (or equivalent) model,
  a labeled test set of actual bearer demand events, and the model's
  predictions against that test set.
- Producing script (not yet written/run): a model training/evaluation
  script (referred to in the task as `2_train_bip.py`); no BIP-equivalent
  model has been trained in this study. The per-UE/per-cell KPI CSVs this
  validation script produces are a plausible *input* (feature/label source)
  to such training, not a source of model-accuracy numbers themselves.
- Expected output format: standard classification evaluation output
  (accuracy, confusion matrix, false-positive rate, missed-prediction rate)
  against a held-out test set, reported per UE (that UE's own prediction
  history) and aggregated per cell.
- Per-UE calculation: bip_accuracy = correct predictions / total predictions
  for that UE's bearer-demand events; bip_false_positive_rate = predicted
  bearer-needed but not needed / total predictions; bip_missed_prediction_rate
  = bearer needed but not predicted / total actual bearer-demand events.
- Per-cell calculation: cell_bip_accuracy = mean/aggregate across all UEs;
  cell_activation_success_rate = successful shadow-bearer activations /
  total activation attempts.
- Baseline for comparison: a trivial/random or rule-based bearer-demand
  predictor, to show the trained BIP model's uplift.

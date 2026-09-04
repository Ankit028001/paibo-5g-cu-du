#!/usr/bin/env python3
"""
validate_paibo_kpis.py

READ-ONLY KPI validation/cross-check script for the ns-3 / 5G-LENA
UE-scaling study (ue-scaling-study.cc ladder, levels 1/10/25/50/100/150),
against the KPIs required by the PAIBO patent deck
(PAIBO_Patent_Vartika.pptx).

THIS SCRIPT DOES NOT RUN ANY SIMULATION, DOES NOT MODIFY ANY OAI FILE,
AND DOES NOT PUSH ANYTHING TO GITHUB. It only reads existing result files
under ns3_phase01/ue_<N>/ and writes four output files into ns3_phase01/.

THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION DATASET.
IT IS NOT REAL OAI CU-DU EXECUTION. Every row written by this script
carries data_source="ns3_5glena_simulation" and
simulation_label="NOT real OAI CU-DU F1 measurements" for this reason.

Hard rule enforced throughout: PAIBO Result Types 1-4 (bearer setup
latency, DRB count reduction, MAC-CE adaptation latency, BIP ML accuracy)
are NEVER fabricated or inferred from proxy metrics. None of the four are
implemented in this ns-3 scenario or in stock OAI; every field for them is
written as NA with an explicit reason, per instruction.

Outputs (written into the same directory as this script):
  per_ue_kpis_validated.csv
  per_cell_kpis_validated.csv
  KPI_AVAILABILITY_MATRIX.md
  PAIBO_VALIDATION_PLAN.md
"""

import os
import xml.etree.ElementTree as ET

import pandas as pd

LEVELS = [1, 10, 25, 50, 100, 150]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PORT = 20000
SIM_TAG_FMT = "ue{n}"

NA = "NA"

# Byte-volume traffic targets from the original instructions email
# (normalised to 100%; these are volume-of-bytes targets, not UE-count
# shares -- UE-count shares are 40/15/15/12/13/5, a different axis).
TARGET_BYTE_PCT = {
    "mMTC": 1.0,   # "<1%"; using 1.0 as the documented upper bound
    "Web": 8.0,
    "Mobile": 10.0,
    "VoD": 35.0,
    "Live": 25.0,
    "V2X": 2.0,
}

NA_REASONS = {
    "bearer_setup_latency_ms": "NOT MEASURED — PAIBO Bearer Hint/shadow-bearer signaling not implemented in ns-3 simulation",
    "active_drb_count": "NOT MEASURED — DRB count not exposed in 5G-LENA FlowMonitor",
    "macce_adaptation_latency_ms": "NOT MEASURED — MAC-CE adaptation requires OAI real stack",
    "bip_accuracy": "NOT MEASURED — PAIBO BIP not implemented in ns-3 simulation",
    "bip_false_positive_rate": "NOT MEASURED — PAIBO BIP not implemented in ns-3 simulation",
    "bip_missed_prediction_rate": "NOT MEASURED — PAIBO BIP not implemented in ns-3 simulation",
    "attach_time_s": "NOT MEASURED — ue-scaling-study.cc only writes an aggregate rrcConnectedCount, not a per-UE attach timestamp",
    "pdu_session_established": "NOT MEASURED — 5G-LENA's NrPointToPointEpcHelper is an LTE-EPC-style core with no NAS/PDU-session concept, unlike real 5GC",
    "mean_ul_sinr_db": "NOT MEASURED — uplink data PHY SINR trace was not enabled in this scenario",
    "mean_rsrp_dbm": "NOT MEASURED — RSRP is not a native 5G-LENA trace field in this build",
    "mean_cqi": "NOT MEASURED — not exposed as a validated per-UE field in this validation pass",
    "prb_utilization_pct": "NOT MEASURED — per-UE PRB count is not a direct native trace field (see KPI_AVAILABILITY_NOTE.md)",
    "mean_ul_mcs": "NOT MEASURED — NrUlMacStats.txt rows in this scenario are minimal/control-only grants (fixed tbSize, mcs=0), not representative UL data MCS since no UL application traffic was configured",
}
CELL_NA_REASONS = {
    "cell_mean_bearer_latency_ms": NA_REASONS["bearer_setup_latency_ms"],
    "cell_pct_ues_lt_12ms_latency": NA_REASONS["bearer_setup_latency_ms"],
    "cell_total_drb_count": NA_REASONS["active_drb_count"],
    "cell_mean_drb_per_ue": NA_REASONS["active_drb_count"],
    "cell_mean_macce_latency_ms": NA_REASONS["macce_adaptation_latency_ms"],
    "cell_bip_accuracy": NA_REASONS["bip_accuracy"],
    "cell_activation_success_rate": NA_REASONS["bip_accuracy"],
    "prb_utilization_pct": NA_REASONS["prb_utilization_pct"],
}


def read_tsv(path):
    # index_col=False: several nr-module trace files have one more data
    # column than header column (a trailing empty field on every row),
    # which makes pandas silently treat the true first column as a row
    # index and shift every other column left by one unless disabled here.
    return pd.read_csv(path, sep="\t", index_col=False)


def strip_cols(df):
    df.columns = [c.strip().lstrip("%").strip() for c in df.columns]
    return df


def read_traffic_config(path):
    df = strip_cols(read_tsv(path))
    rows = []
    ue_index = 0
    for _, r in df.iterrows():
        for _ in range(int(r["ueCount"])):
            rows.append({
                "ue_id": ue_index,
                "imsi": ue_index + 1,
                "traffic_class": r["class"],
                "target_dl_rate_mbps": float(r["perUeCapBps"]) / 1e6,
            })
            ue_index += 1
    return pd.DataFrame(rows)


def read_flowmonitor(path):
    tree = ET.parse(path)
    root = tree.getroot()
    flow_stats = {}
    for flow in root.find("FlowStats").findall("Flow"):
        rx_packets = int(flow.get("rxPackets"))
        flow_stats[int(flow.get("flowId"))] = {
            "txBytes": int(flow.get("txBytes")),
            "rxBytes": int(flow.get("rxBytes")),
            "txPackets": int(flow.get("txPackets")),
            "rxPackets": rx_packets,
            "lostPackets": int(flow.get("lostPackets")),
            "delaySumNs": float(flow.get("delaySum").strip("+ns")),
            "jitterSumNs": float(flow.get("jitterSum").strip("+ns")),
        }
    rows = []
    classifier = root.find("Ipv4FlowClassifier")
    for flow in classifier.findall("Flow"):
        flow_id = int(flow.get("flowId"))
        dest_port = int(flow.get("destinationPort"))
        ue_index = dest_port - BASE_PORT
        if flow_id not in flow_stats or ue_index < 0:
            continue
        s = flow_stats[flow_id]
        rx = s["rxPackets"]
        tx = s["txPackets"]
        rows.append({
            "ue_id": ue_index,
            "imsi": ue_index + 1,
            "dl_bytes": s["rxBytes"],
            "dl_tput_mbps": (s["rxBytes"] * 8 / 1e6) / 30.0,  # 30s sim time
            "packet_loss_pct": (s["lostPackets"] / tx * 100.0) if tx else float("nan"),
            "mean_e2e_delay_ms": (s["delaySumNs"] / rx / 1e6) if rx else float("nan"),
            "mean_jitter_ms": (s["jitterSumNs"] / rx / 1e6) if rx else float("nan"),
        })
    return pd.DataFrame(rows)


def read_rxpackettrace_by_rnti(path):
    df = strip_cols(read_tsv(path))
    agg = df.groupby("rnti").agg(
        mean_dl_sinr_db=("SINR(dB)", "mean"),
        mean_dl_mcs=("mcs", "mean"),
        mean_dl_bler_pct=("corrupt", lambda s: s.mean() * 100.0),
        harq_retx_count=("rv", lambda s: int((s != 0).sum())),
    ).reset_index()
    return agg


def read_rnti_imsi_map(rlc_e2e_path):
    df = strip_cols(read_tsv(rlc_e2e_path))
    return df[["RNTI", "IMSI"]].drop_duplicates().rename(
        columns={"RNTI": "rnti", "IMSI": "imsi"})


def process_level(n, missing_log):
    level_dir = os.path.join(BASE_DIR, f"ue_{n}")
    tag = SIM_TAG_FMT.format(n=n)
    found = {}
    data = {}

    def try_read(name, fn, *args):
        path_desc = args[0] if args else name
        try:
            data[name] = fn(*args)
            found[name] = True
        except Exception as e:
            found[name] = False
            missing_log.append(f"Level {n}: could not read {path_desc} ({e})")

    try_read("run_summary", lambda p: read_tsv(p).set_index("metric")["value"],
              f"{level_dir}/{tag}_run_summary.tsv")
    try_read("traffic_cfg", read_traffic_config, f"{level_dir}/{tag}_traffic_config.tsv")
    try_read("flows", read_flowmonitor, f"{level_dir}/{tag}_flowmonitor.xml")
    try_read("rxpkt", read_rxpackettrace_by_rnti, f"{level_dir}/RxPacketTrace.txt")
    try_read("rnti_imsi", read_rnti_imsi_map, f"{level_dir}/NrDlRlcStatsE2E.txt")
    try_read("summary_md_exists", lambda p: os.path.exists(p) and open(p, encoding="utf-8", errors="replace").read(),
              f"{level_dir}/SUMMARY.md")

    if not found.get("run_summary") or not found.get("traffic_cfg") or not found.get("flows"):
        missing_log.append(f"Level {n}: SKIPPED (missing core files: run_summary/traffic_cfg/flowmonitor)")
        return None, None

    run_summary = data["run_summary"]
    per_ue = data["traffic_cfg"]
    per_ue = per_ue.merge(data["flows"].drop(columns=["imsi"]), on="ue_id", how="left")

    if found.get("rnti_imsi"):
        per_ue = per_ue.merge(data["rnti_imsi"], on="imsi", how="left")
    else:
        per_ue["rnti"] = float("nan")
        missing_log.append(f"Level {n}: RNTI<->IMSI map unavailable, SINR/MCS/BLER/HARQ columns will be NA")

    if found.get("rxpkt") and found.get("rnti_imsi"):
        per_ue = per_ue.merge(data["rxpkt"], on="rnti", how="left")
    else:
        for c in ["mean_dl_sinr_db", "mean_dl_mcs", "mean_dl_bler_pct", "harq_retx_count"]:
            per_ue[c] = float("nan")

    per_ue["attach_success"] = per_ue["rnti"].notna() if "rnti" in per_ue else False
    per_ue["pdu_session_established"] = NA
    per_ue["attach_time_s"] = NA
    per_ue["bearer_setup_latency_ms"] = NA
    per_ue["active_drb_count"] = NA
    per_ue["mean_ul_sinr_db"] = NA
    per_ue["mean_rsrp_dbm"] = NA
    per_ue["mean_ul_mcs"] = NA
    per_ue["mean_cqi"] = NA
    per_ue["ul_tput_mbps"] = 0.0  # measured: DL-only traffic model, genuinely zero UL app traffic
    per_ue["ul_bytes"] = 0
    per_ue["target_ul_rate_mbps"] = 0.0
    per_ue["bip_accuracy"] = NA
    per_ue["bip_false_positive_rate"] = NA
    per_ue["bip_missed_prediction_rate"] = NA
    per_ue["macce_adaptation_latency_ms"] = NA
    per_ue["scenario"] = "A"  # only IDEAL-channel data exists; no scenario B run
    per_ue["num_ues"] = n
    per_ue["data_source"] = "ns3_5glena_simulation"
    per_ue["simulation_label"] = "NOT real OAI CU-DU F1 measurements"

    col_order = [
        "ue_id", "traffic_class", "scenario", "num_ues",
        "attach_success", "attach_time_s", "pdu_session_established",
        "bearer_setup_latency_ms", "active_drb_count",
        "mean_dl_sinr_db", "mean_ul_sinr_db", "mean_rsrp_dbm",
        "mean_dl_bler_pct", "mean_dl_mcs", "mean_ul_mcs",
        "harq_retx_count", "mean_cqi",
        "dl_tput_mbps", "ul_tput_mbps", "dl_bytes", "ul_bytes",
        "packet_loss_pct", "mean_jitter_ms", "mean_e2e_delay_ms",
        "target_dl_rate_mbps", "target_ul_rate_mbps",
        "bip_accuracy", "bip_false_positive_rate", "bip_missed_prediction_rate",
        "macce_adaptation_latency_ms",
        "data_source", "simulation_label",
    ]
    per_ue = per_ue.reindex(columns=col_order)

    configured = int(run_summary["configuredUeCount"])
    connected = int(run_summary["rrcConnectedCount"])
    total_dl_bytes = per_ue["dl_bytes"].sum()
    total_bytes_by_class = per_ue.groupby("traffic_class")["dl_bytes"].sum()
    bytes_pct = (total_bytes_by_class / total_dl_bytes * 100.0) if total_dl_bytes else total_bytes_by_class * 0

    sinr_valid = per_ue["mean_dl_sinr_db"].dropna()
    per_cell = {
        "num_ues_configured": configured,
        "num_ues_registered": connected,
        "registration_success_pct": (connected / configured * 100.0) if configured else float("nan"),
        "scenario": "A",
        "mean_cell_sinr_db": sinr_valid.mean() if len(sinr_valid) else float("nan"),
        "sinr_distribution_p10_db": sinr_valid.quantile(0.10) if len(sinr_valid) else float("nan"),
        "sinr_distribution_p50_db": sinr_valid.quantile(0.50) if len(sinr_valid) else float("nan"),
        "sinr_distribution_p90_db": sinr_valid.quantile(0.90) if len(sinr_valid) else float("nan"),
        "mean_cell_bler_pct": per_ue["mean_dl_bler_pct"].mean(),
        "mean_cell_mcs": per_ue["mean_dl_mcs"].mean(),
        "prb_utilization_pct": NA,
        "agg_dl_tput_mbps": per_ue["dl_tput_mbps"].sum(),
        "agg_ul_tput_mbps": 0.0,
        "agg_dl_bytes": total_dl_bytes,
        "agg_ul_bytes": 0,
        "offered_dl_load_mbps": per_ue["target_dl_rate_mbps"].sum(),
        "offered_ul_load_mbps": 0.0,
        "cell_mean_bearer_latency_ms": NA,
        "cell_pct_ues_lt_12ms_latency": NA,
        "cell_total_drb_count": NA,
        "cell_mean_drb_per_ue": NA,
        "cell_mean_macce_latency_ms": NA,
        "cell_bip_accuracy": NA,
        "cell_activation_success_rate": NA,
        "simulation_wall_s": float(run_summary["wallClockSeconds"]),
        "data_source": "ns3_5glena_simulation",
    }
    for cls, target in TARGET_BYTE_PCT.items():
        per_cell[f"bytes_pct_{cls.lower()}"] = bytes_pct.get(cls, 0.0)
        per_cell[f"target_pct_{cls.lower()}"] = target

    return per_ue, pd.DataFrame([per_cell])


def write_availability_matrix(path, per_ue_all, per_cell_all):
    n150 = per_cell_all[per_cell_all["num_ues_configured"] == 150]
    n150_row = n150.iloc[0] if len(n150) else None

    def v150(col):
        if n150_row is None or col not in n150_row or pd.isna(n150_row[col]) or n150_row[col] == NA:
            return NA
        return round(n150_row[col], 3) if isinstance(n150_row[col], float) else n150_row[col]

    rows = [
        ("dl_tput_mbps", "YES", "FlowMonitor XML", v150("agg_dl_tput_mbps"), "aggregate cell value shown"),
        ("ul_tput_mbps", "YES (=0)", "FlowMonitor XML", 0.0, "DL-only traffic model, no UL app traffic generated"),
        ("packet_loss_pct", "YES", "FlowMonitor XML", NA, "per-UE column; see per_ue_kpis_validated.csv"),
        ("mean_jitter_ms", "YES", "FlowMonitor XML", NA, "per-UE column"),
        ("mean_e2e_delay_ms", "YES", "FlowMonitor XML", NA, "per-UE column"),
        ("mean_dl_sinr_db", "YES", "RxPacketTrace.txt", v150("mean_cell_sinr_db"), "requires RNTI<->IMSI map from NrDlRlcStatsE2E.txt"),
        ("mean_dl_bler_pct", "YES", "RxPacketTrace.txt (corrupt flag)", v150("mean_cell_bler_pct"), None),
        ("mean_dl_mcs", "YES", "RxPacketTrace.txt", v150("mean_cell_mcs"), None),
        ("harq_retx_count", "YES", "RxPacketTrace.txt (rv != 0)", NA, "per-UE column"),
        ("traffic_class", "YES", "simulation config (traffic_config.tsv)", NA, "ground-truth label, not an inferred feature"),
        ("target_dl_rate_mbps", "YES", "simulation config", NA, "MODEL value, not measured"),
        ("num_ues_configured", "YES", "run_summary.tsv", 150, None),
        ("attach_time_s", "NO", NA, NA, NA_REASONS["attach_time_s"]),
        ("pdu_session_established", "NO", NA, NA, NA_REASONS["pdu_session_established"]),
        ("bearer_setup_latency_ms", "NO", NA, NA, NA_REASONS["bearer_setup_latency_ms"]),
        ("active_drb_count", "NO", NA, NA, NA_REASONS["active_drb_count"]),
        ("macce_adaptation_latency_ms", "NO", NA, NA, NA_REASONS["macce_adaptation_latency_ms"]),
        ("bip_accuracy", "NO", NA, NA, NA_REASONS["bip_accuracy"]),
        ("bip_false_positive_rate", "NO", NA, NA, NA_REASONS["bip_false_positive_rate"]),
        ("bip_missed_prediction_rate", "NO", NA, NA, NA_REASONS["bip_missed_prediction_rate"]),
        ("mean_ul_sinr_db", "NO", NA, NA, NA_REASONS["mean_ul_sinr_db"]),
        ("mean_ul_mcs", "NO", NA, NA, NA_REASONS["mean_ul_mcs"]),
        ("mean_rsrp_dbm", "NO", NA, NA, NA_REASONS["mean_rsrp_dbm"]),
        ("mean_cqi", "NO", NA, NA, NA_REASONS["mean_cqi"]),
        ("prb_utilization_pct", "NO", NA, NA, NA_REASONS["prb_utilization_pct"]),
    ]

    lines = ["# KPI Availability Matrix\n",
             "THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION DATASET. "
             "IT IS NOT REAL OAI CU-DU EXECUTION.\n",
             "| KPI | Available? | Source | Value at N=150 | Notes |",
             "|---|---|---|---|---|"]
    for kpi, avail, source, val, note in rows:
        lines.append(f"| {kpi} | {avail} | {source} | {val} | {note or ''} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_validation_plan(path):
    content = """# PAIBO Validation Plan — Result Types 1-4

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
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    missing_log = []
    per_ue_frames = []
    per_cell_frames = []
    levels_ok = []

    for n in LEVELS:
        per_ue, per_cell = process_level(n, missing_log)
        if per_ue is not None:
            per_ue_frames.append(per_ue)
            per_cell_frames.append(per_cell)
            levels_ok.append(n)

    per_ue_all = pd.concat(per_ue_frames, ignore_index=True) if per_ue_frames else pd.DataFrame()
    per_cell_all = pd.concat(per_cell_frames, ignore_index=True) if per_cell_frames else pd.DataFrame()

    per_ue_out = os.path.join(BASE_DIR, "per_ue_kpis_validated.csv")
    per_cell_out = os.path.join(BASE_DIR, "per_cell_kpis_validated.csv")
    matrix_out = os.path.join(BASE_DIR, "KPI_AVAILABILITY_MATRIX.md")
    plan_out = os.path.join(BASE_DIR, "PAIBO_VALIDATION_PLAN.md")

    per_ue_all.to_csv(per_ue_out, index=False)
    per_cell_all.to_csv(per_cell_out, index=False)
    write_availability_matrix(matrix_out, per_ue_all, per_cell_all)
    write_validation_plan(plan_out)

    print("=== PAIBO KPI VALIDATION SUMMARY ===")
    print(f"Levels processed: {', '.join(str(n) for n in levels_ok)}")
    print(f"Levels requested but skipped/missing: {sorted(set(LEVELS) - set(levels_ok))}")
    total_cols = len(per_ue_all.columns) if len(per_ue_all) else 0
    na_cols = sum(1 for c in per_ue_all.columns if len(per_ue_all) and (per_ue_all[c] == NA).all()) if len(per_ue_all) else 0
    print(f"Per-UE columns: {total_cols} total, {na_cols} entirely NA (PAIBO-specific / not-instrumented fields)")
    print("KPIs requiring PAIBO Python sim (never fabricated here): 4 (Result Types 1-4)")

    if len(per_cell_all):
        row150 = per_cell_all[per_cell_all["num_ues_configured"] == 150]
        if len(row150):
            r = row150.iloc[0]
            print("\nPer-cell results at N=150:")
            print(f"  Registration: {r['num_ues_registered']}/{r['num_ues_configured']}")
            print(f"  Agg DL throughput: {r['agg_dl_tput_mbps']:.3f} Mbps")
            print(f"  Mean SINR: {r['mean_cell_sinr_db']}")
            print(f"  Mean BLER: {r['mean_cell_bler_pct']}%")
            print("  Traffic class bytes vs targets:")
            for cls in TARGET_BYTE_PCT:
                key = cls.lower()
                print(f"    {cls}: measured={r.get(f'bytes_pct_{key}'):.3f}% target={r.get(f'target_pct_{key}')}%")

    print("\nPAIBO Result Types status:")
    print("  Type 1 (Bearer latency):    PENDING — needs Python sim")
    print("  Type 2 (DRB reduction):     PENDING — needs Python sim")
    print("  Type 3 (MAC-CE latency):    PENDING — needs Python sim")
    print("  Type 4 (BIP accuracy):      PENDING — needs Python sim")

    if missing_log:
        print("\nMissing/skipped file log:")
        for line in missing_log:
            print(f"  - {line}")

    print(f"\nOutput files:\n  {per_ue_out}\n  {per_cell_out}\n  {matrix_out}\n  {plan_out}")


if __name__ == "__main__":
    main()

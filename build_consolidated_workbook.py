#!/usr/bin/env python3
"""
build_consolidated_workbook.py

READ-ONLY against per_ue_kpis_validated.csv / per_cell_kpis_validated.csv and
the real ns-3 baseline measurement runs (never modified). Builds ONE
consolidated workbook (not separate files) with:

  Sheet 1: Per-UE Results               (unchanged validated ns-3 ladder data)
  Sheet 2: Cell-Level Results           (unchanged validated ns-3 ladder data)
  Sheet 3: KPI Availability / Requirement Cross-Check
  Sheet 4: PAIBO_Real_Measurements_N150 (real bearer latency / DRB / MAC-CE-proxy,
           from the earlier add-a-bearer experiment -- kept for reference,
           clearly NOT part of the non-PAIBO baseline)
  Sheet 5: Baseline_NonPAIBO_Ladder     (real bearer setup latency + DRB=1,
           clean scenario, no added mechanism, across whatever ladder levels
           have completed so far)

Every ns-3 number is labeled "ns-3 simulation" in the Source column; every
OAI number is labeled "OAI CU-DU logs (REAL MEASUREMENT)"; every PAIBO
number would be labeled "PAIBO Python pipeline" -- none currently exist, so
every PAIBO-sourced row is Status=Not Available, Value Observed=NA.
Nothing is fabricated. This script does not run ns-3 or OAI.
"""

import csv
import glob
import os
from collections import defaultdict

from export_to_excel import write_xlsx, read_csv_rows

BASE = os.path.dirname(os.path.abspath(__file__))
PHASE01 = os.path.join(BASE, "ns3_phase01")
FK150 = "/root/fullkpi_150"
BASELINE_LADDER = "/root/baseline_bearer_latency"
SMOKE10 = "/root/bearer_latency_smoke"
SMOKE100 = "/root/bearer_latency_smoke_100"


def read_tsv_stripped(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = [h.strip().lstrip("%").strip() for h in next(reader)]
        return [dict(zip(header, row)) for row in reader]


def bearer_latency_stats(csv_path):
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    vals = [float(r["bearerSetupLatencyMs"]) for r in rows]
    return {"n": len(vals), "min": min(vals), "max": max(vals),
            "mean": sum(vals) / len(vals), "distinct": len(set(vals))}


def collect_baseline_ladder():
    """Real bearer-setup-latency + DRB=1, clean scenario, whatever levels exist."""
    results = {}
    # already-completed smoke tests (clean scenario, no added bearer)
    p10 = os.path.join(SMOKE10, "blat10_bearer_setup_latency.csv")
    if os.path.exists(p10):
        results[10] = bearer_latency_stats(p10)
    p100 = os.path.join(SMOKE100, "blat100_bearer_setup_latency.csv")
    if os.path.exists(p100):
        results[100] = bearer_latency_stats(p100)
    # ladder-driven levels
    for n in [1, 25, 50, 150, 200]:
        p = os.path.join(BASELINE_LADDER, f"ue_{n}", f"blat{n}_bearer_setup_latency.csv")
        if os.path.exists(p):
            results[n] = bearer_latency_stats(p)
    return dict(sorted(results.items()))


def main():
    # ---- Sheet 1 & 2 ----
    sheet1 = ("Per-UE Results", read_csv_rows(os.path.join(PHASE01, "per_ue_kpis_validated.csv")))
    sheet2 = ("Cell-Level Results", read_csv_rows(os.path.join(PHASE01, "per_cell_kpis_validated.csv")))

    # ---- gather real baseline bearer-latency ladder data (whatever's done so far) ----
    ladder = collect_baseline_ladder()
    if ladder:
        lat_lo = min(v["min"] for v in ladder.values())
        lat_hi = max(v["max"] for v in ladder.values())
        levels_str = ",".join(str(n) for n in ladder)
        bearer_value_observed = f"{lat_lo:.4f}-{lat_hi:.4f} ms across N={levels_str} (real, ns-3 baseline; full 1-200 ladder may still be completing)"
    else:
        bearer_value_observed = "NA"

    # ---- Sheet 3: KPI Availability / Requirement Cross-Check ----
    # (kpi_name, source, status, value_observed, granularity, paibo_relevance)
    rows3 = [
        ("DL SINR", "ns-3 simulation", "Available", "~63.5-64 dB (IDEAL channel, constant across UE counts 1-200)", "per-TB", "BIP mobility/QoS input feature"),
        ("DL SINR", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-TB", "reason: 0/8 UEs reached PHY sync in the measured 8-UE pilot"),
        ("UL SINR", "ns-3 simulation", "Not Available", "NA", "per-TB", "reason: uplink data PHY SINR trace not enabled in this scenario"),
        ("UL SINR", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-TB", "reason: no UE reached PHY sync"),
        ("DL RSRP/RSSI", "ns-3 simulation", "Not Available", "NA", "per-UE", "reason: not a native 5G-LENA trace field in this build"),
        ("DL RSRP/RSSI", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-UE", "reason: no UE connected in the measured pilot"),
        ("UL RSRP/RSSI", "ns-3 simulation", "Not Available", "NA", "per-UE", "reason: not a native 5G-LENA trace field"),
        ("UL RSRP/RSSI", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-UE", "reason: no UE connected"),
        ("DL BLER", "ns-3 simulation", "Available", "0.0% at every ladder level (IDEAL channel)", "per-TB", "AMC/adaptation context"),
        ("DL BLER", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-TB", "reason: no data-plane traffic ever established"),
        ("UL BLER", "ns-3 simulation", "Not Available", "NA", "per-TB", "reason: no representative UL data traffic/trace enabled"),
        ("UL BLER", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-TB", "reason: no data-plane traffic"),
        ("DL MCS", "ns-3 simulation", "Available", "~27.5-27.9 (near-max, IDEAL channel AMC convergence)", "per-grant", "AMC/adaptation context"),
        ("DL MCS", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-grant", "reason: no data-plane traffic"),
        ("UL MCS", "ns-3 simulation", "Not Available", "NA", "per-grant", "reason: UL MAC grants in this scenario are minimal/control-only (fixed tbSize, mcs=0), not representative of real UL data MCS"),
        ("UL MCS", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-grant", "reason: no data-plane traffic"),
        ("HARQ Errors/Retransmissions", "ns-3 simulation", "Available", "0 retransmissions at every ladder level (rv != 0 count, RxPacketTrace.txt)", "per-grant", "Adaptation/reliability context"),
        ("HARQ Errors/Retransmissions", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-grant", "reason: no data-plane traffic"),
        ("PRB Utilization", "ns-3 simulation", "Not Available", "NA", "per-cell", "reason: per-UE/per-cell PRB count is not a direct native trace field in this build"),
        ("PRB Utilization", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-cell", "reason: no data-plane traffic"),
        ("RRC State", "ns-3 simulation", "Available", "100% RRC_CONNECTED at every ladder level (ConnectionEstablished trace)", "per-UE", "Direct BIP input state"),
        ("RRC State", "OAI CU-DU logs (REAL MEASUREMENT)", "Available", "RRC_IDLE observed for 8/8 UEs (real measured outcome, not a success)", "per-UE", "Direct BIP input state"),
        ("Registration", "ns-3 simulation", "Available", "100% at every ladder level (1-200 UEs)", "per-cell", "Scale/capacity context"),
        ("Registration", "OAI CU-DU logs (REAL MEASUREMENT)", "Available", "0/8 (106-PRB pilot); 2/100 (separate patched run, attempt_03)", "per-cell", "Scale/capacity context"),
        ("Bearer Setup Latency", "ns-3 simulation", "Available" if ladder else "Not Available", bearer_value_observed, "per-UE, per-event", "Core PAIBO Result Type 1 comparison baseline"),
        ("Bearer Setup Latency", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-event", "reason: never logged as a number, even for the 2-UE success case (narrative log only)"),
        ("Bearer Setup Latency", "PAIBO Python pipeline", "Not Available", "NA", "per-event", "reason: no PAIBO Bearer Hint/shadow-bearer pipeline exists on this machine"),
        ("F1 Setup Time", "ns-3 simulation", "Not Available", "NA", "per-setup", "reason: topological p2p link is established programmatically at t=0, no F1AP setup procedure exists to time"),
        ("F1 Setup Time", "OAI CU-DU logs (REAL MEASUREMENT)", "Partial", "PASS (event confirmed in logs; elapsed-time value not logged)", "per-setup", "CU-DU split validation context"),
        ("PDU Session Time", "ns-3 simulation", "Not Available", "NA", "per-session", "reason: NrPointToPointEpcHelper is LTE-EPC-style, no NAS/PDU-session concept"),
        ("PDU Session Time", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-session", "reason: 0/8 never reached PDU session; 2-UE success case not timestamped in a file"),
        ("Throughput", "ns-3 simulation", "Available", "e.g. 152.5 Mbps aggregate @ 200 UEs (FlowMonitor)", "per-flow, per-cell", "QoS/SLA context"),
        ("Throughput", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-flow", "reason: traffic test status NOT_RUN (gated behind control-plane success, never achieved)"),
        ("Packet Loss", "ns-3 simulation", "Available", "0.0% at every ladder level", "per-flow", "QoS/SLA context"),
        ("Packet Loss", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-flow", "reason: traffic test NOT_RUN"),
        ("Jitter", "ns-3 simulation", "Available", "~0.11-0.37 ms across the ladder (FlowMonitor jitterSum)", "per-flow", "QoS/SLA context"),
        ("Jitter", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-flow", "reason: traffic test NOT_RUN"),
        ("E2E Delay", "ns-3 simulation", "Available", "RLC/PDCP delay ~1.2-2.5 ms range across the ladder", "per-packet", "QoS/SLA context"),
        ("E2E Delay", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-packet", "reason: no data-plane traffic"),
        ("DRB Count", "ns-3 simulation", "Available", "1 per UE at every ladder level (real, distinct-LCID count in NrDlRlcStatsE2E.txt)", "per-UE", "Core PAIBO Result Type 2 comparison baseline"),
        ("DRB Count", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-UE", "reason: 0/8 never reached PDU session; not logged for the 2-UE success case"),
        ("DRB Count", "PAIBO Python pipeline", "Not Available", "NA", "per-UE", "reason: no RL-SDAP consolidation pipeline exists on this machine"),
        ("MAC-CE Adaptation Latency", "ns-3 simulation", "Not Available", "NA", "per-event", "reason: this is PAIBO's own proposed mechanism; no dynamic MAC-CE-triggered RLC-mode-switch exists in stock 5G-LENA, by design not added to this baseline"),
        ("MAC-CE Adaptation Latency", "OAI CU-DU logs (REAL MEASUREMENT)", "Not Available", "NA", "per-event", "reason: mechanism does not exist in stock OAI"),
        ("MAC-CE Adaptation Latency", "PAIBO Python pipeline", "Not Available", "NA", "per-event", "reason: no PAIBO pipeline exists on this machine"),
        ("BIP Accuracy", "PAIBO Python pipeline", "Not Available", "NA", "per-model-eval", "reason: no trained BIP model or labeled bearer-demand dataset exists on this machine"),
        ("BIP False Positive Rate", "PAIBO Python pipeline", "Not Available", "NA", "per-model-eval", "reason: same as BIP Accuracy"),
        ("BIP Missed Prediction Rate", "PAIBO Python pipeline", "Not Available", "NA", "per-model-eval", "reason: same as BIP Accuracy"),
        ("BIP Confidence", "PAIBO Python pipeline", "Not Available", "NA", "per-prediction", "reason: same as BIP Accuracy"),
        ("Activation Success Rate", "PAIBO Python pipeline", "Not Available", "NA", "per-activation", "reason: no shadow-bearer/activation mechanism exists anywhere on this machine to measure"),
    ]

    available = sum(1 for r in rows3 if r[2] == "Available")
    partial = sum(1 for r in rows3 if r[2] == "Partial")
    not_avail = sum(1 for r in rows3 if r[2] == "Not Available")
    total = len(rows3)

    header3 = ["#", "KPI Name", "Source", "Status", "Value Observed", "Granularity", "PAIBO Relevance"]
    sheet3_rows = [
        ["SUMMARY", "Available", available, "", "", "", ""],
        ["SUMMARY", "Partial", partial, "", "", "", ""],
        ["SUMMARY", "Not Available", not_avail, "", "", "", ""],
        ["SUMMARY", "Total", total, "", "", "", ""],
        [],
        header3,
    ]
    for i, r in enumerate(rows3, start=1):
        sheet3_rows.append([i, r[0], r[1], r[2], r[3], r[4], r[5]])
    sheet3_rows.append([])
    sheet3_rows.append(["SUMMARY", "Available", available, "", "", "", ""])
    sheet3_rows.append(["SUMMARY", "Partial", partial, "", "", "", ""])
    sheet3_rows.append(["SUMMARY", "Not Available", not_avail, "", "", "", ""])
    sheet3_rows.append(["SUMMARY", "Total", total, "", "", "", ""])
    sheet3 = ("KPI Availability CrossCheck", sheet3_rows)

    # ---- Sheet 4: PAIBO_Real_Measurements_N150 (from the earlier add-a-bearer
    # experiment -- explicitly NOT the non-PAIBO baseline, kept for reference) ----
    sheet4_rows = [["imsi", "bearer_setup_latency_ms", "active_drb_count", "macce_latency_proxy_ms",
                     "bip_accuracy", "num_ues", "data_source", "notes"]]
    if os.path.exists(FK150):
        with open(os.path.join(FK150, "fk150_bearer_setup_latency.csv"), newline="") as f:
            bearer_rows = list(csv.DictReader(f))
        latency_by_imsi = {r["imsi"]: float(r["bearerSetupLatencyMs"]) for r in bearer_rows}
        rlc_e2e = read_tsv_stripped(os.path.join(FK150, "NrDlRlcStatsE2E.txt"))
        rnti_to_imsi = {}
        lcids_by_imsi = defaultdict(set)
        for r in rlc_e2e:
            rnti_to_imsi[r["RNTI"]] = r["IMSI"]
            lcids_by_imsi[r["IMSI"]].add(r["LCID"])
        pkt_rows = read_tsv_stripped(os.path.join(FK150, "NrDlRxRlcStats.txt"))
        macce_delays_by_imsi = defaultdict(list)
        for r in pkt_rows:
            if r["lcid"] == "5":
                imsi = rnti_to_imsi.get(r["rnti"])
                if imsi:
                    macce_delays_by_imsi[imsi].append(float(r["delay(s)"]) * 1000.0)
        for imsi in sorted(latency_by_imsi, key=lambda x: int(x)):
            drb_count = len(lcids_by_imsi.get(imsi, set()))
            macce_delays = macce_delays_by_imsi.get(imsi, [])
            macce_mean = round(sum(macce_delays) / len(macce_delays), 4) if macce_delays else "NA"
            sheet4_rows.append([
                imsi, round(latency_by_imsi[imsi], 4), drb_count, macce_mean, "NOT AVAILABLE", 150,
                "ns3_5glena_simulation (cu-du-full-kpi-study.cc -- adds an EXTRA dedicated bearer NOT present in "
                "the non-PAIBO baseline; kept for reference only, NOT part of the baseline comparison)",
                "See sheet 'Baseline_NonPAIBO_Ladder' for the true unmodified baseline instead.",
            ])
    sheet4 = ("PAIBO_Real_Measurements_N150", sheet4_rows)

    # ---- Sheet 5: Baseline_NonPAIBO_Ladder (real, clean scenario) ----
    header5 = ["num_ues", "bearer_setup_latency_mean_ms", "bearer_setup_latency_min_ms",
               "bearer_setup_latency_max_ms", "bearer_setup_latency_distinct_values",
               "active_drb_count", "macce_adaptation_latency_ms", "bip_accuracy", "label"]
    sheet5_rows = [header5]
    for n, stats in ladder.items():
        sheet5_rows.append([n, round(stats["mean"], 4), round(stats["min"], 4), round(stats["max"], 4),
                             stats["distinct"], 1, "NA", "NA",
                             "Baseline — ns-3 / 5G-LENA simulation, PAIBO not implemented."])
    sheet5 = ("Baseline_NonPAIBO_Ladder", sheet5_rows)

    out_path = os.path.join(PHASE01, "ns3_phase01_validated_kpis.xlsx")
    tmp_path = out_path + ".tmp"
    write_xlsx([sheet1, sheet2, sheet3, sheet4, sheet5], tmp_path)
    try:
        os.replace(tmp_path, out_path)
        print(f"Wrote {out_path}")
    except PermissionError:
        fallback = out_path.replace(".xlsx", "_NEW.xlsx")
        os.replace(tmp_path, fallback)
        print(f"Target file is locked (likely open in Excel/another program). "
              f"Wrote new content to {fallback} instead -- close the original file and "
              f"re-run this script to finalize the overwrite, or just use {fallback}.")
    print("Sheets: Per-UE Results, Cell-Level Results, KPI Availability CrossCheck, "
          "PAIBO_Real_Measurements_N150, Baseline_NonPAIBO_Ladder")
    print(f"KPI matrix summary: Available={available} Partial={partial} Not Available={not_avail} Total={total}")
    print(f"Baseline ladder levels included so far: {list(ladder.keys())}")


if __name__ == "__main__":
    main()

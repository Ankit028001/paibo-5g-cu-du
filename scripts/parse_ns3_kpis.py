#!/usr/bin/env python3
"""
parse_ns3_kpis.py — ns-3 / 5G-LENA per-UE and per-cell KPI CSV + plot exporter.

THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION POST-PROCESSING SCRIPT.
IT DOES NOT MODIFY OR RE-INTERPRET ns-3'S RAW TRACE OUTPUT, ONLY JOINS/
AGGREGATES IT. All numbers here are traceable back to the raw .txt/.tsv/.xml
files listed in --traces-dir / --run-dir; nothing here is synthesized.

Reads, from a single simulation run's output:
  <run-dir>/<tag>_run_summary.tsv       (configured/RRC-connected UE count)
  <run-dir>/<tag>_traffic_config.tsv     (per-class UE counts, in creation order)
  <run-dir>/<tag>_flowmonitor.xml        (per-flow tx/rx bytes, delay, loss)
  <traces-dir>/NrDlMacStats.txt          (RNTI<->IMSI mapping, MCS)
  <traces-dir>/DlDataSinr.txt            (per-UE downlink data SINR time series)
  <traces-dir>/RxPacketTrace.txt         (per-TB MCS/CQI/corrupt flag)
  <traces-dir>/NrDlRlcStatsE2E.txt       (per-UE RLC delay/bytes, binned)
  <traces-dir>/NrDlPdcpStatsE2E.txt      (per-UE PDCP delay/bytes, binned)

Writes:
  <run-dir>/per_ue_kpis.csv
  <run-dir>/per_cell_kpis.csv
  <run-dir>/plot_per_ue_avg_sinr.png
  <run-dir>/plot_random_ue_sinr_timeseries.png
  <run-dir>/plot_per_ue_throughput.png

Traces (DlDataSinr.txt etc.) may be in a different directory than run-dir
because 5G-LENA's NrHelper::EnableTraces() writes them to the process's
current working directory, not to --outputDir.
"""

import argparse
import os
import random
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def read_tsv(path):
    # index_col=False is required: several nr-module trace files have a
    # trailing tab (extra empty field) on every data row, one more field
    # than the header row. Without this, pandas silently treats the true
    # first data column as a row index instead of a column, shifting every
    # other column's data left by one -- confirmed by inspecting raw bytes
    # of NrDlRlcStatsE2E.txt against its own header field count.
    return pd.read_csv(path, sep="\t", index_col=False)


def read_traffic_config(path):
    df = read_tsv(path)
    # Reconstruct per-UE class assignment: classes consume ueIndex 0..N-1 in
    # the same row order the scenario script wrote them (matches the C++
    # DistributeUesAcrossClasses loop order exactly).
    rows = []
    ue_index = 0
    for _, r in df.iterrows():
        for _ in range(int(r["ueCount"])):
            rows.append({"ueIndex": ue_index, "imsi": ue_index + 1, "class": r["class"],
                         "perUeCapBps": r["perUeCapBps"], "packetSizeBytes": r["packetSizeBytes"]})
            ue_index += 1
    return pd.DataFrame(rows)


def read_flowmonitor(path, base_port=20000):
    tree = ET.parse(path)
    root = tree.getroot()
    flow_stats = {}
    for flow in root.find("FlowStats").findall("Flow"):
        flow_stats[int(flow.get("flowId"))] = {
            "txBytes": int(flow.get("txBytes")),
            "rxBytes": int(flow.get("rxBytes")),
            "txPackets": int(flow.get("txPackets")),
            "rxPackets": int(flow.get("rxPackets")),
            "lostPackets": int(flow.get("lostPackets")),
            "delaySumNs": float(flow.get("delaySum").strip("+ns")),
        }
    rows = []
    classifier = root.find("Ipv4FlowClassifier")
    for flow in classifier.findall("Flow"):
        flow_id = int(flow.get("flowId"))
        dest_port = int(flow.get("destinationPort"))
        ue_index = dest_port - base_port
        if flow_id not in flow_stats or ue_index < 0:
            continue  # not a UE downlink bearer flow (e.g. the F1 heartbeat flow)
        stats = flow_stats[flow_id]
        rx_packets = stats["rxPackets"]
        rows.append({
            "ueIndex": ue_index,
            "imsi": ue_index + 1,
            "flowId": flow_id,
            "txBytes": stats["txBytes"],
            "rxBytes": stats["rxBytes"],
            "txPackets": stats["txPackets"],
            "rxPackets": stats["rxPackets"],
            "lostPackets": stats["lostPackets"],
            "meanDelayMs": (stats["delaySumNs"] / rx_packets / 1e6) if rx_packets else float("nan"),
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="dir with <tag>_run_summary.tsv etc.")
    ap.add_argument("--traces-dir", required=True, help="dir with DlDataSinr.txt etc.")
    ap.add_argument("--tag", required=True, help="simTag used for this run")
    args = ap.parse_args()

    run_dir = args.run_dir
    traces_dir = args.traces_dir
    tag = args.tag

    run_summary = read_tsv(f"{run_dir}/{tag}_run_summary.tsv").set_index("metric")["value"]
    traffic_cfg = read_traffic_config(f"{run_dir}/{tag}_traffic_config.tsv")
    flows = read_flowmonitor(f"{run_dir}/{tag}_flowmonitor.xml")

    # NOTE: NrDlMacStats.txt's own IMSI column is always 0 in this build (a
    # limitation of the module's MAC trace sink, not a bug in this script --
    # confirmed by inspecting raw output). The RNTI<->IMSI mapping is instead
    # built from NrDlRlcStatsE2E.txt / NrDlPdcpStatsE2E.txt, whose IMSI column
    # is populated correctly.
    # NrDlMacStats.txt only exists when --fullTraces=true (e.g. the 200-UE
    # level intentionally runs with --fullTraces=false to control I/O
    # volume). avgMcs is left NaN for such runs rather than failing outright.
    mac_path = f"{traces_dir}/NrDlMacStats.txt"
    if os.path.exists(mac_path):
        mac = read_tsv(mac_path)
        mac.columns = [c.strip().lstrip("%").strip() for c in mac.columns]
        mcs_by_rnti = mac.groupby("RNTI")["mcs"].mean().rename("avgMcs").reset_index().rename(
            columns={"RNTI": "rnti"})
    else:
        print(f"NOTE: {mac_path} not found (reduced trace set) -- avgMcs will be NaN")
        mcs_by_rnti = pd.DataFrame({"rnti": [], "avgMcs": []})

    sinr = read_tsv(f"{traces_dir}/DlDataSinr.txt")
    sinr.columns = [c.strip() for c in sinr.columns]
    sinr_by_rnti = sinr.groupby("RNTI")["SINR(dB)"].agg(["mean", "std", "count"]).rename(
        columns={"mean": "avgSinrDb", "std": "sinrStdDb", "count": "sinrSampleCount"}
    ).reset_index().rename(columns={"RNTI": "rnti"})

    rlc = read_tsv(f"{traces_dir}/NrDlRlcStatsE2E.txt")
    rlc.columns = [c.strip().lstrip("%").strip() for c in rlc.columns]
    rnti_to_imsi = rlc[["RNTI", "IMSI"]].drop_duplicates().rename(
        columns={"RNTI": "rnti", "IMSI": "imsi"})
    rlc_by_imsi = rlc.groupby("IMSI").agg(
        rlcRxBytes=("RxBytes", "sum"), rlcMeanDelayS=("delay(s)", "mean")
    ).reset_index().rename(columns={"IMSI": "imsi"})

    pdcp = read_tsv(f"{traces_dir}/NrDlPdcpStatsE2E.txt")
    pdcp.columns = [c.strip().lstrip("%").strip() for c in pdcp.columns]
    pdcp_by_imsi = pdcp.groupby("IMSI").agg(
        pdcpRxBytes=("RxBytes", "sum"), pdcpMeanDelayS=("delay(s)", "mean")
    ).reset_index().rename(columns={"IMSI": "imsi"})

    per_ue = traffic_cfg.merge(rnti_to_imsi, on="imsi", how="left")
    per_ue = per_ue.merge(sinr_by_rnti, on="rnti", how="left")
    per_ue = per_ue.merge(mcs_by_rnti, on="rnti", how="left")
    per_ue = per_ue.merge(rlc_by_imsi, on="imsi", how="left")
    per_ue = per_ue.merge(pdcp_by_imsi, on="imsi", how="left")
    per_ue = per_ue.merge(flows.drop(columns=["ueIndex"]), on="imsi", how="left")

    per_ue = per_ue.sort_values("imsi")
    per_ue.to_csv(f"{run_dir}/per_ue_kpis.csv", index=False)
    print(f"Wrote {run_dir}/per_ue_kpis.csv ({len(per_ue)} UEs)")

    per_cell = pd.DataFrame([{
        "configuredUeCount": int(run_summary["configuredUeCount"]),
        "rrcConnectedCount": int(run_summary["rrcConnectedCount"]),
        "actualRbCount": run_summary.get("actualRbCount"),
        "totalRxBytes": per_ue["rxBytes"].sum(),
        "totalTxBytes": per_ue["txBytes"].sum(),
        "totalLostPackets": per_ue["lostPackets"].sum(),
        "avgUeSinrDb": per_ue["avgSinrDb"].mean(),
        "avgUeMcs": per_ue["avgMcs"].mean(),
        "avgUeRlcDelayMs": per_ue["rlcMeanDelayS"].mean() * 1000,
        "avgUePdcpDelayMs": per_ue["pdcpMeanDelayS"].mean() * 1000,
    }])
    for cls, grp in per_ue.groupby("class"):
        per_cell[f"rxBytes_{cls}"] = grp["rxBytes"].sum()
    per_cell.to_csv(f"{run_dir}/per_cell_kpis.csv", index=False)
    print(f"Wrote {run_dir}/per_cell_kpis.csv")

    # ---- Plot 1: per-UE average SINR, colored by traffic class ----
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(per_ue["imsi"].astype(str), per_ue["avgSinrDb"])
    ax.set_xlabel("UE (IMSI)")
    ax.set_ylabel("Avg downlink data SINR (dB)")
    ax.set_title(f"Per-UE average SINR — {tag} ({len(per_ue)} UEs)")
    plt.xticks(rotation=90, fontsize=6)
    plt.tight_layout()
    fig.savefig(f"{run_dir}/plot_per_ue_avg_sinr.png", dpi=150)
    plt.close(fig)

    # ---- Plot 2: SINR time series for one randomly chosen UE ----
    random_rnti = random.choice(sinr["RNTI"].unique().tolist())
    ts = sinr[sinr["RNTI"] == random_rnti].sort_values("Time")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts["Time"], ts["SINR(dB)"], marker=".", linewidth=0.5, markersize=2)
    ax.set_xlabel("Simulated time (s)")
    ax.set_ylabel("SINR (dB)")
    ax.set_title(f"Downlink data SINR over time — randomly chosen UE (RNTI={random_rnti}) — {tag}")
    plt.tight_layout()
    fig.savefig(f"{run_dir}/plot_random_ue_sinr_timeseries.png", dpi=150)
    plt.close(fig)

    # ---- Plot 3: per-UE measured throughput (rxBytes over sim duration) ----
    sim_seconds = float(run_summary["simulatedSeconds"])
    fig, ax = plt.subplots(figsize=(10, 4))
    throughput_kbps = (per_ue["rxBytes"] * 8 / 1000) / sim_seconds
    bars = ax.bar(per_ue["imsi"].astype(str), throughput_kbps)
    ax.set_xlabel("UE (IMSI)")
    ax.set_ylabel("Measured DL throughput (kbps)")
    ax.set_title(f"Per-UE measured throughput — {tag} ({len(per_ue)} UEs)")
    plt.xticks(rotation=90, fontsize=6)
    plt.tight_layout()
    fig.savefig(f"{run_dir}/plot_per_ue_throughput.png", dpi=150)
    plt.close(fig)

    print(f"Wrote 3 plots to {run_dir}/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
add_paibo_real_measurements_sheet.py

READ-ONLY against per_ue_kpis_validated.csv / per_cell_kpis_validated.csv
(never modified). Adds a THIRD sheet, "PAIBO_Real_Measurements_N150", to
ns3_phase01_validated_kpis.xlsx containing real ns-3 measurements from the
cu-du-full-kpi-study run at N=150 UEs:

  - bearer_setup_latency_ms : REAL measured (RRC attach-start -> RRC
    Connected/DRB-configured, per UE) -- see cu-du-bearer-latency-study.cc
    / cu-du-full-kpi-study.cc header comments for the exact definition and
    its limitation (this is ns-3's own idealized RRC signaling time, not a
    real 3GPP/OAI measurement and not PAIBO's proposed mechanism).
  - active_drb_count : REAL measured (distinct LCIDs per IMSI in
    NrDlRlcStatsE2E.txt) -- every UE in this run has exactly 2: LCID 3
    (default bearer) + LCID 5 (dedicated control-sized bearer added for
    this measurement).
  - macce_latency_proxy_ms : REAL measured RLC delay of the LCID-5
    dedicated bearer's packets, per UE -- explicitly a PROXY (lower-bound
    latency floor for a small control-plane message over this radio+CU-DU
    path), NOT a real dynamic MAC-CE-triggered RLC-mode-switch event, which
    does not exist in 5G-LENA.
  - bip_accuracy : NOT AVAILABLE -- no PAIBO BIP model or labeled dataset
    exists on this machine; no ns-3 run can produce this number.

Uses the same stdlib-only xlsx writer as export_to_excel.py (no
openpyxl/xlsxwriter). Sheets 1 and 2 are regenerated verbatim from the
untouched validated CSVs, not read back from the old xlsx.
"""

import csv
import os
from collections import defaultdict

from export_to_excel import write_xlsx, read_csv_rows

BASE = os.path.dirname(os.path.abspath(__file__))
PHASE01 = os.path.join(BASE, "ns3_phase01")
FK150 = "/root/fullkpi_150" if os.path.exists("/root/fullkpi_150") else r"\\wsl$\Ubuntu\root\fullkpi_150"


def read_tsv_stripped(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = [h.strip().lstrip("%").strip() for h in next(reader)]
        return [dict(zip(header, row)) for row in reader]


def main():
    # --- Sheet 1 & 2: untouched validated CSVs, regenerated as-is ---
    per_ue_path = os.path.join(PHASE01, "per_ue_kpis_validated.csv")
    per_cell_path = os.path.join(PHASE01, "per_cell_kpis_validated.csv")
    sheet1 = ("PerUE_Validated", read_csv_rows(per_ue_path))
    sheet2 = ("PerCell_Validated", read_csv_rows(per_cell_path))

    # --- Sheet 3: real N=150 PAIBO-relevant measurements ---
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

    header = ["imsi", "bearer_setup_latency_ms", "active_drb_count", "macce_latency_proxy_ms",
              "bip_accuracy", "num_ues", "data_source", "notes"]
    rows = [header]
    for imsi in sorted(latency_by_imsi, key=lambda x: int(x)):
        drb_count = len(lcids_by_imsi.get(imsi, set()))
        macce_delays = macce_delays_by_imsi.get(imsi, [])
        macce_mean = round(sum(macce_delays) / len(macce_delays), 4) if macce_delays else "NA"
        rows.append([
            imsi,
            round(latency_by_imsi[imsi], 4),
            drb_count,
            macce_mean,
            "NOT AVAILABLE",
            150,
            "ns3_5glena_simulation (cu-du-full-kpi-study.cc, real measurement)",
            "bearer_setup_latency_ms = RRC attach-start->Connected, real ns-3 measurement, NOT a real 3GPP/OAI/PAIBO number; "
            "macce_latency_proxy_ms = RLC delay of a small dedicated control-sized bearer (LCID 5), a PROXY only -- "
            "5G-LENA has no real dynamic MAC-CE RLC-mode-switch mechanism; "
            "bip_accuracy is NOT AVAILABLE, no PAIBO BIP model or labeled dataset exists on this machine.",
        ])
    sheet3 = ("PAIBO_Real_Measurements_N150", rows)

    out_path = os.path.join(PHASE01, "ns3_phase01_validated_kpis.xlsx")
    write_xlsx([sheet1, sheet2, sheet3], out_path)
    print(f"Wrote {out_path} with 3 sheets ({len(rows) - 1} UE rows in sheet 3)")

    # --- Console summary of real measured values ---
    lat_vals = list(latency_by_imsi.values())
    print("\nBearer setup latency (N=150): min={:.4f} max={:.4f} mean={:.4f} distinct={}".format(
        min(lat_vals), max(lat_vals), sum(lat_vals) / len(lat_vals), len(set(lat_vals))))
    drb_vals = [len(v) for v in lcids_by_imsi.values()]
    print("DRB count (N=150): min={} max={} all==2={}".format(
        min(drb_vals), max(drb_vals), all(d == 2 for d in drb_vals)))
    all_macce = [d for v in macce_delays_by_imsi.values() for d in v]
    print("MAC-CE-proxy latency (N=150, LCID5 RLC delay): n={} mean={:.4f} min={:.4f} max={:.4f}".format(
        len(all_macce), sum(all_macce) / len(all_macce), min(all_macce), max(all_macce)))
    print("BIP accuracy: NOT AVAILABLE (no PAIBO BIP pipeline exists on this machine)")


if __name__ == "__main__":
    main()

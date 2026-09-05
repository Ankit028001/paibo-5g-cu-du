#!/usr/bin/env python3
"""
add_macce_sheet_v3.py

READ-ONLY against ns3_cudu_baseline_results.xlsx and
ns3_macce_test/macce_summary.csv (never modified). Writes a NEW file,
PAIBO_Baseline_Results_v3.xlsx, containing every existing sheet from
ns3_cudu_baseline_results.xlsx unchanged, plus one new sheet
"MAC-CE Model" built from macce_summary.csv.

No simulation run. No OAI/ns-3 source touched.
"""

import csv
import os
import zipfile
import re

from export_to_excel import write_xlsx

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_XLSX = os.path.join(BASE, "ns3_cudu_baseline_results.xlsx")
MACCE_CSV = os.path.join(BASE, "ns3_macce_test", "macce_summary.csv")
OUT_XLSX = os.path.join(BASE, "PAIBO_Baseline_Results_v3.xlsx")

NOTE = ("0.5 ms = modeled next-slot application interval at 30 kHz SCS. "
        "RRC baseline = measured ns-3 value. NOT real OAI MAC-CE measurement.")
LABEL = "modeled_macce_next_slot_interval -- NOT real OAI MAC-CE"


def read_existing_sheets(xlsx_path):
    z = zipfile.ZipFile(xlsx_path)
    wb = z.read("xl/workbook.xml").decode()
    names = re.findall(r'<sheet name="([^"]+)"[^>]*r:id="(rId\d+)"', wb)
    rels = z.read("xl/_rels/workbook.xml.rels").decode()
    target_by_rid = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))

    sheets = []
    for name, rid in names:
        target = target_by_rid[rid]
        content = z.read(f"xl/{target}").decode()
        rows_xml = re.findall(r'<row r="\d+">(.*?)</row>', content)
        rows = []
        for row_xml in rows_xml:
            cells = re.findall(
                r'<c r="[A-Z]+\d+"[^>]*>(?:<v>([^<]*)</v>|<is><t[^>]*>([^<]*)</t></is>)</c>',
                row_xml)
            rows.append([a if a else b for a, b in cells])
        sheets.append((name, rows))
    return sheets


def main():
    existing_sheets = read_existing_sheets(SRC_XLSX)
    print(f"Read {len(existing_sheets)} existing sheets from {SRC_XLSX} (unchanged, read-only):")
    for name, rows in existing_sheets:
        print(f"  - {name} ({len(rows)} rows)")

    with open(MACCE_CSV, newline="") as f:
        macce_rows = list(csv.DictReader(f))

    macce_sheet_rows = [
        [NOTE],
        [],
        ["N", "Modeled MAC-CE (ms)", "RRC Baseline (ms)", "Saving (ms)", "Saving %", "Source", "Label"],
    ]
    for r in macce_rows:
        macce_sheet_rows.append([
            int(r["num_ues"]),
            float(r["modeled_macce_ms"]),
            float(r["rrc_baseline_ms"]),
            float(r["saving_ms"]),
            round(float(r["saving_pct"]), 2),
            "ns3_macce_test/macce_summary.csv (cu-du-macce-model-study.cc)",
            LABEL,
        ])

    all_sheets = existing_sheets + [("MAC-CE Model", macce_sheet_rows)]
    write_xlsx(all_sheets, OUT_XLSX)
    print(f"\nWrote {OUT_XLSX} with {len(all_sheets)} sheets "
          f"({len(existing_sheets)} unchanged + 1 new 'MAC-CE Model')")


if __name__ == "__main__":
    main()

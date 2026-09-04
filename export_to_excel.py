#!/usr/bin/env python3
"""
export_to_excel.py

READ-ONLY against existing validated CSVs. Writes .xlsx files alongside
them. Uses only the Python standard library (csv, zipfile, xml) -- no
openpyxl/xlsxwriter/pandas-with-excel-engine, since none of those are
installed on this machine and installing packages was explicitly not
authorized for this phase.

Does not regenerate, re-run, or modify any simulation or existing CSV.
"""

import csv
import os
import zipfile
from xml.sax.saxutils import escape

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WORKBOOK_RELS_TMPL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
</Relationships>"""

WORKBOOK_TMPL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
{sheet_entries}
</sheets>
</workbook>"""

SHEET_TMPL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
{rows}
</sheetData>
</worksheet>"""


def col_letter(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def is_number(s):
    if s is None or s == "":
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def rows_to_xml(rows):
    out = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, val in enumerate(row):
            ref = f"{col_letter(c_idx)}{r_idx}"
            if is_number(val):
                cells.append(f'<c r="{ref}"><v>{val}</v></c>')
            else:
                text = escape("" if val is None else str(val))
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>')
        out.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return "\n".join(out)


def write_xlsx(sheets, out_path):
    """sheets: list of (sheet_name, list_of_rows) in desired order."""
    sheet_overrides = []
    workbook_rels = []
    sheet_entries = []
    sheet_files = {}

    for i, (name, rows) in enumerate(sheets, start=1):
        sheet_overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        workbook_rels.append(
            f'<Relationship Id="rId{i}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>')
        safe_name = escape(name)[:31]
        sheet_entries.append(f'<sheet name="{safe_name}" sheetId="{i}" r:id="rId{i}"/>')
        sheet_files[f"xl/worksheets/sheet{i}.xml"] = SHEET_TMPL.format(rows=rows_to_xml(rows))

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES.format(sheet_overrides="\n".join(sheet_overrides)))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", WORKBOOK_TMPL.format(sheet_entries="\n".join(sheet_entries)))
        z.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS_TMPL.format(rels="\n".join(workbook_rels)))
        for path, content in sheet_files.items():
            z.writestr(path, content)


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.reader(f)]


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    # --- ns3_phase01: two already-combined validated CSVs -> one workbook ---
    phase01_dir = os.path.join(base, "ns3_phase01")
    phase01_sheets = []
    for csv_name, sheet_name in [
        ("per_ue_kpis_validated.csv", "PerUE_Validated"),
        ("per_cell_kpis_validated.csv", "PerCell_Validated"),
    ]:
        p = os.path.join(phase01_dir, csv_name)
        if os.path.exists(p):
            phase01_sheets.append((sheet_name, read_csv_rows(p)))
        else:
            print(f"SKIP (not found): {p}")
    if phase01_sheets:
        out = os.path.join(phase01_dir, "ns3_phase01_validated_kpis.xlsx")
        write_xlsx(phase01_sheets, out)
        print(f"Wrote {out} ({len(phase01_sheets)} sheets)")

    # --- ns3_cudu_phase: per-level per_ue_kpis.csv / per_cell_kpis.csv -> one workbook, one sheet per level+type ---
    cudu_dir = os.path.join(base, "ns3_cudu_phase")
    cudu_sheets = []
    for n in [1, 10, 25, 50, 100, 150, 200]:
        level_dir = os.path.join(cudu_dir, f"ue_{n}")
        for csv_name, sheet_prefix in [("per_ue_kpis.csv", "PerUE"), ("per_cell_kpis.csv", "PerCell")]:
            p = os.path.join(level_dir, csv_name)
            if os.path.exists(p):
                cudu_sheets.append((f"{sheet_prefix}_{n}", read_csv_rows(p)))
            else:
                print(f"SKIP (not found): {p}")
    if cudu_sheets:
        out = os.path.join(cudu_dir, "ns3_cudu_phase_kpis.xlsx")
        write_xlsx(cudu_sheets, out)
        print(f"Wrote {out} ({len(cudu_sheets)} sheets)")

    print("Done. No source CSVs were modified (read-only).")


if __name__ == "__main__":
    main()

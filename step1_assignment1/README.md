> **Step 1 — Assignment 1 (Aug 20, 2026)**

# Assignment 1 — 5G Setup, Traffic Modelling, KPI Collection

**Requested (Samsung email, 2026-08-20):** bring up a 5G CU-DU setup, do
diverse traffic modelling, and collect KPIs.

**What is actually in this folder:** the earliest ns-3 5G-LENA KPI ladder
— a **single-node, IDEAL-channel gNB** (no CU-DU split yet), run across
the full UE-scaling ladder **1 → 10 → 25 → 50 → 100 → 150 → 200**. This
predates the dedicated CU-DU topology, which was built next and now lives
in `step2_multi_ue_traffic/`. Traffic modelling and KPI collection for
this first pass are captured here (`KPI_AVAILABILITY_MATRIX.md`,
`SCALING_SUMMARY.md`, `NS3_AUDIT.md`) with validated per-UE/per-cell KPI
CSVs.

**Key results:** all 7 UE-count levels PASS with 100% RRC connection
success.

**Status:** Done

**Files in this folder:**
- `README.md` (this file)
- `KPI_AVAILABILITY_MATRIX.md`, `KPI_AVAILABILITY_NOTE.md`, `NS3_AUDIT.md`,
  `PAIBO_VALIDATION_PLAN.md`, `SCALING_SUMMARY.md`, `LADDER_STATUS.txt`
- `ns3_phase01_validated_kpis.xlsx`, `per_cell_kpis_validated.csv`,
  `per_ue_kpis_validated.csv`, `validate_paibo_kpis.py`
- `ue_1/` … `ue_200/` — per-UE-count run outputs

Scenario source: `source/ns3_scenarios/ue-scaling-study.cc`.

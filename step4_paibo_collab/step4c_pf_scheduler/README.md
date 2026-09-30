> **Step 4c — Replace Round Robin with Proportional Fair Scheduler (Sep 2026)**

# Task 4c — Replace Round Robin Scheduler with Proportional Fair

**Requested (Sukhdeep Singh email, "Step 3: PAIBO Collab Project",
2026-09-09):** "Try to check if you can replace the Round Robin
Scheduler with Proportional Fair Scheduler."

**What was done:**
- Switched the ns-3 5G-LENA `nr` module scheduler from Round Robin to
  `NrMacSchedulerTdmaPF` (the built-in Proportional Fair TDMA scheduler).
- Re-ran the full clean UE ladder (1→10→25→50→100→150→200) under PF and
  recorded a direct PF-vs-RR comparison.

**Key results:** every KPI row under this track shows
`scheduler = "PF (NrMacSchedulerTdmaPF)"`; see `pf_vs_rr_comparison.csv`
and `pf_scheduler_comparison.xlsx` for the head-to-head numbers.

**Status:** Done

**Files in this folder:**
- `README.md` (this file)
- `LADDER_STATUS.txt`, `pf_kpi_ladder_consolidated.csv`,
  `pf_vs_rr_comparison.csv`, `pf_scheduler_comparison.xlsx`
- `ue_1/` … `ue_200/` — per-UE-count run outputs

See also `pf_scheduler_model.md` at the repo root.

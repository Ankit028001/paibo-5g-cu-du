> **Step 4a — Remove Noise, Re-record Clean KPIs (Sep 2026)**

# Task 4a — Remove Noise, Re-record Clean KPIs

**Requested (Sukhdeep Singh email, "Step 3: PAIBO Collab Project",
2026-09-09):** "First of all, remove noise from the setup and then
record the values of the KPIs again."

**What was done:**
- Re-ran the full UE ladder (1→10→25→50→100→150→200) with the noise
  model disabled (`noise_model = "none (clean baseline)"` in every
  output row), as a clean counterpart to the noise-augmented run in
  `step3_gpu_noise_kpi/`.
- Consolidated into a single clean KPI ladder, cross-checked against the
  previously-archived clean data.

**Key results:** clean ladder recorded for all 7 UE-count levels;
consolidated in `clean_kpi_ladder_consolidated.csv`.

**Status:** Done

**Files in this folder:**
- `README.md` (this file)
- `LADDER_STATUS.txt`, `clean_kpi_ladder_consolidated.csv`,
  `clean_kpi_ladder_vs_archived.csv`
- `ue_1/` … `ue_200/` — per-UE-count run outputs

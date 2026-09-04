# Assignment Status

Maps every requirement in `instructions_should_be_followed.txt` (plus the
PAIBO-deck-derived KPI requirements) to a status and evidence path.
THIS IS AN ns-3 / 5G-LENA + OAI SIMULATION/LAB STUDY. Real OAI
measurements, ns-3 simulation results, and any future PAIBO-derived
results are kept in separately labeled files/columns throughout —
see `data_source` / `simulation_label` conventions in
`validate_paibo_kpis.py` and `SCALING_SUMMARY.md`.

| Requirement | Status | Evidence path |
|---|---|---|
| E2E 5G setup (ns-3 5G-LENA, explore OAI/OCUDU) | COMPLETE (as two separate tracks) | `ue-scaling-study.cc`, `cu-du-scaling-study.cc`, `/opt/oai/.../phase2/` |
| CU-DU split with all layers + Core Network | PARTIAL — **CU-DU topology/emulation, not a functional 3GPP protocol split**; EPC-style core present | `cu-du-scaling-study.cc` (header comment states the limitation explicitly); `NrPointToPointEpcHelper` in both scenarios |
| KPI list + availability marked against idea slides | COMPLETE | `KPI_AVAILABILITY_NOTE.md`, `PAIBO_KPI_CROSSCHECK.md`, `KPI_AVAILABILITY_MATRIX.md` |
| 1 CU + 1 DU for testing | COMPLETE (topological) | `cu-du-scaling-study.cc` |
| Memory headroom for AI pipeline, subtract from max UE capacity | PARTIAL — measured baseline numbers documented; no revised max-UE number produced (no AI-pipeline footprint has been measured yet) | `MEMORY_BUDGET_NOTE.md` |
| Traffic % matching previous email | COMPLETE | `*_traffic_config.tsv` at every ladder level, both scenarios |
| Traffic with noise (iperf-inspired / noise-augmented model — NOT real iperf3) | COMPLETE | `cu-du-scaling-study-noise.cc`; full 7-level ladder validated under `ns3_cudu_phase_noise/`; documented in `ns3_cudu_phase_noise/NOISE_MODEL.md` |
| Per-UE/per-cell CSV dump + plots | COMPLETE | `per_ue_kpis*.csv`, `per_cell_kpis*.csv`, `plot_*.png` under `ns3_phase01/` and `ns3_cudu_phase/` |
| Multi-UE proportional scaling ladder | COMPLETE | Levels 1/10/25/50/100/150/200, both scenarios, all PASS |
| Record KPI values in Excel | COMPLETE (this phase) | `ns3_phase01/ns3_phase01_validated_kpis.xlsx`, `ns3_cudu_phase/ns3_cudu_phase_kpis.xlsx` |
| Push traffic/channel model to GitHub | NOT IMPLEMENTED | No repo/push performed; requires explicit approval (visible, hard-to-reverse action) |
| Normalize traffic volume to 100% | COMPLETE | Byte-volume proportions measured and reported in `STATUS_2_TRAFFIC_3_KPI.md` |
| PAIBO Result Type 1 — bearer setup latency | NOT IMPLEMENTED | Source pipeline (`1_generate_traffic.py` etc.) confirmed absent machine-wide (forensic search, prior turn). No synthetic values created. |
| PAIBO Result Type 2 — RL-SDAP / DRB reduction | NOT IMPLEMENTED | `3_train_rl_sdap.py` confirmed absent. No synthetic values created. |
| PAIBO Result Type 3 — MAC-CE adaptation latency | NOT IMPLEMENTED | Requires either real OAI MAC-CE (doesn't exist in stock OAI) or an explicitly-labeled analytical model — neither built yet. |
| PAIBO Result Type 4 — BIP ML accuracy | NOT IMPLEMENTED | `2_train_bip.py` confirmed absent; no trained model, no labeled dataset, `sklearn` not installed. Cannot be produced without fabrication. |
| Merge PAIBO results with ns-3 KPIs | NOT IMPLEMENTED (blocked) | Depends entirely on Result Types 1-4 existing first |
| Real OAI vs ns-3 vs PAIBO clearly separated | COMPLETE | `data_source`/`simulation_label` columns enforced in `validate_paibo_kpis.py`; explicit banners in `SCALING_SUMMARY.md` and scenario `.cc` file headers |
| No extrapolation beyond measured results | COMPLETE | `SCALING_SUMMARY.md` states no extrapolation beyond 200 UEs; NA-with-reason discipline enforced throughout; this note does not invent a max-UE number either |

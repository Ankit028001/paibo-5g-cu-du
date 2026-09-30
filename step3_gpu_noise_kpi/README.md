> **Step 3 — Task 3: GPU Migration, Noise Traffic, KPI Dump (Aug 30, 2026)**

# Task 3 — GPU Migration, iperf-Inspired Noise Traffic, KPI CSV + Plots

**Requested (Samsung email, 2026-08-30):** migrate the setup to a GPU
machine, test max UE capacity (1 CU + 1 DU), create an iperf-based
traffic pattern with noise, and dump per-UE/per-cell KPIs to CSV with
plots.

**What was done:**
- Setup migrated to a GPU-capable machine; the same CU-DU topology from
  `step2_multi_ue_traffic/` re-run there.
- An **iperf-inspired** noise model added on top of ns-3's
  `OnOffApplication`: per-class lognormal rate jitter, packet-size
  variation, and staggered per-UE start offsets, all with dedicated fixed
  RNG seeds for reproducibility. This is explicitly **not real iperf3**
  (ns-3 UEs have no OS socket layer for a real iperf3 process to run
  against) — full model in `ns3_cudu_phase_noise/NOISE_MODEL.md`.
- Per-UE and per-cell KPIs dumped to CSV, plus trend plots (SINR,
  throughput, latency, registration success, traffic volume by class).

**Key results:** all 7 UE-count levels PASS with 100% RRC connection
success under the noisy traffic model too.

**Status:** Done

**Contents:**
- `ns3_cudu_phase_noise/` — noise-augmented CU-DU ladder (see
  `NOISE_MODEL.md` inside for the full model, including a documented
  known interaction where mMTC's max start offset equals the whole
  30s simulation duration)
- `baseline_plots/` — SINR, throughput, latency, registration-success,
  and traffic-volume-by-class plots

Scenario source: `source/ns3_scenarios/cu-du-scaling-study-noise.cc`.

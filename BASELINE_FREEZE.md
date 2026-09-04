# NON-PAIBO BASELINE — FROZEN

This is the frozen state of the non-PAIBO baseline, immediately before any
PAIBO-specific implementation begins. Everything below already exists on
disk and is validated; this file is the manifest/checkpoint marker, not
new data.

```
NON-PAIBO BASELINE
│
├── Real OAI
│   └── CU-DU + 5GC validation
│       - 8-UE / 106-PRB pilot: 0/8 attach (PHY sync failure, WSL2
│         real-time scheduling limitation) — /opt/oai/openairinterface5g/
│         phase2/20260902_vrtsim_cudu_8ue_106prb/
│       - 100-UE-configured run, attempt_03: 2 UEs registered + PDU
│         session established (peak real OAI CU-DU success on this
│         machine) — phase2/20260903_100ue_vrtsim_cudu_189prb_patched/
│       - F1/NGAP/PFCP control-plane health, CPU/RAM measurements: see
│         MEMORY_BUDGET_NOTE.md
│
├── ns-3 / 5G-LENA
│   ├── Ideal channel (single-node gNB)
│   │   └── 1 → 10 → 25 → 50 → 100 → 150 → 200
│   │       ns3_phase01/ (ue-scaling-study.cc)
│   │
│   ├── CU-DU topology (topological split, NOT functional 3GPP F1)
│   │   └── 1 → 10 → 25 → 50 → 100 → 150 → 200
│   │       ns3_cudu_phase/ (cu-du-scaling-study.cc)
│   │
│   └── iperf-inspired / noise-augmented traffic model
│       └── 1 → 10 → 25 → 50 → 100 → 150 → 200
│           ns3_cudu_phase_noise/ (cu-du-scaling-study-noise.cc)
│           NOT real iperf3 — see NOISE_MODEL.md for exact terminology
│           and the documented mMTC-offset-vs-30s-simTime interaction.
│
└── Excel + CSV + plots + KPI documentation
    - ns3_cudu_baseline_results.xlsx (5 sheets: Per-UE Results,
      Cell-Level Results, KPI Availability CrossCheck, Experiment
      Configuration, Traffic Model)
    - ns3_phase01/ns3_phase01_validated_kpis.xlsx (Per-UE/Cell-Level +
      real bearer-setup-latency baseline ladder + reference PAIBO-track
      add-a-bearer experiment, clearly separated)
    - baseline_comparison_summary.csv
    - baseline_plots/ (8 plots, all labeled "ns-3 / 5G-LENA BASELINE — NO PAIBO")
    - ns3_cudu_phase/BASELINE_DATA_INTEGRITY.md (7/7 PASS)
    - BASELINE_REMAINING_GAPS.md (iperf-noise gap: RESOLVED; Scenario B: still open)
    - PAIBO_KPI_CROSSCHECK.md, KPI_AVAILABILITY_MATRIX.md
    - ASSIGNMENT_STATUS.md
```

## What is explicitly NOT in this baseline (by design)

- No PAIBO Result Types 1-4 (bearer setup latency's own separate
  instrumented measurement exists as an ns-3 baseline number, but it is
  NOT a PAIBO Bearer Hint measurement — no such mechanism exists anywhere).
- No BIP model, no DRB-consolidation mechanism, no MAC-CE adaptation
  mechanism, no synthetic PAIBO numbers of any kind.
- No Scenario B (realistic/fading channel) — only Scenario A (IDEAL
  channel) has been run, in both the plain and noise-augmented variants.
- No real iperf3 — the "noise-augmented" branch is an ns-3
  `OnOffApplication`-based approximation, explicitly not real iperf3.

## Freeze point

From here, PAIBO becomes a fully separate layer:

```
Baseline ns-3 (frozen above)  →  PAIBO ns-3/Python (future work)  →  Baseline vs PAIBO comparison
```

A local git checkpoint (commit only, not pushed anywhere) was made at this
point — see the git log in this directory for the commit hash.

# PF Scheduler Comparison — Clean CU-DU Ladder (RR vs PF)

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION. IT IS NOT REAL OAI CU-DU EXECUTION.**

## What this is

A scheduler swap experiment on top of the existing clean (non-noise) CU-DU
baseline (`ns3_cudu_phase/`, scenario `source/ns3_scenarios/cu-du-scaling-study.cc`).
Two independent artifact sets exist for this comparison:

- **`ns3_clean_kpi_ladder/`** — a **fresh confirmation re-run** of the unmodified
  RR baseline scenario (`cu-du-scaling-study.cc`, default scheduler
  `NrMacSchedulerTdmaRR`), full 1/10/25/50/100/150/200 UE ladder. This is a
  reproduction run, not a new experiment: every comparable KPI matched the
  original `ns3_cudu_phase/` archive exactly (`FlowMonitor` XML and parser
  `per_cell_kpis.csv` byte-identical at all 7 levels; only wall-clock time
  differed, due to different hardware).
- **`ns3_clean_kpi_ladder_pf/`** — the same scenario and ladder, run with the
  scheduler changed to **Proportional Fair** (see below).

## What changed for the PF variant

A new source file, `source/ns3_scenarios/cu-du-scaling-study-pf.cc`, was
created as `cu-du-scaling-study.cc` **plus exactly one line**, inserted
immediately after `nrHelper->SetEpcHelper(nrEpcHelper)`:

```cpp
nrHelper->SetSchedulerTypeId(TypeId::LookupByName("ns3::NrMacSchedulerTdmaPF"));
```

This replaces `NrHelper`'s default scheduler (`NrMacSchedulerTdmaRR`, Round
Robin) with **`NrMacSchedulerTdmaPF`** (TDMA Proportional Fair). Nothing else
in the scenario was changed — same channel, same traffic model, same seed
(20260901, run 1), same topology, same F1 link. The original
`cu-du-scaling-study.cc` is byte-identical to the baseline (verified by
SHA256); this is an additive variant, not a modification of the baseline.

Five further PF variants of the other custom scenarios were created the same
way and are included in `source/ns3_scenarios/` for completeness
(`ue-scaling-study-pf.cc`, `cu-du-scaling-study-noise-pf.cc`,
`cu-du-bearer-latency-study-pf.cc`, `cu-du-full-kpi-study-pf.cc`,
`cu-du-macce-model-study-pf.cc`) — **only `cu-du-scaling-study-pf.cc` was run**
for this comparison; the others are unbuilt/unrun source only.

## Result summary (see `ns3_clean_kpi_ladder_pf/pf_vs_rr_comparison.csv` for full detail)

On nearly every KPI, **PF ≡ RR** (Δ = 0) at all 7 UE levels: RRC-connected,
aggregate DL throughput, total rx bytes, packet loss (0 at every level, both
schedulers), per-UE throughput distribution (min/max), and the **Jain
fairness index** (identical, both schedulers). MCS, mean delay, and RLC/PDCP
delay differ by < 0.15 % (AMC-convergence micro-noise from scheduling order).

**The one KPI that moves materially is jitter**, growing with UE count:

| UE count | RR jitter (ms) | PF jitter (ms) | Δ% |
|---:|---:|---:|---:|
| 1   | 0.2207 | 0.2207 | 0.0 |
| 10  | 0.1888 | 0.1888 | 0.0 |
| 25  | 0.1952 | 0.1937 | −0.8 |
| 50  | 0.2131 | 0.2629 | +23.4 |
| 100 | 0.2596 | 0.4833 | +86.2 |
| 150 | 0.3081 | 0.7936 | +157.6 |
| 200 | 0.3714 | 1.0735 | +189.0 |

## Interpretation

The channel in this scenario is **IDEAL** (3GPP RMa LOS path loss only, no
shadowing, no fading — every UE sees ~63.8 dB SINR, effectively identical).
Proportional Fair's entire mechanism is scheduling on
`achievable_rate / running_average_rate` to exploit **per-user channel
variation**; with no channel diversity, PF has nothing to gain on capacity or
fairness over Round Robin here. What PF *does* do differently: each UE's
priority drifts as its own running-average throughput updates, so PF
reorders which UE is served slot-to-slot more than strict Round Robin does —
producing burstier per-UE packet delivery (higher jitter) while the mean
delay and total delivered bytes stay the same. Traffic in this scenario is
also rate-capped per UE (0 packet loss at every level, both schedulers), so
every UE's demand is fully met regardless of scheduler — which is why the
Jain fairness index and per-UE throughput spread are **identical** between
RR and PF. A channel with real per-UE SINR variation (shadowing/fading) would
be required to observe PF's intended throughput/fairness benefit.

## Source / config / provenance

- ns-3.48 (`d2add90b452d600cfb4859baed8e9ea633519447`), 5G-LENA nr v5.1
  (`cedceadda17392c90587fb9400eb9b1f8c236713`)
- Seed 20260901, run 1 (scenario default, not passed on the command line)
- `simTime=30`, `fullTraces=true` for N=1..150, `fullTraces=false` for N=200
  (identical policy on both RR and PF runs)
- Scenario source: `source/ns3_scenarios/cu-du-scaling-study.cc` (RR, baseline,
  unmodified) and `source/ns3_scenarios/cu-du-scaling-study-pf.cc` (PF, new)
- Per-level command actually executed is recorded in each level's
  `command.txt` in both `ns3_clean_kpi_ladder/` and `ns3_clean_kpi_ladder_pf/`
- KPI extraction: the project's own `scripts/parse_ns3_kpis.py`
  (unmodified, no substitute parser used)

## What is explicitly out of scope for this comparison

This RR-vs-PF comparison uses **only** the clean (non-noise) CU-DU scenario.
The noise/stagger-augmented scenario (`ns3_cudu_phase_noise/`,
`cu-du-scaling-study-noise.cc`) is a **separate experiment** and is not part
of, and was not re-run for, this comparison. `cu-du-scaling-study-noise-pf.cc`
exists as a built-but-unrun source variant only (see above).

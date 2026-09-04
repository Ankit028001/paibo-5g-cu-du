# Baseline Remaining Gaps — ns-3 / 5G-LENA, PAIBO Not Implemented

> **UPDATE: this gap is now RESOLVED.** The iperf-inspired / noise-augmented
> traffic model described below has since been implemented
> (`cu-du-scaling-study-noise.cc`) and validated across the full 7-level
> ladder under `ns3_cudu_phase_noise/`. See
> `ns3_cudu_phase_noise/NOISE_MODEL.md` for the full model, its known
> limitations, and the measured effect on aggregate throughput. The
> analysis below is kept for historical record of what was originally
> missing and why.

The assignment instructions explicitly require:

> "6). Create a traffic pattern of a UE and a cell using iperf (as we did in
> our previous project). The traffic should be close to real traffic, so,
> add some noise, as suggested by you."

## Status: NOT IMPLEMENTED in the current validated baseline

| Requirement | Current state | Implemented? |
|---|---|---|
| iperf3-generated traffic | ns-3 `OnOffApplication`, constant-rate UDP flows | **No.** ns-3 UEs/gNB have no OS-level socket layer for a real `iperf3` process to run against; this would need to be approximated inside ns-3's application layer, not literal `iperf3`. |
| Burstiness / realistic traffic variation | Fixed-rate OnOff flow per class (`OnTime=1e9`, `OffTime=0` — effectively always-on, constant rate) | **No.** |
| Noise on traffic (per your own earlier detailed spec: lognormal per-burst rate variation, per-class packet-size distributions, ±5% inter-packet timing jitter, staggered UE start offsets) | Not present in either `ue-scaling-study.cc`, `cu-du-scaling-study.cc`, `cu-du-bearer-latency-study.cc`, or `cu-du-full-kpi-study.cc` | **No.** |

**This gap has not been silently patched into the validated dataset.** No noise model has been added to `cu-du-scaling-study.cc` or any other file used to produce the currently-validated `ns3_cudu_phase/` or `ns3_phase01/` results. Those results remain exactly as originally run: constant-rate, noise-free traffic.

## What implementing this would require

1. **Modify** `cu-du-scaling-study.cc` (and/or `ue-scaling-study.cc`) to add the noise model — a genuine source-code change, not a post-processing step. A fully worked-out spec for this (lognormal rate variation with per-class σ, per-class packet-size distributions, ±5% inter-packet jitter, per-class staggered start offsets, deterministic per-UE RNG streams) was already produced earlier in this session but never applied to any file.
2. **Rebuild** the modified scenario (`./ns3 build`).
3. **Re-run the entire UE ladder** (1/10/25/50/100/150/200) — the existing validated results **cannot** be reused with noise added after the fact, since the noise must be generated during the simulation itself (it affects packet timing/size/rate at generation time, not something derivable from already-completed FlowMonitor/RLC output).
4. **Re-validate** (KPI extraction, plots, integrity checks) against the new noisy dataset, kept separate from this baseline (e.g. under a new `ns3_cudu_phase_noise/` directory), per the standing instruction to never overwrite validated results.

## Decision needed

This gap requires a **new simulation run**, not something derivable from existing data. It has not been started in this baseline-consolidation phase, per the instruction to avoid modifying the validated dataset and to report exactly what's missing rather than filling it in silently. Confirm whether/when to proceed with the noise-model implementation and re-run.

# PAIBO 5G Baseline — Channel Model

## Overview

Two ns-3 channel scenarios are defined for this baseline. **Only Scenario
A has been executed.** Scenario B is a planned configuration only — it
has never been run, and no result exists for it anywhere in this
repository. Every configuration value below is read directly from
`source/ns3_scenarios/cu-du-scaling-study.cc` /
`cu-du-scaling-study-noise.cc` / `ue-scaling-study.cc` (all three use an
identical channel configuration) or computed directly from a validated
result CSV already in this repository.

## Scenario A — Ideal Channel (EXECUTED)

### Purpose

Establish network behavior under a deterministic, interference-free
radio channel, isolating scheduling/protocol-stack behavior (and, in the
CU-DU/noise variants, topology and traffic effects) from radio-channel
variability.

### Configuration

Verified directly from source:

- **Path-loss model:** `NrChannelHelper::ConfigureFactories("RMa", "LOS", "ThreeGpp")`
  — **3GPP RMa (Rural Macro), LOS-only condition forced.** This is **not**
  UMa (Urban Macro) — the scenario source explicitly configures RMa.
- **Shadowing:** disabled (`SetPathlossAttribute("ShadowingEnabled", BooleanValue(false))`)
- **Fading:** not attached — channel is assigned via
  `NrChannelHelper::INIT_PROPAGATION` only (deterministic path loss, no
  fading/multipath spectrum model attached)
- **Carrier frequency:** 3.5 GHz (band n78)
- **Bandwidth:** `189 PRB * 12 subcarriers * 30 kHz = 68.04 MHz` — the
  scenario targets and achieves exactly 189 PRB at every UE level (logged
  and confirmed at runtime; see `ns3_cudu_phase/BASELINE_DATA_INTEGRITY.md`).
  **This scenario does NOT use 106 PRB / 40 MHz** — that configuration
  does not appear anywhere in this scenario's source.
- **SCS:** 30 kHz (numerology 1)
- **TDD pattern:** **NOT VERIFIED / not explicitly configured.** No
  `Pattern` attribute or explicit DL/UL slot pattern string is set
  anywhere in this scenario's source — it uses a single bandwidth part
  with whatever TDD/FDD behavior the 5G-LENA `nr` module defaults to for
  a single-BWP, numerology-1 configuration. The "DL-heavy" claim in an
  earlier draft of this document could not be verified against the source
  and has been removed rather than repeated.
- **Antenna configuration:** UE: 2 rows x 4 columns, isotropic antenna
  elements. gNB: 4 rows x 8 columns, isotropic antenna elements. **Not**
  1x1 omnidirectional.
- **UE placement:** `GridScenarioHelper`, single base station (1 row x 1
  column site grid), horizontal/vertical BS distance 10.0 (inter-site
  spacing, not directly relevant with a single site), BS height 10 m, UE
  height 1.5 m, `ScenarioHeight=3`, `ScenarioLength=3`. **NOT VERIFIED**
  beyond these parameter values: this repository does not have direct
  evidence of the exact UE-placement radius/area these `GridScenarioHelper`
  parameters translate to internally, so the earlier draft's "random
  uniform in cell radius 500 m" claim could not be confirmed and has been
  removed rather than repeated.
- **gNB TX power:** 35 dBm (`totalTxPower = 35`, applied via
  `NrHelper::GetGnbPhy(...)->SetAttribute("TxPower", ...)`). **Not 40 dBm.**
- **UE TX power:** **NOT VERIFIED.** No UE TX power attribute is set
  anywhere in this scenario's source; it uses whatever default the 5G-LENA
  `nr` module applies when this attribute is left unconfigured. The earlier
  draft's "23 dBm" figure could not be confirmed against the source and has
  been removed rather than repeated.
- **Scheduler:** `NrMacSchedulerTdmaRR` (Round-Robin, TDMA) — this is the
  5G-LENA `NrHelper` default (`nr-helper.cc`,
  `m_schedFactory.SetTypeId(NrMacSchedulerTdmaRR::GetTypeId())`), not
  overridden anywhere in this scenario, so Round-Robin is confirmed as
  what actually ran.
- **Seed:** `RngSeedManager::SetSeed(20260901)`, run 1.

### Measured Results (Scenario A, N=150)

Source: `ns3_phase01/per_cell_kpis_validated.csv`, row `num_ues=150`
(single-node gNB variant; the CU-DU and noise-augmented variants share
the identical channel configuration and measure the same SINR at N=150,
confirmed independently in `ns3_cudu_phase_noise/ue_150/per_cell_kpis.csv`:
`avgUeSinrDb=63.81022533333334`, matching exactly):

- Mean DL SINR: **63.8102 dB**
- SINR p10 / p50 / p90: **63.5421 / 63.8294 / 64.0694 dB**
- DL BLER: **0.0%**
- HARQ retransmissions: **0** (verified via `rv != 0` count across all
  rows of `RxPacketTrace.txt` at every ladder level, `ns3_cudu_phase/`)
- Mean DL MCS: **27.8531** (non-noise / CU-DU variant, N=150). In the
  noise-augmented variant at the same UE count, mean MCS measures
  slightly lower (**27.2821**, from
  `ns3_cudu_phase_noise/ue_150/per_cell_kpis.csv`) — this small difference
  is a real, measured data point (traffic-pattern differences can shift
  AMC convergence slightly) and has not been investigated further; it is
  reported here rather than omitted.

### Interpretation

The near-constant ~63.8 dB SINR (sub-1 dB spread across all 150 UEs) is a
direct consequence of the LOS-only, no-shadowing, no-fading configuration
— not evidence of real-world robustness. All UEs experience essentially
identical channel conditions regardless of position. This is intentional
for a baseline that isolates scheduling/protocol/topology behavior from
radio-channel effects, and is documented as a limitation in
`ns3_cudu_phase/SCALING_SUMMARY.md` / `NS3_AUDIT.md`.

## Scenario B — Realistic Channel (DEFINED, NOT YET RUN)

### Purpose

Introduce realistic radio impairments (shadowing, fading, heterogeneous
per-UE SINR) to observe scheduling/protocol behavior under non-ideal
conditions — this has not yet been run against this baseline in any form.

### Planned Configuration

**No planned-configuration values are recorded anywhere in this
repository.** Rather than restate an earlier draft's specific numbers
(which could not be traced to any file in this repository and are
therefore unverifiable), this section is left explicitly incomplete.
Scenario B's configuration should be specified and documented here only
once it is actually defined in a reviewed scenario source file.

### Status

**NOT EXECUTED.** No `ns3_cudu_phase_*` or `ns3_phase01` result directory
corresponding to a realistic/fading channel exists in this repository. No
result for Scenario B is claimed or implied anywhere in this document.

## Relationship to OAI Real Stack

Verified against the real OAI experiment documentation already in this
repository (`ASSIGNMENT_STATUS.md`, `MEMORY_BUDGET_NOTE.md`, and the OAI
`phase2/20260902_vrtsim_cudu_8ue_106prb/SUMMARY.md`):

- The real OAI CU-DU pilot used OAI's **`vrtsim`** virtual radio-transport
  simulator (**not** `rfsim`) — verified from the OAI `SUMMARY.md`, which
  explicitly reports `--device.name vrtsim` throughout. Any statement about
  `rfsim` would be unverified and is not made here.
- That pilot's IDEAL-channel analog corresponds to **`vrtsim.chanmod=0`**
  ("pure passthrough"), confirmed directly in the OAI `SUMMARY.md`: *"IDEAL
  channel (`vrtsim.chanmod=0`, pure passthrough)"*. A near-zero-loss
  modeled variant (`vrtsim.chanmod=1`, `ploss_dB=0`, `noise_power_dB=-100`)
  was also tested there as a bounded diagnostic, not as the primary
  configuration.
- **This is conceptually the closest OAI analog to ns-3 Scenario A**
  (both aim for a channel with no injected impairment), but the two are
  **implemented completely differently** — ns-3's discrete-event RMa/LOS
  propagation-loss model vs. OAI `vrtsim`'s shared-memory IQ passthrough —
  and **must never be presented as measuring the same thing.** In
  particular, the OAI 8-UE pilot measured 0/8 successful UE attaches
  (PHY-layer sync failure, root-caused to this host's real-time scheduling
  limitations, per `ASSIGNMENT_STATUS.md`), so no OAI radio-layer KPI
  (SINR, BLER, MCS, etc.) exists to compare against the ns-3 Scenario A
  numbers above even in principle.

## Important Limitations

- No Doppler / UE mobility modeled in any executed ns-3 run (static
  `GridScenarioHelper` placement).
- No inter-cell interference modeled — single cell, single gNB throughout
  every executed ns-3 scenario in this repository.
- The ns-3 channel model here (3GPP RMa/LOS, INIT_PROPAGATION only) is an
  abstracted statistical path-loss model, not a ray-tracing or
  measurement-based model.
- OAI `vrtsim` is a software shared-memory IQ pipe with configurable
  impairments, not a real RF channel or hardware-in-the-loop system.
- The ns-3 CU-DU topology (`cu-du-scaling-study.cc` /
  `cu-du-scaling-study-noise.cc`) shares this exact channel configuration
  but is a topological representation only, not a functional 3GPP F1
  implementation — see `README.md` and the `.cc` file header comments.

## Source Files

- Scenario A configuration (identical across all three): `source/ns3_scenarios/ue-scaling-study.cc`,
  `source/ns3_scenarios/cu-du-scaling-study.cc`, `source/ns3_scenarios/cu-du-scaling-study-noise.cc`
- Scheduler default: verified against `nr-helper.cc` in the installed 5G-LENA `nr` module (not copied into this repository)
- Scenario A measured results: `ns3_phase01/per_cell_kpis_validated.csv`, `ns3_cudu_phase_noise/ue_150/per_cell_kpis.csv`
- Scenario B planned configuration: not yet defined in any file in this repository — to be added when specified and executed
- OAI relationship claims: `ASSIGNMENT_STATUS.md`, `MEMORY_BUDGET_NOTE.md`, OAI `phase2/20260902_vrtsim_cudu_8ue_106prb/SUMMARY.md` (not copied into this repository)

# Source Provenance

These are copies, not the live installations. `/opt/oai/openairinterface5g`
and `/opt/ns3/ns-3-dev` were NOT modified, moved, or deleted to produce
these copies — verified via `git status` in both trees immediately before
and after copying (OAI: only the same 3 approved modified files +
pre-existing untracked `phase2/`/`phase3_*` dirs, unchanged).

## OAI patches (`source/oai_patches/`)

Copied read-only from `/opt/oai/openairinterface5g/` at commit
**`ceccfc8ffa4340d5bdc08a9fc84d2e6ab3f9472c`**.

| File in this repo | Original path |
|---|---|
| `oai_patches/openairinterface5g_limits.h` | `common/openairinterface5g_limits.h` |
| `oai_patches/system.c` | `common/utils/system.c` |
| `oai_patches/vrtsim.c` | `radio/vrtsim/vrtsim.c` |

These are the exact 3 approved modifications to stock OAI referenced
throughout `ASSIGNMENT_STATUS.md`, `MEMORY_BUDGET_NOTE.md`, and the OAI
phase2 experiment `SUMMARY.md` files — nothing else in OAI was touched.

## ns-3 / 5G-LENA scenarios (`source/ns3_scenarios/`)

Copied read-only from `/opt/ns3/ns-3-dev/contrib/nr/examples/`.
ns-3 version: **ns-3.48**. 5G-LENA `nr` module version: **v5.1
(5g-lena-v5.1.y)**.

| File in this repo | Original path | Produces |
|---|---|---|
| `ns3_scenarios/ue-scaling-study.cc` | `contrib/nr/examples/ue-scaling-study.cc` | `ns3_phase01/` (IDEAL channel, single-node gNB, 6-class traffic ladder) |
| `ns3_scenarios/cu-du-scaling-study.cc` | `contrib/nr/examples/cu-du-scaling-study.cc` | `ns3_cudu_phase/` (topological CU-DU split ladder) |
| `ns3_scenarios/cu-du-scaling-study-noise.cc` | `contrib/nr/examples/cu-du-scaling-study-noise.cc` | `ns3_cudu_phase_noise/` (iperf-inspired / noise-augmented traffic ladder) |
| `ns3_scenarios/cu-du-bearer-latency-study.cc` | `contrib/nr/examples/cu-du-bearer-latency-study.cc` | `Baseline_NonPAIBO_Ladder` sheet data (real RRC-connection-latency measurement, clean scenario, no added bearer) |

**Deliberately NOT included** (per the instruction to keep PAIBO fully
separate from this baseline freeze): `cu-du-full-kpi-study.cc`, which adds
an extra dedicated bearer for the earlier PAIBO-track exploration
(`PAIBO_Real_Measurements_N150` sheet, explicitly labeled in that sheet as
NOT part of the non-PAIBO baseline). If/when the PAIBO layer is resumed,
that file should live under a separate `source/paibo_scenarios/` (or
similar), not here.

## Reproduction

Each scenario was run with `RngSeedManager` seed **20260901**, run **1**,
via the driver scripts in `scripts/` (`run_cudu_ladder.sh`,
`run_cudu_noise_ladder.sh`, `run_baseline_bearer_latency_ladder.sh`) at UE
counts 1/10/25/50/100/150/200, `--simTime=30`. KPI CSVs/plots are produced
by `scripts/parse_ns3_kpis.py`. Build with:
`./ns3 configure --enable-examples --enable-tests && ./ns3 build <target-name>`
from an ns-3.48 tree with the 5G-LENA v5.1 `nr` module installed under
`contrib/nr`.

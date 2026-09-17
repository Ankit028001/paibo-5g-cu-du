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

**`conventional-attach-baseline-study.cc` is the one exception to the
`source/ns3_scenarios/` + top-level-results-directory layout above** — at
the requester's instruction it, its documentation, and its ladder results
were consolidated into a single self-contained folder instead:

| File in this repo | Original path | Contains |
|---|---|---|
| `conventional_attach_baseline/conventional-attach-baseline-study.cc` | `contrib/nr/examples/conventional-attach-baseline-study.cc` | The scenario source itself |
| `conventional_attach_baseline/conventional_attach_baseline_ns3.md` | — | Full MEASURED/MODELED documentation for this scenario |
| `conventional_attach_baseline/conventional_attach_baseline_ladder.csv`, `..._summary.md`, `LADDER_STATUS.txt` | — | Consolidated 7-level (1/10/25/50/100/150/200 UE) ladder results |
| `conventional_attach_baseline/ue_{1,10,25,50,100,150,200}/` | — | Per-UE-count lightweight results (attach timeline CSV, run summary, traffic config, exit status — no FlowMonitor XML, no raw PHY/MAC/RLC/PDCP traces) |

This scenario measures a conventional attach timeline: 1 MEASURED real ns-3
RRC-connection event (`NrGnbRrc::ConnectionEstablished`) plus 18 MODELED
signaling hops following the message sequence shown in the "Standard 3GPP
Attach Procedure" diagram from `5g-sa-paibo-attach-comparison.pptx` — that
is the diagram's own title, quoted as a fact about the source material, not
this artifact's name — plus a genuinely MEASURED FlowMonitor
first-data-packet KPI. See
`conventional_attach_baseline/conventional_attach_baseline_ns3.md` for the
full MEASURED/MODELED breakdown. **Renamed from
`standard-attach-baseline-study.cc` — naming/label change only; re-run
fresh under the new binary name and confirmed byte-for-byte identical
numeric results at every UE count before and after both the rename and
this folder consolidation (git recognized every moved file as a 100%-
identical rename, confirmed via `git status`).**

**Deliberately NOT included** (per the instruction to keep PAIBO fully
separate from this baseline freeze): `cu-du-full-kpi-study.cc`, which adds
an extra dedicated bearer for the earlier PAIBO-track exploration
(`PAIBO_Real_Measurements_N150` sheet, explicitly labeled in that sheet as
NOT part of the non-PAIBO baseline). If/when the PAIBO layer is resumed,
that file should live under a separate `source/paibo_scenarios/` (or
similar), not here. The same applies to any future PAIBO-attach variant of
`conventional-attach-baseline-study.cc` — it is explicitly out of scope for
this file and this commit.

### `contrib/nr/examples/CMakeLists.txt` change for `conventional-attach-baseline-study`

Building `conventional-attach-baseline-study.cc` requires one line added to the
`base_examples` list in `/opt/ns3/ns-3-dev/contrib/nr/examples/CMakeLists.txt`
(this repo does not track a copy of the ns-3/5G-LENA tree itself, only the
scenario `.cc` files that were copied out of it — see note above). The
exact change applied on the build host:

```diff
     cu-du-scaling-study-noise
     cu-du-macce-model-study
+    conventional-attach-baseline-study
     ue-scaling-study-pf
```

(inserted after `cu-du-macce-model-study`, before the `-pf` scheduler
variants, in the existing `base_examples` list — no other line in that
file was touched. This entry previously read `standard-attach-baseline-study`
and was renamed in place.)

## Reproduction

Each scenario was run with `RngSeedManager` seed **20260901**, run **1**,
via the driver scripts in `scripts/` (`run_cudu_ladder.sh`,
`run_cudu_noise_ladder.sh`, `run_baseline_bearer_latency_ladder.sh`) at UE
counts 1/10/25/50/100/150/200, `--simTime=30`. KPI CSVs/plots are produced
by `scripts/parse_ns3_kpis.py`. Build with:
`./ns3 configure --enable-examples --enable-tests && ./ns3 build <target-name>`
from an ns-3.48 tree with the 5G-LENA v5.1 `nr` module installed under
`contrib/nr`.

`conventional-attach-baseline-study` was run the same way, at the same UE
counts, but with `--simTime=10` (matching its own validated 1-UE
proof-of-concept configuration) rather than 30, and with `--hopDelayMs`
left at its default (0.1 ms, also applied to the real EPC `S1uLinkDelay`
attribute — see `conventional_attach_baseline/conventional_attach_baseline_ns3.md`).
Results are under `conventional_attach_baseline/`.

# PAIBO Baseline — Non-PAIBO ns-3 / OAI 5G Baseline (Frozen)

## Project purpose

This repository is the frozen **pre-PAIBO baseline** for a study comparing
PAIBO ("Predictive AI-driven Bearer Orchestration," a Samsung SRI-B patent
proposal) against measured/simulated 5G RAN behavior. It establishes what
can be measured **today**, with no PAIBO mechanism implemented anywhere,
across two independent tracks — a real OAI CU-DU stack and an ns-3/5G-LENA
discrete-event simulation — so that any future PAIBO result can be
compared against a known, honest, non-fabricated baseline.

**PAIBO has NOT been implemented in this repository.** No Bearer Intent
Predictor, no shadow bearers, no Bearer Hint signaling, no MAC-CE
micro-reconfiguration, no RL-based SDAP consolidation, and no BIP model
exist anywhere in this codebase or its results. Every PAIBO-related field
in the KPI documentation is explicitly marked `Not Available`, never
estimated or fabricated.

## Real OAI baseline

A real OpenAirInterface (OAI) CU-DU + 5G Core (CN5G) stack was run on this
host, at OAI commit **`ceccfc8ffa4340d5bdc08a9fc84d2e6ab3f9472c`**, with 3
approved source modifications (see `source/oai_patches/` and
`source/SOURCE_PROVENANCE.md`):

- `common/openairinterface5g_limits.h`
- `common/utils/system.c`
- `radio/vrtsim/vrtsim.c`

**Measured result:** the 8-UE / 106-PRB pilot achieved 0/8 successful UE
attaches (PHY-layer synchronization failure, root-caused to this WSL2
host lacking the real-time thread scheduling `vrtsim`'s shared-memory IQ
timing model assumes). A separate 100-UE-configured experiment achieved a
peak of 2 UEs registered + PDU session established — the highest real OAI
CU-DU success on this machine. F1-C, F1-U (bind-level), and NGAP
control-plane procedures all passed independently of UE attach success.
Full detail: `ASSIGNMENT_STATUS.md`, `MEMORY_BUDGET_NOTE.md`, and the OAI
`phase2/*/SUMMARY.md` files.

## ns-3 / 5G-LENA simulation baseline

ns-3 version **ns-3.48**, 5G-LENA `nr` module version **v5.1**
(`5g-lena-v5.1.y`). Three validated experiment tracks, each run across the
full UE ladder **1 → 10 → 25 → 50 → 100 → 150 → 200**, seed **20260901**,
30 s simulated duration per run:

| Track | Directory | Scenario source |
|---|---|---|
| IDEAL channel, single-node gNB | `ns3_phase01/` | `source/ns3_scenarios/ue-scaling-study.cc` |
| CU-DU topology | `ns3_cudu_phase/` | `source/ns3_scenarios/cu-du-scaling-study.cc` |
| iperf-inspired / noise-augmented traffic | `ns3_cudu_phase_noise/` | `source/ns3_scenarios/cu-du-scaling-study-noise.cc` |

All 7 levels PASS (exit 0, 100% RRC registration) in all 3 tracks — see
`ns3_cudu_phase/BASELINE_DATA_INTEGRITY.md`.

### CU-DU topology experiment

Adds a separate CU node and DU node connected by a dedicated
point-to-point link, plus an EPC-style core. **This is a topological
representation, not a functional 3GPP F1 protocol implementation.**
5G-LENA's `nr` module has no F1AP; PHY/MAC/RLC/PDCP/RRC remain bundled on
the DU node. The F1 link carries a real, measured UDP heartbeat flow —
verified 299/299 packets delivered, 0 loss — but actual UE bearer traffic
does **not** traverse it; it transits the DU node's automatic S1-U tunnel
directly to the SGW/PGW (unavoidable without `nr`-module internals
surgery). See the header comment in `cu-du-scaling-study.cc` for full
detail.

### Noise/stagger experiment

Adds an **iperf-inspired / noise-augmented traffic model** — explicitly
**NOT real iperf3**. ns-3 UEs/gNB have no OS-level socket layer for a real
`iperf3` process to run against. The implementation is ns-3's
`OnOffApplication` with per-UE lognormal rate variation, per-class
packet-size distributions, and staggered application start offsets (all
with dedicated, documented RNG streams). See
`ns3_cudu_phase_noise/NOISE_MODEL.md` for the full model, including a
documented known interaction: mMTC's maximum start offset (30 s) equals
the entire simulation duration (30 s), so some mMTC UEs draw offsets that
leave them very little active transmission time — left as-is and
documented rather than changed, to keep the dataset reproducible.

## Important limitations and caveats

- **ns-3 reaching 200 UEs does NOT mean real OAI supports 200 UEs.** These
  are two independent, non-comparable measurement contexts. ns-3 is a
  discrete-event simulator with no real-time execution constraint; OAI's
  real, measured bottleneck on this host is CPU/real-time scheduling
  (`vrtsim`'s per-callback `O(N)` combining-loop cost), found to fail
  around ~15 actually-connected UEs in a separate experiment — nowhere
  near 200, and for an entirely different reason than anything ns-3
  measures. The two must never be merged, averaged, or cited as if they
  measured the same thing.
- **The ns-3 CU-DU link is a topological representation, not a functional
  3GPP F1 implementation.** See above.
- **The noise experiment uses an iperf-inspired / noise-augmented traffic
  model, not real iperf3.** See above.
- **PAIBO has not yet been implemented.** No PAIBO Result Type (bearer
  setup latency via a real Bearer Hint mechanism, DRB/RL-SDAP reduction,
  MAC-CE adaptation latency, BIP ML accuracy) exists in this repository.
  A separate, real-measured "bearer setup latency" number does exist for
  the ns-3 baseline (`source/ns3_scenarios/cu-du-bearer-latency-study.cc`,
  feeding the `Baseline_NonPAIBO_Ladder` sheet) — this measures 5G-LENA's
  own idealized RRC connection-establishment procedure, and is explicitly
  **not** a PAIBO Bearer Hint measurement.
- Only Scenario A (IDEAL channel: LOS-only path loss, no shadowing, no
  fading) has been run. No realistic/fading channel scenario exists yet.
- `PAIBO_Patent_Vartika.pptx` is marked **Samsung Confidential** by its own
  title slide and is excluded from this repository via `.gitignore` — it
  must never be committed or pushed.

## Repository layout

```
README.md                      -- this file
ASSIGNMENT_STATUS.md            -- requirement-by-requirement status
BASELINE_FREEZE.md              -- frozen-baseline manifest
BASELINE_REMAINING_GAPS.md      -- what's still open (Scenario B, etc.)
MEMORY_BUDGET_NOTE.md           -- real OAI memory/CPU measurements
KPI_AVAILABILITY_MATRIX.md / KPI_AVAILABILITY_NOTE.md / PAIBO_KPI_CROSSCHECK.md
instructions_should_be_followed.txt   -- original assignment text
source/
  oai_patches/                 -- copies of the 3 approved OAI modifications
  ns3_scenarios/                -- copies of the validated ns-3 scenario .cc files
  SOURCE_PROVENANCE.md          -- exact original paths + versions/commits
scripts/                        -- ladder driver scripts + KPI post-processing
ns3_phase01/                     -- IDEAL-channel ladder results
ns3_cudu_phase/                  -- CU-DU topology ladder results
ns3_cudu_phase_noise/            -- noise-augmented traffic ladder results
ns3_cudu_baseline_results.xlsx   -- consolidated CU-DU baseline workbook
baseline_comparison_summary.csv
baseline_plots/                  -- labeled "ns-3 / 5G-LENA BASELINE — NO PAIBO"
```

Large raw per-run ns-3 trace dumps (PHY/MAC control messages, path loss —
hundreds of MB per level) are excluded from git via `.gitignore`; they are
regeneratable by re-running the documented, seeded scenario source against
the documented ns-3/5G-LENA versions. The validated CSVs/xlsx/plots
already derived from them are what's kept as evidence in this repository.

## Recent additions

### Modeled MAC-CE adaptation measurement
- New experiment: `cu-du-macce-model-study.cc`
- Models MAC-CE-triggered adaptation as a 1-slot
  (0.5 ms) event at 30 kHz SCS
- Compared against measured RRC baseline (18–53 ms
  depending on UE count)
- Modeled saving: 97–99% across 1–200 UEs
- See `docs/macce_model.md` for full methodology
- Results in `results/ns3_macce_test/`
- Label throughout:
  "modeled_macce_next_slot_interval — NOT real OAI MAC-CE"

### Updated Excel workbook
- `results/PAIBO_Baseline_Results_v3.xlsx`
- Includes MAC-CE model sheet alongside existing KPIs

> **Step 4 (PAIBO) — PAIBO Attach Baseline Simulation (Sep 2026)**

# PAIBO Attach Baseline vs. Conventional Attach — ns-3 + 5G-LENA

**What this is:** an ns-3.48 / 5G-LENA v5.1 discrete-event simulation
comparing the conventional Initial Attach hop chain
(`../step4b_rrc_attach_study/`) against PAIBO's proposed Component 2 (Shadow
DRB / predictive RRCReconfiguration timing shift via a new
`RRCBearerHint` message). **`NrPointToPointEpcHelper` implements no real
NAS/NGAP/5GC stack, and no real BIP (Bearer Intent Predictor) ML model
exists anywhere in this repository.**

**BIP assumption: Oracle (perfect prediction).** Component 1 (the actual
BIP/BIV predictor) is modeled as always exactly correct — a 100% hit
rate, explicit upper bound, not a measured ML result. Components 3
(MAC-CE adaptation) and 4 (RL-based SDAP) are not implemented.

## Headline numbers (1-UE PoC, confirmed identical at every UE count 1–200)

| Metric | Conventional | PAIBO | Delta |
|---|---|---|---|
| Bearer setup latency | +0.4000 ms | -0.2000 ms | **0.6000 ms saved** |
| Signaling message count | 18 | 19 | net +1 |
| Core signaling latency | 1.8000 ms | 1.9500 ms | +0.1500 ms (BearerHint round-trip overhead) |

These are **constant across UE count** in the current model: the modeled
hop chain is a fixed per-UE offset applied once each UE's real RRC
connection completes, so it doesn't compound with UE count the way the
real, contended `rrcSetupLatencyMs` does (that part rises with UE count
identically in both scenarios — untouched by the PAIBO change).

## Why PAIBO's message count is higher but latency is lower

PAIBO adds two new hops (`RRCBearerHint` + its ack) but, because the
predictor is an oracle with no mismatch ever, collapses the conventional
baseline's `RRCReconfiguration` + `RRCReconfigurationComplete` pair into a
single one-way `DLInformationTransfer`. Net signaling: +2 −1 = **+1
message**. Net bearer-setup latency: the DRB becomes active
(`rrcBearerHintAckMs`) *before* `registrationCompleteMs` even fires,
which is what makes the headline latency number negative.

## Limitations (carried over honestly, not smoothed away)

1. Component 1 is an oracle, not a measurement — any claim beyond "under
   a perfect predictor, Component 2 alone saves 0.6ms and costs +1
   message" requires a real BIP/BIV model, which does not exist here.
2. The 0.6ms saving and +1 message count are constant across UE count in
   this model, by construction — not a claim that it would stay constant
   under a more elaborate load-scaling model.
3. `firstDataPacketTimeMs` is numerically identical to the conventional
   baseline at every UE count — expected, since UE application traffic
   timing is configured independently of this modeled signaling chain.
   PAIBO's benefit shows up in `bearerSetupLatencyMs`, not here.
4. No RR/PF/noise/MAC-CE scenario file was modified for this experiment.
   OAI was not touched.

**Status:** Simulation run and results generated locally; **now pushed to
this repository** (previously local-only at
`/home/ankit/ns3_paibo_attach_baseline_ladder/` and
`/opt/ns3/ns-3-dev/docs/paibo_attach_baseline_ns3.md`).

**Files in this folder:**
- `README.md` (this file)
- `paibo_attach_baseline_ns3.md` — full methodology (hop-by-hop table,
  measured-vs-modeled discipline, derivation of every KPI)
- `paibo_attach_baseline_ladder.csv`, `conventional_vs_paibo_comparison.csv`,
  `paibo_attach_baseline_ladder_summary.md`, `LADDER_STATUS.txt`
- `ue_1/` … `ue_200/` — per-UE-count run outputs
- `results/` — consolidated `PAIBO_Baseline_Results_v3.xlsx` and the
  modeled MAC-CE adaptation experiment (`ns3_macce_test/`), moved here
  from the repo root since both relate to PAIBO components measured/
  modeled in this simulation (MAC-CE is PAIBO Component 3)

Scenario source: `source/ns3_scenarios/paibo-attach-baseline-study.cc`.

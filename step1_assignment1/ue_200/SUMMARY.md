# SUMMARY — ns-3 / 5G-LENA UE-Scaling Study — Level: 200 UEs

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.**
**IT IS NOT REAL OAI CU-DU EXECUTION AND MUST NOT BE PRESENTED OR COMBINED AS IF IT
WERE OAI-MEASURED DATA.**

## Experiment identity
- Scenario program: contrib/nr/examples/ue-scaling-study.cc
- ns-3.48 ; 5G-LENA nr module v5.1 (5g-lena-v5.1.y); build at /opt/ns3/ns-3-dev

## Carrier configuration
- Target 189 PRB @ 30 kHz SCS, band n78 (~3.5 GHz); bandwidth 68.04 MHz, numerology 1.
  Actual RB count at runtime: 189 (no deviation).

## Channel ("IDEAL" analog)
- ThreeGpp RMa LOS path loss only, ShadowingEnabled=false, INIT_PROPAGATION only
  (no fading model attached) — see ue_1/SUMMARY.md for full rationale.

## Seed / determinism
- Seed 20260901 (RngSeedManager). Determinism verified at level 1.

## Architecture
- Single gNB cell, real RRC connection establishment, confirmed via
  NrGnbRrc::ConnectionEstablished trace.

## DEVIATION AT THIS LEVEL ONLY: reduced trace set (`--fullTraces=false`)
The first attempt at ueNum=200 with the full `NrHelper::EnableTraces()` set (as used
at all lower levels 1/10/25/50/100/150) was operationally impractical: after ~25
minutes of wall-clock runtime the PHY/MAC control-message and per-pair pathloss trace
files alone had already reached ~2 GB combined (`RxedUePhyCtrlMsgsTrace.txt` alone
1.22 GB, `DlPathlossTrace.txt` 700 MB) and the simulation had not finished; that run
was terminated as operationally infeasible within this investigation's time budget.
A second attempt using the same full trace set, run fully detached from the harness
(nohup+setsid+disown) also did not complete/produce output, for reasons that could not
be conclusively diagnosed (no crash/OOM evidence in `dmesg`; the process simply stopped
progressing) and was abandoned rather than retried indefinitely.

This third, successful attempt used a code path added specifically for this situation:
a `--fullTraces=false` command-line option (see `ue-scaling-study.cc`) that enables
only `EnableDlDataPhyTraces()` (per-UE SINR + per-TB MCS/size via `RxPacketTrace.txt`/
`DlDataSinr.txt`) and `EnableRlcE2eTraces()`/`EnablePdcpE2eTraces()` (RLC/PDCP delay),
while skipping the very high-volume PHY/MAC control-message traces and per-pair
pathloss traces, none of which map to a KPI required by this study. **All KPIs
required by this study (SINR, MCS, TB size, RLC/PDCP delay, FlowMonitor throughput/
loss/delay, RRC-connected count) were still fully collected at this level.** Only the
non-required supplementary traces (DCI/control-message dumps, per-pair pathloss) are
absent for this level only; they are present for all other levels (1/10/25/50/100/150).
This is a deliberate, documented deviation for feasibility, not a silent substitution.

## UE count: configured vs RRC-connected
- Configured: 200
- RRC-connected: 200 / 200

## Traffic: configured vs measured

| Class | UEs configured | Per-UE cap (bps) | Packet size (B) |
|---|---|---|---|
| mMTC | 80 | 3000 | 100 |
| Web | 30 | 133000 | 600 |
| Mobile | 30 | 166000 | 800 |
| VoD | 24 | 725000 | 1200 |
| Live | 26 | 478000 | 1200 |
| V2X | 10 | 99000 | 300 |

Measured (FlowMonitor, ue200_flowmonitor.xml): 200 flows total, one per UE. Zero flows
with rxBytes=0 — every UE received traffic.

## Per-UE / aggregate KPIs collected
- SINR (DL data): `DlDataSinr.txt` — present, ~4.0 MB, 200 UEs' worth of samples
- MCS/TB size/per-packet SINR: `RxPacketTrace.txt` — present, ~9.6 MB
- RLC/PDCP E2E summary stats: `NrDlRlcStatsE2E.txt`, `NrDlPdcpStatsE2E.txt` — present
- Per-UE PRB count: NOT AVAILABLE (see ../KPI_AVAILABILITY_NOTE.md), as at all levels
- PHY/MAC control-message traces, per-pair pathloss traces: NOT COLLECTED AT THIS
  LEVEL (see deviation note above) — present at all other levels

## Runtime (informational only — N/A as health gate)
- Simulated duration: 30 s
- Wall-clock duration: 1523.65 s (internal) / 1524.08 s (outer), i.e. ~25.4 minutes —
  note this is with the REDUCED trace set; the compute cost (scheduler/interference
  calculations) rather than trace I/O dominates runtime at this scale, so this figure
  is not directly comparable to the full-trace wall-clock figures at lower levels.
  No real-time constraint applies to this discrete-event simulator.

## Health/success gate (same definition as level 1, applied identically)
1. All configured UEs RRC connected
2. FlowMonitor nonzero rxBytes for every UE
3. No crash / exit code 0

## Result: PASS
- Gate 1: 200/200 — PASS
- Gate 2: 200/200 flows nonzero rxBytes — PASS
- Gate 3: exit code 0 — PASS

This is the highest level in the planned ladder (1/10/25/50/100/150/200); the ladder
completed in full with no failing level.

## Raw evidence file locations
- ue200_run_summary.tsv, ue200_traffic_config.tsv, ue200_flowmonitor.xml
- DlDataSinr.txt, RxPacketTrace.txt, NrDlRlcStatsE2E.txt, NrDlPdcpStatsE2E.txt,
  NrUlRlcStatsE2E.txt, NrUlPdcpStatsE2E.txt, all in this directory
- stdout.log, stderr.log, exit_status.txt

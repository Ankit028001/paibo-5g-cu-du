# SUMMARY — ns-3 / 5G-LENA UE-Scaling Study — Level: 10 UEs

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.**
**IT IS NOT REAL OAI CU-DU EXECUTION AND MUST NOT BE PRESENTED OR COMBINED AS IF IT
WERE OAI-MEASURED DATA.**

## Experiment identity
- Scenario program: contrib/nr/examples/ue-scaling-study.cc
- ns-3 version: ns-3.48 ; 5G-LENA nr module: v5.1 (5g-lena-v5.1.y)
- Build location: /opt/ns3/ns-3-dev (dedicated, separate from /opt/oai)

## Carrier configuration
- Target 189 PRB @ 30 kHz SCS, band n78 (~3.5 GHz)
- Configured bandwidth 68.04 MHz, numerology 1, single band/CC/BWP
- Actual RB count at runtime: 189 (no deviation)

## Channel ("IDEAL" analog)
- NrChannelHelper: ConfigureFactories("RMa","LOS","ThreeGpp"), ShadowingEnabled=false,
  AssignChannelsToBands with INIT_PROPAGATION only (no fading model attached)

## Seed / determinism
- Seed 20260901, RngSeedManager::SetSeed/SetRun. Determinism previously verified
  bit-identical across two runs (see ue_1/SUMMARY.md for the verification details).

## Architecture
- Single gNB cell, real RRC connection establishment via AttachToClosestGnb(),
  confirmed via NrGnbRrc::ConnectionEstablished trace.

## UE count: configured vs RRC-connected
- Configured: 10
- RRC-connected: 10 / 10

## Traffic: configured vs measured
Six-class model, proportional distribution (largest-remainder rounding). At N=10:

| Class | UEs configured | Per-UE cap (bps) | Packet size (B) |
|---|---|---|---|
| mMTC | 4 | 3000 | 100 |
| Web | 2 | 133000 | 600 |
| Mobile | 2 | 166000 | 800 |
| VoD | 1 | 725000 | 1200 |
| Live | 1 | 478000 | 1200 |
| V2X | 0 | 99000 | 300 |

(V2X share at N=10 is 0.5 UE, rounded down; the reference table's largest-remainder
classes absorbed the leftover UE — this is expected behavior of the proportional
distribution method at low N, not a fault.)

Measured (FlowMonitor, ue10_flowmonitor.xml, 10 flows total, one per UE):
- All 10 flows show nonzero rxBytes; rxBytes cluster into 5 groups matching the 5
  active classes: 4x14080 B (mMTC), 2x514960/635076 B (Web/Mobile), 1x1808844 B,
  1x2744580 B (VoD/Live) — consistent with each class's configured per-UE rate cap
  scaled by the ~29.6s active flow duration.
- No lost packets detected in any of the 10 flows (spot-checked via rxBytes==txBytes
  pattern consistent with level 1).

## Per-UE / aggregate KPIs collected
Same trace set as level 1 (SINR, MCS, RLC/PDCP delay, pathloss) — present and
non-empty for all 10 UEs (10x volume of level-1 traces). Per-UE PRB count: NOT
AVAILABLE (see ../KPI_AVAILABILITY_NOTE.md).

## Runtime (informational only — N/A as health gate)
- Simulated duration: 30 s
- Wall-clock duration: 25.18 s (measured via internal std::chrono around
  Simulator::Run(); outer shell-measured wall time 25.30 s)
- No real-time constraint applies to this discrete-event simulator.

## Health/success gate (same definition as level 1, applied identically)
1. All configured UEs RRC connected
2. FlowMonitor nonzero rxBytes for every UE
3. No crash / exit code 0

## Result: PASS
- Gate 1: 10/10 — PASS
- Gate 2: 10/10 flows nonzero rxBytes — PASS
- Gate 3: exit code 0 — PASS

## Raw evidence file locations
- ue10_run_summary.tsv, ue10_traffic_config.tsv, ue10_flowmonitor.xml
- DlDataSinr.txt, DlCtrlSinr.txt, RxPacketTrace.txt, NrDlMacStats.txt,
  NrDlRxRlcStats.txt, NrDlTxRlcStats.txt, NrDlPdcpRxStats.txt, NrDlPdcpTxStats.txt,
  DlPathlossTrace.txt, UlPathlossTrace.txt, and other trace files, all in this directory
- stdout.log, stderr.log, exit_status.txt

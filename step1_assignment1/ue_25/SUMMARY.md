# SUMMARY — ns-3 / 5G-LENA UE-Scaling Study — Level: 25 UEs

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.**
**IT IS NOT REAL OAI CU-DU EXECUTION AND MUST NOT BE PRESENTED OR COMBINED AS IF IT
WERE OAI-MEASURED DATA.**

## Experiment identity
- Scenario program: contrib/nr/examples/ue-scaling-study.cc
- ns-3.48 ; 5G-LENA nr module v5.1 (5g-lena-v5.1.y); build at /opt/ns3/ns-3-dev

## Carrier configuration
- Target 189 PRB @ 30 kHz SCS, band n78 (~3.5 GHz); configured bandwidth 68.04 MHz,
  numerology 1. Actual RB count at runtime: 189 (no deviation).

## Channel ("IDEAL" analog)
- ThreeGpp RMa LOS path loss only, ShadowingEnabled=false, INIT_PROPAGATION only
  (no fading model attached) — see ue_1/SUMMARY.md for full rationale.

## Seed / determinism
- Seed 20260901 (RngSeedManager). Determinism verified at level 1 (bit-identical
  FlowMonitor XML across repeat runs); same code path used at all levels.

## Architecture
- Single gNB cell, real RRC connection establishment, confirmed via
  NrGnbRrc::ConnectionEstablished trace.

## UE count: configured vs RRC-connected
- Configured: 25
- RRC-connected: 25 / 25

## Traffic: configured vs measured

| Class | UEs configured | Per-UE cap (bps) | Packet size (B) |
|---|---|---|---|
| mMTC | 10 | 3000 | 100 |
| Web | 4 | 133000 | 600 |
| Mobile | 4 | 166000 | 800 |
| VoD | 3 | 725000 | 1200 |
| Live | 3 | 478000 | 1200 |
| V2X | 1 | 99000 | 300 |

Measured (FlowMonitor, ue25_flowmonitor.xml): 25 flows total, one per UE. Zero flows
with rxBytes=0 (checked via grep across the full XML) — every UE received traffic.

## Per-UE / aggregate KPIs collected
Same trace set as lower levels (SINR, MCS, RLC/PDCP delay, pathloss), scaled to 25
UEs' worth of packets — present and non-empty. Per-UE PRB count: NOT AVAILABLE (see
../KPI_AVAILABILITY_NOTE.md).

## Runtime (informational only — N/A as health gate)
- Simulated duration: 30 s
- Wall-clock duration: 82.05 s (internal), 82.19 s (outer shell) — up from 25.2 s at
  N=10, consistent with the expected super-linear cost growth of a multi-UE scheduler/
  interference simulation as UE count increases. No real-time constraint applies.

## Health/success gate (same definition as level 1)
1. All configured UEs RRC connected
2. FlowMonitor nonzero rxBytes for every UE
3. No crash / exit code 0

## Result: PASS
- Gate 1: 25/25 — PASS
- Gate 2: 25/25 flows nonzero rxBytes — PASS
- Gate 3: exit code 0 — PASS

## Raw evidence file locations
- ue25_run_summary.tsv, ue25_traffic_config.tsv, ue25_flowmonitor.xml
- DlDataSinr.txt, DlCtrlSinr.txt, RxPacketTrace.txt, NrDlMacStats.txt,
  NrDlRxRlcStats.txt, NrDlTxRlcStats.txt, NrDlPdcpRxStats.txt, NrDlPdcpTxStats.txt,
  DlPathlossTrace.txt, UlPathlossTrace.txt, and other trace files, all in this directory
- stdout.log, stderr.log, exit_status.txt

# SUMMARY — ns-3 / 5G-LENA UE-Scaling Study — Level: 50 UEs

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

## UE count: configured vs RRC-connected
- Configured: 50
- RRC-connected: 50 / 50

## Traffic: configured vs measured

| Class | UEs configured | Per-UE cap (bps) | Packet size (B) |
|---|---|---|---|
| mMTC | 20 | 3000 | 100 |
| Web | 8 | 133000 | 600 |
| Mobile | 8 | 166000 | 800 |
| VoD | 6 | 725000 | 1200 |
| Live | 6 | 478000 | 1200 |
| V2X | 2 | 99000 | 300 |

Measured (FlowMonitor, ue50_flowmonitor.xml): 50 flows total, one per UE. Zero flows
with rxBytes=0 — every UE received traffic.

## Per-UE / aggregate KPIs collected
Same trace set as lower levels — present and non-empty for all 50 UEs. Per-UE PRB
count: NOT AVAILABLE (see ../KPI_AVAILABILITY_NOTE.md).

## Runtime (informational only — N/A as health gate)
- Simulated duration: 30 s
- Wall-clock duration: 197.73 s (internal) / 197.90 s (outer) — continuing the
  super-linear wall-clock growth trend (10 UE: 25.2s, 25 UE: 82.1s, 50 UE: 197.7s).
  This is purely a discrete-event simulation compute-cost trend and has no bearing on
  a "real-time" pass/fail gate, which does not apply to ns-3.

## Health/success gate (same definition as level 1)
1. All configured UEs RRC connected
2. FlowMonitor nonzero rxBytes for every UE
3. No crash / exit code 0

## Result: PASS
- Gate 1: 50/50 — PASS
- Gate 2: 50/50 flows nonzero rxBytes — PASS
- Gate 3: exit code 0 — PASS

## Raw evidence file locations
- ue50_run_summary.tsv, ue50_traffic_config.tsv, ue50_flowmonitor.xml
- DlDataSinr.txt, DlCtrlSinr.txt, RxPacketTrace.txt, NrDlMacStats.txt,
  NrDlRxRlcStats.txt, NrDlTxRlcStats.txt, NrDlPdcpRxStats.txt, NrDlPdcpTxStats.txt,
  DlPathlossTrace.txt, UlPathlossTrace.txt, and other trace files, all in this directory
- stdout.log, stderr.log, exit_status.txt

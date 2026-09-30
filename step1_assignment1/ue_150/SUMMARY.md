# SUMMARY — ns-3 / 5G-LENA UE-Scaling Study — Level: 150 UEs

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
- Configured: 150
- RRC-connected: 150 / 150

## Traffic: configured vs measured

| Class | UEs configured | Per-UE cap (bps) | Packet size (B) |
|---|---|---|---|
| mMTC | 60 | 3000 | 100 |
| Web | 23 | 133000 | 600 |
| Mobile | 23 | 166000 | 800 |
| VoD | 18 | 725000 | 1200 |
| Live | 19 | 478000 | 1200 |
| V2X | 7 | 99000 | 300 |

Measured (FlowMonitor, ue150_flowmonitor.xml): 150 flows total, one per UE. Zero flows
with rxBytes=0 — every UE received traffic.

## Per-UE / aggregate KPIs collected
Same trace set as lower levels — present and non-empty for all 150 UEs. Per-UE PRB
count: NOT AVAILABLE (see ../KPI_AVAILABILITY_NOTE.md).

## Runtime (informational only — N/A as health gate)
- Simulated duration: 30 s
- Wall-clock duration: 1182.12 s (internal) / 1182.47 s (outer), i.e. ~19.7 minutes for
  150 UEs — continuing the super-linear wall-clock cost trend (10:25.2s, 25:82.1s,
  50:197.7s, 100:554.7s, 150:1182.1s). Purely a discrete-event simulation compute-cost
  trend on this 44-core host; no bearing on a "real-time" pass/fail gate, which does
  not apply to ns-3.

## Health/success gate (same definition as level 1)
1. All configured UEs RRC connected
2. FlowMonitor nonzero rxBytes for every UE
3. No crash / exit code 0

## Result: PASS
- Gate 1: 150/150 — PASS
- Gate 2: 150/150 flows nonzero rxBytes — PASS
- Gate 3: exit code 0 — PASS

## Raw evidence file locations
- ue150_run_summary.tsv, ue150_traffic_config.tsv, ue150_flowmonitor.xml
- DlDataSinr.txt, DlCtrlSinr.txt, RxPacketTrace.txt, NrDlMacStats.txt,
  NrDlRxRlcStats.txt, NrDlTxRlcStats.txt, NrDlPdcpRxStats.txt, NrDlPdcpTxStats.txt,
  DlPathlossTrace.txt, UlPathlossTrace.txt, and other trace files, all in this directory
- stdout.log, stderr.log, exit_status.txt

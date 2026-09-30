# SUMMARY — ns-3 / 5G-LENA UE-Scaling Study — Level: 1 UE

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.**
**IT IS NOT REAL OAI CU-DU EXECUTION AND MUST NOT BE PRESENTED OR COMBINED AS IF IT
WERE OAI-MEASURED DATA.** This is a separate simulation study answering a different
question (protocol/network-layer scaling behavior in an idealized discrete-event model)
than the real OAI vrtsim/rfsimulator experiments in this investigation.

## Experiment identity
- Scenario program: contrib/nr/examples/ue-scaling-study.cc (custom, based on stock
  5G-LENA cttc-nr-demo.cc)
- ns-3 version: ns-3.48 (tag ns-3.48, gitlab.com/nsnam/ns-3-dev)
- 5G-LENA nr module version: v5.1 (branch 5g-lena-v5.1.y, gitlab.com/cttc-lena/nr)
  - confirmed as the current stable pairing per the nr module's own RELEASE_NOTES.md
  (NR-v5.1, August 6 2026, requires ns-3.48; NR-v5.2 was "under development"/unreleased
  at time of this study)
- Build location: /opt/ns3/ns-3-dev (dedicated, separate from /opt/oai)

## Carrier configuration
- Target: 189 PRB, 30 kHz SCS, band n78 (~3.5 GHz), matching the OAI experiment carrier
- Configured: centralFrequency=3.5 GHz, bandwidth=68.04 MHz (189 * 12 * 30 kHz),
  numerology=1 (30 kHz SCS), single band/single CC/single BWP
- Actual RB count reported by the module at runtime: 189 (see ue1_run_summary.tsv,
  field actualRbCount) - no deviation from the 189 PRB target was needed; the
  requested bandwidth mapped exactly onto 189 usable RBs at numerology 1.

## Channel configuration ("IDEAL" analog)
- OAI target: IDEAL channel (chanmod=0, no added noise/multipath)
- 5G-LENA closest analog selected: NrChannelHelper configured with
  ConfigureFactories("RMa", "LOS", "ThreeGpp"), ShadowingEnabled=false, and channel
  assigned via AssignChannelsToBands(..., NrChannelHelper::INIT_PROPAGATION) -
  i.e. only the deterministic ThreeGpp RMa LOS path-loss model is attached; the
  fast-fading/multipath spectrum model is deliberately NOT attached (no
  INIT_FADING flag). This yields a deterministic, distance-based path loss with no
  shadowing and no fast fading - the closest available 5G-LENA analog to OAI's IDEAL
  channel. Evidence: per-packet SINR in RxPacketTrace.txt is stable/deterministic
  (~63.6 dB at 10 m gNB-UE distance) and MCS converges to the maximum (28).

## Seed / determinism
- Seed: 20260901, applied via RngSeedManager::SetSeed(20260901) +
  RngSeedManager::SetRun(1) in the scenario program
- Determinism verification: two independent runs at ueNum=5/simTime=5 with identical
  arguments produced bit-identical FlowMonitor XML output (md5
  b2a62f3fcfa3d5935907f5117851d3f0 on both runs) and identical run-summary fields
  (excluding wall-clock time, which is expected to vary). This confirms genuine RNG
  determinism in ns-3, unlike the OAI vrtsim runs in this investigation.

## Architecture
- Single gNB cell (GridScenarioHelper, 1 row x 1 column, single sector)
- Real 5G-LENA NR RRC stack: UEs perform actual RRC connection establishment via
  NrHelper::AttachToClosestGnb(); connection completion is confirmed via the
  NrGnbRrc::ConnectionEstablished trace source (not just NetDevice object creation)

## UE count: configured vs RRC-connected
- Configured: 1
- RRC-connected (from ConnectionEstablished trace count): 1 / 1

## Traffic: configured vs measured
Six-class model, proportional distribution per OAI phase2 100-UE reference table
(/opt/oai/openairinterface5g/phase2/20260903_100ue_vrtsim_cudu_189prb/traffic/traffic_model.md,
read-only reference; OAI tree not modified). At ueNum=1, only the largest class (mMTC)
receives a UE (proportional rounding, largest-remainder method).

| Class | UEs configured | Per-UE cap (bps) | Packet size (B) |
|---|---|---|---|
| mMTC | 1 | 3000 | 100 |
| Web | 0 | 133000 | 600 |
| Mobile | 0 | 166000 | 800 |
| VoD | 0 | 725000 | 1200 |
| Live | 0 | 478000 | 1200 |
| V2X | 0 | 99000 | 300 |

Measured (FlowMonitor, ue1_flowmonitor.xml, single flow = the one mMTC UE):
- txBytes = rxBytes = 14080 bytes over the flow duration (packets not dropped)
- txPackets = rxPackets = 110, lostPackets = 0
- Measured throughput ~= 14080*8 / 29.6s ~= 3.81 kbps (vs 3 kbps configured cap - within
  expected range given discrete packetization at 100 B/packet)
- Mean delay ~= 1.5 ms, mean jitter ~= 0.22 ms (computed from delaySum/jitterSum divided by
  rxPackets in the XML)

## Per-UE / aggregate KPIs collected
- SINR (DL data): DlDataSinr.txt - present, stable (~63.6 dB), consistent with the
  IDEAL-analog channel
- MCS: RxPacketTrace.txt - present, ramps from 0 to the maximum (28) as AMC converges
- Per-UE PRB count: NOT AVAILABLE as a direct trace column (see
  ../KPI_AVAILABILITY_NOTE.md)
- Aggregate cell throughput: derived by summing FlowMonitor rxBytes across UEs (at
  ueNum=1 this equals the single flow above)
- RLC/PDCP per-PDU delay: NrDlRxRlcStats.txt, NrDlPdcpRxStats.txt - present

## Runtime (informational only - N/A as a health gate for this simulator)
- Simulated duration: 30 s
- Wall-clock duration: 35.46 s
- This simulator has no real-time execution constraint. Wall-clock-vs-simulated time
  is reported for information only and is explicitly NOT a pass/fail criterion here -
  unlike the OAI vrtsim investigation's real-time TX/RX-late gate, which does not apply
  to a discrete-event simulator.

## Health/success gate (defined before running)
1. All configured UEs reach RRC connected (via ConnectionEstablished trace)
2. FlowMonitor reports non-zero delivered (rx) bytes for every configured UE's flow
3. No ns-3 fatal errors/crashes (process exit code 0)

## Result: PASS
- Gate 1: 1/1 RRC connected - PASS
- Gate 2: rxBytes=14080 > 0 for the one flow - PASS
- Gate 3: exit code 0, no crash - PASS

## Raw evidence file locations
- ue1_run_summary.tsv, ue1_traffic_config.tsv, ue1_flowmonitor.xml
- DlDataSinr.txt, DlCtrlSinr.txt, RxPacketTrace.txt, NrDlMacStats.txt,
  NrDlRxRlcStats.txt, NrDlTxRlcStats.txt, NrDlPdcpRxStats.txt,
  NrDlPdcpTxStats.txt, DlPathlossTrace.txt, UlPathlossTrace.txt, and other
  Rxed/Txed*CtrlMsgsTrace.txt files, all in this directory
- stdout.log, stderr.log, exit_status.txt

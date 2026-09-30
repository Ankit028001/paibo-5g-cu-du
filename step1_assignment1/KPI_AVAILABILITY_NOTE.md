# KPI Availability Note — ns-3 / 5G-LENA UE-Scaling Study

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION STUDY. IT IS NOT REAL OAI CU-DU
EXECUTION AND MUST NOT BE PRESENTED OR COMBINED AS IF IT WERE OAI-MEASURED DATA.**

This note documents exactly what KPIs were found to be available in this ns-3.48 +
5G-LENA nr module v5.1 build, where they come from, and what format they use. It was
produced by inspecting the module's own example scripts, helper source, and trace
sink implementations (not assumed from OAI KPI naming conventions).

## Sources inspected
- `contrib/nr/examples/cttc-nr-demo.cc` (base example, FlowMonitor usage pattern)
- `contrib/nr/helper/nr-helper.cc` (`NrHelper::EnableTraces()` and its sub-functions)
- `contrib/nr/helper/nr-phy-rx-trace.h/.cc` (PHY trace sink implementation, file formats)
- `contrib/nr/model/nr-gnb-rrc.cc` (RRC `ConnectionEstablished`/`NewUeContext` trace sources)
- `contrib/nr/helper/nr-channel-helper.h/.cc` (channel/propagation configuration API)
- Actual trace file output from a live smoke run (`/tmp/ns3_direct_test/*`, ueNum=3)

## KPIs confirmed AVAILABLE

| KPI | Source | Format / file |
|---|---|---|
| Per-UE / per-flow throughput (Tx & Rx bytes, Mbps) | ns-3 `FlowMonitor` (`FlowMonitorHelper`) | `<tag>_flowmonitor.xml`, one `<Flow>` element per 5-tuple |
| Per-UE / per-flow packet loss (tx vs rx packet/byte counts, `lostPackets`) | `FlowMonitor` | same XML |
| Per-UE / per-flow mean delay, jitter, delay/jitter histograms | `FlowMonitor` | same XML |
| Aggregate cell throughput | Derived by summing `FlowMonitor` per-flow rxBytes | computed in SUMMARY.md, not a native single trace |
| Per-UE downlink SINR (data), dB | `NrHelper::EnableDlDataPhyTraces()` -> `NrPhyRxTrace::DlDataSinrCallback` | `DlDataSinr.txt` (tab-separated: Time, CellId, RNTI, BWPId, SINR(dB)) |
| Per-UE downlink SINR (control), dB | `NrHelper::EnableDlCtrlPhyTraces()` | `DlCtrlSinr.txt`, same columns |
| Per-transport-block MCS, TB size, rank, RV, per-packet SINR, CQI, corruption/TBler flag | `NrHelper::EnableDlDataPhyTraces()`/`EnableUlPhyTraces()` -> `RxPacketTraceUe`/gNB callback | `RxPacketTrace.txt` (columns: Time, direction, frame, subF, slot, 1stSym, nSymbol, cellId, bwpId, rnti, tbSize, mcs, rank, rv, SINR(dB), CQI, corrupt, TBler) - verified live: MCS ramps 0->28 as AMC converges under the IDEAL-analog channel |
| MAC scheduling record (MCS, symbols allocated, HARQ id, NDI, RV per grant) | `NrHelper::EnableDlMacSchedTraces()`/`EnableUlMacSchedTraces()` | `NrDlMacStats.txt` / `NrUlMacStats.txt` (per-grant row; PRB count derivable from `numSym` + RBG config, not a direct PRB column) |
| Per-UE RLC-layer per-PDU delay, packet size | `NrHelper::EnableRlcE2eTraces()` | `NrDlRxRlcStats.txt` / `NrDlTxRlcStats.txt` (time, cellId, rnti, lcid, packetSize, delay(s)) |
| Per-UE RLC end-to-end summary stats | `NrHelper::EnableRlcSimpleTraces()` | `NrDlRlcStatsE2E.txt` |
| Per-UE PDCP-layer per-PDU delay, packet size | `NrHelper::EnablePdcpE2eTraces()` | `NrDlPdcpRxStats.txt` / `NrDlPdcpTxStats.txt` |
| Per-UE PDCP end-to-end summary stats | `NrHelper::EnablePdcpSimpleTraces()` | `NrDlPdcpStatsE2E.txt` |
| Path loss per UE (DL/UL), dB | `NrHelper::EnablePathlossTraces()` | `DlPathlossTrace.txt` / `UlPathlossTrace.txt` |
| gNB/UE MAC and PHY control-message traces (DCI, etc.) | `EnableGnbPhyCtrlMsgsTraces()`, `EnableUePhyCtrlMsgsTraces()`, `EnableGnbMacCtrlMsgsTraces()`, `EnableUeMacCtrlMsgsTraces()` | `Rxed/TxedGnbPhyCtrlMsgsTrace.txt`, `RxedUePhyDlDciTrace.txt`, etc. |
| Actual RRC-connected UE count (not just device object creation) | `NrGnbRrc` trace source `ConnectionEstablished` (fired on real RRC connection setup completion), hooked via `Config::ConnectWithoutContext` in `ue-scaling-study.cc` | `<tag>_run_summary.tsv`, field `rrcConnectedCount` |
| Configured vs. measured traffic rate per class | Configured: `<tag>_traffic_config.tsv` (written by the scenario script from the six-class model); Measured: `FlowMonitor` XML per-flow rxBytes, cross-referenced by port range | two separate files, manually joined in each level's SUMMARY.md |
| Wall-clock vs. simulated runtime | `std::chrono` around `Simulator::Run()`, written by the scenario script | `<tag>_run_summary.tsv`, fields `wallClockSeconds` / `simulatedSeconds` -- **informational only; ns-3 is a discrete-event simulator with no real-time execution constraint, so this is explicitly N/A as a pass/fail gate (unlike the OAI vrtsim real-time TX/RX-late gate, which does not apply to a non-real-time simulator)** |

## KPIs explicitly NOT AVAILABLE in this build/module (as configured)

- **Per-UE PRB (physical resource block) count directly as a single column** -- NOT AVAILABLE
  as a native trace field. `NrDlMacStats.txt` records `numSym` (OFDM symbols) and MCS per
  grant; deriving an exact PRB count per UE requires additional postprocessing against the
  resource-block-group/numerology configuration, which was not implemented in this pass
  (only PHY-level TB size + MCS + SINR were reported as-is).
- **Direct 5G-LENA "aggregate cell throughput" single trace source** -- NOT AVAILABLE as a
  single built-in metric; it is a derived sum over per-UE `FlowMonitor` entries.
- **Any real-time execution / TX-RX-late / real-time factor gate** -- NOT APPLICABLE. This
  is a discrete-event simulator; there is no analog to the OAI vrtsim real-time constraint.
  Wall-clock-vs-simulated-time is reported as an informational figure only, per the task
  instructions, and must not be conflated with the OAI real-time gate.
- **NrRadioEnvironmentMapHelper (REM) output** -- available in the module (see
  `rem-example.cc`/`rem-beam-example.cc`) but NOT used/generated in this study; it produces
  spatial SINR/coverage maps, not per-UE time-series KPIs, and was out of scope for this
  UE-count scaling study.

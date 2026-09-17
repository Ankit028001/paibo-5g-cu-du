# Standard 3GPP Attach Baseline — ns-3 + 5G-LENA (1-UE Proof of Concept)

**THIS IS AN ns-3.48 / 5G-LENA v5.1 DISCRETE-EVENT SIMULATION. `NrPointToPointEpcHelper`
implements an LTE-EPC-style core with no NAS/NGAP/PFCP stack. There is no real 5G SA
Registration Request/Accept, no real PDU Session Establishment, and no real PDU Session
Resource Setup procedure running in this simulator.** This document reports the results of the
1-UE proof-of-concept run only. No 1–200 UE ladder was run. No PAIBO variant was implemented.

## Update (this revision): first-data-packet KPI added

The original version of this baseline had no first-data-packet KPI — the timeline CSV stopped
at the MODELED `dataReadyMs` chain. This revision adds a genuinely MEASURED
`firstDataPacketTimeMs` / `attachToFirstDataPacketLatencyMs` pair, read directly from
`FlowMonitor`'s own recorded `timeFirstRxPacket` for each UE's application flow (joined to the
UE's IMSI by matching the flow's destination IP/port against the UE's assigned address and
application port — see `standard-attach-baseline-study.cc`, post-`Simulator::Run()` join block).
**The existing modeled hop chain, `--hopDelayMs`, and the measured RRC setup latency are
completely unchanged by this revision** — this was purely additive.

## What is MEASURED vs MODELED (updated)

**MEASURED (real ns-3 discrete events):**
- `attachStartMs` — `Simulator::Now()` captured immediately before
  `nrHelper->AttachToClosestGnb(...)` (batch-level; with 1 UE this is not a limitation).
- `rrcSetupCompleteMs` / `rrcConnectedTimeMs`(equivalent) — `NrGnbRrc::ConnectionEstablished`
  event, the real simulated RRC-connection-setup completion time. Diagram's "Till
  RRCSetupComplete (Registration Request)" step.
- `rrcSetupLatencyMs = rrcSetupCompleteMs - attachStartMs` — real simulated RRC/MAC/PHY
  procedure duration.
- **`firstDataPacketTimeMs`** — FlowMonitor's actual recorded `timeFirstRxPacket` for the UE's
  application UDP flow (remoteHost → UE). This is a real ns-3 packet-reception event, not
  derived from or related to the modeled hop chain.
- **`attachToFirstDataPacketLatencyMs = firstDataPacketTimeMs - attachStartMs`** — the real
  elapsed simulated time from attach start to the first application packet actually being
  received by the UE.

**MODELED (synthetic scaffold, 18 fixed hops of `--hopDelayMs` each, anchored at
`rrcSetupCompleteMs`):** `initialUeMessageMs`, `authRequestMs`, `authResponseMs`,
`securityModeCommandNasMs`, `securityModeCompleteNasMs`, `initialContextSetupRequestMs`,
`securityModeCommandAsMs`, `securityModeCompleteAsMs`, `ueCapabilityEnquiryMs`,
`ueCapabilityInformationMs`, `initialContextSetupResponseMs`, `registrationAcceptMs`,
`registrationCompleteMs`, `pduSessionEstablishmentRequestMs`,
`pduSessionResourceSetupRequestMs`, `rrcReconfigurationDrbMs`, `rrcReconfigurationCompleteMs`,
`pduSessionResourceSetupResponseMs`, `dataReadyMs`, and the two KPIs derived purely from that
chain: `coreSignalingLatencyMs` and `totalAttachToDataLatencyMs`.

### A. RRC setup latency is a measured radio/RRC event
`rrcSetupLatencyMs` (18.0357 ms in this run) comes entirely from ns-3's real, simulated
random-access + RRC-connection-setup procedure (`NrGnbRrc::ConnectionEstablished`). It reflects
actual PHY/MAC/RRC simulated behavior, not a modeled constant.

### B. firstDataPacketTimeMs is a measured FlowMonitor application-flow event
It is read directly from `FlowMonitor::GetFlowStats()`'s `timeFirstRxPacket` field for the flow
matching the UE's IP address and application port (UDP, destination port 20000 in this run),
verified in this run against the raw `attach1_flowmonitor.xml` (flow id 2,
`destinationAddress="7.0.0.2"`, `destinationPort="20000"`, `protocol="17"`,
`timeFirstRxPacket="+6.68279e+08ns"` = 668.279 ms) — an independent re-parse of the XML
confirms this exact value, not just the code's own computed number.

### C. attachToFirstDataPacketLatencyMs includes the actual time until the first application packet is received
`attachToFirstDataPacketLatencyMs = firstDataPacketTimeMs - attachStartMs = 668.279 - 0 =
668.279 ms` in this run. This is the real, measured, end-to-end time from attach start to the
UE actually receiving its first application-layer packet — it is not a modeled figure.

### D. dataReadyMs / totalAttachToDataLatencyMs is a modeled attach timeline
`dataReadyMs` (19.8357 ms) and `totalAttachToDataLatencyMs` (19.8357 ms, MODELED) must **never**
be described as the measured first-data latency. They mark only the end of the synthetic
18-hop signaling chain, not any real packet event.

### E. The first application packet occurs substantially later than modeled dataReadyMs
In this run: modeled `dataReadyMs` = 19.8357 ms vs. measured `firstDataPacketTimeMs` = 668.279
ms — a ~650 ms gap. This is expected and not a bug: `udpAppStartTime` (400 ms) plus the
UE-side application's own On/Off scheduling and first-packet transmission/propagation time are
entirely independent of, and not synchronized with, the modeled signaling chain's timing. The
modeled chain answers "when would signaling say the bearer is ready"; the measured KPI answers
"when did a real packet actually arrive" — these are different questions with different
timescales in this configuration and should not be conflated or compared as if measuring the
same thing.

### F. Current model still does not implement actual NAS/NGAP/5GC signaling
Adding the first-data-packet KPI does not change this. `NrPointToPointEpcHelper` still has no
NAS/NGAP/PFCP stack; the 18 MODELED hops are still a synthetic scaffold, not real signaling.
This revision only adds one additional genuinely MEASURED (not modeled) KPI alongside it.

## Exact simulation configuration (this run) — unchanged from the previous revision

| Parameter | Value |
|---|---|
| Scenario binary | `ns3-dev-standard-attach-baseline-study-default` |
| `--ueNum` | 1 |
| `--simTime` | 10 s |
| `--hopDelayMs` | 0.1 ms (default; unchanged; also applied to real `S1uLinkDelay`) |
| `--fullTraces` | true |
| `--rngSeed` / `--rngRun` | 20260901 / 1 (default) |
| `--simTag` | attach1 |
| `--outputDir` | `/home/ankit/ns3_standard_attach_baseline/ue_1` (path note: `/root/...` not writable by build user; unchanged from previous run) |

## Build

```
cd /opt/ns3/ns-3-dev
./ns3 build standard-attach-baseline-study
```
Target/executable (confirmed, unchanged): `/opt/ns3/ns-3-dev/build/contrib/nr/examples/ns3-dev-standard-attach-baseline-study-default`.
Rebuild after this revision: **succeeded**, 3/3 build steps (incremental), **zero warnings, zero errors** from the modified file.

## Run command (actual)

```
LD_LIBRARY_PATH=/opt/ns3/ns-3-dev/build/lib \
  /opt/ns3/ns-3-dev/build/contrib/nr/examples/ns3-dev-standard-attach-baseline-study-default \
  --ueNum=1 --simTime=10 \
  --outputDir=/home/ankit/ns3_standard_attach_baseline/ue_1 \
  --simTag=attach1 --fullTraces=true
```
Exit code: **0**.

## Results — `attach1_attach_timeline.csv` (exactly 1 data row, verified)

```
imsi,cellId,rnti,attachStartMs,rrcSetupCompleteMs,initialUeMessageMs,authRequestMs,authResponseMs,securityModeCommandNasMs,securityModeCompleteNasMs,initialContextSetupRequestMs,securityModeCommandAsMs,securityModeCompleteAsMs,ueCapabilityEnquiryMs,ueCapabilityInformationMs,initialContextSetupResponseMs,registrationAcceptMs,registrationCompleteMs,pduSessionEstablishmentRequestMs,pduSessionResourceSetupRequestMs,rrcReconfigurationDrbMs,rrcReconfigurationCompleteMs,pduSessionResourceSetupResponseMs,dataReadyMs,rrcSetupLatencyMs,firstDataPacketTimeMs,attachToFirstDataPacketLatencyMs,coreSignalingLatencyMs,totalAttachToDataLatencyMs
1,1,1,0,18.0357,18.1357,18.2357,18.3357,18.4357,18.5357,18.6357,18.7357,18.8357,18.9357,19.0357,19.1357,19.2357,19.3357,19.4357,19.5357,19.6357,19.7357,19.8357,19.8357,18.0357,668.279,668.279,1.8,19.8357
```

## Results — `attach1_run_summary.tsv`

```
metric	value
configuredUeCount	1
rrcConnectedCount	1
modeledHopDelayMs	0.1
meanRrcSetupLatencyMs	18.0357
firstDataPacketObservedCountMEASURED	1
meanFirstDataPacketTimeMsMEASURED	668.279
meanAttachToFirstDataPacketLatencyMsMEASURED	668.279
meanCoreSignalingLatencyMsMODELED	1.8
meanTotalAttachToDataLatencyMsMODELED	19.8357
simulatedSeconds	10
wallClockSeconds	0.752403
rngSeed	20260901
rngRun	1
```

## Independent XML verification

Re-parsed `attach1_flowmonitor.xml` directly with `grep` (not assumed from the earlier report):
```
timeFirstRxPacket="+1.001e+08ns"   <- flowId=1, F1 heartbeat flow (DU->CU, port 9999), irrelevant to UE data
timeFirstRxPacket="+6.68279e+08ns" <- flowId=2, UE application flow (dest 7.0.0.2:20000, UDP)
```
`6.68279e+08 ns = 668.279 ms`, confirmed identical to the value the scenario code extracted and
wrote to the CSV. The join logic correctly selected flow 2 (the real UE traffic flow) and not
flow 1 (the unrelated F1 heartbeat flow).

## Consistency checks (unchanged fields)

- `rrcSetupLatencyMs = 18.0357 ms` — identical to the previous (pre-fix) run.
- `coreSignalingLatencyMs = 1.8 ms = 18 hops x 0.1 ms/hop` — identical, hop model untouched.
- `totalAttachToDataLatencyMs = 19.8357 ms = 18.0357 + 1.8` — identical.
- `dataReadyMs = 19.8357 ms` — identical to the previous run (simulation configuration
  unchanged).
- `firstDataPacketTimeMs (668.279) >= attachStartMs (0)` — holds.
- All timestamps are `Simulator::Now()`/`FlowMonitor`-simulation-time based; wall-clock time
  (`wallClockSeconds=0.752`) remains reported separately and on an unrelated scale.

## Limitations / methodological notes

1. **`attachStartMs` remains batch-level, not per-UE** (unchanged, non-issue at ueNum=1; already
   flagged in `docs/standard_attach_ns3_measurement_plan.md`).
2. **Output path remains `/home/ankit/...` instead of `/root/...`** due to filesystem
   permissions on this host (unchanged from previous run).
3. **`firstDataPacketTimeMs` join is by destination IP+port+protocol only** — sufficient and
   unambiguous for this single-UE, single-flow-per-UE traffic model, but if a future variant
   gives one UE multiple concurrent flows, the current join takes the first matching flow only;
   would need extending (not needed for this proof of concept).
4. No 1–200 UE ladder was run. No PAIBO-attach variant was implemented. No existing RR/PF,
   noise, or MAC-CE scenario file was modified. OAI was not touched.

# Conventional Attach Baseline — ns-3 + 5G-LENA

**THIS IS AN ns-3.48 / 5G-LENA v5.1 DISCRETE-EVENT SIMULATION. `NrPointToPointEpcHelper`
implements an LTE-EPC-style core with no NAS/NGAP/PFCP stack. There is no real 5G SA
Registration Request/Accept, no real PDU Session Establishment, and no real PDU Session
Resource Setup procedure running in this simulator.** "Conventional Attach" is this artifact's
own label for a timeline that follows the message sequence shown in the "Standard 3GPP Attach
Procedure" diagram in `5g-sa-paibo-attach-comparison.pptx` — that is the diagram's own title,
quoted as a fact about the source material; it is not a claim that this simulator implements
the 3GPP standard itself, nor a name this artifact uses for itself elsewhere in this repo.

## Naming note (this revision)

This scenario and its documentation were previously named/labeled "Standard Attach Baseline"
(`standard-attach-baseline-study.cc`, `docs/standard_attach_baseline_ns3.md`,
`ns3_standard_attach_baseline_ladder/`). They have been renamed to "Conventional Attach
Baseline" (`conventional-attach-baseline-study.cc`, this document,
`ns3_conventional_attach_baseline_ladder/`) at the requester's instruction, to avoid the
"Standard 3GPP" label implying this artifact is itself the 3GPP standard rather than a
simulator model of one diagram from it. **This is a naming/label change only** — the attach
hop model, `--hopDelayMs`, the measured RRC-connection instrumentation, the FlowMonitor
first-data-packet join, the traffic model, and the channel configuration are byte-for-byte
unchanged; only identifiers, file names, and prose were renamed. All numeric results below were
re-generated from a fresh run of the renamed binary (same RNG seed/run) to confirm this, not
copied over from the prior run under assumption of equivalence.

## What is MEASURED vs MODELED

**MEASURED (real ns-3 discrete events):**
- `attachStartMs` — `Simulator::Now()` captured immediately before
  `nrHelper->AttachToClosestGnb(...)` (batch-level across all UEs in one call).
- `rrcSetupCompleteMs` — `NrGnbRrc::ConnectionEstablished` event, the real simulated
  RRC-connection-setup completion time. Diagram's "Till RRCSetupComplete (Registration
  Request)" step.
- `rrcSetupLatencyMs = rrcSetupCompleteMs - attachStartMs` — real simulated RRC/MAC/PHY
  procedure duration.
- `firstDataPacketTimeMs` — FlowMonitor's actual recorded `timeFirstRxPacket` for the UE's
  application UDP flow (remoteHost → UE). A real ns-3 packet-reception event, not derived from
  or related to the modeled hop chain.
- `attachToFirstDataPacketLatencyMs = firstDataPacketTimeMs - attachStartMs` — the real
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
`rrcSetupLatencyMs` comes entirely from ns-3's real, simulated random-access +
RRC-connection-setup procedure (`NrGnbRrc::ConnectionEstablished`). It reflects actual
PHY/MAC/RRC simulated behavior, not a modeled constant.

### B. firstDataPacketTimeMs is a measured FlowMonitor application-flow event
Read directly from `FlowMonitor::GetFlowStats()`'s `timeFirstRxPacket` field for the flow
matching the UE's IP address and application port (UDP), joined by IMSI, never by assumption.

### C. attachToFirstDataPacketLatencyMs includes the actual time until the first application packet is received
This is the real, measured, end-to-end time from attach start to the UE actually receiving its
first application-layer packet — it is not a modeled figure.

### D. dataReadyMs / totalAttachToDataLatencyMs is a modeled attach timeline
These must **never** be described as the measured first-data latency. They mark only the end of
the synthetic 18-hop signaling chain, not any real packet event.

### E. The first application packet occurs substantially later than modeled dataReadyMs
This is expected and not a bug: `udpAppStartTime` (400 ms) plus the UE-side application's own
On/Off scheduling and first-packet transmission/propagation time are entirely independent of,
and not synchronized with, the modeled signaling chain's timing. The modeled chain answers
"when would signaling say the bearer is ready"; the measured KPI answers "when did a real
packet actually arrive" — these must not be conflated or compared as if measuring the same
thing.

### F. Current model still does not implement actual NAS/NGAP/5GC signaling
`NrPointToPointEpcHelper` still has no NAS/NGAP/PFCP stack; the 18 MODELED hops are still a
synthetic scaffold, not real signaling. The rename does not change this.

## Build

```
cd /opt/ns3/ns-3-dev
./ns3 build conventional-attach-baseline-study
```
Target/executable: `/opt/ns3/ns-3-dev/build/contrib/nr/examples/ns3-dev-conventional-attach-baseline-study-default`.
Build: succeeded, zero warnings/errors from the renamed file (only pre-existing unrelated `nr`
module deprecation warnings appear in the full build log, same as before the rename).

## Run command pattern

```
LD_LIBRARY_PATH=/opt/ns3/ns-3-dev/build/lib \
  /opt/ns3/ns-3-dev/build/contrib/nr/examples/ns3-dev-conventional-attach-baseline-study-default \
  --ueNum=<N> --simTime=10 \
  --outputDir=/home/ankit/ns3_conventional_attach_baseline_ladder/ue_<N> \
  --simTag=conv<N> --fullTraces=true
```

## Results

See `ns3_conventional_attach_baseline_ladder/standard...` -- renamed to
`ns3_conventional_attach_baseline_ladder/conventional_attach_baseline_ladder.csv` and
`conventional_attach_baseline_ladder_summary.md` for the full 7-level (1/10/25/50/100/150/200
UE) ladder results, re-generated fresh under the renamed binary. Values are confirmed identical
to the prior "Standard Attach Baseline" run at every level (same RNG seed/run, same model — only
names changed).

## Limitations / methodological notes (unchanged by the rename)

1. `attachStartMs` remains batch-level, not per-UE.
2. `firstDataPacketTimeMs` join is by destination IP+port+protocol only — sufficient for this
   single-UE-per-flow traffic model.
3. No PAIBO-attach variant was implemented as part of this rename. No existing RR/PF, noise, or
   MAC-CE scenario file was modified. OAI was not touched.

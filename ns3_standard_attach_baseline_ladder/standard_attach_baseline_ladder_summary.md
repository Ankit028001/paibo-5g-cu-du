# Standard Attach Baseline Ladder — Summary

THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION LADDER. `NrPointToPointEpcHelper` implements no real NAS/NGAP/5GC stack. MEASURED columns (RRC setup latency, first-data-packet KPIs) are real ns-3 events; MODELED columns (core signaling latency, total attach-to-data latency) are a synthetic 18-hop timing scaffold anchored at the real RRC-connected timestamp -- see standard-attach-baseline-study.cc and docs/standard_attach_baseline_ns3.md for the full MEASURED/MODELED distinction.

firstDataPacketTimeMs / attachToFirstDataPacketLatencyMs are measured application-flow events (FlowMonitor); because udpAppStartTime and OnOff scheduling are part of the application configuration, this KPI must NOT be interpreted as pure 3GPP attach signaling latency, and must not replace the modeled totalAttachToDataLatencyMs KPI.

| ueCount | status | configuredUeCount | rrcConnectedCount | successPct | meanRrcSetupLatencyMs | minRrcSetupLatencyMs | maxRrcSetupLatencyMs | firstDataObservedCount | meanFirstDataPacketTimeMs | meanAttachToFirstDataLatencyMs | modeledHopDelayMs | coreSignalingLatencyMs | modeledTotalAttachToDataLatencyMs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | OK | 1 | 1 | 100.00 | 18.0357 | 18.0357 | 18.0357 | 1 | 668.2790 | 668.2790 | 0.1000 | 1.8000 | 19.8357 |
| 10 | OK | 10 | 10 | 100.00 | 18.0357 | 18.0357 | 18.0357 | 10 | 527.5356 | 527.5356 | 0.1000 | 1.8000 | 19.8357 |
| 25 | OK | 25 | 25 | 100.00 | 20.4757 | 18.0357 | 26.5357 | 25 | 527.4742 | 527.4742 | 0.1000 | 1.8000 | 22.2757 |
| 50 | OK | 50 | 50 | 100.00 | 25.1257 | 18.0357 | 35.5357 | 50 | 528.3907 | 528.3907 | 0.1000 | 1.8000 | 26.9257 |
| 100 | OK | 100 | 100 | 100.00 | 34.4257 | 18.0357 | 53.5357 | 100 | 528.7789 | 528.7789 | 0.1000 | 1.8000 | 36.2257 |
| 150 | OK | 150 | 150 | 100.00 | 45.0224 | 18.0357 | 76.0357 | 150 | 529.4036 | 529.4036 | 0.1000 | 1.8000 | 46.8224 |
| 200 | OK | 200 | 200 | 100.00 | 53.1607 | 18.0357 | 89.5357 | 200 | 530.3243 | 530.3243 | 0.1000 | 1.8000 | 54.9607 |

## Validation notes per level

- ueCount=1: rowCountInTimeline=1, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 1}
- ueCount=10: rowCountInTimeline=10, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 10}
- ueCount=25: rowCountInTimeline=25, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 25}
- ueCount=50: rowCountInTimeline=50, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 50}
- ueCount=100: rowCountInTimeline=100, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 100}
- ueCount=150: rowCountInTimeline=150, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 150}
- ueCount=200: rowCountInTimeline=200, negativeLatencyDetected=False, flowCheck(heartbeatFlows/ueFlows)={'heartbeatFlows': 1, 'ueFlows': 200}

## Consistency check against validated 1-UE PoC

- meanRrcSetupLatencyMs at ueCount=1: 18.0357 ms (PoC reference: 18.0357 ms)
- coreSignalingLatencyMs at ueCount=1: 1.8000 ms (PoC reference: 1.8 ms)
- modeledTotalAttachToDataLatencyMs at ueCount=1: 19.8357 ms (PoC reference: 19.8357 ms)

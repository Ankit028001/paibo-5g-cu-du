# PAIBO Attach Baseline Ladder vs. Conventional Attach Baseline — Comparison

THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION LADDER. Neither scenario implements real NAS/NGAP/5GC signaling or a real BIP ML predictor -- PAIBO's Component 1 (BIP/BIV) is an ORACLE assumption (perfect prediction, zero mismatch), not a measured ML result. Only PAIBO Component 2 (Shadow DRB / predictive RRCReconfiguration timing) is modeled here. See paibo-attach-baseline-study.cc and paibo_attach_baseline_ns3.md for the full MEASURED/MODELED breakdown and the exact hop-chain derivation.

**Headline metric (Metric 1): bearerSetupLatencyMs = DRB active time - Registration Complete time.** Conventional baseline: DRB becomes active only after the full PDU-phase RRCReconfiguration round trip (positive value). PAIBO: DRB becomes active during registration, before Registration Complete even fires (value <= 0). Reported as ms saved, not a percentage, since a percentage is undefined when the PAIBO value is <= 0.

| ueCount | conv bearerSetupLatencyMs | paibo bearerSetupLatencyMs | ms saved | conv coreSignalingMs | paibo coreSignalingMs | conv totalAttachToDataMs | paibo totalAttachToDataMs | conv msgCount | paibo msgCount | net msg change |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 19.8357 | 19.9857 | 18 | 19 | +1 |
| 10 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 19.8357 | 19.9857 | 18 | 19 | +1 |
| 25 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 22.2757 | 22.4257 | 18 | 19 | +1 |
| 50 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 26.9257 | 27.0757 | 18 | 19 | +1 |
| 100 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 36.2257 | 36.3757 | 18 | 19 | +1 |
| 150 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 46.8224 | 46.9724 | 18 | 19 | +1 |
| 200 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 54.9607 | 55.1107 | 18 | 19 | +1 |

## PAIBO-side validation notes per level

- ueCount=1: rowCountInTimeline=1, rrcConnectedCount=1/1, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=1/1
- ueCount=10: rowCountInTimeline=10, rrcConnectedCount=10/10, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=10/10
- ueCount=25: rowCountInTimeline=25, rrcConnectedCount=25/25, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=25/25
- ueCount=50: rowCountInTimeline=50, rrcConnectedCount=50/50, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=50/50
- ueCount=100: rowCountInTimeline=100, rrcConnectedCount=100/100, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=100/100
- ueCount=150: rowCountInTimeline=150, rrcConnectedCount=150/150, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=150/150
- ueCount=200: rowCountInTimeline=200, rrcConnectedCount=200/200, negativeRrcOrCoreLatencyDetected=False (expected False -- only bearerSetupLatencyMs is allowed to be negative), drbReadyBeforeRegCompleteCount=200/200

## First-data-packet KPI (expected to be ~identical between the two scenarios)

| ueCount | conv meanFirstDataPacketTimeMs | paibo meanFirstDataPacketTimeMs |
|---|---|---|
| 1 | 668.2790 | 668.2790 |
| 10 | 527.5356 | 527.5356 |
| 25 | 527.4742 | 527.4742 |
| 50 | 528.3907 | 528.3907 |
| 100 | 528.7789 | 528.7789 |
| 150 | 529.4036 | 529.4036 |
| 200 | 530.3243 | 530.3243 |

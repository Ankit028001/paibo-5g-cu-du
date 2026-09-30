# PAIBO Attach Baseline vs. Conventional Attach Baseline — ns-3 + 5G-LENA

**THIS IS AN ns-3.48 / 5G-LENA v5.1 DISCRETE-EVENT SIMULATION. `NrPointToPointEpcHelper`
implements no real NAS/NGAP/5GC stack, and no real BIP (Bearer Intent Predictor) ML model
exists anywhere in this repository.** This scenario models only PAIBO's Component 2 (Shadow
DRB / predictive RRCReconfiguration timing shift) against an explicit oracle assumption for
Component 1 (perfect prediction, zero mismatch). Components 3 (MAC-CE adaptation) and 4
(RL-based SDAP) are not implemented — future work, out of scope for ns-3.

## What this scenario models, and what it deliberately does not

| Component | In this ns-3 model | Note |
|---|---|---|
| 1. BIP/BIV predictor | **Oracle assumption** | Shadow DRB config is always exactly correct (100% hit rate). This is an explicit upper-bound, not a measured ML result — no BIP/BIV model exists in this repo. A real predictor's accuracy is a separate (journal-track) study. |
| 2. Shadow DRB | **Modeled** — this IS the experiment | See hop chain below. |
| 3. MAC-CE adaptation | Not implemented | Future work. |
| 4. RL-based SDAP | Not implemented | Future work. DRB-count metric optional if resumed. |

## MEASURED vs MODELED (same discipline as the conventional baseline)

Exactly one event is real: `NrGnbRrc::ConnectionEstablished` (RRC connection setup). Everything
downstream is a MODELED scheduled-forward timing chain anchored at that real timestamp, using
the same single `--hopDelayMs` knob as `conventional-attach-baseline-study.cc` (also applied to
the real EPC `S1uLinkDelay` attribute). No new independently-invented latency constant is
introduced — the two non-full-hop steps below are exact fractions of that one parameter:

- `shadowInstantiationMs` (gNB-local compute) = **0.5 × hopDelayMs** (0.05ms at the 0.1ms
  default — the exact value given when this scenario was specified)
- `shadowMatchCheckMs` (gNB-local compute, oracle ⇒ always matches) = **0.0 × hopDelayMs**
  ("near zero" modeled as literally instantaneous, not an invented small constant)

Both are gNB-internal computation steps, not UE-facing signaling messages, and are excluded
from the signaling message count (Metric 3).

## The hop chain (PAIBO order; see pptx image-1-2.png, "Proposed PAIBO Attach Procedure")

Steps 1–11 are identical to the conventional baseline (Initial UE Message through Initial
Context Setup Response). Then PAIBO diverges:

| # | Step | Column | Weight × hopDelayMs |
|---|---|---|---|
| 12 | RRCBearerHint (predicted DRB/s config) [gNB→UE] — **NEW** | `rrcBearerHintMs` | 1.0 |
| 13 | Shadow DRB instantiation at gNB (gNB-internal) — **NEW** | `shadowInstantiationMs` | 0.5 |
| 14 | RRCBearerHint acknowledgment [UE→gNB] — **NEW**, DRB becomes active here | `rrcBearerHintAckMs` | 1.0 |
| 15 | Registration Accept | `registrationAcceptMs` | 1.0 |
| 16 | Registration Complete | `registrationCompleteMs` | 1.0 |
| 17 | PDU Session Establishment Request | `pduSessionEstablishmentRequestMs` | 1.0 |
| 18 | gNB checks shadow match (gNB-internal, oracle) — **NEW** | `shadowMatchCheckMs` | 0.0 |
| 19 | PDU Session Resource Setup Request | `pduSessionResourceSetupRequestMs` | 1.0 |
| 20 | PDU Session Establishment Accept via plain `DLInformationTransfer` — **NEW**, replaces the conventional baseline's `RRCReconfiguration`+`Complete` pair | `pduSessionEstablishmentAcceptMs` | 1.0 |
| 21 | PDU Session Resource Setup Response | `pduSessionResourceSetupResponseMs` | 1.0 |
| — | Data ready to flow | `dataReadyMs` (== step 21) | — |

**Why step 20 is a single hop, not the conventional baseline's two:** per the pptx diagram's own
note, a full `RRCReconfiguration` + `RRCReconfigurationComplete` round trip is "required only if
mismatch/miss/surplus is detected." Since Component 1 is modeled as a perfect oracle, there is
never a mismatch, so PDU Session Establishment Accept collapses to a single one-way
`DLInformationTransfer` — no reconfiguration, no Complete needed.

## Derived KPIs

- **`drbActiveMs` = `rrcBearerHintAckMs`** — the UE has applied and acknowledged the predicted
  DRB config.
- **`bearerSetupLatencyMs` = `drbActiveMs` − `registrationCompleteMs`** (MODELED) — **the
  headline PAIBO metric.** Can be negative (DRB active *before* Registration Complete even
  fires). Never floored to 0; the signed value is the honest result and is exactly what makes
  PAIBO's benefit visible.
- **`coreSignalingLatencyMs` = `dataReadyMs` − `rrcSetupCompleteMs`** (MODELED) — kept for
  continuity with the conventional baseline. **Slightly larger** for PAIBO (the BearerHint round
  trip costs more than the PDU-phase savings when measured end-to-end from RRC-connected). This
  is expected and is *not* the metric PAIBO's benefit is claimed on.
- **`totalAttachToDataLatencyMs` = `dataReadyMs` − `attachStartMs`** (MODELED) — same convention
  as the conventional baseline.
- **`signalingMessageCount`** (MODELED, constant per run) — real UE↔gNB / gNB↔Core signaling
  hops only (excludes the two gNB-internal compute steps). PAIBO = **19**, conventional = **18**.
  Net **+1**: +2 for RRCBearerHint/Ack, −1 because the oracle-case `DLInformationTransfer` needs
  no `RRCReconfigurationComplete`.

`firstDataPacketTimeMs` / `attachToFirstDataPacketLatencyMs` use the identical FlowMonitor-join
methodology as the conventional baseline (real `timeFirstRxPacket`, joined by IMSI). These come
out numerically **identical** to the conventional baseline at every UE count — expected, since
UE application traffic start time and scheduling are configured independently of this modeled
signaling chain. **This KPI is not where PAIBO's benefit shows up; `bearerSetupLatencyMs` is.**

## Results — 1-UE proof of concept, then full 1–200 UE ladder

Build: `./ns3 build paibo-attach-baseline-study` → succeeded, zero warnings/errors from this
file (only pre-existing unrelated `nr` module deprecation warnings elsewhere in the build).
Binary: `ns3-dev-paibo-attach-baseline-study-default`.

1-UE PoC (`--ueNum=1 --simTime=10`, default `--hopDelayMs=0.1`), matched by hand-calculation
before the run: `bearerSetupLatencyMs = -0.2ms` (predicted and confirmed exactly),
`coreSignalingLatencyMs = 1.95ms`, `firstDataPacketTimeMs = 668.279ms` (identical to the
conventional baseline's 1-UE result).

Full ladder (1/10/25/50/100/150/200 UEs, same config as the conventional baseline's ladder):
all 7 levels exit 0, 100% RRC connection success, exactly one timeline row per configured UE at
every level, no negative RRC-setup or core-signaling latency anywhere (only `bearerSetupLatencyMs`
is allowed to be negative, by design), and 100% of UEs show `drbReadyBeforeRegCompleteCount` at
every level.

## Conventional vs PAIBO comparison (all 7 UE counts)

| ueCount | conv bearerSetupLatencyMs | paibo bearerSetupLatencyMs | ms saved | conv coreSignalingMs | paibo coreSignalingMs | conv msgCount | paibo msgCount |
|---|---|---|---|---|---|---|---|
| 1 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |
| 10 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |
| 25 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |
| 50 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |
| 100 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |
| 150 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |
| 200 | 0.4000 | -0.2000 | 0.6000 | 1.8000 | 1.9500 | 18 | 19 |

`bearerSetupLatencyMsSaved` and the message-count delta are **constant across UE count** — this
is expected in the current model: the modeled hop chain is a fixed per-UE offset applied
independently once each UE's real RRC connection completes, so it doesn't compound with UE
count the way the real, contended `rrcSetupLatencyMs` (MEASURED) does. `rrcSetupLatencyMs` itself
rises with UE count identically in both scenarios (same real PHY/MAC contention in both — this
part of the pipeline is untouched by the PAIBO change), so the *absolute* `bearerSetupLatencyMs`
values are constant while the underlying attach procedure surrounding them still scales
realistically with load.

## Limitations / methodological notes

1. **Component 1 is an oracle, not a measurement.** Any claim beyond "under a perfect predictor,
   Component 2 alone saves 0.6ms of bearer setup latency and costs +1 signaling message" would
   require a real BIP/BIV model, which does not exist here.
2. **`bearerSetupLatencyMsSaved` is constant across UE count in this model** — see above. A more
   elaborate model where BearerHint/shadow-instantiation cost scales with load would be a
   reasonable extension but was not requested and is not implemented.
3. Same inherited limitations as the conventional baseline: `attachStartMs` is batch-level not
   per-UE; the first-data-packet join is by destination IP+port+protocol only.
4. No RR/PF/noise/MAC-CE scenario file was modified. OAI was not touched.

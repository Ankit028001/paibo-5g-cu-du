> Step 4b (Sep 9, 2026) — RACH / RRC / RRC Reconfiguration / Initial Attach
> study notes mapped to NS-3 5G-LENA code
> Status: Complete

# RACH / RRC / RRC Reconfiguration / Initial Attach — ShareTechnote Study, Mapped to NS-3 5G-LENA

Source for the theory sections: [5G | ShareTechnote](https://www.sharetechnote.com/)
("RACH", "RRC Overview", "RRC Reconfiguration", "Initial Attach"). Source
for the implementation sections: this repository's ns-3.48 / 5G-LENA v5.1
scenario code, cross-checked against `step4b_rrc_attach_study/conventional_attach_baseline_ns3.md`
and `step4_paibo_collab/paibo_simulation/paibo_attach_baseline_ns3.md`.

---

## 1. RACH (Random Access Channel)

**What it is in theory:** RACH is the procedure a UE uses to first get
noticed by, and synchronized with, a cell before any RRC signaling can
happen. In the standard 4-step contention-based procedure, the UE picks a
random preamble from a pool broadcast by the cell, transmits it on the
PRACH resource, and the network responds with a Random Access Response
(RAR), followed by an RRC Connection Request and a contention-resolution
message. If two UEs pick the same preamble in the same slot, contention
occurs and one or both must retry.

**How it is implemented in NS-3 5G-LENA:** the `nr` module implements the
4-step contention-based RACH procedure directly in its MAC layer. The
cell broadcasts a pool of **64 preambles**, on a **10ms PRACH period**,
matching the standard configuration. Each UE independently draws a
preamble at random from this pool per attempt (per-UE draw, with
cell-wide contention when counts collide), and retries on failure. This
is a real, simulated discrete-event procedure — **not** a fixed constant
— and its outcome directly determines when `RRCSetupComplete` fires.
**This RACH-to-`RRCSetupComplete` span is the REAL measured part of our
simulation**, captured as `rrcSetupLatencyMs` in
`conventional_attach_baseline_ns3.md` (Section "A. RRC setup latency is a
measured radio/RRC event").

**Which source file handles it:** the RACH state machine itself lives in
the `nr` module's MAC implementation (`contrib/nr/model/nr-gnb-mac.cc`,
`contrib/nr/model/nr-ue-mac.cc` — preamble pool size of 64 is enforced in
`nr-gnb-mac.cc`). Our scenario files (e.g.
`source/ns3_scenarios/cu-du-scaling-study.cc`,
`step4b_rrc_attach_study/conventional-attach-baseline-study.cc`) do not
reimplement RACH — they configure the scenario (UE count, topology) and
then measure the real RACH+RRC-setup outcome via the
`NrGnbRrc::ConnectionEstablished` trace.

---

## 2. RRC Overview

**What it is in theory:** RRC (Radio Resource Control) is the control-plane
protocol between the UE and the gNB that manages the radio connection
itself — connection setup, reconfiguration, measurement reporting,
mobility, and release. It sits above RACH/MAC and below NAS: once RACH
gets the UE noticed, RRC is what actually establishes and manages the
UE's radio link and bearer configuration.

**How it is implemented in NS-3 5G-LENA:** the `nr` module implements RRC
as two mirrored classes — one running on the UE side, one on the gNB
side — that exchange RRC messages (`RRCSetupRequest`, `RRCSetup`,
`RRCSetupComplete`, `RRCReconfiguration`, etc.) as real simulated
messages with real simulated timing. The gNB-side class is where
`ConnectionEstablished` fires — the one real, measured RRC event this
repository's baselines are anchored on.

**Which source file handles it:** `NrUeRrc` (UE side) and `NrGnbRrc`
(gNB side), in `contrib/nr/model/nr-ue-rrc.cc` and
`contrib/nr/model/nr-gnb-rrc.cc` respectively. Our own scenario code
never reimplements RRC state machines — it only attaches a trace sink to
`NrGnbRrc::ConnectionEstablished` to capture `rrcSetupCompleteMs`.

---

## 3. RRC Reconfiguration

**What it is in theory:** RRCReconfiguration is the message the network
sends to modify a UE's existing radio configuration — for example, to
add or modify a Data Radio Bearer (DRB) once a PDU session needs to be
set up. The UE applies the new configuration and replies with
`RRCReconfigurationComplete`, acknowledging the change. This exchange is
a full round trip, so it costs a full network round-trip delay before
the bearer is actually usable.

**How it is implemented in NS-3 5G-LENA:** in our attach timeline model,
RRCReconfiguration is not a real ns-3 signaling exchange but a
**MODELED** step in the 18-hop synthetic scaffold documented in
`conventional_attach_baseline_ns3.md`. Specifically, it is **Hop 16
(`rrcReconfigurationDrbMs`) and Hop 17 (`rrcReconfigurationCompleteMs`)
in our 18-hop model** — the DRB reconfiguration request and its
acknowledgment. **This RRCReconfiguration + Complete round trip is the
BOTTLENECK PAIBO targets**: PAIBO's proposed `RRCBearerHint` mechanism
(see `step4_paibo_collab/paibo_simulation/paibo_attach_baseline_ns3.md`)
pre-stages the DRB configuration earlier in the hop chain so that, under
an oracle (perfect-prediction) assumption, this round trip collapses to
a single one-way `DLInformationTransfer` instead — this is exactly where
PAIBO's modeled 0.6ms bearer-setup-latency saving comes from.

**Which source file handles it:** the two hops are defined and timed in
`source/ns3_scenarios/cu-du-bearer-latency-study.cc` (and its variant
`cu-du-bearer-latency-study-pf.cc`), and in
`step4b_rrc_attach_study/conventional-attach-baseline-study.cc`, both of
which schedule `rrcReconfigurationDrbMs` and
`rrcReconfigurationCompleteMs` as fixed-offset events via
`Simulator::Schedule()`, anchored at the real `rrcSetupCompleteMs`
timestamp — not as a real RRC message exchange in ns-3's RRC classes.

---

## 4. Initial Attach (all 19 steps, real vs modeled)

**What it is in theory:** Initial Attach is the end-to-end procedure a UE
goes through from first appearing at a cell to having a usable data
bearer: RACH → RRC connection setup → NAS Registration (with
authentication and security) → PDU Session Establishment → RRC
Reconfiguration for the DRB → data ready. In a real 5G SA network this
involves real NAS/NGAP signaling between the UE, gNB, AMF, SMF, and UPF.

**How it is implemented in NS-3 5G-LENA:** our Initial Attach model has
**19 total steps**: **1 REAL step + 18 MODELED steps.**

- **Step 0/1 — RRC phase — REAL (measured):** RACH completion through
  `RRCSetupComplete`, captured via the real `NrGnbRrc::ConnectionEstablished`
  trace. This is genuine ns-3 discrete-event simulation of PHY/MAC/RRC
  behavior, not a scheduled constant.
- **Steps 2–19 — 18 MODELED hops:** `initialUeMessageMs`, `authRequestMs`,
  `authResponseMs`, `securityModeCommandNasMs`, `securityModeCompleteNasMs`,
  `initialContextSetupRequestMs`, `securityModeCommandAsMs`,
  `securityModeCompleteAsMs`, `ueCapabilityEnquiryMs`,
  `ueCapabilityInformationMs`, `initialContextSetupResponseMs`,
  `registrationAcceptMs`, `registrationCompleteMs`,
  `pduSessionEstablishmentRequestMs`, `pduSessionResourceSetupRequestMs`,
  `rrcReconfigurationDrbMs` (Hop 16), `rrcReconfigurationCompleteMs`
  (Hop 17), `pduSessionResourceSetupResponseMs`. Each of these is
  **scheduled via `Simulator::Schedule()` at a fixed 0.1ms
  (`--hopDelayMs`) offset**, one after another, anchored at the real
  `rrcSetupCompleteMs` timestamp — **not** real NAS/NGAP packets. This is
  because `NrPointToPointEpcHelper` implements an LTE-EPC-style core with
  **no real NAS/NGAP/PFCP stack** and no real AMF/SMF/UPF — the 18 hops
  are a documented synthetic scaffold standing in for that signaling.

This MEASURED-vs-MODELED split is deliberate and is called out explicitly
in `conventional_attach_baseline_ns3.md` so that the one real radio-layer
result (`rrcSetupLatencyMs`) is never confused with the 18 modeled
signaling hops that follow it.

**Which source file handles it:** `source/ns3_scenarios/cu-du-bearer-latency-study.cc`
schedules the 18 modeled hops and reads the real `rrcSetupCompleteMs`
anchor. The equivalent conventional-attach ladder scenario is
`step4b_rrc_attach_study/conventional-attach-baseline-study.cc`; the
PAIBO variant that changes hops 16–17 into a single `DLInformationTransfer`
hop is `source/ns3_scenarios/paibo-attach-baseline-study.cc`.

---

## Summary table

| Topic | Real or Modeled | Source file |
|---|---|---|
| RACH (4-step, 64 preambles, 10ms PRACH period) | **Real** (ns-3 MAC discrete event) | `contrib/nr/model/nr-gnb-mac.cc`, `nr-ue-mac.cc` |
| RRC connection setup (→ `RRCSetupComplete`) | **Real** (ns-3 RRC discrete event) | `contrib/nr/model/nr-gnb-rrc.cc` (`NrGnbRrc`), `nr-ue-rrc.cc` (`NrUeRrc`) |
| RRC Reconfiguration (Hop 16–17, PAIBO's target) | **Modeled** (`Simulator::Schedule()`, 0.1ms/hop) | `source/ns3_scenarios/cu-du-bearer-latency-study.cc` |
| Initial Attach (1 real + 18 modeled steps) | **Mixed** — RRC phase real, rest modeled | `source/ns3_scenarios/cu-du-bearer-latency-study.cc`, `step4b_rrc_attach_study/conventional-attach-baseline-study.cc` |

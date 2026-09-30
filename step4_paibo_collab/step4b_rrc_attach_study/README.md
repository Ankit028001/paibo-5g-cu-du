> **Step 4b — RACH / RRC / RRC Reconfiguration / Initial Attach Study, Mapped to NS-3 (Sep 2026)**

# Task 4b — RACH/RRC/Attach Study Mapped to NS-3 Implementation

**Requested (Sukhdeep Singh email, "Step 3: PAIBO Collab Project",
2026-09-09):** study RACH, RRC Overview, RRC Reconfiguration, and Initial
Attach (5G | ShareTechnote), then see how each is implemented in our NS-3
simulator — important groundwork before making idea-driven changes to
the simulator code.

**What was done:**
- Mapped the Initial Attach procedure as implemented by ns-3 5G-LENA onto
  a documented, measured baseline (`conventional-attach-baseline-study.cc`
  + `conventional_attach_baseline_ns3.md` in this folder), covering the
  full attach hop chain (Initial UE Message → RRC setup → Registration →
  PDU Session Establishment) with an explicit MEASURED-vs-MODELED
  breakdown: which steps are real ns-3 events (e.g. RRC connection
  establishment) and which are a documented hop-delay model (NAS steps
  modeled as 18 × `hopDelayMs`, not real NAS packets —
  `NrPointToPointEpcHelper` implements no real NAS/NGAP/5GC stack).
- This mapping is what `step4_paibo_collab/paibo_simulation/` is built
  directly on top of — the PAIBO scenario reuses the same hop chain and
  diverges only where PAIBO's proposed RRCBearerHint procedure changes
  it.

**Status:** Done

**Files in this folder:**
- `README.md` (this file)
- `conventional-attach-baseline-study.cc`,
  `conventional_attach_baseline_ns3.md`,
  `conventional_attach_baseline_ladder.csv`,
  `conventional_attach_baseline_ladder_summary.md`, `LADDER_STATUS.txt`
- `ue_1/` … `ue_200/` — per-UE-count run outputs

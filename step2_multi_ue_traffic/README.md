> **Step 2 — Task 2: Multi-UE Traffic Proportions (Aug 24, 2026)**

# Task 2 — Multi-UE Setup with Traffic Proportions

**Requested (Samsung email, 2026-08-24):** multi-UE setup using the
agreed traffic proportions (mMTC 40%, Web 15%, Mobile 15%, VoD 12%, Live
video 13%, V2X 5%), with the traffic model and channel model documented
on GitHub.

**What is actually in this folder:** the **CU-DU topology** ladder — a
separate CU node and DU node on a dedicated point-to-point link, plus an
EPC-style core (`NrPointToPointEpcHelper` — **not** a real AMF/SMF/UPF),
run across the full UE-scaling ladder 1→10→25→50→100→150→200 with the
agreed 6-class traffic mix applied. This is a topological representation,
not a functional 3GPP F1 protocol implementation — 5G-LENA's `nr` module
has no F1AP; PHY/MAC/RLC/PDCP/RRC remain bundled on the DU node.

Traffic model and channel model docs are kept at the repo root
(`traffic_model.md`, `channel_model.md`, per instruction to leave
root-level `.md` files in place).

**Key results:** all 7 UE-count levels PASS with 100% RRC connection
success (`BASELINE_DATA_INTEGRITY.md`).

**Status:** Done

**Files in this folder:**
- `README.md` (this file)
- `BASELINE_DATA_INTEGRITY.md`, `ns3_cudu_phase_kpis.xlsx`
- `ue_1/` … `ue_200/` — per-UE-count run outputs

Scenario source: `source/ns3_scenarios/cu-du-scaling-study.cc`.

# Status Report — Sections 2 & 3

Covers instruction items on traffic modelling diversity and KPI collection,
against the ns-3/5G-LENA UE-scaling study (`ue-scaling-study.cc` and the
CU-DU variant `cu-du-scaling-study.cc`). All figures below are traceable to
files under `ns3_phase01/` and `ns3_cudu_phase/`.

## 2. Diverse Traffic Modelling

**Implemented:** a 6-class heterogeneous downlink traffic model —
mMTC, Web, Mobile, VoD, Live, V2X — applied identically across every UE
count in the ladder (1/10/25/50/100/150/200) and both scenarios (baseline
single-node gNB, and the CU-DU topology).

- **UE-count shares** (per the previous-email target, normalised to 100%):
  mMTC 40%, Web 15%, Mobile 15%, VoD 12%, Live 13%, V2X 5%.
- **Per-UE rate cap / packet size** per class taken directly from the OAI
  phase2 100-UE `traffic_model.md` reference table (e.g. mMTC 3 kbps/100 B,
  VoD 725 kbps/1200 B), so the ns-3 model and the OAI reference agree
  exactly at N=100.
- **Byte-volume validation at N=150** (measured vs. the target byte-volume
  percentages from the instructions):

  | Class | Measured | Target |
  |---|---|---|
  | mMTC | 0.74% | <1% |
  | Web | 10.4% | ~8% |
  | Mobile | 12.8% | ~10% |
  | VoD | 43.4% | ~35% |
  | Live | 30.2% | ~25% |
  | V2X | 2.46% | ~2% |

  Directionally correct and in the right order of magnitude per class;
  running a few points above target on Web/Mobile/VoD/Live consistently
  across UE counts, which is worth a closer look if exact byte-volume
  matching matters for downstream use.

**Open gaps:**
- Traffic is generated with ns-3's `OnOffApplication` at a constant,
  always-on rate per class — not real `iperf3`, and no burstiness/noise
  has been added yet (this was explicitly requested and remains open).
- Only the IDEAL channel (Scenario A, no fading/shadowing) has been run;
  no traffic data exists yet for a realistic-channel (Scenario B) run.

## 3. KPI Collection

**Implemented:**
- A full **KPI availability audit** (`KPI_AVAILABILITY_NOTE.md`) enumerating
  every KPI 5G-LENA's `nr` module trace sinks actually expose: per-UE/
  per-flow throughput, packet loss, delay, jitter (FlowMonitor); per-UE
  downlink SINR, MCS, CQI, transport-block corruption (PHY traces); per-UE
  RLC/PDCP delay (E2E stats); RRC-connected count; DL/UL pathloss.
- A **cross-check against the PAIBO patent deck's implied KPI set**
  (`PAIBO_KPI_CROSSCHECK.md`, `KPI_AVAILABILITY_MATRIX.md`): confirms which
  categories are directly measurable today (throughput, SINR, MCS, delay,
  loss), which need light extra derivation (DRB count via LCID, PDB
  compliance), and which are fundamentally unavailable without building
  the PAIBO feature itself (bearer setup latency breakdown, RRC/NGAP
  signaling overhead, real 5QI/ARP values, UE mobility, slice/time-of-day
  context, UE power, any ML-model accuracy metric).
- A **post-processing pipeline** (`parse_ns3_kpis.py`, `validate_paibo_kpis.py`)
  that joins the raw per-run trace files into `per_ue_kpis.csv` and
  `per_cell_kpis.csv`, plus 3 plots per run (per-UE average SINR, one
  randomly chosen UE's SINR time series, per-UE measured throughput).
  Validated end-to-end across the full ladder for both scenarios — every
  level has CSVs and plots on disk.
- Strict **NA-with-reason discipline**: every KPI that isn't actually
  instrumented is written as `NA` with an explicit reason rather than
  estimated or fabricated (e.g. `active_drb_count`, `bearer_setup_latency_ms`,
  and all four PAIBO-model accuracy fields are NA — none of that is
  implemented in ns-3 or OAI today).

**Open gaps:**
- No per-cell PRB utilization; no per-UE RSRP, CQI, or uplink SINR (not
  native trace fields in this build).
- No per-UE attach *timestamp* — only an aggregate RRC-connected count per
  run (`ue-scaling-study.cc` doesn't log per-UE attach events to file).
- Results exist only as CSV; not yet exported to Excel per the original
  instruction to "record values of KPIs... in the excel sheet."

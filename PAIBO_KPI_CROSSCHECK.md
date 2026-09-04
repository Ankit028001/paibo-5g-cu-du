# KPI Cross-Check vs. PAIBO Idea Slides

Source: `PAIBO_Patent_Vartika.pptx` (Samsung SRI-B patent deck — "Predictive
AI-Driven Bearer Orchestration"). This deck has no slide literally titled
"KPI list"; the KPIs below are the concrete metrics/data fields it names
across its problem statement, BIV field table, and latency comparison table
(slides 7, 8, 10, 20, 23, 31, 40, 49). This note marks which of those are
available from the current ns-3/5G-LENA + OAI setup, per instruction #2.

**Important framing:** PAIBO describes an AI-driven RRC feature (Bearer
Intent Predictor, shadow bearers, a new "Bearer Hint" RRC message,
MAC-CE micro-reconfiguration, RL-based SDAP consolidation) that does **not
exist** in stock 3GPP, OAI, or ns-3/5G-LENA today. Several of its KPIs are
properties of that not-yet-built AI model/protocol, not something any RAN
simulator or real stack can report until PAIBO itself is implemented.

| KPI / data field (PAIBO source) | Availability in current setup | Notes |
|---|---|---|
| Per-UE/per-flow throughput, delay, jitter, loss | **Available** | ns-3 FlowMonitor + RLC/PDCP E2E traces; exported to `per_ue_kpis.csv`/`per_cell_kpis.csv` via `parse_ns3_kpis.py` |
| Per-UE SINR, MCS, CQI, TB corruption | **Available** | `DlDataSinr.txt`, `RxPacketTrace.txt`, `NrDlMacStats.txt` (MAC-level trace only present when `--fullTraces=true`) |
| Bearer setup / activation latency (slide 23, 31: 100–200ms 3GPP vs 8–12ms PAIBO) | **Not available** | Neither OAI nor ns-3 implement the proposed Bearer Hint / shadow-bearer flow; only the ordinary RRC-connection-establishment time is measurable (ns-3 `ConnectionEstablished` trace), not PAIBO's claimed sub-step breakdown (NGAP arrival → RRCReconfiguration sent → UE apply → Complete) |
| RRC/NGAP signaling overhead (message count/size; slide 10: 15–30%, slide 48: 85% reduction) | **Not available** | Neither study currently counts RRC/NGAP messages or bytes; would need new packet-level RRC/S1AP trace instrumentation |
| DRB count per UE / DRB proliferation (slide 30: 5 flows → 2 DRBs) | **Partially available (derivable)** | ns-3 RLC/PDCP traces are per (IMSI, RNTI, LCID); distinct LCID count per UE is a usable proxy for DRB count, but not currently a dedicated CSV column — would need a small script addition |
| 5QI, GBR/MBR, ARP (per-bearer QoS profile) | **Partially available (proxy only)** | Our 6-class traffic model uses a custom `perUeCapBps`/packet size per class, not real 3GPP 5QI/ARP signaling values — a coarse stand-in, not the real field |
| Packet Delay Budget (PDB) compliance | **Available (derivable)** | Per-packet RLC/PDCP delay is already captured; % of packets under a given PDB threshold per traffic class is a straightforward post-processing addition, not yet computed |
| ML prediction confidence, accuracy, false-positive rate, missed-prediction rate (slide 20, 40) | **Not available — out of scope for a RAN simulator** | These are runtime metrics of the BIP inference model itself. They can only be measured once a BIP-equivalent model is trained and evaluated against a labeled dataset; the KPI CSVs this study produces are a candidate *input* to that future training/eval, not a source of these metrics themselves |
| UE mobility trajectory (velocity, location history, dwell time) | **Not available** | Current ns-3 scenario places UEs in a static grid (`GridScenarioHelper`), no mobility model attached; OAI captures likewise have no UE mobility |
| Application fingerprint / traffic classification features | **Partially available (coarse proxy)** | The 6-class label (mMTC/Web/Mobile/VoD/Live/V2X) is a configured ground-truth label, not a learned/observed fingerture — usable as a training label, not as an input feature PAIBO would infer at runtime |
| Slice context (S-NSSAI), time-of-day traffic patterns | **Not available** | Single-cell, single 30s run, no network slicing modeled, no multi-hour/day traffic variation |
| UE power consumption | **Not available** | No energy model attached in the ns-3 scenario; OAI captures measured host/process CPU% and RSS, not UE-side power |

## Bottom line

Of the metric categories PAIBO's slides name, the current ns-3/5G-LENA +
OAI setup **directly provides**: per-UE/per-cell throughput, delay, jitter,
loss, SINR, MCS, CQI. It can **derive with minor extra scripting**: DRB
count per UE, PDB compliance rate. It **cannot provide at all** without new
instrumentation or the BIP model itself: RRC/NGAP signaling overhead,
real 5QI/ARP values, UE mobility, slice/time-of-day context, UE power, and
any ML-model accuracy metric (those require training/evaluating an actual
BIP-equivalent model against a dataset — this study's CSV output is a
plausible *input* to that future step, not a source of those numbers).

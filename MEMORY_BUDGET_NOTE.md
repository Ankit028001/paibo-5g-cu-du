# Memory Budget Note — UE Scaling vs. AI Data-Pipeline Headroom

Addresses instruction #4: "While doing UE scaling, remember, we need to
save memory for data dump, data pre-processing, and AI model inferencing
part so, subtract that from the max UE capacity."

**All figures below are OAI-measured values from the existing phase2 audit
(`/opt/oai/openairinterface5g/phase2/20260903_100ue_vrtsim_cudu_189prb_patched/SUMMARY.md`).
Nothing here is extrapolated, modeled, or estimated beyond what was
actually measured on that run.**

## Measured values

- **Host total RAM:** 82 GiB (`free -h` on the lab host).
- **Per-UE OAI process RSS:** ~872 MiB/UE — measured on an isolated
  1-UE/189-PRB run (same build, same config). This is the only
  per-process RSS figure that was actually measured per-UE; multi-UE
  attempts in that audit sampled RAM at the host-aggregate level only,
  not broken out per process.
- **Peak RAM actually observed at multi-UE scale:** ~20.5 GiB (~25% of
  82 GiB) with 15 real UE processes running (attempt_03 in the same
  audit). Available RAM never dropped below ~64 GiB in any attempt.

## Observed bottleneck: CPU, not RAM

The same audit states directly: **"RAM was not the limiting factor in any
attempt."** The measured, reproducible limiting factor was CPU/real-time
compute — specifically the `O(N)` per-callback cost of the vrtsim
DL-replication/UL-combining loop (`radio/vrtsim/vrtsim.c:911-918`,
`949-971`), which exceeded the real-time deadline at N≈15 actually-connected
UEs in that experiment, well before RAM, CPU core count, or CN5G capacity
were exhausted.

## Consequence for "subtract memory for the AI pipeline from max UE capacity"

Given the above:

- If a fixed memory reserve is set aside for data dump + pre-processing +
  AI model inferencing (e.g. any number of GiB up to several tens of GiB),
  it does **not** change the practical maximum UE count for the **OAI
  real-time track**, because that maximum is already set by CPU/real-time
  compute at ~15 UEs — far below any RAM ceiling, with or without a
  reservation. Headroom subtraction from RAM is not the binding constraint
  here.
- For the **ns-3 discrete-event track** (not real-time-constrained), the
  validated ladder reached 200 UEs with no RAM exhaustion reported at any
  level; the operational limits actually hit there were trace-file I/O
  volume and wall-clock runtime, not RAM capacity, per `SCALING_SUMMARY.md`.

**This note does not propose a new numeric "safe max UE count" derived
from an assumed AI-pipeline memory reservation, because no such
reservation size (data dump / pre-processing / inferencing footprint) has
been measured for this project's specific pipeline.** Doing so would
require either (a) measuring the actual footprint of this project's own
KPI-CSV pre-processing (`parse_ns3_kpis.py`/`validate_paibo_kpis.py`) and
any future PAIBO model inference step, or (b) an explicit assumption
clearly labeled as an assumption rather than a measurement. Neither has
been done as of this note.

## Bottom line

- Measured: 82 GiB host RAM, ~872 MiB/UE OAI RSS, ~20.5 GiB peak used at
  15 UEs, CPU/real-time identified as the actual bottleneck.
- Not measured / not claimed: any specific memory footprint for "data
  dump," "data pre-processing," or "AI model inferencing" in this
  project's pipeline, and therefore no revised max-UE-capacity number is
  presented here. If a concrete AI model (e.g. a BIP-equivalent) is later
  built and its actual memory footprint measured, this note should be
  updated with that real figure rather than an assumed one.

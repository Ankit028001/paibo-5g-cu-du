# PAIBO 5G Baseline — Traffic Model

## Overview

Synthetic traffic model representing six 5G application classes,
implemented via ns-3 `OnOffApplication` (UDP, downlink only — remote
host → UE) with per-UE lognormal rate variation, per-class packet-size
distributions, and staggered application start offsets. **This is NOT
real iperf3 traffic, NOT real HTTP/video/V2X protocol traffic, and NOT
traffic measured from a real deployment.** Every value below is either
read directly from the implementing source file or computed directly
from a validated `*_traffic_config.tsv` / `per_cell_kpis.csv` result
file already in this repository — nothing is inferred or assumed.

Two ns-3 scenario variants implement this traffic model:
- `source/ns3_scenarios/cu-du-scaling-study.cc` — constant-rate version (no noise)
- `source/ns3_scenarios/cu-du-scaling-study-noise.cc` — the noise-augmented version documented in detail below
- `source/ns3_scenarios/ue-scaling-study.cc` — same 6-class model, single-node gNB (no CU-DU topology)

All three share the identical `GetTrafficClasses()` UE-count shares and
per-UE rate caps; only `cu-du-scaling-study-noise.cc` adds the lognormal
rate/size/offset noise described in this document.

## UE Population Distribution

Verified directly from the actual executed `cudunoise{N}_traffic_config.tsv`
files under `ns3_cudu_phase_noise/ue_{N}/` (noise-augmented scenario). These
are the **real allocations produced by the largest-remainder integer
distribution algorithm** (`DistributeUesAcrossClasses()` in source), not
a hand-specified table — note in particular that V2X receives **0 UEs at
N=10** (5% of 10 UEs rounds down under this algorithm, with the single
remainder unit going to another class), which would not appear in a
naively-rounded table.

| Class | Target UE-count share | N=10 | N=25 | N=50 | N=100 | N=150 | N=200 |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| mMTC  | 40% | 4 | 10 | 20 | 40 | 60 | 80 |
| Web   | 15% | 2 | 4  | 8  | 15 | 23 | 30 |
| Mobile| 15% | 2 | 4  | 8  | 15 | 23 | 30 |
| VoD   | 12% | 1 | 3  | 6  | 12 | 18 | 24 |
| Live  | 13% | 1 | 3  | 6  | 13 | 19 | 26 |
| V2X   |  5% | 0 | 1  | 2  | 5  | 7  | 10 |
| **Total** | 100% | **10** | **25** | **50** | **100** | **150** | **200** |

Source: `ns3_cudu_phase_noise/ue_{10,25,50,100,150,200}/cudunoise{N}_traffic_config.tsv`
(also identical in the non-noise `ns3_cudu_phase/` and `ns3_phase01/` variants,
since the allocation algorithm depends only on `ueNum` and the class shares,
not on the noise model).

## Per-Class Traffic Parameters

All classes use **UDP** (`ns3::UdpSocketFactory`), traffic flowing
**downlink only** (client `OnOffApplication` on the remote host, sink on
the UE) — there is no uplink traffic and no TCP anywhere in this scenario,
for any class. Every class's `OnTime`/`OffTime` is set to
`ConstantRandomVariable[Constant=1e9]` / `[Constant=0]` — i.e. **one
continuous ON period for the entire simulated duration**. There is no
exponential or other ON/OFF burst pattern implemented anywhere in this
scenario; per-UE rate noise (below) is drawn **once per UE** for that
single continuous burst, not re-drawn periodically.

### mMTC / IoT
- Nominal per-UE rate (`perUeCapBps`): **3000 bps (0.003 Mbps)**
- Nominal packet size: 100 bytes
- Actual packet size with noise: `Uniform(64, 256)` bytes, redrawn once per UE
- Rate noise sigma: 0.25
- Max start offset: `Uniform(0, 30)` seconds

### Web Application
- Nominal per-UE rate: **133000 bps (0.133 Mbps)**
- Nominal packet size: 600 bytes
- Actual packet size with noise: `Uniform(512, 1500)` bytes
- Rate noise sigma: 0.40
- Max start offset: `Uniform(0, 15)` seconds

### Mobile Application
- Nominal per-UE rate: **166000 bps (0.166 Mbps)**
- Nominal packet size: 800 bytes
- Actual packet size with noise: `Uniform(512, 1400)` bytes
- Rate noise sigma: 0.35
- Max start offset: `Uniform(0, 15)` seconds

### Video on Demand (VoD)
- Nominal per-UE rate: **725000 bps (0.725 Mbps)**
- Packet size: **fixed 1200 bytes — no size noise applied** (`pktSizeMin=0` in source)
  - **Known discrepancy, documented rather than silently resolved:** the source
    code comment on this line reads `// fixed 1316B per spec; kept at 1200 to
    match baseline`. The nominal 5G-LENA/PAIBO specification apparently called
    for 1316 bytes (a common MPEG-TS-aligned size), but the actual value
    **compiled, run, and measured in every result in this repository is
    1200 bytes**, deliberately kept equal to the pre-noise baseline scenario's
    packet size so the two are comparable. 1200 bytes is the value used in
    the executed experiment; 1316 bytes was never run.
- Rate noise sigma: 0.05 (smallest of all classes — near-constant rate)
- Max start offset: `Uniform(0, 10)` seconds

### Live Video / Streaming
- Nominal per-UE rate: **478000 bps (0.478 Mbps)**
- Packet size: **fixed 1200 bytes — no size noise applied** (`pktSizeMin=0` in source)
  - Same 1316B-vs-1200B discrepancy as VoD above, same resolution: the source
    comment references "1316B per spec," but 1200 bytes is what was actually
    compiled and run.
- Rate noise sigma: 0.10
- Max start offset: `Uniform(0, 10)` seconds

### V2X
- Nominal per-UE rate: **99000 bps (0.099 Mbps)**
- Nominal packet size: 300 bytes
- Actual packet size with noise: `Uniform(300, 600)` bytes
- Rate noise sigma: 0.08
- Max start offset: `Uniform(0, 5)` seconds

## Noise Model

Verified directly from `contrib/nr/examples/cu-du-scaling-study-noise.cc`
(copy: `source/ns3_scenarios/cu-du-scaling-study-noise.cc`).

**Three noise types are implemented, applied once per UE (not per burst,
since there is only one continuous burst per UE — see above):**

1. **Per-UE lognormal rate variation:**
   ```
   actual_rate_bps = nominal_rate_bps * exp(rate_sigma * Z),   Z ~ N(0,1)
   ```
2. **Per-UE packet-size variation** — drawn once from the per-class
   `Uniform(min, max)` range above (mMTC, Web, Mobile, V2X only; VoD and
   Live have no size noise, fixed size).
3. **Per-UE staggered application start offset** — drawn once from the
   per-class `Uniform(0, maxOffset)` range above, added to the base app
   start time (`udpAppStartTime = 400 ms`).

**A fourth noise type (fine-grained inter-packet timing jitter) is NOT
implemented.** ns-3's `OnOffApplication` has no per-packet inter-arrival
jitter hook; implementing it would require a custom application replacing
`OnOffApplication`. This is a documented gap, not a silent omission.

**RNG stream allocation — verified exactly as implemented (per-UE, not
per-class):**
```
base = ue_index * 20
rate-noise stream   = base + 10   (NormalRandomVariable, Mean=0, Variance=1)
size-noise stream   = base + 11   (UniformRandomVariable; classes with fixed
                                    size, i.e. VoD/Live, do not use this stream)
start-offset stream = base + 13   (UniformRandomVariable)
```
Every UE, regardless of traffic class, uses these same three stream-offset
values (`+10`, `+11`, `+13`) relative to its own per-UE `base`. There is
**no per-class stream allocation** — streams are not assigned as one range
per traffic class.

**Master seed:** `RngSeedManager::SetSeed(20260901)`, run 1 — identical
across every scenario variant and UE level in this repository.

## Traffic Volume Targets vs Measured (N=150)

**Primary source: the noise-augmented scenario itself**
(`ns3_cudu_phase_noise/ue_150/per_cell_kpis.csv`, `totalRxBytes=94,978,325`
over the 150-UE run):

| Class  | Target % bytes (assignment spec) | Measured % bytes (noise scenario, N=150) |
|--------|:---:|:---:|
| mMTC   | <1%  | 0.51%  |
| Web    | ~8%  | 8.25%  |
| Mobile | ~10% | 12.19% |
| VoD    | ~35% | 44.76% |
| Live   | ~25% | 31.83% |
| V2X    | ~2%  | 2.48%  |

**For reference only — the non-noise baseline scenario** at the same UE
count and class allocation (`ns3_phase01/per_cell_kpis_validated.csv`,
row `num_ues=150`):

| Class  | Target % bytes | Measured % bytes (non-noise baseline, N=150) |
|--------|:---:|:---:|
| mMTC   | <1%  | 0.74%  |
| Web    | ~8%  | 10.40% |
| Mobile | ~10% | 12.83% |
| VoD    | ~35% | 43.39% |
| Live   | ~25% | 30.18% |
| V2X    | ~2%  | 2.46%  |

Both tables show the same qualitative pattern: VoD/Live consistently
measure above their byte-volume targets, mMTC below. No percentage in
either table has been normalized or adjusted to match the target —
these are the byte counts exactly as measured.

## Important Disclaimer

This traffic model uses ns-3 `OnOffApplication` with statistical noise.
It is explicitly **NOT**:
- Real iperf3 traffic
- Real HTTP, video, or V2X protocol traffic
- Traffic measured from a real deployment

It is labeled **"iperf-inspired / noise-augmented synthetic traffic
model"** throughout this repository (see also
`ns3_cudu_phase_noise/NOISE_MODEL.md` and `README.md`).

## Source Files

- Base (non-noise) model: `source/ns3_scenarios/ue-scaling-study.cc`,
  `source/ns3_scenarios/cu-du-scaling-study.cc`
- Noise model (documented above): `source/ns3_scenarios/cu-du-scaling-study-noise.cc`
- Noise model narrative documentation: `ns3_cudu_phase_noise/NOISE_MODEL.md`
- UE population data: `ns3_cudu_phase_noise/ue_{10,25,50,100,150,200}/cudunoise{N}_traffic_config.tsv`
- Traffic-volume measurement data: `ns3_cudu_phase_noise/ue_150/per_cell_kpis.csv`,
  `ns3_phase01/per_cell_kpis_validated.csv`

# iperf-Inspired / Noise-Augmented Traffic Model — ns-3 CU-DU Ladder

**Terminology note (important for the paper):** this is NOT "iperf3 traffic."
ns-3 UEs/gNB have no OS-level socket layer, so a real `iperf3` process
cannot run against them. The implementation is ns-3's `OnOffApplication`
with statistical parameters chosen to approximate the kind of rate/size/
timing variability `iperf3` would show on real traffic. Call this the
**"iperf-inspired / noise-augmented traffic model"** — never "iperf3
traffic" or "real iperf3" — in any report, slide, or paper.

Source: `contrib/nr/examples/cu-du-scaling-study-noise.cc`. Derived from
the validated `cu-du-scaling-study.cc` baseline, which is **completely
unmodified** — this is a separate file, and its output lives entirely
under `ns3_cudu_phase_noise/`, never overwriting the noise-free baseline
under `ns3_cudu_phase/`.

## What's implemented (3 of the originally-specified 4 noise types)

### 1. Per-UE lognormal rate variation
```
actual_rate = target_rate * exp(sigma * Z),   Z ~ N(0,1)
```
One draw per UE (see "Known limitation" below), class-specific sigma:

| Class | sigma |
|---|---|
| mMTC | 0.25 |
| Web | 0.40 |
| Mobile | 0.35 |
| VoD | 0.05 |
| Live | 0.10 |
| V2X | 0.08 |

### 2. Per-UE packet-size variation
One draw per UE from a per-class distribution:

| Class | Distribution |
|---|---|
| mMTC | Uniform(64, 256) bytes |
| Web | Uniform(512, 1500) bytes (Pareto-like real traffic proxy) |
| Mobile | Uniform(512, 1400) bytes |
| VoD | Fixed 1200 bytes (no variation — MPEG-TS-like) |
| Live | Fixed 1200 bytes (no variation) |
| V2X | Uniform(300, 600) bytes |

### 3. Per-UE staggered application start offset
Uniform per class, applied as `udpAppStartTime + Uniform(0, maxOffset)`:

| Class | Max offset |
|---|---|
| mMTC | 30 s |
| Web | 15 s |
| Mobile | 15 s |
| VoD | 10 s |
| Live | 10 s |
| V2X | 5 s |

### Not implemented: fine-grained inter-packet timing jitter
ns-3's `OnOffApplication` sends packets at a fixed rate implied by
`DataRate`/`PacketSize` for the duration of one continuous ON burst; it has
no built-in per-packet inter-arrival jitter hook. Implementing true IAT
jitter would require a custom traffic-generator application replacing
`OnOffApplication`. Not built — documented as a known gap, not faked.

## Known limitation: single continuous burst, not per-burst noise
The traffic in both the baseline and this noise variant is one continuous
ON period per UE for the whole simulated duration (`OnTime=1e9`,
`OffTime=0`), not a sequence of discrete bursts. The rate-noise formula
above is therefore drawn **once per UE** for its one continuous burst, not
re-drawn at every ON transition as the original per-burst specification
intended. Genuinely time-varying per-burst noise within a UE's flow would
require replacing `OnOffApplication` with a custom app — not implemented.

## Known interaction: fixed offsets vs. fixed 30-second simulation duration

**mMTC's maximum start offset (30 s) equals the entire simulation duration
(30 s).** Combined with the app start time (0.4 s), some mMTC UEs draw
offsets close to 30 s and therefore have very little — in the most extreme
observed case, almost no — active transmission time before the simulation
ends. At N=200, 2 of 80 mMTC UEs drew offsets of 29.40 s and 29.92 s.

This is a real, correctly-implemented consequence of using the originally
specified fixed absolute offsets (30/15/15/10/10/5 s) against a fixed
30-second simulation, not a bug. **By decision, this has been left
as-is and documented rather than changed**, to keep the dataset
reproducible and avoid creating a second, subtly different variant of the
result. If a future run wants offsets scaled to simulation duration
instead of fixed absolute values, that is a one-line change — not applied
here.

## Measured effect on aggregate throughput

Aggregate DL throughput is **12-18% lower** than the noise-free baseline
at every UE count (e.g. N=150: 25.328 Mbps vs. 30.365 Mbps baseline).
Verified root cause: **not** the rate-noise magnitude (per-class actual
rate means land at or slightly above nominal — e.g. VoD actual mean
727,464 bps vs. nominal 725,000 bps) but the staggered start offsets
themselves, which reduce every UE's effective transmission window within
the fixed 30-second simulation (mean offset for the byte-heavy classes —
Web/Mobile/VoD/Live — is 4-8 s out of a ~29.6 s baseline window, a
15-27% reduction in active transmission time per UE). SINR and BLER are
unaffected (the radio channel model is untouched by this traffic-layer
change).

## Random seeds / reproducibility
- Master seed: 20260901 (`RngSeedManager::SetSeed`), run 1.
- Per-UE RNG stream base = `ue_index * 20`.
- Rate-noise stream = base + 10.
- Packet-size-noise stream = base + 11.
- Start-offset stream = base + 13.
- Same seed reproduces the identical traffic realization; a different seed
  produces an independent one.

## Validation performed
- N=1 smoke test: confirmed noise applied and non-trivial (rate
  3000→2474.11 bps, packet size 100→186 bytes, start offset 3.78 s).
- N=10 smoke test: confirmed per-UE, per-class-scaled variation (distinct
  draws per UE, larger spread for higher-sigma classes, VoD/Live
  correctly near-nominal).
- Full ladder (1/10/25/50/100/150/200 UEs): all 7 levels PASS (exit 0,
  100% RRC registration at every level). Wall-clock times closely track
  the noise-free baseline (noise adds negligible compute overhead).

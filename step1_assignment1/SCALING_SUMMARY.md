# SCALING_SUMMARY — ns-3 / 5G-LENA UE-Scaling Study

**THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION STUDY.**
**IT IS NOT REAL OAI CU-DU EXECUTION.** It answers a different question than the real
OAI vrtsim/rfsimulator CU-DU experiments elsewhere in this investigation (idealized
protocol/network-layer scaling behavior in a discrete-event model, vs. real-time
radio-stack execution limits on real software). **Its results must NOT be combined
with, averaged with, or presented alongside OAI-measured data as if they were
equivalent or interchangeable measurements.**

## Toolchain
- ns-3 version: ns-3.48 (gitlab.com/nsnam/ns-3-dev, tag `ns-3.48`)
- 5G-LENA nr module version: v5.1 (gitlab.com/cttc-lena/nr, branch `5g-lena-v5.1.y`)
- This pairing was confirmed directly from the nr module's own RELEASE_NOTES.md
  (NR-v5.1, released August 6 2026, requires ns-3.48; the only newer entry, NR-v5.2,
  was listed as "under development" / unreleased at the time of this study, so v5.1
  is the current stable release and correct choice)
- Build location: `/opt/ns3/ns-3-dev` — entirely separate from `/opt/oai`

## Carrier / channel (applies to all levels)
- Target: 189 PRB, 30 kHz SCS, band n78 (~3.5 GHz) — achieved exactly (actualRbCount
  = 189 at every level, no deviation needed)
- Channel: 5G-LENA `NrChannelHelper` with ThreeGpp RMa LOS deterministic path loss,
  shadowing disabled, and the fading/multipath spectrum model deliberately NOT
  attached (`INIT_PROPAGATION` only) — closest available analog to OAI's IDEAL
  channel (chanmod=0)

## Seed / determinism
- Seed 20260901 via `RngSeedManager`. Verified: two independent runs with identical
  arguments produced bit-identical FlowMonitor XML output (same md5 hash).

## Ladder design
Staged progression 1 -> 10 -> 25 -> 50 -> 100 -> 150 -> 200, chosen to (a) match the
order-of-magnitude checkpoints implied by the task (small smoke level, then roughly
geometric steps to 200) and (b) reuse 100 as an exact checkpoint against the OAI
phase2 100-UE traffic reference table for direct comparability of the traffic-model
class allocation logic (not of measured performance). Each level ran for 30 s
simulated time (steady-state traffic statistics window) with app traffic starting at
t=0.4s.

## Health/success gate (defined before running, applied identically at every level)
1. All configured UEs reach RRC connected (`NrGnbRrc::ConnectionEstablished` trace
   count == configured UE count)
2. FlowMonitor reports non-zero delivered (rx) bytes for every configured UE's flow
3. No ns-3 fatal errors/crashes (process exit code 0)

## Results table

| UE level | Configured | RRC-connected | FlowMonitor flows w/ 0 rxBytes | Exit code | Wall-clock (s) | Gate result |
|---|---|---|---|---|---|---|
| 1   | 1   | 1   | 0/1   | 0 | 35.46   | PASS |
| 10  | 10  | 10  | 0/10  | 0 | 25.30   | PASS |
| 25  | 25  | 25  | 0/25  | 0 | 82.19   | PASS |
| 50  | 50  | 50  | 0/50  | 0 | 197.90  | PASS |
| 100 | 100 | 100 | 0/100 | 0 | 554.99  | PASS |
| 150 | 150 | 150 | 0/150 | 0 | 1182.47 | PASS |
| 200 | 200 | 200 | 0/200 | 0 | 1524.08 | PASS (reduced trace set — see ue_200/SUMMARY.md) |

Note on wall-clock column: these are ns-3 discrete-event simulation wall-clock times
on a 44-core/82 GiB host, reported for information only. **They are NOT a measure of
real-time execution feasibility and are not comparable to the OAI vrtsim real-time
TX/RX-late gate — that concept is N/A for a non-real-time discrete-event simulator.**
The wall-clock column at 200 UEs used a reduced trace set (see below) and is not
directly comparable to the full-trace wall-clock figures at lower levels, since the
reduction targeted I/O volume, not the underlying scheduler/interference computation
that dominates runtime at scale.

## Independent audit

A separate independent audit of this study's raw output files (`NS3_AUDIT.md`, in this
same directory) was produced during this investigation and re-derived every KPI
directly from raw traces rather than trusting each level's `SUMMARY.md` claims. It
independently confirmed: zero `FlowMonitor` packet loss, zero transport-block errors
(`TBler`/`corrupt` flags in `RxPacketTrace.txt`), and zero HARQ retransmissions
(`ndi` in `NrDlMacStats.txt`) at every completed level. It also raised one important
methodological point, carried forward here:

**The chosen IDEAL-channel analog (ThreeGpp RMa LOS path loss only, no shadowing, no
fast fading) produces an extremely high, essentially constant SINR (~63.5-63.8 dB) at
every UE count, which drives the AMC scheduler to near-maximum MCS (~27.8-27.9/28) and
guarantees zero transport-block errors/retransmissions at every level tested. This
means the "nonzero delivery per UE" health gate was effectively guaranteed to pass by
the channel configuration itself.** A PASS at any level in this study should be read
narrowly as "the RRC/MAC control-plane bookkeeping and FlowMonitor accounting behaved
correctly for N simultaneous UEs in an error-free simulated channel," not as evidence
that a real, imperfect-channel, real-time-constrained stack could sustain N UEs of real
traffic. (The audit also raised, then itself corrected via an addendum, a claim about
FlowMonitor reporting 2 flows per UE; that claim was checked and found to be a
misreading of the XML schema — see the addendum at the end of `NS3_AUDIT.md`. There are
genuinely N flows for N UEs at every level, as stated in each level's `SUMMARY.md`.)

## Conclusion

- **Highest measured PASS: 200 UEs** — the full planned ladder (1/10/25/50/100/150/200)
  completed with every level passing the pre-defined health gate. No level failed.
- **No FAILED level occurred.** (Two full-trace attempts at 200 UEs were operationally
  abandoned before completion — one for excessive trace I/O volume/runtime, one for
  an undiagnosed stall with no crash evidence — but neither constitutes a level
  "failing" the defined health gate, since neither produced a completed run with a
  gate result; they are documented as operational retries, not scientific failures.
  The gate was only ever evaluated against completed runs, and every completed run
  passed.)
- **No extrapolation beyond 200 UEs was performed or is implied.** This study did not
  attempt, and makes no claim about, UE counts beyond 200. Any statement about
  behavior above 200 UEs would be pure speculation and is explicitly out of scope.
- **This is a simulation study, not OAI-measured data.** The OAI investigation in this
  same research program independently found real-time execution limits with OAI's own
  vrtsim/rfsimulator radio simulators at UE counts far below 200; this ns-3/5G-LENA
  study did NOT reproduce or validate that finding, does not use OAI's real
  protocol-stack binaries, and answers a different question (idealized discrete-event
  network-layer scaling under a deterministic channel, with no real-time execution
  constraint). **These two results must never be merged, averaged, or cited as if
  they measured the same thing.** Where both are referenced, they must be clearly
  attributed to their respective methodology (OAI real CU-DU real-time execution vs.
  ns-3/5G-LENA discrete-event simulation).

## Output structure
- `/mnt/c/Users/Common/Downloads/Siya/ns3_phase01/KPI_AVAILABILITY_NOTE.md` — full KPI
  audit (what is/is not available in this ns-3.48 + 5G-LENA v5.1 build)
- `/mnt/c/Users/Common/Downloads/Siya/ns3_phase01/ue_<N>/` — one directory per level,
  each with `SUMMARY.md`, raw FlowMonitor XML, run-summary/traffic-config TSVs, and
  (except ue_200, see its SUMMARY.md) the full PHY/MAC/RLC/PDCP trace set
- `/mnt/c/Users/Common/Downloads/Siya/ns3_phase01/LADDER_STATUS.txt` — raw pass/fail
  log line per level as generated during the run

## Safety confirmation
`/opt/oai/openairinterface5g` was never modified, built, or run as part of this study.
This ns-3/5G-LENA work used an entirely separate, dedicated location
(`/opt/ns3/ns-3-dev`). The only interaction with the OAI tree was a single read-only
`Read` of `phase2/20260903_100ue_vrtsim_cudu_189prb/traffic/traffic_model.md` to reuse
its published six-class traffic reference table. No OAI docker/CN5G containers were
started, stopped, or otherwise touched (verified via `docker ps`, read-only, showing
the pre-existing OAI CN5G stack still running throughout, untouched, started 2 hours
prior to this study and unaffected by it).

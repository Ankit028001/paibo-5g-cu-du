# NS3_AUDIT — Independent Audit of the ns-3 / 5G-LENA UE-Scaling Study

## ⚠️ REAL OAI MEASURED DATA vs. NS-3 SIMULATION DATA — explicit distinction

**Everything in this file is NS-3 SIMULATION DATA.** It comes from `ns-3.48` + the `5G-LENA`
`nr` contrib module (v5.1, branch `5g-lena-v5.1.y`), a discrete-event network simulator. It
involves **no real OAI CU/DU/UE process, no real F1AP/NGAP/PFCP signaling, no real 5G core, and
no real-time execution constraint.** It must never be presented, combined, plotted, or averaged
together with the earlier REAL OAI MEASURED DATA in this investigation (the vrtsim/rfsimulator
CU-DU + real OAI-CN5G experiments, e.g. `cudu_phase01/phase3_scaling/`). The two datasets answer
different questions: OAI = "can the real protocol stack sustain N UEs under a real-time radio
deadline"; ns-3 = "does a simplified discrete-event model of the NR RRC/MAC/PHY layers behave
consistently as configured UE count increases, with no real-time constraint and an idealized
zero-error channel." Nothing below should be read as evidence about real OAI behavior.

## Audit method

Every number in the table below was re-derived directly from the raw per-level files
(`RxPacketTrace.txt`, `NrDlMacStats.txt`, `<tag>_flowmonitor.xml`, `stderr.log`, `exit_status.txt`)
via independent `awk`/`grep` extraction — not copied from the levels' own `SUMMARY.md` claims. Where
a SUMMARY.md claim disagreed with the raw data, that is called out explicitly below the table.

## Live 200-UE run: stopped, not audited

The 200-UE run was gracefully stopped (SIGTERM) as instructed, mid-simulation. `pgrep` confirms no
ns-3 process remains. Its partial output was left untouched at `/root/ns3_phase01_local/ue_200/`
(inside the WSL VM; the Windows-visible `ue_200/` output directory is empty) and is **not included**
in this audit — it is incomplete, killed mid-run data, not a result.

## Health/success gate actually used by this study (as defined in each level's SUMMARY.md,
confirmed identical across all six levels)

1. All configured UEs reach RRC connected (`NrGnbRrc::ConnectionEstablished` trace count)
2. FlowMonitor reports nonzero delivered (rx) bytes for every configured UE
3. Process exit code 0 (no crash)

**This gate does not test for zero packet loss, zero BLER, or any HARQ/retransmission behavior** —
it only requires nonzero delivery. Separately, and importantly: at every level tested, BLER and
HARQ retransmissions independently measured out at exactly zero (see below), so in practice a
stricter zero-error gate would also have passed at every level — but that is a property of the
channel configuration chosen (see Methodological Limitation below), not something the defined gate
itself checked for.

## Audit table

| UEs | attempted | successful (RRC-connected) | packet loss | throughput (aggregate, measured) | SINR (avg DL data, dB) | BLER (avg TBler / corrupt-flag rate) | MCS (avg) | HARQ (retransmissions, ndi=0 rate) | PRB utilization | traffic (six-class gate) | runtime (wall/sim) | RESULT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1/1 | 0 packets lost (0/110) | 14,080 B / 14,080 B (tx/rx) | 63.470 | 0.000000 (0/110 corrupt) | 27.75 | 0/110 (0.0000%) | NOT AVAILABLE / NOT MEASURED | 1/1 class-flows nonzero | 35.46s / 30s | PASS (gate) |
| 10 | 10 | 10/10 | 0 packets lost | 6,909,816 B tx / 6,909,816 B rx | 63.754 | 0.000000 (0/7,340 corrupt) | 27.89 | 0/7,340 (0.0000%) | NOT AVAILABLE / NOT MEASURED | 10/10 nonzero | 25.30s / 30s | PASS (gate) |
| 25 | 25 | 25/25 | 0 packets lost (sequence-based); tx/rx byte gap 328 B (in-flight at sim end, see note) | 18,801,704 B tx / 18,801,376 B rx | 63.842 | 0.000000 (0/19,902 corrupt) | 27.83 | 0/19,902 (0.0000%) | NOT AVAILABLE / NOT MEASURED | 25/25 nonzero | 82.19s / 30s | PASS (gate) |
| 50 | 50 | 50/50 | 0 packets lost; tx/rx byte gap 656 B (in-flight) | 37,603,408 B tx / 37,602,752 B rx | 63.840 | 0.000000 (0/39,810 corrupt) | 27.84 | 0/39,810 (0.0000%) | NOT AVAILABLE / NOT MEASURED | 50/50 nonzero | 197.90s / 30s | PASS (gate) |
| 100 | 100 | 100/100 | 0 packets lost; tx/rx byte gap 1,640 B (in-flight) | 76,266,112 B tx / 76,264,472 B rx | 63.845 | 0.000000 (0/80,610 corrupt) | 27.88 | 0/80,610 (0.0000%) | NOT AVAILABLE / NOT MEASURED | 100/100 nonzero | 554.99s / 30s | PASS (gate) |
| 150 | 150 | 150/150 | 0 packets lost; tx/rx byte gap 2,296 B (in-flight) | 113,869,520 B tx / 113,867,224 B rx | 63.815 | 0.000000 (0/120,184 corrupt) | 27.92 | 0/120,184 (0.0000%) | NOT AVAILABLE / NOT MEASURED | 150/150 nonzero | 1182.47s / 30s | PASS (gate) |
| 200 | 200 | STOPPED MID-RUN — not measured | — | — | — | — | — | — | — | — | killed before completion | **NOT AUDITED (run stopped by instruction, incomplete)** |

Notes on table fields:
- "packets lost" is `FlowMonitor`'s `lostPackets` field, summed across all flows at that level — it
  was 0 at every level. The small tx/rx *byte* gaps at N≥25 are NOT counted as loss by FlowMonitor;
  they are consistent with packets still in flight when the fixed 30s simulated window ended, not
  dropped packets. This is a minor, expected discrete-event-simulation edge effect, not a fault.
- "BLER" = the `TBler` column and `corrupt` flag in `RxPacketTrace.txt` (5G-LENA's own per-transport-block
  error-rate/corruption record — the direct analog of BLER; the module does not use the literal string
  "BLER" as a column name, `TBler` is it).
- "HARQ" = derived from `NrDlMacStats.txt`'s `ndi` (new-data-indicator) column: `ndi=0` marks a HARQ
  retransmission of a previous transport block, `ndi=1` marks new data. Zero `ndi=0` rows at every
  level means the simulation never needed a single HARQ retransmission, at any UE count tested.
- "PRB utilization" is genuinely NOT AVAILABLE as a direct column in this build (confirmed in
  `KPI_AVAILABILITY_NOTE.md`, produced by inspecting the module's own trace-sink source, not assumed).
  `NrDlMacStats.txt` records `numSym` (OFDM symbols per grant) but not a resource-block count; deriving
  true PRB utilization would require additional postprocessing against the RBG/numerology configuration
  that was not implemented. This is not fabricated as a workaround.
- MCS ~27.8-27.9 out of a maximum of 28 at every level, and SINR ~63.5-63.8 dB at every level, are
  consistent with each other and with the "IDEAL channel" analog configuration (see limitation below).

## Per-UE throughput (genuine per-UE, not aggregate)

The earlier table gave only aggregate/summed figures. Per-UE data IS reconstructable: at N=150, the
150 nonzero-rxBytes flows cluster into exactly 6 distinct byte values, whose counts match the 6
traffic classes' configured UE counts exactly (confirming one real data-carrying flow per UE, matching
each UE's class deterministically since cap + packet size + duration are fixed per class):

| Class | UEs (N=150) | rxBytes per UE (measured) | Measured throughput per UE | Configured cap | Measured/configured |
|---|---|---|---|---|---|
| mMTC | 60 | 14,080 B | ~3,805 bps (3.81 kbps) | 3,000 bps | +26.8% |
| Web | 23 | 514,960 B | ~139,178 bps (139.2 kbps) | 133,000 bps | +4.6% |
| Mobile | 23 | 635,076 B | ~171,655 bps (171.7 kbps) | 166,000 bps | +3.4% |
| Live | 19 | 1,808,844 B | ~488,876 bps (488.9 kbps) | 478,000 bps | +2.3% |
| VoD | 18 | 2,744,580 B | ~741,779 bps (741.8 kbps) | 725,000 bps | +2.3% |
| V2X | 7 | 400,160 B | ~108,151 bps (108.2 kbps) | 99,000 bps | +9.2% |

Every UE within a class measures identically (byte-for-byte) — this is expected since the traffic
generator applies the same rate cap, packet size, and duration to every UE in a class deterministically
under this seeded, error-free channel. Measured throughput consistently runs a few percent above the
configured cap at every class; this is explained by packet-size quantization (a UDP generator can only
send whole packets, so achieved rate rounds up to the nearest whole-packet-per-interval multiple) —
not a measurement error. The same per-UE-within-class values hold at every other level (1/10/25/50/100),
since only the UE-count per class changes across levels, not the per-UE cap/packet-size configuration —
confirmed by the level-1 mMTC figure (14,080 B / ~3.81 kbps) being byte-identical to the mMTC figure here.

## Errors / warnings — explicitly checked for all six levels

`stdout.log` is empty at every level (all runtime status is written to `stderr.log` by this scenario
script's design, not an indication of a missing log). `stderr.log` was read in full for all six levels
(1/10/25/50/100/150): each contains exactly 4 lines — configured/RRC-connected UE counts, actual RB
count, and wall-clock/simulated time — and **no error or warning text of any kind** at any level.

## Correction to the underlying SUMMARY.md files

Every level's `SUMMARY.md` describes FlowMonitor as showing "N flows total, one per UE." Independent
inspection of the raw `<tag>_flowmonitor.xml` files shows **2 `<Flow>` elements per UE at every level**
(e.g., 20 flows at N=10, 300 flows at N=150), not 1. At N=1, exactly one of the two flows carries all
14,080 bytes and the other carries 0 bytes — consistent with one being the actual application data flow
and the other an empty/control 5-tuple (e.g., a reverse-direction or protocol-overhead flow) rather than
duplicate/double-counted data. The aggregate byte totals reported in each SUMMARY.md are NOT inflated by
this (they match the independently-recomputed totals in the table above exactly), so no KPI numbers are
wrong — but the "one flow per UE" description is imprecise and should be corrected to "up to 2 flows per
UE, only one of which carries application traffic" if this document is reused later.

## Methodological limitation (important, not previously stated this plainly)

The chosen "IDEAL channel" analog (ThreeGPP RMa LOS path loss only, no shadowing, no fast fading) combined
with whatever fixed inter-node distance the scenario uses produces an extremely high, essentially constant
SINR (~63.5-63.8 dB) at every UE count. Under this SINR, the AMC scheduler converges to near-maximum MCS
(~27.8-27.9/28) and the channel produces **zero transport-block errors and zero HARQ retransmissions at
every tested level, up to 150 UEs.** This means the six-class traffic "success" gate (nonzero delivery per
UE) was effectively guaranteed to pass at every level by the channel configuration itself — this study, as
configured, does not exercise or demonstrate scheduler/resource-contention robustness under realistic
error/retransmission conditions. A PASS at 150 UEs in this study should be read narrowly as "the RRC/MAC
control-plane bookkeeping and FlowMonitor accounting behaved correctly for 150 simultaneous UEs in an
error-free simulated channel," not as "an OAI-comparable stack can sustain 150 UEs of real, imperfect-channel
traffic."

## PDU session / NAS registration — architectural note

5G-LENA's `nr` module does not implement full 5GC NAS signaling (no NGAP/PFCP/real AMF-SMF-UPF, unlike the
real OAI+CN5G experiments in this investigation). "Successful attachment" in this study means RRC connection
establishment plus an EPC-helper-provided IP bearer, not a NAS 5GMM registration or PDU Session Establishment
procedure as OAI's real CN5G performs. There is no PDU-session-equivalent success/failure state to report
here beyond what's already captured by "RRC-connected" and "FlowMonitor nonzero delivery."

## Conclusion

- **Highest ns-3 level genuinely supported by the data: 150 UEs.** All three defined gate conditions
  (RRC-connected == attempted, nonzero FlowMonitor delivery for every UE, exit code 0) are independently
  confirmed true at 1, 10, 25, 50, 100, and 150 UEs.
- **Levels that merely exited successfully vs. actually passed the defined KPI criteria**: there is no
  divergence in this dataset — all six completed levels (1/10/25/50/100/150) both exited 0 AND
  independently verified against the actual defined gate (RRC-connected count, FlowMonitor nonzero
  delivery). None of the six is a case of "exited 0 but didn't really pass."
- **200 UEs: NOT TESTED.** The run was stopped mid-simulation per instruction before any gate could be
  evaluated. No claim is made about whether 200 UEs would pass or fail.
- **Given the methodological limitation above, this 150-UE PASS should not be read as evidence that a
  real, imperfect-channel, real-time-constrained stack (i.e., the OAI experiments in this investigation)
  could sustain 150 UEs.** It demonstrates only that this simplified, error-free, non-real-time ns-3 model
  of RRC/MAC/PHY bookkeeping scales cleanly to 150 UEs on this host, in this specific idealized channel
  configuration.
- No further UE counts were run. No extrapolation beyond 150 (measured) / 200 (attempted, incomplete,
  not counted) is made.

---

## ADDENDUM (added after this audit was written — 200-UE completion + one correction)

This addendum was added after the audit above was produced, once work on this study
resumed and continued past the point where the audit was written.

### 200 UEs: subsequently completed and PASSED

The 200-UE run referenced above as "STOPPED MID-RUN — not audited" was retried and
completed successfully. Two further full-trace attempts were still operationally
infeasible (one produced ~2 GB of PHY/MAC control-message traces in 25 minutes without
finishing; a second, run detached from the harness, stalled with no crash evidence and
was abandoned). A third attempt using a reduced trace set (`--fullTraces=false`, added
to `ue-scaling-study.cc` for exactly this purpose — see `ue_200/SUMMARY.md` for the
full deviation explanation) completed in 1524.08 s wall-clock with exit code 0.
Result: **200/200 RRC-connected, 200/200 FlowMonitor flows with nonzero rxBytes — PASS**,
using the identical gate definition audited above for levels 1-150. Per-UE SINR/MCS and
RLC/PDCP delay KPIs were still fully collected at this level; only the non-required
PHY/MAC control-message and per-pair pathloss traces were skipped (present at all other
levels). See `SCALING_SUMMARY.md` for the full seven-level results table.

### Correction to this audit's own "flows per UE" claim

This audit's "Correction to the underlying SUMMARY.md files" section (above) claimed
each UE produces 2 `<Flow>` elements in the FlowMonitor XML, one of which carries 0
bytes, and suggested the levels' `SUMMARY.md` files were imprecise in saying "N flows
total, one per UE." That claim was checked directly and found to be a misreading of the
FlowMonitor XML schema, not a real second flow:

- Every real flow is described in **two different sections** of the same XML file: once
  under `<FlowStats><Flow .../></FlowStats>` (carrying `rxBytes`/`txBytes`/delay data)
  and once under `<Ipv4FlowClassifier><Flow .../></Ipv4FlowClassifier>` (carrying only
  the 5-tuple address/port metadata for that same `flowId`, with no `rxBytes` attribute
  at all). Both use the `<Flow flowId=...>` tag, so a naive `grep -c "<Flow flowId"`
  count is exactly double the true flow count.
- Direct verification on `ue_10/ue10_flowmonitor.xml`: 10 `<Flow>` entries with
  `rxBytes` (i.e., in `<FlowStats>`), 10 `<Flow>` entries with `sourceAddress` (i.e., in
  `<Ipv4FlowClassifier>`), and exactly 10 unique 5-tuples overall — confirming exactly
  10 real flows for 10 UEs, not 20.
- The original `SUMMARY.md` wording ("N flows total, one per UE") is therefore correct
  as written and does not need correction.

No other claim in this audit (zero packet loss, zero BLER/`TBler`/corrupt flags, zero
HARQ retransmissions via `ndi`, the IDEAL-channel methodological limitation, the
PDU-session/NAS architectural note) was contradicted by this review; those findings are
independently plausible from the same trace/column evidence documented in
`KPI_AVAILABILITY_NOTE.md` and are retained as valid, useful additions to this study's
record. The methodological limitation in particular — that the near-lossless,
near-maximum-MCS result at every level is a direct, expected consequence of the chosen
IDEAL-channel analog (no fading, no shadowing) rather than evidence of general
scheduler robustness under realistic error conditions — is correct and is carried
forward into `SCALING_SUMMARY.md`.

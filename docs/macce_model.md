# Modeled MAC-CE Adaptation Event — Measurement Methodology

## Important disclaimer

This experiment models a MAC-CE-triggered adaptation event
in ns-3. It does NOT implement or measure a real 3GPP MAC-CE.
It does NOT perform a real RLC AM/UM reconfiguration.

## What was modeled

At a fixed simulation time (settle_time + 5 seconds), a
MAC-CE-triggered RLC mode adaptation event is modeled for
all UEs. The adaptation is assumed to take effect in the
next 30 kHz NR slot:

  macce_latency_ms = 0.5 ms  (1 slot at 30 kHz SCS)

This is a modeled next-slot application interval, not a
measured over-the-air MAC-CE latency.

## RRC baseline values (measured from ns-3)

The comparison baseline comes from the validated
Baseline_NonPAIBO_Ladder dataset (ns-3 RRC establishment
time measured from the simulation):

| N UEs | RRC baseline (ms) | MAC-CE model (ms) | Saving % |
|-------|-------------------|-------------------|----------|
| 1     | 18.04             | 0.5               | 97.2%    |
| 10    | 18.04             | 0.5               | 97.2%    |
| 25    | 20.48             | 0.5               | 97.6%    |
| 50    | 25.13             | 0.5               | 98.0%    |
| 100   | 34.43             | 0.5               | 98.5%    |
| 150   | 45.02             | 0.5               | 98.9%    |
| 200   | 53.16             | 0.5               | 99.1%    |

## Key finding

The modeled saving increases with UE count because the RRC
baseline grows with scheduler load while the MAC-CE interval
remains constant. This supports the PAIBO design rationale:
at scale, MAC-CE lightweight signaling becomes proportionally
more valuable.

## Terminology used throughout

All CSV files and outputs use:
  label = "modeled_macce_next_slot_interval —
           NOT real OAI MAC-CE"

The UM → AM transition in the model is a labeled modeling
choice, not a real RLC reconfiguration.

## Source file

  source/ns3_scenarios/cu-du-macce-model-study.cc

## Seed

  20260901 (all runs)

## Simulation environment

  ns-3.48 + 5G-LENA v5.1
  30 kHz SCS, 189 PRB, band n78
  CU-DU topology (topological split, not functional F1AP)

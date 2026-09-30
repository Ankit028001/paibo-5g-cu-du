# Baseline Data Integrity — ns-3 / 5G-LENA CU-DU Ladder

**Baseline — ns-3 / 5G-LENA simulation, PAIBO not implemented.**

Checked, per UE level, for presence of: `per_ue_kpis.csv`, `per_cell_kpis.csv`,
all 3 plots (`plot_per_ue_avg_sinr.png`, `plot_per_ue_throughput.png`,
`plot_random_ue_sinr_timeseries.png`), `cudu{N}_run_summary.tsv`,
`cudu{N}_traffic_config.tsv`, `cudu{N}_flowmonitor.xml`, `exit_status.txt`
(and that it records `exitCode=0`). No simulation was re-run for this check;
this is a read-only audit of the already-completed, previously validated
ladder under `ns3_cudu_phase/`.

| UE Level | Files Present | Exit Code 0 | Registration | Agg. DL Throughput (Mbps) | Mean SINR (dB) | Mean MCS | Result |
|---|---|---|---|---|---|---|---|
| 1 | PASS | PASS | 1/1 | 0.004 | 63.4703 | 27.7455 | **PASS** |
| 10 | PASS | PASS | 10/10 | 1.843 | 63.7579 | 27.7392 | **PASS** |
| 25 | PASS | PASS | 25/25 | 5.014 | 63.7993 | 27.5513 | **PASS** |
| 50 | PASS | PASS | 50/50 | 10.027 | 63.8078 | 27.5730 | **PASS** |
| 100 | PASS | PASS | 100/100 | 20.337 | 63.8233 | 27.7394 | **PASS** |
| 150 | PASS | PASS | 150/150 | 30.365 | 63.8102 | 27.8531 | **PASS** |
| 200 | PASS | PASS | 200/200 | 40.674 | 63.8146 | NA (see note) | **PASS** |

**Note on N=200 MCS:** blank/NA because that level ran with `--fullTraces=false`
(the MAC scheduler trace, `NrDlMacStats.txt`, is not written at that level to
control I/O volume at the top of the ladder — a documented run-configuration
choice, not a missing/failed measurement). All other required files and KPIs
are present and PASS at N=200.

## Overall result

**7/7 UE levels PASS.** No missing files, no non-zero exit codes, 100%
UE registration at every level. No simulation was re-run to produce this
report — all data already existed under `ns3_cudu_phase/ue_{1,10,25,50,100,150,200}/`.

# KPI Availability Matrix

THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT SIMULATION DATASET. IT IS NOT REAL OAI CU-DU EXECUTION.

| KPI | Available? | Source | Value at N=150 | Notes |
|---|---|---|---|---|
| dl_tput_mbps | YES | FlowMonitor XML | 30.365 | aggregate cell value shown |
| ul_tput_mbps | YES (=0) | FlowMonitor XML | 0.0 | DL-only traffic model, no UL app traffic generated |
| packet_loss_pct | YES | FlowMonitor XML | NA | per-UE column; see per_ue_kpis_validated.csv |
| mean_jitter_ms | YES | FlowMonitor XML | NA | per-UE column |
| mean_e2e_delay_ms | YES | FlowMonitor XML | NA | per-UE column |
| mean_dl_sinr_db | YES | RxPacketTrace.txt | 63.81 | requires RNTI<->IMSI map from NrDlRlcStatsE2E.txt |
| mean_dl_bler_pct | YES | RxPacketTrace.txt (corrupt flag) | 0.0 |  |
| mean_dl_mcs | YES | RxPacketTrace.txt | 27.853 |  |
| harq_retx_count | YES | RxPacketTrace.txt (rv != 0) | NA | per-UE column |
| traffic_class | YES | simulation config (traffic_config.tsv) | NA | ground-truth label, not an inferred feature |
| target_dl_rate_mbps | YES | simulation config | NA | MODEL value, not measured |
| num_ues_configured | YES | run_summary.tsv | 150 |  |
| attach_time_s | NO | NA | NA | NOT MEASURED — ue-scaling-study.cc only writes an aggregate rrcConnectedCount, not a per-UE attach timestamp |
| pdu_session_established | NO | NA | NA | NOT MEASURED — 5G-LENA's NrPointToPointEpcHelper is an LTE-EPC-style core with no NAS/PDU-session concept, unlike real 5GC |
| bearer_setup_latency_ms | NO | NA | NA | NOT MEASURED — PAIBO Bearer Hint/shadow-bearer signaling not implemented in ns-3 simulation |
| active_drb_count | NO | NA | NA | NOT MEASURED — DRB count not exposed in 5G-LENA FlowMonitor |
| macce_adaptation_latency_ms | NO | NA | NA | NOT MEASURED — MAC-CE adaptation requires OAI real stack |
| bip_accuracy | NO | NA | NA | NOT MEASURED — PAIBO BIP not implemented in ns-3 simulation |
| bip_false_positive_rate | NO | NA | NA | NOT MEASURED — PAIBO BIP not implemented in ns-3 simulation |
| bip_missed_prediction_rate | NO | NA | NA | NOT MEASURED — PAIBO BIP not implemented in ns-3 simulation |
| mean_ul_sinr_db | NO | NA | NA | NOT MEASURED — uplink data PHY SINR trace was not enabled in this scenario |
| mean_ul_mcs | NO | NA | NA | NOT MEASURED — NrUlMacStats.txt rows in this scenario are minimal/control-only grants (fixed tbSize, mcs=0), not representative UL data MCS since no UL application traffic was configured |
| mean_rsrp_dbm | NO | NA | NA | NOT MEASURED — RSRP is not a native 5G-LENA trace field in this build |
| mean_cqi | NO | NA | NA | NOT MEASURED — not exposed as a validated per-UE field in this validation pass |
| prb_utilization_pct | NO | NA | NA | NOT MEASURED — per-UE PRB count is not a direct native trace field (see KPI_AVAILABILITY_NOTE.md) |

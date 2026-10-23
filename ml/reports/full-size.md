# Multi-seed synthetic ranking experiment

Seeds: [42, 43, 44]

| Evaluation | Policy | NDCG@3 mean ± sd | NDCG@5 mean ± sd |
|---|---|---:|---:|
| observed_all_shown | A_random | 0.3329 ± 0.0100 | 0.3889 ± 0.0094 |
| observed_all_shown | B_request_and_burden | 0.3882 ± 0.0087 | 0.4282 ± 0.0086 |
| observed_all_shown | C_preliminary_rules | 0.3878 ± 0.0083 | 0.4280 ± 0.0075 |
| observed_all_shown | ideal | 0.4044 ± 0.0052 | 0.4368 ± 0.0058 |
| observed_all_shown | model | 0.4219 ± 0.0109 | 0.4501 ± 0.0088 |
| observed_all_shown | candidate_only | 0.3899 ± 0.0090 | 0.4272 ± 0.0058 |
| observed_all_shown | shuffled_labels | 0.3371 ± 0.0062 | 0.3910 ± 0.0047 |
| observed_positive_queries | A_random | 0.5568 ± 0.0067 | 0.6473 ± 0.0045 |
| observed_positive_queries | B_request_and_burden | 0.6425 ± 0.0084 | 0.7088 ± 0.0068 |
| observed_positive_queries | C_preliminary_rules | 0.6418 ± 0.0073 | 0.7083 ± 0.0050 |
| observed_positive_queries | ideal | 0.6693 ± 0.0027 | 0.7230 ± 0.0018 |
| observed_positive_queries | model | 0.6983 ± 0.0144 | 0.7450 ± 0.0104 |
| observed_positive_queries | candidate_only | 0.6454 ± 0.0131 | 0.7071 ± 0.0097 |
| observed_positive_queries | shuffled_labels | 0.5580 ± 0.0061 | 0.6472 ± 0.0030 |
| oracle_all_candidates | A_random | 0.7529 ± 0.0063 | 0.7714 ± 0.0054 |
| oracle_all_candidates | B_request_and_burden | 0.8017 ± 0.0051 | 0.8164 ± 0.0049 |
| oracle_all_candidates | C_preliminary_rules | 0.8184 ± 0.0048 | 0.8308 ± 0.0040 |
| oracle_all_candidates | ideal | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |
| oracle_all_candidates | model | 0.8569 ± 0.0008 | 0.8685 ± 0.0030 |
| oracle_all_candidates | candidate_only | 0.7696 ± 0.0110 | 0.7940 ± 0.0045 |
| oracle_all_candidates | shuffled_labels | 0.7414 ± 0.0179 | 0.7626 ± 0.0148 |

Offline synthetic experiment; not approved for deployment.
Observed metrics only use shown candidates. Oracle metrics use all eligible candidates.
All-zero observed queries contribute zero in observed_all_shown.
Full feature importance, subgroup diagnostics, limitations and parameters: summary.json.

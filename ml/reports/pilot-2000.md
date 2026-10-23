# Multi-seed synthetic ranking experiment

Seeds: [42, 43, 44]

| Evaluation | Policy | NDCG@3 mean ± sd | NDCG@5 mean ± sd |
|---|---|---:|---:|
| observed_all_shown | A_random | 0.3399 ± 0.0144 | 0.3959 ± 0.0121 |
| observed_all_shown | B_request_and_burden | 0.3927 ± 0.0245 | 0.4278 ± 0.0215 |
| observed_all_shown | C_preliminary_rules | 0.3873 ± 0.0245 | 0.4237 ± 0.0223 |
| observed_all_shown | ideal | 0.4042 ± 0.0203 | 0.4393 ± 0.0208 |
| observed_all_shown | model | 0.4052 ± 0.0133 | 0.4388 ± 0.0171 |
| observed_all_shown | candidate_only | 0.3663 ± 0.0159 | 0.4090 ± 0.0169 |
| observed_all_shown | shuffled_labels | 0.3392 ± 0.0235 | 0.3877 ± 0.0194 |
| observed_positive_queries | A_random | 0.5393 ± 0.0353 | 0.6435 ± 0.0139 |
| observed_positive_queries | B_request_and_burden | 0.6480 ± 0.0201 | 0.7060 ± 0.0173 |
| observed_positive_queries | C_preliminary_rules | 0.6390 ± 0.0189 | 0.6992 ± 0.0170 |
| observed_positive_queries | ideal | 0.6670 ± 0.0091 | 0.7251 ± 0.0098 |
| observed_positive_queries | model | 0.6690 ± 0.0049 | 0.7244 ± 0.0012 |
| observed_positive_queries | candidate_only | 0.6048 ± 0.0180 | 0.6752 ± 0.0126 |
| observed_positive_queries | shuffled_labels | 0.5598 ± 0.0287 | 0.6399 ± 0.0132 |
| oracle_all_candidates | A_random | 0.7513 ± 0.0128 | 0.7646 ± 0.0166 |
| oracle_all_candidates | B_request_and_burden | 0.7827 ± 0.0128 | 0.7961 ± 0.0132 |
| oracle_all_candidates | C_preliminary_rules | 0.8005 ± 0.0136 | 0.8107 ± 0.0137 |
| oracle_all_candidates | ideal | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |
| oracle_all_candidates | model | 0.8337 ± 0.0317 | 0.8405 ± 0.0279 |
| oracle_all_candidates | candidate_only | 0.7649 ± 0.0146 | 0.7896 ± 0.0065 |
| oracle_all_candidates | shuffled_labels | 0.7536 ± 0.0213 | 0.7721 ± 0.0154 |

Offline synthetic experiment; not approved for deployment.
Observed metrics only use shown candidates. Oracle metrics use all eligible candidates.
All-zero observed queries contribute zero in observed_all_shown.
Full feature importance, subgroup diagnostics, limitations and parameters: summary.json.

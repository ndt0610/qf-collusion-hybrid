# Phase 1 data and graph profile

Bảng này chỉ định dạng lại [CSV Phase 1](phase1_data_graph_profile.csv) đã lưu; không chạy lại `profile_data.py`. Các ô `—` là ô trống trong CSV. Bốn vòng thuộc Arbitrum chain 42161; SHA-256 nguồn nằm trong [manifest dữ liệu](../../data/manifests/sources.json).

## Dữ liệu sau lọc

Các cột dữ liệu dưới đây trùng nhau giữa G1 và G2 của từng vòng; mỗi vòng hiển thị một lần.

| round_id | rows_total | rows_kept | usd_nonpositive | donors | projects | usd_kept | approved_application_count | application_not_approved | raw_approved_join_ratio | raw_rows_match_metadata | raw_donors_match_metadata | raw_usd_matches_metadata |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 13197 | 13187 | 10 | 3750 | 46 | 50404.68574 | 46 | — | 1.0 | True | True | True |
| 29 | 9314 | 9276 | 38 | 2261 | 129 | 57961.50639 | 129 | — | 1.0 | True | True | True |
| 865 | 12883 | 12865 | 2 | 4411 | 56 | 25999.09904 | 56 | 16 | 0.998758053248467 | True | True | True |
| 867 | 11059 | 11052 | 2 | 3861 | 142 | 41524.90517 | 142 | 5 | 0.9995478795551135 | True | True | True |

## Đồ thị đồng đóng góp

| round_id | graph_method | pair_work | candidate_undirected | edges_k10 | edges_k20 | edges_k40 | seconds | peak_rss_mib |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | G1 | 4540112 | 2728621 | 32416 | 62336 | 118161 | 5.6 | 239.3 |
| 27 | G2 | 4540112 | 2728621 | 37151 | 73652 | 145631 | 4.352 | 247.0 |
| 29 | G1 | 475868 | 310650 | 18116 | 34598 | 65532 | 0.687 | 653.6 |
| 29 | G2 | 475868 | 310650 | 22061 | 43173 | 81931 | 0.604 | 653.6 |
| 865 | G1 | 7493125 | 5145901 | 39267 | 76596 | 148021 | 10.269 | 847.6 |
| 865 | G2 | 7493125 | 5145901 | 43495 | 86333 | 170325 | 8.912 | 838.6 |
| 867 | G1 | 1816546 | 1555473 | 32221 | 62038 | 118467 | 3.86 | 579.5 |
| 867 | G2 | 1816546 | 1555473 | 38115 | 75113 | 144394 | 2.514 | 614.6 |

`pair_work`, `candidate_undirected`, số cạnh theo k, thời gian và RSS giữ nguyên từ CSV. Thời gian là phép dựng đồ thị đã ghi trong Phase 1, không bao gồm Louvain hay chạy cơ chế matching.

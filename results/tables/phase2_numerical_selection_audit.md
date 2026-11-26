# Post-held-out numerical selection audit

Diagnostic only. A 1e-12 pool-fraction tolerance would treat the listed positive gains around 1e-19 as numerical zero, then favor smaller dev damage. The frozen configuration and all held-out results remain unchanged; no alternative was evaluated on held-out.

| mechanism | status | graph_method | k | resolution | beta0 | beta_coh | beta_conc | beta_S | beta_C | dev_mech_damage | dev_attack_gain | near_zero_candidate_count |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| soft_shapley | pre_frozen | G2 | 10 | 0.5 | -0.25 | 0.0 | 0.8 | 0.8 | 0.0 | 0.0492632400673635 | 1.7982560163090126e-19 | 8 |
| soft_shapley | lowest_damage_if_numeric_zero | G2 | 10 | 0.5 | -0.25 | 0.4 | 0.8 | 0.4 | 0.0 | 0.0385845902172784 | 2.303087764239921e-19 | 8 |
| soft_full | pre_frozen | G2 | 10 | 0.5 | -0.25 | 0.0 | 0.8 | 0.8 | -0.6 | 0.0499311655138775 | 1.7855534212666056e-19 | 40 |
| soft_full | lowest_damage_if_numeric_zero | G2 | 10 | 0.5 | -0.25 | 0.4 | 0.8 | 0.4 | -0.6 | 0.0383029927612743 | 2.2853981105273654e-19 | 40 |

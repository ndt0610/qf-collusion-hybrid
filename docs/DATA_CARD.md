# Data card — Grants Data Portal historical snapshot

`data_license: "unverified"`. The portal [repository](https://github.com/nexusdatalabs/grantsdataportal.xyz/tree/a67cb98e19e757c9c94c4cf178b914e845697b00) says MIT for its code. The separate downloadable Parquet files have no clearly verified separate license. Raw and processed data remain excluded from Git; the project contains URLs and SHA-256 hashes in `data/manifests/sources.json`.

Source: https://grantsdataportal.xyz/ and its donations, rounds and applications Parquet files. The snapshot covers Grants Stack era events, not all historical Gitcoin grants. `donor_address` is a wallet, not a verified person. `amount_in_usd` is the portal's converted USD amount; original `amount` and `token_address` are preserved. The snapshot has no ground-truth Sybil labels, and upstream Sybil filtering history is unknown. Current application status can differ from status at contribution time.

Phase 0B downloaded 497,347 donation records (57,137,200-byte file; SHA-256 `34a615c30a6cd34788b9367c65423fd03272ea7fc72497b46d09a78b174aa189`). It contains 104,737 case-normalized donor addresses and 2,568 project IDs. Round `42161:27` has 13,197 records, 3,751 donor addresses, 46 projects, and 10 rows with zero USD; all 13,197 link to an application whose current status is `APPROVED`. A single transaction receipt was spot-checked against Arbitrum RPC; this does not audit the full dataset.

Phase 1 preprocessing keeps finite positive USD, current approved application with matching project ID, and timestamps in the recorded donation window. It aggregates all events for one `(donor,project)` using Decimal before square roots. Every exclusion is counted in `results/tables/phase1_data_graph_profile.csv`. The original raw file stays untouched in `data/raw/`.

Known limits: multiple wallets per person; one transaction can contain several donations; USD valuation may be imperfect; some round metadata windows may disagree with donation timestamps (notably round `42161:23`, excluded from Phase 1 candidates); no labels for genuine collusion or Sybil; a real-data background is not a clean control group.

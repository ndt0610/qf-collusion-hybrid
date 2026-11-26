# Third-party notices

The project depends on NumPy, SciPy, NetworkX, pandas, PyArrow, psutil, matplotlib, pytest, eth-utils and pycryptodome under their respective licenses. Versions are pinned in `requirements.lock`. Use `pip show` and package license files from the installed environment for the full notices. Phase 3 also depends on Hardhat, ethers and the OpenZeppelin Contracts and Merkle Tree packages; versions are pinned in `evm/package-lock.json`. Solidity imports OpenZeppelin `Ownable`, `ReentrancyGuard`, and `MerkleProof` without copying their implementations into this repository.

The optional local presentation UI uses Streamlit and Plotly, with versions pinned in `requirements-ui.txt`.

Mathematical mechanisms are described from [Buterin (2019)](https://ethresear.ch/t/pairwise-coordination-subsidies-a-new-quadratic-funding-design/5553) and [Miller, Weyl, Kanich (2025)](https://arxiv.org/html/2509.18343v1). No code from the GPL-3.0 `Jmiller4/qf-variants` repository is included. Prior Phase 0B research did read that repository; this project therefore does not claim a strict clean-room process. The CO-QF implementation here follows the published Algorithm 2 and tests handwritten examples.

The Grants Data Portal application repository is MIT licensed. The license of its separately hosted Parquet data is **unverified**; raw data is excluded from this repository. See `docs/DATA_CARD.md`.

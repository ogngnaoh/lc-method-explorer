# Local setup and verification

Static figures, reports and the presentation can be reviewed directly on GitHub. The optional app runs on your own computer.

## Use the frozen experiment

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/). On macOS, install OpenMP for XGBoost with `brew install libomp`.

From the repository root:

```sh
uv sync --frozen
uv run --frozen python scripts/download_models.py
uv run --frozen python scripts/verify_results.py
uv run --frozen pytest -q tests
uv sync --project demo --frozen
uv run --project demo --frozen pytest -q demo/test_demo.py
cd demo
uv run --frozen streamlit run app.py
```

Open `http://127.0.0.1:8501`. Start from `demo/` to apply the loopback-only server and telemetry-off configuration. Stop with Ctrl+C. Internet access is needed for initial packages and artifact downloads; inference is local afterward.

The downloader verifies the release archive and each member against committed SHA256 checksums before installing. It will not overwrite different local artifacts. Joblib models can execute code when loaded: use only the trusted project release. `verify_results.py` then checks the original code/input provenance, model hashes, holdout membership, measured labels, every saved model prediction and aggregate MAE. Demo tests also check missing measurements, new structures and invalid predictions.

## Rebuild the experiment separately

Keep the published run unchanged. In a separate copy, download and check the raw data:

```sh
uv run --frozen python scripts/download_mcmrt.py
uv run --frozen python -m chromrt.pipeline
```

The pipeline prepares tables, verifies the fixed group assignments and evaluates the development median baseline. It refuses incompatible prepared data or splits.

For a refit, move **only that copy's** `reports/experiments/mcmrt-v3-compound-v1/` and `models/mcmrt-v3-compound-v1/` folders to a backup location, then run:

```sh
uv run --frozen python -m chromrt.experiment development
uv run --frozen python -m chromrt.experiment final
uv run --frozen python scripts/verify_results.py
uv run --frozen python scripts/plot_results.py
```

The experiment refuses to overwrite existing selection/final records. Repeating this protocol is a reproduction, not a new untouched test. Further tuning requires a new experiment version and independent evaluation data. Serialization hashes, timestamps and small numeric differences can vary across environments.

## Evidence and portability

The original experiment ran on an Apple M2 Pro with 16 GB RAM and four CPU workers. Development comparison took 49.4 seconds; final refitting/evaluation took 5.9 seconds, excluding setup and imports. These timings describe this run only.

The root lockfile fixes the experiment libraries; the separate demo lockfile adds Streamlit while preserving model-library versions. The release checks document verification in a clean repository copy on the same machine. Independent operating-system/hardware reproduction remains unverified.

See [release verification](RELEASE_QA.md) for the exact checks performed. `data/source/mcmrt_manifest.json` records source provenance; all published experiment records remain in `reports/experiments/mcmrt-v3-compound-v1/`.

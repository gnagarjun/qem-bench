# Reproducibility

- **Seeds.** A root seed (`configs/default.yaml`, 20260601) feeds `SeedSequence(root, spawn_key=sha256(labels))` for every
  (block, instance, noise, N, repetition, comparison, method). Streams therefore do not depend on execution order.
  Tests check that identical configurations give bit-identical estimates and that repetitions differ.
- **Provenance.** Each run directory holds `config_resolved.json` (full config and hash), `environment.json` (Python, OS,
  CPU, package versions, git commit), `manifest.json` (SHA-256 and row counts of every Parquet file) and `validation_report.json`.
- **No silent overwrite.** A new run creates a fresh directory. `--resume` only completes missing chunks and refuses a changed configuration.
  Chunks are written atomically (via a temporary file and rename).
- **Aggregation manifest.** `results/aggregated/<name>/manifest.json` links aggregated outputs to the SHA-256 of their raw inputs.
  `scripts/validate_results.py` re-checks those hashes, re-validates the datasets, and confirms all 12 figures exist.
- **Large data.** Raw Parquet files (about 30 MB for the standard run) are git-ignored. Publish them on Zenodo or through Git LFS and record the DOI here.
  Aggregated tables and the demo subset are committed.
- **Timings** depend on the machine. They were measured on a 4-core aarch64 Linux container and are not comparable across hosts.

## Exact commands
```bash
uv sync --extra dev
uv run pytest                                   # 76 tests
uv run bash scripts/reproduce_all.sh            # regenerates results/, figures and paper tables
```

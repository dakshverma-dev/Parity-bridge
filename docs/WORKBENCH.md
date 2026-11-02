# Benchmark workbench

The `create` command runs the existing quick benchmark on CPU with three timing
repetitions. Surface runs use PyMatching at four distance/noise points.
qLDPC runs evaluate both BP+OSD decoders on BB[[72,12,6]] at two noise points.
See [the methodology](METHODOLOGY.md) for code and timing definitions and
[validation](VALIDATION.md) for the scope of the existing experiments.

Each immutable run directory contains a versioned manifest, the harness metadata,
the original benchmark CSV, and, for measured runs, ordered shot evidence. The
manifest records the command, harness commit and artifact SHA-256 hashes. The
metadata retains the source fingerprint, Git dirty flag, sampling seed, software
versions, hardware, timing settings and parameter grid. Run IDs use lowercase
letters, digits, hyphens and underscores. Repeated measurements need new IDs.

The builder collects raw output in scratch space, validates a staged copy and
renames it into the bundle directory on the same volume. This keeps incomplete
runs out of the viewer. SHA-256 checks artifact integrity against the manifest.
The manifest is local provenance and has no cryptographic signature.

## Import a corrected measurement

The import path accepts recorded CSVs using `median-paired-v2` and preserves
their bytes. Select one code family per import. The `historical` and `fixture`
labels remain visible in comparisons and exports.

```bash
python scripts/build_release_report.py create --family surface --run-id corrected-cpu --results-dir results/local-cpu-corrected --source-kind historical --command "Unrecorded invocation. Run settings are in docs/RESULTS_local-cpu-corrected.md."
python scripts/build_release_report.py validate release_app/data/runs/corrected-cpu
```

Record the actual command when it is available. The corrected CPU example uses
the settings from [published results](RESULTS_local-cpu-corrected.md).
Earlier T4 timing protocols remain archived in [benchmark history](HISTORY.md).
The release builder's original `--junit` invocation and the viewer's legacy
`/health`, `/api/reports/latest` and `/api/reports/latest/raw` endpoints still
read schema-version-1 release reports from `RELEASE_DATA_DIR`.

## Reading a comparison

The two runs must declare the same code family, noise model, protocol and set of
parameter points. You can choose a different decoder in each run. At each point
the viewer shows logical error counts, shots and the published Wilson 95%
interval. These intervals describe each decoder's binomial error proportion.

A measured run fingerprints the ordered syndrome and ground-truth sample arrays.
For a matched fingerprint and shot count, the viewer counts shots where exactly
one decoder recorded a logical failure. A seed alone can produce different
samples across Stim builds or machines. Imported aggregates have no verified
shot-level pairing. Equal aggregate counts alone establish neither equal error
locations nor statistical equivalence.

Speed ratios require measured runs with matching hardware identity, dependencies,
ordered shots and timing settings. The batch factor is right median shots/s
divided by left median shots/s. The single-shot p50 factor is left latency divided
by right latency. Below 1 means the right side was slower. Repetitions across
saved runs are separate measurements, and their ratio has no confidence interval.
CPU scheduling and host load can affect the result.

The CPU runs have no host/device transfer. qLDPC total batch timings include
fallback. The qLDPC hybrid also records a separate CPU diagnostic pass for the
fallback call and its input gather and output assignment. It is outside the
timing repetitions and should not be added to the total. Historical GPU
measurements retain their original end-to-end timings including transfers.
The workbench does not generate new GPU bundles or isolate historical transfer
costs. CUDA test coverage is recorded in the verification record.

# SmartDistServe complete code and data bundle

Extract this ZIP into a folder and run commands from the extracted project root.
All evaluated datasets are synthetic. No actual ShareGPT, HumanEval, or LongBench
data is included because none was used in the study.

## Contents

- smartdistserve/: all simulator, scheduler, workload, metrics, experiment, report, and CLI code.
- tests/: the 38 automated tests.
- scripts/: graph generation, independent metric auditing, and full trace replay.
- configs/experiment.json: exact profiles, arrival rates, seeds, and ablations.
- data/synthetic/: readable CSV exports of all input instances and all policy outcomes.
- results/reference/: original traces, per-request outcomes, all 440 runs, summaries,
  paired comparisons, source/trace/output hashes, logs, graphs, and validation evidence.
- research/: measured manuscript source, template, and code/results review.
- output/pdf/: final formal PDF, its generation code, extracted text, and PDF validation.
- pyproject.toml: Python package metadata; simulator has no external dependencies.
- requirements-plots.txt: exact plotting dependency versions.
- BUNDLE_MANIFEST.json: SHA-256 hash and size of each packaged file.

## Reproduce

Python 3.11+ is required for the simulator and tests. No GPU is required.

```text
python -m unittest discover -s tests -v
python -m smartdistserve experiment --config configs/experiment.json
python -m smartdistserve report --results results/reference
python scripts/audit_results.py --results results/reference
python scripts/replay_results.py --results results/reference
```

For plots, install requirements-plots.txt and run scripts/plot_results.py.
PDF generation additionally requires ReportLab and pypdf; its script uses
Windows Segoe UI fonts. It is supplied for transparency but is not required
to reproduce simulation measurements. A virtual environment, Git metadata,
temporary render files, caches, and unrelated runtime packages are excluded.

The simulator models token counts and event times; it does not generate LLM text.
Service coefficients are uncalibrated assumptions. See README.md and the paper
for interpretation limits and established prior scheduling work.

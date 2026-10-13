"""Export the exact synthetic trace instances and package the complete research artifact."""
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "synthetic"
OUT = ROOT / "output" / "package"
DATA.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
with gzip.open(ROOT / "results/reference/traces.jsonl.gz", "rt", encoding="utf-8") as f:
    traces = [json.loads(line) for line in f]
rows = []
for trace in traces:
    suite, condition, rate, seed = trace["trace_id"].split(":")
    for record in trace["records"]:
        rows.append({"trace_id": trace["trace_id"], "trace_sha256": trace["sha256"],
                     "source": "synthetic", "suite": suite, "condition": condition,
                     "offered_rate": float(rate), "seed": int(seed), **record})
columns = list(rows[0])


def write_csv(path, records):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


write_csv(DATA / "all_synthetic_requests.csv", rows)
counts = Counter(row["profile"] for row in rows)
for profile in ("sharegpt", "humaneval", "longbench"):
    write_csv(DATA / f"{profile}_synthetic.csv", [row for row in rows if row["profile"] == profile])
with gzip.open(ROOT / "results/reference/requests.csv.gz", "rt", encoding="utf-8", newline="") as src:
    with (DATA / "all_policy_outcomes.csv").open("w", encoding="utf-8", newline="") as dst:
        for chunk in iter(lambda: src.read(1024*1024), ""):
            dst.write(chunk)
outcome_rows = 0
with (DATA / "all_policy_outcomes.csv").open(encoding="utf-8", newline="") as f:
    outcome_rows = sum(1 for _ in csv.DictReader(f))
index = {"source": "synthetic", "actual_benchmark_data_used": False,
         "stored_trace_instances": len(traces), "distinct_full_trace_hashes": len({t["sha256"] for t in traces}),
         "input_request_instances": len(rows), "input_instances_by_profile": dict(counts),
         "policy_outcome_rows": outcome_rows, "policy_runs": 440,
         "files": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in sorted(DATA.glob("*.csv"))}}
(DATA / "DATA_INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
(DATA / "README.md").write_text("""# Exact synthetic data used by SmartDistServe

No actual ShareGPT, HumanEval, or LongBench datasets were obtained or used.
These files contain generated token-length requests inspired by chat, code,
and long-context applications. They contain no actual prompts or answers.

- all_synthetic_requests.csv: all 37,350 input request instances across the 110 stored condition/seed trace instances.
- sharegpt_synthetic.csv: chat-profile input instances.
- humaneval_synthetic.csv: code-profile input instances.
- longbench_synthetic.csv: long-context input instances.
- all_policy_outcomes.csv: all 149,400 saved request outcomes from four policies, including warmup requests and failures.
- DATA_INDEX.json: counts, provenance, file sizes, and SHA-256 hashes.

The uncompressed outcome CSV is exported locally and included in the full ZIP
bundle. Git tracks its exact compressed original at
results/reference/requests.csv.gz to avoid a redundant large text file.
Run python output/package/build_bundle.py to recreate all CSV exports.

The three profile CSVs partition all_synthetic_requests.csv; they are not additional data.
Each input request has a composite identity (trace_id, request_id). Each outcome
has identity (trace_id, policy, request_id). Some trace instances deliberately
reuse the same realization for paired ablations; 110 stored instances have 95
distinct hashes when estimates are included. Do not treat repeated realizations
or the four policy outcomes as independent experimental samples.

Input fields include arrival time (seconds), input/output token counts,
request-specific TTFT/TPOT SLOs (seconds), prefill-duration estimates (seconds),
and output-token estimates. The scheduler does not receive realized output length.
The CSVs preserve the exact saved input values; workload definitions and all
random seeds are in configs/experiment.json and results/reference/manifest.json.
The original replayable inputs are results/reference/traces.jsonl.gz.

For importing one selected trace with the CLI, filter all_synthetic_requests.csv
to one trace_id first. Importing all traces as a single run is invalid because
request IDs and clocks reset for each experiment.
""", encoding="utf-8")
guide = """# SmartDistServe complete code and data bundle

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
"""
(OUT / "START_HERE.md").write_text(guide, encoding="utf-8")
selected = []
for folder in ("smartdistserve", "tests", "scripts", "configs", "research", "results/reference", "data/synthetic", "output/pdf"):
    selected.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts
                    and p.suffix not in (".pyc", ".pyo"))
selected.extend(ROOT / name for name in ("README.md", "pyproject.toml", "requirements-plots.txt", ".gitignore", ".gitattributes"))
selected.extend([Path(__file__).resolve(), OUT / "START_HERE.md"])
selected = sorted(set(selected))


def archive_name(path):
    return "START_HERE.md" if path == OUT / "START_HERE.md" else path.relative_to(ROOT).as_posix()


manifest = {archive_name(p): {"bytes": p.stat().st_size,
              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected}
manifest_path = OUT / "BUNDLE_MANIFEST.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
zip_path = OUT / "SmartDistServe_All_Code_and_Data.zip"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in selected:
        z.write(p, archive_name(p))
    z.write(manifest_path, "BUNDLE_MANIFEST.json")
with zipfile.ZipFile(zip_path) as z:
    if z.testzip() is not None:
        raise RuntimeError("ZIP integrity check failed")
    for p in selected:
        assert hashlib.sha256(z.read(archive_name(p))).hexdigest() == manifest[archive_name(p)]["sha256"]
print(json.dumps({"zip": str(zip_path), "bytes": zip_path.stat().st_size, "files": len(selected)+1,
                  "input_instances": len(rows), "outcome_rows": outcome_rows,
                  "profile_counts": dict(counts), "integrity": "pass"}, indent=2))

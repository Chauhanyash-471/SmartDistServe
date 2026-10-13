"""Paired seeded experiments, trace artifacts, per-request outcomes, and manifests."""
from dataclasses import asdict, replace
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys

from . import __version__
from .config import Hardware, Profile, SchedulerConfig, WorkloadConfig, positive
from .io import gzip_text, write_json
from .metrics import evaluate
from .scheduling import POLICIES
from .simulator import simulate
from .workloads import generate, trace_hash


def source_hashes(root):
    files = []
    for folder in ("smartdistserve", "scripts", "tests", "configs"):
        files.extend(p for p in (root / folder).rglob("*") if p.suffix in (".py", ".json"))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    # Unknown dataclass fields intentionally fail rather than silently changing experiments.
    Hardware(**cfg.get("hardware", {}))
    SchedulerConfig(**cfg.get("scheduler", {}))
    for name, value in cfg["profiles"].items():
        Profile(name=name, **value)
    WorkloadConfig(**cfg.get("workload", {}))
    return cfg


def run_experiments(config_path, output, *, progress=print):
    cfg = load_config(config_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent.parent
    h = Hardware(**cfg.get("hardware", {}))
    sc = SchedulerConfig(**cfg.get("scheduler", {}))
    profiles = {name: Profile(name=name, **p) for name, p in cfg["profiles"].items()}
    base = WorkloadConfig(**cfg.get("workload", {}))
    policies = cfg.get("policies", list(POLICIES))
    seeds = cfg["seeds"]
    if not policies or len(set(policies)) != len(policies) or set(policies) - set(POLICIES):
        raise ValueError("policies must be unique known policies")
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be nonempty and unique")
    cases = []
    for name, values in cfg["workloads"].items():
        rates = values["rates"]
        if not rates or len(set(rates)) != len(rates):
            raise ValueError("rates must be nonempty and unique per workload")
        for rate in rates:
            cases.append(("main", name, rate, values["weights"], {}, {}, {}))
    for values in cfg.get("ablations", []):
        cases.append(("ablation", values["name"], values["rate"], values["weights"],
                      values.get("workload", {}), values.get("hardware", {}),
                      values.get("scheduler", {})))
    if not cases:
        raise ValueError("at least one experiment condition is required")
    if len({(suite, name, rate) for suite, name, rate, *_ in cases}) != len(cases):
        raise ValueError("duplicate experiment conditions")
    # Validate every case before creating the data files.
    for _, _, rate, weights, wc, hc, sched in cases:
        replace(base, **{**wc, "rate": rate})
        replace(h, **hc)
        replace(sc, **sched)
        if not weights or set(weights) - set(profiles):
            raise ValueError("unknown/empty profile weights")
        for weight in weights.values():
            positive("profile weight", weight, zero=True)
        if sum(weights.values()) <= 0:
            raise ValueError("at least one profile weight must be positive")
    for seed in seeds:
        replace(base, seed=seed)
    total = len(cases) * len(seeds) * len(policies)
    runs, trace_index = [], []
    with gzip_text(output / "requests.csv.gz") as request_file, \
            gzip_text(output / "traces.jsonl.gz") as trace_file:
        writer = None
        for suite, name, rate, weights, wc, hc, sched in cases:
            case_h, case_sc = replace(h, **hc), replace(sc, **sched)
            for seed in seeds:
                w = replace(base, **{**wc, "rate": rate, "seed": seed})
                requests = generate(w, profiles, weights, case_h)
                sha = trace_hash(requests)
                trace_id = f"{suite}:{name}:{rate:g}:{seed}"
                meta = {"trace_id": trace_id, "source": "synthetic", "sha256": sha,
                        "workload": asdict(w), "weights": weights, "requests": len(requests)}
                trace_index.append(meta)
                trace_file.write(json.dumps({**meta, "records": [asdict(r) for r in requests]},
                                            sort_keys=True, allow_nan=False) + "\n")
                for policy in policies:
                    result = simulate(requests, case_h, policy, case_sc)
                    metrics = evaluate(result, case_h, start=w.warmup, stop=w.duration)
                    meta_run = {"suite": suite, "workload": name, "offered_rate": rate,
                                "seed": seed, "policy": policy, "trace_id": trace_id,
                                "trace_sha256": sha, "source": "synthetic"}
                    runs.append({**meta_run, "hardware": asdict(case_h),
                                 "scheduler": asdict(case_sc), "metrics": metrics})
                    for record in result.records:
                        row = {**meta_run, "measured": int(w.warmup <= record.request.arrival < w.duration),
                               **record.row()}
                        if writer is None:
                            writer = csv.DictWriter(request_file, fieldnames=list(row))
                            writer.writeheader()
                        writer.writerow(row)
                progress(f"{len(runs)}/{total}: {suite}/{name}, rate={rate:g}, seed={seed}")
    write_json(output / "runs.json", runs)
    scalar_rows = [{**{k: run[k] for k in ("suite", "workload", "offered_rate", "seed", "policy", "source")},
                    **{k: v for k, v in run["metrics"].items() if not isinstance(v, dict)}} for run in runs]
    with (output / "runs.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(scalar_rows[0]))
        writer.writeheader()
        writer.writerows(scalar_rows)
    manifest = {"version": __version__, "source": "synthetic", "config": cfg,
                "python": sys.version, "platform": platform.platform(),
                "run_count": len(runs), "trace_count": len(trace_index),
                "traces": trace_index, "source_sha256": source_hashes(root),
                "output_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                  for name in ("runs.json", "runs.csv", "requests.csv.gz", "traces.jsonl.gz")}}
    write_json(output / "manifest.json", manifest)
    return runs

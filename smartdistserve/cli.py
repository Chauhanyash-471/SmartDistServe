"""CLI entry points; simulator execution requires only Python's standard library."""
import argparse
from dataclasses import asdict, replace
import csv
import json
from pathlib import Path

from .config import Hardware, Profile, SchedulerConfig, WorkloadConfig, default_profiles
from .experiments import run_experiments
from .io import write_json
from .metrics import evaluate
from .reporting import report
from .scheduling import POLICIES
from .simulator import simulate
from .workloads import generate, load_trace, trace_hash


def main(argv=None):
    parser = argparse.ArgumentParser(description="SmartDistServe synthetic research simulator")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="one synthetic run or explicitly labeled CSV trace")
    run.add_argument("--policy", choices=POLICIES, default="smart")
    run.add_argument("--profile", choices=(*default_profiles(), "mixed"), default="mixed")
    run.add_argument("--rate", type=float)
    run.add_argument("--duration", type=float)
    run.add_argument("--warmup", type=float)
    run.add_argument("--seed", type=int)
    run.add_argument("--config", help="JSON overrides for hardware, scheduler, profiles, workload")
    run.add_argument("--output", default="results/single")
    run.add_argument("--trace", help="CSV columns match the Request dataclass")
    run.add_argument("--source", choices=("synthetic", "empirical"))
    run.add_argument("--provenance", help="source URL/path, tokenizer, collection and estimate method")
    experiment = sub.add_parser("experiment", help="run the entire paired seeded suite")
    experiment.add_argument("--config", default="configs/experiment.json")
    experiment.add_argument("--output", default="results/reference")
    rep = sub.add_parser("report", help="generate measured tables and the research draft")
    rep.add_argument("--results", default="results/reference")
    rep.add_argument("--draft", default="research/SmartDistServe.md")
    args = parser.parse_args(argv)
    try:
        if args.command == "experiment":
            run_experiments(args.config, args.output)
        elif args.command == "report":
            report(args.results, args.draft)
        else:
            cfg = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
            h, sc = Hardware(**cfg.get("hardware", {})), SchedulerConfig(**cfg.get("scheduler", {}))
            profiles = default_profiles()
            profiles.update({name: Profile(name=name, **p) for name, p in cfg.get("profiles", {}).items()})
            overrides = {name: getattr(args, name) for name in ("rate", "duration", "warmup", "seed")
                         if getattr(args, name) is not None}
            w = WorkloadConfig(**{**cfg.get("workload", {}), **overrides})
            if args.trace:
                if not args.source or not args.provenance:
                    parser.error("--trace requires --source and --provenance")
                requests = load_trace(args.trace, source=args.source, provenance=args.provenance)
                if any(r.arrival >= w.duration for r in requests):
                    raise ValueError("trace arrivals must be inside --duration")
                source, provenance = args.source, args.provenance
            else:
                weights = {"sharegpt": .5, "humaneval": .25, "longbench": .25} if args.profile == "mixed" else {args.profile: 1}
                requests = generate(w, profiles, weights, h)
                source, provenance = "synthetic", "Clipped lognormal lengths; Poisson/thinned periodic Poisson arrivals"
            result = simulate(requests, h, args.policy, sc)
            metrics = evaluate(result, h, start=w.warmup, stop=w.duration)
            output = Path(args.output)
            output.mkdir(parents=True, exist_ok=True)
            write_json(output / "run.json", {"source": source, "provenance": provenance,
                       "trace_sha256": trace_hash(requests), "policy": args.policy,
                       "hardware": asdict(h), "scheduler": asdict(sc), "workload": asdict(w),
                       "metrics": metrics})
            with (output / "requests.csv").open("w", newline="", encoding="utf-8") as f:
                if result.records:
                    writer = csv.DictWriter(f, fieldnames=list(result.records[0].row()))
                    writer.writeheader()
                    writer.writerows(s.row() for s in result.records)
            print(json.dumps(metrics, indent=2, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()

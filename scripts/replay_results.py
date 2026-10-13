"""Replay saved traces and compare exact metrics; default replays every policy run."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smartdistserve.config import Hardware, SchedulerConfig
from smartdistserve.metrics import evaluate
from smartdistserve.simulator import simulate
from smartdistserve.workloads import Request, trace_hash


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results/reference")
    p.add_argument("--limit", type=int, default=0, help="0 replays all runs")
    args = p.parse_args()
    if args.limit < 0:
        p.error("limit must be nonnegative")
    folder = Path(args.results)
    runs = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    if args.limit:
        runs = runs[:args.limit]
    by_trace = defaultdict(list)
    for run in runs:
        by_trace[run["trace_id"]].append(run)
    failures, checked = [], 0
    with gzip.open(folder / "traces.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)
            if trace["trace_id"] not in by_trace:
                continue
            requests = [Request(**r) for r in trace["records"]]
            if trace_hash(requests) != trace["sha256"]:
                failures.append(f"trace hash: {trace['trace_id']}")
            for run in by_trace[trace["trace_id"]]:
                h = Hardware(**run["hardware"])
                result = simulate(requests, h, run["policy"], SchedulerConfig(**run["scheduler"]))
                metrics = evaluate(result, h, start=trace["workload"]["warmup"], stop=trace["workload"]["duration"])
                if metrics != run["metrics"]:
                    failures.append(f"metrics: {trace['trace_id']}:{run['policy']}")
                checked += 1
            print(f"Replayed {checked}/{len(runs)} runs", flush=True)
    if checked != len(runs):
        failures.append("missing saved traces")
    result = {"runs_replayed": checked, "exact_metrics_match": not failures, "failures": failures}
    (folder / "replay.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())

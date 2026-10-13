"""Independent result audit from serialized request timelines and input traces.

Uses only the standard library and deliberately does not call evaluate().
"""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def quantile(values, q=.95):
    values = sorted(values)
    if not values:
        return None
    i = (len(values) - 1) * q
    return values[int(i)] * (1 - i % 1) + values[math.ceil(i)] * (i % 1)


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9)


def audit(folder):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    runs = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    checks = 0
    failures = []

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    for name, sha in manifest["output_sha256"].items():
        check(hashlib.sha256((folder / name).read_bytes()).hexdigest() == sha, f"output hash: {name}")
    root = Path(__file__).resolve().parent.parent
    for name, sha in manifest["source_sha256"].items():
        check((root / name).exists() and hashlib.sha256((root / name).read_bytes()).hexdigest() == sha,
              f"source changed since experiment: {name}")
    traces = {}
    with gzip.open(folder / "traces.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)
            payload = json.dumps(trace["records"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            check(hashlib.sha256(payload).hexdigest() == trace["sha256"], f"trace hash: {trace['trace_id']}")
            traces[trace["trace_id"]] = trace
    rows = defaultdict(list)
    with gzip.open(folder / "requests.csv.gz", "rt", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[(row["trace_id"], row["policy"])].append(row)
    check(len(runs) == manifest["run_count"], "run count")
    check(len(traces) == manifest["trace_count"], "trace count")
    expected_policies = set(manifest["config"].get("policies", ["fcfs", "sjf", "edf", "smart"]))
    for trace_id in traces:
        check({r["policy"] for r in runs if r["trace_id"] == trace_id} == expected_policies,
              f"missing policy: {trace_id}")
    for run in runs:
        key = (run["trace_id"], run["policy"])
        all_rows = rows[key]
        trace = traces[run["trace_id"]]
        m, h = run["metrics"], run["hardware"]
        check(len(all_rows) == m["total_requests"] == trace["requests"], f"completion count {key}")
        check(len({r["request_id"] for r in all_rows}) == len(all_rows), f"duplicate request {key}")
        check(run["trace_sha256"] == trace["sha256"], f"run trace identity {key}")
        expected = {r["request_id"]: r for r in trace["records"]}
        measured, slo = [], []
        ttfts, tpots, waits, gaps, slowdowns = [], [], [], [], []
        pre_intervals = defaultdict(list)
        profile_groups, length_groups = defaultdict(list), defaultdict(list)
        ttft_ok, tpot_ok = [], []
        for row in all_rows:
            rid = int(row["request_id"])
            arrival, ps, first, completion = (float(row[name]) for name in ("arrival", "prefill_start", "first_token", "completion"))
            input_tokens, output_tokens = int(row["input_tokens"]), int(row["output_tokens"])
            check(close(arrival, expected[rid]["arrival"]) and input_tokens == expected[rid]["input_tokens"]
                  and output_tokens == expected[rid]["output_tokens"], f"input mismatch {key}:{rid}")
            check(arrival <= ps <= first <= completion, f"timeline {key}:{rid}")
            pre_service = h["prefill_overhead"] + input_tokens / h["prefill_tokens_per_second"] + h["prefill_quadratic"] * (input_tokens / 4096) ** 2
            check(close(first - ps, pre_service), f"prefill duration {key}:{rid}")
            pre_intervals[int(row["prefill_gpu"])].append((ps, first))
            wait, tpot = ps - arrival, None
            isolated = pre_service
            if output_tokens > 1:
                ready, ds = float(row["decode_ready"]), float(row["decode_start"])
                check(first <= ready <= ds <= completion, f"decode timeline {key}:{rid}")
                transfer = h["transfer_latency"] + input_tokens * h["kv_bytes_per_token"] / h["transfer_bytes_per_second"]
                check(close(ready - first, transfer), f"transfer duration {key}:{rid}")
                wait += ds - ready
                tpot = (completion - first) / (output_tokens - 1)
                # Independent closed form of isolated context-dependent decode time.
                steps = output_tokens - 1
                isolated += transfer + steps * h["decode_base"] + h["decode_context_increment"] * (
                    steps * input_tokens + steps * (steps + 1) / 2)
            check(close(first - arrival, float(row["ttft_s"])), f"TTFT {key}:{rid}")
            check(close(tpot, float(row["tpot_s"]) if row["tpot_s"] else None), f"TPOT {key}:{rid}")
            check(close(wait, float(row["waiting_s"])), f"waiting {key}:{rid}")
            ok1 = first - arrival <= float(row["ttft_slo"]) + 1e-12
            ok2 = tpot is None or tpot <= float(row["tpot_slo"]) + 1e-12
            ok = ok1 and ok2
            check(ok == bool(int(row["slo_met"])), f"SLO {key}:{rid}")
            measured_flag = trace["workload"]["warmup"] <= arrival < trace["workload"]["duration"]
            check(measured_flag == bool(int(row["measured"])), f"cohort {key}:{rid}")
            if measured_flag:
                measured.append(row)
                ttfts.append(first - arrival)
                if tpot is not None:
                    tpots.append(tpot)
                waits.append(wait)
                gaps.append(float(row["max_token_gap_s"]))
                slowdowns.append((completion - arrival) / isolated)
                slo.append(ok)
                ttft_ok.append(ok1)
                tpot_ok.append(ok2)
                profile_groups[row["profile"]].append((ok, wait))
                size = "short_<=512" if input_tokens <= 512 else ("medium_513_2048" if input_tokens <= 2048 else "long_>2048")
                length_groups[size].append((ok, wait))
        for gpu, jobs in pre_intervals.items():
            jobs.sort()
            check(all(a[1] <= b[0] + 1e-10 for a, b in zip(jobs, jobs[1:])), f"prefill overlap {key}:{gpu}")
        n = len(measured)
        check(n == m["requests"], f"cohort count {key}")
        if not n:
            continue
        avg = lambda xs: sum(xs) / len(xs) if xs else None
        expected_metrics = {"ttft_mean_s": avg(ttfts), "ttft_p95_s": quantile(ttfts),
                            "tpot_mean_s": avg(tpots), "tpot_p95_s": quantile(tpots),
                            "waiting_p95_s": quantile(waits), "waiting_max_s": max(waits),
                            "slo_attainment": avg(slo), "ttft_attainment": avg(ttft_ok),
                            "tpot_attainment": avg(tpot_ok), "arrival_rate": n / m["measurement_seconds"],
                            "goodput_per_gpu": sum(slo) / (m["measurement_seconds"] * (h["prefill_gpus"] + h["decode_gpus"])),
                            "slowdown_p95": quantile(slowdowns), "max_token_gap_p95_s": quantile(gaps)}
        for label, groups in (("profile", profile_groups), ("length", length_groups)):
            rates = [avg([v[0] for v in group]) for group in groups.values()]
            expected_metrics[f"jain_{label}_slo"] = sum(rates) ** 2 / (len(rates) * sum(x*x for x in rates)) if sum(rates) else 0
            for name, group in groups.items():
                gm = m[f"{label}_metrics"][name]
                check(gm["requests"] == len(group) and close(gm["slo_attainment"], avg([x[0] for x in group]))
                      and close(gm["waiting_p95_s"], quantile([x[1] for x in group])), f"group {key}:{label}:{name}")
        for name, value in expected_metrics.items():
            check(close(value, m[name]), f"aggregate {key}:{name}")
    result = {"checks": checks, "failures": failures, "runs": len(runs), "traces": len(traces),
              "request_rows": sum(map(len, rows.values())),
              "assessment": "pass" if not failures else "fail"}
    (folder / "audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results/reference")
    result = audit(parser.parse_args().results)
    sys.exit(bool(result["failures"]))

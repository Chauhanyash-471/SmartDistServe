"""Seed-level means, t intervals, paired contrasts, and transparent reporting."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean, stdev

from .io import write_json

METRICS = ("ttft_mean_s", "ttft_p95_s", "tpot_mean_s", "tpot_p95_s", "slo_attainment",
           "goodput_per_gpu", "waiting_p95_s", "waiting_max_s", "jain_profile_slo",
           "jain_length_slo", "slowdown_p95", "max_token_gap_p95_s", "drain_seconds")
# Two-sided Student t critical values for 95% intervals, df=1..30.
T95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
       2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
       2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)


def interval(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "mean": None, "ci95_halfwidth": None}
    if len(values) == 1:
        return {"n": 1, "mean": values[0], "ci95_halfwidth": None}
    if len(values) > 31:
        raise ValueError("Student t table supports at most 31 seeds; extend table before aggregation")
    halfwidth = T95[len(values) - 2] * stdev(values) / math.sqrt(len(values))
    return {"n": len(values), "mean": mean(values), "ci95_halfwidth": halfwidth}


def summarize(runs):
    groups = defaultdict(list)
    for run in runs:
        groups[(run["suite"], run["workload"], run["offered_rate"], run["policy"])].append(run)
    summary = []
    for (suite, workload, rate, policy), values in sorted(groups.items()):
        summary.append({"suite": suite, "workload": workload, "offered_rate": rate, "policy": policy,
                        **{metric: interval([r["metrics"][metric] for r in values]) for metric in METRICS}})
    contrasts = []
    paired = defaultdict(dict)
    for run in runs:
        paired[(run["suite"], run["workload"], run["offered_rate"], run["seed"])][run["policy"]] = run
    differences = defaultdict(lambda: defaultdict(list))
    for (suite, workload, rate, _), policies in paired.items():
        if "fcfs" not in policies:
            continue
        for policy, run in policies.items():
            if policy == "fcfs":
                continue
            if run["trace_sha256"] != policies["fcfs"]["trace_sha256"]:
                raise ValueError("paired policies must use identical traces")
            for metric in METRICS:
                a, b = run["metrics"][metric], policies["fcfs"]["metrics"][metric]
                if a is not None and b is not None:
                    differences[(suite, workload, rate, policy)][metric].append(a - b)
    for (suite, workload, rate, policy), values in sorted(differences.items()):
        contrasts.append({"suite": suite, "workload": workload, "offered_rate": rate, "policy": policy,
                          **{metric: interval(values[metric]) for metric in METRICS}})
    return summary, contrasts


def report(results_dir, draft_path=None):
    results_dir = Path(results_dir)
    runs = json.loads((results_dir / "runs.json").read_text(encoding="utf-8"))
    manifest = json.loads((results_dir / "manifest.json").read_text(encoding="utf-8"))
    summary, contrasts = summarize(runs)
    write_json(results_dir / "summary.json", summary)
    write_json(results_dir / "paired_contrasts.json", contrasts)
    flat = []
    for row in summary:
        scalar = {k: row[k] for k in ("suite", "workload", "offered_rate", "policy")}
        for m in METRICS:
            scalar.update({f"{m}_{k}": v for k, v in row[m].items()})
        flat.append(scalar)
    with (results_dir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    sections = ["## Measured simulation results", "",
                f"Executed {len(runs)} policy runs on {manifest['trace_count']} synthetic traces. "
                f"Seeds: {manifest['config']['seeds']}. All results below were computed from `runs.json`.", "",
                "Each cell is a mean across seeds. Intervals in `summary.csv` are two-sided 95% Student t "
                "intervals on seed-level statistics; tail percentiles are averaged across runs, not pooled. "
                "These intervals describe workload sampling variability, not hardware-model uncertainty. "
                "No multiple-comparison correction is applied.", "",
                "### Main sweep (complete grid)", "",
                "| Synthetic profile | Rate req/s | Policy | TTFT mean s | TPOT mean s | SLO % | Goodput req/s/GPU | P95 wait s | Jain length SLO |",
                "|---|---:|---|---:|---:|---:|---:|---:|---:|"]

    def fmt(row, metric, scale=1, digits=3):
        value = row[metric]["mean"]
        return "NA" if value is None else f"{value * scale:.{digits}f}"

    for row in summary:
        if row["suite"] == "main":
            sections.append(f"| {row['workload']} | {row['offered_rate']:g} | {row['policy']} | "
                            f"{fmt(row, 'ttft_mean_s')} | {fmt(row, 'tpot_mean_s')} | "
                            f"{fmt(row, 'slo_attainment', 100, 1)} | {fmt(row, 'goodput_per_gpu')} | "
                            f"{fmt(row, 'waiting_p95_s')} | {fmt(row, 'jain_length_slo')} |")
    sections += ["", "### Priority policy versus FCFS", "",
                 "Differences below are paired by seed and trace. Positive SLO difference favors Smart; "
                 "positive waiting-time difference means Smart has worse tail waiting. These are descriptive "
                 "comparisons over the entire main grid, not a selected best case.", "",
                 "| Synthetic profile | Rate req/s | SLO difference percentage points (95% halfwidth) | P95 wait difference s (95% halfwidth) |",
                 "|---|---:|---:|---:|"]
    smart = [row for row in contrasts if row["suite"] == "main" and row["policy"] == "smart"]
    for row in smart:
        def delta(m, scale=1):
            v = row[m]
            if v["mean"] is None:
                return "NA"
            half = v["ci95_halfwidth"]
            return f"{v['mean'] * scale:+.3f} +/- {half * scale:.3f}" if half is not None else f"{v['mean'] * scale:+.3f} (n=1)"
        sections.append(f"| {row['workload']} | {row['offered_rate']:g} | "
                        f"{delta('slo_attainment', 100)} | {delta('waiting_p95_s')} |")
    gains = [r["slo_attainment"]["mean"] for r in smart if r["slo_attainment"]["mean"] is not None]
    if gains:
        wins = sum(x > 1e-12 for x in gains)
        losses = sum(x < -1e-12 for x in gains)
        sections += ["", f"Across {len(gains)} tested conditions, Smart's mean SLO attainment exceeds FCFS "
                     f"in {wins}, falls below it in {losses}, and ties in {len(gains)-wins-losses}. "
                     f"Paired mean differences range from {min(gains)*100:+.3f} to {max(gains)*100:+.3f} "
                     "percentage points. This does not establish universal superiority or novelty."]
    # Explain fixed, named conditions if present; values always come from runs.
    sections += ["", "### Interpretation of measured tradeoffs", ""]
    indexed = {(r["suite"], r["workload"], r["offered_rate"], r["policy"]): r for r in summary}
    for rate in (3, 6):
        rows = [indexed.get(("main", "mixed", rate, policy)) for policy in ("fcfs", "smart", "sjf", "edf")]
        if all(rows):
            fcfs, priority, sjf, edf = rows
            sections.append(f"At mixed rate {rate:g} req/s, mean joint SLO attainment is "
                            f"{fmt(fcfs, 'slo_attainment', 100, 2)}% (FCFS), "
                            f"{fmt(priority, 'slo_attainment', 100, 2)}% (Smart), "
                            f"{fmt(sjf, 'slo_attainment', 100, 2)}% (SJF), and "
                            f"{fmt(edf, 'slo_attainment', 100, 2)}% (EDF). "
                            f"Mean run P95 queue wait is {fmt(fcfs, 'waiting_p95_s')} s (FCFS), "
                            f"{fmt(priority, 'waiting_p95_s')} s (Smart), "
                            f"{fmt(sjf, 'waiting_p95_s')} s (SJF), and "
                            f"{fmt(edf, 'waiting_p95_s')} s (EDF). Aggregate attainment and tail waiting "
                            "therefore need to be assessed together; a higher successful-request rate "
                            "alone does not establish better fairness.")
            sections.append("")
    baseline = indexed.get(("main", "mixed", 3, "smart"))
    for name, label in (("no_aging", "Removing both aging mechanisms"),
                        ("no_duration", "Removing the duration term")):
        ablated = indexed.get(("ablation", name, 3, "smart"))
        if baseline and ablated:
            delta = ablated["slo_attainment"]["mean"] - baseline["slo_attainment"]["mean"]
            sections.append(f"{label} changes mean mixed-rate-3 Smart attainment from "
                            f"{fmt(baseline, 'slo_attainment', 100, 2)}% to "
                            f"{fmt(ablated, 'slo_attainment', 100, 2)}% ({delta*100:+.3f} percentage points). "
                            "This is one operating point, so it does not establish a general effect or "
                            "a statistically reliable component benefit.")
            sections.append("")
    sections += ["", "### Ablations at the configured mixed-workload rate", "",
                 "Every ablation includes all four policies and identical traces within that condition. "
                 "The table shows Smart only; full comparison data are retained in the summary and run files.", "",
                 "| Condition | SLO % | P95 wait s | Jain profile SLO | Jain length SLO |",
                 "|---|---:|---:|---:|---:|"]
    for row in summary:
        if row["suite"] == "ablation" and row["policy"] == "smart":
            sections.append(f"| {row['workload']} | {fmt(row, 'slo_attainment', 100, 1)} | "
                            f"{fmt(row, 'waiting_p95_s')} | {fmt(row, 'jain_profile_slo')} | "
                            f"{fmt(row, 'jain_length_slo')} |")
    sections += ["", "### Conservative tested-grid capacity diagnostic", "",
                 "For each workload/policy, select the largest offered rate for which **every seed** "
                 "attains at least 90% joint SLO success. Report offered rate divided by provisioned GPUs. "
                 "This finite, fully drained simulation is not a steady-state capacity measurement, and this "
                 "diagnostic is distinct from the cohort successful-request goodput above. 'None' means no "
                 "tested rate qualified, not zero capacity.", "",
                 "| Synthetic profile | Policy | Highest qualified tested rate req/s | Offered rate/GPU |",
                 "|---|---|---:|---:|"]
    qualified = defaultdict(list)
    grouped = defaultdict(list)
    for run in runs:
        if run["suite"] == "main":
            grouped[(run["workload"], run["policy"], run["offered_rate"])].append(run)
    pairs = set()
    for (name, policy, rate), values in grouped.items():
        pairs.add((name, policy))
        if all(v["metrics"]["slo_attainment"] is not None and v["metrics"]["slo_attainment"] >= .9 for v in values):
            h = values[0]["hardware"]
            qualified[(name, policy)].append((rate, rate / (h["prefill_gpus"] + h["decode_gpus"])))
    for name, policy in sorted(pairs):
        rates = qualified[(name, policy)]
        value = max(rates) if rates else None
        cells = f"{value[0]:g} | {value[1]:.3f}" if value else "None | None"
        sections.append(f"| {name} | {policy} | {cells} |")
    sections += ["", "The saved request logs include all warmup and measurement arrivals, failures, "
                 "single-token cases, first-token timestamps, decode admission, and final completion. "
                 "Use `python scripts/audit_results.py` to independently recompute the scalar metrics.", ""]
    text = "\n".join(sections)
    (results_dir / "measured_results.md").write_text(text, encoding="utf-8")
    if draft_path:
        template_path = Path(__file__).resolve().parent.parent / "research" / "draft_template.md"
        template = template_path.read_text(encoding="utf-8")
        if template.count("{{MEASURED_RESULTS}}") != 1:
            raise ValueError("draft template must contain exactly one measured results placeholder")
        Path(draft_path).parent.mkdir(parents=True, exist_ok=True)
        Path(draft_path).write_text(template.replace("{{MEASURED_RESULTS}}", text), encoding="utf-8")
    return summary
